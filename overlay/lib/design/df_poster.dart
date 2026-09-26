import 'package:flutter/material.dart';

import '../core_bridge.dart';
import '../models.dart';
import '../widgets.dart';

import 'df_surface.dart';
import 'df_tokens.dart';

/// 海报卡：搜索结果与榜单的主力单元。
///
/// 封面用上游的 [DramaCover]（自带磁盘缓存与占位图），这里只负责外框、圆角、
/// 玻璃底与悬停反馈。悬停只改颜色不做位移，长列表里最省性能。
class DfPosterCard extends StatefulWidget {
  const DfPosterCard({
    super.key,
    required this.drama,
    required this.repository,
    this.onTap,
    this.badge,
    this.trailing,
  });

  final Drama drama;
  final AppRepository repository;
  final VoidCallback? onTap;

  /// 封面左上角的角标，如「已下载」。
  final Widget? badge;
  final Widget? trailing;

  @override
  State<DfPosterCard> createState() => _DfPosterCardState();
}

class _DfPosterCardState extends State<DfPosterCard> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    final drama = widget.drama;
    final meta = <String>[
      if (drama.episodes > 0) '${drama.episodes} 集',
      if (drama.category.isNotEmpty) drama.category,
    ].join(' · ');

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: widget.onTap,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 150),
                curve: Curves.easeOut,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(DfTokens.radiusCard),
                  border: Border.all(
                    color: _hovered
                        ? palette.accent.withValues(alpha: 0.6)
                        : palette.cardStroke,
                  ),
                  boxShadow: _hovered ? DfTokens.shadowSoft : null,
                ),
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(DfTokens.radiusCard),
                      child: DramaCover(
                        drama: drama,
                        repository: widget.repository,
                        radius: DfTokens.radiusCard,
                        // 海报墙的卡片只有一百多像素宽，按 260 解码足够清晰，
                        // 内存占用只有按 440 解码的三分之一
                        decodeWidth: 260,
                      ),
                    ),
                    // 底部压一层暗角，让白色标题在任何封面上都可读
                    Positioned(
                      left: 0,
                      right: 0,
                      bottom: 0,
                      child: IgnorePointer(
                        child: Container(
                          height: 38,
                          decoration: const BoxDecoration(
                            borderRadius: BorderRadius.vertical(
                              bottom: Radius.circular(DfTokens.radiusCard),
                            ),
                            gradient: LinearGradient(
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                              colors: [Color(0x00000000), Color(0x66000000)],
                            ),
                          ),
                        ),
                      ),
                    ),
                    if (widget.badge != null)
                      Positioned(
                        left: 8,
                        top: 8,
                        child: widget.badge!,
                      ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: DfTokens.gapSm),
            Row(
              children: [
                Expanded(
                  child: Text(
                    drama.title.isEmpty ? '未命名' : drama.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: _hovered ? palette.accent : palette.textPrimary,
                    ),
                  ),
                ),
                if (widget.trailing != null) widget.trailing!,
              ],
            ),
            if (meta.isNotEmpty) ...[
              const SizedBox(height: 2),
              Text(
                meta,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: DfText.micro(palette),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// 海报墙：按可用宽度决定列数，`shrinkWrap` 供嵌入滚动页使用。
///
/// 用 [GridView.builder] 而不是一次性铺开 children，超出屏幕的卡片不会构建，
/// 也不会提前解码封面。
class DfPosterGrid extends StatelessWidget {
  const DfPosterGrid({
    super.key,
    required this.items,
    required this.repository,
    this.onOpen,
    this.width,
    this.minCardWidth = 156,
    this.aspectRatio = 0.58,
    this.spacing = 14,
    this.padding = EdgeInsets.zero,
  });

  final List<Drama> items;
  final AppRepository repository;
  final void Function(Drama drama)? onOpen;
  final double? width;
  final double minCardWidth;
  final double aspectRatio;
  final double spacing;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final available = (width ?? MediaQuery.sizeOf(context).width) - 64;
    final columns = (available / minCardWidth).floor().clamp(2, 9);

    return GridView.builder(
      shrinkWrap: true,
      padding: padding,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: items.length,
      gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: columns,
        crossAxisSpacing: spacing,
        mainAxisSpacing: spacing,
        childAspectRatio: aspectRatio,
      ),
      itemBuilder: (context, index) => DfPosterCard(
        drama: items[index],
        repository: repository,
        onTap: onOpen == null ? null : () => onOpen!(items[index]),
      ),
    );
  }
}

