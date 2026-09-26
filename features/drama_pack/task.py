from __future__ import annotations

"""短剧下载任务：一部剧一个任务，每集对应一个 HTTP 下载步骤。

下载、分片、断点续传完全复用 http_pack 的 HttpTaskStep，
本模块只负责把「剧 → 选中的集 → 每集的直链」组装成底座（Ghost-Downloader-3）的任务结构。
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, parse_qs

from loguru import logger

from app.models.task import Task, TaskFile
from app.platform.filesystem import toSafeFilename

from .api import (
    BASE,
    Drama,
    formatEpisodeTitle,
    detail,
    resolveStream,
)

DRAMA_SCHEME = "drama"


@dataclass(frozen=True)
class EpisodePick:
    index: int
    vid: str
    title: str


class DramaTask(Task):
    packId = "drama"
    canEdit = True


def buildDramaTaskUrl(
    seriesId: str,
    title: str,
    picks: list[int],
    category: str = "",
) -> str:
    eps = ",".join(str(i) for i in picks) if len(picks) < 400 else "all"
    query = f"name={quote(title)}&eps={quote(eps)}"
    if category:
        query += f"&cat={quote(category)}"
    return f"{DRAMA_SCHEME}://hongguo/{seriesId}?{query}"


def parseDramaTaskUrl(url: str) -> tuple[str, str, list[int], str]:
    parsed = urlparse(url)
    if parsed.scheme != DRAMA_SCHEME or parsed.hostname != "hongguo":
        raise ValueError("不是短剧任务链接")
    seriesId = parsed.path.strip("/")
    query = parse_qs(parsed.query)
    title = unquote((query.get("name") or [""])[0])
    category = unquote((query.get("cat") or [""])[0])
    epsText = unquote((query.get("eps") or ["all"])[0])
    picks: list[int] = []
    for part in epsText.split(","):
        part = part.strip()
        if part.isdigit():
            picks.append(int(part))
    return seriesId, title, picks, category


async def buildDramaTask(
    options_url: str,
    outputFolder: Path,
    subworkerCount: int = 8,
) -> DramaTask:
    """解析任务链接：取详情 → 解析每集直链 → 组装多集任务。"""
    from http_pack.task import HttpTaskStep

    seriesId, title, picks, category = parseDramaTaskUrl(options_url)
    drama = await detail(seriesId)
    title = title or drama.title or seriesId

    total = len(drama.vidList)
    wanted = [p for p in picks if 1 <= p <= total] or list(range(1, total + 1))
    if not wanted:
        raise ValueError("没有可下载的剧集")

    # 并发解析每集直链（网页一次一个请求，5 路并发已足够快且不刺激风控）
    semaphore = asyncio.Semaphore(5)
    failures: list[str] = []

    async def resolveOne(pick: int) -> tuple[int, str] | None:
        async with semaphore:
            try:
                info = await resolveStream(seriesId, drama.vidList[pick - 1])
                return pick, info.url
            except Exception as e:
                failures.append(f"第{pick}集：{e}")
                return None

    results = await asyncio.gather(*(resolveOne(p) for p in wanted))
    resolved = {pick: url for item in results if item for pick, url in [item]}
    if not resolved:
        raise ValueError("所有选中剧集都取流失败：\n" + "\n".join(failures[:3]))

    safeName = toSafeFilename(title, fallback=f"短剧_{seriesId}")
    folder = Path(outputFolder) / safeName

    task = DramaTask(
        name=safeName,
        url=options_url,
        packId="drama",
        outputFolder=Path(outputFolder),
        files=[],
        steps=[],
    )
    steps = []
    files: list[TaskFile] = []
    for order, pick in enumerate(sorted(resolved)):
        relative = f"{safeName}/{formatEpisodeTitle(pick)}.mp4"
        files.append(TaskFile(index=order, relativePath=relative))
        steps.append(HttpTaskStep(
            stepIndex=order,
            fileIndex=order,
            url=resolved[pick],
            headers={"referer": BASE + "/"},
            subworkerCount=subworkerCount,
            canUseRangeRequests=True,
            outputFile=str(folder / f"{formatEpisodeTitle(pick)}.mp4"),
        ))
    task.steps = steps
    task.files = files
    task.fileSize = 0
    task.__post_init__()

    if failures:
        logger.warning("短剧 {} 有 {} 集取流失败: {}", title, len(failures), "; ".join(failures[:3]))
    return task


def buildSingleEpisodeTask(
    drama: Drama,
    pick: int,
    streamUrl: str,
    outputFolder: Path,
    subworkerCount: int = 8,
):
    """单集任务（粘贴播放页链接时用），复用 http_pack 的标准任务。"""
    from http_pack.task import HttpTask, HttpTaskStep

    safeName = toSafeFilename(drama.title or "红果短剧", fallback="红果短剧")
    fileName = f"{formatEpisodeTitle(pick)}.mp4"
    task = HttpTask(
        name=f"{safeName}_{formatEpisodeTitle(pick)}",
        url=streamUrl,
        packId="http",
        outputFolder=Path(outputFolder),
    )
    task.addStep(HttpTaskStep(
        stepIndex=1,
        url=streamUrl,
        headers={"referer": BASE + "/"},
        subworkerCount=subworkerCount,
        canUseRangeRequests=True,
        outputFile=str(Path(outputFolder) / safeName / fileName),
    ))
    return task
