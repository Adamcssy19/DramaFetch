"""拉取主上游源码到 upstream/ 目录。

本仓库不保存上游源码，构建前用这个脚本现拉：下载上游 main 分支的源码压缩包并解压。
解压结果不入库（.gitignore 已忽略 upstream/）。

用法：
    python scripts/fetch_upstream.py
"""

import io
import json
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

# Windows 上的 Python 默认按本地编码输出，直接打印中文会报编码错误
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(encoding='utf-8', errors='replace')

UPSTREAM_REPO = 'x315600/guoapp'
UPSTREAM_ARCHIVE = f'https://codeload.github.com/{UPSTREAM_REPO}/tar.gz/refs/heads/main'
UPSTREAM_COMMIT_API = f'https://api.github.com/repos/{UPSTREAM_REPO}/commits/main'

root = Path(__file__).resolve().parents[1]
target = root / 'upstream' / 'guoapp'


def latest_commit():
    """查询上游 main 分支的最新提交。查询失败不算错误，只用于日志。"""
    try:
        request = urllib.request.Request(
            UPSTREAM_COMMIT_API,
            headers={
                'User-Agent': 'DramaFetch-Build',
                'Accept': 'application/vnd.github+json',
            },
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read()).get('sha', '')
    except Exception as error:  # noqa: BLE001
        print('未能查询上游提交号：', error)
        return ''


def main():
    print(f'正在拉取上游源码：{UPSTREAM_REPO}')
    request = urllib.request.Request(
        UPSTREAM_ARCHIVE,
        headers={'User-Agent': 'DramaFetch-Build'},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        payload = response.read()
    print('已下载 %.1f MB' % (len(payload) / 1048576))

    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as archive:
        members = archive.getmembers()
        if not members:
            raise SystemExit('上游压缩包为空')

        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        for member in members:
            # 去掉压缩包自带的顶层目录，例如 guoapp-main/
            parts = member.name.split('/', 1)
            if len(parts) < 2 or not parts[1]:
                continue
            member.name = parts[1]
            archive.extract(member, target, filter='data')

    print('源码目录：', target)
    print('文件数：', sum(1 for item in target.rglob('*') if item.is_file()))
    commit = latest_commit()
    if commit:
        print('上游提交：', commit)
    return commit


if __name__ == '__main__':
    main()
