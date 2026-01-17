import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../modules/detail_screen.dart';
import 'document_form_screen.dart';

class DocumentDetailScreen extends ConsumerWidget {
  const DocumentDetailScreen({super.key, required this.documentId});

  final int documentId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detail = ref.watch(
      detailProvider(DetailRequest('documents', documentId)),
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Document'),
        actions: [
          detail.maybeWhen(
            data: (data) => IconButton(
              icon: const Icon(Icons.edit_outlined),
              onPressed: () async {
                final updated = await Navigator.of(context)
                    .push<Map<String, dynamic>>(
                      MaterialPageRoute(
                        builder: (_) => DocumentFormScreen(document: data),
                      ),
                    );
                if (updated != null) {
                  ref.invalidate(
                    detailProvider(DetailRequest('documents', documentId)),
                  );
                }
              },
            ),
            orElse: () => const SizedBox.shrink(),
          ),
        ],
      ),
      body: detail.when(
        data: (data) => _DocumentDetailBody(document: data),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) =>
            Center(child: Text('Failed to load document: $error')),
      ),
    );
  }
}

class _DocumentDetailBody extends StatelessWidget {
  const _DocumentDetailBody({required this.document});

  final Map<String, dynamic> document;

  @override
  Widget build(BuildContext context) {
    final fileUrl = document['file']?.toString() ?? '';
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _DetailTile(label: 'File name', value: document['file_name']),
        _DetailTile(
          label: 'Project',
          value: document['project_detail']?['name'],
        ),
        _DetailTile(label: 'File type', value: document['file_type']),
        _DetailTile(label: 'Version', value: document['version']),
        _DetailTile(label: 'Notes', value: document['notes']),
        _DetailTile(
          label: 'Uploaded by',
          value: document['uploaded_by_detail']?['full_name'],
        ),
        const SizedBox(height: 12),
        if (fileUrl.isNotEmpty)
          ElevatedButton.icon(
            onPressed: () => _openFile(fileUrl),
            icon: const Icon(Icons.open_in_new),
            label: const Text('Open File'),
          )
        else
          const Text('No file uploaded for this document.'),
      ],
    );
  }

  Future<void> _openFile(String url) async {
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
