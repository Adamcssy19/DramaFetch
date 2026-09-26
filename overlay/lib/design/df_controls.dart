import 'package:flutter/material.dart';

import 'df_surface.dart';
import 'df_tokens.dart';

/// 玻璃搜索框。
///
/// 自绘外观，不依赖 [InputDecorationTheme] —— 全局主题里的输入框样式是给设置页的
/// 表单用的，搜索框需要更大的圆角与强调色聚焦态，混用会互相牵制。
class DfSearchField extends StatefulWidget {
  const DfSearchField({
    super.key,
    required this.controller,
    this.focusNode,
    this.hintText = '搜索想看的剧',
    this.onChanged,
    this.onSubmitted,
    this.onClear,
    this.height = 46,
    this.autofocus = false,
    this.leading,
  });

  final TextEditingController controller;
  final FocusNode? focusNode;
  final String hintText;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onSubmitted;
  final VoidCallback? onClear;
  final double height;
  final bool autofocus;
  final Widget? leading;

  @override
  State<DfSearchField> createState() => _DfSearchFieldState();
}

class _DfSearchFieldState extends State<DfSearchField> {
  bool _focused = false;
  bool _hasText = false;

  @override
  void initState() {
    super.initState();
    _hasText = widget.controller.text.isNotEmpty;
    widget.controller.addListener(_syncText);
    widget.focusNode?.addListener(_syncFocus);
  }

  @override
  void dispose() {
    widget.controller.removeListener(_syncText);
    widget.focusNode?.removeListener(_syncFocus);
    super.dispose();
  }

  void _syncText() {
    final hasText = widget.controller.text.isNotEmpty;
    if (hasText != _hasText && mounted) setState(() => _hasText = hasText);
  }

  void _syncFocus() {
    final focused = widget.focusNode?.hasFocus ?? false;
    if (focused != _focused && mounted) setState(() => _focused = focused);
  }

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    final radius = BorderRadius.circular(DfTokens.radiusPill);

    return AnimatedContainer(
      duration: const Duration(milliseconds: 140),
      curve: Curves.easeOut,
      height: widget.height,
      decoration: BoxDecoration(
        color: _focused ? palette.cardFillHover : palette.controlFill,
        borderRadius: radius,
        border: Border.all(
          color: _focused
              ? palette.accent.withValues(alpha: 0.7)
              : palette.controlStroke,
        ),
        boxShadow: _focused ? DfTokens.shadowSoft : null,
      ),
      child: Row(
        children: [
          Padding(
            padding: const EdgeInsets.only(left: 16, right: 10),
            child: Icon(
              Icons.search_rounded,
              size: 19,
              color: _focused ? palette.accent : palette.textTertiary,
            ),
          ),
          Expanded(
            child: TextField(
              controller: widget.controller,
              focusNode: widget.focusNode,
              autofocus: widget.autofocus,
              cursorColor: palette.accent,
              style: TextStyle(fontSize: 14, color: palette.textPrimary),
              decoration: InputDecoration(
                isDense: true,
                filled: false,
                border: InputBorder.none,
                enabledBorder: InputBorder.none,
                focusedBorder: InputBorder.none,
                contentPadding: const EdgeInsets.symmetric(vertical: 12),
                hintText: widget.hintText,
                hintStyle: TextStyle(fontSize: 14, color: palette.textTertiary),
              ),
              onChanged: (value) {
                widget.onChanged?.call(value);
              },
              onSubmitted: widget.onSubmitted,
            ),
          ),
          if (_hasText)
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: IconButton(
                tooltip: '清空',
                iconSize: 16,
                color: palette.textTertiary,
                icon: const Icon(Icons.close_rounded),
                onPressed: widget.onClear,
              ),
            )
          else if (widget.leading != null)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: widget.leading,
            ),
        ],
      ),
    );
  }
}

/// 主按钮：强调色渐变的胶囊。
class DfPrimaryButton extends StatefulWidget {
  const DfPrimaryButton({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.height = DfTokens.controlHeight,
    this.busy = false,
    this.expanded = false,
  });

  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final double height;
  final bool busy;
  final bool expanded;

  @override
  State<DfPrimaryButton> createState() => _DfPrimaryButtonState();
}

