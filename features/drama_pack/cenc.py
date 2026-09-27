from __future__ import annotations

"""红果 CENC-AES-CTR 加密 MP4 解密。

算法移植自 hongguo-downloader（GPL-3.0）与红果鉴（guoapp）：
- spade_a → hongguoContentKey 派生 16 字节 AES 密钥
- senc box 提供每个 sample 的 8 字节 IV
- keystream = AES-ECB(key, IV || counter)，与密文异或
- 输出前重建 moov：剪除加密相关 box、stsd 中 encv/enca 换回明文编码
"""

import struct
from base64 import b64decode

from Crypto.Cipher import AES

_CONTAINER = {"moov", "trak", "mdia", "minf", "stbl", "edts", "dinf", "udta", "meta"}


def hongguoContentKey(value: str) -> bytes:
    """spade_a 编码串 → 16 字节 AES 密钥。"""
    value = value.strip()
    try:
        raw = b64decode(value, validate=True)
    except Exception:
        raw = b64decode(value + "=" * (-len(value) % 4))
    if len(raw) < 3:
        raise ValueError("密钥数据过短")
    tagLength = (raw[0] ^ raw[1] ^ raw[2]) - 48
    contentLength = len(raw) - tagLength - 1
    if tagLength < 1 or contentLength < 33 or contentLength >= len(raw):
        raise ValueError("密钥结构无效")
    seed = raw[-tagLength - 2] ^ raw[-tagLength - 1]
    tag = bytes(raw[len(raw) - tagLength + i] ^ seed for i in range(tagLength))
    if tag in (b"app_v2", b"web_v2"):
        raise ValueError("密钥版本暂不支持")
    decoded = bytearray(contentLength)
    prevEven, prevOdd = 250, 85
    for i, cur in enumerate(raw[1:1 + contentLength]):
        prev = prevEven if i % 2 == 0 else prevOdd
        if i % 2 == 0:
            prevEven = cur
        else:
            prevOdd = cur
        decoded[i] = ((prev ^ cur) - 21 - bin(i).count("1")) & 0xFF
    padding = int(chr(decoded[0]), 36)
    if contentLength - padding - 1 != 32:
        raise ValueError("密钥内容无效")
    key = bytes.fromhex(decoded[1:33].decode("ascii"))
    if len(key) != 16:
        raise ValueError("不是有效的 AES-128 密钥")
    return key


def _parseBoxes(data, start, end):
    boxes = []
    off = start
    while off + 8 <= end:
        size = struct.unpack_from(">I", data, off)[0]
        typ = data[off + 4:off + 8].decode("latin1")
        hdr = 8
        if size == 1:
            size = struct.unpack_from(">Q", data, off + 8)[0]
            hdr = 16
        elif size == 0:
            size = end - off
        if size < hdr or off + size > end:
            break
        children = _parseBoxes(data, off + hdr, off + size) if typ in _CONTAINER else None
        boxes.append({"typ": typ, "off": off, "size": size, "hdr": hdr,
                      "children": children})
        off += size
    return boxes


def _walk(boxes):
    for box in boxes:
        if box["children"]:
            yield from _walk(box["children"])
        yield box


def _decryptSample(key: bytes, nonce: bytes, cipher: bytes) -> bytes:
    blocks = (len(cipher) + 15) // 16
    streamIn = bytearray(16 * blocks)
    for k in range(blocks):
        streamIn[k * 16:k * 16 + 8] = nonce[:8]
        streamIn[k * 16 + 8:k * 16 + 16] = k.to_bytes(8, "big")
    keystream = AES.new(key, AES.MODE_ECB).encrypt(bytes(streamIn))
    return bytes(c ^ ks for c, ks in zip(cipher, keystream))


