import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/di/providers.dart';
import '../common/date_field.dart';
import '../common/select_list_screen.dart';
import '../modules/detail_screen.dart';
import 'expense_claim_form_screen.dart';
import 'expense_claims_list_screen.dart';

final expenseClaimAttachmentsProvider =
    FutureProvider.family<List<Map<String, dynamic>>, int>((
      ref,
      claimId,
    ) async {
      final repo = ref.watch(apiRepositoryProvider);
      return repo.fetchList(
        'expense-claim-attachments',
        params: {'claim': claimId},
      );
    });

class ExpenseClaimDetailScreen extends ConsumerWidget {
  const ExpenseClaimDetailScreen({super.key, required this.claimId});

  final int claimId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detail = ref.watch(
      detailProvider(DetailRequest('expense-claims', claimId)),
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Expense Claim'),
        actions: [
          detail.maybeWhen(
            data: (data) {
              final status = data['status']?.toString() ?? '';
              final session = ref.watch(authControllerProvider).session;
              final userId = session?.user.id;
              final isOwner = userId != null && data['employee'] == userId;
              final canEdit = isOwner && status != 'paid';
              if (!canEdit) {
                return const SizedBox.shrink();
              }
              return IconButton(
                icon: const Icon(Icons.edit_outlined),
                onPressed: () async {
                  final updated = await Navigator.of(context)
                      .push<Map<String, dynamic>>(
                        MaterialPageRoute(
                          builder: (_) => ExpenseClaimFormScreen(claim: data),
                        ),
                      );
                  if (updated != null) {
                    ref.invalidate(
                      detailProvider(DetailRequest('expense-claims', claimId)),
                    );
                    ref.invalidate(expenseClaimsProvider);
                  }
                },
              );
            },
            orElse: () => const SizedBox.shrink(),
          ),
        ],
      ),
      body: detail.when(
        data: (data) => _ExpenseClaimDetailBody(claim: data, claimId: claimId),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) =>
            Center(child: Text('Failed to load claim: $error')),
      ),
    );
  }
}

class _ExpenseClaimDetailBody extends ConsumerStatefulWidget {
  const _ExpenseClaimDetailBody({required this.claim, required this.claimId});

  final Map<String, dynamic> claim;
  final int claimId;

  @override
  ConsumerState<_ExpenseClaimDetailBody> createState() =>
      _ExpenseClaimDetailBodyState();
}

class _ExpenseClaimDetailBodyState
    extends ConsumerState<_ExpenseClaimDetailBody> {
  bool _uploading = false;

  @override
  Widget build(BuildContext context) {
    final attachments = ref.watch(
      expenseClaimAttachmentsProvider(widget.claimId),
    );
    final role = ref.watch(authControllerProvider).session?.user.role ?? '';
    final canApprove =
        role == 'admin' || role == 'finance' || role == 'accountant';
    final status = widget.claim['status']?.toString() ?? '';

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _DetailTile(
          label: 'Employee',
          value: widget.claim['employee_detail']?['full_name'],
        ),
        _DetailTile(
          label: 'Project',
          value: widget.claim['project_detail']?['name'],
        ),
        _DetailTile(label: 'Date', value: widget.claim['expense_date']),
        _DetailTile(label: 'Amount', value: widget.claim['amount']),
        _DetailTile(label: 'Category', value: widget.claim['category']),
        _DetailTile(label: 'Description', value: widget.claim['description']),
        _DetailTile(label: 'Status', value: status),
        _DetailTile(
          label: 'Approved By',
          value: widget.claim['approved_by_detail']?['full_name'],
        ),
        _DetailTile(label: 'Approved At', value: widget.claim['approved_at']),
        if (canApprove) ...[
          const SizedBox(height: 8),
          _ActionRow(
            status: status,
            onApprove: () => _handleApprove(context),
            onReject: () => _handleReject(context),
            onPay: () => _handlePay(context),
          ),
        ],
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
        endpoint: 'expense-claim-attachments',
        fields: {'claim': widget.claimId},
        file: File(result.files.single.path!),
      );
      ref.invalidate(expenseClaimAttachmentsProvider(widget.claimId));
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

  Future<void> _handleApprove(BuildContext context) async {
    if (!await _confirm(context, 'Approve this claim?')) {
      return;
    }
    try {
      final repo = ref.read(apiRepositoryProvider);
      await repo.post('expense-claims/${widget.claimId}/approve/', {});
      ref.invalidate(
        detailProvider(DetailRequest('expense-claims', widget.claimId)),
      );
      ref.invalidate(expenseClaimsProvider);
    } catch (error) {
      if (!context.mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to approve claim: $error')),
      );
    }
  }

  Future<void> _handleReject(BuildContext context) async {
    if (!await _confirm(context, 'Reject this claim?')) {
      return;
    }
    try {
      final repo = ref.read(apiRepositoryProvider);
      await repo.post('expense-claims/${widget.claimId}/reject/', {});
      ref.invalidate(
        detailProvider(DetailRequest('expense-claims', widget.claimId)),
      );
      ref.invalidate(expenseClaimsProvider);
    } catch (error) {
      if (!context.mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Failed to reject claim: $error')));
    }
  }

  Future<void> _handlePay(BuildContext context) async {
    final result = await showModalBottomSheet<_PaymentData>(
      context: context,
      isScrollControlled: true,
      builder: (context) => _PaymentSheet(amount: widget.claim['amount']),
    );
    if (result == null) {
      return;
    }
    try {
      final repo = ref.read(apiRepositoryProvider);
      await repo.post('expense-claims/${widget.claimId}/pay/', {
        'payment_date': result.paymentDate,
        'amount': result.amount,
        'account': result.accountId,
        'method': result.method,
        'reference': result.reference,
        'notes': result.notes,
      });
      ref.invalidate(
        detailProvider(DetailRequest('expense-claims', widget.claimId)),
      );
      ref.invalidate(expenseClaimsProvider);
    } catch (error) {
      if (!context.mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Failed to pay claim: $error')));
    }
  }

  Future<bool> _confirm(BuildContext context, String message) async {
    final result = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Confirm'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Yes'),
          ),
        ],
      ),
    );
    return result ?? false;
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

