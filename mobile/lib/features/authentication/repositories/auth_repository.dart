
import '../models/user_model.dart';
import '../services/auth_service.dart';

class AuthRepository {
  AuthRepository(this._service);

  final AuthService _service;

  // SIGN IN

  Future<UserModel> signIn({
    required String identifier,
    required String password,
  }) async {
    final response = await _service.signIn(
      identifier: identifier,
      password: password,
    );

    final userJson = response['user'] as Map<String, dynamic>;

    return UserModel.fromJson(userJson);
  }

  Future<UserModel> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    final response = await _service.changePassword(
      currentPassword: currentPassword,
      newPassword: newPassword,
    );
    return UserModel.fromJson(response['user'] as Map<String, dynamic>);
  }



  // GET CURRENT USER

  Future<UserModel?> getCurrentUser() async {
    if (await _service.getAccessToken() == null) return null;
    final response = await _service.getCurrentUser();

    return UserModel.fromJson(response);
  }

  // LOGOUT

  Future<void> logout() async {
    await _service.logout();
  }
}
