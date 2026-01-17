import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';

class DetailRequest {
  DetailRequest(this.endpoint, this.id);

  final String endpoint;
  final int id;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is DetailRequest && endpoint == other.endpoint && id == other.id;

  @override
  int get hashCode => Object.hash(endpoint, id);
}

final detailProvider =
    FutureProvider.family<Map<String, dynamic>, DetailRequest>((
      ref,
      request,
    ) async {
      final repo = ref.watch(apiRepositoryProvider);
      return repo.fetchDetail(request.endpoint, request.id);
    });

class DetailScreen extends ConsumerWidget {
  const DetailScreen({
    super.key,
    required this.endpoint,
    required this.id,
    this.initialData,
  });

  final String endpoint;
  final int id;
  final Map<String, dynamic>? initialData;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncValue = ref.watch(detailProvider(DetailRequest(endpoint, id)));
    return Scaffold(
      appBar: AppBar(title: const Text('Details')),
      body: asyncValue.when(
        data: (data) => _DetailBody(data: data),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) =>
            Center(child: Text('Failed to load details: $error')),
      ),
    );
  }
}

class _DetailBody extends StatelessWidget {
  const _DetailBody({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final entries = data.entries.toList();
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemBuilder: (context, index) {
        final entry = entries[index];
        return Container(
          padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                entry.key.toString(),
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                  color: Theme.of(context).colorScheme.primary,
                ),
              ),
              const SizedBox(height: 6),
              Text(_formatValue(entry.value)),
            ],
          ),
        );
      },
      separatorBuilder: (context, index) => const SizedBox(height: 10),
      itemCount: entries.length,
    );
  }

  String _formatValue(dynamic value) {
    if (value == null) {
      return '-';
    }
    if (value is Map) {
      return value.entries
          .map((entry) => '${entry.key}: ${entry.value}')
          .join('\n');
    }
    if (value is List) {
      return value.map((item) => item.toString()).join('\n');
    }
    return value.toString();
  }
}