/// 剧集格子：集号 + 状态点。
class DfEpisodeTile extends StatefulWidget {
  const DfEpisodeTile({
    super.key,
    required this.number,
    this.label,
    this.state = DfEpisodeState.idle,
    this.selected = false,
    this.onTap,
  });

  final int number;
  final String? label;
  final DfEpisodeState state;
  final bool selected;
  final VoidCallback? onTap;

  @override
  State<DfEpisodeTile> createState() => _DfEpisodeTileState();
}

enum DfEpisodeState { idle, downloading, done, failed }

class _DfEpisodeTileState extends State<DfEpisodeTile> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    final active = widget.selected || _hovered;

    final Color tone;
    switch (widget.state) {
      case DfEpisodeState.done:
        tone = palette.success;
      case DfEpisodeState.downloading:
        tone = palette.accent;
      case DfEpisodeState.failed:
        tone = palette.danger;
      case DfEpisodeState.idle:
        tone = active ? palette.accent : palette.textSecondary;
    }

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 120),
          height: 62,
          decoration: BoxDecoration(
            color: widget.selected
                ? palette.accentSoft
                : (_hovered ? palette.cardFillHover : palette.cardFill),
            borderRadius: BorderRadius.circular(DfTokens.radiusControl),
            border: Border.all(
              color: widget.selected
                  ? palette.accent.withValues(alpha: 0.55)
                  : (_hovered ? palette.cardStrokeHover : palette.cardStroke),
            ),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                widget.label ?? '${widget.number}',
                maxLines: 1,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: active ? palette.accent : palette.textPrimary,
                ),
              ),
              const SizedBox(height: 6),
              if (widget.state == DfEpisodeState.downloading)
                SizedBox(
                  width: 22,
                  child: DfProgressBar(value: null, height: 3, tone: tone),
                )
              else
                DfStatusDot(color: tone, size: 5),
            ],
          ),
        ),
      ),
    );
  }
}

/// 通用列表行：左图标/封面、中间两行文字、尾部动作。
class DfListRow extends StatefulWidget {
  const DfListRow({
    super.key,
    required this.title,
    this.subtitle,
    this.leading,
    this.trailing,
    this.onTap,
    this.selected = false,
    this.dense = false,
  });

  final String title;
  final String? subtitle;
  final Widget? leading;
  final Widget? trailing;
  final VoidCallback? onTap;
  final bool selected;
  final bool dense;

  @override
  State<DfListRow> createState() => _DfListRowState();
}

class _DfListRowState extends State<DfListRow> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    final highlighted = widget.selected || _hovered;

    return MouseRegion(
      cursor: widget.onTap == null
          ? SystemMouseCursors.basic
          : SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 120),
          padding: EdgeInsets.symmetric(
            horizontal: DfTokens.gapSm,
            vertical: widget.dense ? DfTokens.gapXs : DfTokens.gapSm,
          ),
          decoration: BoxDecoration(
            color: widget.selected
                ? palette.accentSoft
                : (_hovered ? palette.cardFillHover : Colors.transparent),
            borderRadius: BorderRadius.circular(DfTokens.radiusControl),
            border: Border.all(
              color: highlighted ? palette.cardStroke : Colors.transparent,
            ),
          ),
          child: Row(
            children: [
              if (widget.leading != null) ...[
                widget.leading!,
                const SizedBox(width: DfTokens.gapSm + 2),
              ],
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      widget.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 13.5,
                        fontWeight: FontWeight.w500,
                        color: palette.textPrimary,
                      ),
                    ),
                    if (widget.subtitle != null) ...[
                      const SizedBox(height: 2),
                      Text(
                        widget.subtitle!,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: DfText.micro(palette),
                      ),
                    ],
                  ],
                ),
              ),
              if (widget.trailing != null) ...[
                const SizedBox(width: DfTokens.gapSm),
                widget.trailing!,
              ],
            ],
          ),
        ),
      ),
    );
  }
}
