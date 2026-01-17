import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../common/app_list_tile.dart';
import 'task_detail_screen.dart';
import 'task_form_screen.dart';

class TaskQuery {
  TaskQuery(this.search, this.status);

  final String search;
  final String status;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is TaskQuery && search == other.search && status == other.status;

  @override
  int get hashCode => Object.hash(search, status);
}

final tasksProvider =
    FutureProvider.family<List<Map<String, dynamic>>, TaskQuery>((
      ref,
      query,
    ) async {
      final repo = ref.watch(apiRepositoryProvider);
      final params = <String, dynamic>{};
      if (query.search.isNotEmpty) {
        params['search'] = query.search;
      }
      if (query.status.isNotEmpty && query.status != 'open') {
        params['status'] = query.status;
      }
      return repo.fetchList('tasks', params: params.isEmpty ? null : params);
    });

class TasksListScreen extends ConsumerStatefulWidget {
  const TasksListScreen({super.key, this.initialStatus = ''});

  final String initialStatus;

  @override
  ConsumerState<TasksListScreen> createState() => _TasksListScreenState();
}

class _TasksListScreenState extends ConsumerState<TasksListScreen> {
  String _search = '';
  String _status = '';

  @override
  void initState() {
    super.initState();
    _status = widget.initialStatus;
  }

  @override
  Widget build(BuildContext context) {
    final asyncTasks = ref.watch(tasksProvider(TaskQuery(_search, _status)));
    final role = ref.watch(authControllerProvider).session?.user.role ?? '';
    final canCreate = role == 'admin' || role == 'architect';

    return Scaffold(
      appBar: AppBar(title: const Text('Tasks')),
      floatingActionButton: canCreate
          ? FloatingActionButton(
              onPressed: () async {
                final created = await Navigator.of(context)
                    .push<Map<String, dynamic>>(
                      MaterialPageRoute(builder: (_) => const TaskFormScreen()),
                    );
                if (created != null) {
                  ref.invalidate(tasksProvider(TaskQuery(_search, _status)));
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
                    hintText: 'Search tasks...',
                    prefixIcon: Icon(Icons.search),
                  ),
                  onChanged: (value) => setState(() => _search = value.trim()),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: _status.isEmpty ? null : _status,
                  decoration: const InputDecoration(labelText: 'Status'),
                  items: const [
                    DropdownMenuItem(value: '', child: Text('All statuses')),
                    DropdownMenuItem(value: 'open', child: Text('Open')),
                    DropdownMenuItem(value: 'todo', child: Text('To Do')),
                    DropdownMenuItem(
                      value: 'in_progress',
                      child: Text('In Progress'),
                    ),
                    DropdownMenuItem(value: 'done', child: Text('Done')),
                  ],
                  onChanged: (value) => setState(() => _status = value ?? ''),
                ),
              ],
            ),
          ),
          Expanded(
            child: asyncTasks.when(
              data: (tasks) {
                final visibleTasks = _status == 'open'
                    ? tasks.where((task) {
                        final status = task['status']?.toString() ?? '';
                        return status == 'todo' || status == 'in_progress';
                      }).toList()
                    : tasks;
                if (visibleTasks.isEmpty) {
                  return const Center(child: Text('No tasks found.'));
                }
                return RefreshIndicator(
                  onRefresh: () async => ref.invalidate(
                    tasksProvider(TaskQuery(_search, _status)),
                  ),
                  child: ListView.separated(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    itemBuilder: (context, index) {
                      final task = visibleTasks[index];
                      return AppListTile(
                        title: Text(task['title']?.toString() ?? 'Task'),
                        subtitle: Text(
                          '${task['project_detail']?['name'] ?? 'Project'} • ${task['status'] ?? ''}',
                        ),
                        trailing: _StatusMenu(task: task),
                        onTap: () {
                          final id = task['id'];
                          if (id is int) {
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) => TaskDetailScreen(taskId: id),
                              ),
                            );
                          }
                        },
                      );
                    },
                    separatorBuilder: (context, index) =>
                        const SizedBox(height: 12),
                    itemCount: visibleTasks.length,
                  ),
                );
              },
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) =>
                  Center(child: Text('Failed to load tasks: $error')),
            ),
          ),
        ],
      ),
    );
  }
}

class _StatusMenu extends ConsumerWidget {
  const _StatusMenu({required this.task});

  final Map<String, dynamic> task;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return PopupMenuButton<String>(
      icon: const Icon(Icons.more_vert),
      onSelected: (status) async {
        final id = task['id'];
        if (id is! int) {
          return;
        }
        try {
          final repo = ref.read(apiRepositoryProvider);
          await repo.post('tasks/$id/quick_update/', {'status': status});
          if (!context.mounted) {
            return;
          }
          ref.invalidate(tasksProvider);
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Task moved to ${status.replaceAll('_', ' ')}.'),
            ),
          );
        } catch (error) {
          if (!context.mounted) {
            return;
          }
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Failed to update task: $error')),
          );
        }
      },
      itemBuilder: (context) => const [
        PopupMenuItem(value: 'todo', child: Text('Move to To Do')),
        PopupMenuItem(value: 'in_progress', child: Text('Move to In Progress')),
        PopupMenuItem(value: 'done', child: Text('Move to Done')),
      ],
    );
  }
}
