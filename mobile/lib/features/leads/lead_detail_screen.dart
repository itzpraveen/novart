import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../modules/detail_screen.dart';
import 'lead_convert_screen.dart';
import 'lead_form_screen.dart';

class LeadDetailScreen extends ConsumerWidget {
  const LeadDetailScreen({super.key, required this.leadId});

  final int leadId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detail = ref.watch(detailProvider(DetailRequest('leads', leadId)));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Lead Details'),
        actions: [
          detail.maybeWhen(
            data: (data) => IconButton(
              icon: const Icon(Icons.edit_outlined),
              onPressed: () async {
                final updated = await Navigator.of(context)
                    .push<Map<String, dynamic>>(
                      MaterialPageRoute(
                        builder: (_) => LeadFormScreen(lead: data),
                      ),
                    );
                if (updated != null) {
                  ref.invalidate(
                    detailProvider(DetailRequest('leads', leadId)),
                  );
                }
              },
            ),
            orElse: () => const SizedBox.shrink(),
          ),
        ],
      ),
      body: detail.when(
        data: (data) => _LeadDetailBody(data: data),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Failed to load lead: $error')),
      ),
      floatingActionButton: detail.maybeWhen(
        data: (data) {
          final status = data['status']?.toString() ?? '';
          final isConverted = data['is_converted'] == true;
          if (status == 'lost' || isConverted) {
            return null;
          }
          return FloatingActionButton.extended(
            onPressed: () async {
              await Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => LeadConvertScreen(lead: data),
                ),
              );
              ref.invalidate(detailProvider(DetailRequest('leads', leadId)));
            },
            label: const Text('Convert'),
            icon: const Icon(Icons.swap_horiz),
          );
        },
        orElse: () => null,
      ),
    );
  }
}

class _LeadDetailBody extends StatelessWidget {
  const _LeadDetailBody({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _DetailTile(label: 'Title', value: data['title']),
        _DetailTile(label: 'Client', value: data['client_detail']?['name']),
        _DetailTile(label: 'Status', value: data['status']),
        _DetailTile(label: 'Lead Source', value: data['lead_source']),
        _DetailTile(label: 'Estimated Value', value: data['estimated_value']),
        _DetailTile(label: 'Notes', value: data['notes']),
        _DetailTile(label: 'Planning Details', value: data['planning_details']),
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
