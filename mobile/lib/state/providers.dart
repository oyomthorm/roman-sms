import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../api/client.dart';

final walletProvider = FutureProvider.autoDispose((ref) async {
  final r = await ApiClient.instance.dio.get('/api/v1/wallet');
  return r.data as Map<String, dynamic>;
});

final transactionsProvider = FutureProvider.autoDispose((ref) async {
  final r = await ApiClient.instance.dio.get('/api/v1/wallet/transactions');
  return (r.data['items'] as List).cast<Map<String, dynamic>>();
});

final contactsProvider = FutureProvider.autoDispose((ref) async {
  final r = await ApiClient.instance.dio.get('/api/v1/contacts');
  return (r.data['items'] as List).cast<Map<String, dynamic>>();
});

final campaignsProvider = FutureProvider.autoDispose((ref) async {
  final r = await ApiClient.instance.dio.get('/api/v1/campaigns');
  return (r.data['items'] as List).cast<Map<String, dynamic>>();
});

final campaignDetailProvider = FutureProvider.autoDispose.family((ref, int id) async {
  final r = await ApiClient.instance.dio.get('/api/v1/campaigns/$id');
  return r.data as Map<String, dynamic>;
});

final plansProvider = FutureProvider.autoDispose((ref) async {
  final r = await ApiClient.instance.dio.get('/api/v1/plans');
  return (r.data['items'] as List).cast<Map<String, dynamic>>();
});

final notificationsProvider = FutureProvider.autoDispose((ref) async {
  final r = await ApiClient.instance.dio.get('/api/v1/notifications');
  return (r.data['items'] as List).cast<Map<String, dynamic>>();
});

final chatChannelsProvider = FutureProvider.autoDispose((ref) async {
  final r = await ApiClient.instance.dio.get('/api/v1/chat/channels');
  return (r.data['items'] as List).cast<Map<String, dynamic>>();
});

// For polling, we'll use a StreamProvider
final chatMessagesProvider = StreamProvider.autoDispose.family((ref, int channelId) {
  final controller = StreamController<List<Map<String, dynamic>>>();
  
  Timer? timer;
  Future<void> fetch() async {
    try {
      final r = await ApiClient.instance.dio.get('/api/v1/chat/channels/$channelId/messages');
      if (!controller.isClosed) {
        controller.add((r.data['items'] as List).cast<Map<String, dynamic>>());
      }
    } catch (_) {}
  }

  fetch(); // Initial fetch
  timer = Timer.periodic(const Duration(seconds: 3), (_) => fetch());

  ref.onDispose(() {
    timer?.cancel();
    controller.close();
  });

  return controller.stream;
});

final dashboardStatsProvider = FutureProvider.autoDispose((ref) async {
  final r = await ApiClient.instance.dio.get('/api/v1/dashboard');
  return r.data as Map<String, dynamic>;
});
