import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import 'auth_repository.dart';
import 'auth_state.dart';
import 'token_storage.dart';

class AuthController extends StateNotifier<AuthState> {
  AuthController(this._repository, this._storage, this._apiClient)
    : super(AuthState.unknown) {
    _apiClient.setUnauthorizedHandler(signOut);
    _bootstrap();
  }

  final AuthRepository _repository;
  final TokenStorage _storage;
  final ApiClient _apiClient;

  Future<void> _bootstrap() async {
    await _storage.load();
    final accessToken = _storage.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      state = AuthState.unauthenticated;
      return;
    }
    try {
      final session = await _repository.fetchSession();
      state = AuthState(status: AuthStatus.authenticated, session: session);
    } catch (_) {
      final refreshed = await _repository.refreshSession();
      if (refreshed == null) {
        await _repository.logout();
        state = AuthState.unauthenticated;
        return;
      }
      state = AuthState(status: AuthStatus.authenticated, session: refreshed);
    }
  }

  Future<void> signIn(String username, String password) async {
    state = const AuthState(status: AuthStatus.loading);
    try {
      final session = await _repository.login(
        username: username,
        password: password,
      );
      state = AuthState(status: AuthStatus.authenticated, session: session);
    } catch (err) {
      state = AuthState(
        status: AuthStatus.unauthenticated,
        error: 'Unable to sign in. Check your credentials.',
      );
    }
  }

  Future<void> signOut() async {
    await _repository.logout();
    state = AuthState.unauthenticated;
  }
}
