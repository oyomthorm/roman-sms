import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';
import '../state/providers.dart';
import '../widgets/add_contact_sheet.dart';
import 'contact_detail_screen.dart';

class GroupDetailScreen extends ConsumerStatefulWidget {
  final int groupId;
  final String? initialGroupName;

  const GroupDetailScreen({
    super.key,
    required this.groupId,
    this.initialGroupName,
  });

  @override
  ConsumerState<GroupDetailScreen> createState() => _GroupDetailScreenState();
}

class _GroupDetailScreenState extends ConsumerState<GroupDetailScreen> {
  Future<void> _openAddSheet() async {
    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (context) => AddContactSheet(initialGroupId: widget.groupId),
    );
    ref.invalidate(groupContactsProvider(widget.groupId));
  }

  Future<void> _openContact(Map<String, dynamic> contact) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ContactDetailScreen(initialContact: contact),
      ),
    );
    ref.invalidate(groupContactsProvider(widget.groupId));
  }

  @override
  Widget build(BuildContext context) {
    final groupAsync = ref.watch(groupContactsProvider(widget.groupId));

    return Scaffold(
      appBar: AppBar(
        title: Text(
          widget.initialGroupName ?? 'Group #${widget.groupId}',
          style: GoogleFonts.inter(fontWeight: FontWeight.bold),
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openAddSheet,
        backgroundColor: RomanSmsTheme.primaryGreen,
        icon: const Icon(Icons.person_add, color: Colors.white),
        label: Text('Add Contact',
            style: GoogleFonts.inter(
                color: Colors.white, fontWeight: FontWeight.bold)),
      ),
      body: RefreshIndicator(
        onRefresh: () async =>
            ref.invalidate(groupContactsProvider(widget.groupId)),
        child: groupAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) =>
              Center(child: Text('Error loading group: $e')),
          data: (payload) {
            final group = payload['group'] as Map<String, dynamic>? ?? {};
            final contacts = (payload['contacts'] as List)
                .cast<Map<String, dynamic>>();
            final stats =
                payload['stats'] as Map<String, dynamic>? ?? {};

            final title =
                (group['name'] as String?) ?? widget.initialGroupName ?? 'Group';
            final total = (stats['total'] as num?)?.toInt() ?? contacts.length;
            final optedOut = (stats['opted_out'] as num?)?.toInt() ??
                contacts.where((c) => c['opted_out'] == true).length;

            return ListView(
              padding: const EdgeInsets.all(20),
              children: [
                Text(
                  title,
                  style: GoogleFonts.inter(
                      fontSize: 20, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    _buildCircleStat('Total', total.toString()),
                    _buildCircleStat('Opt-outs', optedOut.toString(),
                        isWarning: true),
                  ],
                ),
                const SizedBox(height: 24),
                if (contacts.isEmpty)
                  Center(
                    child: Padding(
                      padding: const EdgeInsets.all(32.0),
                      child: Text('No contacts in this group yet.',
                          style: GoogleFonts.inter(
                              color: RomanSmsTheme.textMuted)),
                    ),
                  )
                else
                  Card(
                    child: Column(
                      children: contacts.asMap().entries.map((entry) {
                        final index = entry.key;
                        final contact = entry.value;
                        final isOptedOut = contact['opted_out'] == true;

                        return Column(
                          children: [
                            ListTile(
                              onTap: () => _openContact(contact),
                              leading: CircleAvatar(
                                backgroundColor: isOptedOut
                                    ? Colors.grey.shade200
                                    : RomanSmsTheme.lightGreen,
                                child: Icon(Icons.person,
                                    color: isOptedOut
                                        ? Colors.grey
                                        : RomanSmsTheme.primaryGreen),
                              ),
                              title: Text(
                                contact['name'] ?? 'Unknown Name',
                                style: GoogleFonts.inter(
                                    fontWeight: FontWeight.w600, fontSize: 14),
                              ),
                              subtitle: Text(contact['phone'],
                                  style: GoogleFonts.inter(fontSize: 12)),
                              trailing: isOptedOut
                                  ? Container(
                                      padding: const EdgeInsets.symmetric(
                                          horizontal: 8, vertical: 4),
                                      decoration: BoxDecoration(
                                        color: Colors.red.shade50,
                                        borderRadius: BorderRadius.circular(8),
                                      ),
                                      child: Text('Opted Out',
                                          style: GoogleFonts.inter(
                                              fontSize: 10,
                                              color: Colors.red,
                                              fontWeight: FontWeight.bold)),
                                    )
                                  : const Icon(Icons.chevron_right,
                                      color: Colors.grey),
                            ),
                            if (index < contacts.length - 1)
                              const Divider(height: 1, indent: 60),
                          ],
                        );
                      }).toList(),
                    ),
                  ),
                const SizedBox(height: 80),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _buildCircleStat(String label, String value,
      {bool isWarning = false}) {
    return Column(
      children: [
        Container(
          width: 100,
          height: 100,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: Colors.white,
            border: Border.all(
              color: isWarning ? Colors.red.shade100 : RomanSmsTheme.lightGreen,
              width: 4,
            ),
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
              value,
              style: GoogleFonts.inter(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: isWarning ? Colors.red : RomanSmsTheme.primaryGreen,
              ),
            ),
          ),
        ),
        const SizedBox(height: 8),
        Text(label,
            style: GoogleFonts.inter(
                fontSize: 12,
                color: RomanSmsTheme.textMuted,
                fontWeight: FontWeight.w600)),
      ],
    );
  }
}