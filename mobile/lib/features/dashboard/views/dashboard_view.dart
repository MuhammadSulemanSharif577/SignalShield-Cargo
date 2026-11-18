import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../authentication/viewmodels/auth_viewmodel.dart';
import '../../../app/theme/app_colors.dart';

class DashboardView extends ConsumerWidget {
  const DashboardView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('SignalShield Cargo'),
        backgroundColor: AppColors.background,
        actions: [
          IconButton(
            tooltip: 'Sign out',
            icon: const Icon(Icons.logout),
            onPressed: () => ref.read(authViewModelProvider.notifier).signOut(),
          ),
        ],
      ),
      body: const Center(
        child: Text(
          'Dashboard placeholder',
          style: TextStyle(color: AppColors.text, fontSize: 18),
        ),
      ),
    );
  }
}
