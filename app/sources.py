from __future__ import annotations

import asyncio
from asyncio.staggered import staggered_race
from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Callable
from typing import Any

from loguru import logger

from app.client import buildClient, fetchFile
from app.models.task import TaskError


@dataclass(frozen=True)
class Repo:
    name: str
    mirrors: dict[str, str] = field(default_factory=dict)

    def nameOn(self, source: str) -> str | None:
        if source == "github":
            return self.name
        return self.mirrors.get(source)

    def buildSources(self) -> list[str]:
        return [s for s in SOURCE_ORDER if self.nameOn(s) is not None]


@dataclass(frozen=True)
class SourceEndpoints:
    api: str
    download: str
    raw: str
    rawInfix: str


SOURCES = {
    "gitcode": SourceEndpoints(
        api="https://api.gitcode.com/api/v5/repos",
        download="https://gitcode.com",
        raw="https://cnb.cool",
        rawInfix="/-/git/raw/",
    ),
    "github": SourceEndpoints(
        api="https://api.github.com/repos",
        download="https://github.com",
        raw="https://raw.githubusercontent.com",
        rawInfix="/",
    ),
}

SOURCE_ORDER = ("github", "gitcode")
STAGGER_DELAY = 0.05


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    size: int
    downloadCount: int
    downloadUrl: str


@dataclass(frozen=True)
class Release:
    version: str
    publishedAt: str
    body: str
    pageUrl: str
    prerelease: bool
    assets: list[ReleaseAsset]

    @classmethod
    def fromResponse(cls, data: dict[str, Any]) -> Release:
        version = ""
        for key in ("tag_name", "name"):
            value = str(data.get(key) or "").strip()
            if value:
                version = value
                break

        assets = [
            ReleaseAsset(
                name=a.get("name", ""),
                size=a.get("size", 0),
                downloadCount=a.get("download_count", 0),
                downloadUrl=a.get("browser_download_url", ""),
            )
            for a in data.get("assets", [])
        ]

        return cls(
            version=version or "Unknown",
            publishedAt=data.get("published_at", "") or data.get("created_at", ""),
            body=data.get("body", "") or "",
            pageUrl=data.get("html_url", ""),
            prerelease=data.get("prerelease", False),
            assets=assets,
        )


async def fetchLatestRelease(repo: Repo) -> Release:
    from app.update import parseVersion

    async def attempt(source):
        endpoints = SOURCES[source]
        url = f"{endpoints.api}/{repo.nameOn(source)}/releases/latest"
        headers = {"accept": "application/vnd.github+json"} if source == "github" else {}
        client = buildClient(headers=headers, timeout=15)
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = await resp.json()
            return Release.fromResponse(data)
        except Exception as e:
            logger.debug("从 {} 获取 {} release 失败: {}", source, repo.name, repr(e))
            raise
        finally:
            client.close()

    sources = repo.buildSources()
    results = await asyncio.gather(
        *[attempt(s) for s in sources], return_exceptions=True)
    chosen: Release | None = None
    for result in results:
        if isinstance(result, BaseException):
            continue
        if chosen is None:
            chosen = result
            continue
        if parseVersion(result.version) > parseVersion(chosen.version):
            chosen = result
    if chosen is None:
        raise TaskError("无法获取 {name} 的最新 release", name=repo.name)
    return chosen



async def fetchJson(repo: Repo, branch: str, path: str) -> tuple[dict, str]:
    async def attempt(source):
        endpoints = SOURCES[source]
        url = f"{endpoints.raw}/{repo.nameOn(source)}{endpoints.rawInfix}{branch}/{path}"
        client = buildClient(timeout=15)
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            result = await resp.json()
            return result, source
        except Exception as e:
            logger.debug("从 {} 获取 {}/{} 失败: {}", source, repo.name, path, repr(e))
            raise
        finally:
            client.close()

    result, index, _ = await staggered_race(
        [lambda s=s: attempt(s) for s in repo.buildSources()], STAGGER_DELAY)
    if index is not None:
        return result
    raise TaskError("无法获取 {name}/{branch}/{path}", name=repo.name, branch=branch, path=path)


async def fetchRawFile(
    repo: Repo, branch: str, path: str, outputPath: Path,
    onProgress: Callable[[float], None] | None = None,
) -> str:
    async def probe(source):
        endpoints = SOURCES[source]
        url = f"{endpoints.raw}/{repo.nameOn(source)}{endpoints.rawInfix}{branch}/{path}"
        client = buildClient(headers={"Range": "bytes=0-0"}, timeout=10)
        try:
            resp = await client.get(url)
            try:
                resp.raise_for_status()
                return url, source
            finally:
                resp.close()
        except Exception as e:
            logger.debug("从 {} 下载 {}/{} 失败: {}", source, repo.name, path, repr(e))
            raise
        finally:
            client.close()

    result, index, _ = await staggered_race(
        [lambda s=s: probe(s) for s in repo.buildSources()], STAGGER_DELAY)
    if index is None:
        raise TaskError("无法下载 {name}/{branch}/{path}", name=repo.name, branch=branch, path=path)
    url, source = result
    await fetchFile(url, outputPath, onProgress=onProgress)
    return source


