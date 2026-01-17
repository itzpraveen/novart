import 'auth_session.dart';

enum AuthStatus { unknown, loading, authenticated, unauthenticated }

class AuthState {
  const AuthState({required this.status, this.session, this.error});

  final AuthStatus status;
  final AuthSession? session;
  final String? error;

  bool get isAuthenticated => status == AuthStatus.authenticated;

  AuthState copyWith({
    AuthStatus? status,
    AuthSession? session,
    String? error,
  }) {
    return AuthState(
      status: status ?? this.status,
      session: session ?? this.session,
      error: error,
    );
  }

  static const unknown = AuthState(status: AuthStatus.unknown);
  static const loading = AuthState(status: AuthStatus.loading);
  static const unauthenticated = AuthState(status: AuthStatus.unauthenticated);
}
