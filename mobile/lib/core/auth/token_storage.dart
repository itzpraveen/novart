import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class TokenStorage {
  TokenStorage(this._storage);

  final FlutterSecureStorage _storage;

  String? _accessToken;
  String? _refreshToken;

  static const _accessKey = 'access_token';
  static const _refreshKey = 'refresh_token';

  Future<void> load() async {
    _accessToken = await _storage.read(key: _accessKey);
    _refreshToken = await _storage.read(key: _refreshKey);
  }

  String? get accessToken => _accessToken;
  String? get refreshToken => _refreshToken;

  Future<void> save({String? accessToken, String? refreshToken}) async {
    if (accessToken != null) {
      _accessToken = accessToken;
      await _storage.write(key: _accessKey, value: accessToken);
    }
    if (refreshToken != null) {
      _refreshToken = refreshToken;
      await _storage.write(key: _refreshKey, value: refreshToken);
    }
  }

  Future<void> clear() async {
    _accessToken = null;
    _refreshToken = null;
    await _storage.delete(key: _accessKey);
    await _storage.delete(key: _refreshKey);
  }
}
