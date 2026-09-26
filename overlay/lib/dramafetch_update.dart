import 'dart:async';

import 'package:flutter/material.dart';

import 'app_theme.dart';
import 'core_bridge.dart';

/// 比较版本号，只看前三段数字。
bool isNewerVersion(String latest, String current) {
  List<int> parse(String value) => value
      .split('+')
      .first
      .split('.')
      .map((part) => int.tryParse(part.replaceAll(RegExp(r'[^0-9]'), '')) ?? 0)
      .toList();
  final left = parse(latest);
  final right = parse(current);
  for (var i = 0; i < 3; i++) {
    final a = i < left.length ? left[i] : 0;
    final b = i < right.length ? right[i] : 0;
    if (a != b) return a > b;
  }
  return false;
}

/// 应用内自动更新。
///
/// 检查流程：先并发探测各个加速源的延迟，选最快的一个，再去读最新发布信息。
/// 有新版本时由界面上弹窗提示；用户选择稍后，就改成主界面上的提示条常驻显示。
class DramaFetchUpdateManager extends ChangeNotifier {
  DramaFetchUpdateManager({
    required this.repository,
    required this.currentVersion,
  });

  final AppRepository repository;
  final String currentVersion;

  bool checking = false;
  String mirror = '';
  String mirrorLabel = '直连 GitHub';
  int mirrorDelay = -1;
  String latest = '';
  String notes = '';
  String publishedAt = '';
  String pageUrl = '';
  String error = '';

  /// 用户已经点过「稍后」，改为在界面上常驻提示
  bool postponed = false;
  bool dialogShown = false;

  Map<String, dynamic> progress = const {};
  Timer? _poll;

  bool get hasUpdate =>
      latest.isNotEmpty && isNewerVersion(latest, currentVersion);

  String get downloadState => progress['state'] as String? ?? '';
  double get downloadRatio {
    final received = (progress['received'] as num?)?.toDouble() ?? 0;
    final total = (progress['total'] as num?)?.toDouble() ?? 0;
    if (total <= 0) return 0;
    return (received / total).clamp(0.0, 1.0);
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  /// 启动时调用：先测速选源，再检查版本。
  Future<void> checkAuto() async {
    if (checking) return;
    checking = true;
    error = '';
    notifyListeners();

    try {
      final probes = await repository.probeUpdate();
      final best = probes['best'] as String? ?? '';
      final label = probes['bestLabel'] as String? ?? '直连 GitHub';
      mirror = best;
      mirrorLabel = label;
      mirrorDelay = (probes['bestDelay'] as num?)?.toInt() ?? -1;
    } catch (_) {
      // 测速失败就退回直连，不影响后面的检查
    }

    try {
      final info = await repository.checkUpdate(mirror: mirror);
      latest = info['latest'] as String? ?? '';
      notes = info['notes'] as String? ?? '';
      publishedAt = info['publishedAt'] as String? ?? '';
      pageUrl = info['pageUrl'] as String? ?? '';
    } catch (err) {
      error = err.toString();
    } finally {
      checking = false;
      notifyListeners();
    }
  }

  /// 换一个加速源重新检查。
  Future<void> recheckWith(String nextMirror, String label) async {
    mirror = nextMirror;
    mirrorLabel = label;
    checking = true;
    error = '';
    notifyListeners();
    try {
      final info = await repository.checkUpdate(mirror: mirror);
      latest = info['latest'] as String? ?? '';
      notes = info['notes'] as String? ?? '';
      publishedAt = info['publishedAt'] as String? ?? '';
      pageUrl = info['pageUrl'] as String? ?? '';
    } catch (err) {
      error = err.toString();
    } finally {
      checking = false;
      notifyListeners();
    }
  }

  Future<void> download() async {
    progress = const {'state': 'downloading', 'received': 0, 'total': 0};
    notifyListeners();
    try {
      await repository.downloadUpdate(mirror: mirror);
      _poll?.cancel();
      _poll = Timer.periodic(const Duration(milliseconds: 700), (_) async {
        try {
          final status = await repository.updateStatus();
          progress = status;
          notifyListeners();
          if (status['state'] != 'downloading') _poll?.cancel();
        } catch (_) {
          _poll?.cancel();
        }
      });
    } catch (err) {
      progress = {'state': 'failed', 'error': err.toString()};
      notifyListeners();
    }
  }

  Future<void> launchInstaller() async {
    await repository.launchUpdate();
  }
}

/// 启动时发现新版本弹出的对话框。
Future<void> showUpdateDialog(
  BuildContext context,
  DramaFetchUpdateManager manager,
) async {
  manager.dialogShown = true;
  return showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (dialogContext) => _UpdateDialog(manager: manager),
  );
}

