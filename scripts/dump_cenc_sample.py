"""抓一集原始（未解密）CENC 流，用于离线验证解密实现。

解密出问题（黑屏 / 花屏 / 音频乱码）时，先在真机上拿到原始密文样本，
再用 ffmpeg 验证解密产物，比在应用里反复重下快得多：

    uv run python scripts/dump_cenc_sample.py <seriesId> [集号]

输出：
  %TEMP%\\raw_cenc.mp4       原始密文（可直接喂给 drama_pack.cenc 调试）
  %TEMP%\\dec_cenc.mp4       用当前实现解密后的产物

验证（本机装了 ffmpeg 时）：
  ffmpeg -v error -i %TEMP%\\dec_cenc.mp4 -f null -     # 无输出即全部正常
  再确认产物里不应再有 encv/enca/sinf/tenc 残留。

注意：解密是在下载时就地覆盖 mdat 的，旧文件无法事后修复（senc 已从
moov 中删除、明文也无法还原），必须重新下载。
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
for _p in (str(_REPO), str(_REPO / "features")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from drama_pack import api, cenc  # noqa: E402

# 加密流的 CDN 只认这个 referer，用果子站点域名会 403
CENC_REFERER = "https://novel.snssdk.com/"


def _dumpMarkers(data: bytes) -> None:
    print("--- 加密相关标记 ---")
    for tag in (b"encv", b"enca", b"sinf", b"tenc", b"senc", b"saiz", b"saio",
                b"hvc1", b"mp4a"):
        print(f"  {tag.decode():5s}: {data.count(tag)}")


async def dump(seriesId: str, pick: int) -> int:
    detail = await api.detail(seriesId)
    if pick < 1 or pick > len(detail.vidList):
        print(f"集号超出范围：该剧共 {len(detail.vidList)} 集")
        return 2
    vid = detail.vidList[pick - 1]
    stream = await api.resolveStream(seriesId, vid, title=detail.title,
                                     pick=pick, channel="app")
    print(f"剧集: {detail.title} | 第 {pick} 集 | 清晰度 {stream.quality}")
    if not stream.cencKey:
        print("该流未加密，无需解密验证")
        return 3

    client = api.buildClient(userAgent=api.BROWSER_UA, timeout=60)
    try:
        response = await client.get(stream.url, headers={"referer": CENC_REFERER})
        try:
            response.raise_for_status()
            chunks = []
            async for chunk in response.stream():
                if chunk:
                    chunks.append(chunk)
            raw = b"".join(chunks)
        finally:
            response.close()
    finally:
        client.close()

    temp = Path(os.environ.get("TEMP", "."))
    rawPath = temp / "raw_cenc.mp4"
    rawPath.write_bytes(raw)
    print(f"\n原始密文: {rawPath} ({len(raw)} 字节)")
    _dumpMarkers(raw)

    plain = cenc.decryptCencMp4(bytearray(raw), bytes.fromhex(stream.cencKey))
    decPath = temp / "dec_cenc.mp4"
    decPath.write_bytes(plain)
    print(f"\n解密产物: {decPath} ({len(plain)} 字节)")
    _dumpMarkers(plain)
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    seriesId = sys.argv[1]
    pick = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    return asyncio.run(dump(seriesId, pick))


if __name__ == "__main__":
    raise SystemExit(main())
