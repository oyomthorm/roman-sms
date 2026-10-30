import 'package:google_fonts/google_fonts.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../theme/app_theme.dart';
import '../state/auth_provider.dart';

class AppShell extends ConsumerWidget {
  final Widget child;
  const AppShell({super.key, required this.child});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final location = GoRouterState.of(context).uri.path;

    int currentIndex = 0;
    String title = 'Dashboard';
    if (location.startsWith('/campaigns')) {
      currentIndex = 1;
      title = 'Campaigns';
    } else if (location.startsWith('/contacts')) {
      currentIndex = 2;
      title = 'Contacts';
    } else if (location.startsWith('/wallet')) {
      currentIndex = 3;
      title = 'Wallet';
    }

    return Scaffold(
      // ---- APP BAR: this is the new piece ----
      appBar: AppBar(
        backgroundColor: RomanSmsTheme.primaryGreen,
        foregroundColor: Colors.white,
        title: Text(
          title,
          style: GoogleFonts.inter(fontWeight: FontWeight.w600),
        ),
        // The hamburger icon is auto-generated because this Scaffold has a
        // `drawer:` below. No explicit `leading:` needed.
      ),
      // ---- end new piece ----

      body: child,
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.05),
              blurRadius: 10,
              offset: const Offset(0, -5),
            ),
          ],
        ),
        child: BottomNavigationBar(
          currentIndex: currentIndex,
          selectedItemColor: RomanSmsTheme.primaryGreen,
          unselectedItemColor: RomanSmsTheme.textMuted,
          type: BottomNavigationBarType.fixed,
          onTap: (index) {
            switch (index) {
              case 0:
                context.go('/');
                break;
              case 1:
                context.go('/campaigns');
                break;
              case 2:
                context.go('/contacts');
                break;
              case 3:
                context.go('/wallet');
                break;
            }
          },
          items: const [
            BottomNavigationBarItem(
                icon: Icon(Icons.home_outlined),
                activeIcon: Icon(Icons.home),
                label: 'Home'),
            BottomNavigationBarItem(
                icon: Icon(Icons.send_outlined),
                activeIcon: Icon(Icons.send),
                label: 'Campaigns'),
            BottomNavigationBarItem(
                icon: Icon(Icons.people_outline),
                activeIcon: Icon(Icons.people),
                label: 'Contacts'),
            BottomNavigationBarItem(
                icon: Icon(Icons.account_balance_wallet_outlined),
                activeIcon: Icon(Icons.account_balance_wallet),
                label: 'Wallet'),
          ],
        ),
      ),
      drawer: Drawer(
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            DrawerHeader(
              decoration:
                  const BoxDecoration(color: RomanSmsTheme.primaryGreen),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  const CircleAvatar(
                    backgroundColor: Colors.white,
                    child:
                        Icon(Icons.person, color: RomanSmsTheme.primaryGreen),
                  ),
                  const SizedBox(height: 12),
                  Text('Roman SMS',
                      style: GoogleFonts.inter(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.bold)),
                  Text('Associate Portal',
                      style: GoogleFonts.inter(
                          color: Colors.white70, fontSize: 12)),
                ],
              ),
            ),
            ListTile(
              leading: const Icon(Icons.account_circle),
              title: const Text('Profile & Settings'),
              onTap: () {
                Navigator.pop(context);
                context.push('/profile');
              },
            ),
            ListTile(
              leading: const Icon(Icons.notifications_outlined),
              title: const Text('Notifications'),
              onTap: () {
                Navigator.pop(context);
                context.push('/notifications');
              },
            ),
            ListTile(
              leading: const Icon(Icons.chat_bubble_outline),
              title: const Text('Chat'),
              onTap: () {
                Navigator.pop(context);
                context.push('/chat');
              },
            ),
            ListTile(
              leading: const Icon(Icons.shopping_cart_outlined),
              title: const Text('Buy SMS Credits'),
              onTap: () {
                Navigator.pop(context);
                context.push('/plans');
              },
            ),
            const Divider(),
            ListTile(
              leading: const Icon(Icons.logout, color: Colors.red),
              title:
                  Text('Sign Out', style: GoogleFonts.inter(color: Colors.red)),
              onTap: () async {
                Navigator.pop(context);
                await ref.read(authProvider.notifier).logout();
                if (context.mounted) context.go('/login');
              },
            ),
          ],
        ),
      ),
    );
  }
}