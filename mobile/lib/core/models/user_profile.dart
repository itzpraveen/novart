class UserProfile {
  UserProfile({
    required this.id,
    required this.username,
    required this.fullName,
    required this.email,
    required this.role,
  });

  final int id;
  final String username;
  final String fullName;
  final String email;
  final String role;

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    final fullName =
        (json['full_name'] as String?) ??
        '${json['first_name'] ?? ''} ${json['last_name'] ?? ''}'.trim();
    return UserProfile(
      id: json['id'] as int? ?? 0,
      username: json['username'] as String? ?? '',
      fullName: fullName.isEmpty
          ? (json['username'] as String? ?? '')
          : fullName,
      email: json['email'] as String? ?? '',
      role: json['role'] as String? ?? '',
    );
  }
}