class _DfPrimaryButtonState extends State<DfPrimaryButton> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    final enabled = widget.onPressed != null && !widget.busy;

    final button = Opacity(
      opacity: enabled ? 1 : 0.5,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 130),
        height: widget.height,
        padding: const EdgeInsets.symmetric(horizontal: 18),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(DfTokens.radiusPill),
          gradient: DfTokens.accentGradient,
          boxShadow: _hovered && enabled
              ? [
                  BoxShadow(
                    color: palette.accent.withValues(alpha: 0.34),
                    blurRadius: 20,
                    offset: const Offset(0, 8),
                  ),
                ]
              : DfTokens.shadowSoft,
        ),
        child: Row(
          mainAxisSize: widget.expanded ? MainAxisSize.max : MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (widget.busy)
              const SizedBox(
                width: 15,
                height: 15,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor: AlwaysStoppedAnimation(Colors.white),
                ),
              )
            else if (widget.icon != null)
              Icon(widget.icon, size: 17, color: Colors.white),
            if (widget.busy || widget.icon != null) const SizedBox(width: 8),
            Text(
              widget.label,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: Colors.white,
              ),
            ),
          ],
        ),
      ),
    );

    return MouseRegion(
      cursor: enabled ? SystemMouseCursors.click : SystemMouseCursors.basic,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: enabled ? widget.onPressed : null,
        child: button,
      ),
    );
  }
}

/// 次要按钮：玻璃底、细描边。
class DfGlassButton extends StatefulWidget {
  const DfGlassButton({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.height = DfTokens.controlHeight,
    this.danger = false,
  });

  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final double height;
  final bool danger;

  @override
  State<DfGlassButton> createState() => _DfGlassButtonState();
}

class _DfGlassButtonState extends State<DfGlassButton> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    final enabled = widget.onPressed != null;
    final tone = widget.danger ? palette.danger : palette.textPrimary;

    return MouseRegion(
      cursor: enabled ? SystemMouseCursors.click : SystemMouseCursors.basic,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: enabled ? widget.onPressed : null,
        child: Opacity(
          opacity: enabled ? 1 : 0.45,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 130),
            height: widget.height,
            padding: const EdgeInsets.symmetric(horizontal: 14),
            decoration: BoxDecoration(
              color: _hovered ? palette.cardFillHover : palette.controlFill,
              borderRadius: BorderRadius.circular(DfTokens.radiusPill),
              border: Border.all(
                color: _hovered
                    ? (widget.danger
                          ? palette.danger.withValues(alpha: 0.55)
                          : palette.cardStrokeHover)
                    : palette.controlStroke,
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (widget.icon != null) ...[
                  Icon(widget.icon, size: 16, color: tone),
                  const SizedBox(width: 7),
                ],
                Text(
                  widget.label,
                  style: TextStyle(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w500,
                    color: tone,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// 玻璃标签，可选中。
class DfChip extends StatelessWidget {
  const DfChip({
    super.key,
    required this.label,
    this.selected = false,
    this.onTap,
    this.icon,
    this.tone,
  });

  final String label;
  final bool selected;
  final VoidCallback? onTap;
  final IconData? icon;
  final Color? tone;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    final color = tone ?? palette.accent;

    final chip = AnimatedContainer(
      duration: const Duration(milliseconds: 130),
      height: 30,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: selected ? color.withValues(alpha: 0.18) : palette.controlFill,
        borderRadius: BorderRadius.circular(DfTokens.radiusPill),
        border: Border.all(
          color: selected ? color.withValues(alpha: 0.5) : palette.controlStroke,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 13, color: selected ? color : palette.textSecondary),
            const SizedBox(width: 6),
          ],
          Text(
            label,
            style: TextStyle(
              fontSize: 12.5,
              fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
              color: selected ? color : palette.textSecondary,
            ),
          ),
        ],
      ),
    );

    if (onTap == null) return chip;
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onTap,
        child: chip,
      ),
    );
  }
}

/// 细进度条，自带玻璃轨道。
class DfProgressBar extends StatelessWidget {
  const DfProgressBar({
    super.key,
    required this.value,
    this.height = 6,
    this.showLabel = false,
    this.tone,
  });

  /// 0~1，null 表示不确定进度。
  final double? value;
  final double height;
  final bool showLabel;
  final Color? tone;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    final color = tone ?? palette.accent;
    final percent = ((value ?? 0) * 100).clamp(0, 100).toStringAsFixed(0);

