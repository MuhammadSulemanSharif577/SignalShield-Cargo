
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../../../core/network/api_config.dart';

class AuthService {
  static const String _tokenKey = 'access_token';

  final FlutterSecureStorage _storage;

  final Dio _dio;

  AuthService({
    Dio? dio,
    FlutterSecureStorage? storage,
  })  : _storage = storage ?? const FlutterSecureStorage(),
        _dio = dio ??
            Dio(
              BaseOptions(
                baseUrl: ApiConfig.baseUrl,
                connectTimeout: const Duration(seconds: 15),
                receiveTimeout: const Duration(seconds: 15),
                sendTimeout: const Duration(seconds: 15),
                headers: {
                  'Content-Type': 'application/json',
                  'Accept': 'application/json',
                },
              ),
            ) {
    // The backend uses opaque bearer tokens, not JWTs.
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _storage.read(key: _tokenKey);

          if (options.path != ApiConfig.loginEndpoint &&
              !options.headers.containsKey('Authorization') &&
              token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }

          handler.next(options);
        },
        onError: (error, handler) async {
          if (error.response?.statusCode == 401 &&
              error.requestOptions.path != ApiConfig.loginEndpoint) {
            await _storage.delete(key: _tokenKey);
          }
          handler.next(error);
        },
      ),
    );
  }



  // SIGN IN

  Future<Map<String, dynamic>> signIn({
    required String identifier,
    required String password,
  }) async {
    return _postAndStoreToken(
      ApiConfig.loginEndpoint,
      {
        'email': identifier.trim(),
        'password': password,
      },
    );
  }

  Future<Map<String, dynamic>> changePassword({
    required String currentPassword,
    required String newPassword,
  }) {
    return _postAndStoreToken(ApiConfig.changePasswordEndpoint, {
      'currentPassword': currentPassword,
      'newPassword': newPassword,
    });
  }

  // COMMON POST REQUEST + TOKEN STORAGE

  Future<Map<String, dynamic>> _postAndStoreToken(
      String endpoint,
      Map<String, dynamic> requestData,
      ) async {
    try {
      final response = await _dio.post(
        endpoint,
        data: requestData,
      );

      if (response.data is! Map) {
        throw const AuthApiException(
          'Unexpected response received from the server.',
        );
      }

      final responseData = Map<String, dynamic>.from(response.data);

      final token = responseData['token'];

      if (token is! String || token.isEmpty) {
        throw const AuthApiException(
          'The server did not return an access token.',
        );
      }

      await _requireDriver(responseData['user'], token);

      // Password changes rotate the token, so always replace the stored value.
      await _storage.write(
        key: _tokenKey,
        value: token,
      );

      return responseData;
    } on DioException catch (error) {
      throw AuthApiException(_getErrorMessage(error), statusCode: error.response?.statusCode);
    }
  }

  // GET CURRENT AUTHENTICATED USER

  Future<Map<String, dynamic>> getCurrentUser() async {
    try {
      final response = await _dio.get(
        ApiConfig.currentUserEndpoint,
      );

      if (response.data is! Map) {
        throw const AuthApiException(
          'Unexpected user response received.',
        );
      }

      final user = Map<String, dynamic>.from(response.data);
      await _requireDriver(user, await getAccessToken());
      return user;
    } on DioException catch (error) {
      throw AuthApiException(_getErrorMessage(error), statusCode: error.response?.statusCode);
    }
  }

  // READ STORED TOKEN

  Future<String?> getAccessToken() async {
    return _storage.read(key: _tokenKey);
  }

  // LOGOUT

  Future<void> logout({String? token}) async {
    try {
      final bearer = token ?? await getAccessToken();
      if (bearer != null) {
        await _dio.post(
          ApiConfig.logoutEndpoint,
          options: Options(headers: {'Authorization': 'Bearer $bearer'}),
        );
      }
    } on DioException {
      // Local sign-out must still work when offline or already expired.
    } finally {
      await _storage.delete(key: _tokenKey);
    }
  }

  Future<void> _requireDriver(Object? user, String? token) async {
    final driverId = user is Map ? user['driverId'] : null;
    if (driverId is String && driverId.trim().isNotEmpty) return;
    // Reject before saving a new token; also remove any previously saved session.
    await logout(token: token);
    throw const AuthApiException(
      'This app is for driver accounts. Use the web app for staff access.',
      statusCode: 401,
    );
  }

  // API ERROR HANDLING

  String _getErrorMessage(DioException error) {
    final responseData = error.response?.data;

    if (responseData is Map) {
      final message = responseData['message'];
      if (message is String && message.isNotEmpty) return message;
      final detail = responseData['detail'];

      if (detail is String) {
        return detail;
      }

      if (detail != null) {
        return detail.toString();
      }
    }

    if (error.type == DioExceptionType.connectionTimeout ||
        error.type == DioExceptionType.receiveTimeout ||
        error.type == DioExceptionType.sendTimeout) {
      return 'Connection timed out. Please try again.';
    }

    if (error.type == DioExceptionType.connectionError) {
      return 'Unable to connect to the server. Check your internet connection and API address.';
    }

    if (error.response == null) {
      return 'Something went wrong while connecting to the server.';
    }

    return 'Server error: ${error.response?.statusCode}';
  }
}

// CUSTOM AUTHENTICATION EXCEPTION

class AuthApiException implements Exception {
  const AuthApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}
