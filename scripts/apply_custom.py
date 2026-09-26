"""把本仓库的定制内容应用到主上游目录。

主上游源码在 upstream/guoapp 下以**完整快照**方式存放，每次同步都会被整体替换成上游最新版本，
所以所有定制都必须在本脚本里重新应用一遍，这样「上游更新」与「我们的改动」互不干扰。

定制分两类：
1. overlay/ 下的文件覆盖到 upstream/guoapp 对应路径 —— 适合我们整体重写的文件
2. 对上游文件做定点文本替换 —— 适合只改几行的文件，避免覆盖后丢掉上游更新

用法：
    python scripts/apply_custom.py
"""

import re
import shutil
import sys
from pathlib import Path

# Windows 上的 Python 默认按本地编码输出，直接打印中文会报编码错误
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(encoding='utf-8', errors='replace')

root = Path(__file__).resolve().parents[1]
# 主上游放在 upstream/guoapp，参考用的其它上游放在 upstream/reference，不参与定制与构建
upstream = root / 'upstream' / 'guoapp'
overlay = root / 'overlay'
version_file = root / 'version.txt'

APP_NAME = 'DramaFetch'
APP_SLUG = 'dramafetch'

applied = []
warnings = []
errors = []


def write(path, text):
    path.write_text(text, encoding='utf-8', newline='\n')


def replace_text(relative, old, new, required=True, note='', marker=None, remove=False):
    """在 upstream/guoapp 下的某个文件里做定点替换。

    marker 用来保证幂等：marker 已经出现在文件里，就说明这条改动应用过，直接跳过。
    这一步很关键 —— 同步流程每天都会重新跑本脚本，不幂等就会把同一段内容重复插入。

    remove=True 表示这是一条「删除」改动（new 为空）：找不到待删内容就说明已经删过了，
    直接跳过而不是报错。

    required 为真时，找不到待替换内容会报错终止。
    """
    path = upstream / relative
    if not path.is_file():
        (errors if required else warnings).append(f'{relative} 不存在（{note}）')
        return
    text = path.read_text(encoding='utf-8')
    if marker and marker in text:
        return
    if old not in text:
        if remove:
            return
        message = f'{relative} 里找不到待替换内容（{note}）'
        (errors if required else warnings).append(message)
        return
    write(path, text.replace(old, new, 1))
    applied.append(f'{relative} — {note}')


def apply_project_version():
    """版本号用本项目 version.txt 里的值，不跟随上游。"""
    if not version_file.is_file():
        errors.append('缺少 version.txt')
        return
    version = version_file.read_text(encoding='utf-8').strip()
    if not version:
        errors.append('version.txt 内容为空')
        return
    target = upstream / 'pubspec.yaml'
    text = target.read_text(encoding='utf-8')
    updated, count = re.subn(r'^version:\s*\S+\s*$', f'version: {version}', text, count=1, flags=re.MULTILINE)
    if count != 1:
        errors.append('pubspec.yaml 里找不到版本号')
        return
    if updated != text:
        write(target, updated)
        applied.append(f'pubspec.yaml（版本号设为本项目的 {version}）')

    # 上游把版本号也硬编码在界面用的常量里，一并同步，
    # 否则应用内「检查更新」会拿上游的版本号去和发布页比较。
    layout = upstream / 'lib' / 'app_layout.dart'
    if layout.is_file():
        layout_text = layout.read_text(encoding='utf-8')
        layout_updated, layout_count = re.subn(
            r"^const appVersion = '[^']*';\s*$",
            f"const appVersion = '{version}';",
            layout_text,
            count=1,
            flags=re.MULTILINE,
        )
        if layout_count == 1:
            if layout_updated != layout_text:
                write(layout, layout_updated)
                applied.append(f'app_layout.dart（版本号同步为 {version}）')
        else:
            warnings.append('app_layout.dart 里找不到 appVersion 常量，界面可能显示错误的当前版本')

    return version