class _ActionRow extends StatelessWidget {
  const _ActionRow({
    required this.status,
    required this.onApprove,
    required this.onReject,
    required this.onPay,
  });

  final String status;
  final VoidCallback onApprove;
  final VoidCallback onReject;
  final VoidCallback onPay;

  @override
  Widget build(BuildContext context) {
    final canApprove = status == 'submitted';
    final canPay = status == 'approved';
    return Wrap(
      spacing: 12,
      children: [
        if (canApprove)
          OutlinedButton.icon(
            onPressed: onReject,
            icon: const Icon(Icons.close),
            label: const Text('Reject'),
          ),
        if (canApprove)
          ElevatedButton.icon(
            onPressed: onApprove,
            icon: const Icon(Icons.check),
            label: const Text('Approve'),
          ),
        if (canPay)
          ElevatedButton.icon(
            onPressed: onPay,
            icon: const Icon(Icons.payments_outlined),
            label: const Text('Pay'),
          ),
      ],
    );
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

class _PaymentSheet extends StatefulWidget {
  const _PaymentSheet({this.amount});

  final dynamic amount;

  @override
  State<_PaymentSheet> createState() => _PaymentSheetState();
}

class _PaymentSheetState extends State<_PaymentSheet> {
  final _formKey = GlobalKey<FormState>();
  final _dateController = TextEditingController();
  final _amountController = TextEditingController();
  final _methodController = TextEditingController();
  final _referenceController = TextEditingController();
  final _notesController = TextEditingController();

  int? _accountId;
  String _accountLabel = '';

  @override
  void initState() {
    super.initState();
    _amountController.text = widget.amount?.toString() ?? '';
  }

  @override
  void dispose() {
    _dateController.dispose();
    _amountController.dispose();
    _methodController.dispose();
    _referenceController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        top: 16,
        bottom: 16 + MediaQuery.of(context).viewInsets.bottom,
      ),
      child: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Record Payment',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 16),
            DateField(controller: _dateController, label: 'Payment Date *'),
            const SizedBox(height: 12),
            TextFormField(
              controller: _amountController,
              decoration: const InputDecoration(labelText: 'Amount *'),
              keyboardType: TextInputType.number,
              validator: (value) {
                if (value == null || value.trim().isEmpty) {
                  return 'Amount is required.';
                }
                return null;
              },
            ),
            const SizedBox(height: 12),
            _SelectRow(
              label: 'Account *',
              value: _accountLabel.isEmpty ? 'Select account' : _accountLabel,
              onTap: () async {
                final selected = await Navigator.of(context).push<SelectOption>(
                  MaterialPageRoute(
                    builder: (_) => const SelectListScreen(
                      title: 'Select Account',
                      endpoint: 'accounts',
                    ),
                  ),
                );
                if (selected != null) {
                  setState(() {
                    _accountId = selected.id;
                    _accountLabel = selected.label;
                  });
                }
              },
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _methodController,
              decoration: const InputDecoration(labelText: 'Method'),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _referenceController,
              decoration: const InputDecoration(labelText: 'Reference'),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _notesController,
              decoration: const InputDecoration(labelText: 'Notes'),
              maxLines: 2,
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('Cancel'),
                  ),
                ),
                Expanded(
                  child: ElevatedButton(
                    onPressed: () {
                      if (_accountId == null) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Select an account.')),
                        );
                        return;
                      }
                      if (_dateController.text.trim().isEmpty) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Payment date is required.'),
                          ),
                        );
                        return;
                      }
                      if (!_formKey.currentState!.validate()) {
                        return;
                      }
                      Navigator.of(context).pop(
                        _PaymentData(
                          paymentDate: _dateController.text.trim(),
                          amount:
                              double.tryParse(_amountController.text.trim()) ??
                              0,
                          accountId: _accountId!,
                          method: _methodController.text.trim(),
                          reference: _referenceController.text.trim(),
                          notes: _notesController.text.trim(),
                        ),
                      );
                    },
                    child: const Text('Save'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _PaymentData {
  _PaymentData({
    required this.paymentDate,
    required this.amount,
    required this.accountId,
    required this.method,
    required this.reference,
    required this.notes,
  });

  final String paymentDate;
  final double amount;
  final int accountId;
  final String method;
  final String reference;
  final String notes;
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
