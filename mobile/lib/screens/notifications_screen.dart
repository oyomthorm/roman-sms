import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import '../api/client.dart';
import '../theme/app_theme.dart';
import '../state/providers.dart';

class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifAsync = ref.watch(notificationsProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text('Notifications', style: GoogleFonts.inter(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(notificationsProvider),
        child: notifAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(child: Text('Error: $e')),
          data: (items) {
            if (items.isEmpty) {
              return Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.notifications_none, size: 64, color: Colors.grey),
                    const SizedBox(height: 16),
                    Text('You are all caught up!', style: GoogleFonts.inter(fontSize: 16, color: RomanSmsTheme.textMuted)),
                  ],
                ),
              );
            }

            return ListView.builder(
              padding: const EdgeInsets.all(20),
              itemCount: items.length,
              itemBuilder: (context, index) {
                final n = items[index];
                final isDanger = n['type'] == 'danger';
                final isWarning = n['type'] == 'warning';
                final isSuccess = n['type'] == 'success';
                
                Color bgColor = Colors.white;
                Color iconColor = RomanSmsTheme.primaryGreen;
                IconData icon = Icons.info_outline;

                if (isDanger) { iconColor = Colors.red; icon = Icons.error_outline; bgColor = Colors.red.shade50; }
                else if (isWarning) { iconColor = Colors.orange; icon = Icons.warning_amber; bgColor = Colors.orange.shade50; }
                else if (isSuccess) { iconColor = RomanSmsTheme.primaryGreen; icon = Icons.check_circle_outline; bgColor = RomanSmsTheme.lightGreen; }

                return Dismissible(
                  key: Key(n['key']),
                  direction: DismissDirection.endToStart,
                  background: Container(
                    alignment: Alignment.centerRight,
                    padding: const EdgeInsets.only(right: 20),
                    color: Colors.red,
                    child: const Icon(Icons.delete, color: Colors.white),
                  ),
                  onDismissed: (_) async {
                    await ApiClient.instance.dio.post('/api/v1/notifications/${n['key']}/dismiss');
                    ref.invalidate(notificationsProvider);
                  },
                  child: Card(
                    color: bgColor,
                    margin: const EdgeInsets.only(bottom: 12),
                    child: ListTile(
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      leading: Icon(icon, color: iconColor, size: 28),
                      title: Text(n['title'], style: GoogleFonts.inter(fontWeight: FontWeight.bold, fontSize: 14)),
                      subtitle: Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text(n['body'], style: GoogleFonts.inter(fontSize: 13)),
                      ),
                    ),
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }
}
