import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/di/providers.dart';
import '../common/app_list_tile.dart';
import 'detail_screen.dart';

final listProvider = FutureProvider.family<List<Map<String, dynamic>>, String>((
  ref,
  endpoint,
) async {
  final repo = ref.watch(apiRepositoryProvider);
  return repo.fetchList(endpoint);
});

class SimpleListScreen extends ConsumerWidget {
  const SimpleListScreen({
    super.key,
    required this.title,
    required this.endpoint,
  });

  final String title;
  final String endpoint;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncItems = ref.watch(listProvider(endpoint));

    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: asyncItems.when(
        data: (items) {
          return RefreshIndicator(
            onRefresh: () async => ref.refresh(listProvider(endpoint).future),
            child: items.isEmpty
                ? ListView(
                    children: [
                      SizedBox(height: 120),
                      Center(child: Text('No records found.')),
                    ],
                  )
                : ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemBuilder: (context, index) {
                      final item = items[index];
                      return AppListTile(
                        title: Text(_itemTitle(item)),
                        subtitle: Text(_itemSubtitle(item)),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () {
                          final id = item['id'];
                          if (id is int) {
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) =>
                                    DetailScreen(endpoint: endpoint, id: id),
                              ),
                            );
                          }
                        },
                      );
                    },
                    separatorBuilder: (context, index) =>
                        const SizedBox(height: 12),
                    itemCount: items.length,
                  ),
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) =>
            Center(child: Text('Failed to load $title: $error')),
      ),
    );
  }

  String _itemTitle(Map<String, dynamic> item) {
    return (item['name'] ??
            item['title'] ??
            item['code'] ??
            item['invoice_number'] ??
            item['receipt_number'] ??
            item['description'] ??
            'Item')
        .toString();
  }

  String _itemSubtitle(Map<String, dynamic> item) {
    final formatter = NumberFormat.compact();
    if (item.containsKey('status')) {
      return 'Status: ${item['status']}';
    }
    if (item.containsKey('amount')) {
      final value = item['amount'];
      final numeric = value is num ? value : num.tryParse(value.toString());
      return 'Amount: ${formatter.format(numeric ?? 0)}';
    }
    if (item.containsKey('email')) {
      return item['email'].toString();
    }
    if (item.containsKey('phone')) {
      return item['phone'].toString();
    }
    if (item.containsKey('date')) {
      return item['date'].toString();
    }
    if (item.containsKey('created_at')) {
      return 'Updated: ${item['created_at']}';
    }
    return 'ID: ${item['id'] ?? '-'}';
  }
}
