from __future__ import annotations

"""解析封装：对接开源短视频去水印库 parse-video-py。

上游：https://github.com/wujunwei928/parse-video-py （MIT，★700+，26 平台）
纯 Python 实现（aiohttp / httpx / lxml / parsel / jmespath / pyyaml），
不需要 FastAPI 或 uvicorn —— 所以这里优先「进程内直接调用」，零子进程开销：

  1. 进程内 `from parse_video_py import parse_video_share_url` 直接 await
  2. 退化为子进程 CLI：`parse-video-py parse <url> --format json`
  3. 再退化为 `uvx --from git+…`（本机有 uv 时免装）

该库没有发布到 PyPI，已作为 git 依赖写进 pyproject.toml，
由 `uv sync` + Nuitka 打进安装包，正常用户无需任何额外操作。

关于「抖音风控兜底」：二改库 baige778/parse-video-py 增加了持久化登录态的
无头浏览器兜底（原生 HTML 解析失败 → Chromium 兜底），成功率更高但会引入
Playwright/Chromium（几百 MB），与项目「低内存、单安装包」定位冲突，
因此这里只用上游纯 HTTP 实现；如遇到抖音风控可考虑单独起它做可选后端。
"""

import asyncio
import json
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any

# 从分享文案里抠出 URL（如「7.43 复制打开抖音… https://v.douyin.com/xxx/ …」）
_URL_RE = re.compile(r"https?://[\w.-]+[\w/-]*[\w.-]*\??[\w=&:\-+%.]*/?[^\s，,。；;]*")

# 用户常直接粘贴不带 scheme 的裸域名，这里兜底识别
_BARE_DOMAIN_RE = re.compile(
    r"(?:^|[\s，,。；;])((?:[\w-]+\.)+(?:com|cn|net|tv|org|me|link|xyz)"
    r"(?:/[\w\-./?=&:%+]*)?)"
)

# 域名 → 平台名（仅用于 UI 展示，不参与解析）
_PLATFORM_BY_DOMAIN = {
    "douyin.com": "抖音",
    "iesdouyin.com": "抖音",
    "kuaishou.com": "快手",
    "xiaohongshu.com": "小红书",
    "xhslink.com": "小红书",
    "xhslink.cn": "小红书",
    "bilibili.com": "哔哩哔哩",
    "b23.tv": "哔哩哔哩",
    "ixigua.com": "西瓜视频",
    "weibo.com": "微博",
    "weibo.cn": "微博",
    "qq.com": "腾讯视频",
    "sohu.com": "搜狐视频",
    "pearvideo.com": "梨视频",
    "huya.com": "虎牙",
    "ixigua": "西瓜视频",
    "acfun.cn": "AcFun",
    "pipix.com": "皮皮虾",
    "pipigx.com": "皮皮搞笑",
    "meipai.com": "美拍",
    "twitter.com": "Twitter",
    "x.com": "Twitter",
    "cctv.com": "央视网",
    "cctv.cn": "央视网",
    "haokan.baidu.com": "好看视频",
    "doupai.cc": "逗拍",
    "zuiyou": "最右",
    "6.cn": "六间房",
    "quanmin": "度小视",
}

# 抖音 / 快手等常见短链，用于提示（不用于逻辑分支）
_SHORT_LINK_HINT = ("v.douyin.com", "v.kuaishou.com", "xhslink")


