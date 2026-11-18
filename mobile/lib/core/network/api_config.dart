
class ApiConfig {
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000/api/v1',
  );



  static const String loginEndpoint = '/auth/login';

  static const String currentUserEndpoint = '/auth/me';
  static const String changePasswordEndpoint = '/auth/change-password';
  static const String logoutEndpoint = '/auth/logout';
}
