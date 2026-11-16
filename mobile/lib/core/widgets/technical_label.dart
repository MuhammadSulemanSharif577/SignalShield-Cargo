import 'package:flutter/material.dart';
import '../../app/theme/app_colors.dart';

class TechnicalLabel extends StatelessWidget {
  const TechnicalLabel(
    this.text, {
    super.key,
    this.trailing,
  });

  final String text;
  final String? trailing;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            text.toUpperCase(),
            style: const TextStyle(
              color: AppColors.muted,
              fontSize: 8,
              letterSpacing: 1.05,
              fontWeight: FontWeight.w700,
              fontFamily: 'monospace',
            ),
          ),
        ),
        if (trailing != null)
          Text(
            trailing!,
            style: const TextStyle(
              color: AppColors.primaryLight,
              fontSize: 8,
              letterSpacing: 0.8,
              fontWeight: FontWeight.w700,
              fontFamily: 'monospace',
            ),
          ),
      ],
    );
  }
}
