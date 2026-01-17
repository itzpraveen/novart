import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../modules/detail_screen.dart';
import 'client_form_screen.dart';

class ClientDetailScreen extends ConsumerWidget {
  const ClientDetailScreen({super.key, required this.clientId});

  final int clientId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detail = ref.watch(
      detailProvider(DetailRequest('clients', clientId)),
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Client Details'),
        actions: [
          detail.maybeWhen(
            data: (data) => IconButton(
              icon: const Icon(Icons.edit_outlined),
              onPressed: () async {
                final updated = await Navigator.of(context)
                    .push<Map<String, dynamic>>(
                      MaterialPageRoute(
                        builder: (_) => ClientFormScreen(client: data),
                      ),
                    );
                if (updated != null) {
                  ref.invalidate(
                    detailProvider(DetailRequest('clients', clientId)),
                  );
                }
              },
            ),
            orElse: () => const SizedBox.shrink(),
          ),
        ],
      ),
      body: detail.when(
        data: (data) => _ClientDetailBody(data: data),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) =>
            Center(child: Text('Failed to load client: $error')),
      ),
    );
  }
}

class _ClientDetailBody extends StatelessWidget {
  const _ClientDetailBody({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _DetailTile(label: 'Name', value: data['name']),
        _DetailTile(label: 'Phone', value: data['phone']),
        _DetailTile(label: 'Email', value: data['email']),
        _DetailTile(label: 'Address', value: data['address']),
        _DetailTile(label: 'City', value: data['city']),
        _DetailTile(label: 'State', value: data['state']),
        _DetailTile(label: 'Postal Code', value: data['postal_code']),
        _DetailTile(label: 'Notes', value: data['notes']),
      ],
    );
  }
}

class _DetailTile extends StatelessWidget {
  const _DetailTile({required this.label, this.value});

  final String label;
  final dynamic value;

  @override
  Widget build(BuildContext context) {
    final display = value?.toString().trim();
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                color: Theme.of(context).colorScheme.primary,
              ),
            ),
            const SizedBox(height: 6),
            Text(display == null || display.isEmpty ? '-' : display),
          ],
        ),
      ),
    );
  }
}
