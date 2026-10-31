import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import '../api/client.dart';
import '../theme/app_theme.dart';
import '../state/providers.dart';
import '../widgets/group_picker_dialog.dart';

class ContactDetailScreen extends ConsumerStatefulWidget {
  final Map<String, dynamic> initialContact;
  const ContactDetailScreen({super.key, required this.initialContact});

  @override
  ConsumerState<ContactDetailScreen> createState() =>
      _ContactDetailScreenState();
}

class _ContactDetailScreenState extends ConsumerState<ContactDetailScreen> {
  late String? _name;
  late bool _optedOut;
  bool _optingOut = false;
  bool _deleting = false;

  int get _contactId => widget.initialContact['id'] as int;
  String get _phone => widget.initialContact['phone'] as String? ?? '';
  // NOTE: _districtId is intentionally still a getter. It has the same
  // staleness bug _groupId had, but district editing is not in scope
  // this round — a future district picker will promote it to state too.
  int? get _districtId => widget.initialContact['district_id'] as int?;

  int? _groupId; // state: promoted from getter so picker PATCH can update it

  @override
  void initState() {
    super.initState();
    _name = widget.initialContact['name'] as String?;
    _optedOut = widget.initialContact['opted_out'] == true;
    _groupId = widget.initialContact['group_id'] as int?;
    _refresh();
  }

  Future<void> _refresh() async {
    try {
      final r =
          await ApiClient.instance.dio.get('/api/v1/contacts/$_contactId');
      if (!mounted) return;
      setState(() {
        _name = r.data['name'] as String?;
        _optedOut = r.data['opted_out'] == true;
        _groupId = r.data['group_id'] as int?; // was missing — fixed
      });
    } catch (_) {
      // Silent. We have initial data from the list; a failed refresh is not fatal.
    }
  }

  Future<void> _pickGroup() async {
    final result = await GroupPickerDialog.show(
      context,
      currentGroupId: _groupId,
    );
    if (!result.picked) return;

    try {
      final r = await ApiClient.instance.dio.patch(
        '/api/v1/contacts/$_contactId',
        data: {'group_id': result.groupId}, // null clears, int sets
      );
      if (!mounted) return;
      setState(() => _groupId = r.data['group_id'] as int?);
      ref.invalidate(contactsProvider);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to update group: $e')),
      );
    }
  }

  Future<void> _editName() async {
    final controller = TextEditingController(text: _name ?? '');
    final newName = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Edit Name'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(
            labelText: 'Name',
            hintText: 'Leave empty to clear',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, controller.text.trim()),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    if (newName == null) return;

    try {
      final r = await ApiClient.instance.dio.patch(
        '/api/v1/contacts/$_contactId',
        data: {'name': newName},
      );
      if (!mounted) return;
      setState(() => _name = r.data['name'] as String?);
      ref.invalidate(contactsProvider);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to update name: $e')),
      );
    }
  }

  Future<void> _optOut() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Opt out this contact?'),
        content: Text(
          '$_phone will be added to the platform-wide opt-out list and will not receive further SMS.',
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Opt Out'),
          ),
        ],
      ),
    );
    if (ok != true) return;

    setState(() => _optingOut = true);
    try {
      await ApiClient.instance.dio.post('/api/v1/contacts/$_contactId/optout');
      if (!mounted) return;
      setState(() => _optedOut = true);
      ref.invalidate(contactsProvider);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to opt out: $e')),
      );
    } finally {
      if (mounted) setState(() => _optingOut = false);
    }
  }

  Future<void> _delete() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete this contact?'),
        content: Text(
            '$_phone will be removed from your contact list. This cannot be undone.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (ok != true) return;

    setState(() => _deleting = true);
    try {
      await ApiClient.instance.dio.delete('/api/v1/contacts/$_contactId');
      if (!mounted) return;
      ref.invalidate(contactsProvider);
      Navigator.pop(context);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to delete: $e')),
      );
      setState(() => _deleting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final displayName =
        (_name == null || _name!.isEmpty) ? 'Unnamed contact' : _name!;

    // Resolve group name for the tile. If the provider is loading or errored,
    // fall back to "Group #id" — the tile must render even if the group list
    // call fails, because the contact itself loaded fine.
    String? groupName;
    if (_groupId != null) {
      ref.watch(groupsProvider).whenData((groups) {
        for (final g in groups) {
          if (g['id'] == _groupId) {
            groupName = g['name'] as String?;
            break;
          }
        }
      });
    }
    final groupSubtitle =
        _groupId == null ? '—' : (groupName ?? 'Group #$_groupId');

    return Scaffold(
      appBar: AppBar(
        title: Text(displayName,
            style: GoogleFonts.inter(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.edit),
            onPressed: _optingOut || _deleting ? null : _editName,
            tooltip: 'Edit name',
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline, color: Colors.red),
            onPressed: _optingOut || _deleting ? null : _delete,
            tooltip: 'Delete',
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Center(
            child: CircleAvatar(
              radius: 40,
              backgroundColor:
                  _optedOut ? Colors.grey.shade300 : RomanSmsTheme.lightGreen,
              child: Icon(
                Icons.person,
                size: 40,
                color: _optedOut ? Colors.grey : RomanSmsTheme.primaryGreen,
              ),
            ),
          ),
          const SizedBox(height: 16),
          Center(
            child: Text(displayName,
                style: GoogleFonts.inter(
                    fontSize: 20, fontWeight: FontWeight.bold)),
          ),
          if (_optedOut)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Center(
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.red.shade50,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    'OPTED OUT',
                    style: GoogleFonts.inter(
                        fontSize: 11,
                        color: Colors.red,
                        fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ),
          const SizedBox(height: 32),
          Card(
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.phone),
                  title: Text('Phone',
                      style: GoogleFonts.inter(
                          fontSize: 12, color: RomanSmsTheme.textMuted)),
                  subtitle: Text(_phone,
                      style: GoogleFonts.inter(fontWeight: FontWeight.w600)),
                ),
                const Divider(height: 1, indent: 60),
                ListTile(
                  leading: const Icon(Icons.group),
                  title: Text('Group',
                      style: GoogleFonts.inter(
                          fontSize: 12, color: RomanSmsTheme.textMuted)),
                  subtitle: Text(groupSubtitle,
                      style: GoogleFonts.inter(fontWeight: FontWeight.w600)),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: (_optingOut || _deleting) ? null : _pickGroup,
                ),
                const Divider(height: 1, indent: 60),
                ListTile(
                  leading: const Icon(Icons.location_on),
                  title: Text('District',
                      style: GoogleFonts.inter(
                          fontSize: 12, color: RomanSmsTheme.textMuted)),
                  subtitle: Text(
                      _districtId == null ? '—' : 'District #$_districtId',
                      style: GoogleFonts.inter(fontWeight: FontWeight.w600)),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          if (!_optedOut)
            ElevatedButton.icon(
              onPressed: _optingOut ? null : _optOut,
              icon: _optingOut
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white),
                    )
                  : const Icon(Icons.block),
              label: Text(_optingOut ? 'Opting out…' : 'Opt Out This Contact'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.orange.shade700,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12)),
              ),
            ),
        ],
      ),
    );
  }
} 
