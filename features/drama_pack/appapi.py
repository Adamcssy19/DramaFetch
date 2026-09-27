from __future__ import annotations

"""果子 App 接口客户端：X-Gorgon 签名 + 随机设备身份。

签名与设备策略移植自果子鉴（guoapp）的 Go 实现：
每次请求对「query 串 + body」做 MD5 混淆生成 X-Gorgon，配合随机生成的
device_id / iid 绕过设备维度的风控（无签名的裸请求只会得到 200 空响应）。
"""

import hashlib
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from loguru import logger

from wreq import Client, Emulation
from wreq.emulation import Platform
from wreq.redirect import Policy

from app.config.paths import APP_DATA_DIR

API_BASE = "https://api5-normal-sinfonlineb.fqnovel.com"
APP_UA = ("com.phoenix.read/73532 (Linux; U; Android 16; zh_CN; 25053RT47C; "
          "Build/BP2A.250605.031.A3; Cronet/TTNetVersion:04657795 2026-01-23 "
          "QuicVersion:c67e9834 2025-09-08)")
MEDIA_REFERER = "https://novel.snssdk.com/"

_BASE_QUERY = {
    "aid": "8662", "app_name": "novelread", "version_code": "73532",
    "version_name": "7.3.5.32", "manifest_version_code": "73532",
    "update_version_code": "73532", "channel": "update_64",
    "device_platform": "android", "os": "android", "ssmix": "a",
    "device_type": "25053RT47C", "device_brand": "Redmi", "language": "zh",
    "os_api": "36", "os_version": "16", "resolution": "1280*2772", "dpi": "520",
    "ac": "wifi",
}

_DEVICE_FILE = APP_DATA_DIR / "hongguo_device.json"


def _rol8(v: int, n: int) -> int:
    v &= 0xFF
    return ((v << n) | (v >> (8 - n))) & 0xFF if n else v


def _rev8(v: int) -> int:
    return int(f"{v & 0xFF:08b}"[::-1], 2)


def _sign(url: str, body: bytes | None) -> dict[str, str]:
    """生成 X-Gorgon / X-Khronos 等签名头（url 需为最终完整地址）。"""
    now = int(time.time())
    payload = bytearray(20)
    rawQuery = url.split("?", 1)[1] if "?" in url else ""
    payload[0:4] = hashlib.md5(rawQuery.encode()).digest()[:4]
    if body:
        payload[4:8] = hashlib.md5(body).digest()[:4]
    payload[12:16] = b"\x00\x06\x0b\x1c"
    payload[16:20] = now.to_bytes(4, "big")
    key = bytes.fromhex("44b9b9d9a4aef9fca493aa757ca3c2c4a496938f")
    for i in range(20):
        payload[i] ^= key[i]
    for i in range(20):
        mixed = _rol8(payload[i], 4) ^ payload[(i + 1) % 20]
        payload[i] = _rev8(mixed) ^ 0xFF ^ 20
    signature = bytes([0x84, 0x04, 0x40, 0x1C, 0, 0]) + bytes(payload)
    headers = {
        "x-khronos": str(now),
        "x-gorgon": signature.hex(),
        "x-ss-req-ticket": str(int(time.time() * 1000)),
    }
    if body:
        headers["x-ss-stub"] = hashlib.md5(body).hexdigest().upper()
    return headers


def _loadDevice() -> tuple[str, str]:
    """设备身份持久化：同一安装保持同一随机设备，降低风控概率。"""
    try:
        data = json.loads(_DEVICE_FILE.read_text(encoding="utf-8"))
        deviceID, installID = str(data["device_id"]), str(data["install_id"])
        if deviceID.isdigit() and installID.isdigit():
            return deviceID, installID
    except Exception:
        pass
    deviceID = str(random.randint(1_000_000_000_000_000_000, 8_999_999_999_999_999_999))
    installID = str(random.randint(1_000_000_000_000_000_000, 8_999_999_999_999_999_999))
    try:
        _DEVICE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DEVICE_FILE.write_text(
            json.dumps({"device_id": deviceID, "install_id": installID}),
            encoding="utf-8")
    except Exception as e:
        logger.debug("果子设备身份保存失败: {}", e)
    return deviceID, installID


def _appQuery() -> str:
    deviceID, installID = _loadDevice()
    q = dict(_BASE_QUERY, device_id=deviceID, iid=installID,
             _rticket=str(int(time.time() * 1000)))
    return urlencode(sorted(q.items()))


class AppApiError(Exception):
    """App 接口访问失败，message 面向日志与调试。"""


@dataclass(frozen=True)
class AppStream:
    url: str
    cencKey: str  # hex，空表示明文
    quality: int  # 竖屏高度，如 1080


async def appVideoModel(vid: str) -> list[AppStream]:
    """取单集全部清晰度的播放地址（CENC 加密流，密钥一并返回）。"""
    from Crypto.Cipher import AES  # 延迟导入，避免无关场景加载

    from .cenc import hongguoContentKey

    body = json.dumps({
        "video_id": str(vid), "content_type": 1,
        "biz_param": {"need_all_video_definition": True, "video_platform": 3},
    }, separators=(",", ":")).encode()
    url = f"{API_BASE}/novel/player/video_model/v1/?{_appQuery()}"

    client = Client(emulation=Emulation(profile=Emulation.OkHttp5, platform=Platform.Android),
                    redirect=Policy.limited(10))
    try:
        headers = {"user-agent": APP_UA, "accept": "application/json",
                   "x-xs-from-web": "0", "sdk-version": "2",
                   "content-type": "application/json; charset=utf-8",
                   **_sign(url, body)}
        response = await client.post(url, body=body, headers=headers)
        raw = await response.bytes()
    except Exception as e:
        raise AppApiError(f"App 接口请求失败: {e}") from e
    finally:
        client.close()

    if not raw:
        raise AppApiError("App 接口返回空响应（风控）")
    try:
        result = json.loads(raw)
    except Exception as e:
        raise AppApiError("App 接口返回格式异常") from e
    if str(result.get("code") or "0") not in ("0",):
        raise AppApiError(f"App 接口错误码 {result.get('code')}")

    model = (result.get("data") or {}).get("video_model")
    if isinstance(model, str):
        try:
            model = json.loads(model)
        except Exception as e:
            raise AppApiError("video_model 解析失败") from e
    streams = (model or {}).get("video_list") or []

    out: list[AppStream] = []
    for row in streams:
        meta = row.get("video_meta") or {}
        addresses: list[str] = []
        for key in ("main_url", "backup_url", "backup_url_1", "backup_url_2"):
            value = str(row.get(key) or "").strip()
            if value.startswith("http"):
                addresses.append(value)
        if not addresses:
            continue
        codec = str(meta.get("codec_type") or "").lower()
        if codec == "bytevc2":  # 该编码解码器兼容性差，跳过
            continue
        encryption = row.get("encrypt_info") or {}
        spade = str(encryption.get("spade_a") or "")
        try:
            cencKey = hongguoContentKey(spade).hex() if spade else ""
        except Exception as e:
            logger.debug("跳过无法解密清晰度 {}: {}", meta.get("definition"), e)
            continue
        quality = 0
        digits = "".join(ch for ch in str(meta.get("definition") or "") if ch.isdigit())
        if digits:
            quality = int(digits)
        for address in addresses:
            out.append(AppStream(url=address, cencKey=cencKey, quality=quality))
    if not out:
        raise AppApiError("App 接口未返回可用的媒体地址")
    return out


def aesEcbKeystreamBlock(key: bytes, block: bytes) -> bytes:
    return AES.new(key, AES.MODE_ECB).encrypt(block)
