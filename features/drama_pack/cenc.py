from __future__ import annotations

"""果子 CENC-AES-CTR 加密 MP4 解密。

算法移植自 hongguo-downloader（GPL-3.0）与果子鉴（guoapp）：
- spade_a → hongguoContentKey 派生 16 字节 AES 密钥
- senc box 提供每个 sample 的 8 字节 IV
- keystream = AES-ECB(key, IV || counter)，与密文异或
- 输出前重建 moov：剪除加密相关 box、stsd 中 encv/enca 换回明文编码
"""

import struct
from base64 import b64decode

from Crypto.Cipher import AES

_CONTAINER = {"moov", "trak", "mdia", "minf", "stbl", "stsd", "edts", "dinf", "udta", "meta",
              "sinf", "schi"}


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


def _decryptSample(key: bytes, ivSize: int, iv: bytes,
                   cipher: bytes, subsamples) -> bytes:
    """单 sample CENC-AES-CTR 解密。

    - ivSize 8：counter block = IV(8) || counter(8, 大端，从 0 累加)
    - ivSize 16：counter block = IV[0:8] || (IV[8:16] + blockCounter) 大端
    - subsamples 为 None 表示整段加密；否则按 (clear, encrypted) 子段处理，
      明文段原样拷贝，加密段做 CTR 异或，block 计数器在子段间连续。
    """
    out = bytearray(len(cipher))
    blockCounter = 0
    hi = iv[0:8] if ivSize == 16 else b""
    lo = int.from_bytes(iv[8:16], "big") if ivSize == 16 else 0
    if not subsamples:
        subsamples = [(0, len(cipher))]

    pos = 0
    for clear, enc in subsamples:
        if clear:
            out[pos:pos + clear] = cipher[pos:pos + clear]
            pos += clear
        if enc:
            nBlocks = (enc + 15) // 16
            stream = bytearray(16 * nBlocks)
            for k in range(nBlocks):
                if ivSize == 16:
                    counter = (lo + blockCounter) & 0xFFFFFFFFFFFFFFFF
                    block = hi + counter.to_bytes(8, "big")
                else:
                    block = iv + blockCounter.to_bytes(8, "big")
                blockCounter += 1
                stream[k * 16:k * 16 + 16] = block
            keystream = AES.new(key, AES.MODE_ECB).encrypt(bytes(stream))
            seg = cipher[pos:pos + enc]
            out[pos:pos + enc] = bytes(a ^ b for a, b in zip(seg, keystream[:enc]))
            pos += enc
    return bytes(out)


def _parseSenc(data, box, ivSize) -> list:
    """解析 senc box：返回逐 sample 条目 [(iv, subsamples_or_None), ...]。"""
    base = box["off"] + box["hdr"]
    flags = struct.unpack_from(">I", data, base)[0] & 0x00FFFFFF
    count = struct.unpack_from(">I", data, base + 4)[0]
    useSub = bool(flags & 0x02)
    p = base + 8
    entries = []
    for _ in range(count):
        iv = bytes(data[p:p + ivSize])
        p += ivSize
        subs = None
        if useSub:
            nSub = struct.unpack_from(">H", data, p)[0]
            p += 2
            subs = []
            for _ in range(nSub):
                clear = struct.unpack_from(">H", data, p)[0]
                p += 2
                encrypted = struct.unpack_from(">I", data, p)[0]
                p += 4
                subs.append((clear, encrypted))
        entries.append((iv, subs))
    return entries


