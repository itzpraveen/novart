import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../common/select_list_screen.dart';
import 'site_visit_detail_screen.dart';
import 'site_visit_form_screen.dart';

class SiteVisitQuery {
  SiteVisitQuery(this.projectId);

  final int? projectId;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is SiteVisitQuery && projectId == other.projectId;

  @override
  int get hashCode => projectId.hashCode;
}

final siteVisitsProvider =
    FutureProvider.family<List<Map<String, dynamic>>, SiteVisitQuery>((
      ref,
      query,
    ) async {
      final repo = ref.watch(apiRepositoryProvider);
      final params = <String, dynamic>{};
      if (query.projectId != null) {
        params['project'] = query.projectId;
      }
      return repo.fetchList(
        'site-visits',
        params: params.isEmpty ? null : params,
      );
    });

class SiteVisitsListScreen extends ConsumerStatefulWidget {
  const SiteVisitsListScreen({super.key});

  @override
  ConsumerState<SiteVisitsListScreen> createState() =>
      _SiteVisitsListScreenState();
}

class _SiteVisitsListScreenState extends ConsumerState<SiteVisitsListScreen> {
  String _search = '';
  int? _projectId;
  String _projectLabel = '';

  @override
  Widget build(BuildContext context) {
    final asyncVisits = ref.watch(
      siteVisitsProvider(SiteVisitQuery(_projectId)),
    );

    return Scaffold(
      appBar: AppBar(title: const Text('Site Visits')),
      floatingActionButton: FloatingActionButton(
        onPressed: () async {
          final created = await Navigator.of(context)
              .push<Map<String, dynamic>>(
                MaterialPageRoute(builder: (_) => const SiteVisitFormScreen()),
              );
          if (created != null) {
            ref.invalidate(siteVisitsProvider(SiteVisitQuery(_projectId)));
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
                    hintText: 'Search visits...',
                    prefixIcon: Icon(Icons.search),
                  ),
                  onChanged: (value) => setState(() => _search = value.trim()),
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
            child: asyncVisits.when(
              data: (visits) {
                final filtered = _applySearch(visits);
                if (filtered.isEmpty) {
                  return const Center(child: Text('No site visits found.'));
                }
                return RefreshIndicator(
                  onRefresh: () async => ref.invalidate(
                    siteVisitsProvider(SiteVisitQuery(_projectId)),
                  ),
                  child: ListView.separated(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    itemBuilder: (context, index) {
                      final visit = filtered[index];
                      return ListTile(
                        tileColor: Theme.of(context).colorScheme.surface,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        title: Text(_titleFor(visit)),
                        subtitle: Text(_subtitleFor(visit)),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () {
                          final id = visit['id'];
                          if (id is int) {
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) =>
                                    SiteVisitDetailScreen(visitId: id),
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
                  Center(child: Text('Failed to load site visits: $error')),
            ),
          ),
        ],
      ),
    );
  }

  List<Map<String, dynamic>> _applySearch(List<Map<String, dynamic>> visits) {
    if (_search.isEmpty) {
      return visits;
    }
    final term = _search.toLowerCase();
    return visits.where((visit) {
      final project = visit['project_detail'] as Map<String, dynamic>?;
      final name = project?['name']?.toString().toLowerCase() ?? '';
      final code = project?['code']?.toString().toLowerCase() ?? '';
      final location = visit['location']?.toString().toLowerCase() ?? '';
      final notes = visit['notes']?.toString().toLowerCase() ?? '';
      return name.contains(term) ||
          code.contains(term) ||
          location.contains(term) ||
          notes.contains(term);
    }).toList();
  }

  String _titleFor(Map<String, dynamic> visit) {
    final project = visit['project_detail'] as Map<String, dynamic>?;
    final name = project?['name']?.toString() ?? 'Project';
    final code = project?['code']?.toString() ?? '';
    if (code.isEmpty) {
      return name;
    }
    return '$code • $name';
  }

  String _subtitleFor(Map<String, dynamic> visit) {
    final date = visit['visit_date']?.toString() ?? '';
    final visitor = visit['visited_by_detail']?['full_name']?.toString() ?? '';
    final location = visit['location']?.toString() ?? '';
    final parts = [
      date,
      visitor,
      location,
    ].where((value) => value.trim().isNotEmpty).toList();
    return parts.isEmpty ? 'Site visit' : parts.join(' • ');
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
