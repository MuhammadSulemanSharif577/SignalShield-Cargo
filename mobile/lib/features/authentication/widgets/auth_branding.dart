
import 'package:flutter/material.dart';
import '../../../app/theme/app_colors.dart';

class AuthBranding extends StatelessWidget {
  const AuthBranding({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SizedBox(height: 12),

        Image.asset(
          'assets/GPSLogisticLogo.png',
          height: 125,

          width: 200,
          fit: BoxFit.contain,
          errorBuilder: (context, error, stackTrace) {
            return const Icon(
              Icons.shield_rounded,
              size: 85,
              color: AppColors.primary,
            );
          },
        ),

        const SizedBox(height: 12),

        // Application Name
       const Text(
         'SIGNALSHIELD CARGO',
         textAlign: TextAlign.center,
         style: TextStyle(
           fontSize: 19,
           fontWeight: FontWeight.w900,
           letterSpacing: 2.0,
           color: Colors.white,
         ),
       ),

        const SizedBox(height: 6),



      ],
    );
  }
}
