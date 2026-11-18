import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../app/theme/app_colors.dart';
import '../../../core/utils/validators.dart';
import '../../../core/widgets/primary_button.dart';
import '../../../core/widgets/technical_label.dart';
import '../viewmodels/auth_viewmodel.dart';
import '../widgets/auth_branding.dart';
import '../widgets/auth_text_field.dart';

class LoginView extends ConsumerStatefulWidget {
  const LoginView({super.key});

  @override
  ConsumerState<LoginView> createState() => _LoginViewState();
}

class _LoginViewState extends ConsumerState<LoginView> {
  final _formKey = GlobalKey<FormState>();
  final _identifierController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _obscurePassword = true;

  @override
  void dispose() {
    _identifierController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _signIn() async {
    FocusScope.of(context).unfocus();
    if (!_formKey.currentState!.validate()) return;

    final success = await ref.read(authViewModelProvider.notifier).signIn(
      identifier: _identifierController.text,
      password: _passwordController.text,
    );

    if (!mounted) return;

    if (!success) {
      final state = ref.read(authViewModelProvider);
      final message = state.hasError
          ? state.error.toString().replaceFirst('Exception: ', '')
          : 'Unable to sign in. Please try again.';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(message),
          backgroundColor: AppColors.surfaceAlt,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authViewModelProvider);
    final isLoading = authState.isLoading;
    final bottomInset = MediaQuery.viewInsetsOf(context).bottom;

    return Scaffold(
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            return SingleChildScrollView(
              padding: EdgeInsets.fromLTRB(18, 18, 18, 24 + bottomInset * 0.15),
              child: ConstrainedBox(
                constraints: BoxConstraints(minHeight: constraints.maxHeight - 42),
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const AuthBranding(),
                      const SizedBox(height: 26),
                      const Text(
                        'Welcome Back',
                        style: TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -0.3,
                        ),
                      ),
                      const SizedBox(height: 17),

                      const TechnicalLabel(
                        'Email',

                      ),
                      const SizedBox(height: 7),
                      AuthTextField(
                        controller: _identifierController,
                        hint: 'Enter your account email',
                        icon: Icons.mail_outline_rounded,
                        validator: Validators.email,
                        keyboardType: TextInputType.emailAddress,
                      ),
                      const SizedBox(height: 15),

                      const TechnicalLabel(
                        'Access Cipher / Password',
                        trailing: 'MIL-STD-810H',
                      ),
                      const SizedBox(height: 7),
                      AuthTextField(
                        controller: _passwordController,
                        hint: 'Enter security key phrase',
                        icon: Icons.lock_outline_rounded,
                        isPassword: true,
                        obscureText: _obscurePassword,
                        onToggleVisibility: () {
                          setState(() => _obscurePassword = !_obscurePassword);
                        },
                        validator: Validators.password,
                      ),
                      const SizedBox(height: 10),

                      const Text(
                        'Use the credentials provided by your administrator. Contact them if you need access or a password reset.',
                        style: TextStyle(fontSize: 10, color: AppColors.muted),
                      ),
                      const SizedBox(height: 13),
                      PrimaryButton(
                        label: 'Sign In',
                        icon: Icons.lock_open_rounded,
                        isLoading: isLoading,
                        onPressed: _signIn,
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}
