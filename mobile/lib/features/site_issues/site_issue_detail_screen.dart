import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/di/providers.dart';
import '../modules/detail_screen.dart';
import 'site_issue_form_screen.dart';

final siteIssueAttachmentsProvider =
    FutureProvider.family<List<Map<String, dynamic>>, int>((
      ref,
      issueId,
    ) async {
      final repo = ref.watch(apiRepositoryProvider);
      return repo.fetchList(
        'site-issue-attachments',
        params: {'issue': issueId},
      );
    });

class SiteIssueDetailScreen extends ConsumerWidget {
  const SiteIssueDetailScreen({super.key, required this.issueId});

  final int issueId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detail = ref.watch(
      detailProvider(DetailRequest('site-issues', issueId)),
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Site Issue'),
        actions: [
          detail.maybeWhen(
            data: (data) => IconButton(
              icon: const Icon(Icons.edit_outlined),
              onPressed: () async {
                final updated = await Navigator.of(context)
                    .push<Map<String, dynamic>>(
                      MaterialPageRoute(
                        builder: (_) => SiteIssueFormScreen(issue: data),
                      ),
                    );
                if (updated != null) {
                  ref.invalidate(
                    detailProvider(DetailRequest('site-issues', issueId)),
                  );
                }
              },
            ),
            orElse: () => const SizedBox.shrink(),
          ),
        ],
      ),
      body: detail.when(
        data: (data) => _SiteIssueDetailBody(issue: data, issueId: issueId),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) =>
            Center(child: Text('Failed to load issue: $error')),
      ),
    );
  }
}

class _SiteIssueDetailBody extends ConsumerStatefulWidget {
  const _SiteIssueDetailBody({required this.issue, required this.issueId});

  final Map<String, dynamic> issue;
  final int issueId;

  @override
  ConsumerState<_SiteIssueDetailBody> createState() =>
      _SiteIssueDetailBodyState();
}

class _SiteIssueDetailBodyState extends ConsumerState<_SiteIssueDetailBody> {
  bool _uploading = false;

  @override
  Widget build(BuildContext context) {
    final attachments = ref.watch(siteIssueAttachmentsProvider(widget.issueId));
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _DetailTile(label: 'Title', value: widget.issue['title']),
        _DetailTile(
          label: 'Project',
          value: widget.issue['project_detail']?['name'],
        ),
        _DetailTile(label: 'Status', value: widget.issue['status']),
        _DetailTile(label: 'Raised On', value: widget.issue['raised_on']),
        _DetailTile(label: 'Resolved On', value: widget.issue['resolved_on']),
        _DetailTile(
          label: 'Raised By',
          value: widget.issue['raised_by_detail']?['full_name'],
        ),
        _DetailTile(
          label: 'Site Visit',
          value: widget.issue['site_visit_detail']?['visit_date'],
        ),
        _DetailTile(label: 'Description', value: widget.issue['description']),
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
        endpoint: 'site-issue-attachments',
        fields: {'issue': widget.issueId},
        file: File(result.files.single.path!),
      );
      ref.invalidate(siteIssueAttachmentsProvider(widget.issueId));
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
