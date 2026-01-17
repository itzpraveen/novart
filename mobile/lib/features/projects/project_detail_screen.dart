import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../modules/detail_screen.dart';
import 'project_form_screen.dart';

class ProjectDetailScreen extends ConsumerWidget {
  const ProjectDetailScreen({super.key, required this.projectId});

  final int projectId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detail = ref.watch(
      detailProvider(DetailRequest('projects', projectId)),
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Project Details'),
        actions: [
          detail.maybeWhen(
            data: (data) => IconButton(
              icon: const Icon(Icons.edit_outlined),
              onPressed: () async {
                final updated = await Navigator.of(context)
                    .push<Map<String, dynamic>>(
                      MaterialPageRoute(
                        builder: (_) => ProjectFormScreen(project: data),
                      ),
                    );
                if (updated != null) {
                  ref.invalidate(
                    detailProvider(DetailRequest('projects', projectId)),
                  );
                }
              },
            ),
            orElse: () => const SizedBox.shrink(),
          ),
        ],
      ),
      body: detail.when(
        data: (data) => _ProjectDetailBody(data: data, projectId: projectId),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) =>
            Center(child: Text('Failed to load project: $error')),
      ),
    );
  }
}

class _ProjectDetailBody extends ConsumerWidget {
  const _ProjectDetailBody({required this.data, required this.projectId});

  final Map<String, dynamic> data;
  final int projectId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _DetailTile(label: 'Code', value: data['code']),
        _DetailTile(label: 'Name', value: data['name']),
        _DetailTile(label: 'Client', value: data['client_detail']?['name']),
        _DetailTile(label: 'Stage', value: data['current_stage']),
        _DetailTile(label: 'Health', value: data['health_status']),
        _DetailTile(
          label: 'Project Manager',
          value: data['project_manager_detail']?['full_name'],
        ),
        _DetailTile(
          label: 'Site Engineer',
          value: data['site_engineer_detail']?['full_name'],
        ),
        _DetailTile(label: 'Location', value: data['location']),
        _DetailTile(label: 'Built-up Area', value: data['built_up_area']),
        _DetailTile(label: 'Start Date', value: data['start_date']),
        _DetailTile(
          label: 'Expected Handover',
          value: data['expected_handover'],
        ),
        _DetailTile(label: 'Description', value: data['description']),
        const SizedBox(height: 12),
        ElevatedButton.icon(
          onPressed: () async {
            final stage = await _pickStage(
              context,
              data['current_stage']?.toString(),
            );
            if (!context.mounted) {
              return;
            }
            if (stage == null) {
              return;
            }
            try {
              final repo = ref.read(apiRepositoryProvider);
              await repo.post('projects/$projectId/stage_update/', {
                'stage': stage,
              });
              ref.invalidate(
                detailProvider(DetailRequest('projects', projectId)),
              );
            } catch (error) {
              if (!context.mounted) {
                return;
              }
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('Failed to update stage: $error')),
              );
            }
          },
          icon: const Icon(Icons.sync_alt),
          label: const Text('Update Stage'),
        ),
      ],
    );
  }

  Future<String?> _pickStage(BuildContext context, String? current) async {
    const stages = [
      'Enquiry',
      'Concept',
      'Design Development',
      'Approvals',
      'Working Drawings',
      'Site Execution',
      'Handover',
      'Closed',
    ];
    return showModalBottomSheet<String>(
      context: context,
      builder: (context) => ListView(
        shrinkWrap: true,
        children: stages
            .map(
              (stage) => ListTile(
                title: Text(stage),
                trailing: stage == current ? const Icon(Icons.check) : null,
                onTap: () => Navigator.of(context).pop(stage),
              ),
            )
            .toList(),
      ),
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