async def probeDownloadUrl(repo: Repo, tag: str, asset: str) -> str:
    async def probe(source):
        url = buildDownloadUrl(repo, tag, asset, source=source)
        client = buildClient(headers={"Range": "bytes=0-0"}, timeout=10)
        try:
            resp = await client.get(url)
            try:
                resp.raise_for_status()
                return url
            finally:
                resp.close()
        except Exception as e:
            logger.debug("从 {} 下载 {}/{} 失败: {}", source, repo.name, asset, repr(e))
            raise
        finally:
            client.close()

    result, index, _ = await staggered_race(
        [lambda s=s: probe(s) for s in repo.buildSources()], STAGGER_DELAY)
    if index is None:
        raise TaskError("无法下载 {name}/{tag}/{asset}", name=repo.name, tag=tag, asset=asset)
    return result


# ── GitHub 加速镜像：对 release 资产直链做前缀代理 ──

MIRROR_PREFIXES: dict[str, str] = {
    "github": "",                          # 官方直连
    "ghfast": "https://ghfast.top/",
    "gh-proxy": "https://gh-proxy.com/",
    "moeyy": "https://github.moeyy.xyz/",
    "llkk": "https://gh.llkk.cc/",
}
MIRROR_LABELS: dict[str, str] = {
    "auto": "自动测速",
    "github": "GitHub 直连",
    "ghfast": "ghfast.top",
    "gh-proxy": "gh-proxy.com",
    "moeyy": "github.moeyy.xyz",
    "llkk": "gh.llkk.cc",
}

# 模块级偏好与最近一次测速结果（供 UI 展示与手动换源）
preferredMirror: str = "auto"
mirrorLatencies: dict[str, float] = {}


def setPreferredMirror(name: str) -> None:
    global preferredMirror
    preferredMirror = name if name in MIRROR_PREFIXES else "auto"


def buildAssetUrlCandidates(repo: Repo, tag: str, asset: str) -> list[tuple[str, str]]:
    direct = f"https://github.com/{repo.name}/releases/download/{tag}/{asset}"
    return [(name, f"{prefix}{direct}" if prefix else direct)
            for name, prefix in MIRROR_PREFIXES.items()]


async def probeMirrorUrl(url: str, timeout: float = 6.0) -> float | None:
    """HEAD 式探测（Range 0-0），返回耗时秒数；失败返回 None。"""
    import time
    start = time.perf_counter()
    client = buildClient(headers={"Range": "bytes=0-0"}, timeout=int(timeout))
    try:
        resp = await client.get(url)
        try:
            resp.raise_for_status()
            return time.perf_counter() - start
        finally:
            resp.close()
    except Exception as e:
        logger.debug("镜像测速失败 {}: {}", url, repr(e))
        return None
    finally:
        client.close()


async def probeDownloadUrl(repo: Repo, tag: str, asset: str) -> str:
    """在直连与各加速镜像中探测资产可用性，自动选择延迟最低的源。"""
    candidates = buildAssetUrlCandidates(repo, tag, asset)

    global preferredMirror
    if preferredMirror != "auto":
        byName = dict(candidates)
        if preferredMirror in byName:
            return byName[preferredMirror]

    latencies = await asyncio.gather(
        *[probeMirrorUrl(url) for _, url in candidates])
    ranked = sorted(
        (delay, name, url)
        for (name, url), delay in zip(candidates, latencies)
        if delay is not None)
    mirrorLatencies.clear()
    mirrorLatencies.update(
        {name: delay for (name, _url), delay in zip(candidates, latencies)
         if delay is not None})
    if not ranked:
        raise TaskError("无法下载 {name}/{tag}/{asset}", name=repo.name, tag=tag, asset=asset)
    logger.info("加速源测速：{} 选中 {} ({:.2f}s)",
                ", ".join(f"{n}={d:.2f}s" for d, n, _ in ranked),
                ranked[0][1], ranked[0][0])
    return ranked[0][2]


async def fetchReleaseAsset(
    repo: Repo, tag: str, asset: str, outputPath: Path,
    onProgress: Callable[[float], None] | None = None,
) -> str:
    url = await probeDownloadUrl(repo, tag, asset)
    await fetchFile(url, outputPath, onProgress=onProgress)
    return url


PYPI_MIRRORS = {
    "gitcode": "https://mirrors.bfsu.edu.cn/pypi/web/json",
    "github": "https://pypi.org/pypi",
}


def buildPypiUrl(package: str, *, source: str) -> str:
    base = PYPI_MIRRORS.get(source, PYPI_MIRRORS["github"])
    if source == "gitcode":
        return f"{base}/{package}"
    return f"{base}/{package}/json"


async def fetchPypiJson(package: str) -> dict:
    async def attempt(source):
        url = buildPypiUrl(package, source=source)
        client = buildClient(timeout=15)
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return await resp.json()
        except Exception as e:
            logger.debug("从 {} 获取 PyPI {} 失败: {}", source, package, repr(e))
            raise
        finally:
            client.close()

    result, index, _ = await staggered_race(
        [lambda s=s: attempt(s) for s in SOURCE_ORDER], STAGGER_DELAY)
    if index is not None:
        return result
    raise TaskError("无法获取 PyPI 包信息: {package}", package=package)


def buildDownloadUrl(repo: Repo, tag: str, asset: str, *, source: str) -> str:
    endpoints = SOURCES[source]
    return f"{endpoints.download}/{repo.nameOn(source)}/releases/download/{tag}/{asset}"


def buildRawUrl(repo: Repo, branch: str, path: str, *, source: str) -> str:
    endpoints = SOURCES[source]
    return f"{endpoints.raw}/{repo.nameOn(source)}{endpoints.rawInfix}{branch}/{path}"