    final bar = ClipRRect(
      borderRadius: BorderRadius.circular(DfTokens.radiusPill),
      child: SizedBox(
        height: height,
        child: value == null
            ? LinearProgressIndicator(
                backgroundColor: palette.divider,
                valueColor: AlwaysStoppedAnimation(color),
              )
            : Stack(
                children: [
                  Positioned.fill(
                    child: ColoredBox(color: palette.divider),
                  ),
                  FractionallySizedBox(
                    widthFactor: value!.clamp(0.0, 1.0),
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [color, palette.accentAlt],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
      ),
    );

    if (!showLabel) return bar;
    return Row(
      children: [
        Expanded(child: bar),
        const SizedBox(width: 10),
        Text('$percent%', style: DfText.micro(palette)),
      ],
    );
  }
}

/// 区块标题：左标题右动作。
class DfSectionHeader extends StatelessWidget {
  const DfSectionHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.trailing,
    this.padding = const EdgeInsets.only(bottom: DfTokens.gapSm),
  });

  final String title;
  final String? subtitle;
  final Widget? trailing;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    return Padding(
      padding: padding,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(title, style: DfText.section(palette)),
                if (subtitle != null) ...[
                  const SizedBox(height: 3),
                  Text(subtitle!, style: DfText.micro(palette)),
                ],
              ],
            ),
          ),
          if (trailing != null) trailing!,
        ],
      ),
    );
  }
}

/// 空状态：图标 + 一句话，居中。
class DfEmptyState extends StatelessWidget {
  const DfEmptyState({
    super.key,
    required this.icon,
    required this.message,
    this.hint,
    this.action,
    this.compact = false,
  });

  final IconData icon;
  final String message;
  final String? hint;
  final Widget? action;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    return Center(
      child: Padding(
        padding: EdgeInsets.symmetric(
          horizontal: DfTokens.gapLg,
          vertical: compact ? DfTokens.gapLg : 60,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            DfIconBadge(icon: icon, size: 56, iconSize: 24),
            const SizedBox(height: DfTokens.gapMd),
            Text(
              message,
              textAlign: TextAlign.center,
              style: DfText.body(palette).copyWith(fontWeight: FontWeight.w600),
            ),
            if (hint != null) ...[
              const SizedBox(height: DfTokens.gapXs),
              Text(
                hint!,
                textAlign: TextAlign.center,
                style: DfText.caption(palette),
              ),
            ],
            if (action != null) ...[
              const SizedBox(height: DfTokens.gapMd),
              ?action,
            ],
          ],
        ),
      ),
    );
  }
}

/// 提示条，用于错误与完成态。
class DfNotice extends StatelessWidget {
  const DfNotice({
    super.key,
    required this.message,
    this.icon = Icons.info_outline_rounded,
    this.tone,
  });

  final String message;
  final IconData icon;
  final Color? tone;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    final color = tone ?? palette.accent;
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: DfTokens.gapMd,
        vertical: DfTokens.gapSm,
      ),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(DfTokens.radiusControl),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: DfTokens.gapSm),
          Expanded(
            child: Text(
              message,
              style: TextStyle(fontSize: 13, color: palette.textPrimary),
            ),
          ),
        ],
      ),
    );
  }
}

/// 统计小块：数字 + 说明，用在下载概览、存储信息这类地方。
class DfStatTile extends StatelessWidget {
  const DfStatTile({
    super.key,
    required this.value,
    required this.label,
    this.icon,
    this.tone,
  });

  final String value;
  final String label;
  final IconData? icon;
  final Color? tone;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    return DfGlass(
      padding: const EdgeInsets.all(DfTokens.gapMd),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              if (icon != null) ...[
                Icon(icon, size: 15, color: tone ?? palette.accent),
                const SizedBox(width: 6),
              ],
              Text(label, style: DfText.micro(palette)),
            ],
          ),
          const SizedBox(height: 8),
          Text(value, style: DfText.number(palette)),
        ],
      ),
    );
  }
}

/// 圆形外壳的状态点，用于「有更新」这类轻提示。
class DfStatusDot extends StatelessWidget {
  const DfStatusDot({super.key, this.color, this.size = 8});

  final Color? color;
  final double size;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    final tone = color ?? palette.success;
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: tone,
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(color: tone.withValues(alpha: 0.6), blurRadius: 8),
        ],
      ),
    );
  }
}
