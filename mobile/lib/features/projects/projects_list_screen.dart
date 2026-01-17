import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../../core/theme/app_theme.dart';
import '../common/app_list_tile.dart';
import '../common/shimmer_loading.dart';
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
      if (query.stage.isNotEmpty && query.stage != 'active') {
        params['current_stage'] = query.stage;
      }
      return repo.fetchList('projects', params: params.isEmpty ? null : params);
    });

class ProjectsListScreen extends ConsumerStatefulWidget {
  const ProjectsListScreen({super.key, this.initialStage = ''});

  final String initialStage;

  @override
  ConsumerState<ProjectsListScreen> createState() => _ProjectsListScreenState();
}

class _ProjectsListScreenState extends ConsumerState<ProjectsListScreen> {
  String _search = '';
  String _stage = '';
  final _searchController = TextEditingController();
  bool _showFilters = false;

  @override
  void initState() {
    super.initState();
    _stage = widget.initialStage;
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final asyncProjects = ref.watch(
      projectsProvider(ProjectQuery(_search, _stage)),
    );
    final role = ref.watch(authControllerProvider).session?.user.role ?? '';
    final canCreate = role == 'admin' || role == 'architect';

    return Scaffold(
      appBar: AppBar(
        title: const Text('Projects'),
        actions: [
          IconButton(
            icon: Icon(
              _showFilters ? Icons.filter_alt_off : Icons.filter_alt_outlined,
            ),
            onPressed: () {
              HapticFeedback.lightImpact();
              setState(() => _showFilters = !_showFilters);
            },
          ),
        ],
      ),
      floatingActionButton: canCreate
          ? FloatingActionButton.extended(
              onPressed: () async {
                HapticFeedback.lightImpact();
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
              icon: const Icon(Icons.add),
              label: const Text('New Project'),
            )
          : null,
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
            child: TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: 'Search projects...',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.close),
                        onPressed: () {
                          _searchController.clear();
                          setState(() => _search = '');
                        },
                      )
                    : null,
              ),
              onChanged: (value) => setState(() => _search = value.trim()),
            ),
          ),
          AnimatedSize(
            duration: const Duration(milliseconds: 200),
            curve: Curves.easeInOut,
            child: _showFilters
                ? Padding(
                    padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                    child: _StageFilter(
                      selected: _stage,
                      onChanged: (value) => setState(() => _stage = value),
                    ),
                  )
                : const SizedBox.shrink(),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: asyncProjects.when(
              data: (projects) {
                final visibleProjects = _stage == 'active'
                    ? projects
                          .where(
                            (project) =>
                                (project['current_stage']?.toString() ?? '') !=
                                'Closed',
                          )
                          .toList()
                    : projects;

                if (visibleProjects.isEmpty) {
                  return EmptyStateWidget(
                    icon: Icons.apartment_outlined,
                    title: 'No projects found',
                    subtitle: _search.isNotEmpty
                        ? 'Try a different search term'
                        : 'Projects will appear here',
                  );
                }

                return RefreshIndicator(
                  onRefresh: () async {
                    HapticFeedback.mediumImpact();
                    ref.invalidate(
                      projectsProvider(ProjectQuery(_search, _stage)),
                    );
                  },
                  child: ListView.separated(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 100),
                    physics: const AlwaysScrollableScrollPhysics(),
                    itemBuilder: (context, index) {
                      final project = visibleProjects[index];
                      return TweenAnimationBuilder<double>(
                        tween: Tween(begin: 0, end: 1),
                        duration: Duration(milliseconds: 200 + (index * 50)),
                        curve: Curves.easeOutCubic,
                        builder: (context, value, child) {
                          return Transform.translate(
                            offset: Offset(0, 20 * (1 - value)),
                            child: Opacity(opacity: value, child: child),
                          );
                        },
                        child: _ProjectCard(
                          project: project,
                          onTap: () {
                            final id = project['id'];
                            if (id is int) {
                              HapticFeedback.lightImpact();
                              Navigator.of(context).push(
                                MaterialPageRoute(
                                  builder: (_) =>
                                      ProjectDetailScreen(projectId: id),
                                ),
                              );
                            }
                          },
                        ),
                      );
                    },
                    separatorBuilder: (context, index) =>
                        const SizedBox(height: 10),
                    itemCount: visibleProjects.length,
                  ),
                );
              },
              loading: () => const _ProjectsListSkeleton(),
              error: (error, _) => ErrorStateWidget(
                message: error.toString(),
                onRetry: () => ref.invalidate(
                  projectsProvider(ProjectQuery(_search, _stage)),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _StageFilter extends StatelessWidget {
  const _StageFilter({required this.selected, required this.onChanged});

  final String selected;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          _FilterChip(
            label: 'All',
            selected: selected.isEmpty,
            onSelected: () => onChanged(''),
          ),
          const SizedBox(width: 8),
          _FilterChip(
            label: 'Active',
            selected: selected == 'active',
            onSelected: () => onChanged('active'),
          ),
          const SizedBox(width: 8),
          _FilterChip(
            label: 'Enquiry',
            selected: selected == 'Enquiry',
            onSelected: () => onChanged('Enquiry'),
          ),
          const SizedBox(width: 8),
          _FilterChip(
            label: 'Concept',
            selected: selected == 'Concept',
            onSelected: () => onChanged('Concept'),
          ),
          const SizedBox(width: 8),
          _FilterChip(
            label: 'Design',
            selected: selected == 'Design Development',
            onSelected: () => onChanged('Design Development'),
          ),
          const SizedBox(width: 8),
          _FilterChip(
            label: 'Execution',
            selected: selected == 'Site Execution',
            onSelected: () => onChanged('Site Execution'),
          ),
          const SizedBox(width: 8),
          _FilterChip(
            label: 'Closed',
            selected: selected == 'Closed',
            onSelected: () => onChanged('Closed'),
          ),
        ],
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  const _FilterChip({
    required this.label,
    required this.selected,
    required this.onSelected,
  });

  final String label;
  final bool selected;
  final VoidCallback onSelected;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        onSelected();
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? AppTheme.primary : AppTheme.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: selected ? AppTheme.primary : AppTheme.outline.withAlpha(150),
          ),
        ),
        child: Text(
          label,
          style: Theme.of(context).textTheme.labelMedium?.copyWith(
            color: selected ? Colors.white : AppTheme.onSurface,
            fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
          ),
        ),
      ),
    );
  }
}

