import 'package:flutter/material.dart';

class AppListTile extends StatelessWidget {
  const AppListTile({
    super.key,
    required this.title,
    this.subtitle,
    this.leading,
    this.leadingIcon,
    this.leadingColor,
    this.trailing,
    this.onTap,
  });

  final Widget title;
  final Widget? subtitle;
  final Widget? leading;
  final IconData? leadingIcon;
  final Color? leadingColor;
  final Widget? trailing;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    Widget? resolvedLeading = leading;
    if (resolvedLeading == null && leadingIcon != null) {
      final iconColor = Theme.of(context).colorScheme.onPrimary;
      final background = leadingColor ?? Theme.of(context).colorScheme.primary;
      resolvedLeading = CircleAvatar(
        radius: 18,
        backgroundColor: background,
        child: Icon(leadingIcon, size: 18, color: iconColor),
      );
    }

    return Card(
      child: ListTile(
        leading: resolvedLeading,
        title: title,
        subtitle: subtitle,
        trailing: trailing,
        onTap: onTap,
      ),
    );
  }
}
