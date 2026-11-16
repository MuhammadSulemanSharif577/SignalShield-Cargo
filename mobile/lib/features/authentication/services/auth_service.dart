
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
    // Automatically attach JWT to requests when one is stored.
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _storage.read(key: _tokenKey);

          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }

          handler.next(options);
        },
      ),
    );
  }



  // SIGN IN

  Future<Map<String, dynamic>> signIn({
    required String identifier,
    required String password,
    required bool keepSessionBound,
  }) async {
    return _postAndStoreToken(
      ApiConfig.loginEndpoint,
      {
        'identifier': identifier.trim(),
        'password': password,
        'remember_me': keepSessionBound,
      },
    );
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

      final token = responseData['access_token'];

      if (token is! String || token.isEmpty) {
        throw const AuthApiException(
          'The server did not return an access token.',
        );
      }

      // Store JWT securely on the device.
      await _storage.write(
        key: _tokenKey,
        value: token,
      );

      return responseData;
    } on DioException catch (error) {
      throw AuthApiException(_getErrorMessage(error));
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

      return Map<String, dynamic>.from(response.data);
    } on DioException catch (error) {
      throw AuthApiException(_getErrorMessage(error));
    }
  }

  // READ STORED TOKEN

  Future<String?> getAccessToken() async {
    return _storage.read(key: _tokenKey);
  }

  // LOGOUT

  Future<void> logout() async {
    await _storage.delete(key: _tokenKey);
  }

  // API ERROR HANDLING

  String _getErrorMessage(DioException error) {
    final responseData = error.response?.data;

    if (responseData is Map) {
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
  const AuthApiException(this.message);

  final String message;

  @override
  String toString() => message;
}