class _UpdateDialog extends StatefulWidget {
  const _UpdateDialog({required this.manager});

  final DramaFetchUpdateManager manager;

  @override
  State<_UpdateDialog> createState() => _UpdateDialogState();
}

class _UpdateDialogState extends State<_UpdateDialog> {
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final manager = widget.manager;
    final state = manager.downloadState;

    return AnimatedBuilder(
      animation: manager,
      builder: (context, _) => AlertDialog(
        titlePadding: const EdgeInsets.fromLTRB(24, 22, 24, 0),
        contentPadding: const EdgeInsets.fromLTRB(24, 14, 24, 8),
        actionsPadding: const EdgeInsets.fromLTRB(16, 4, 16, 14),
        title: Row(
          children: [
            Icon(Icons.system_update_alt_rounded, color: scheme.primary),
            const SizedBox(width: 12),
            Expanded(
              child: Text('发现新版本 ${manager.latest}'),
            ),
          ],
        ),
        content: SizedBox(
          width: 460,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '当前版本 ${manager.currentVersion}'
                '${manager.publishedAt.isEmpty ? '' : ' · 发布于 ${_dateLabel(manager.publishedAt)}'}',
                style: AppTheme.caption(context),
              ),
              const SizedBox(height: 16),
              if (manager.notes.trim().isNotEmpty) ...[
                Theme(
                  data: theme.copyWith(dividerColor: Colors.transparent),
                  child: ExpansionTile(
                    tilePadding: EdgeInsets.zero,
                    childrenPadding: const EdgeInsets.only(bottom: 8),
                    title: Text('更新内容', style: AppTheme.section(context)),
                    children: [
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: scheme.surfaceContainer,
                          borderRadius: BorderRadius.circular(
                            AppTheme.radiusCard,
                          ),
                          border: Border.all(color: scheme.outlineVariant),
                        ),
                        child: MarkdownText(manager.notes.trim()),
                      ),
                    ],
                  ),
                ),
              ],
              if (state == 'downloading') ...[
                const SizedBox(height: 18),
                LinearProgressIndicator(value: manager.downloadRatio),
                const SizedBox(height: 8),
                Text(
                  _progressLabel(manager.progress),
                  style: AppTheme.caption(context),
                ),
              ],
              if (state == 'failed') ...[
                const SizedBox(height: 14),
                Text(
                  manager.progress['error'] as String? ?? '下载失败，请稍后重试',
                  style: TextStyle(color: scheme.error, fontSize: 13),
                ),
              ],
              if (state == 'done') ...[
                const SizedBox(height: 14),
                Text('安装包已下载完成', style: AppTheme.caption(context)),
              ],
            ],
          ),
        ),
        actions: [
          if (state != 'downloading')
            TextButton(
              onPressed: () {
                manager.postponed = true;
                manager.notifyListeners();
                Navigator.of(context).pop();
              },
              child: const Text('稍后'),
            ),
          if (state == 'done')
            FilledButton(
              onPressed: () => unawaited(_launch(context, manager)),
              child: const Text('运行安装程序'),
            )
          else if (state != 'downloading')
            FilledButton(
              onPressed: () => unawaited(manager.download()),
              child: const Text('下载并安装'),
            ),
        ],
      ),
    );
  }

  Future<void> _launch(
    BuildContext context,
    DramaFetchUpdateManager manager,
  ) async {
    await manager.launchInstaller();
    if (!context.mounted) return;
    Navigator.of(context).pop();
  }
}

/// 用户选择稍后时，在主界面顶部常驻的提示条。
class DramaFetchUpdateBanner extends StatelessWidget {
  const DramaFetchUpdateBanner({super.key, required this.manager, this.onTap});

