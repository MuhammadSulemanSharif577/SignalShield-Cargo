import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/authentication/views/login_view.dart';
import '../../features/authentication/views/change_password_view.dart';
import '../../features/authentication/viewmodels/auth_viewmodel.dart';
import '../../features/dashboard/views/dashboard_view.dart';
import 'route_names.dart';

final appRouterProvider = Provider<GoRouter>((ref) {
  final router = GoRouter(
    initialLocation: RouteNames.login,
    redirect: (context, route) {
      final auth = ref.read(authViewModelProvider);
      final user = auth.valueOrNull;
      final path = route.matchedLocation;
      if (user == null) {
        return path == RouteNames.login ? null : RouteNames.login;
      }
      if (user.mustChangePassword) {
        return path == RouteNames.changePassword ? null : RouteNames.changePassword;
      }
      return path == RouteNames.login || path == RouteNames.changePassword
          ? RouteNames.dashboard : null;
    },
    routes: [
      GoRoute(
        path: RouteNames.changePassword,
        builder: (context, state) => const ChangePasswordView(),
      ),
      GoRoute(
        path: RouteNames.login,
        builder: (context, state) => const LoginView(),
      ),
      GoRoute(
        path: RouteNames.dashboard,
        builder: (context, state) => const DashboardView(),
      ),
    ],
  );
  ref.listen(authViewModelProvider, (_, next) => router.refresh());
  ref.onDispose(router.dispose);
  return router;
});
