import 'package:flutter/material.dart';

import 'app_build.dart';

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

/// Windows 11 风格的侧边导航。
///
/// 顶部是应用图标与名称，下面是四个入口。选中项用左侧强调色短条加浅色底表示，
/// 悬停项有过渡底色，整体贴合 WinUI 3 里导航视图的观感。
class DramaFetchNav extends StatelessWidget {
  const DramaFetchNav({
    super.key,
    required this.selectedIndex,
    required this.onSelected,
    required this.expanded,
    required this.destinations,
  });

  final int selectedIndex;
  final ValueChanged<int> onSelected;
  final bool expanded;
  final List<DramaFetchNavItem> destinations;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: expanded ? 232 : 56,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _Brand(expanded: expanded),
          const SizedBox(height: 6),
          for (var index = 0; index < destinations.length; index++)
            _NavTile(
              item: destinations[index],
              selected: index == selectedIndex,
              expanded: expanded,
              onTap: () => onSelected(index),
            ),
          const Spacer(),
        ],
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
    final scheme = Theme.of(context).colorScheme;
    return SizedBox(
      height: 56,
      child: Padding(
        padding: EdgeInsets.symmetric(horizontal: expanded ? 16 : 0),
        child: Row(
          mainAxisAlignment: expanded
              ? MainAxisAlignment.start
              : MainAxisAlignment.center,
          children: [
            const SizedBox(
              width: 24,
              height: 24,
              child: Image(
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
                    fontWeight: FontWeight.w600,
                    letterSpacing: -0.1,
                    color: scheme.onSurface,
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

/// 单个导航项。选中时左侧有一条强调色短条，悬停时底色轻微变化。
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
    final scheme = Theme.of(context).colorScheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final accent = widget.selected ? scheme.primary : scheme.onSurface;

    final Color? background = widget.selected
        ? (dark ? const Color(0xFF2D2D2D) : const Color(0xFFE9E9E9))
        : (_hovered
              ? (dark ? const Color(0xFF2A2A2A) : const Color(0xFFEFEFEF))
              : Colors.transparent);

    return Padding(
      padding: EdgeInsets.fromLTRB(widget.expanded ? 8 : 6, 2, 8, 2),
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
              duration: const Duration(milliseconds: 140),
              curve: Curves.easeOut,
              height: 40,
              decoration: BoxDecoration(
                color: background,
                borderRadius: BorderRadius.circular(5),
                border: _focused
                    ? Border.all(color: scheme.onSurface, width: 1.5)
                    : null,
              ),
              child: Row(
                children: [
                  // 选中指示条：WinUI 3 里贴在图标左侧的短条
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 160),
                    curve: Curves.easeOutCubic,
                    width: 3,
                    height: widget.selected ? 16 : 0,
                    margin: const EdgeInsets.only(left: 3, right: 7),
                    decoration: BoxDecoration(
                      color: scheme.primary,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                  Expanded(
                    child: Padding(
                      padding: EdgeInsets.only(
                        left: widget.selected ? 0 : 7,
                        right: widget.expanded ? 8 : 10,
                      ),
                      child: Row(
                        mainAxisAlignment: widget.expanded
                            ? MainAxisAlignment.start
                            : MainAxisAlignment.center,
                        children: [
                          Icon(
                            widget.selected
                                ? widget.item.selectedIcon
                                : widget.item.icon,
                            size: 18,
                            color: widget.selected
                                ? scheme.primary
                                : scheme.onSurfaceVariant,
                          ),
                          if (widget.expanded) ...[
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                widget.item.label,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  fontSize: 14,
                                  fontWeight: widget.selected
                                      ? FontWeight.w600
                                      : FontWeight.w400,
                                  color: widget.selected
                                      ? accent
                                      : scheme.onSurface,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
