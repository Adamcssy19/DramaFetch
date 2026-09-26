"""构建 Windows 版应用。

只调用 upstream 目录里的构建步骤，不使用上游的打包脚本 —— 上游那个脚本会按两个版本
产出便携压缩包，本项目只出单一版本的安装程序。

产物目录：upstream/build/windows/x64/runner/Release
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Windows 上的 Python 默认按本地编码输出，直接打印中文会报编码错误
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(encoding='utf-8', errors='replace')

root = Path(__file__).resolve().parents[1]
upstream = root / 'upstream' / 'guoapp'

# 构建产物必须包含的文件，缺任何一个都说明构建不完整
REQUIRED = [
    'dramafetch.exe',
    'duanju_core.dll',
    'flutter_windows.dll',
    'libffmpegkit.dll',
    'libmpv-2.dll',
    'msvcp140.dll',
    'vcruntime140.dll',
    'data/icudtl.dat',
    'data/app.so',
]


def main():
    flutter = shutil.which('flutter')
    if not flutter:
        raise SystemExit('请先把 Flutter SDK 的 bin 目录加入 PATH。')

    environment = os.environ.copy()
    environment.setdefault('GOPROXY', 'https://goproxy.cn,direct')
    environment.setdefault('GOSUMDB', 'off')

    steps = [
        (
            [sys.executable, str(upstream / 'scripts' / 'build_native.py'),
             '--platform', 'windows', '--all-sources'],
            '编译站源核心',
        ),
        ([flutter, 'pub', 'get', '--enforce-lockfile'], '拉取依赖'),
        (
            [flutter, 'build', 'windows', '--release', '--no-pub',
             '--dart-define=ALL_SOURCES=true'],
            '打包应用',
        ),
    ]

    for command, title in steps:
        print('=' * 12, title, '=' * 12, flush=True)
        subprocess.run(command, cwd=upstream, env=environment, check=True)

    bundle = upstream / 'build' / 'windows' / 'x64' / 'runner' / 'Release'
    missing = [name for name in REQUIRED if not (bundle / name).is_file()]
    if missing:
        raise SystemExit('构建产物缺少文件：' + ', '.join(missing))
    print('构建完成：', bundle)


if __name__ == '__main__':
    main()
