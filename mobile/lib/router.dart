import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'screens/dashboard_screen.dart';
import 'screens/new_campaign_screen.dart';
import 'screens/login_screen.dart';
import 'screens/signup_screen.dart';
import 'screens/signup_pending_screen.dart';
import 'screens/contacts_screen.dart';
import 'screens/wallet_screen.dart';
import 'screens/campaigns_screen.dart';
import 'screens/campaign_detail_screen.dart';
import 'screens/plans_screen.dart';
import 'screens/profile_screen.dart';
import 'screens/notifications_screen.dart';
import 'screens/chat_channels_screen.dart';
import 'screens/chat_detail_screen.dart';
import 'widgets/app_shell.dart';
import 'state/auth_provider.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    initialLocation: '/',
    redirect: (context, state) {
      final isLoggedIn = authState.isAuthenticated;
      final path = state.uri.path;
      // Public (unauthenticated) routes
      final isPublic =
          path == '/login' || path == '/signup' || path == '/signup/pending';

      if (!isLoggedIn && !isPublic) return '/login';
      if (isLoggedIn && path == '/login') return '/';
      return null;
    },
    routes: [
      GoRoute(path: '/login', builder: (context, state) => const LoginScreen()),
      GoRoute(
          path: '/signup', builder: (context, state) => const SignupScreen()),
      GoRoute(
        path: '/signup/pending',
        builder: (context, state) => const SignupPendingScreen(),
      ),
      ShellRoute(
        builder: (context, state, child) => AppShell(child: child),
        routes: [
          GoRoute(
              path: '/', builder: (context, state) => const DashboardScreen()),
          GoRoute(
              path: '/campaigns',
              builder: (context, state) => const CampaignsScreen()),
          GoRoute(
              path: '/contacts',
              builder: (context, state) => const ContactsScreen()),
          GoRoute(
              path: '/wallet',
              builder: (context, state) => const WalletScreen()),
        ],
      ),
      GoRoute(
          path: '/campaigns/new',
          builder: (context, state) => const NewCampaignScreen()),
      GoRoute(
        path: '/campaigns/:id',
        builder: (context, state) => CampaignDetailScreen(
          campaignId: int.parse(state.pathParameters['id']!),
        ),
      ),
      GoRoute(path: '/plans', builder: (context, state) => const PlansScreen()),
      GoRoute(
          path: '/profile', builder: (context, state) => const ProfileScreen()),
      GoRoute(
          path: '/notifications',
          builder: (context, state) => const NotificationsScreen()),
      GoRoute(
          path: '/chat',
          builder: (context, state) => const ChatChannelsScreen()),
      GoRoute(
        path: '/chat/:id',
        builder: (context, state) {
          final name = state.uri.queryParameters['name'] ?? 'Chat';
          return ChatDetailScreen(
            channelId: int.parse(state.pathParameters['id']!),
            channelName: name,
          );
        },
      ),
    ],
  );
});
