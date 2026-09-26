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
/// 搜索框下面是之前搜过的关键词，点一下就能再搜一次；输入后以海报墙的方式给出结果。
/// 打开软件时会自动做一次更新检查（先测速选源），有新版本就弹窗提示。
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
    _debounce = Timer(const Duration(milliseconds: 400), () => _search(query));
  }

  Future<void> _search(String query) async {
    final source = widget.store.sources.isEmpty
        ? ''
        : widget.store.sources.first.id;
    if (source.isEmpty) {
      setState(() => _error = '暂无可用站源');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
      _submitted = query;
    });
    unawaited(widget.store.rememberSearch(query));
    try {
      final page = await widget.repository.catalog(source, query: query);
      if (!mounted) return;
      setState(() => _results = page.items);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _useKeyword(String keyword) {
    _input.text = keyword;
    _input.selection = TextSelection.collapsed(offset: keyword.length);
    unawaited(_search(keyword));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final history = widget.store.recentSearches;
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
            Text('输入剧名即可查找，结果会随输入实时更新', style: AppTheme.caption(context)),
            const SizedBox(height: 20),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 560),
              child: TextField(
                controller: _input,
                focusNode: _focus,
                autofocus: true,
                style: theme.textTheme.bodyMedium,
                onChanged: (value) => setState(() => _onChanged(value)),
                onSubmitted: (value) {
                  final query = value.trim();
                  if (query.isNotEmpty) unawaited(_search(query));
                },
                decoration: InputDecoration(
                  hintText: '搜索想看的剧',
                  isDense: true,
                  prefixIcon: Icon(
                    Icons.search_rounded,
                    size: 18,
                    color: scheme.onSurfaceVariant,
                  ),
                  prefixIconConstraints: const BoxConstraints(
                    minWidth: 38,
                    minHeight: 20,
                  ),
                  suffixIcon: !typing
                      ? null
                      : IconButton(
                          tooltip: '清空',
                          iconSize: 16,
                          icon: const Icon(Icons.close_rounded),
                          onPressed: () {
                            _input.clear();
                            setState(() => _onChanged(''));
                            _focus.requestFocus();
                          },
                        ),
                ),
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
                  Text('最近搜索', style: AppTheme.section(context)),
                  const Spacer(),
                  if (history.isNotEmpty)
                    TextButton(
                      onPressed: () =>
                          unawaited(widget.store.clearRecentSearches()),
                      child: const Text('清空记录'),
                    ),
                ],
              ),
              const SizedBox(height: 10),
              if (history.isEmpty)
                Text('还没有搜索记录', style: AppTheme.caption(context))
              else
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final keyword in history)
                      _KeywordButton(
                        keyword: keyword,
                        onTap: () => _useKeyword(keyword),
                      ),
                  ],
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
                onOpen: widget.onOpen,
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
              drama.title,
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

/// 最近搜索的关键词按钮，样式贴近系统里的次要按钮。
class _KeywordButton extends StatefulWidget {
  const _KeywordButton({required this.keyword, required this.onTap});

  final String keyword;
  final VoidCallback onTap;

  @override
  State<_KeywordButton> createState() => _KeywordButtonState();
}

class _KeywordButtonState extends State<_KeywordButton> {
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
          duration: const Duration(milliseconds: 140),
          curve: Curves.easeOut,
          height: 32,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: _hovered
                ? theme.colorScheme.surfaceContainerHigh
                : theme.colorScheme.surfaceContainer,
            borderRadius: BorderRadius.circular(AppTheme.radiusControl),
            border: Border.all(color: theme.colorScheme.outlineVariant),
          ),
          child: Text(
            widget.keyword,
            style: TextStyle(fontSize: 13, color: theme.colorScheme.onSurface),
          ),
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
