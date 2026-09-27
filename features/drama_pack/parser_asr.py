from __future__ import annotations

"""文案提取（字幕 + 声音文案）的可插拔 ASR 框架。

当前只搭框架，不内置任何 ASR 引擎——按需求「先留可插拔接口」：
  - 抽取音频走 ffmpeg（短剧本体已带 ffmpeg 工具链）；
  - 语音转写由 ASREngine 子类完成，外部可随时注册一个真引擎
    （本地 Whisper / 云端识别 API 等），未注册时返回占位说明。

字幕说明：短视频绝大多数不带独立字幕轨，所谓「文案」实际来自声音转写，
所以统一走 ASR；若将来某平台暴露字幕轨，可在引擎层单独处理。
"""

import abc
import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from loguru import logger


class ASREngine(abc.ABC):
    """语音识别引擎接口：输入音频路径，输出纯文本文案。"""

    name: str = "unnamed"
    available: bool = True

    @abc.abstractmethod
    async def transcribe(self, audio_path: Path) -> str:
        ...


_REGISTRY: dict[str, ASREngine] = {}


def register_asr(engine: ASREngine) -> None:
    """注册一个 ASR 引擎，之后即可被 `get_asr()` 选用。"""
    _REGISTRY[engine.name] = engine
    logger.info("已注册 ASR 引擎: {}", engine.name)


def get_asr(name: Optional[str] = None) -> ASREngine:
    if name and name in _REGISTRY:
        return _REGISTRY[name]
    if _REGISTRY:
        return next(iter(_REGISTRY.values()))
    return _PlaceholderASR()


class _PlaceholderASR(ASREngine):
    name = "placeholder"
    available = False

    async def transcribe(self, audio_path: Path | None = None) -> str:
        return (
            "（尚未接入 ASR 引擎）\n\n"
            "“提取文案”已打通「解析 → 抽取音频 → 转写」全链路，\n"
            "但还需要一个语音识别引擎才能产出文字。在 parser_asr.py 中：\n"
            "  class MyASR(ASREngine):\n"
            "      name = \"my\"\n"
            "      async def transcribe(self, audio_path): ...\n"
            "  register_asr(MyASR())\n"
            "可选本地 Whisper 或云端识别 API。"
        )


async def extract_audio(source: str, out_path: Path) -> Path:
    """从视频 URL 或本地文件抽取单声道 16k 音频（mp3）。需要 ffmpeg。"""
    cmd = [
        "ffmpeg", "-y", "-i", source,
        "-vn", "-ac", "1", "-ar", "16000", "-f", "mp3",
        str(out_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    code = await proc.wait()
    if code != 0:
        raise RuntimeError("ffmpeg 抽取音频失败（请确认 ffmpeg 已安装且在 PATH 中）")
    return out_path


async def transcribe(source: str) -> str:
    """端到端：抽取音频并转写。source 为视频直链或本地文件路径。"""
    engine = get_asr()
    if not engine.available:
        # 未接入真引擎时直接给出指引，避免无谓地跑 ffmpeg
        return await engine.transcribe(None)
    audio = Path(tempfile.mktemp(suffix=".mp3"))
    try:
        await extract_audio(source, audio)
        return await engine.transcribe(audio)
    finally:
        try:
            audio.unlink()
        except OSError:
            pass
