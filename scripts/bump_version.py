"""提升版本号。

上游有更新时由「每日检查上游更新」流程调用，把修订号加一，例如 0.0.1+1 → 0.0.2+2。
主版本与次版本由人工在 version.txt 里维护，脚本只动修订号。

用法：
    python scripts/bump_version.py
"""

import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(encoding='utf-8', errors='replace')

root = Path(__file__).resolve().parents[1]
version_file = root / 'version.txt'


def main():
    raw = version_file.read_text(encoding='utf-8').strip()
    match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:\+(\d+))?', raw)
    if not match:
        raise SystemExit(f'version.txt 格式无法识别：{raw}')

    major, minor, patch = (int(group) for group in match.group(1, 2, 3))
    build = int(match.group(4)) if match.group(4) else patch

    patch += 1
    build += 1
    updated = f'{major}.{minor}.{patch}+{build}'
    version_file.write_text(updated + '\n', encoding='utf-8')
    print('版本号已更新：', raw, '→', updated)
    return updated


if __name__ == '__main__':
    main()
