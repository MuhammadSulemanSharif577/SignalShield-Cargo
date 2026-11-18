class UserModel {
  const UserModel({
    required this.id,
    required this.displayName,
    required this.email,
    this.driverId,
    this.mustChangePassword = false,
  });

  final String id;
  final String displayName;
  final String email;
  final String? driverId;
  final bool mustChangePassword;

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'].toString(),
      displayName: (json['full_name'] ?? json['name'] ?? '').toString(),
      email: (json['email'] ?? '').toString(),
      driverId: json['driverId'] as String?,
      mustChangePassword: json['mustChangePassword'] == true,
    );
  }
}
