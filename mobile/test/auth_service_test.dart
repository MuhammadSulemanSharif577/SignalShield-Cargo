import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:driver_app/core/network/api_config.dart';
import 'package:driver_app/features/authentication/models/user_model.dart';
import 'package:driver_app/features/authentication/services/auth_service.dart';

import 'auth_test_support.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Dio dio;

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
    dio = Dio(BaseOptions(baseUrl: 'https://api.example.com/api/v1'));
  });
  tearDown(() => dio.close());

  test('login sends email/password only, without stale bearer, and stores token', () async {
    FlutterSecureStorage.setMockInitialValues({'access_token': 'old-token'});
    dio.httpClientAdapter = TestAdapter((request) {
      expect(request.path, ApiConfig.loginEndpoint);
      expect(request.uri.path, '/api/v1/auth/login');
      expect(request.headers['Authorization'], isNull);
      expect(request.data, {
        'email': 'driver@example.com',
        'password': ' TemporaryPassword123 ',
      });
      return (status: 200, body: sessionResponse(mustChangePassword: true));
    });
    final service = AuthService(dio: dio);
    final response = await service.signIn(
      identifier: ' driver@example.com ',
      password: ' TemporaryPassword123 ',
    );
    expect(await service.getAccessToken(), 'session-token');
    final user = UserModel.fromJson(response['user']);
    expect(user.driverId, 'd1');
    expect(user.mustChangePassword, isTrue);
    expect(user.displayName, 'Driver One');
  });

  test('password change uses camelCase and replaces the bearer token', () async {
    FlutterSecureStorage.setMockInitialValues({'access_token': 'old-token'});
    dio.httpClientAdapter = TestAdapter((request) {
      expect(request.path, ApiConfig.changePasswordEndpoint);
      expect(request.headers['Authorization'], 'Bearer old-token');
      expect(request.data, {
        'currentPassword': 'TemporaryPassword123',
        'newPassword': ' NewPassword123 ',
      });
      return (status: 200, body: sessionResponse(token: 'rotated-token'));
    });
    final service = AuthService(dio: dio);
    await service.changePassword(
      currentPassword: 'TemporaryPassword123',
      newPassword: ' NewPassword123 ',
    );
    expect(await service.getAccessToken(), 'rotated-token');
  });

  test('reads backend message and retains a valid session on validation errors', () async {
    FlutterSecureStorage.setMockInitialValues({'access_token': 'old-token'});
    dio.httpClientAdapter = TestAdapter((_) => (
      status: 422,
      body: {'code': 'invalid_credentials', 'message': 'The current password is incorrect.'},
    ));
    final service = AuthService(dio: dio);
    await expectLater(
      service.changePassword(currentPassword: 'wrong', newPassword: 'NewPassword123'),
      throwsA(isA<AuthApiException>().having(
        (error) => error.message, 'message', 'The current password is incorrect.',
      )),
    );
    expect(await service.getAccessToken(), 'old-token');
  });

  test('expired or revoked sessions are cleared after current-user 401', () async {
    FlutterSecureStorage.setMockInitialValues({'access_token': 'expired-token'});
    dio.httpClientAdapter = TestAdapter((request) {
      expect(request.path, ApiConfig.currentUserEndpoint);
      expect(request.headers['Authorization'], 'Bearer expired-token');
      return (status: 401, body: {'code': 'invalid_token', 'message': 'Session expired.'});
    });
    final service = AuthService(dio: dio);
    await expectLater(service.getCurrentUser(), throwsA(isA<AuthApiException>()));
    expect(await service.getAccessToken(), isNull);
  });

  test('logout revokes the backend session and accepts an empty 204', () async {
    FlutterSecureStorage.setMockInitialValues({'access_token': 'old-token'});
    dio.httpClientAdapter = TestAdapter((request) {
      expect(request.path, ApiConfig.logoutEndpoint);
      expect(request.method, 'POST');
      expect(request.headers['Authorization'], 'Bearer old-token');
      return (status: 204, body: null);
    });
    final service = AuthService(dio: dio);
    await service.logout();
    expect(await service.getAccessToken(), isNull);
  });

  test('logout clears the device token even when the server is unreachable', () async {
    FlutterSecureStorage.setMockInitialValues({'access_token': 'old-token'});
    dio.httpClientAdapter = TestAdapter((request) {
      throw DioException(requestOptions: request, type: DioExceptionType.connectionError);
    });
    final service = AuthService(dio: dio);
    await service.logout();
    expect(await service.getAccessToken(), isNull);
  });

  for (final driverId in [null, '', '   ']) {
    test('rejects login without a linked driver ($driverId) and revokes the new token', () async {
      FlutterSecureStorage.setMockInitialValues({'access_token': 'old-token'});
      final adapter = TestAdapter((request) {
        if (request.path == ApiConfig.loginEndpoint) {
          return (
            status: 200,
            body: sessionResponse(token: 'staff-token', driverId: driverId),
          );
        }
        expect(request.path, ApiConfig.logoutEndpoint);
        // Revoke the newly issued token, not the old token on the device.
        expect(request.headers['Authorization'], 'Bearer staff-token');
        return (status: 204, body: null);
      });
      dio.httpClientAdapter = adapter;
      final service = AuthService(dio: dio);
      await expectLater(
        service.signIn(identifier: 'admin@example.com', password: 'AdminPassword123'),
        throwsA(isA<AuthApiException>().having(
          (error) => error.message, 'message',
          'This app is for driver accounts. Use the web app for staff access.',
        )),
      );
      expect(await service.getAccessToken(), isNull);
      expect(adapter.requests.map((request) => request.path), [
        ApiConfig.loginEndpoint, ApiConfig.logoutEndpoint,
      ]);
    });
  }

  test('rejects a missing driverId even when backend role names include Driver', () async {
    final response = sessionResponse();
    (response['user'] as Map<String, dynamic>).remove('driverId');
    dio.httpClientAdapter = TestAdapter((request) {
      if (request.path == ApiConfig.loginEndpoint) {
        return (status: 200, body: response);
      }
      return (status: 204, body: null);
    });
    final service = AuthService(dio: dio);
    await expectLater(
      service.signIn(identifier: 'staff@example.com', password: 'Password123'),
      throwsA(isA<AuthApiException>()),
    );
    expect(await service.getAccessToken(), isNull);
  });

  test('rejects restored staff sessions even if remote revocation fails', () async {
    FlutterSecureStorage.setMockInitialValues({'access_token': 'staff-token'});
    final adapter = TestAdapter((request) {
      expect(request.headers['Authorization'], 'Bearer staff-token');
      if (request.path == ApiConfig.currentUserEndpoint) {
        return (
          status: 200,
          body: sessionResponse(driverId: null)['user'] as Map<String, dynamic>,
        );
      }
      expect(request.path, ApiConfig.logoutEndpoint);
      throw DioException(requestOptions: request, type: DioExceptionType.connectionError);
    });
    dio.httpClientAdapter = adapter;
    final service = AuthService(dio: dio);
    await expectLater(service.getCurrentUser(), throwsA(isA<AuthApiException>()));
    expect(await service.getAccessToken(), isNull);
    expect(adapter.requests.length, 2);
  });
}
