import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/login_screen.dart';
import '../../features/auth/splash_screen.dart';
import '../../features/home/home_shell.dart';
import '../auth/auth_state.dart';
import '../di/providers.dart';

class AuthRouterNotifier extends ChangeNotifier {
  AuthRouterNotifier(this.ref) {
    ref.listen<AuthState>(
      authControllerProvider,
      (previous, next) => notifyListeners(),
    );
  }

  final Ref ref;

  AuthStatus get status => ref.read(authControllerProvider).status;
}

final routerProvider = Provider<GoRouter>((ref) {
  final notifier = AuthRouterNotifier(ref);

  return GoRouter(
    initialLocation: '/splash',
    refreshListenable: notifier,
    redirect: (context, state) {
      final status = notifier.status;
      final isSplash = state.matchedLocation == '/splash';
      final isLogin = state.matchedLocation == '/login';

      if (status == AuthStatus.unknown) {
        return isSplash ? null : '/splash';
      }
      if (status == AuthStatus.loading) {
        return null;
      }
      if (status == AuthStatus.unauthenticated) {
        return isLogin ? null : '/login';
      }
      if (status == AuthStatus.authenticated && (isLogin || isSplash)) {
        return '/';
      }
      return null;
    },
    routes: [
      GoRoute(
        path: '/splash',
        builder: (context, state) => const SplashScreen(),
      ),
      GoRoute(path: '/login', builder: (context, state) => const LoginScreen()),
      GoRoute(path: '/', builder: (context, state) => const HomeShell()),
    ],
  );
});
