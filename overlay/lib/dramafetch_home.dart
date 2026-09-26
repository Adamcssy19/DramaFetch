import 'dart:async';

import 'package:flutter/material.dart';

import 'app_theme.dart';
import 'core_bridge.dart';
import 'local_store.dart';
import 'models.dart';

/// 本项目改造：首页以搜索为主。
/// 打开软件第一眼就是搜索框，下面是最近搜索过的关键词，点击即可直接再搜一次。
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
  Timer? _debounce;
  bool _loading = false;
  String? _error;
  List<Drama> _results = const [];

  @override
  void dispose() {
    _debounce?.cancel();
    _input.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    _debounce?.cancel();
    final query = value.trim();
    if (query.isEmpty) {
      setState(() {
        _results = const [];
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
    final scheme = Theme.of(context).colorScheme;
    final history = widget.store.recentSearches;
    return AnimatedBuilder(
      animation: widget.store,
      builder: (context, _) => ListView(
        padding: const EdgeInsets.fromLTRB(24, 28, 24, 24),
        children: [
          TextField(
            controller: _input,
            autofocus: true,
            onChanged: _onChanged,
            onSubmitted: (value) {
              final query = value.trim();
              if (query.isNotEmpty) unawaited(_search(query));
            },
            decoration: InputDecoration(
              hintText: '搜索想看的短剧',
              prefixIcon: const Icon(Icons.search_rounded),
              suffixIcon: _input.text.isEmpty
                  ? null
                  : IconButton(
                      tooltip: '清空',
                      icon: const Icon(Icons.close_rounded),
                      onPressed: () {
                        _input.clear();
                        _onChanged('');
                      },
                    ),
            ),
          ),
          if (_loading) const Padding(
            padding: EdgeInsets.only(top: 16),
            child: LinearProgressIndicator(),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(top: 16),
              child: Text(_error!, style: TextStyle(color: scheme.error)),
            ),
          if (_input.text.trim().isEmpty) ...[
            const SizedBox(height: 28),
            Row(
              children: [
                Text(
                  '最近搜索',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: scheme.onSurfaceVariant,
                  ),
                ),
                const Spacer(),
                if (history.isNotEmpty)
                  TextButton(
                    onPressed: () =>
                        unawaited(widget.store.clearRecentSearches()),
                    child: const Text('清空'),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            if (history.isEmpty)
              Text(
                '还没有搜索记录',
                style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 13),
              )
            else
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final keyword in history)
                    ActionChip(
                      label: Text(keyword),
                      onPressed: () => _useKeyword(keyword),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(
                          AppTheme.radiusCard,
                        ),
                        side: BorderSide(color: scheme.outlineVariant),
                      ),
                      backgroundColor: scheme.surfaceContainer,
                    ),
                ],
              ),
          ],
          if (_results.isNotEmpty) ...[
            const SizedBox(height: 28),
            Text(
              '搜索结果',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: scheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 12),
            for (final drama in _results)
              Card(
                elevation: 0,
                margin: const EdgeInsets.only(bottom: 8),
                color: scheme.surface,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(AppTheme.radiusCard),
                  side: BorderSide(color: scheme.outlineVariant),
                ),
                child: ListTile(
                  title: Text(drama.title),
                  subtitle: Text(
                    '${drama.episodes} 集'
                    '${drama.category.isEmpty ? '' : ' · ${drama.category}'}',
                  ),
                  trailing: const Icon(Icons.chevron_right_rounded),
                  onTap: () => widget.onOpen(drama),
                ),
              ),
          ],
        ],
      ),
    );
  }
}
