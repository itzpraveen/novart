import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../common/form_section.dart';
import '../common/select_list_screen.dart';

class DocumentFormScreen extends ConsumerStatefulWidget {
  const DocumentFormScreen({super.key, this.document});

  final Map<String, dynamic>? document;

  @override
  ConsumerState<DocumentFormScreen> createState() => _DocumentFormScreenState();
}

class _DocumentFormScreenState extends ConsumerState<DocumentFormScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _fileNameController;
  late final TextEditingController _versionController;
  late final TextEditingController _notesController;

  int? _projectId;
  String _projectLabel = '';
  String _fileType = 'other';
  File? _selectedFile;
  bool _saving = false;

  static const fileTypes = ['drawing', 'approval', 'boq', 'photo', 'other'];

  @override
  void initState() {
    super.initState();
    final document = widget.document ?? {};
    _fileNameController = TextEditingController(
      text: document['file_name']?.toString() ?? '',
    );
    _versionController = TextEditingController(
      text: document['version']?.toString() ?? '',
    );
    _notesController = TextEditingController(
      text: document['notes']?.toString() ?? '',
    );
    _projectId = document['project'] as int?;
    _projectLabel = document['project_detail']?['name']?.toString() ?? '';
    _fileType = document['file_type']?.toString() ?? 'other';
  }

  @override
  void dispose() {
    _fileNameController.dispose();
    _versionController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isEdit = widget.document != null;

    return Scaffold(
      appBar: AppBar(title: Text(isEdit ? 'Edit Document' : 'New Document')),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              FormSection(
                title: 'Document Details',
                children: [
                  _SelectRow(
                    label: 'Project *',
                    value: _projectLabel.isEmpty
                        ? 'Select project'
                        : _projectLabel,
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
                  ),
                  const SizedBox(height: 12),
                  _FilePickerRow(
                    label: 'File *',
                    fileName: _selectedFile?.path,
                    placeholder: isEdit
                        ? (widget.document?['file']?.toString() ??
                              'Select file')
                        : 'Select file',
                    onTap: _pickFile,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _fileNameController,
                    decoration: const InputDecoration(labelText: 'File name *'),
                    validator: (value) {
                      if (value == null || value.trim().isEmpty) {
                        return 'File name is required.';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: _fileType,
                    decoration: const InputDecoration(labelText: 'File type'),
                    items: fileTypes
                        .map(
                          (type) => DropdownMenuItem(
                            value: type,
                            child: Text(type.toUpperCase()),
                          ),
                        )
                        .toList(),
                    onChanged: (value) {
                      if (value != null) {
                        setState(() => _fileType = value);
                      }
                    },
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _versionController,
                    decoration: const InputDecoration(labelText: 'Version'),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _notesController,
                    decoration: const InputDecoration(labelText: 'Notes'),
                    maxLines: 3,
                  ),
                ],
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _saving
                    ? null
                    : () async {
                        if (_projectId == null) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Select a project.')),
                          );
                          return;
                        }
                        if (!isEdit && _selectedFile == null) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Select a file to upload.'),
                            ),
                          );
                          return;
                        }
                        if (!_formKey.currentState!.validate()) {
                          return;
                        }
                        setState(() => _saving = true);
                        try {
                          final payload = {
                            'project': _projectId,
                            'file_name': _fileNameController.text.trim(),
                            'file_type': _fileType,
                            'version': _versionController.text.trim(),
                            'notes': _notesController.text.trim(),
                          };
                          final repo = ref.read(apiRepositoryProvider);
                          Map<String, dynamic> saved;
                          if (isEdit) {
                            saved = await repo.updateWithFile(
                              endpoint: 'documents',
                              id: widget.document!['id'] as int,
                              fields: payload,
                              file: _selectedFile,
                            );
                          } else {
                            saved = await repo.uploadFile(
                              endpoint: 'documents',
                              fields: payload,
                              file: _selectedFile!,
                            );
                          }
                          if (!context.mounted) {
                            return;
                          }
                          Navigator.of(context).pop(saved);
                        } catch (error) {
                          if (!context.mounted) {
                            return;
                          }
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text('Failed to save document: $error'),
                            ),
                          );
                        } finally {
                          if (mounted) {
                            setState(() => _saving = false);
                          }
                        }
                      },
                child: Text(_saving ? 'Saving...' : 'Save Document'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['pdf', 'png', 'jpg', 'jpeg'],
    );
    if (result == null || result.files.single.path == null) {
      return;
    }
    final file = File(result.files.single.path!);
    setState(() {
      _selectedFile = file;
      if (_fileNameController.text.trim().isEmpty) {
        _fileNameController.text = file.path.split(Platform.pathSeparator).last;
      }
    });
  }
}

class _SelectRow extends StatelessWidget {
  const _SelectRow({
    required this.label,
    required this.value,
    required this.onTap,
  });

  final String label;
  final String value;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: InputDecorator(
        decoration: InputDecoration(labelText: label),
        child: Row(
          children: [
            Expanded(child: Text(value)),
            const Icon(Icons.chevron_right),
          ],
        ),
      ),
    );
  }
}

class _FilePickerRow extends StatelessWidget {
  const _FilePickerRow({
    required this.label,
    required this.fileName,
    required this.placeholder,
    required this.onTap,
  });

  final String label;
  final String? fileName;
  final String placeholder;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final display = fileName ?? placeholder;
    return InkWell(
      onTap: onTap,
      child: InputDecorator(
        decoration: InputDecoration(labelText: label),
        child: Row(
          children: [
            Expanded(child: Text(display)),
            const Icon(Icons.attach_file),
          ],
        ),
      ),
    );
  }
}
