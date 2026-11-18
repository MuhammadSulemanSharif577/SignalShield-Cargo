import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/utils/validators.dart';
import '../../../core/widgets/primary_button.dart';
import '../viewmodels/auth_viewmodel.dart';

class ChangePasswordView extends ConsumerStatefulWidget {
  const ChangePasswordView({super.key});

  @override
  ConsumerState<ChangePasswordView> createState() => _ChangePasswordViewState();
}

class _ChangePasswordViewState extends ConsumerState<ChangePasswordView> {
  final _formKey = GlobalKey<FormState>();
  final _current = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();

  @override
  void dispose() {
    _current.dispose();
    _password.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final success = await ref.read(authViewModelProvider.notifier).changePassword(
      currentPassword: _current.text,
      newPassword: _password.text,
    );
    if (!mounted || success) return;
    final error = ref.read(authViewModelProvider).error;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(error?.toString() ?? 'Unable to change password.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final busy = ref.watch(authViewModelProvider).isLoading;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Change temporary password'),
        actions: [
          IconButton(
            tooltip: 'Sign out',
            onPressed: busy ? null : () => ref.read(authViewModelProvider.notifier).signOut(),
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text('Choose a private password before continuing. Use at least 10 characters, an uppercase letter, a lowercase letter, and a number.'),
              const SizedBox(height: 24),
              TextFormField(
                controller: _current,
                obscureText: true,
                decoration: const InputDecoration(labelText: 'Current password'),
                validator: Validators.password,
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _password,
                obscureText: true,
                decoration: const InputDecoration(labelText: 'New password'),
                validator: (value) {
                  final password = value ?? '';
                  if (password.length < 10 || password.length > 1024 ||
                      !RegExp(r'[A-Z]').hasMatch(password) ||
                      !RegExp(r'[a-z]').hasMatch(password) ||
                      !RegExp(r'[0-9]').hasMatch(password)) {
                    return 'Use 10–1024 characters, uppercase, lowercase, and a number.';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _confirm,
                obscureText: true,
                decoration: const InputDecoration(labelText: 'Confirm password'),
                validator: (value) => value == _password.text ? null : 'Passwords do not match.',
              ),
              const SizedBox(height: 24),
              PrimaryButton(
                label: 'Update password',
                onPressed: _submit,
                isLoading: busy,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
