import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import 'app_list_tile.dart';

class SelectOption {
  SelectOption({required this.id, required this.label, required this.raw});

  final int id;
  final String label;
  final Map<String, dynamic> raw;
}

class SelectQuery {
  SelectQuery(this.endpoint, this.search);

  final String endpoint;
  final String search;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is SelectQuery &&
          endpoint == other.endpoint &&
          search == other.search;

  @override
  int get hashCode => Object.hash(endpoint, search);
}

final selectOptionsProvider =
    FutureProvider.family<List<Map<String, dynamic>>, SelectQuery>((
      ref,
      query,
    ) async {
      final repo = ref.watch(apiRepositoryProvider);
      final params = <String, dynamic>{};
      if (query.search.isNotEmpty) {
        params['search'] = query.search;
      }
      return repo.fetchList(
        query.endpoint,
        params: params.isEmpty ? null : params,
      );
    });

class SelectListScreen extends ConsumerStatefulWidget {
  const SelectListScreen({
    super.key,
    required this.title,
    required this.endpoint,
  });

  final String title;
  final String endpoint;

  @override
  ConsumerState<SelectListScreen> createState() => _SelectListScreenState();
}

class _SelectListScreenState extends ConsumerState<SelectListScreen> {
  String _search = '';

  @override
  Widget build(BuildContext context) {
    final asyncItems = ref.watch(
      selectOptionsProvider(SelectQuery(widget.endpoint, _search)),
    );

    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              decoration: const InputDecoration(
                hintText: 'Search...',
                prefixIcon: Icon(Icons.search),
              ),
              onChanged: (value) => setState(() => _search = value.trim()),
            ),
          ),
          Expanded(
            child: asyncItems.when(
              data: (items) {
                if (items.isEmpty) {
                  return const Center(child: Text('No matches found.'));
                }
                return ListView.separated(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  itemBuilder: (context, index) {
                    final item = items[index];
                    final label = _labelFor(item);
                    final subtitle = _subtitleFor(item);
                    return AppListTile(
                      title: Text(label),
                      subtitle: subtitle.isEmpty ? null : Text(subtitle),
                      onTap: () {
                        final id = item['id'] as int?;
                        if (id != null) {
                          Navigator.of(
                            context,
                          ).pop(SelectOption(id: id, label: label, raw: item));
                        }
                      },
                    );
                  },
                  separatorBuilder: (context, index) =>
                      const SizedBox(height: 12),
                  itemCount: items.length,
                );
              },
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) =>
                  Center(child: Text('Failed to load: $error')),
            ),
          ),
        ],
      ),
    );
  }

  String _labelFor(Map<String, dynamic> item) {
    return (item['name'] ??
            item['title'] ??
            item['code'] ??
            item['username'] ??
            item['email'] ??
            'Item')
        .toString();
  }

  String _subtitleFor(Map<String, dynamic> item) {
    if (item['phone'] != null && item['phone'].toString().isNotEmpty) {
      return item['phone'].toString();
    }
    if (item['email'] != null && item['email'].toString().isNotEmpty) {
      return item['email'].toString();
    }
    if (item['role'] != null) {
      return item['role'].toString();
    }
    return '';
  }
}
