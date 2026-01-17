import '../models/user_profile.dart';

class AuthSession {
  AuthSession({required this.user, required this.permissions});

  final UserProfile user;
  final Map<String, bool> permissions;
}
