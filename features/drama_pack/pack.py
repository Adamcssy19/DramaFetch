from __future__ import annotations

"""DramaFetch 短剧特性包：解析器 + 界面页注册。"""

import re
from urllib.parse import urlparse

from app.models.pack import FeaturePack, TaskParser
from app.models.task import Task, TaskOptions

from . import api
from .task import buildDramaTask, buildSingleEpisodeTask

_PLAYER_PATH = re.compile(r"^/player/(\d+)(?:/(\d+))?$")
_NUMERIC_ID = re.compile(r"^\d{6,}$")


def _isHongguoUrl(url: str) -> bool:
    try:
        return urlparse(url).hostname or "" in {"hongguoduanju.com", "www.hongguoduanju.com"}
    except ValueError:
        return False


class DramaParser(TaskParser):
    priority = 50

    def match(self, options: TaskOptions) -> bool:
        url = options.url.strip()
        return url.startswith("drama://") or _isHongguoUrl(url)

    def matchPassive(self, options: TaskOptions) -> bool:
        url = options.url.strip()
        if url.startswith("drama://"):
            return True
        if not _isHongguoUrl(url):
            return False
        path = urlparse(url).path
        return bool(_PLAYER_PATH.match(path)) or path.startswith("/detail")

    async def parse(self, options: TaskOptions) -> Task:
        url = options.url.strip()
        if url.startswith("drama://"):
            return await buildDramaTask(
                url,
                outputFolder=options.outputFolder,
                subworkerCount=options.subworkerCount,
            )

        parsed = urlparse(url)
        path = parsed.path

        # 播放页链接 → 单集任务
        player = _PLAYER_PATH.match(path)
        if player and player.group(2):
            seriesId, vid = player.group(1), player.group(2)
            drama = await api.detail(seriesId)
            pick = next(
                (i + 1 for i, v in enumerate(drama.vidList) if v == vid), 1
            )
            stream = await api.resolveStream(seriesId, vid,
                                             title=drama.title, pick=pick)
            return buildSingleEpisodeTask(
                drama, pick, stream,
                outputFolder=options.outputFolder,
                subworkerCount=options.subworkerCount,
            )

        # 详情页链接 → 整部任务（全集）
        if path.startswith("/detail"):
            from urllib.parse import parse_qs

            seriesId = (parse_qs(parsed.query).get("series_id") or [""])[0]
            if not _NUMERIC_ID.match(seriesId):
                raise ValueError("详情链接缺少有效的 series_id")
            return await buildDramaTask(
                f"drama://hongguo/{seriesId}?eps=all",
                outputFolder=options.outputFolder,
                subworkerCount=options.subworkerCount,
            )

        raise ValueError("仅支持果子短剧的播放页或详情页链接")


class DramaPack(FeaturePack):
    packId = "drama"

    parsers = [DramaParser]

    def taskCardClass(self, task: Task) -> type | None:
        from .cards import DramaTaskCard

        return DramaTaskCard

    def pages(self):
        from .page import DramaPage, RankPage

        return [DramaPage, RankPage]

    def optionCards(self, task: Task, parent=None) -> list:
        from app.view.components.option_cards import OutputFolderCard, SubworkerCountCard

        return [
            OutputFolderCard(parent, initial=task.outputFolder),
            SubworkerCountCard(parent),
        ]
