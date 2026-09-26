from __future__ import annotations

"""红果短剧网页接口封装。

全部数据取自 hongguoduanju.com 的服务端渲染页面：页面内嵌一段
`_ROUTER_DATA = {...}` JSON，解析它即可拿到搜索、分类、详情与播放地址，
不依赖已失效的 App 接口，也不涉及任何解密。
"""

import json
import re
from dataclasses import dataclass, field, replace
from urllib.parse import quote, urlparse, parse_qs, unquote

from loguru import logger

from app.client import buildClient

BASE = "https://hongguoduanju.com"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

CATEGORY_ROUTES: list[tuple[str, str]] = [
    ("real-drama", "真人剧"),
    ("comic-drama", "漫剧"),
    ("ai-drama", "AI剧"),
    ("comic", "动漫"),
]

RANK_ROUTES: list[tuple[str, str]] = [
    ("hot-drama", "红果热播榜"),
    ("hot-real-drama", "真人剧热播榜"),
    ("hot-comic-drama", "漫剧热播榜"),
    ("hot-ai-drama", "AI剧热播榜"),
]

# 榜单页只对普通浏览器 UA 返回空壳（数据由前端再拉），
# 爬虫 UA 会直接服务端渲染出完整 rankList，因此榜单请求走爬虫 UA。
CRAWLER_UA = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)

_NUMERIC_ID = re.compile(r"^\d{6,}$")


class DramaApiError(Exception):
    """接口访问失败，message 直接面向用户展示。"""


@dataclass(frozen=True)
class Drama:
    seriesId: str
    title: str
    cover: str = ""
    intro: str = ""
    episodeCount: str = ""
    remark: str = ""
    category: str = ""
    vidList: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class StreamInfo:
    url: str
    width: str = ""
    height: str = ""
    duration: str = ""


def isNumericId(text: str) -> bool:
    return bool(_NUMERIC_ID.match((text or "").strip()))


async def _getText(path: str, userAgent: str = BROWSER_UA) -> str:
    client = buildClient(userAgent=userAgent, timeout=20)
    try:
        response = await client.get(BASE + path, headers={"accept": "text/html"})
        try:
            status = response.status.as_int()
            if status != 200:
                raise DramaApiError(f"红果页面返回了异常状态码 {status}")
            return await response.text()
        finally:
            response.close()
    except DramaApiError:
        raise
    except Exception as e:
        logger.opt(exception=e).warning("红果页面请求失败 {}", path)
        raise DramaApiError("红果站点暂时无法访问，请稍后重试") from e
    finally:
        client.close()


async def getBytes(url: str) -> bytes:
    client = buildClient(userAgent=BROWSER_UA, timeout=20)
    try:
        response = await client.get(url, headers={"accept": "image/*"})
        try:
            response.raise_for_status()
            chunks = []
            async for chunk in response.stream():
                if chunk:
                    chunks.append(chunk)
            return b"".join(chunks)
        finally:
            response.close()
    finally:
        client.close()


def parseRouterData(raw: str) -> dict:
    match = re.search(r"_ROUTER_DATA\s*=\s*", raw)
    if not match:
        raise DramaApiError("红果页面结构已变化，未找到路由数据")
    try:
        data, _ = json.JSONDecoder().raw_decode(raw[match.end():])
    except Exception as e:
        raise DramaApiError("红果路由数据解析失败，站点可能已改版") from e
    loader = data.get("loaderData")
    return loader if isinstance(loader, dict) else {}


def loaderPage(loader: dict, *prefixes: str) -> dict:
    """按前缀匹配 loaderData 下的页面数据（键名常带 $ / (参数) 后缀）。"""
    for name in prefixes:
        value = loader.get(name)
        if isinstance(value, dict) and value:
            return value
    for key, value in loader.items():
        for name in prefixes:
            stem = name.rstrip("$")
            if stem and key.startswith(stem) and isinstance(value, dict) and value:
                return value
    return {}


