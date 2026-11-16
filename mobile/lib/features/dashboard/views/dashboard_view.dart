import 'package:flutter/material.dart';
import '../../../app/theme/app_colors.dart';

class DashboardView extends StatelessWidget {
  const DashboardView({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('SignalShield Cargo'),
        backgroundColor: AppColors.background,
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