@dataclass
class ParseResult:
    title: str = ""
    video_url: str = ""
    music_url: str = ""
    cover_url: str = ""
    author: str = ""
    author_uid: str = ""
    platform: str = ""
    images: list[dict[str, str]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """拿到无水印视频直链才算成功；纯图集作品不算。"""
        return bool(self.video_url)

    @property
    def isGallery(self) -> bool:
        """图集作品（无视频、只有图片列表）。"""
        return not self.video_url and bool(self.images)


# ────────────────────────── 对外入口 ──────────────────────────


async def parse(url: str) -> ParseResult:
    """解析分享链接，返回无水印视频信息。失败抛异常（消息可直接展示）。"""
    url = extractUrl(url)
    if not url:
        raise ValueError("未检测到有效链接，请粘贴包含 http(s) 地址的分享内容")

    try:
        info = await _parseInProcess(url)
        if info is not None:
            return info
        return await _parseByCli(url)
    except Exception as err:  # noqa: BLE001 - 统一转成可读文案
        raise _friendly(err) from None


# 上游异常多为英文，转成中文可读文案（命中即替换，未命中保留原文）
_ERROR_MAP: tuple[tuple[str, str], ...] = (
    ("does not have source config", "暂不支持该平台的分享链接"),
    ("has no video parser", "该平台还没有可用的解析器"),
    ("Failed to parse video ID from app share URL", "分享链接无效或已过期，请重新复制分享"),
    ("Failed to parse video id from app share URL", "分享链接无效或已过期，请重新复制分享"),
    ("Failed to get video detail", "拿不到视频详情（可能被平台风控拦截，稍后重试）"),
    ("Failed to get video info", "拿不到视频信息（可能被平台风控拦截，稍后重试）"),
    ("Captcha", "触发平台验证码，请稍后重试"),
    ("captcha", "触发平台验证码，请稍后重试"),
    ("login", "需要登录态（该作品仅登录后可见）"),
    ("deleted", "该作品已被删除"),
)


def _friendly(err: Exception) -> Exception:
    """把上游英文异常翻成中文可读文案；未命中时保留原文。"""
    text = str(err) or err.__class__.__name__
    for needle, chinese in _ERROR_MAP:
        if needle in text:
            return RuntimeError(chinese)
    if isinstance(err, RuntimeError):
        return err
    return RuntimeError(text)


# ────────────────────────── 链接提取 ──────────────────────────


def extractUrl(text: str) -> str:
    """从分享文案中提取第一个 URL；已优先复用上游实现。"""
    text = (text or "").strip()
    if not text:
        return ""
    try:
        from parse_video_py.utils import extract_url  # type: ignore

        found = extract_url(text)
        if found:
            return found
    except Exception:
        pass

    m = _URL_RE.search(text)
    if m:
        return m.group()

    # 兜底：裸域名（自动补 https://）
    m = _BARE_DOMAIN_RE.search(" " + text)
    if m:
        return "https://" + m.group(1)
    return ""


def platformOf(url: str) -> str:
    host = ""
    try:
        from urllib.parse import urlparse

        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return ""
    for domain, name in _PLATFORM_BY_DOMAIN.items():
        if host.endswith(domain):
            return name
    return host or ""


def isShortLink(url: str) -> bool:
    return any(h in (url or "") for h in _SHORT_LINK_HINT)


# ────────────────────────── 方式一：进程内 ──────────────────────────


async def _parseInProcess(url: str) -> ParseResult | None:
    """上游库已安装时直接调用；未安装返回 None 以便回落 CLI。"""
    try:
        from parse_video_py import parse_video_share_url  # type: ignore
    except ImportError:
        return None

    info = await parse_video_share_url(url)
    return _fromVideoInfo(info, url)


def _fromVideoInfo(info: Any, url: str) -> ParseResult:
    author = getattr(info, "author", None)
    images = []
    for img in getattr(info, "images", None) or []:
        img_url = getattr(img, "url", "") or ""
        if img_url:
            images.append({
                "url": img_url,
                "live_photo_url": getattr(img, "live_photo_url", "") or "",
            })
    return ParseResult(
        title=getattr(info, "title", "") or "",
        video_url=getattr(info, "video_url", "") or "",
        music_url=getattr(info, "music_url", "") or "",
        cover_url=getattr(info, "cover_url", "") or "",
        author=getattr(author, "name", "") or "",
        author_uid=getattr(author, "uid", "") or "",
        platform=platformOf(url),
        images=images,
        raw={
            "video_url": getattr(info, "video_url", "") or "",
            "cover_url": getattr(info, "cover_url", "") or "",
            "title": getattr(info, "title", "") or "",
            "music_url": getattr(info, "music_url", "") or "",
            "images": images,
            "author": {
                "uid": getattr(author, "uid", "") or "",
                "name": getattr(author, "name", "") or "",
                "avatar": getattr(author, "avatar", "") or "",
            },
        },
    )


# ────────────────────────── 方式二：子进程 CLI ──────────────────────────


async def _parseByCli(url: str) -> ParseResult:
    """上游库未安装 → 走 CLI 子进程（已安装的控制台脚本 / uvx 免安装）。"""
    last_err: Exception | None = None
    for cmd in _cliCandidates(url):
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            continue

        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=90)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            last_err = TimeoutError("解析超时（>90s）")
            continue

        text = out.decode("utf-8", "ignore").strip()
        data = _extractJson(text)
        if data:
            result = _fromDict(data, url)
            if result.video_url or result.images:
                return result

        detail = err.decode("utf-8", "ignore").strip()
        if _looksMissing(cmd, detail):
            # 该入口本身不存在（命令未安装），换下一个候选
            continue
        if detail:
            last_err = RuntimeError(detail.splitlines()[-1][:300])

    if last_err is not None:
        raise last_err
    raise RuntimeError(_INSTALL_HINT)


