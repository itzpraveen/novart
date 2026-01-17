import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../common/app_list_tile.dart';
import 'project_detail_screen.dart';
import 'project_form_screen.dart';

class ProjectQuery {
  ProjectQuery(this.search, this.stage);

  final String search;
  final String stage;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ProjectQuery && search == other.search && stage == other.stage;

  @override
  int get hashCode => Object.hash(search, stage);
}

final projectsProvider =
    FutureProvider.family<List<Map<String, dynamic>>, ProjectQuery>((
      ref,
      query,
    ) async {
      final repo = ref.watch(apiRepositoryProvider);
      final params = <String, dynamic>{};
      if (query.search.isNotEmpty) {
        params['search'] = query.search;
      }
      if (query.stage.isNotEmpty) {
        params['current_stage'] = query.stage;
      }
      return repo.fetchList('projects', params: params.isEmpty ? null : params);
    });

class ProjectsListScreen extends ConsumerStatefulWidget {
  const ProjectsListScreen({super.key});

  @override
  ConsumerState<ProjectsListScreen> createState() => _ProjectsListScreenState();
}

class _ProjectsListScreenState extends ConsumerState<ProjectsListScreen> {
  String _search = '';
  String _stage = '';

  @override
  Widget build(BuildContext context) {
    final asyncProjects = ref.watch(
      projectsProvider(ProjectQuery(_search, _stage)),
    );
    final role = ref.watch(authControllerProvider).session?.user.role ?? '';
    final canCreate = role == 'admin' || role == 'architect';

    return Scaffold(
      appBar: AppBar(title: const Text('Projects')),
      floatingActionButton: canCreate
          ? FloatingActionButton(
              onPressed: () async {
                final created = await Navigator.of(context)
                    .push<Map<String, dynamic>>(
                      MaterialPageRoute(
                        builder: (_) => const ProjectFormScreen(),
                      ),
                    );
                if (created != null) {
                  ref.invalidate(
                    projectsProvider(ProjectQuery(_search, _stage)),
                  );
                }
              },
              child: const Icon(Icons.add),
            )
          : null,
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                TextField(
                  decoration: const InputDecoration(
                    hintText: 'Search projects...',
                    prefixIcon: Icon(Icons.search),
                  ),
                  onChanged: (value) => setState(() => _search = value.trim()),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: _stage.isEmpty ? null : _stage,
                  decoration: const InputDecoration(labelText: 'Stage'),
                  items: const [
                    DropdownMenuItem(value: '', child: Text('All stages')),
                    DropdownMenuItem(value: 'Enquiry', child: Text('Enquiry')),
                    DropdownMenuItem(value: 'Concept', child: Text('Concept')),
                    DropdownMenuItem(
                      value: 'Design Development',
                      child: Text('Design Development'),
                    ),
                    DropdownMenuItem(
                      value: 'Approvals',
                      child: Text('Approvals'),
                    ),
                    DropdownMenuItem(
                      value: 'Working Drawings',
                      child: Text('Working Drawings'),
                    ),
                    DropdownMenuItem(
                      value: 'Site Execution',
                      child: Text('Site Execution'),
                    ),
                    DropdownMenuItem(
                      value: 'Handover',
                      child: Text('Handover'),
                    ),
                    DropdownMenuItem(value: 'Closed', child: Text('Closed')),
                  ],
                  onChanged: (value) => setState(() => _stage = value ?? ''),
                ),
              ],
            ),
          ),
          Expanded(
            child: asyncProjects.when(
              data: (projects) {
                if (projects.isEmpty) {
                  return const Center(child: Text('No projects found.'));
                }
                return RefreshIndicator(
                  onRefresh: () async => ref.invalidate(
                    projectsProvider(ProjectQuery(_search, _stage)),
                  ),
                  child: ListView.separated(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    itemBuilder: (context, index) {
                      final project = projects[index];
                      return AppListTile(
                        title: Text(
                          '${project['code'] ?? ''} ${project['name'] ?? ''}'
                              .trim(),
                        ),
                        subtitle: Text(
                          '${project['client_detail']?['name'] ?? 'Client'} • ${project['current_stage'] ?? ''}',
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () {
                          final id = project['id'];
                          if (id is int) {
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) =>
                                    ProjectDetailScreen(projectId: id),
                              ),
                            );
                          }
                        },
                      );
                    },
                    separatorBuilder: (context, index) =>
                        const SizedBox(height: 12),
                    itemCount: projects.length,
                  ),
                );
              },
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) =>
                  Center(child: Text('Failed to load projects: $error')),
            ),
          ),
        ],
      ),
    );
  }
}
