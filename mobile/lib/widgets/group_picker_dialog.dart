import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../state/providers.dart';
import '../theme/app_theme.dart';

/// Result of a group picker interaction.
/// - picked == false: user cancelled, no change intended
/// - picked == true, groupId == null: user chose "None (remove from group)"
/// - picked == true, groupId != null: user selected that group
typedef GroupPickerResult = ({bool picked, int? groupId});

class GroupPickerDialog extends ConsumerWidget {
  final int? currentGroupId;

  const GroupPickerDialog({super.key, this.currentGroupId});

  static Future<GroupPickerResult> show(
    BuildContext context, {
    int? currentGroupId,
  }) async {
    final result = await showDialog<GroupPickerResult>(
      context: context,
      builder: (_) => GroupPickerDialog(currentGroupId: currentGroupId),
    );
    // Dialog dismissed by tapping outside / back button
    return result ?? (picked: false, groupId: null);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final groupsAsync = ref.watch(groupsProvider);

    return AlertDialog(
      title: Text('Select group',
          style: GoogleFonts.inter(fontWeight: FontWeight.bold)),
      contentPadding: const EdgeInsets.symmetric(vertical: 12),
      content: SizedBox(
        width: double.maxFinite,
        child: groupsAsync.when(
          loading: () => const Padding(
            padding: EdgeInsets.all(24),
            child: Center(child: CircularProgressIndicator()),
          ),
          error: (e, _) => Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('Couldn\'t load groups.',
                    style: GoogleFonts.inter(color: Colors.red)),
                const SizedBox(height: 8),
                TextButton(
                  onPressed: () => ref.invalidate(groupsProvider),
                  child: const Text('Retry'),
                ),
              ],
            ),
          ),
          data: (groups) {
            if (groups.isEmpty) {
              return Padding(
                padding: const EdgeInsets.all(24),
                child: Text(
                  'No groups yet — create one in the web panel.',
                  textAlign: TextAlign.center,
                  style: GoogleFonts.inter(color: RomanSmsTheme.textMuted),
                ),
              );
            }
            return ListView(
              shrinkWrap: true,
              children: [
                ListTile(
                  leading: const Icon(Icons.block),
                  title: Text('None (remove from group)',
                      style: GoogleFonts.inter(fontWeight: FontWeight.w500)),
                  trailing: currentGroupId == null
                      ? const Icon(Icons.check,
                          color: RomanSmsTheme.primaryGreen)
                      : null,
                  onTap: () =>
                      Navigator.pop(context, (picked: true, groupId: null)),
                ),
                const Divider(height: 1),
                for (final g in groups)
                  ListTile(
                    leading: const Icon(Icons.group),
                    title: Text(
                      (g['name'] as String?) ?? 'Group #${g['id']}',
                      style: GoogleFonts.inter(fontWeight: FontWeight.w500),
                    ),
                    subtitle: (g['contact_count'] is int)
                        ? Text('${g['contact_count']} contact(s)',
                            style: GoogleFonts.inter(
                                fontSize: 12, color: RomanSmsTheme.textMuted))
                        : null,
                    trailing: currentGroupId == g['id']
                        ? const Icon(Icons.check,
                            color: RomanSmsTheme.primaryGreen)
                        : null,
                    onTap: () => Navigator.pop(
                        context, (picked: true, groupId: g['id'] as int)),
                  ),
              ],
            );
          },
        ),
      ),
      actions: [
        TextButton(
          onPressed: () =>
              Navigator.pop(context, (picked: false, groupId: null)),
          child: const Text('Cancel'),
        ),
      ],
    );
  }
}