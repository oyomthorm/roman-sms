# Mobile (Flutter) - developer reference

## Location

- Source: mobile/ in this repo
- Package name: com.example.roman_sms — should be renamed to com.romansms.app before Play Store submission.

## Stack

Riverpod, go_router, Dio, flutter_secure_storage, google_fonts, fl_chart (unused), intl

## Architecture

    lib/
      main.dart            MaterialApp.router + ProviderScope
      router.dart          GoRouter - public routes, shell routes, auth redirect
      api/client.dart      Dio singleton + auth interceptor + submitSignup
      state/               auth_provider.dart + providers.dart
      screens/             One screen per feature
      widgets/             app_shell.dart, add_contact_sheet.dart
      theme/app_theme.dart

## Adding a new screen

1. Create lib/screens/feature_screen.dart
2. Add a GoRoute in router.dart - under ShellRoute if it shows nav+drawer, outside if full-screen
3. Add a FutureProvider in state/providers.dart if it needs data
4. Dio interceptor attaches the Bearer token automatically

## Adding a new API endpoint

1. Add a FutureProvider.autoDispose in state/providers.dart, consume via ref.watch(provider).when(...)
2. For non-GET calls: add a helper on ApiClient, not scattered dio.post calls
3. Decimal fields come back as Strings. Parse with num.parse(...), never int.parse(...)

## Testing on a physical phone (release build)

Do not test with flutter run - debug builds auto-inject INTERNET permission and hide release-build bugs.

    cd mobile
    flutter clean
    flutter pub get
    flutter build apk --release
    adb install build\app\outputs\flutter-apk\app-release.apk

Preconditions:

- android/app/src/main/AndroidManifest.xml contains the uses-permission android.permission.INTERNET line
- lib/api/client.dart has baseUrl: https://romansms.com

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Connection Refused on release APK | Missing INTERNET permission | Add uses-permission android.permission.INTERNET |
| Connection Refused on flutter run -d chrome | CORS (web unsupported) | Use Android |
| Wallet shows 0 | Master org has 0 credits | Seed master, grant plan |
| Plans show blank or crash | NumberFormat.format() on String | Wrap with num.parse(...) |
| Drawer does not open | Screen not under ShellRoute | Add route under ShellRoute |

## Building for Play Store

1. Rename package to com.romansms.app
2. Generate keystore, add signing config
3. minifyEnabled = true
4. Add networkSecurityConfig (TLS 1.2+, no cleartext)
5. usesCleartextTraffic=false
6. flutter build appbundle --release (not --apk)

## Ongoing costs (see ADR-021)

Every new web feature must be evaluated for mobile. Every web UI bug is fixed twice. Mitigation: extract shared UI via Flutter Web - not decided.