def _resolveIvSize(data, sencBox, tencIvSize: int) -> int:
    """确定每个 sample 的 IV 长度。

    优先用 senc 自身的尺寸反推：未启用子样本时，
    (box size - 头 - 8) / sampleCount 就是每条 IV 的字节数（只能是 8 或 16）。
    这比读 tenc 更可靠 —— tenc 埋在 sinf/schi 里，盒子遍历容易漏掉，
    一旦取不到就会退化成默认值，把整条 IV 序列读错位（表现为视频黑屏）。

    红果实际用的是 8 字节 IV，而格式默认值常被写成 16，两者差一个字节
    就会错位，所以这里以 senc 反推为准、tenc 仅作兜底。
    """
    if sencBox is not None:
        base = sencBox["off"] + sencBox["hdr"]
        flags = struct.unpack_from(">I", data, base)[0] & 0x00FFFFFF
        count = struct.unpack_from(">I", data, base + 4)[0]
        if count and not (flags & 0x02):
            per = (sencBox["size"] - sencBox["hdr"] - 8) // count
            if per in (8, 16):
                return per
    return tencIvSize if tencIvSize in (8, 16) else 16


def decryptCencMp4(data: bytearray, key: bytes) -> bytes:
    """就地解密 CENC 加密的 MP4 字节，返回可播放的完整 MP4。"""
    total = len(data)
    top = _parseBoxes(data, 0, total)
    moov = next((b for b in top if b["typ"] == "moov"), None)
    if moov is None:
        raise ValueError("MP4 中没有 moov box")

    # tenc 提供 default_Per_Sample_IV_Size：box 头之后是
    # version(1)+flags(3) | reserved(1) | pattern(1) | isProtected(1) | IVSize(1)
    # 所以 IVSize 在 hdr+7。
    tencIvSize = 0
    for box in _walk(top):
        if box["typ"] == "tenc" and box["size"] >= box["hdr"] + 8:
            tencIvSize = data[box["off"] + box["hdr"] + 7]
            break

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
        ivSize = _resolveIvSize(data, senc, tencIvSize)
        sencEntries = _parseSenc(data, senc, ivSize) if senc else []
        tracks.append({"sizes": sizes, "offs": offs, "senc": sencEntries,
                       "ivSize": ivSize})

    for track in tracks:
        for i, off in enumerate(track["offs"]):
            size = track["sizes"][i]
            if off + size > total or i >= len(track["senc"]):
                continue
            iv, subs = track["senc"][i]
            if not iv:
                continue
            data[off:off + size] = _decryptSample(
                key, track["ivSize"], iv, data[off:off + size], subs)

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
        # 有补丁的 box 必须优先用补丁：stsd 会被解析出子节点（样本条目本身
        # 就是一个 box），若按「非叶子」分支去拼子节点，就会绕开补丁、
        # 把 encv/enca + sinf/tenc 原样留下 —— 容器仍声明加密，普通播放器
        # 直接黑屏（只有容错强的 ffmpeg 系播放器能解）。
        patched = patches.get(box["off"])
        if patched is not None:
            return patched
        if not box["children"]:
            return bytes(data[box["off"]:box["off"] + box["size"]])
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

    # moov 因为剪掉 senc/saiz/saio 而变短，mdat 会整体前移 delta 字节，
    # 所以 stco/co64 里的绝对偏移必须同步减去 delta。
    #
    # 注意顺序：必须改完再重新 serialize 一次。stco 是叶子 box，serialize
    # 时直接从 data 里读它的字节 —— 若先 serialize 再改 data，新 moov 里
    # 仍是旧偏移，播放器就会从错位处读数据（表现为黑屏/花屏）。
    # 偏移字段定长 4/8 字节，改值不会改变 moov 长度，因此 delta 依然有效。
    if delta:
        for box in walkChildren(tree):
            if box["typ"] == "stco":
                width = 4
            elif box["typ"] == "co64":
                width = 8
            else:
                continue
            nc = struct.unpack_from(">I", data, box["off"] + 12)[0]
            for i in range(nc):
                pos = box["off"] + 16 + i * width
                fmt = ">I" if width == 4 else ">Q"
                value = struct.unpack_from(fmt, data, pos)[0]
                if value >= delta:
                    struct.pack_into(fmt, data, pos, value - delta)
        first = serialize(tree)

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
