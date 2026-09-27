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
from app.config.cfg import cfg
from app.platform.filesystem import toSafeFilename

from . import api
from .api import (
    BASE,
    Drama,
    StreamInfo,
    formatEpisodeTitle,
    detail,
    resolveStream,
)
from http_pack.task import HttpTask, HttpTaskStep
from m3u8_pack.task import M3U8TaskStep

DRAMA_SCHEME = "drama"
POSTER_NAME = "poster.jpg"


def posterNameFor(title: str, seriesId: str) -> str:
    """海报文件名：剧名_频道ID.jpg，便于人工辨认。"""
    return f"{toSafeFilename(title)}_{seriesId}.jpg"


@dataclass(frozen=True)
class EpisodePick:
    index: int
    vid: str
    title: str


@dataclass(kw_only=True)
class CencTaskStep(HttpTaskStep):
    """CENC 加密源的下载步骤：下载完成后自动解密为可播放 MP4。"""

    cencKey: str = ""

    async def run(self, reportSpeed, waitForSpeedLimit) -> None:
        self.stageText = "下载中"
        await super().run(reportSpeed, waitForSpeedLimit)
        from .cenc import decryptCencMp4

        path = Path(self.outputFile)
        data = bytearray(path.read_bytes())
        self.stageText = "解密中"
        plain = decryptCencMp4(data, bytes.fromhex(self.cencKey))
        temp = path.with_suffix(path.suffix + ".dec")
        temp.write_bytes(plain)
        temp.replace(path)
        logger.info("已完成 CENC 解密: {}", path.name)


@dataclass(kw_only=True, eq=False)
class DramaTask(Task):
    packId = "drama"
    canEdit = True
    posterFile: str = ""

    @property
    def outputPath(self) -> str:
        """短剧任务的实际产物是「剧文件夹」，而非 outputFolder/name。"""
        for step in self.steps:
            outputFile = getattr(step, "outputFile", "")
            if outputFile:
                return str(Path(outputFile).parent)
        return str(Path(self.outputFolder) / self.name)


def buildDramaTaskUrl(
    seriesId: str,
    title: str,
    picks: list[int],
    category: str = "",
    channel: str = "auto",
    quality: int = 0,
) -> str:
    eps = ",".join(str(i) for i in picks) if len(picks) < 400 else "all"
    query = f"name={quote(title)}&eps={quote(eps)}"
    if category:
        query += f"&cat={quote(category)}"
    if channel and channel != "auto":
        query += f"&ch={quote(channel)}"
    if quality:
        query += f"&q={quality}"
    return f"{DRAMA_SCHEME}://hongguo/{seriesId}?{query}"


def parseDramaTaskUrl(url: str) -> tuple[str, str, list[int], str, str, int]:
    parsed = urlparse(url)
    if parsed.scheme != DRAMA_SCHEME or parsed.hostname != "hongguo":
        raise ValueError("不是短剧任务链接")
    seriesId = parsed.path.strip("/")
    query = parse_qs(parsed.query)
    title = unquote((query.get("name") or [""])[0])
    category = unquote((query.get("cat") or [""])[0])
    channel = (query.get("ch") or ["auto"])[0]
    try:
        quality = int((query.get("q") or ["0"])[0])
    except ValueError:
        quality = 0
    epsText = unquote((query.get("eps") or ["all"])[0])
    picks: list[int] = []
    for part in epsText.split(","):
        part = part.strip()
        if part.isdigit():
            picks.append(int(part))
    return seriesId, title, picks, category, channel, quality


