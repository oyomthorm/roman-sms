import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'router.dart';
import 'theme/app_theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ProviderScope(child: RomanSmsApp()));
}

class RomanSmsApp extends ConsumerWidget {
  const RomanSmsApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);

    return MaterialApp.router(
      title: 'Roman SMS',
      debugShowCheckedModeBanner: false,
      theme: RomanSmsTheme.lightTheme,
      routerConfig: router,
    );
  }
}