def main():
    if not upstream.is_dir():
        raise SystemExit('缺少 upstream/guoapp 目录')

    # ---- 1. 覆盖文件 ----
    for source in sorted(overlay.rglob('*')):
        if not source.is_file():
            continue
        target = upstream / source.relative_to(overlay)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        applied.append(f'{source.relative_to(overlay)}（覆盖）')

    # ---- 2. 清理不需要的上游内容 ----
    # 上游自己的工作流：放在子目录不会被 GitHub 执行，删掉以免混淆
    upstream_workflows = upstream / '.github'
    if upstream_workflows.exists():
        shutil.rmtree(upstream_workflows)
        applied.append('.github（移除上游工作流）')

    # ---- 3. 定点替换 ----
    replace_text(
        'windows/CMakeLists.txt',
        'set(BINARY_NAME "zhenguojian")',
        f'set(BINARY_NAME "{APP_SLUG}")',
        marker=f'set(BINARY_NAME "{APP_SLUG}")',
        note='可执行文件名',
    )

    for key in ('CompanyName', 'ProductName'):
        replace_text(
            'windows/runner/Runner.rc',
            f'VALUE "{key}", "真果鉴"',
            f'VALUE "{key}", "{APP_NAME}"',
            marker=f'VALUE "{key}", "{APP_NAME}"',
            note=f'{key} 显示名',
        )

    # 版本信息里的版权署名
    replace_text(
        'windows/runner/Runner.rc',
        'Copyright (C) 2026 com.duanju. All rights reserved.',
        f'Copyright (C) 2026 {APP_NAME}. All rights reserved.',
        required=False,
        marker=f'Copyright (C) 2026 {APP_NAME}',
        note='版权署名',
    )

    # 关于对话框里的图标换成项目图标
    replace_text(
        'lib/home_screen.dart',
        """                        applicationIcon: const Icon(
                          Icons.play_circle_filled_rounded,
                          size: 48,
                          color: Color(0xFFFF765F),
                        ),""",
        """                        applicationIcon: const SizedBox(
                          width: 48,
                          height: 48,
                          child: Image(image: AssetImage('assets/logo.png')),
                        ),""",
        required=False,
        marker="AssetImage('assets/logo.png')",
        note='关于对话框图标',
    )

    # 把图标注册进应用资源
    replace_text(
        'pubspec.yaml',
        '  assets:\n    - assets/video_enhancement/\n',
        '  assets:\n    - assets/logo.png\n    - assets/video_enhancement/\n',
        marker='- assets/logo.png',
        note='图标资源注册',
    )

    # ---- 多方式下载：让用户指定红果的取流方式 ----
    # 实现放在新增的 native/core/dramafetch_direct.go，设置项复用「网络与资源」页。

    replace_text(
        'native/core/app_settings.go',
        '\tDownloadBySource    bool   `json:"downloadBySource"`\n',
        '\tDownloadBySource    bool   `json:"downloadBySource"`\n'
        '\tDownloadMethod      string `json:"downloadMethod"`\n',
        marker='`json:"downloadMethod"`',
        note='设置结构增加下载方式',
    )

    replace_text(
        'native/core/app_settings.go',
        '\t\tengine.downloads.scheduleLocked()\n'
        '\t\tengine.downloads.mu.Unlock()\n'
        '\t}\n'
        '}\n',
        '\t\tengine.downloads.scheduleLocked()\n'
        '\t\tengine.downloads.mu.Unlock()\n'
        '\t}\n'
        '\t// 下载方式：本项目新增，用户在「网络与资源」里指定红果取流方式\n'
        '\tactiveDownloadMethod = normalizeDownloadMethod(settings.DownloadMethod)\n'
        '}\n',
        marker='activeDownloadMethod = normalizeDownloadMethod',
        note='设置生效时应用下载方式',
    )

    replace_text(
        'lib/resource_settings_screen.dart',
        "import 'core_bridge.dart';\n",
        "import 'core_bridge.dart';\nimport 'download_methods.dart';\n",
        required=False,
        marker="import 'download_methods.dart';",
        note='引入下载方式清单',
    )
    replace_text(
        'lib/resource_settings_screen.dart',
        "  String _mode = 'auto';\n  int _catalog",
        "  String _mode = 'auto';\n  String _method = 'auto';\n  int _catalog",
        marker="String _method = 'auto';",
        note='下载方式状态',
    )
    replace_text(
        'lib/resource_settings_screen.dart',
        '        _mode = settings.proxyMode;\n',
        '        _mode = settings.proxyMode;\n        _method = settings.downloadMethod;\n',
        marker='_method = settings.downloadMethod;',
        note='读取下载方式',
    )
    replace_text(
        'lib/resource_settings_screen.dart',
        '          downloadBySource: _folders,\n',
        '          downloadBySource: _folders,\n          downloadMethod: _method,\n',
        marker='downloadMethod: _method,',
        note='保存下载方式',
    )
    replace_text(
        'lib/resource_settings_screen.dart',
        "                  _count('同时下载数量', _downloads, (value) => _downloads = value),\n",
        "                  _count('同时下载数量', _downloads, (value) => _downloads = value),\n"
        "                  const SizedBox(height: 16),\n"
        "                  DropdownButtonFormField<String>(\n"
        "                    initialValue: _method,\n"
        "                    decoration: const InputDecoration(labelText: '红果下载方式'),\n"
        "                    items: [\n"
        "                      for (final option in downloadMethodOptions)\n"
        "                        DropdownMenuItem(\n"
        "                          value: option.id,\n"
        "                          child: Text(option.name),\n"
        "                        ),\n"
        "                    ],\n"
        "                    onChanged: _busy\n"
        "                        ? null\n"
        "                        : (value) => setState(() => _method = value ?? 'auto'),\n"
        "                  ),\n"
        "                  Padding(\n"
        "                    padding: const EdgeInsets.only(top: 8),\n"
        "                    child: Text(\n"
        "                      downloadMethodOf(_method).detail,\n"
        "                      style: TextStyle(\n"
        "                        color: Theme.of(context).colorScheme.onSurfaceVariant,\n"
        "                        fontSize: 12,\n"
        "                      ),\n"
        "                    ),\n"
        "                  ),\n",
        marker="labelText: '红果下载方式'",
        note='下载方式选项',
    )

    # 红果取流入口接入：指定方式时由本项目实现接管，自动模式保持上游逻辑
    replace_text(
        'native/core/provider_hongguo.go',
        'func (d *Downloader) resolveHongguoMedia(ctx context.Context, task Task) (providerMedia, error) {\n'
        '\tsource, seriesID, ok := splitProviderDramaID(task.DramaID)\n',
        'func (d *Downloader) resolveHongguoMedia(ctx context.Context, task Task) (providerMedia, error) {\n'
        '\t// 用户指定了取流方式时，交由本项目的实现处理\n'
        '\tif media, handled, err := d.resolveDramaFetchMedia(ctx, task); handled {\n'
        '\t\treturn media, err\n'
        '\t}\n'
        '\tsource, seriesID, ok := splitProviderDramaID(task.DramaID)\n',
        marker='resolveDramaFetchMedia(ctx, task); handled',
        note='红果取流接入多方式',
    )

    # ---- 下载目录与文件命名 ----

    # 默认下载目录放到系统下载文件夹下的 DramaFetch 目录，方便直接找到
    replace_text(
        'native/core/app_storage.go',
        '\tif json.Unmarshal(body, &value) == nil && filepath.IsAbs(value.Directory) {\n'
        '\t\treturn filepath.Clean(value.Directory)\n'
        '\t}\n'
        '\treturn filepath.Join(directory, "downloads")\n',
        '\tif json.Unmarshal(body, &value) == nil && filepath.IsAbs(value.Directory) {\n'
        '\t\treturn filepath.Clean(value.Directory)\n'
        '\t}\n'
        '\t// 默认放在系统下载文件夹下的 DramaFetch 目录，方便直接找到\n'
        '\tif home, err := os.UserHomeDir(); err == nil && home != "" {\n'
        '\t\treturn filepath.Join(home, "Downloads", "DramaFetch")\n'
        '\t}\n'
        '\treturn filepath.Join(directory, "downloads")\n',
        marker='"Downloads", "DramaFetch"',
        note='默认下载目录',
    )

    # 按剧名归档
    replace_text(
        'native/core/app_download_collections.go',
        'func (manager *nativeDownloads) jobDirectory(job nativeDownloadJob) string {\n'
        '\tif job.Folder != "" {\n',
        'func (manager *nativeDownloads) jobDirectory(job nativeDownloadJob) string {\n'
        '\t// 本项目改造：按剧名归档，下载目录里直接可读\n'
        '\tif name := nativeDownloadFolderName(job); name != "" {\n'
        '\t\treturn filepath.Join(manager.root, name)\n'
        '\t}\n'
        '\tif job.Folder != "" {\n',
        marker='nativeDownloadFolderName(job)',
        note='按剧名归档',
    )

    # 视频文件名用「剧名 集号」
    replace_text(
        'native/core/app_download_transfer.go',
        '\tentry := "media.mp4"\n',
        '\tentry := nativeDownloadFileName(job)\n',
        marker='entry := nativeDownloadFileName(job)',
        note='视频文件命名',
    )

    # ---- 首页与导航 ----

    replace_text(
        'lib/home_screen.dart',
        "import 'local_store.dart';\n",
        "import 'dramafetch_home.dart';\nimport 'local_store.dart';\n",
        required=False,
        marker="import 'dramafetch_home.dart';",
        note='引入新首页',
    )

    # 桌面导航：第一项改成搜索，去掉追剧
    replace_text(
        'lib/home_screen.dart',
        '                    destinations: [\n'
        '                      NavigationRailDestination(\n'
        '                        icon: Icon(Icons.explore_outlined),\n'
        '                        selectedIcon: Icon(Icons.explore),\n'
        "                        label: Text('发现'),\n"
        '                      ),\n'
        '                      NavigationRailDestination(\n'
        '                        icon: Icon(Icons.bookmark_border_rounded),\n'
        '                        selectedIcon: Icon(Icons.bookmark_rounded),\n'
        "                        label: Text('追剧'),\n"
        '                      ),\n',
        '                    destinations: [\n'
        '                      NavigationRailDestination(\n'
        '                        icon: Icon(Icons.search_outlined),\n'
        '                        selectedIcon: Icon(Icons.search),\n'
        "                        label: Text('搜索'),\n"
        '                      ),\n',
        marker="label: Text('搜索'),",
        note='导航去掉追剧',
    )

    # 首页内容换成搜索页；下载页索引随之前移
    replace_text(
        'lib/home_screen.dart',
        '                  child: _tab == 0\n'
        '                      ? widget.store.sources.isEmpty\n'
        '                            ? const StatusPanel(\n'
        "                                title: '暂无可用站源',\n"
        "                                message: '请联系管理员为当前用户开放站源。',\n"
        '                              )\n'
        '                            : _catalog(selectionInBody: desktop || television)\n'
        '                      : _tab == 3\n',
        '                  child: _tab == 0\n'
        '                      ? DramaFetchHome(\n'
        '                          repository: widget.repository,\n'
        '                          store: widget.store,\n'
        '                          onOpen: _openDrama,\n'
        '                        )\n'
        '                      : _tab == 2\n',
        marker='DramaFetchHome(',
        note='首页换成搜索页',
    )

    # 删掉用户管理入口（本项目不做多用户）
    replace_text(
        'lib/settings_screen.dart',
        '              ListTile(\n'
        '                leading: const Icon(Icons.people_outline),\n'
        "                title: const Text('用户管理'),\n"
        "                subtitle: Text('当前：${widget.store.profile.name}'),\n"
        '                onTap: () => Navigator.push(\n'
        '                  context,\n'
        '                  MaterialPageRoute<void>(\n'
        '                    builder: (_) => ProfilesScreen(store: widget.store),\n'
        '                  ),\n'
        '                ),\n'
        '              ),\n',
        '',
        remove=True,
        note='去掉用户管理入口',
    )

    # 删掉 Emby 导出相关开关（本项目不导出媒体库元数据）
    replace_text(
        'lib/settings_screen.dart',
        '                SwitchListTile(\n'
        '                  value: widget.store.autoExport,\n'
        "                  title: const Text('下载完成后自动导出 Emby'),\n"
        '                  subtitle: const Text(\n'
        "                    '在下载目录的 exports 中生成视频和海报 URL 元数据，可将该目录加入 Emby 媒体库。',\n"
        '                  ),\n'
        '                  onChanged: _busy\n'
        '                      ? null\n'
        '                      : (value) async {\n'
        '                          try {\n'
        '                            if (value) {\n'
        '                              await BackgroundDownloads.ensureStarted();\n'
        '                            }\n'
        '                            await widget.store.setAutoExport(value);\n'
        '                          } catch (error) {\n'
        '                            if (mounted) {\n'
        '                              setState(() => _message = error.toString());\n'
        '                            }\n'
        '                          }\n'
        '                        },\n'
        '                ),\n'
        '                SwitchListTile(\n'
        '                  value: widget.store.exportPosters,\n'
        "                  title: const Text('同时导出海报文件'),\n"
        "                  subtitle: const Text('默认只写海报 URL。源站海报需要解密或外部读取失败时可开启。'),\n"
        '                  onChanged: _busy\n'
        '                      ? null\n'
        '                      : (value) => saveUserChange(\n'
        '                          context,\n'
        '                          () => widget.store.setExportPosters(value),\n'
        '                        ),\n'
        '                ),\n',
        '',
        remove=True,
        note='去掉 Emby 导出开关',
    )

    # 提示文案里不再提合并与 Emby
    replace_text(
        'lib/settings_screen.dart',
        "const Text('在下载页删除不需要的分集，在本地媒体页删除合并成品或 Emby 导出，可释放空间。'),",
        "const Text('在下载页删除不需要的分集可以释放空间。'),",
        marker='在下载页删除不需要的分集可以释放空间',
        note='精简存储提示文案',
    )

    # 去掉下载页的「本地媒体与合并」入口
    replace_text(
        'lib/downloads_screen.dart',
        '      IconButton(\n'
        "        key: const ValueKey('download-local-media'),\n"
        "        tooltip: '本地媒体与合并',\n"
        '        onPressed: () => Navigator.push(\n'
        '          context,\n'
        '          MaterialPageRoute<void>(\n'
        '            builder: (_) => LocalMediaScreen(\n'
        '              repository: widget.repository,\n'
        '              store: widget.store,\n'
        '            ),\n'
        '          ),\n'
        '        ),\n'
        '        icon: const Icon(Icons.video_library_outlined),\n'
        '      ),\n',
        '',
        remove=True,
        note='去掉本地媒体与合并入口',
    )

    # 侧边栏固定四项：搜索 / 榜单 / 下载 / 设置
    replace_text(
        'lib/home_screen.dart',
        '                    destinations: [\n'
        '                      NavigationRailDestination(\n'
        '                        icon: Icon(Icons.search_outlined),\n'
        '                        selectedIcon: Icon(Icons.search),\n'
        "                        label: Text('搜索'),\n"
        '                      ),\n'
        '                      NavigationRailDestination(\n'
        '                        icon: Icon(Icons.history_rounded),\n'
        "                        label: Text('最近观看'),\n"
        '                      ),\n'
        '                      if (widget.store.canDownload)\n'
        '                        NavigationRailDestination(\n'
        '                          icon: Icon(Icons.download_outlined),\n'
        '                          selectedIcon: Icon(Icons.download_rounded),\n'
        "                          label: Text('下载'),\n"
        '                        ),\n'
        '                    ],\n',
        '                    destinations: [\n'
        '                      NavigationRailDestination(\n'
        '                        icon: Icon(Icons.search_outlined),\n'
        '                        selectedIcon: Icon(Icons.search),\n'
        "                        label: Text('搜索'),\n"
        '                      ),\n'
        '                      NavigationRailDestination(\n'
        '                        icon: Icon(Icons.leaderboard_outlined),\n'
        '                        selectedIcon: Icon(Icons.leaderboard_rounded),\n'
        "                        label: Text('榜单'),\n"
        '                      ),\n'
        '                      NavigationRailDestination(\n'
        '                        icon: Icon(Icons.download_outlined),\n'
        '                        selectedIcon: Icon(Icons.download_rounded),\n'
        "                        label: Text('下载'),\n"
        '                      ),\n'
        '                      NavigationRailDestination(\n'
        '                        icon: Icon(Icons.settings_outlined),\n'
        '                        selectedIcon: Icon(Icons.settings_rounded),\n'
        "                        label: Text('设置'),\n"
        '                      ),\n'
        '                    ],\n',
        marker="label: Text('榜单'),",
        note='侧边栏四项',
    )

    # 页面内容按新的四项索引切换
    replace_text(
        'lib/home_screen.dart',
        '                      : _tab == 2\n'
        '                      ? DownloadsScreen(\n'
        '                          repository: widget.repository,\n'
        '                          store: widget.store,\n'
        '                          embedded: true,\n'
        '                        )\n'
        '                      : SavedLibrary(\n'
        "                          key: ValueKey('saved-tab-$_tab'),\n"
        '                          repository: widget.repository,\n'
        '                          store: widget.store,\n'
        '                          history: true,\n'
        '                          onOpen: _openDrama,\n'
        '                          onContinue: (drama) =>\n'
        '                              _openDrama(drama, resume: true),\n'
        '                          onDownload:\n'
        '                              widget.repository.supportsDownloads &&\n'
        '                                  widget.store.canDownload\n'
        '                              ? (drama) => _openDrama(drama, download: true)\n'
        '                              : null,\n'
        '                        ),\n',
        '                      : _tab == 1\n'
        '                      ? RankingsScreen(\n'
        '                          repository: widget.repository,\n'
        '                          store: widget.store,\n'
        '                          initialGroup: widget.store.sources.isEmpty\n'
        "                              ? ''\n"
        '                              : widget.store.sources.first.id,\n'
        '                        )\n'
        '                      : _tab == 2\n'
        '                      ? DownloadsScreen(\n'
        '                          repository: widget.repository,\n'
        '                          store: widget.store,\n'
        '                          embedded: true,\n'
        '                        )\n'
        '                      : SettingsScreen(\n'
        '                          repository: widget.repository,\n'
        '                          store: widget.store,\n'
        '                        ),\n',
        marker='initialGroup: widget.store.sources.isEmpty',
        note='页面切换四项',
    )

    # ---- 自动更新：注册更新动作 ----
    replace_text(
        'native/core/app_runtime.go',
        '\tswitch input.Action {\n\tcase "lan":\n',
        '\tswitch input.Action {\n'
        '\tcase "update":\n'
        '\t\treturn engine.nativeUpdate(ctx, input)\n'
        '\tcase "lan":\n',
        marker='return engine.nativeUpdate(ctx, input)',
        note='注册更新动作',
    )

    # 仓库接口：抽象定义
    replace_text(
        'lib/core_bridge.dart',
        '  Future<ResourceSettings> resourceSettings() async => const ResourceSettings();\n',
        '  Future<ResourceSettings> resourceSettings() async => const ResourceSettings();\n'
        '  Future<Map<String, dynamic>> checkUpdate({String mirror = \'\'}) async =>\n'
        "      throw AppFailure('当前环境不支持检查更新');\n"
        '  Future<Map<String, dynamic>> downloadUpdate({String mirror = \'\'}) async =>\n'
        "      throw AppFailure('当前环境不支持下载更新');\n"
        '  Future<Map<String, dynamic>> updateStatus() async => const {};\n'
        '  Future<Map<String, dynamic>> launchUpdate() async =>\n'
        "      throw AppFailure('当前环境不支持启动安装程序');\n",
        marker='Future<Map<String, dynamic>> checkUpdate(',
        note='仓库接口增加更新方法',
    )

    # 仓库接口：本地核心实现
    replace_text(
        'lib/core_bridge.dart',
        '  Future<ResourceSettings> resourceSettings() async {\n'
        '    _adminPermission();\n'
        '    return ResourceSettings.fromJson(\n'
        "      await _call({'action': 'resourceSettings'}),\n"
        '    );\n'
        '  }\n',
        '  Future<ResourceSettings> resourceSettings() async {\n'
        '    _adminPermission();\n'
        '    return ResourceSettings.fromJson(\n'
        "      await _call({'action': 'resourceSettings'}),\n"
        '    );\n'
        '  }\n'
        '\n'
        '  @override\n'
        "  Future<Map<String, dynamic>> checkUpdate({String mirror = ''}) async {\n"
        '    _adminPermission();\n'
        "    return _call({'action': 'update', 'command': 'check', 'query': mirror});\n"
        '  }\n'
        '\n'
        '  @override\n'
        "  Future<Map<String, dynamic>> downloadUpdate({String mirror = ''}) async {\n"
        '    _adminPermission();\n'
        "    return _call({'action': 'update', 'command': 'download', 'query': mirror});\n"
        '  }\n'
        '\n'
        '  @override\n'
        '  Future<Map<String, dynamic>> updateStatus() async {\n'
        '    _adminPermission();\n'
        "    return _call({'action': 'update', 'command': 'status'});\n"
        '  }\n'
        '\n'
        '  @override\n'
        '  Future<Map<String, dynamic>> launchUpdate() async {\n'
        '    _adminPermission();\n'
        "    return _call({'action': 'update', 'command': 'launch'});\n"
        '  }\n',
        marker="'command': 'download'",
        note='本地核心实现更新方法',
    )

    # 设置页加入检查更新入口
    replace_text(
        'lib/settings_screen.dart',
        "import 'local_store.dart';\n",
        "import 'local_store.dart';\nimport 'update_screen.dart';\n",
        required=False,
        marker="import 'update_screen.dart';",
        note='引入更新页面',
    )
    replace_text(
        'lib/settings_screen.dart',
        '              if (widget.store.canDownload)\n'
        '                ListTile(\n'
        '                  leading: const Icon(Icons.download_outlined),\n',
        '              ListTile(\n'
        '                leading: const Icon(Icons.system_update_alt_rounded),\n'
        "                title: const Text('检查更新'),\n"
        "                subtitle: const Text('获取新版本，可切换加速源'),\n"
        '                trailing: const Icon(Icons.chevron_right_rounded),\n'
        '                onTap: () => Navigator.push(\n'
        '                  context,\n'
        '                  MaterialPageRoute<void>(\n'
        '                    builder: (_) =>\n'
        '                        UpdateScreen(repository: widget.repository),\n'
        '                  ),\n'
        '                ),\n'
        '              ),\n'
        '              if (widget.store.canDownload)\n'
        '                ListTile(\n'
        '                  leading: const Icon(Icons.download_outlined),\n',
        marker='UpdateScreen(repository: widget.repository)',
        note='设置页更新入口',
    )

    # ---- 4. 版本号按本项目设置 ----
    version = apply_project_version()

    print('已应用 %d 项定制' % len(applied))
    if version:
        print('本项目版本号：', version)

    for item in warnings:
        print('::warning::' + item)
    if errors:
        for item in errors:
            print('::error::' + item)
        sys.exit(1)
    print('定制应用完成')


if __name__ == '__main__':
    main()
