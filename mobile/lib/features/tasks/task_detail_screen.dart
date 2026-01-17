import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/di/providers.dart';
import '../modules/detail_screen.dart';
import 'task_form_screen.dart';

class TaskDetailScreen extends ConsumerWidget {
  const TaskDetailScreen({super.key, required this.taskId});

  final int taskId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detail = ref.watch(detailProvider(DetailRequest('tasks', taskId)));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Task Details'),
        actions: [
          detail.maybeWhen(
            data: (data) => IconButton(
              icon: const Icon(Icons.edit_outlined),
              onPressed: () async {
                final updated = await Navigator.of(context)
                    .push<Map<String, dynamic>>(
                      MaterialPageRoute(
                        builder: (_) => TaskFormScreen(task: data),
                      ),
                    );
                if (updated != null) {
                  ref.invalidate(
                    detailProvider(DetailRequest('tasks', taskId)),
                  );
                }
              },
            ),
            orElse: () => const SizedBox.shrink(),
          ),
        ],
      ),
      body: detail.when(
        data: (data) => _TaskDetailBody(task: data, taskId: taskId),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Failed to load task: $error')),
      ),
    );
  }
}

class TaskCommentQuery {
  TaskCommentQuery(this.taskId);

  final int taskId;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is TaskCommentQuery && taskId == other.taskId;

  @override
  int get hashCode => taskId.hashCode;
}

final taskCommentsProvider =
    FutureProvider.family<List<Map<String, dynamic>>, TaskCommentQuery>((
      ref,
      query,
    ) async {
      final repo = ref.watch(apiRepositoryProvider);
      return repo.fetchList('task-comments', params: {'task': query.taskId});
    });

class _TaskDetailBody extends ConsumerStatefulWidget {
  const _TaskDetailBody({required this.task, required this.taskId});

  final Map<String, dynamic> task;
  final int taskId;

  @override
  ConsumerState<_TaskDetailBody> createState() => _TaskDetailBodyState();
}

class _TaskDetailBodyState extends ConsumerState<_TaskDetailBody> {
  final _commentController = TextEditingController();
  final List<File> _attachments = [];
  bool _submitting = false;

  @override
  void dispose() {
    _commentController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final comments = ref.watch(
      taskCommentsProvider(TaskCommentQuery(widget.taskId)),
    );

    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _DetailTile(label: 'Title', value: widget.task['title']),
              _DetailTile(
                label: 'Project',
                value: widget.task['project_detail']?['name'],
              ),
              _DetailTile(label: 'Status', value: widget.task['status']),
              _DetailTile(label: 'Priority', value: widget.task['priority']),
              _DetailTile(label: 'Due Date', value: widget.task['due_date']),
              _DetailTile(
                label: 'Assignee',
                value: widget.task['assigned_to_detail']?['full_name'],
              ),
              _DetailTile(
                label: 'Description',
                value: widget.task['description'],
              ),
              const SizedBox(height: 12),
              Text('Comments', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              comments.when(
                data: (items) {
                  if (items.isEmpty) {
                    return const Text('No comments yet.');
                  }
                  return Column(
                    children: items
                        .map((comment) => _CommentCard(comment: comment))
                        .toList(),
                  );
                },
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (error, _) => Text('Failed to load comments: $error'),
              ),
              const SizedBox(height: 80),
            ],
          ),
        ),
        _buildComposer(context),
      ],
    );
  }

  Widget _buildComposer(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        boxShadow: const [
          BoxShadow(
            color: Colors.black12,
            blurRadius: 6,
            offset: Offset(0, -2),
          ),
        ],
      ),
      child: Column(
        children: [
          if (_attachments.isNotEmpty)
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _attachments
                  .map(
                    (file) => Chip(
                      label: Text(_filename(file.path)),
                      onDeleted: () =>
                          setState(() => _attachments.remove(file)),
                    ),
                  )
                  .toList(),
            ),
          Row(
            children: [
              IconButton(
                icon: const Icon(Icons.attach_file),
                onPressed: _submitting
                    ? null
                    : () async {
                        final result = await FilePicker.platform.pickFiles(
                          type: FileType.custom,
                          allowedExtensions: const [
                            'pdf',
                            'png',
                            'jpg',
                            'jpeg',
                          ],
                        );
                        if (result != null &&
                            result.files.single.path != null) {
                          setState(() {
                            _attachments.add(File(result.files.single.path!));
                          });
                        }
                      },
              ),
              Expanded(
                child: TextField(
                  controller: _commentController,
                  decoration: const InputDecoration(
                    hintText: 'Add a comment...',
                  ),
                  minLines: 1,
                  maxLines: 3,
                ),
              ),
              const SizedBox(width: 8),
              ElevatedButton(
                onPressed: _submitting ? null : () => _submitComment(context),
                child: _submitting
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Send'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _submitComment(BuildContext context) async {
    final body = _commentController.text.trim();
    if (body.isEmpty) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Enter a comment first.')));
      return;
    }
    setState(() => _submitting = true);
    try {
      final repo = ref.read(apiRepositoryProvider);
      final created = await repo.create('task-comments', {
        'task': widget.taskId,
        'body': body,
      });
      final commentId = created['id'] as int?;
      if (commentId != null) {
        for (final file in _attachments) {
          await repo.uploadFile(
            endpoint: 'task-comment-attachments',
            fields: {'comment': commentId},
            file: file,
          );
        }
      }
      if (!mounted) {
        return;
      }
      _commentController.clear();
      _attachments.clear();
      ref.invalidate(taskCommentsProvider(TaskCommentQuery(widget.taskId)));
    } catch (error) {
      if (!context.mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Failed to post comment: $error')));
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  String _filename(String path) {
    return path.split(Platform.pathSeparator).last;
  }
}

class _CommentCard extends StatelessWidget {
  const _CommentCard({required this.comment});

  final Map<String, dynamic> comment;

  @override
  Widget build(BuildContext context) {
    final author = comment['author_detail']?['full_name'] ?? 'User';
    final attachments =
        (comment['attachments'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              author.toString(),
              style: Theme.of(
                context,
              ).textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 6),
            Text(comment['body']?.toString() ?? ''),
            if (attachments.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: attachments
                    .map(
                      (attachment) => ActionChip(
                        label: Text(
                          _attachmentLabel(
                            attachment['file']?.toString() ?? 'File',
                          ),
                        ),
                        onPressed: () => _openAttachment(
                          attachment['file']?.toString() ?? '',
                        ),
                      ),
                    )
                    .toList(),
              ),
            ],
          ],
        ),
      ),
    );
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
