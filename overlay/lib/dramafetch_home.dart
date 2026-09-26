import 'dart:async';

import 'package:flutter/material.dart';

import 'app_layout.dart';
import 'app_theme.dart';
import 'core_bridge.dart';
import 'dramafetch_update.dart';
import 'local_store.dart';
import 'models.dart';
import 'widgets.dart';

/// 首页：打开软件第一眼就是搜索。
///
/// 搜索支持三种输入：
/// - 剧名关键词，走目录搜索
/// - 剧集编号（纯数字），直接打开详情
/// - 播放页链接，从链接里取出编号后直接打开
///
/// 下面列出的是**点开过的剧**，点一下直接回到那部剧；只是搜过没点开的不记。
class DramaFetchHome extends StatefulWidget {
  const DramaFetchHome({
    super.key,
    required this.repository,
    required this.store,
    required this.onOpen,
  });

  final AppRepository repository;
  final LocalStore store;
  final void Function(Drama drama) onOpen;

  @override
  State<DramaFetchHome> createState() => _DramaFetchHomeState();
}

class _DramaFetchHomeState extends State<DramaFetchHome> {
  final _input = TextEditingController();
  final _focus = FocusNode();
  Timer? _debounce;
  DramaFetchUpdateManager? _updates;
  bool _loading = false;
  String? _error;
  List<Drama> _results = const [];
  String _submitted = '';

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_updates != null) return;
    _updates = DramaFetchUpdateManager(
      repository: widget.repository,
      currentVersion: AppLayout.versionOf(context).split('+').first,
    );
    _scheduleAutoCheck();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _input.dispose();
    _focus.dispose();
    _updates?.dispose();
    super.dispose();
  }

  String get _sourceID =>
      widget.store.sources.isEmpty ? 'hongguo' : widget.store.sources.first.id;

  /// 打开软件后稍等片刻再做更新检查，避免和首屏加载抢资源。
  void _scheduleAutoCheck() {
    unawaited(
      Future<void>.delayed(const Duration(seconds: 2), () async {
        final manager = _updates;
        if (!mounted || manager == null) return;
        await manager.checkAuto();
        if (!mounted || !manager.hasUpdate || manager.dialogShown) return;
        await showUpdateDialog(context, manager);
      }),
    );
  }

  void _open(Drama drama) {
    unawaited(widget.store.rememberOpened(drama.id, drama.title));
    widget.onOpen(drama);
  }

  /// 从输入里提取剧集编号：纯数字，或链接里的长数字串。
  String? _extractDramaID(String input) {
    final text = input.trim();
    if (RegExp(r'^\d{8,}$').hasMatch(text)) return text;
    if (!text.contains('/') && !text.toLowerCase().contains('http')) {
      return null;
    }
    final match = RegExp(r'(\d{10,})').firstMatch(text);
    return match?.group(1);
  }

  void _onChanged(String value) {
    _debounce?.cancel();
    final query = value.trim();
    if (query.isEmpty) {
      setState(() {
        _results = const [];
        _submitted = '';
        _error = null;
        _loading = false;
      });
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 400), () => _submit(query));
  }

  /// 统一入口：编号或链接直接打开，其余当关键词搜索。
  Future<void> _submit(String raw) async {
    final query = raw.trim();
    if (query.isEmpty) return;
    final direct = _extractDramaID(query);
    if (direct != null) {
      _open(Drama(id: direct, source: _sourceID, title: direct));
      return;
    }
    await _search(query);
  }

  Future<void> _search(String query) async {
    if (widget.store.sources.isEmpty) {
      setState(() => _error = '暂无可用下载渠道');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
      _submitted = query;
    });
    try {
      final page = await widget.repository.catalog(_sourceID, query: query);
      if (!mounted) return;
      setState(() => _results = page.items);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final opened = widget.store.recentOpened;
    final typing = _input.text.trim().isNotEmpty;
    final updates = _updates;

    return AnimatedBuilder(
      animation: widget.store,
      builder: (context, _) => LayoutBuilder(
        builder: (context, constraints) => ListView(
          padding: const EdgeInsets.fromLTRB(32, 26, 32, 32),
          children: [
            if (updates != null)
              DramaFetchUpdateBanner(
                manager: updates,
                onTap: () {
                  updates.dialogShown = true;
                  showUpdateDialog(context, updates);
                },
              ),
            Text('搜索', style: AppTheme.title(context)),
            const SizedBox(height: 6),
            Text(
              '输剧名、剧集编号，或直接粘贴播放页链接',
              style: AppTheme.caption(context),
            ),
            const SizedBox(height: 20),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 560),
              child: _SearchBox(
                controller: _input,
                focusNode: _focus,
                onChanged: (value) => setState(() => _onChanged(value)),
                onSubmitted: (value) => unawaited(_submit(value)),
                onClear: () {
                  _input.clear();
                  setState(() => _onChanged(''));
                  _focus.requestFocus();
                },
                showClear: typing,
              ),
            ),
            if (_loading) ...[
              const SizedBox(height: 14),
              const LinearProgressIndicator(minHeight: 2),
            ],
            if (_error != null) ...[
              const SizedBox(height: 18),
              _Notice(icon: Icons.error_outline, message: _error!),
            ],
            if (!typing) ...[
              const SizedBox(height: 32),
              Row(
                children: [
                  Text('最近打开', style: AppTheme.section(context)),
                  const Spacer(),
                  if (opened.isNotEmpty)
                    TextButton(
                      onPressed: () =>
                          unawaited(widget.store.clearRecentOpened()),
                      child: const Text('清空记录'),
                    ),
                ],
              ),
              const SizedBox(height: 6),
              if (opened.isEmpty)
                Text('还没有打开过任何剧', style: AppTheme.caption(context))
              else
                for (final entry in opened)
                  _OpenedRow(
                    title: entry['title'] ?? '',
                    onTap: () => _open(
                      Drama(
                        id: entry['id'] ?? '',
                        source: _sourceID,
                        title: entry['title'] ?? '',
                      ),
                    ),
                  ),
            ],
            if (typing && _results.isNotEmpty) ...[
              const SizedBox(height: 28),
              Text(
                '搜索结果 · ${_results.length} 部',
                style: AppTheme.section(context),
              ),
              const SizedBox(height: 14),
              _ResultGrid(
                items: _results,
                repository: widget.repository,
                width: constraints.maxWidth,
                onOpen: _open,
              ),
            ],
            if (typing && !_loading && _results.isEmpty && _error == null) ...[
              const SizedBox(height: 60),
              Center(
                child: Column(
                  children: [
                    Icon(
                      Icons.search_off_rounded,
                      size: 32,
                      color: scheme.onSurfaceVariant,
                    ),
                    const SizedBox(height: 10),
                    Text(
                      '没有找到「$_submitted」相关的剧',
                      style: AppTheme.caption(context),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// 深色描边搜索框，照着 Uiverse 上那款样式做的：
/// 深灰底、2 像素描边、圆角 5，聚焦时描边与文字转青色，并在左上方带一层青色光晕。
class _SearchBox extends StatefulWidget {
  const _SearchBox({
    required this.controller,
    required this.focusNode,
    required this.onChanged,
    required this.onSubmitted,
    required this.onClear,
    required this.showClear,
  });

  final TextEditingController controller;
  final FocusNode focusNode;
  final ValueChanged<String> onChanged;
  final ValueChanged<String> onSubmitted;
  final VoidCallback onClear;
  final bool showClear;

  @override
  State<_SearchBox> createState() => _SearchBoxState();
}

class _SearchBoxState extends State<_SearchBox> {
  static const _fill = Color(0xFF212121);
  static const _cyan = Color(0xFF00FFFF);
  static const _stroke = Color(0xFFFFFFFF);

  bool _focused = false;

  @override
  void initState() {
    super.initState();
    widget.focusNode.addListener(_onFocusChanged);
  }

  @override
  void dispose() {
    widget.focusNode.removeListener(_onFocusChanged);
    super.dispose();
  }

  void _onFocusChanged() {
    if (!mounted) return;
    setState(() => _focused = widget.focusNode.hasFocus);
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 100),
      curve: Curves.easeOut,
      height: 44,
      padding: const EdgeInsets.symmetric(horizontal: 10),
      decoration: BoxDecoration(
        color: _fill,
        borderRadius: BorderRadius.circular(5),
        border: Border.all(color: _focused ? _cyan : _stroke, width: 2),
        boxShadow: _focused
            ? [
                BoxShadow(
                  color: _cyan.withValues(alpha: 0.85),
                  offset: const Offset(-3, -3),
                  blurRadius: 15,
                ),
              ]
            : null,
      ),
      child: TextField(
        controller: widget.controller,
        focusNode: widget.focusNode,
        autofocus: true,
        cursorColor: _focused ? _cyan : _stroke,
        style: TextStyle(
          fontSize: 14,
          color: _focused ? _cyan : _stroke,
        ),
        decoration: InputDecoration(
          hintText: '搜索想看的剧',
          hintStyle: const TextStyle(color: Color(0xFF9E9E9E), fontSize: 14),
          isDense: true,
          filled: false,
          border: InputBorder.none,
          enabledBorder: InputBorder.none,
          focusedBorder: InputBorder.none,
          contentPadding: const EdgeInsets.symmetric(vertical: 12),
          suffixIcon: !widget.showClear
              ? null
              : IconButton(
                  tooltip: '清空',
                  iconSize: 16,
                  color: _focused ? _cyan : _stroke,
                  icon: const Icon(Icons.close_rounded),
                  onPressed: widget.onClear,
                ),
        ),
        onChanged: widget.onChanged,
        onSubmitted: widget.onSubmitted,
      ),
    );
  }
}

/// 最近打开过的一部剧。
class _OpenedRow extends StatefulWidget {
  const _OpenedRow({required this.title, required this.onTap});

  final String title;
  final VoidCallback onTap;

  @override
  State<_OpenedRow> createState() => _OpenedRowState();
}

class _OpenedRowState extends State<_OpenedRow> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 130),
          curve: Curves.easeOut,
          height: 44,
          padding: const EdgeInsets.symmetric(horizontal: 10),
          margin: const EdgeInsets.only(bottom: 2),
          decoration: BoxDecoration(
            color: _hovered
                ? theme.colorScheme.surfaceContainer
                : Colors.transparent,
            borderRadius: BorderRadius.circular(AppTheme.radiusControl),
          ),
          child: Row(
            children: [
              Icon(
                Icons.history_rounded,
                size: 16,
                color: theme.colorScheme.onSurfaceVariant,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  widget.title.isEmpty ? '未命名' : widget.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 14,
                    color: theme.colorScheme.onSurface,
                  ),
                ),
              ),
              Icon(
                Icons.chevron_right_rounded,
                size: 18,
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 搜索结果的海报墙。按可用宽度自动决定列数。
class _ResultGrid extends StatelessWidget {
  const _ResultGrid({
    required this.items,
    required this.repository,
    required this.width,
    required this.onOpen,
  });

  final List<Drama> items;
  final AppRepository repository;
  final double width;
  final void Function(Drama drama) onOpen;

  @override
  Widget build(BuildContext context) {
    final available = width - 64;
    final columns = (available / 168).floor().clamp(2, 8);
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: items.length,
      gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: columns,
        crossAxisSpacing: 14,
        mainAxisSpacing: 14,
        mainAxisExtent: 244,
      ),
      itemBuilder: (context, index) => _ResultCard(
        drama: items[index],
        repository: repository,
        onTap: () => onOpen(items[index]),
      ),
    );
  }
}

/// 一张海报卡片：封面加标题，悬停时描边变强调色。
class _ResultCard extends StatefulWidget {
  const _ResultCard({
    required this.drama,
    required this.repository,
    required this.onTap,
  });

  final Drama drama;
  final AppRepository repository;
  final VoidCallback onTap;

  @override
  State<_ResultCard> createState() => _ResultCardState();
}

class _ResultCardState extends State<_ResultCard> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
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
        onTap: widget.onTap,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 150),
                curve: Curves.easeOut,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(AppTheme.radiusCard),
                  border: Border.all(
                    color: _hovered ? scheme.primary : scheme.outlineVariant,
                    width: _hovered ? 1.5 : 1,
                  ),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(AppTheme.radiusCard - 1),
                  child: DramaCover(
                    drama: drama,
                    repository: widget.repository,
                    radius: AppTheme.radiusCard - 1,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              drama.title.isEmpty ? '未命名' : drama.title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: _hovered ? scheme.primary : scheme.onSurface,
              ),
            ),
            if (meta.isNotEmpty) ...[
              const SizedBox(height: 2),
              Text(
                meta,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(fontSize: 11, color: scheme.onSurfaceVariant),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// 提示条：用于错误等需要立刻看见的信息。
class _Notice extends StatelessWidget {
  const _Notice({required this.icon, required this.message});

  final IconData icon;
  final String message;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: scheme.errorContainer.withValues(alpha: 0.35),
        borderRadius: BorderRadius.circular(AppTheme.radiusCard),
        border: Border.all(color: scheme.error.withValues(alpha: 0.4)),
      ),
      child: Row(
        children: [
          Icon(icon, size: 16, color: scheme.error),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: TextStyle(fontSize: 13, color: scheme.onSurface),
            ),
          ),
        ],
      ),
    );
  }
}
