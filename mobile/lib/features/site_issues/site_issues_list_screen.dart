import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../common/app_list_tile.dart';
import '../common/select_list_screen.dart';
import 'site_issue_detail_screen.dart';
import 'site_issue_form_screen.dart';

class SiteIssueQuery {
  SiteIssueQuery(this.projectId, this.status);

  final int? projectId;
  final String status;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is SiteIssueQuery &&
          projectId == other.projectId &&
          status == other.status;

  @override
  int get hashCode => Object.hash(projectId, status);
}

final siteIssuesProvider =
    FutureProvider.family<List<Map<String, dynamic>>, SiteIssueQuery>((
      ref,
      query,
    ) async {
      final repo = ref.watch(apiRepositoryProvider);
      final params = <String, dynamic>{};
      if (query.projectId != null) {
        params['project'] = query.projectId;
      }
      if (query.status.isNotEmpty) {
        params['status'] = query.status;
      }
      return repo.fetchList(
        'site-issues',
        params: params.isEmpty ? null : params,
      );
    });

class SiteIssuesListScreen extends ConsumerStatefulWidget {
  const SiteIssuesListScreen({super.key});

  @override
  ConsumerState<SiteIssuesListScreen> createState() =>
      _SiteIssuesListScreenState();
}

class _SiteIssuesListScreenState extends ConsumerState<SiteIssuesListScreen> {
  String _search = '';
  String _status = '';
  int? _projectId;
  String _projectLabel = '';

  @override
  Widget build(BuildContext context) {
    final asyncIssues = ref.watch(
      siteIssuesProvider(SiteIssueQuery(_projectId, _status)),
    );

    return Scaffold(
      appBar: AppBar(title: const Text('Site Issues')),
      floatingActionButton: FloatingActionButton(
        onPressed: () async {
          final created = await Navigator.of(context)
              .push<Map<String, dynamic>>(
                MaterialPageRoute(builder: (_) => const SiteIssueFormScreen()),
              );
          if (created != null) {
            ref.invalidate(
              siteIssuesProvider(SiteIssueQuery(_projectId, _status)),
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
                    hintText: 'Search issues...',
                    prefixIcon: Icon(Icons.search),
                  ),
                  onChanged: (value) => setState(() => _search = value.trim()),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  key: ValueKey(_status),
                  initialValue: _status.isEmpty ? null : _status,
                  decoration: const InputDecoration(labelText: 'Status'),
                  items: const [
                    DropdownMenuItem(value: '', child: Text('All statuses')),
                    DropdownMenuItem(value: 'open', child: Text('Open')),
                    DropdownMenuItem(
                      value: 'in_progress',
                      child: Text('In Progress'),
                    ),
                    DropdownMenuItem(
                      value: 'resolved',
                      child: Text('Resolved'),
                    ),
                  ],
                  onChanged: (value) => setState(() => _status = value ?? ''),
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
            child: asyncIssues.when(
              data: (issues) {
                final filtered = _applySearch(issues);
                if (filtered.isEmpty) {
                  return const Center(child: Text('No site issues found.'));
                }
                return RefreshIndicator(
                  onRefresh: () async => ref.invalidate(
                    siteIssuesProvider(SiteIssueQuery(_projectId, _status)),
                  ),
                  child: ListView.separated(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    itemBuilder: (context, index) {
                      final issue = filtered[index];
                      return AppListTile(
                        title: Text(issue['title']?.toString() ?? 'Issue'),
                        subtitle: Text(_subtitleFor(issue)),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () {
                          final id = issue['id'];
                          if (id is int) {
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) =>
                                    SiteIssueDetailScreen(issueId: id),
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
                  Center(child: Text('Failed to load site issues: $error')),
            ),
          ),
        ],
      ),
    );
  }

  List<Map<String, dynamic>> _applySearch(List<Map<String, dynamic>> issues) {
    if (_search.isEmpty) {
      return issues;
    }
    final term = _search.toLowerCase();
    return issues.where((issue) {
      final title = issue['title']?.toString().toLowerCase() ?? '';
      final description = issue['description']?.toString().toLowerCase() ?? '';
      final project = issue['project_detail'] as Map<String, dynamic>?;
      final projectName = project?['name']?.toString().toLowerCase() ?? '';
      return title.contains(term) ||
          description.contains(term) ||
          projectName.contains(term);
    }).toList();
  }

  String _subtitleFor(Map<String, dynamic> issue) {
    final project = issue['project_detail'] as Map<String, dynamic>?;
    final projectName = project?['name']?.toString() ?? 'Project';
    final status = issue['status']?.toString() ?? '';
    final raisedOn = issue['raised_on']?.toString() ?? '';
    final parts = [
      projectName,
      status,
      raisedOn,
    ].where((value) => value.trim().isNotEmpty).toList();
    return parts.isEmpty ? 'Issue' : parts.join(' • ');
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
