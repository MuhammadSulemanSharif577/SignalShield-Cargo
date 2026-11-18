
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/user_model.dart';
import '../repositories/auth_repository.dart';
import '../services/auth_service.dart';

final authServiceProvider = Provider<AuthService>((ref) => AuthService());

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(ref.watch(authServiceProvider));
});

final authViewModelProvider =
StateNotifierProvider<AuthViewModel, AsyncValue<UserModel?>>((ref) {
  return AuthViewModel(ref.watch(authRepositoryProvider));
});

class AuthViewModel extends StateNotifier<AsyncValue<UserModel?>> {
  AuthViewModel(this._repository) : super(const AsyncData(null));

  final AuthRepository _repository;

  // SIGN IN
  Future<bool> signIn({
    required String identifier,
    required String password,
    required bool keepSessionBound,
  }) async {
    state = const AsyncLoading();

    try {
      final user = await _repository.signIn(
        identifier: identifier.trim(),
        password: password,
        keepSessionBound: keepSessionBound,
      );

      state = AsyncData(user);
      return true;
    } catch (error, stackTrace) {
      state = AsyncError(error, stackTrace);
      return false;
    }
  }



  // RESTORE CURRENT USER
  Future<void> loadCurrentUser() async {
    state = const AsyncLoading();

    try {
      final user = await _repository.getCurrentUser();

      state = AsyncData(user);
    } catch (error, stackTrace) {
      state = AsyncError(error, stackTrace);
    }
  }

  // SIGN OUT
  Future<void> signOut() async {
    try {
      await _repository.logout();

      state = const AsyncData(null);
    } catch (error, stackTrace) {
      state = AsyncError(error, stackTrace);
    }
  }

  // CLEAR ERROR
  void clearError() {
    if (state.hasError) {
      state = const AsyncData(null);
    }
  }
}
