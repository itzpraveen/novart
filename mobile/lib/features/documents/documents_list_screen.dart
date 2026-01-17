import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../common/app_list_tile.dart';
import '../common/select_list_screen.dart';
import 'document_detail_screen.dart';
import 'document_form_screen.dart';

class DocumentQuery {
  DocumentQuery(this.projectId, this.fileType);

  final int? projectId;
  final String fileType;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is DocumentQuery &&
          projectId == other.projectId &&
          fileType == other.fileType;

  @override
  int get hashCode => Object.hash(projectId, fileType);
}

final documentsProvider =
    FutureProvider.family<List<Map<String, dynamic>>, DocumentQuery>((
      ref,
      query,
    ) async {
      final repo = ref.watch(apiRepositoryProvider);
      final params = <String, dynamic>{};
      if (query.projectId != null) {
        params['project'] = query.projectId;
      }
      if (query.fileType.isNotEmpty) {
        params['file_type'] = query.fileType;
      }
      return repo.fetchList(
        'documents',
        params: params.isEmpty ? null : params,
      );
    });

class DocumentsListScreen extends ConsumerStatefulWidget {
  const DocumentsListScreen({super.key});

  @override
  ConsumerState<DocumentsListScreen> createState() =>
      _DocumentsListScreenState();
}

class _DocumentsListScreenState extends ConsumerState<DocumentsListScreen> {
  String _search = '';
  String _fileType = '';
  int? _projectId;
  String _projectLabel = '';

  @override
  Widget build(BuildContext context) {
    final asyncDocs = ref.watch(
      documentsProvider(DocumentQuery(_projectId, _fileType)),
    );

    return Scaffold(
      appBar: AppBar(title: const Text('Documents')),
      floatingActionButton: FloatingActionButton(
        onPressed: () async {
          final created = await Navigator.of(context)
              .push<Map<String, dynamic>>(
                MaterialPageRoute(builder: (_) => const DocumentFormScreen()),
              );
          if (created != null) {
            ref.invalidate(
              documentsProvider(DocumentQuery(_projectId, _fileType)),
            );
          }
        },
        child: const Icon(Icons.add),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                TextField(
                  decoration: const InputDecoration(
                    hintText: 'Search documents...',
                    prefixIcon: Icon(Icons.search),
                  ),
                  onChanged: (value) => setState(() => _search = value.trim()),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  key: ValueKey(_fileType),
                  initialValue: _fileType.isEmpty ? null : _fileType,
                  decoration: const InputDecoration(labelText: 'File type'),
                  items: const [
                    DropdownMenuItem(value: '', child: Text('All types')),
                    DropdownMenuItem(value: 'drawing', child: Text('Drawing')),
                    DropdownMenuItem(
                      value: 'approval',
                      child: Text('Approval'),
                    ),
                    DropdownMenuItem(value: 'boq', child: Text('BOQ')),
                    DropdownMenuItem(value: 'photo', child: Text('Photo')),
                    DropdownMenuItem(value: 'other', child: Text('Other')),
                  ],
                  onChanged: (value) => setState(() => _fileType = value ?? ''),
                ),
                const SizedBox(height: 12),
                _SelectRow(
                  label: 'Project',
                  value: _projectLabel.isEmpty ? 'All projects' : _projectLabel,
                  onTap: () async {
                    final selected = await Navigator.of(context)
                        .push<SelectOption>(
                          MaterialPageRoute(
                            builder: (_) => const SelectListScreen(
                              title: 'Select Project',
                              endpoint: 'projects',
                            ),
                          ),
                        );
                    if (selected != null) {
                      setState(() {
                        _projectId = selected.id;
                        _projectLabel = selected.label;
                      });
                    }
                  },
                  onClear: _projectId == null
                      ? null
                      : () => setState(() {
                          _projectId = null;
                          _projectLabel = '';
                        }),
                ),
              ],
            ),
          ),
          Expanded(
            child: asyncDocs.when(
              data: (docs) {
                final filtered = _applySearch(docs);
                if (filtered.isEmpty) {
                  return const Center(child: Text('No documents found.'));
                }
                return RefreshIndicator(
                  onRefresh: () async => ref.invalidate(
                    documentsProvider(DocumentQuery(_projectId, _fileType)),
                  ),
                  child: ListView.separated(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    itemBuilder: (context, index) {
                      final doc = filtered[index];
                      return AppListTile(
                        title: Text(doc['file_name']?.toString() ?? 'Document'),
                        subtitle: Text(_subtitleFor(doc)),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () {
                          final id = doc['id'];
                          if (id is int) {
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) =>
                                    DocumentDetailScreen(documentId: id),
                              ),
                            );
                          }
                        },
                      );
                    },
                    separatorBuilder: (context, index) =>
                        const SizedBox(height: 12),
                    itemCount: filtered.length,
                  ),
                );
              },
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) =>
                  Center(child: Text('Failed to load documents: $error')),
            ),
          ),
        ],
      ),
    );
  }

  List<Map<String, dynamic>> _applySearch(List<Map<String, dynamic>> docs) {
    if (_search.isEmpty) {
      return docs;
    }
    final term = _search.toLowerCase();
    return docs.where((doc) {
      final name = doc['file_name']?.toString().toLowerCase() ?? '';
      final notes = doc['notes']?.toString().toLowerCase() ?? '';
      final project = doc['project_detail'] as Map<String, dynamic>?;
      final projectName = project?['name']?.toString().toLowerCase() ?? '';
      return name.contains(term) ||
          notes.contains(term) ||
          projectName.contains(term);
    }).toList();
  }

  String _subtitleFor(Map<String, dynamic> doc) {
    final project = doc['project_detail'] as Map<String, dynamic>?;
    final projectName = project?['name']?.toString() ?? 'Project';
    final fileType = doc['file_type']?.toString() ?? '';
    final version = doc['version']?.toString() ?? '';
    final parts = [
      projectName,
      fileType,
      version,
    ].where((value) => value.trim().isNotEmpty).toList();
    return parts.isEmpty ? 'Document' : parts.join(' • ');
  }
}

class _SelectRow extends StatelessWidget {
  const _SelectRow({
    required this.label,
    required this.value,
    required this.onTap,
    this.onClear,
  });

  final String label;
  final String value;
  final VoidCallback onTap;
  final VoidCallback? onClear;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          suffixIcon: onClear == null
              ? null
              : IconButton(icon: const Icon(Icons.clear), onPressed: onClear),
        ),
        child: Row(
          children: [
            Expanded(child: Text(value)),
            const Icon(Icons.expand_more),
          ],
        ),
      ),
    );
  }
}
