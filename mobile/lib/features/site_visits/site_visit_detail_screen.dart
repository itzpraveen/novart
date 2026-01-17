import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/di/providers.dart';
import '../modules/detail_screen.dart';
import 'site_visit_form_screen.dart';

final siteVisitAttachmentsProvider =
    FutureProvider.family<List<Map<String, dynamic>>, int>((
      ref,
      visitId,
    ) async {
      final repo = ref.watch(apiRepositoryProvider);
      return repo.fetchList(
        'site-visit-attachments',
        params: {'site_visit': visitId},
      );
    });

class SiteVisitDetailScreen extends ConsumerWidget {
  const SiteVisitDetailScreen({super.key, required this.visitId});

  final int visitId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detail = ref.watch(
      detailProvider(DetailRequest('site-visits', visitId)),
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Site Visit'),
        actions: [
          detail.maybeWhen(
            data: (data) => IconButton(
              icon: const Icon(Icons.edit_outlined),
              onPressed: () async {
                final updated = await Navigator.of(context)
                    .push<Map<String, dynamic>>(
                      MaterialPageRoute(
                        builder: (_) => SiteVisitFormScreen(visit: data),
                      ),
                    );
                if (updated != null) {
                  ref.invalidate(
                    detailProvider(DetailRequest('site-visits', visitId)),
                  );
                }
              },
            ),
            orElse: () => const SizedBox.shrink(),
          ),
        ],
      ),
      body: detail.when(
        data: (data) => _SiteVisitDetailBody(visit: data, visitId: visitId),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) =>
            Center(child: Text('Failed to load visit: $error')),
      ),
    );
  }
}

class _SiteVisitDetailBody extends ConsumerStatefulWidget {
  const _SiteVisitDetailBody({required this.visit, required this.visitId});

  final Map<String, dynamic> visit;
  final int visitId;

  @override
  ConsumerState<_SiteVisitDetailBody> createState() =>
      _SiteVisitDetailBodyState();
}

class _SiteVisitDetailBodyState extends ConsumerState<_SiteVisitDetailBody> {
  bool _uploading = false;

  @override
  Widget build(BuildContext context) {
    final attachments = ref.watch(siteVisitAttachmentsProvider(widget.visitId));
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _DetailTile(
          label: 'Project',
          value: widget.visit['project_detail']?['name'],
        ),
        _DetailTile(label: 'Visit Date', value: widget.visit['visit_date']),
        _DetailTile(
          label: 'Visited By',
          value: widget.visit['visited_by_detail']?['full_name'],
        ),
        _DetailTile(label: 'Location', value: widget.visit['location']),
        _DetailTile(label: 'Expenses', value: widget.visit['expenses']),
        _DetailTile(label: 'Notes', value: widget.visit['notes']),
        const SizedBox(height: 12),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('Attachments', style: Theme.of(context).textTheme.titleMedium),
            TextButton.icon(
              onPressed: _uploading ? null : () => _addAttachment(context),
              icon: const Icon(Icons.attach_file),
              label: const Text('Add'),
            ),
          ],
        ),
        attachments.when(
          data: (items) {
            if (items.isEmpty) {
              return const Text('No attachments yet.');
            }
            return Wrap(
              spacing: 8,
              runSpacing: 8,
              children: items
                  .map(
                    (attachment) => ActionChip(
                      label: Text(
                        _attachmentLabel(
                          attachment['file']?.toString() ?? 'Attachment',
                        ),
                      ),
                      onPressed: () =>
                          _openAttachment(attachment['file']?.toString() ?? ''),
                    ),
                  )
                  .toList(),
            );
          },
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => Text('Failed to load attachments: $error'),
        ),
      ],
    );
  }

  Future<void> _addAttachment(BuildContext context) async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['pdf', 'png', 'jpg', 'jpeg'],
    );
    if (result == null || result.files.single.path == null) {
      return;
    }
    setState(() => _uploading = true);
    try {
      final repo = ref.read(apiRepositoryProvider);
      await repo.uploadFile(
        endpoint: 'site-visit-attachments',
        fields: {'site_visit': widget.visitId},
        file: File(result.files.single.path!),
      );
      ref.invalidate(siteVisitAttachmentsProvider(widget.visitId));
    } catch (error) {
      if (!context.mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to upload attachment: $error')),
      );
    } finally {
      if (mounted) {
        setState(() => _uploading = false);
      }
    }
  }

  String _attachmentLabel(String url) {
    final parts = url.split('/');
    return parts.isEmpty ? 'Attachment' : parts.last;
  }

  Future<void> _openAttachment(String url) async {
    if (url.isEmpty) {
      return;
    }
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
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
