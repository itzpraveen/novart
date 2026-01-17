import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

class DateField extends StatelessWidget {
  const DateField({
    super.key,
    required this.controller,
    required this.label,
    this.firstDate,
    this.lastDate,
  });

  final TextEditingController controller;
  final String label;
  final DateTime? firstDate;
  final DateTime? lastDate;

  @override
  Widget build(BuildContext context) {
    return TextFormField(
      controller: controller,
      readOnly: true,
      decoration: InputDecoration(
        labelText: label,
        suffixIcon: const Icon(Icons.calendar_today_outlined),
      ),
      onTap: () async {
        final now = DateTime.now();
        final initialDate = _parseDate(controller.text) ?? now;
        final picked = await showDatePicker(
          context: context,
          initialDate: initialDate,
          firstDate: firstDate ?? DateTime(now.year - 10),
          lastDate: lastDate ?? DateTime(now.year + 10),
        );
        if (picked != null) {
          controller.text = DateFormat('yyyy-MM-dd').format(picked);
        }
      },
    );
  }

  DateTime? _parseDate(String value) {
    try {
      return DateTime.parse(value);
    } catch (_) {
      return null;
    }
  }
}
