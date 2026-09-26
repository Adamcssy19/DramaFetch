import 'dart:async';

import 'package:flutter/material.dart';

import 'app_layout.dart';
import 'core_bridge.dart';

/// 下载加速源。前缀留空表示直连 GitHub；其余会把原始地址拼在前缀后面走镜像。
class _Mirror {
  const _Mirror(this.prefix, this.label);
  final String prefix;
  final String label;
}

const _mirrors = <_Mirror>[
  _Mirror('', '直连 GitHub'),
  _Mirror('https://ghfast.top/', 'ghfast.top'),
  _Mirror('https://gh-proxy.com/', 'gh-proxy.com'),
  _Mirror('https://ghproxy.net/', 'ghproxy.net'),
  _Mirror('https://gh.llkk.cc/', 'gh.llkk.cc'),
];

class UpdateScreen extends StatefulWidget {
  const UpdateScreen({super.key, required this.repository});
  final AppRepository repository;

  @override
  State<UpdateScreen> createState() => _UpdateScreenState();
}

class _UpdateScreenState extends State<UpdateScreen> {
  int _mirrorIndex = 0;
  bool _checking = false;
  String? _error;
  Map<String, dynamic>? _info;
  Map<String, dynamic> _progress = const {};
  Timer? _poll;

  String get _mirror => _mirrors[_mirrorIndex].prefix;

  @override
  void initState() {
    super.initState();
    unawaited(_check());
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  Future<void> _check() async {
    if (_checking) return;
    setState(() {
      _checking = true;
      _error = null;
      _info = null;
    });
    try {
      final result = await widget.repository.checkUpdate(mirror: _mirror);
      if (!mounted) return;
      setState(() => _info = result);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  Future<void> _download() async {
    setState(() {
      _error = null;
      _progress = const {'state': 'downloading', 'received': 0, 'total': 0};
    });
    try {
      await widget.repository.downloadUpdate(mirror: _mirror);
      _poll?.cancel();
      _poll = Timer.periodic(const Duration(milliseconds: 800), (_) async {
        try {
          final status = await widget.repository.updateStatus();
          if (!mounted) return;
          setState(() => _progress = status);
          if (status['state'] != 'downloading') _poll?.cancel();
        } catch (_) {
          _poll?.cancel();
        }
      });
    } catch (error) {
      if (mounted) {
        setState(() {
          _progress = const {};
          _error = error.toString();
        });
      }
    }
  }

  Future<void> _launch() async {
    try {
      await widget.repository.launchUpdate();
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('已启动安装程序，按提示完成更新即可')));
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final current = _currentVersion(context);
    final latest = _info?['latest'] as String? ?? '';
    final available = latest.isNotEmpty && _isNewer(latest, current);
    final state = _progress['state'] as String? ?? '';
    final received = (_progress['received'] as num?)?.toDouble() ?? 0;
    final total = (_progress['total'] as num?)?.toDouble() ?? 0;
    final ratio = total > 0 ? (received / total).clamp(0.0, 1.0) : null;

    return Scaffold(
      appBar: AppBar(
        title: const Text('检查更新'),
        actions: [
          TextButton(
            onPressed: _checking ? null : _check,
            child: Text(_checking ? '检查中…' : '重新检查'),
          ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              DropdownButtonFormField<int>(
                initialValue: _mirrorIndex,
                decoration: const InputDecoration(labelText: '下载加速源'),
                items: [
                  for (var i = 0; i < _mirrors.length; i++)
                    DropdownMenuItem(
                      value: i,
                      child: Text(_mirrors[i].label),
                    ),
                ],
                onChanged: _checking
                    ? null
                    : (value) =>
                          setState(() => _mirrorIndex = value ?? 0),
              ),
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text(
                  '直连失败时换一个镜像；检查更新与下载安装包都会使用所选加速源。',
                  style: TextStyle(fontSize: 12),
                ),
              ),
              const SizedBox(height: 24),
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('当前版本'),
                subtitle: Text(current.isEmpty ? '未知' : current),
              ),
              if (_checking) const LinearProgressIndicator(),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text(
                    _error!,
                    style: TextStyle(color: scheme.error),
                  ),
                ),
              if (_info != null && !available)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(Icons.check_circle_outline, color: scheme.primary),
                  title: const Text('已是最新版本'),
                  subtitle: Text('发布页最新为 ${latest.isEmpty ? '未知' : latest}'),
                ),
              if (available) ...[
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(Icons.system_update_alt_rounded, color: scheme.primary),
                  title: Text('发现新版本 $latest'),
                  subtitle: Text(_publishedLabel(_info?['publishedAt'])),
                ),
                if ((_info?['notes'] as String? ?? '').isNotEmpty)
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: scheme.surfaceContainer,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: scheme.outlineVariant),
                    ),
                    child: Text(_info!['notes'] as String),
                  ),
                const SizedBox(height: 20),
                if (state == 'downloading') ...[
                  LinearProgressIndicator(value: ratio),
                  const SizedBox(height: 8),
                  Text(_progressLabel(received, total)),
                ] else if (state == 'done')
                  FilledButton.icon(
                    onPressed: _launch,
                    icon: const Icon(Icons.rocket_launch_outlined),
                    label: const Text('运行安装程序'),
                  )
                else
                  FilledButton.icon(
                    onPressed: _download,
                    icon: const Icon(Icons.download_outlined),
                    label: const Text('下载并安装'),
                  ),
                if (state == 'failed')
                  Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: Text(
                      _progress['error'] as String? ?? '下载失败，请换个加速源重试',
                      style: TextStyle(color: scheme.error),
                    ),
                  ),
                if (state == 'done')
                  Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: Text(
                      '安装包位置：${_progress['path'] ?? ''}',
                      style: const TextStyle(fontSize: 12),
                    ),
                  ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  String _currentVersion(BuildContext context) {
    final raw = AppLayout.versionOf(context);
    return raw.split('+').first;
  }

  String _publishedLabel(Object? value) {
    final text = value is String ? value : '';
    if (text.isEmpty) return '';
    final parsed = DateTime.tryParse(text);
    if (parsed == null) return '发布时间：$text';
    final local = parsed.toLocal();
    return '发布时间：${local.year}-${local.month.toString().padLeft(2, '0')}-'
        '${local.day.toString().padLeft(2, '0')}';
  }

  String _progressLabel(double received, double total) {
    String size(double bytes) {
      if (bytes >= 1048576) return '${(bytes / 1048576).toStringAsFixed(1)} MB';
      if (bytes >= 1024) return '${(bytes / 1024).toStringAsFixed(0)} KB';
      return '${bytes.toInt()} B';
    }

    if (total <= 0) return '已下载 ${size(received)}';
    return '已下载 ${size(received)} / ${size(total)}';
  }
}

/// 比较版本号，只看前三段数字。
bool _isNewer(String latest, String current) {
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
