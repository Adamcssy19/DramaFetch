import 'dart:ui' show ImageFilter;

import 'package:flutter/material.dart';

import 'df_tokens.dart';
import 'df_window_bar.dart';

/// 应用背景：渐变打底 + 三团静态光斑。
///
/// 光斑是玻璃质感的必要前提 —— 纯色背景上的半透明面板看起来只是灰方块。
/// 用 [CustomPaint] 一次画完，尺寸不变就不再重绘，比叠三层大模糊图省得多。
///
/// 另外负责挂载窗口按钮：系统标题栏已经在 windows/runner/main.cpp 里摘掉，
/// 最小化与关闭必须由应用自己提供，挂在这一层才能保证每个页面都看得到。
class DfBackdrop extends StatelessWidget {
  const DfBackdrop({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [palette.backdropTop, palette.backdropBottom],
        ),
      ),
      child: Stack(
        fit: StackFit.expand,
        children: [
          RepaintBoundary(
            child: CustomPaint(painter: _GlowPainter(palette)),
          ),
          child,
          const Positioned(top: 10, right: 14, child: DfWindowButtons()),
        ],
      ),
    );
  }
}

class _GlowPainter extends CustomPainter {
  const _GlowPainter(this.palette);

  final DfPalette palette;

  @override
  void paint(Canvas canvas, Size size) {
    void glow(Offset center, double radius, Color color) {
      final paint = Paint()
        ..shader = RadialGradient(
          colors: [color, color.withValues(alpha: 0)],
          stops: const [0.0, 1.0],
        ).createShader(Rect.fromCircle(center: center, radius: radius));
      canvas.drawCircle(center, radius, paint);
    }

    final shortest = size.shortestSide;
    glow(
      Offset(size.width * 0.16, size.height * -0.04),
      shortest * 0.98,
      palette.glowPrimary,
    );
    glow(
      Offset(size.width * 0.94, size.height * 0.1),
      shortest * 0.82,
      palette.glowSecondary,
    );
    glow(
      Offset(size.width * 0.58, size.height * 1.08),
      shortest * 1.05,
      palette.glowTertiary,
    );
  }

  @override
  bool shouldRepaint(_GlowPainter oldDelegate) =>
      !identical(oldDelegate.palette, palette);
}

/// 玻璃面板：卡片式布局的基础块。
///
/// 视觉由四层叠出来 —— 外阴影、半透明填充、1 像素描边、内部斜向高光。
/// [blur] 大于 0 才会真正模糊背景，**只给侧边栏、顶栏、对话框这类固定浮层用**，
/// 列表里成百上千个卡片全都开模糊会直接把低配机器拖垮。
class DfGlass extends StatelessWidget {
  const DfGlass({
    super.key,
    required this.child,
    this.radius = DfTokens.radiusCard,
    this.padding = EdgeInsets.zero,
    this.margin,
    this.blur = 0,
    this.fill,
    this.stroke,
    this.shadows,
    this.sheen = true,
    this.width,
    this.height,
    this.clip = true,
  });

  final Widget child;
  final double radius;
  final EdgeInsetsGeometry padding;
  final EdgeInsetsGeometry? margin;

  /// 背景模糊强度，0 表示不模糊（默认，最省性能）。
  final double blur;
  final Color? fill;
  final Color? stroke;
  final List<BoxShadow>? shadows;
  final bool sheen;
  final double? width;
  final double? height;
  final bool clip;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    final radiusValue = BorderRadius.circular(radius);
    final shadowList = shadows ?? DfTokens.shadowSoft;

    Widget panel = DecoratedBox(
      decoration: BoxDecoration(
        color: fill ?? palette.glassFill,
        borderRadius: radiusValue,
        border: Border.all(color: stroke ?? palette.glassStroke),
      ),
      child: Stack(
        children: [
          if (sheen)
            Positioned.fill(
              child: IgnorePointer(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    borderRadius: radiusValue,
                    gradient: DfTokens.sheen,
                  ),
                ),
              ),
            ),
          Padding(padding: padding, child: child),
        ],
      ),
    );

    if (blur > 0) {
      panel = BackdropFilter(
        filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
        child: panel,
      );
    }

    if (clip) {
      panel = ClipRRect(borderRadius: radiusValue, child: panel);
    }

    return Container(
      width: width,
      height: height,
      margin: margin,
      decoration: BoxDecoration(
        borderRadius: radiusValue,
        boxShadow: shadowList,
      ),
      child: panel,
    );
  }
}