def decryptCencMp4(data: bytearray, key: bytes) -> bytes:
    """就地解密 CENC 加密的 MP4 字节，返回可播放的完整 MP4。"""
    total = len(data)
    top = _parseBoxes(data, 0, total)
    moov = next((b for b in top if b["typ"] == "moov"), None)
    if moov is None:
        raise ValueError("MP4 中没有 moov box")

    tracks = []
    for stbl in (b for b in _walk(top) if b["typ"] == "stbl"):
        get = lambda t: next((c for c in stbl["children"] if c["typ"] == t), None)
        stsz, stco, stsc, senc = get("stsz"), get("stco"), get("stsc"), get("senc")
        if not (stsz and stco and stsc):
            continue
        sampleSize = struct.unpack_from(">I", data, stsz["off"] + 12)[0]
        count = struct.unpack_from(">I", data, stsz["off"] + 16)[0]
        sizes = ([struct.unpack_from(">I", data, stsz["off"] + 20 + i * 4)[0]
                  for i in range(count)]
                 if sampleSize == 0 else [sampleSize] * count)
        nc = struct.unpack_from(">I", data, stco["off"] + 12)[0]
        chunkOffs = [struct.unpack_from(">I", data, stco["off"] + 16 + i * 4)[0]
                     for i in range(nc)]
        ns = struct.unpack_from(">I", data, stsc["off"] + 12)[0]
        stscTab = [struct.unpack_from(">III", data, stsc["off"] + 16 + i * 12)
                   for i in range(ns)]
        ivs = []
        if senc:
            sc = struct.unpack_from(">I", data, senc["off"] + 12)[0]
            ivs = [data[senc["off"] + 16 + i * 8: senc["off"] + 24 + i * 8]
                   for i in range(sc)]
        chunkSpc = {}
        for i, (first, perChunk, _) in enumerate(stscTab):
            nxt = stscTab[i + 1][0] if i + 1 < len(stscTab) else nc + 1
            for ci in range(first - 1, nxt - 1):
                chunkSpc[ci] = perChunk
        offs, si = [], 0
        for ci in range(nc):
            off = chunkOffs[ci]
            for _ in range(chunkSpc.get(ci, 1)):
                if si >= count:
                    break
                offs.append(off)
                off += sizes[si]
                si += 1
        tracks.append({"sizes": sizes, "offs": offs, "ivs": ivs})

    for track in tracks:
        for i, off in enumerate(track["offs"]):
            size = track["sizes"][i]
            if off + size > total or i >= len(track["ivs"]):
                continue
            data[off:off + size] = _decryptSample(
                key, track["ivs"][i], data[off:off + size])

    def clone(box):
        return {"typ": box["typ"], "off": box["off"], "size": box["size"],
                "hdr": box["hdr"],
                "children": [clone(c) for c in box["children"]] if box["children"] else None}

    def prune(box):
        if not box["children"]:
            return box
        box["children"] = [prune(c) for c in box["children"]
                           if c["typ"] not in ("senc", "saio", "saiz", "sgpd", "sbgp")]
        return box

    tree = prune(clone(moov))

    def walkChildren(box):
        for c in box.get("children") or []:
            yield c
            yield from walkChildren(c)

    patches = {}
    for box in walkChildren(tree):
        if box["typ"] != "stsd":
            continue
        content = box["off"] + 8
        count = struct.unpack_from(">I", data, content + 4)[0]
        p = content + 8
        entries = []
        for _ in range(count):
            entrySize = struct.unpack_from(">I", data, p)[0]
            entryType = data[p + 4:p + 8].decode("latin1")
            if entryType in ("encv", "enca"):
                newType = b"hvc1" if entryType == "encv" else b"mp4a"
                hdrSize = 78 if entryType == "encv" else 28
                entry = bytearray(8 + hdrSize)
                struct.pack_into(">I", entry, 0, 0)
                entry[4:8] = newType
                entry[8:] = data[p + 8:p + 8 + hdrSize]
                extra = bytearray()
                q = p + 8 + hdrSize
                while q + 8 <= p + entrySize:
                    sub = struct.unpack_from(">I", data, q)[0]
                    subType = data[q + 4:q + 8].decode("latin1")
                    if sub == 1:
                        sub = struct.unpack_from(">Q", data, q + 8)[0]
                    elif sub == 0:
                        sub = p + entrySize - q
                    if subType != "sinf":
                        extra += data[q:q + sub]
                    q += sub
                full = bytearray(bytes(entry) + bytes(extra))
                struct.pack_into(">I", full, 0, len(full))
                entries.append(bytes(full))
            else:
                entries.append(bytes(data[p:p + entrySize]))
            p += entrySize
        stsdHdr = bytearray(data[box["off"]:content + 8])
        struct.pack_into(">I", stsdHdr, 12, len(entries))
        fullStsd = bytearray(stsdHdr + b"".join(entries))
        struct.pack_into(">I", fullStsd, 0, len(fullStsd))
        patches[box["off"]] = bytes(fullStsd)

    def serialize(box):
        if not box["children"]:
            return (patches.get(box["off"])
                    or bytes(data[box["off"]:box["off"] + box["size"]]))
        body = b"".join(serialize(c) for c in box["children"])
        hdr = bytearray(data[box["off"]:box["off"] + box["hdr"]])
        if box["hdr"] == 8:
            struct.pack_into(">I", hdr, 0, 8 + len(body))
        else:
            struct.pack_into(">I", hdr, 0, 1)
            struct.pack_into(">Q", hdr, 8, 16 + len(body))
        return bytes(hdr) + body

    first = serialize(tree)
    delta = moov["size"] - len(first)
    for box in walkChildren(tree):
        if box["typ"] != "stco":
            continue
        nc = struct.unpack_from(">I", data, box["off"] + 12)[0]
        for i in range(nc):
            pos = box["off"] + 16 + i * 4
            value = struct.unpack_from(">I", data, pos)[0]
            if value >= delta:
                struct.pack_into(">I", data, pos, value - delta)

    out, off = [], 0
    while off < total:
        size = struct.unpack_from(">I", data, off)[0]
        typ = data[off + 4:off + 8].decode("latin1")
        if size == 1:
            size = struct.unpack_from(">Q", data, off + 8)[0]
        elif size == 0:
            size = total - off
        out.append(first if typ == "moov" else bytes(data[off:off + size]))
        off += size
    return b"".join(out)
