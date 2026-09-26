"""用 Inno Setup 把构建产物打包成 Windows 安装程序。

产物：dist/DramaFetch-x64-<版本号>-setup.exe
"""

import argparse
import os
import re
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
source = upstream / 'build' / 'windows' / 'x64' / 'runner' / 'Release'
output = root / 'dist'

parser = argparse.ArgumentParser()
parser.add_argument('--iscc', type=Path, default=None, help='ISCC.exe 路径，缺省时自动查找')
options = parser.parse_args()


def locate_iscc():
    if options.iscc and Path(options.iscc).is_file():
        return Path(options.iscc)
    candidates = [
        Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Inno Setup 6' / 'ISCC.exe',
        Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Inno Setup 6' / 'ISCC.exe',
    ]
    for path in candidates:
        if path.is_file():
            return path
    found = shutil.which('ISCC') or shutil.which('iscc')
    if found:
        return Path(found)
    raise SystemExit('找不到 Inno Setup 编译器 ISCC.exe，请先安装 Inno Setup 6。')


version = (root / 'version.txt').read_text(encoding='utf-8').strip()
if not version:
    raise SystemExit('version.txt 内容为空。')
# 文件名里不带构建号，只保留 0.0.1 这样的版本号
display = version.split('+')[0]

exe = source / 'dramafetch.exe'
if not exe.is_file():
    raise SystemExit('尚未完成构建，缺少 ' + str(exe))

output.mkdir(parents=True, exist_ok=True)
iscc = locate_iscc()
print('使用编译器：', iscc)
print('应用版本号：', version)

subprocess.run(
    [
        str(iscc),
        f'/DAppVersion={version}',
        f'/DVersionInName={display}',
        f'/DSourceDir={source}',
        f'/DOutputDir={output}',
        str(root / 'installer' / 'dramafetch.iss'),
    ],
    check=True,
)

for artifact in sorted(output.glob('*.exe')):
    print('安装包：', artifact, artifact.stat().st_size, '字节')
