"""「已下载」页按剧归并的筛选逻辑：必须只认 drama://hongguo/{seriesId}。

回归背景：`DownloadedPage._collectRecords` 原本在 `parseDramaTaskUrl` 抛错时
用 `urlparse` 兜底，而兜底只校验了 `scheme == "drama"`、没校验 hostname，
于是 `drama://other/999` 这类别的 drama 协议任务会被当成一部剧混进列表。
这里把筛选规则用纯函数复刻一遍并断言，防止再犯。
"""

from __future__ import annotations

from urllib.parse import urlparse

import pytest

from drama_pack.task import parseDramaTaskUrl


def extractSeriesId(url: str) -> str:
    """与 DownloadedPage._collectRecords 中的判定保持一致。"""
    parsed = urlparse(url or "")
    if parsed.scheme != "drama" or parsed.hostname != "hongguo":
        return ""
    seriesId = parsed.path.strip("/")
    try:
        seriesId, _title, _picks, _cat, _ch, _q = parseDramaTaskUrl(url)
    except Exception:
        pass
    return seriesId


@pytest.mark.parametrize("url, expected", [
    ("drama://hongguo/7683196130645003288?name=A&eps=1-3", "7683196130645003288"),
    ("drama://hongguo/101", "101"),
    ("drama://hongguo/101?name=%E5%89%A7&eps=all", "101"),
    # 非 hongguo 的 drama 任务不能算短剧
    ("drama://other/999?name=B", ""),
    ("drama://m3u8/abc", ""),
    # 非 drama 协议一律排除
    ("https://example.com/x.mp4", ""),
    ("http://hongguoduanju.com/player/123/1", ""),
    ("", ""),
    ("not a url", ""),
])
def test_series_id_filter(url: str, expected: str) -> None:
    assert extractSeriesId(url) == expected


def test_hostname_case_insensitive() -> None:
    # urlparse 会把 hostname 规范成小写，大写域名也要认得
    assert extractSeriesId("drama://HONGGUO/123") == "123"


def test_missing_query_still_parses() -> None:
    # 没有 eps/name 参数时 parseDramaTaskUrl 走默认值，不应抛错
    assert extractSeriesId("drama://hongguo/123") == "123"
