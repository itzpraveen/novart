import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../api/api_client.dart';
import '../api/api_repository.dart';
import '../auth/auth_controller.dart';
import '../auth/auth_repository.dart';
import '../auth/auth_state.dart';
import '../auth/token_storage.dart';

final tokenStorageProvider = Provider<TokenStorage>((ref) {
  return TokenStorage(const FlutterSecureStorage());
});

final apiClientProvider = Provider<ApiClient>((ref) {
  final storage = ref.watch(tokenStorageProvider);
  return ApiClient(storage);
});

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(
    ref.watch(apiClientProvider),
    ref.watch(tokenStorageProvider),
  );
});

final authControllerProvider = StateNotifierProvider<AuthController, AuthState>(
  (ref) {
    return AuthController(
      ref.watch(authRepositoryProvider),
      ref.watch(tokenStorageProvider),
      ref.watch(apiClientProvider),
    );
  },
);

final apiRepositoryProvider = Provider<ApiRepository>((ref) {
  return ApiRepository(ref.watch(apiClientProvider));
});