async def buildDramaTask(
    options_url: str,
    outputFolder: Path,
    subworkerCount: int = 8,
) -> DramaTask:
    """解析任务链接：取详情 → 解析每集直链 → 组装多集任务。"""
    seriesId, title, picks, category, channel, quality = parseDramaTaskUrl(options_url)
    drama = await detail(seriesId)
    title = title or drama.title or seriesId

    total = len(drama.vidList)
    wanted = [p for p in picks if 1 <= p <= total] or list(range(1, total + 1))
    if not wanted:
        raise ValueError("没有可下载的剧集")

    # 并发解析每集直链（App 接口原画优先，失败退官网网页直链）
    semaphore = asyncio.Semaphore(5)
    failures: list[str] = []

    async def resolveOne(pick: int) -> tuple[int, StreamInfo] | None:
        async with semaphore:
            try:
                info = await resolveStream(seriesId, drama.vidList[pick - 1],
                                           title=title, pick=pick,
                                           channel=channel, quality=quality)
                return pick, info
            except Exception as e:
                failures.append(f"第{pick}集：{e}")
                return None

    results = await asyncio.gather(*(resolveOne(p) for p in wanted))
    resolved = {pick: info for item in results if item for pick, info in [item]}
    if not resolved:
        raise ValueError("所有选中剧集都取流失败：\n" + "\n".join(failures[:3]))

    safeName = toSafeFilename(title, fallback=f"短剧_{seriesId}")
    baseFolder = Path(outputFolder)
    subfolder = str(cfg.dramaSubfolder.value or "").strip()
    if subfolder:
        baseFolder = baseFolder / toSafeFilename(subfolder)
    folder = baseFolder / safeName
    template = cfg.dramaNameFormat.value

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
        epName = toSafeFilename(formatEpisodeTitle(pick, template, safeName),
                                fallback=f"第{pick:03d}集")
        relative = "/".join(part for part in (subfolder, safeName, f"{epName}.mp4") if part)
        files.append(TaskFile(index=order, relativePath=relative))
        info = resolved[pick]
        referer = "https://novel.snssdk.com/" if info.cencKey else BASE + "/"
        common = dict(
            stepIndex=order,
            fileIndex=order,
            url=info.url,
            subworkerCount=subworkerCount,
            outputFile=str(folder / f"{epName}.mp4"),
        )
        if info.kind == "hls":
            steps.append(M3U8TaskStep(headers={}, threadCount=subworkerCount, **common))
        elif info.cencKey:
            steps.append(CencTaskStep(cencKey=info.cencKey,
                                      headers={"referer": referer}, **common))
        else:
            steps.append(HttpTaskStep(headers={"referer": referer}, **common))
    task.steps = steps
    task.files = files
    task.fileSize = 0
    task.__post_init__()

    # 保存剧集海报（供任务列表卡片显示），失败不影响任务
    try:
        folder.mkdir(parents=True, exist_ok=True)
        posterName = posterNameFor(title, seriesId)
        task.posterFile = posterName
        posterPath = folder / posterName
        if drama.cover and not posterPath.exists():
            coverBytes = await api.getBytes(drama.cover)
            if coverBytes:
                posterPath.write_bytes(coverBytes)
    except Exception as e:
        logger.warning("下载剧集海报失败: {}", e)

    if failures:
        logger.warning("短剧 {} 有 {} 集取流失败: {}", title, len(failures), "; ".join(failures[:3]))
    return task


def buildSingleEpisodeTask(
    drama: Drama,
    pick: int,
    stream: StreamInfo,
    outputFolder: Path,
    subworkerCount: int = 8,
):
    """单集任务（粘贴播放页链接时用），复用 http_pack 的标准任务。"""
    safeName = toSafeFilename(drama.title or "果子短剧", fallback="果子短剧")
    epName = toSafeFilename(
        formatEpisodeTitle(pick, cfg.dramaNameFormat.value, safeName),
        fallback=f"第{pick:03d}集")
    fileName = f"{epName}.mp4"
    baseFolder = Path(outputFolder)
    subfolder = str(cfg.dramaSubfolder.value or "").strip()
    if subfolder:
        baseFolder = baseFolder / toSafeFilename(subfolder)
    task = HttpTask(
        name=f"{safeName}_{epName}",
        url=stream.url,
        packId="http",
        outputFolder=Path(outputFolder),
    )
    common = dict(
        stepIndex=1,
        url=stream.url,
        subworkerCount=subworkerCount,
        outputFile=str(baseFolder / safeName / fileName),
    )
    if stream.kind == "hls":
        task.addStep(M3U8TaskStep(headers={}, threadCount=subworkerCount, **common))
    elif stream.cencKey:
        task.addStep(CencTaskStep(cencKey=stream.cencKey,
                                  headers={"referer": "https://novel.snssdk.com/"}, **common))
    else:
        task.addStep(HttpTaskStep(headers={"referer": BASE + "/"}, **common))
    return task
