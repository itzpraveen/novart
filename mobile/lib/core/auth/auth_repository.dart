import '../api/api_client.dart';
import '../models/user_profile.dart';
import 'auth_session.dart';
import 'token_storage.dart';

class AuthRepository {
  AuthRepository(this._client, this._storage);

  final ApiClient _client;
  final TokenStorage _storage;

  Future<AuthSession> login({
    required String username,
    required String password,
  }) async {
    final response = await _client.post(
      'auth/token/',
      data: {'username': username, 'password': password},
    );
    final data = response.data as Map<String, dynamic>;
    await _storage.save(
      accessToken: data['access'] as String?,
      refreshToken: data['refresh'] as String?,
    );
    return fetchSession();
  }

  Future<AuthSession?> refreshSession() async {
    final refreshToken = _storage.refreshToken;
    if (refreshToken == null || refreshToken.isEmpty) {
      return null;
    }
    final response = await _client.post(
      'auth/refresh/',
      data: {'refresh': refreshToken},
    );
    final data = response.data as Map<String, dynamic>;
    await _storage.save(accessToken: data['access'] as String?);
    if (data['refresh'] != null) {
      await _storage.save(refreshToken: data['refresh'] as String?);
    }
    return fetchSession();
  }

  Future<AuthSession> fetchSession() async {
    final response = await _client.get('auth/me/');
    final data = response.data as Map<String, dynamic>;
    final user = UserProfile.fromJson(data['user'] as Map<String, dynamic>);
    final permissions = <String, bool>{};
    final permsJson = data['permissions'] as Map<String, dynamic>? ?? {};
    permsJson.forEach((key, value) {
      permissions[key] = value == true;
    });
    return AuthSession(user: user, permissions: permissions);
  }

  Future<void> logout() async {
    await _storage.clear();
  }
}