# 判定「命令/模块根本没装上」，避免把安装缺失误报成解析失败
_MISSING_MARKERS = (
    "no module named",
    "command not found",
    "not recognized as an internal or external command",
    "can't open file",
    "no such file or directory",
)


def _looksMissing(cmd: list[str], stderr_text: str) -> bool:
    if not stderr_text:
        # 无任何输出：命令跑起来了但没结果，不算「没安装」
        return False
    low = stderr_text.lower()
    return any(marker in low for marker in _MISSING_MARKERS)


_INSTALL_HINT = (
    "未找到 parse-video-py 解析库（该库未发布到 PyPI，需从源码安装）：\n"
    '  uv pip install "git+https://github.com/wujunwei928/parse-video-py"\n'
    '  pip install "git+https://github.com/wujunwei928/parse-video-py"\n'
    "项目地址：https://github.com/wujunwei928/parse-video-py\n"
    "（发布版 DramaFetch 已内置该库，如仍见此提示说明安装包不完整）"
)

_GIT_SPEC = "git+https://github.com/wujunwei928/parse-video-py"


def _cliCandidates(url: str) -> list[list[str]]:
    """1) 已安装的控制台脚本；2) 借助 uv 临时拉取（需本机有 uv 与网络）。"""
    return [
        ["parse-video-py", "parse", url, "--format", "json"],
        ["uvx", "--from", _GIT_SPEC, "parse-video-py", "parse", url, "--format", "json"],
    ]


def _extractJson(text: str) -> dict | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _fromDict(data: dict, url: str) -> ParseResult:
    """兼容 CLI JSON 输出：VideoInfo 的 asdict 结构。"""
    author = data.get("author") or {}
    if isinstance(author, dict):
        author_name = author.get("name") or author.get("uid") or ""
        author_uid = author.get("uid") or ""
    else:
        author_name, author_uid = str(author), ""

    images = []
    for img in data.get("images") or []:
        if isinstance(img, dict) and img.get("url"):
            images.append({
                "url": str(img.get("url") or ""),
                "live_photo_url": str(img.get("live_photo_url") or ""),
            })

    return ParseResult(
        title=str(data.get("title") or ""),
        video_url=str(data.get("video_url") or data.get("videoUrl") or ""),
        music_url=str(data.get("music_url") or data.get("musicUrl") or ""),
        cover_url=str(data.get("cover_url") or data.get("coverUrl") or ""),
        author=str(author_name),
        author_uid=str(author_uid),
        platform=str(data.get("platform") or platformOf(url)),
        images=images,
        raw=data,
    )
