# driver_app

A cargo application with integrated GNSS spoofing feature.

## Getting Started

Use the user account created for the driver by an administrator. A linked `driverId`
is required: staff/admin accounts are rejected, their mobile session is revoked
when reachable, and the device token is cleared. The same check
applies to saved sessions. This app check does not replace backend authorization.
Login uses email and password; terminal IDs, public signup, email recovery, and
“remember me” are not supported by the backend. Temporary passwords must be changed
at first login.
Sessions are stored securely and checked with `/api/v1/auth/me` when the app starts.
Expired/revoked sessions require signing in again. The dashboard remains a placeholder.

For a standard Android emulator (the default API address is `10.0.2.2:8000`):

```sh
flutter pub get
flutter run
```

For a physical phone, use your backend computer's reachable LAN IP, not `localhost`
or `10.0.2.2`, and ensure the backend listens on the network interface:

```sh
flutter run --dart-define=API_BASE_URL=http://192.168.1.100:8000/api/v1
```

`API_BASE_URL` includes `/api/v1`, matching `ApiConfig`. Rebuild/relaunch after
changing it. Debug/profile builds allow HTTP for local development; release builds
should use an HTTPS API URL. Ask the backend owner to apply its existing database
migrations before testing shared driver accounts. No backend changes are needed
for this mobile integration.

Checks: `flutter analyze` and `flutter test`.

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Learn Flutter](https://docs.flutter.dev/get-started/learn-flutter)
- [Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Flutter learning resources](https://docs.flutter.dev/reference/learning-resources)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.
