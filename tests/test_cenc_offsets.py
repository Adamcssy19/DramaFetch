"""CENC 解密的两个关键不变量回归测试。

这两个 bug 都是「自洽的合成测试」查不出来的，所以这里的夹具**独立实现**
AES-CTR 密钥流（不调用被测代码），并直接校验输出文件的样本表指向正确数据。

1. IV 长度：senc 未使用子样本时，(box size - 头 - 8) / sampleCount 就是每条
   IV 的字节数。早期实现只从 tenc 读（偏移还写错了一位、tenc 又埋在 sinf/schi
   里遍历不到），于是退化成默认 16 —— 红果实际是 8，IV 序列整体错位、解出来
   全是乱码（表现为视频黑屏）。
2. stco 偏移：剪掉 senc/saiz/saio 后 moov 变短、mdat 前移，stco 里的绝对偏移
   必须同步减去 delta，且**必须在最终 serialize 之前改**。否则新 moov 里仍是
   旧偏移，播放器从错位处读数据 —— 同样表现为黑屏/花屏。
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest
from Crypto.Cipher import AES

_REPO = Path(__file__).resolve().parent.parent
for _p in (str(_REPO), str(_REPO / "features")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from drama_pack import cenc  # noqa: E402

KEY = bytes.fromhex("2f67c11c16783701d1b1abb4f3db9ec9")


# ─────────────────── 独立实现的 CENC 加密（不使用被测代码） ───────────────────


def encryptSample(key: bytes, ivSize: int, iv: bytes, plain: bytes) -> bytes:
    """CENC AES-CTR 加密：CTR 是对称的，加密与解密同为异或密钥流。"""
    out = bytearray(len(plain))
    aes = AES.new(key, AES.MODE_ECB)
    hi = iv[0:8]
    lo = int.from_bytes(iv[8:16], "big")
    for k in range((len(plain) + 15) // 16):
        if ivSize == 16:
            block = hi + ((lo + k) & 0xFFFFFFFFFFFFFFFF).to_bytes(8, "big")
        else:
            block = iv + k.to_bytes(8, "big")
        keystream = aes.encrypt(block)
        seg = plain[k * 16:(k + 1) * 16]
        out[k * 16:k * 16 + len(seg)] = bytes(
            a ^ b for a, b in zip(seg, keystream[:len(seg)]))
    return bytes(out)


# ─────────────────────────── 极简 MP4 构造/读取 ───────────────────────────


def _box(typ: str, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + typ.encode("latin1") + payload


def _fullBox(typ: str, version: int, flags: int, payload: bytes) -> bytes:
    return _box(typ, struct.pack(">B", version) + flags.to_bytes(3, "big") + payload)


def _makePlainSamples(count: int, base: int) -> list[bytes]:
    """造出「看起来像长度前缀 NAL」的明文，任何错位都会立刻反映为不相等。"""
    out = []
    for i in range(count):
        head = struct.pack(">I", 16 + i) + bytes([0x40, 0x01])
        body = bytes((base + i * 7 + j) & 0xFF for j in range(32 + i))
        out.append(head + body)
    return out


def _buildMp4(tracks, ivSize: int, mdatStart: int) -> bytes:
    """tracks: [(明文样本列表, IV 列表), ...]；mdatStart 已知，stco 用绝对偏移。"""
    layout = []          # (trackIndex, sampleIndex, 相对 mdat 负载的偏移)
    cursor = 0
    for si in range(max(len(s) for s, _ in tracks)):
        for ti, (samples, _ivs) in enumerate(tracks):
            if si < len(samples):
                layout.append((ti, si, cursor))
                cursor += len(samples[si])

    payload = bytearray(cursor)
    for ti, (samples, ivs) in enumerate(tracks):
        for si, plain in enumerate(samples):
            off = next(o for t, s, o in layout if t == ti and s == si)
            payload[off:off + len(plain)] = encryptSample(KEY, ivSize, ivs[si], plain)

    traks = bytearray()
    for ti, (samples, ivs) in enumerate(tracks):
        entries = [(mdatStart + o, len(samples[si]))
                   for t, si, o in layout if t == ti]
        assert len(entries) == len(samples)

        stsz = _fullBox("stsz", 0, 0, struct.pack(">II", 0, len(samples))
                        + b"".join(struct.pack(">I", sz) for _o, sz in entries))
        stco = _fullBox("stco", 0, 0, struct.pack(">I", len(entries))
                        + b"".join(struct.pack(">I", o) for o, _sz in entries))
        stsc = _fullBox("stsc", 0, 0, struct.pack(">I", 1) + struct.pack(">III", 1, 1, 1))
        senc = _fullBox("senc", 0, 0, struct.pack(">I", len(ivs)) + b"".join(ivs))
        saiz = _fullBox("saiz", 0, 0, b"\x00" + struct.pack(">I", len(ivs))
                        + bytes([ivSize]) * len(ivs))
        saio = _fullBox("saio", 0, 0, struct.pack(">I", 0))

        # tenc 埋在 sinf/schi 里 —— 正是早期实现遍历不到它的原因
        tenc = _fullBox("tenc", 0, 0, b"\x00\x00\x01" + bytes([ivSize]) + b"\x11" * 16)
        sinf = _box("sinf", _box("frma", b"hvc1")
                    + _fullBox("schm", 0, 0, b"cenc" + struct.pack(">I", 0x10000))
                    + _box("schi", tenc))
        stsd = _fullBox("stsd", 0, 0, struct.pack(">I", 1)
                        + _box("encv", b"\x00" * 78 + sinf))

        stbl = _box("stbl", stsd + stsz + stsc + stco + senc + saiz + saio)
        traks += _box("trak", _box("mdia", _box("minf", stbl)))

    moov = _box("moov", _box("mvhd", b"\x00" * 100) + bytes(traks))
    return _box("ftyp", b"isomiso2mp41") + moov + _box("mdat", bytes(payload))


def buildCencFile(tracks, ivSize: int = 8):
    """两遍组装：先占位算出 mdat 负载起始位置，再用真实绝对偏移重建。

    stco 指向的是样本数据本身，即 mdat 负载起点 + 样本在负载内的偏移。
    """
    placeholder = _buildMp4(tracks, ivSize, mdatStart=0)
    payloadStart = placeholder.index(b"mdat") + 4   # 'mdat' 四字节类型之后即负载
    return _buildMp4(tracks, ivSize, mdatStart=payloadStart)


def _iterBoxes(data: bytes, start: int, end: int):
    off = start
    while off + 8 <= end:
        size = struct.unpack_from(">I", data, off)[0]
        typ = data[off + 4:off + 8].decode("latin1")
        if size < 8 or off + size > end:
            break
        yield typ, off, size
        off += size


def _trakSpans(data: bytes) -> list[tuple[int, int]]:
    """moov 内每个 trak 的 (起始, 长度)。"""
    moov = next(b for b in _iterBoxes(data, 0, len(data)) if b[0] == "moov")
    return [(off, size) for typ, off, size in
            _iterBoxes(data, moov[1] + 8, moov[1] + moov[2]) if typ == "trak"]


def _descend(data: bytes, start: int, size: int, names: tuple[str, ...]):
    """从某个 box（起点/长度）出发，逐层取指定名字的子 box，返回其 payload 范围。"""
    spans = [(start + 8, start + size)]
    for name in names:
        nxt = []
        for s, e in spans:
            for typ, off, boxSize in _iterBoxes(data, s, e):
                if typ == name:
                    nxt.append((off + 8, off + boxSize))
        spans = nxt
        if not spans:
            return None
    return spans[0]


def readSamples(data: bytes, trackIndex: int) -> list[bytes]:
    """独立实现：按 stsz/stsc/stco 从文件里取出每个样本。"""
    trakOff, trakSize = _trakSpans(data)[trackIndex]
    stblOff, stblSize = _descend(data, trakOff, trakSize, ("mdia", "minf", "stbl"))

    def child(typ):
        for t, off, size in _iterBoxes(data, stblOff, stblOff + stblSize):
            if t == typ:
                return off, size
        raise AssertionError(f"stbl 内缺少 {typ}")

    stszOff, _ = child("stsz")
    stcoOff, _ = child("stco")
    stscOff, _ = child("stsc")

    sampleSize = struct.unpack_from(">I", data, stszOff + 12)[0]
    count = struct.unpack_from(">I", data, stszOff + 16)[0]
    sizes = ([struct.unpack_from(">I", data, stszOff + 20 + i * 4)[0]
              for i in range(count)]
             if sampleSize == 0 else [sampleSize] * count)
    nc = struct.unpack_from(">I", data, stcoOff + 12)[0]
    chunkOffs = [struct.unpack_from(">I", data, stcoOff + 16 + i * 4)[0]
                 for i in range(nc)]
    ns = struct.unpack_from(">I", data, stscOff + 12)[0]
    stscTab = [struct.unpack_from(">III", data, stscOff + 16 + i * 12)
               for i in range(ns)]
    perChunk = {}
    for i, (first, per, _d) in enumerate(stscTab):
        nxt = stscTab[i + 1][0] if i + 1 < len(stscTab) else nc + 1
        for ci in range(first - 1, nxt - 1):
            perChunk[ci] = per

    out, si = [], 0
    for ci in range(nc):
        off = chunkOffs[ci]
        for _ in range(perChunk.get(ci, 1)):
            if si >= count:
                break
            out.append(bytes(data[off:off + sizes[si]]))
            off += sizes[si]
            si += 1
    return out


# ─────────────────────────────── 测试 ───────────────────────────────


def _makeTracks(ivSize: int):
    ivs1 = [bytes([0x92, 0xF8, 0x1C, 0xF4, 0xA2, 0x53, 0x60, 0x3A + i])
            for i in range(4)]
    ivs2 = [bytes([0x44, 0x58, 0x8E, 0x07, 0x77, 0xB1, 0x1D, 0xD7 + i])
            for i in range(3)]
    if ivSize == 16:
        ivs1 = [iv + b"\x00" * 8 for iv in ivs1]
        ivs2 = [iv + b"\x00" * 8 for iv in ivs2]
    return [(_makePlainSamples(4, 0x10), ivs1),
            (_makePlainSamples(3, 0x90), ivs2)]


@pytest.mark.parametrize("ivSize", [8, 16])
def test_samples_are_correctly_decrypted_at_table_offsets(ivSize: int):
    """核心不变量：按输出文件自己的样本表读出来的数据，必须等于原始明文。

    这条同时覆盖两个历史 bug：
    - IV 长度取错 → 明文不等
    - stco 未随 moov 缩短而修正 → 从错位处读数据，明文不等
    """
    tracks = _makeTracks(ivSize)
    encrypted = buildCencFile(tracks, ivSize=ivSize)

    plain = cenc.decryptCencMp4(bytearray(encrypted), KEY)

    for ti, (samples, _ivs) in enumerate(tracks):
        assert readSamples(plain, ti) == samples, f"track {ti} 样本内容不一致"


@pytest.mark.parametrize("ivSize", [8, 16])
def test_iv_size_comes_from_senc_arithmetic(ivSize: int):
    """senc 未用子样本时，IV 长度应由 senc 自身尺寸反推，不依赖能否读到 tenc。"""
    tracks = _makeTracks(ivSize)
    data = bytearray(buildCencFile(tracks, ivSize=ivSize))
    top = cenc._parseBoxes(data, 0, len(data))
    senc = next(b for b in cenc._walk(top) if b["typ"] == "senc")
    assert cenc._resolveIvSize(data, senc, 16) == ivSize


def test_encryption_markers_are_removed():
    """输出不应再带 encv/enca/senc/saiz/saio，且 stsd 换回 hvc1。"""
    tracks = _makeTracks(8)
    plain = cenc.decryptCencMp4(bytearray(buildCencFile(tracks)), KEY)
    for marker in (b"encv", b"senc", b"saiz", b"saio", b"sinf"):
        assert marker not in plain, f"输出里残留 {marker!r}"
    assert b"hvc1" in plain


def test_chunk_offsets_are_shifted_by_moov_delta():
    """显式校验 stco 平移量：输出里首个样本的偏移应指向该样本的真实位置。"""
    tracks = _makeTracks(8)
    encrypted = buildCencFile(tracks, ivSize=8)
    plain = cenc.decryptCencMp4(bytearray(encrypted), KEY)

    for ti, (samples, _ivs) in enumerate(tracks):
        trakOff, trakSize = _trakSpans(plain)[ti]
        stblOff, stblSize = _descend(plain, trakOff, trakSize, ("mdia", "minf", "stbl"))
        stcoOff = next(o for t, o, _s in _iterBoxes(plain, stblOff, stblOff + stblSize)
                       if t == "stco")
        first = struct.unpack_from(">I", plain, stcoOff + 16)[0]
        size = len(samples[0])
        assert plain[first:first + size] == samples[0]