/// 可点击的玻璃卡片。
///
/// 悬停只改填充色与描边色，**不做位移和缩放** —— 变换会让整张卡片重新合成，
/// 长列表里逐个抬升是低配机器的头号卡顿源。
class DfCard extends StatefulWidget {
  const DfCard({
    super.key,
    required this.child,
    this.onTap,
    this.onSecondaryTap,
    this.padding = const EdgeInsets.all(DfTokens.gapMd),
    this.radius = DfTokens.radiusCard,
    this.selected = false,
    this.interactive = true,
    this.blur = 0,
    this.fill,
    this.stroke,
    this.width,
    this.height,
  });

  final Widget child;
  final VoidCallback? onTap;
  final VoidCallback? onSecondaryTap;
  final EdgeInsetsGeometry padding;
  final double radius;
  final bool selected;

  /// 是否响应悬停高亮。静态展示卡（如统计块）可设为 false 省掉一次监听。
  final bool interactive;
  final double blur;
  final Color? fill;
  final Color? stroke;
  final double? width;
  final double? height;

  @override
  State<DfCard> createState() => _DfCardState();
}

class _DfCardState extends State<DfCard> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);

    final Color fill;
    if (widget.selected) {
      fill = palette.accentSoft;
    } else if (_hovered) {
      fill = widget.fill ?? palette.cardFillHover;
    } else {
      fill = widget.fill ?? palette.cardFill;
    }

    final Color stroke;
    if (widget.selected) {
      stroke = palette.accent.withValues(alpha: 0.55);
    } else if (_hovered) {
      stroke = widget.stroke ?? palette.cardStrokeHover;
    } else {
      stroke = widget.stroke ?? palette.cardStroke;
    }

    Widget card = AnimatedContainer(
      duration: const Duration(milliseconds: 130),
      curve: Curves.easeOut,
      padding: widget.padding,
      decoration: BoxDecoration(
        color: fill,
        borderRadius: BorderRadius.circular(widget.radius),
        border: Border.all(color: stroke),
        boxShadow: widget.blur > 0 ? DfTokens.shadowFloat : DfTokens.shadowSoft,
      ),
      child: widget.child,
    );

    if (widget.blur > 0) {
      card = BackdropFilter(
        filter: ImageFilter.blur(sigmaX: widget.blur, sigmaY: widget.blur),
        child: card,
      );
    }

    card = ClipRRect(borderRadius: BorderRadius.circular(widget.radius), child: card);

    final content = SizedBox(
      width: widget.width,
      height: widget.height,
      child: card,
    );

    final clickable = widget.onTap != null || widget.onSecondaryTap != null;
    if (!clickable || !widget.interactive) return content;

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: widget.onTap,
        onSecondaryTap: widget.onSecondaryTap,
        child: content,
      ),
    );
  }
}

/// 区块分隔线，比系统默认更淡。
class DfDivider extends StatelessWidget {
  const DfDivider({super.key, this.indent = 0, this.height = DfTokens.gapMd});

  final double indent;
  final double height;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    return Padding(
      padding: EdgeInsets.symmetric(vertical: height / 2),
      child: Divider(
        height: 1,
        thickness: 1,
        indent: indent,
        color: palette.divider,
      ),
    );
  }
}

/// 图标底座：卡片里放图标时的统一容器，省得每处都手写一圈玻璃底。
class DfIconBadge extends StatelessWidget {
  const DfIconBadge({
    super.key,
    required this.icon,
    this.size = 42,
    this.iconSize = 20,
    this.color,
    this.radius = DfTokens.radiusControl,
  });

  final IconData icon;
  final double size;
  final double iconSize;
  final Color? color;
  final double radius;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    final tone = color ?? palette.accent;
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(radius),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [tone.withValues(alpha: 0.26), tone.withValues(alpha: 0.08)],
        ),
        border: Border.all(color: tone.withValues(alpha: 0.28)),
      ),
      child: Icon(icon, size: iconSize, color: tone),
    );
  }
}