def dramaFromAny(item: dict, category: str = "") -> Drama | None:
    if not isinstance(item, dict):
        return None
    data = item.get("video_data") if isinstance(item.get("video_data"), dict) else item
    seriesId = str(
        data.get("series_id_str") or data.get("series_id")
        or item.get("series_id_str") or item.get("series_id") or ""
    )
    if not isNumericId(seriesId):
        return None
    title = str(
        data.get("series_title") or data.get("series_name") or data.get("title")
        or item.get("series_name") or item.get("name") or seriesId
    )
    count = str(data.get("episode_cnt") or item.get("episode_cnt") or "")
    remark = str(data.get("episode_right_text") or item.get("episode_right_text") or "")
    if not remark and count:
        remark = f"共{count}集"
    vids = item.get("vid_list") or data.get("vid_list") or []
    vidList = tuple(str(v) for v in vids if str(v).strip().isdigit())
    return Drama(
        seriesId=seriesId,
        title=title,
        cover=str(data.get("series_cover") or data.get("cover") or item.get("series_cover") or ""),
        intro=str(data.get("series_intro") or data.get("video_desc") or item.get("series_intro") or ""),
        episodeCount=count,
        remark=remark,
        category=str(data.get("category_name") or category),
        vidList=vidList,
    )


async def search(keyword: str) -> list[Drama]:
    keyword = keyword.strip()
    if not keyword:
        return []
    raw = await _getText("/search/" + quote(keyword))
    page = loaderPage(parseRouterData(raw), "search_(keyword)/page", "search_")
    if page.get("isSuccess") is not True:
        raise DramaApiError("红果搜索暂时不可用，请稍后重试")
    rows = page.get("searchList") or []
    out: list[Drama] = []
    seen: set[str] = set()
    for row in rows:
        drama = dramaFromAny(row, "短剧")
        if drama and drama.seriesId not in seen:
            seen.add(drama.seriesId)
            out.append(drama)
    if not out:
        raise DramaApiError("没有搜到相关短剧，换个关键词试试")
    return out


async def category(route: str, page: int = 1, categoryName: str = "") -> tuple[list[Drama], int]:
    raw = await _getText(f"/category/{route}?page={max(1, page)}")
    data = loaderPage(parseRouterData(raw), "category_page", "category_")
    if data.get("isSuccess") is False:
        raise DramaApiError("红果分类数据暂时不可用，请稍后重试")
    rows = data.get("recommendList") or []
    out: list[Drama] = []
    seen: set[str] = set()
    for row in rows:
        drama = dramaFromAny(row, categoryName)
        if drama and drama.seriesId not in seen:
            seen.add(drama.seriesId)
            out.append(drama)
    try:
        totalPages = int((data.get("pagination") or {}).get("totalPages") or 1)
    except (TypeError, ValueError):
        totalPages = 1
    return out, totalPages


def rankItemToDrama(item: dict) -> Drama | None:
    if not isinstance(item, dict):
        return None
    seriesId = str(item.get("seriesId") or item.get("id") or "")
    if not isNumericId(seriesId):
        return None
    remarkParts: list[str] = []
    if item.get("rank") is not None:
        remarkParts.append(f"第{item['rank']}名")
    for key in ("heatText", "scoreText"):
        value = str(item.get(key) or "").strip()
        if value:
            remarkParts.append(value)
    tags = [str(t) for t in (item.get("tags") or []) if str(t).strip()]
    return Drama(
        seriesId=seriesId,
        title=str(item.get("title") or seriesId),
        cover=str(item.get("cover") or ""),
        intro=str(item.get("description") or ""),
        remark=" · ".join(remarkParts),
        category="/".join(tags[:3]) if tags else "榜单",
    )


async def rank(route: str, page: int = 1) -> tuple[list[Drama], int]:
    raw = await _getText(
        f"/rank/{quote(route)}?page={max(1, page)}", userAgent=CRAWLER_UA)
    data = loaderPage(parseRouterData(raw), f"rank_{route}/page", f"rank_{route}", "rank_")
    content = data.get("content") if isinstance(data.get("content"), dict) else data
    rows = content.get("rankList") or []
    out: list[Drama] = []
    seen: set[str] = set()
    for row in rows:
        drama = rankItemToDrama(row)
        if drama and drama.seriesId not in seen:
            seen.add(drama.seriesId)
            out.append(drama)
    try:
        totalPages = int((content.get("pagination") or {}).get("totalPages") or 1)
    except (TypeError, ValueError):
        totalPages = 1
    return out, totalPages


