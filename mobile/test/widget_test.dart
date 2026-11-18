import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:driver_app/app/app.dart';
import 'package:driver_app/app/routes/app_router.dart';
import 'package:driver_app/app/routes/route_names.dart';
import 'package:driver_app/core/network/api_config.dart';
import 'package:driver_app/features/authentication/services/auth_service.dart';
import 'package:driver_app/features/authentication/viewmodels/auth_viewmodel.dart';

import 'auth_test_support.dart';

void main() {
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  Future<ProviderContainer> launch(WidgetTester tester, TestAdapter adapter) async {
    final dio = Dio(BaseOptions(baseUrl: 'https://api.example.com/'))
      ..httpClientAdapter = adapter;
    final container = ProviderContainer(overrides: [
      authServiceProvider.overrideWithValue(AuthService(dio: dio)),
    ]);
    addTearDown(() {
      container.dispose();
      dio.close();
    });
    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: const SignalShieldApp(),
    ));
    await tester.pumpAndSettle();
    return container;
  }

  testWidgets('login, required password change, token rotation and logout', (tester) async {
    var rejectPassword = true;
    final adapter = TestAdapter((request) {
      if (request.path == ApiConfig.loginEndpoint) {
        return (status: 200, body: sessionResponse(mustChangePassword: true));
      }
      if (request.path == ApiConfig.changePasswordEndpoint) {
        if (rejectPassword) {
          return (status: 422, body: {'message': 'The current password is incorrect.'});
        }
        return (status: 200, body: sessionResponse(token: 'rotated-token'));
      }
      expect(request.path, ApiConfig.logoutEndpoint);
      expect(request.headers['Authorization'], 'Bearer rotated-token');
      return (status: 204, body: null);
    });
    final container = await launch(tester, adapter);
    expect(find.text('Create Account'), findsNothing);
    expect(find.text('Keep Session Bound'), findsNothing);
    await tester.enterText(find.byType(TextFormField).at(0), 'driver@example.com');
    await tester.enterText(find.byType(TextFormField).at(1), 'TemporaryPassword123');
    await tester.ensureVisible(find.text('Sign In'));
    await tester.tap(find.text('Sign In'));
    await tester.pumpAndSettle();
    expect(find.text('Change temporary password'), findsOneWidget);
    container.read(appRouterProvider).go(RouteNames.dashboard);
    await tester.pumpAndSettle();
    expect(find.text('Dashboard placeholder'), findsNothing);

    await tester.enterText(find.byType(TextFormField).at(0), 'TemporaryPassword123');
    await tester.enterText(find.byType(TextFormField).at(1), 'NewPassword123');
    await tester.enterText(find.byType(TextFormField).at(2), 'NewPassword123');
    await tester.ensureVisible(find.text('Update password'));
    await tester.tap(find.text('Update password'));
    await tester.pumpAndSettle();
    expect(find.text('The current password is incorrect.'), findsOneWidget);
    expect(find.text('Change temporary password'), findsOneWidget);
    rejectPassword = false;
    await tester.tap(find.text('Update password'));
    await tester.pumpAndSettle();
    expect(find.text('Dashboard placeholder'), findsOneWidget);
    await tester.tap(find.byTooltip('Sign out'));
    await tester.pumpAndSettle();
    expect(find.text('Welcome Back'), findsOneWidget);
    expect(await container.read(authServiceProvider).getAccessToken(), isNull);
  });

  testWidgets('restores temporary-password state and prevents dashboard bypass', (tester) async {
    FlutterSecureStorage.setMockInitialValues({'access_token': 'session-token'});
    final adapter = TestAdapter((request) {
      expect(request.path, ApiConfig.currentUserEndpoint);
      return (status: 200, body: sessionResponse(mustChangePassword: true)['user'] as Map<String, dynamic>);
    });
    final container = await launch(tester, adapter);
    expect(find.text('Change temporary password'), findsOneWidget);
    container.read(appRouterProvider).go(RouteNames.dashboard);
    await tester.pumpAndSettle();
    expect(find.text('Change temporary password'), findsOneWidget);
    expect(find.text('Dashboard placeholder'), findsNothing);
  });

  testWidgets('expired restored sessions return to login', (tester) async {
    FlutterSecureStorage.setMockInitialValues({'access_token': 'expired-token'});
    final adapter = TestAdapter((_) => (
      status: 401,
      body: {'code': 'invalid_token', 'message': 'Session expired.'},
    ));
    final container = await launch(tester, adapter);
    expect(find.text('Welcome Back'), findsOneWidget);
    expect(await container.read(authServiceProvider).getAccessToken(), isNull);
    container.read(appRouterProvider).go(RouteNames.dashboard);
    await tester.pumpAndSettle();
    expect(find.text('Dashboard placeholder'), findsNothing);
  });

  testWidgets('staff login is rejected without showing dashboard or password-change screen', (tester) async {
    final adapter = TestAdapter((request) {
      if (request.path == ApiConfig.loginEndpoint) {
        return (status: 200, body: sessionResponse(driverId: null, mustChangePassword: true));
      }
      expect(request.path, ApiConfig.logoutEndpoint);
      return (status: 204, body: null);
    });
    final container = await launch(tester, adapter);
    await tester.enterText(find.byType(TextFormField).at(0), 'admin@example.com');
    await tester.enterText(find.byType(TextFormField).at(1), 'AdminPassword123');
    await tester.ensureVisible(find.text('Sign In'));
    await tester.tap(find.text('Sign In'));
    await tester.pumpAndSettle();
    expect(find.text('This app is for driver accounts. Use the web app for staff access.'), findsOneWidget);
    expect(find.text('Dashboard placeholder'), findsNothing);
    expect(find.text('Change temporary password'), findsNothing);
    expect(await container.read(authServiceProvider).getAccessToken(), isNull);
    container.read(appRouterProvider).go(RouteNames.dashboard);
    await tester.pumpAndSettle();
    expect(find.text('Dashboard placeholder'), findsNothing);
  });

  testWidgets('previously saved admin session is cleared and cannot bypass login', (tester) async {
    FlutterSecureStorage.setMockInitialValues({'access_token': 'staff-token'});
    final adapter = TestAdapter((request) {
      if (request.path == ApiConfig.currentUserEndpoint) {
        return (status: 200, body: sessionResponse(driverId: null)['user'] as Map<String, dynamic>);
      }
      expect(request.path, ApiConfig.logoutEndpoint);
      expect(request.headers['Authorization'], 'Bearer staff-token');
      return (status: 204, body: null);
    });
    final container = await launch(tester, adapter);
    expect(find.text('Welcome Back'), findsOneWidget);
    expect(await container.read(authServiceProvider).getAccessToken(), isNull);
    for (final path in [RouteNames.dashboard, RouteNames.changePassword]) {
      container.read(appRouterProvider).go(path);
      await tester.pumpAndSettle();
      expect(find.text('Welcome Back'), findsOneWidget);
      expect(find.text('Dashboard placeholder'), findsNothing);
      expect(find.text('Change temporary password'), findsNothing);
    }
  });
}
