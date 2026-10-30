import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:go_router/go_router.dart';
import '../theme/app_theme.dart';
import '../state/providers.dart';

class ChatChannelsScreen extends ConsumerWidget {
  const ChatChannelsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final channelsAsync = ref.watch(chatChannelsProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text('Messages', style: GoogleFonts.inter(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(chatChannelsProvider),
        child: channelsAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(child: Text('Error: $e')),
          data: (channels) {
            return ListView.builder(
              padding: const EdgeInsets.all(20),
              itemCount: channels.length,
              itemBuilder: (context, index) {
                final ch = channels[index];
                final unread = ch['unread'] as int? ?? 0;
                final isBroadcast = ch['kind'] == 'broadcast';

                return Card(
                  margin: const EdgeInsets.only(bottom: 12),
                  child: ListTile(
                    onTap: () => context.push('/chat/${ch['id']}?name=${ch['name']}'),
                    leading: CircleAvatar(
                      backgroundColor: isBroadcast ? Colors.orange.shade50 : RomanSmsTheme.lightGreen,
                      child: Icon(
                        isBroadcast ? Icons.campaign : Icons.support_agent,
                        color: isBroadcast ? Colors.orange : RomanSmsTheme.primaryGreen,
                      ),
                    ),
                    title: Text(ch['name'], style: GoogleFonts.inter(fontWeight: FontWeight.w600)),
                    subtitle: Text(isBroadcast ? 'Announcements' : 'Direct Message', style: GoogleFonts.inter(fontSize: 12)),
                    trailing: unread > 0 
                      ? CircleAvatar(
                          radius: 12,
                          backgroundColor: RomanSmsTheme.primaryGreen,
                          child: Text('$unread', style: GoogleFonts.inter(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold)),
                        )
                      : const Icon(Icons.chevron_right, color: Colors.grey),
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
