import 'package:flutter/material.dart';

import 'app_build.dart';
import 'design/df_design.dart';

/// 侧边导航的一项。
class DramaFetchNavItem {
  const DramaFetchNavItem({
    required this.icon,
    required this.selectedIcon,
    required this.label,
  });

  final IconData icon;
  final IconData selectedIcon;
  final String label;
}

/// 卡片式侧边导航：整条导航是一块悬浮的液态玻璃板。
///
/// 这里是全局唯一允许开背景模糊的地方之一（另一处是顶栏）。
/// 侧边栏尺寸固定、内容不滚动，[BackdropFilter] 只在窗口尺寸变化时重算一次，
/// 不会像列表卡片那样每帧复制背景，因此成本可以接受。
class DramaFetchNav extends StatelessWidget {
  const DramaFetchNav({
    super.key,
    required this.selectedIndex,
    required this.onSelected,
    required this.expanded,
    required this.destinations,
    this.version,
  });

  final int selectedIndex;
  final ValueChanged<int> onSelected;
  final bool expanded;
  final List<DramaFetchNavItem> destinations;

  /// 底部显示的版本号，不传则不显示。
  final String? version;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);

    return SizedBox(
      width: expanded ? 238 : 74,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 12, 6, 12),
        child: DfGlass(
          radius: DfTokens.radiusPanel,
          blur: 0,
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _Brand(expanded: expanded),
              const SizedBox(height: DfTokens.gapSm),
              DfDivider(height: DfTokens.gapSm, indent: 4),
              const SizedBox(height: DfTokens.gapSm),
              for (var index = 0; index < destinations.length; index++)
                _NavTile(
                  item: destinations[index],
                  selected: index == selectedIndex,
                  expanded: expanded,
                  onTap: () => onSelected(index),
                ),
              const Spacer(),
              if (version != null && version!.isNotEmpty) ...[
                const SizedBox(height: DfTokens.gapSm),
                Padding(
                  padding: const EdgeInsets.only(left: 10, bottom: 4),
                  child: expanded
                      ? Text(
                          'v${version!.split('+').first}',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: DfText.micro(palette),
                        )
                      : Center(
                          child: Text(
                            'v${version!.split('+').first}',
                            maxLines: 1,
                            style: DfText.micro(palette),
                          ),
                        ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// 侧边栏顶部的品牌区：应用图标加名称。
class _Brand extends StatelessWidget {
  const _Brand({required this.expanded});

  final bool expanded;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    return SizedBox(
      height: 46,
      child: Padding(
        padding: EdgeInsets.symmetric(horizontal: expanded ? 8 : 0),
        child: Row(
          mainAxisAlignment: expanded
              ? MainAxisAlignment.start
              : MainAxisAlignment.center,
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(10),
                gradient: DfTokens.accentGradient,
                boxShadow: DfTokens.shadowSoft,
              ),
              padding: const EdgeInsets.all(5),
              child: const Image(
                image: AssetImage('assets/logo.png'),
                filterQuality: FilterQuality.medium,
              ),
            ),
            if (expanded) ...[
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  appName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    letterSpacing: -0.2,
                    color: palette.textPrimary,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// 单个导航项：选中时是强调色玻璃胶囊，悬停只改底色。
class _NavTile extends StatefulWidget {
  const _NavTile({
    required this.item,
    required this.selected,
    required this.expanded,
    required this.onTap,
  });

  final DramaFetchNavItem item;
  final bool selected;
  final bool expanded;
  final VoidCallback onTap;

  @override
  State<_NavTile> createState() => _NavTileState();
}

class _NavTileState extends State<_NavTile> {
  bool _hovered = false;
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    final palette = DfPalette.of(context);
    final active = widget.selected || _hovered;

    final Color background;
    if (widget.selected) {
      background = palette.accentSoft;
    } else if (_hovered) {
      background = palette.cardFillHover;
    } else {
      background = Colors.transparent;
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: DfTokens.gapXs),
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        onEnter: (_) => setState(() => _hovered = true),
        onExit: (_) => setState(() => _hovered = false),
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: widget.onTap,
          child: Focus(
            onFocusChange: (value) => setState(() => _focused = value),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 130),
              curve: Curves.easeOut,
              height: 42,
              decoration: BoxDecoration(
                color: background,
                borderRadius: BorderRadius.circular(DfTokens.radiusControl),
                border: Border.all(
                  color: widget.selected
                      ? palette.accent.withValues(alpha: 0.45)
                      : (_focused
                            ? palette.accent.withValues(alpha: 0.6)
                            : Colors.transparent),
                ),
              ),
              child: Row(
                mainAxisAlignment: widget.expanded
                    ? MainAxisAlignment.start
                    : MainAxisAlignment.center,
                children: [
                  if (widget.expanded)
                    const SizedBox(width: 12)
                  else
                    const Spacer(),
                  Icon(
                    widget.selected
                        ? widget.item.selectedIcon
                        : widget.item.icon,
                    size: 18,
                    color: widget.selected
                        ? palette.accent
                        : (_hovered
                              ? palette.textPrimary
                              : palette.textSecondary),
                  ),
                  if (widget.expanded) ...[
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        widget.item.label,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 13.5,
                          fontWeight: widget.selected
                              ? FontWeight.w600
                              : FontWeight.w500,
                          color: active
                              ? (widget.selected
                                    ? palette.accent
                                    : palette.textPrimary)
                              : palette.textSecondary,
                        ),
                      ),
                    ),
                  ] else
                    const Spacer(),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