  final DramaFetchUpdateManager manager;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return AnimatedBuilder(
      animation: manager,
      builder: (context, _) {
        if (!manager.hasUpdate || !manager.postponed) {
          return const SizedBox.shrink();
        }
        return Padding(
          padding: const EdgeInsets.only(bottom: 18),
          child: Material(
            color: scheme.primaryContainer.withValues(alpha: 0.45),
            borderRadius: BorderRadius.circular(AppTheme.radiusCard),
            child: InkWell(
              onTap: onTap,
              borderRadius: BorderRadius.circular(AppTheme.radiusCard),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 12,
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.system_update_alt_rounded,
                      size: 18,
                      color: scheme.primary,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        '有新版本 ${manager.latest} 可用',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: scheme.onSurface,
                        ),
                      ),
                    ),
                    Text(
                      '查看更新',
                      style: TextStyle(
                        fontSize: 13,
                        color: scheme.primary,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

String _dateLabel(String value) {
  final parsed = DateTime.tryParse(value);
  if (parsed == null) return value;
  final local = parsed.toLocal();
  return '${local.year}-${local.month.toString().padLeft(2, '0')}-'
      '${local.day.toString().padLeft(2, '0')}';
}

String _progressLabel(Map<String, dynamic> progress) {
  String size(double bytes) {
    if (bytes >= 1048576) return '${(bytes / 1048576).toStringAsFixed(1)} MB';
    if (bytes >= 1024) return '${(bytes / 1024).toStringAsFixed(0)} KB';
    return '${bytes.toInt()} B';
  }

  final received = (progress['received'] as num?)?.toDouble() ?? 0;
  final total = (progress['total'] as num?)?.toDouble() ?? 0;
  final threads = (progress['threads'] as num?)?.toInt() ?? 0;
  final base = total <= 0
      ? '已下载 ${size(received)}'
      : '已下载 ${size(received)} / ${size(total)}';
  return threads > 1 ? '$base · $threads 线程' : base;
}

/// 极简 Markdown 渲染：标题、列表、粗体、行内代码、分隔线。
///
/// 更新说明来自发布页，格式比较固定，自己渲染一份就够了，不必为此引入额外依赖。
class MarkdownText extends StatelessWidget {
  const MarkdownText(this.source, {super.key});

  final String source;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final base = TextStyle(fontSize: 13, height: 1.65, color: scheme.onSurface);
    final rows = <Widget>[];

    for (final raw in source.split('\n')) {
      final line = raw.trimRight();
      if (line.trim().isEmpty) {
        rows.add(const SizedBox(height: 8));
        continue;
      }
      if (RegExp(r'^\s*(-{3,}|\*{3,})\s*$').hasMatch(line)) {
        rows.add(
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Divider(height: 1, color: scheme.outlineVariant),
          ),
        );
        continue;
      }
      final heading = RegExp(r'^(#{1,4})\s+(.*)$').firstMatch(line);
      if (heading != null) {
        final level = heading.group(1)!.length;
        rows.add(
          Padding(
            padding: EdgeInsets.only(
              top: rows.isEmpty ? 0 : 12,
              bottom: 4,
            ),
            child: Text(
              heading.group(2)!.trim(),
              style: base.copyWith(
                fontSize: level <= 2 ? 15 : 14,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        );
        continue;
      }
      final bullet = RegExp(r'^\s*[-*+]\s+(.*)$').firstMatch(line);
      if (bullet != null) {
        rows.add(
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 7, right: 8),
                child: Container(
                  width: 4,
                  height: 4,
                  decoration: BoxDecoration(
                    color: scheme.onSurfaceVariant,
                    shape: BoxShape.circle,
                  ),
                ),
              ),
              Expanded(child: Text.rich(_inline(context, bullet.group(1)!, base))),
            ],
          ),
        );
        continue;
      }
      final numbered = RegExp(r'^\s*(\d+)\.\s+(.*)$').firstMatch(line);
      if (numbered != null) {
        rows.add(
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: 22,
                child: Text(
                  '${numbered.group(1)}.',
                  style: base.copyWith(color: scheme.onSurfaceVariant),
                ),
              ),
              Expanded(
                child: Text.rich(_inline(context, numbered.group(2)!, base)),
              ),
            ],
          ),
        );
        continue;
      }
      rows.add(Text.rich(_inline(context, line.trim(), base)));
    }

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: rows);
  }

  /// 处理行内的 **粗体** 与 `代码`。
  TextSpan _inline(BuildContext context, String text, TextStyle base) {
    final scheme = Theme.of(context).colorScheme;
    final spans = <TextSpan>[];
    final pattern = RegExp(r'\*\*(.+?)\*\*|`(.+?)`');
    var index = 0;
    for (final match in pattern.allMatches(text)) {
      if (match.start > index) {
        spans.add(TextSpan(text: text.substring(index, match.start)));
      }
      final bold = match.group(1);
      final code = match.group(2);
      if (bold != null) {
        spans.add(
          TextSpan(
            text: bold,
            style: base.copyWith(fontWeight: FontWeight.w700),
          ),
        );
      } else if (code != null) {
        spans.add(
          TextSpan(
            text: code,
            style: base.copyWith(
              fontFamily: 'Consolas',
              backgroundColor: scheme.surfaceContainerHighest,
            ),
          ),
        );
      }
      index = match.end;
    }
    if (index < text.length) {
      spans.add(TextSpan(text: text.substring(index)));
    }
    return TextSpan(style: base, children: spans);
  }
}