async def detail(seriesId: str) -> Drama:
    seriesId = seriesId.strip()
    if not isNumericId(seriesId):
        raise DramaApiError("剧集编号无效")
    raw = await _getText("/detail?series_id=" + quote(seriesId))
    page = loaderPage(parseRouterData(raw), "detail_page", "detail_")
    info = page.get("seriesDetail")
    if not isinstance(info, dict) or not info:
        raise DramaApiError("红果未返回该剧详情，可能已下架")
    drama = dramaFromAny(info)
    if drama is None:
        raise DramaApiError("红果详情缺少有效的剧集编号")
    if not drama.vidList:
        vids = info.get("vid_list") or []
        drama = replace(drama, vidList=tuple(str(v) for v in vids if str(v).strip().isdigit()))
    if not drama.vidList:
        raise DramaApiError("该剧没有返回任何剧集，可能仅剩预告")
    return drama


async def resolveStream(seriesId: str, vid: str) -> StreamInfo:
    path = f"/player/{quote(seriesId)}/{quote(vid)}"
    raw = await _getText(path)
    page = loaderPage(parseRouterData(raw), "player_(series_id)/(vid)/page", "player_")
    info = page.get("video_player_info")
    if not isinstance(info, dict):
        raise DramaApiError("红果未返回播放数据，该集可能仅允许网页试看")
    url = str(info.get("main_url") or "")
    if not url.startswith("http"):
        raise DramaApiError("该集没有公开的播放地址，可能需要登录或仅限试看")
    return StreamInfo(
        url=url,
        width=str(info.get("width") or ""),
        height=str(info.get("height") or ""),
        duration=str(info.get("duration") or ""),
    )


async def resolveSeriesId(text: str) -> str:
    """从编号、播放页或详情链接中提取 series_id。"""
    text = (text or "").strip()
    if isNumericId(text):
        return text
    if text.isdigit() and len(text) <= 12:
        return text
    if not text.lower().startswith(("http://", "https://")):
        raise DramaApiError("无法识别的链接或编号")
    parsed = urlparse(text)
    if "hongguoduanju.com" not in parsed.netloc.lower():
        raise DramaApiError("仅支持红果短剧的分享链接")
    match = re.search(r"/player/(\d+)", parsed.path)
    if match:
        return match.group(1)
    query = parse_qs(parsed.query)
    for key in ("series_id", "video_series_id"):
        value = (query.get(key) or [""])[0]
        if isNumericId(value):
            return value
    raw = await _getText(text if text.startswith("/") else parsed.path + (
        "?" + parsed.query if parsed.query else ""))
    body = unquote(raw)
    for pattern in (r"video_series_id=(\d+)", r'"series_id"\s*:\s*"?(\d+)"?'):
        found = re.search(pattern, body)
        if found:
            return found.group(1)
    raise DramaApiError("无法从该链接解析剧集编号")


def parsePickSpec(spec: str, total: int) -> list[int]:
    """解析选集语法：`all`、`1-50`、`1-10, 25, 30-45`、`-20`（前20）、`20-`（20起）。"""
    text = (spec or "").strip().lower()
    if not text or text == "all" or text == "全部":
        return list(range(1, total + 1))
    picked: set[int] = set()
    for part in text.replace("，", ",").split(","):
        part = part.strip()
        if not part:
            continue
        singleMatch = re.match(r"^(\d+)$", part)              # 25 → 第 25 集
        headMatch = re.match(r"^-(\d+)$", part)               # -20 → 前 20 集
        tailMatch = re.match(r"^(\d+)-$", part)               # 20- → 第 20 集起
        rangeMatch = re.match(r"^(\d+)\s*-\s*(\d+)$", part)   # 1-50
        if singleMatch:
            number = int(singleMatch.group(1))
            if 1 <= number <= total:
                picked.add(number)
        elif headMatch:
            picked.update(range(1, min(total, int(headMatch.group(1))) + 1))
        elif tailMatch:
            start = max(1, int(tailMatch.group(1)))
            picked.update(range(start, total + 1))
        elif rangeMatch:
            start = max(1, int(rangeMatch.group(1)))
            end = min(total, int(rangeMatch.group(2)))
            if start <= end:
                picked.update(range(start, end + 1))
    return sorted(picked)


def formatEpisodeTitle(index: int) -> str:
    return f"第{index:03d}集"
