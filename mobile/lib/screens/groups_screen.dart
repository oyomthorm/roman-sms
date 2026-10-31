import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../state/providers.dart';
import '../theme/app_theme.dart';

class GroupsScreen extends ConsumerWidget {
  const GroupsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final groupsAsync = ref.watch(groupsProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text('Groups',
            style: GoogleFonts.inter(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(groupsProvider),
        child: groupsAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(child: Text('Error loading groups: $e')),
          data: (groups) {
            final totalGroups = groups.length;

            return ListView(
              padding: const EdgeInsets.all(20),
              children: [
                // Single stat circle: total groups
                Center(
                  child: Column(
                    children: [
                      Container(
                        width: 100,
                        height: 100,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: Colors.white,
                          border: Border.all(
                              color: RomanSmsTheme.lightGreen, width: 4),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withValues(alpha: 0.02),
                              blurRadius: 10,
                              offset: const Offset(0, 4),
                            ),
                          ],
                        ),
                        child: Center(
                          child: Text(
                            totalGroups.toString(),
                            style: GoogleFonts.inter(
                              fontSize: 24,
                              fontWeight: FontWeight.bold,
                              color: RomanSmsTheme.primaryGreen,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text('Groups',
                          style: GoogleFonts.inter(
                              fontSize: 12,
                              color: RomanSmsTheme.textMuted,
                              fontWeight: FontWeight.w600)),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
                Text('All Groups',
                    style: GoogleFonts.inter(
                        fontSize: 18, fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                if (groups.isEmpty)
                  Center(
                    child: Padding(
                      padding: const EdgeInsets.all(32.0),
                      child: Text(
                        'No groups yet. Create one in the web panel.',
                        textAlign: TextAlign.center,
                        style:
                            GoogleFonts.inter(color: RomanSmsTheme.textMuted),
                      ),
                    ),
                  )
                else
                  Card(
                    child: Column(
                      children: groups.asMap().entries.map((entry) {
                        final index = entry.key;
                        final group = entry.value;
                        final count = group['contact_count'];
                        final countLabel =
                            count is int ? '$count contact(s)' : '—';

                        return Column(
                          children: [
                            ListTile(
                              leading: CircleAvatar(
                                backgroundColor: RomanSmsTheme.lightGreen,
                                child: Icon(Icons.group,
                                    color: RomanSmsTheme.primaryGreen),
                              ),
                              title: Text(
                                (group['name'] as String?) ?? 'Unnamed group',
                                style: GoogleFonts.inter(
                                    fontWeight: FontWeight.w600, fontSize: 14),
                              ),
                              subtitle: Text(countLabel,
                                  style: GoogleFonts.inter(fontSize: 12)),
                              // No chevron, no onTap — R6b adds group detail.
                            ),
                            if (index < groups.length - 1)
                              const Divider(height: 1, indent: 60),
                          ],
                        );
                      }).toList(),
                    ),
                  ),
                const SizedBox(height: 20),
              ],
            );
          },
        ),
      ),
    );
  }
}