class _ProjectCard extends StatelessWidget {
  const _ProjectCard({required this.project, required this.onTap});

  final Map<String, dynamic> project;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final stage = project['current_stage']?.toString() ?? '';
    final stageColor = _getStageColor(stage);

    return AppListTile(
      leadingIcon: Icons.apartment_outlined,
      leadingColor: stageColor,
      title: Text(
        '${project['code'] ?? ''} ${project['name'] ?? ''}'.trim(),
      ),
      subtitle: Row(
        children: [
          Flexible(
            child: Text(
              project['client_detail']?['name']?.toString() ?? 'Client',
              overflow: TextOverflow.ellipsis,
            ),
          ),
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 6),
            width: 4,
            height: 4,
            decoration: BoxDecoration(
              color: AppTheme.onSurface.withAlpha(80),
              shape: BoxShape.circle,
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: stageColor.withAlpha(20),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              stage,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                color: stageColor,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
      trailing: Icon(
        Icons.chevron_right,
        color: AppTheme.onSurface.withAlpha(100),
      ),
      onTap: onTap,
    );
  }

  Color _getStageColor(String stage) {
    switch (stage.toLowerCase()) {
      case 'enquiry':
        return const Color(0xFF6B7280);
      case 'concept':
        return const Color(0xFF8B5CF6);
      case 'design development':
        return const Color(0xFF3B82F6);
      case 'approvals':
        return const Color(0xFFF59E0B);
      case 'working drawings':
        return const Color(0xFF10B981);
      case 'site execution':
        return const Color(0xFFEF4444);
      case 'handover':
        return const Color(0xFF06B6D4);
      case 'closed':
        return const Color(0xFF64748B);
      default:
        return AppTheme.primary;
    }
  }
}

class _ProjectsListSkeleton extends StatelessWidget {
  const _ProjectsListSkeleton();

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 100),
      physics: const NeverScrollableScrollPhysics(),
      itemCount: 8,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (_, __) => const SkeletonListTile(),
    );
  }
}
