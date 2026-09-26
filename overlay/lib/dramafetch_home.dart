import 'dart:async';

import 'package:flutter/material.dart';

import 'app_layout.dart';
import 'core_bridge.dart';
import 'design/df_design.dart';
import 'dramafetch_update.dart';
import 'local_store.dart';
import 'models.dart';

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
    final palette = DfPalette.of(context);
    final opened = widget.store.recentOpened;
    final typing = _input.text.trim().isNotEmpty;
    final updates = _updates;

    return AnimatedBuilder(
      animation: widget.store,
      builder: (context, _) => LayoutBuilder(
        builder: (context, constraints) => ListView(
          padding: const EdgeInsets.fromLTRB(28, 26, 28, 34),
          children: [
            if (updates != null)
              Padding(
                padding: const EdgeInsets.only(bottom: DfTokens.gapMd),
                child: DramaFetchUpdateBanner(
                  manager: updates,
                  onTap: () {
                    updates.dialogShown = true;
                    showUpdateDialog(context, updates);
                  },
                ),
              ),
            Text('搜索', style: DfText.display(palette)),
            const SizedBox(height: 6),
            Text(
              '输剧名、剧集编号，或直接粘贴播放页链接',
              style: DfText.caption(palette),
            ),
            const SizedBox(height: 20),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 620),
              child: DfSearchField(
                controller: _input,
                focusNode: _focus,
                autofocus: true,
                hintText: '搜索想看的剧',
                onChanged: (value) => setState(() => _onChanged(value)),
                onSubmitted: (value) => unawaited(_submit(value)),
                onClear: () {
                  _input.clear();
                  setState(() => _onChanged(''));
                  _focus.requestFocus();
                },
              ),
            ),
            if (_loading) ...[
              const SizedBox(height: DfTokens.gapMd),
              const DfProgressBar(value: null, height: 3),
            ],
            if (_error != null) ...[
              const SizedBox(height: DfTokens.gapMd),
              DfNotice(
                message: _error!,
                icon: Icons.error_outline_rounded,
                tone: palette.danger,
              ),
            ],
            if (!typing) ...[
              const SizedBox(height: DfTokens.gapXl),
              if (opened.isEmpty)
                DfGlass(
                  padding: const EdgeInsets.symmetric(vertical: DfTokens.gapLg),
                  child: const DfEmptyState(
                    icon: Icons.history_rounded,
                    message: '还没有打开过任何剧',
                    hint: '搜到之后点开，这里会留下记录',
                    compact: true,
                  ),
                )
              else
                DfGlass(
                  padding: const EdgeInsets.all(DfTokens.gapSm),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Padding(
                        padding: const EdgeInsets.fromLTRB(6, 6, 6, 4),
                        child: DfSectionHeader(
                          title: '最近打开',
                          subtitle: '共 ${opened.length} 部',
                          padding: EdgeInsets.zero,
                          trailing: DfGlassButton(
                            label: '清空记录',
                            height: 30,
                            icon: Icons.delete_outline_rounded,
                            onPressed: () =>
                                unawaited(widget.store.clearRecentOpened()),
                          ),
                        ),
                      ),
                      for (final entry in opened)
                        DfListRow(
                          title: (entry['title'] ?? '').isEmpty
                              ? '未命名'
                              : entry['title']!,
                          subtitle: entry['id'],
                          leading: const DfIconBadge(
                            icon: Icons.movie_outlined,
                            size: 34,
                            iconSize: 16,
                          ),
                          trailing: Icon(
                            Icons.chevron_right_rounded,
                            size: 18,
                            color: palette.textTertiary,
                          ),
                          onTap: () => _open(
                            Drama(
                              id: entry['id'] ?? '',
                              source: _sourceID,
                              title: entry['title'] ?? '',
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
            ],
            if (typing && _results.isNotEmpty) ...[
              const SizedBox(height: DfTokens.gapXl),
              DfSectionHeader(
                title: '搜索结果',
                subtitle: '找到 ${_results.length} 部',
              ),
              DfPosterGrid(
                items: _results,
                repository: widget.repository,
                width: constraints.maxWidth,
                onOpen: _open,
              ),
            ],
            if (typing && !_loading && _results.isEmpty && _error == null)
              Padding(
                padding: const EdgeInsets.only(top: 40),
                child: DfEmptyState(
                  icon: Icons.search_off_rounded,
                  message: _submitted.isEmpty
                      ? '没有找到相关的剧'
                      : '没有找到「$_submitted」相关的剧',
                  hint: '换个关键词，或直接粘贴剧集编号与播放页链接',
                ),
              ),
          ],
        ),
      ),
    );
  }
}
