import 'dart:async';

import 'package:flutter/material.dart';

import 'app_theme.dart';
import 'core_bridge.dart';
import 'local_store.dart';
import 'models.dart';
import 'widgets.dart';

/// 首页：打开软件第一眼就是搜索。
/// 搜索框下面是之前搜过的关键词，点一下就能再搜一次；输入后直接给出结果列表。
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
  bool _loading = false;
  String? _error;
  List<Drama> _results = const [];
  String _submitted = '';

  @override
  void dispose() {
    _debounce?.cancel();
    _input.dispose();
    _focus.dispose();
    super.dispose();
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

    return AnimatedBuilder(
      animation: widget.store,
      builder: (context, _) => ListView(
        padding: const EdgeInsets.fromLTRB(32, 28, 32, 32),
        children: [
          Text('搜索', style: AppTheme.title(context)),
          const SizedBox(height: 6),
          Text('输入剧名即可查找，结果会随输入实时更新', style: AppTheme.caption(context)),
          const SizedBox(height: 22),
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
            const SizedBox(height: 34),
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
            const SizedBox(height: 12),
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
            const SizedBox(height: 30),
            Text(
              '搜索结果 · ${_results.length} 部',
              style: AppTheme.section(context),
            ),
            const SizedBox(height: 12),
            for (final drama in _results)
              _ResultRow(
                drama: drama,
                repository: widget.repository,
                onTap: () => widget.onOpen(drama),
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
            style: TextStyle(
              fontSize: 13,
              color: theme.colorScheme.onSurface,
            ),
          ),
        ),
      ),
    );
  }
}

/// 搜索结果的一行：封面加标题，悬停时整行底色变化。
class _ResultRow extends StatefulWidget {
  const _ResultRow({
    required this.drama,
    required this.repository,
    required this.onTap,
  });

  final Drama drama;
  final AppRepository repository;
  final VoidCallback onTap;

  @override
  State<_ResultRow> createState() => _ResultRowState();
}

class _ResultRowState extends State<_ResultRow> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final drama = widget.drama;
    final meta = <String>[
      if (drama.episodes > 0) '${drama.episodes} 集',
      if (drama.category.isNotEmpty) drama.category,
      if (drama.releaseStatus.isNotEmpty) drama.releaseLabel,
    ].join(' · ');

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 130),
          curve: Curves.easeOut,
          margin: const EdgeInsets.only(bottom: 4),
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: _hovered
                ? theme.colorScheme.surfaceContainer
                : Colors.transparent,
            borderRadius: BorderRadius.circular(AppTheme.radiusCard),
          ),
          child: Row(
            children: [
              SizedBox(
                width: 48,
                height: 64,
                child: DramaCover(
                  drama: drama,
                  repository: widget.repository,
                  radius: AppTheme.radiusControl,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      drama.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: theme.colorScheme.onSurface,
                      ),
                    ),
                    if (meta.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(meta, style: AppTheme.caption(context)),
                    ],
                  ],
                ),
              ),
              const SizedBox(width: 12),
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
