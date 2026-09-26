import 'dart:io';

import 'package:flutter/material.dart';
import 'package:window_manager/window_manager.dart';

import 'df_tokens.dart';

/// 无边框窗口的窗口按钮。
///
/// 系统标题栏已经在 `windows/runner/main.cpp` 里摘掉、窗口铺满屏幕工作区，
/// 最小化与关闭改由应用自己提供，所以这两个按钮必须常驻在所有页面之上 ——
/// 由 [DfBackdrop] 统一挂载，任何页面（包括对话框）都能看到。
///
/// 这里刻意不复用 `DfGlass`：那个组件在 `df_surface.dart` 里，本文件又被它引用，
/// 互相 import 虽然能编译，但读起来绕。玻璃底直接用令牌画一遍更清楚。
class DfWindowButtons extends StatelessWidget {
  const DfWindowButtons({super.key});

  @override
  Widget build(BuildContext context) {
    // 只有桌面端去掉了系统标题栏，其它平台沿用系统自带的那一套按钮
    if (!Platform.isWindows) return const SizedBox.shrink();

    final palette = DfPalette.of(context);
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: palette.glassFillStrong,
        borderRadius: BorderRadius.circular(DfTokens.radiusPill),
        border: Border.all(color: palette.glassStroke),
        boxShadow: DfTokens.shadowSoft,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _WindowButton(
            icon: Icons.remove_rounded,
            tooltip: '最小化',
            onPressed: () => _invoke(windowManager.minimize),
          ),
          const SizedBox(width: 2),
          _WindowButton(
            icon: Icons.close_rounded,
            tooltip: '关闭',
            danger: true,
            onPressed: () => _invoke(windowManager.close),
          ),
        ],
      ),
    );
  }
}

/// 窗口管理器在未初始化或非桌面环境下会抛异常，这里统一吞掉：
/// 按钮点不动，总好过把整个界面拖崩。
Future<void> _invoke(Future<void> Function() action) async {
  try {
    await action();
  } catch (_) {
    // 忽略：窗口管理器当前不可用
  }
}

class _WindowButton extends StatefulWidget {
  const _WindowButton({
    required this.icon,
    required this.tooltip,
    required this.onPressed,
    this.danger = false,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback onPressed;

  /// 关闭按钮悬停时用警示色，避免误点。
  final bool danger;

  @override
  State<_WindowButton> createState() => _WindowButtonState();
}

class _WindowButtonState extends State<_WindowButton> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    final hot = _hovered && widget.danger;

    return Tooltip(
      message: widget.tooltip,
      waitDuration: const Duration(milliseconds: 400),
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        onEnter: (_) => setState(() => _hovered = true),
        onExit: (_) => setState(() => _hovered = false),
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: widget.onPressed,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 120),
            curve: Curves.easeOut,
            width: 30,
            height: 26,
            decoration: BoxDecoration(
              color: hot
                  ? palette.danger.withValues(alpha: 0.9)
                  : (_hovered ? palette.cardFillHover : Colors.transparent),
              borderRadius: BorderRadius.circular(DfTokens.radiusPill),
            ),
            child: Icon(
              widget.icon,
              size: 16,
              color: hot ? Colors.white : palette.textSecondary,
            ),
          ),
        ),
      ),
    );
  }
}
