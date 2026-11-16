
import '../models/user_model.dart';
import '../services/auth_service.dart';

class AuthRepository {
  AuthRepository(this._service);

  final AuthService _service;

  // SIGN IN

  Future<UserModel> signIn({
    required String identifier,
    required String password,
    required bool keepSessionBound,
  }) async {
    final response = await _service.signIn(
      identifier: identifier,
      password: password,
      keepSessionBound: keepSessionBound,
    );

    final userJson = response['user'] as Map<String, dynamic>;

    return UserModel.fromJson(userJson);
  }



  // GET CURRENT USER

  Future<UserModel> getCurrentUser() async {
    final response = await _service.getCurrentUser();

    return UserModel.fromJson(response);
  }

  // LOGOUT

  Future<void> logout() async {
    await _service.logout();
  }
}
