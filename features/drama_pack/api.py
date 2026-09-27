from __future__ import annotations

"""果子短剧网页接口封装。

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
    ("hot-drama", "果子热播榜"),
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
    rank: int = 0   # 排行榜名次，0 表示非榜单


@dataclass(frozen=True)
class StreamInfo:
    url: str
    width: str = ""
    height: str = ""
    duration: str = ""
    cencKey: str = ""  # hex；非空表示 CENC 加密流，下载完成后需要解密
    quality: int = 0   # 分辨率高度（App 源为精确值，网页源取自视频信息）
    kind: str = ""     # ""=单文件直链 / "hls"=m3u8 分片流


def isNumericId(text: str) -> bool:
    return bool(_NUMERIC_ID.match((text or "").strip()))


async def _getText(path: str, userAgent: str = BROWSER_UA) -> str:
    client = buildClient(userAgent=userAgent, timeout=20)
    try:
        response = await client.get(BASE + path, headers={"accept": "text/html"})
        try:
            status = response.status.as_int()
            if status != 200:
                raise DramaApiError(f"果子页面返回了异常状态码 {status}")
            return await response.text()
        finally:
            response.close()
    except DramaApiError:
        raise
    except Exception as e:
        logger.opt(exception=e).warning("果子页面请求失败 {}", path)
        raise DramaApiError("果子站点暂时无法访问，请稍后重试") from e
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
        raise DramaApiError("果子页面结构已变化，未找到路由数据")
    try:
        data, _ = json.JSONDecoder().raw_decode(raw[match.end():])
    except Exception as e:
        raise DramaApiError("果子路由数据解析失败，站点可能已改版") from e
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
        raise DramaApiError("果子搜索暂时不可用，请稍后重试")
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
        raise DramaApiError("果子分类数据暂时不可用，请稍后重试")
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
    try:
        rank = int(item["rank"])
    except (KeyError, TypeError, ValueError):
        rank = 0
    remarkParts: list[str] = []
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
        rank=rank,
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


async def _fetchPlayerPage(seriesId: str) -> dict:
    """播放页 SSR 数据：剧集元数据 + 当前真实可播的分集列表。"""
    raw = await _getText(f"/player/{quote(seriesId)}")
    return loaderPage(parseRouterData(raw), "player_(series_id)/page", "player_")


async def detail(seriesId: str) -> Drama:
    seriesId = seriesId.strip()
    if not isNumericId(seriesId):
        raise DramaApiError("剧集编号无效")
    # 优先走播放页：它 SSR 的 seriesDetail 同时带元数据和当前有效分集；
    # 详情页内嵌的 vid_list 可能是已下架的旧集（用它们访问播放页只会得到空壳页面）
    try:
        page = await _fetchPlayerPage(seriesId)
    except DramaApiError as e:
        logger.warning("播放页获取失败，退回详情页: {}", e)
        page = {}
    info = page.get("seriesDetail") if isinstance(page.get("seriesDetail"), dict) else None
    if info:
        drama = dramaFromAny(info)
        if drama is not None:
            vids = tuple(str(v) for v in (info.get("vid_list") or [])
                         if str(v).strip().isdigit())
            if vids:
                drama = replace(drama, vidList=vids)
            if drama.vidList:
                return drama

    raw = await _getText("/detail?series_id=" + quote(seriesId))
    page = loaderPage(parseRouterData(raw), "detail_page", "detail_")
    info = page.get("seriesDetail")
    if not isinstance(info, dict) or not info:
        raise DramaApiError("果子未返回该剧详情，可能已下架")
    drama = dramaFromAny(info)
    if drama is None:
        raise DramaApiError("果子详情缺少有效的剧集编号")
    if not drama.vidList:
        vids = info.get("vid_list") or []
        drama = replace(drama, vidList=tuple(str(v) for v in vids if str(v).strip().isdigit()))
    if not drama.vidList:
        raise DramaApiError("该剧没有返回任何剧集，可能仅剩预告")
    return drama


_PLAYBACK_PROXY_API = "https://djapi.999888456.xyz/api/hongguo/play"
_MIRROR_BASE = "https://www.hongguoapp.cn"
_MIRROR_PLAYER_RE = re.compile(r"player_[a-z0-9]+=(\{.*?\})\s*</script>", re.S)
_MIRROR_SEARCH_CACHE: dict[str, str | None] = {}


def _rol8(value: int, n: int) -> int:
    value &= 0xFF
    return ((value << n) | (value >> (8 - n))) & 0xFF if n else value


def _decodeBackupResponse(text: str) -> bytes:
    """备用解析接口的 v2. 加密响应：掩码派生 AES-CBC 密钥后解密（果子鉴算法）。"""
    text = text.strip()
    if not text.startswith("v2."):
        return text.encode()
    parts = text.split(".", 3)
    if len(parts) != 3 or len(parts[1]) <= 4 or len(parts[1]) > 1028:
        raise DramaApiError("备用接口响应密钥无效")
    from base64 import b64decode

    from Crypto.Cipher import AES

    encoded = bytes.fromhex(parts[1][4:])
    if len(encoded) < 32:
        raise DramaApiError("备用接口响应密钥无效")
    mask = bytes([104, 64, 70, 166, 190, 168, 143, 130, 225, 254,
                  251, 217, 196, 34, 45, 60, 29, 20, 103, 105])
    material = bytearray(len(encoded))
    for i, cur in enumerate(encoded):
        previous = 109 if i == 0 else encoded[i - 1]
        slot = i % len(mask)
        salt = mask[slot] ^ ((90 + 13 * slot) & 0xFF) ^ 85
        shifted = (cur + 215 - 11 * i) & 0xFF
        material[i] = previous ^ salt ^ _rol8(shifted, 3)
    try:
        ciphertext = b64decode(parts[2], validate=True)
    except Exception:
        ciphertext = b64decode(parts[2] + "=" * (-len(parts[2]) % 4))
    if not ciphertext or len(ciphertext) % 16:
        raise DramaApiError("备用接口加密响应无效")
    plain = AES.new(bytes(material[:16]), AES.MODE_CBC,
                    bytes(material[16:32])).decrypt(bytes(ciphertext))
    pad = plain[-1]
    if 1 <= pad <= 16:
        plain = plain[:-pad]
    return plain


async def _backupPlayback(seriesId: str, vid: str, quality: int = 0) -> StreamInfo:
    """备用解析接口：第三方代理，返回 CENC 加密流与密钥（果子鉴渠道）。"""
    from base64 import b64encode

    from .cenc import hongguoContentKey

    reference = json.dumps({
        "content_type": 1004, "from_video_id": "",
        "series_id": str(seriesId), "vid": str(vid), "video_platform": 3,
    }, separators=(",", ":")).encode()
    url = f"{_PLAYBACK_PROXY_API}?id={b64encode(reference).decode()}"
    client = buildClient(userAgent=BROWSER_UA, timeout=20)
    try:
        response = await client.get(url, headers={"accept": "text/plain", "referer": BASE + "/"})
        try:
            status = response.status.as_int()
            if status != 200:
                raise DramaApiError(f"备用接口 HTTP {status}")
            text = await response.text()
        finally:
            response.close()
    except DramaApiError:
        raise
    except Exception as e:
        raise DramaApiError("备用接口无法访问") from e
    finally:
        client.close()

    payload = json.loads(_decodeBackupResponse(text))
    for flag in (payload.get("parse"), payload.get("jx")):
        if str(flag or "") not in ("", "null", "false", "0", '"0"', '""'):
            raise DramaApiError("备用接口未返回直接媒体地址")

    options: list[tuple[str, int, str]] = []   # (src, quality, cencKey)
    for option in payload.get("key_urls") or []:
        src = str(option.get("src") or "").strip()
        if not src.startswith("http") or len(src) > 8192:
            continue
        spade = str(option.get("spade_a") or "")
        try:
            cencKey = hongguoContentKey(spade).hex()
        except Exception:
            continue
        digits = "".join(ch for ch in str(option.get("name") or "") if ch.isdigit())
        options.append((src, int(digits) if digits else 0, cencKey))
    if not options:
        raise DramaApiError("备用接口未返回可用的媒体和密钥")
    best = pickQualityOption(options, quality)
    return StreamInfo(url=best[0], cencKey=best[2], quality=best[1])


def pickQualityOption(options: list[tuple[str, int, str]], quality: int) -> tuple[str, int, str]:
    """按目标清晰度选最接近的一条（同差距取更高）。quality<=0 表示最高。"""
    if quality > 0:
        return min(options, key=lambda o: (abs(o[1] - quality), -o[1]))
    return max(options, key=lambda o: o[1])


def pickQualityStream(streams, quality: int):
    """按目标清晰度从 AppStream 流列表里选一条。"""
    if quality > 0:
        return min(streams, key=lambda s: (abs(s.quality - quality), -s.quality))
    return max(streams, key=lambda s: s.quality)


async def resolveStream(
    seriesId: str, vid: str, title: str = "", pick: int = 0,
    channel: str = "auto", quality: int = 0,
) -> StreamInfo:
    """解析单集播放地址。channel：auto 依次尝试四条渠道，也可指定 app/web/backup/mirror。"""
    from .appapi import appVideoModel

    async def viaApp() -> StreamInfo:
        streams = await appVideoModel(vid)
        if not streams:
            raise DramaApiError("App 接口未返回可用清晰度")
        best = pickQualityStream(streams, quality)
        return StreamInfo(url=best.url, cencKey=best.cencKey, quality=best.quality)

    async def viaWeb() -> StreamInfo:
        path = f"/player/{quote(seriesId)}/{quote(vid)}"
        raw = await _getText(path)
        page = loaderPage(parseRouterData(raw), "player_(series_id)/(vid)/page", "player_")
        info = page.get("video_player_info")
        if not isinstance(info, dict):
            raise DramaApiError("果子未返回播放数据，该集可能仅允许网页试看")
        url = str(info.get("main_url") or "")
        if not url.startswith("http"):
            raise DramaApiError("该集没有公开的播放地址")
        return StreamInfo(
            url=url,
            width=str(info.get("width") or ""),
            height=str(info.get("height") or ""),
            duration=str(info.get("duration") or ""),
        )

    async def viaBackup() -> StreamInfo:
        return await _backupPlayback(seriesId, vid, quality)

    async def viaMirror() -> StreamInfo:
        return await _mirrorResolve(title, pick)

    runners = {
        "app": ("App源", viaApp),
        "web": ("官网源", viaWeb),
        "backup": ("备用源", viaBackup),
        "mirror": ("镜像站", viaMirror),
    }
    order = list(runners)
    if channel in runners:
        order = [channel]
    errors: list[str] = []
    for name in order:
        label, runner = runners[name]
        try:
            return await runner()
        except Exception as e:
            errors.append(f"{label}：{e}")
            logger.info("{} 取流失败，尝试下一渠道: {}", label, e)
    raise DramaApiError("全部渠道取流失败（" + "；".join(errors) + "）")


async def _mirrorFetch(path: str) -> str:
    client = buildClient(userAgent=BROWSER_UA, timeout=20)
    try:
        response = await client.get(
            _MIRROR_BASE + path,
            headers={"accept": "text/html", "accept-language": "zh-CN,zh;q=0.9"})
        try:
            status = response.status.as_int()
            if status != 200:
                raise DramaApiError(f"镜像站 HTTP {status}")
            return await response.text()
        finally:
            response.close()
    except DramaApiError:
        raise
    except Exception as e:
        raise DramaApiError("镜像站无法访问") from e
    finally:
        client.close()


async def _mirrorFindVod(title: str) -> str | None:
    title = (title or "").strip()
    if not title:
        return None
    if title in _MIRROR_SEARCH_CACHE:
        return _MIRROR_SEARCH_CACHE[title]
    vodId: str | None = None
    try:
        raw = await _mirrorFetch(f"/vodsearch/-------------.html?wd={quote(title)}")
        items = re.findall(r'href="/voddetail/(\d+)\.html"[^>]*title="([^"]*)"', raw)
        if not items:
            items = [(m, re.sub(r"<[^>]+>", "", t)) for m, t in
                     re.findall(r'href="/voddetail/(\d+)\.html"[^>]*>([^<]+)</a>', raw)]
        for candidate, name in items:
            if name.strip() == title:
                vodId = candidate
                break
        if vodId is None and items:
            vodId = items[0][0]
    except Exception as e:
        logger.debug("镜像站搜索失败: {}", e)
    _MIRROR_SEARCH_CACHE[title] = vodId
    return vodId


async def _mirrorResolve(title: str, pick: int) -> StreamInfo:
    """镜像站渠道：按剧名匹配后取明文 m3u8 分片流。"""
    vodId = await _mirrorFindVod(title)
    if not vodId:
        raise DramaApiError("镜像站未收录该剧")
    raw = await _mirrorFetch(f"/vodplay/{vodId}-1-{max(1, pick)}.html")
    for m in _MIRROR_PLAYER_RE.finditer(raw):
        try:
            obj = json.loads(m.group(1))
        except Exception:
            continue
        url = str(obj.get("url") or "")
        if ";" in url:
            url = url.split(";", 1)[0]
        if re.search(r"https?://\S+\.m3u8", url):
            return StreamInfo(url=url, kind="hls")
    raise DramaApiError("镜像站该集没有 m3u8 地址")


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
        raise DramaApiError("仅支持果子短剧的分享链接")
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


def formatEpisodeTitle(index: int, template: str = "{剧名} {集数}", seriesTitle: str = "") -> str:
    name = (template or "{剧名} {集数}").replace("{集数}", f"{index:03d}")
    if "{剧名}" in name:
        name = name.replace("{剧名}", seriesTitle)
    return name
