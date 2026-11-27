#!/usr/bin/env python3
"""KC-10 Extender（Kuoyi 2026-11-27）：用原版 KC135.SH 改，加油機制和加油員視角照 KC-135-16。

步驟（全部照 KC-135 的工具，只換常數）：
  1. 拿掉外側兩具翼下引擎（KC-10 只有兩具翼下引擎）：三個 LOD 裡全部頂點都在 |x| 66..82、up ≤ 1 的面
     改成 `38 rel` 跳過。
  2. kc135_gray：起落架裁短、內側引擎艙上提、灰色塗裝，但機身色 153 → BODY（深一點的灰）。
  3. sh_scale：整架等比例放大 S = 4/3（KC-10 55.4 m / KC-135 41.5 m）。
  4. kc135_refuel：硬桿樞紐、機腹燈、尾燈、零件標頭、F2 半徑換成放大後的值；硬桿本身長度和加油框不變。
  5. 尾引擎：垂直尾翼根部的十二角形引擎艙（左右兩半），掛在三個 LOD 的垂直尾翼上：
     眼睛在右邊（x ≥ 0）時畫 左半 → 垂直尾翼（含方向舵）→ 右半，左邊時反過來，
     尾翼根部搬到引擎艙頂（KC-10 的尾翼坐在引擎上）。
     眼睛低於水平尾翼時改成在整架飛機最前面畫（被機身、水平尾翼蓋住），尾翼位置那份收成一點。
  6. 貼圖名稱 _kc135.PIC → _kc10.PIC（同樣 14 byte），PIC 綠色組 95..111 平移到灰色組 +SHIFT（最深 159）。
用法：python3 kc10.py 原版KC135.SH 輸出KC10.SH 原版_KC135.PIC 輸出_KC10.PIC [預覽.SH]
"""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, insert_blocks
import kc135_refuel as R
import kc135_gray as G
import sh_scale

S = 4 / 3
BODY = 155                       # KC-135 是 153；KC-10 稍微深一點
SHIFT = 50                       # PIC 綠色組 95..111 → 145..159（KC-135 是 +48）
C_NAC, C_HOLE = BODY, 158
NAC_SLOT = 700                   # 尾引擎頂點槽（硬桿用 600..，KC-135 原本最多 590）
OUTER_X, OUTER_UP = (66, 82), 1  # 外側引擎艙＋吊架（原版座標）
LOD_BUFS = ((0x82, 491, 0x42BC), (0x4C71, 269, 0x6B38), (0x6B38, 97, 0x73E4))
FIN6C = 0x346B                   # 主 LOD：6C 眼睛 x ≥ 0 → 左面尾翼(0x3478) / 右面尾翼(0x3538)，後面 38 → 0x363F
FIN_FACES = ((0x67E0, 0x680E), (0x7141, 0x7167))   # 中、低 LOD 的兩片尾翼面
# 尾引擎（原版座標，之後乘 S）：中心 up 17、半徑 5（底部貼在機背 up 12），進氣口 fwd −66、噴嘴 −114
NAC_UC = 17
NAC_RINGS = ((-66, 3.7), (-68, 4.6), (-72, 5.0), (-100, 5.0), (-108, 4.3), (-114, 3.4))
NSIDE = 12
HIDE_U = 10                      # 原版座標：眼睛低於這個高度（水平尾翼 8..11、機背 12）就先畫尾引擎
FIN_ROOT = NAC_UC + 5            # 尾翼根部搬到引擎艙頂
NODE_LEN = {0x06: 18, 0x0C: 14, 0x0E: 14, 0x10: 14, 0x6C: 10}
F_FLAT = 0x0461                  # u16 索引 + 背面剔除 + 打光 + 單色；平面點用 i16（放大後超過 i8）


def sc(v): return sh_scale.sc(v, S)


def code_of(d):
    pe, opt, secs = pe_sections(d); code = next(s for s in secs if s['name'] == 'CODE')
    return pe, secs, code, bytearray(d[code['ro']:code['ro'] + code['vs']])


def face_end(c, p):
    fl = struct.unpack_from('<H', c, p + 1)[0]; q = p + 5
    if fl & 0x60: q += 6 + (3 if fl & 0x200 else 6)
    k = c[q]; q += 1 + (2 * k if fl & 0x400 else k)
    if fl & 4: q += k * (2 if fl & 0x100 else 4)
    return q


def remove_outer(d):
    d = bytearray(d); pe, secs, code, c = code_of(d)
    ops, unk, _ = sh_scale.walk(c)
    n = 0
    for a, nv, lim in LOD_BUFS:
        V = [struct.unpack_from('<hhh', c, a + 6 + 6 * i) for i in range(nv)]
        for p, t in sorted(ops.items()):
            if t != 'FC' or not a < p < lim: continue
            fl = struct.unpack_from('<H', c, p + 1)[0]; q = p + 5
            if fl & 0x60: q += 6 + (3 if fl & 0x200 else 6)
            k = c[q]; q += 1
            idx = [struct.unpack_from('<H', c, q + 2 * i)[0] for i in range(k)] if fl & 0x400 else list(c[q:q + k])
            if not all(i < nv for i in idx): continue
            P = [V[i] for i in idx]
            if all(OUTER_X[0] <= abs(v[0]) <= OUTER_X[1] and v[2] <= OUTER_UP for v in P):
                e = face_end(c, p)
                c[p] = 0x38; struct.pack_into('<h', c, p + 1, e - (p + 3)); c[p + 3:e] = b'\x1E' * (e - p - 3); n += 1
    R.check_relocs(bytes(d), pe, code, c)
    d[code['ro']:code['ro'] + code['vs']] = c
    print('outer engine faces removed', n)
    return bytes(d)


def nacelle():
    """回傳 (82 緩衝 bytes, 左半面 bytes, 右半面 bytes)；座標已放大。"""
    V = []
    def vert(x, u, f): V.append((x, u, f)); return NAC_SLOT + len(V) - 1
    rings = []
    for f, r in NAC_RINGS:
        ring = []
        for k in range(NSIDE):
            a = 2 * math.pi * k / NSIDE
            ring.append(vert(sc(r * math.sin(a)), sc(NAC_UC + r * math.cos(a)), sc(f)))
        rings.append(ring)
    P = lambda i: V[i - NAC_SLOT]
    axis_u = NAC_UC * S

    def face(idx, out):
        """out = 朝外的大概方向；照 (B−A)×(C−A) 排頂點順序，法向量用三點叉積。"""
        A, B, C = P(idx[0]), P(idx[1]), P(idx[2])
        e1 = [B[t] - A[t] for t in range(3)]; e2 = [C[t] - A[t] for t in range(3)]
        n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]]
        if sum(n[t] * out[t] for t in range(3)) < 0: n = [-k for k in n]; idx = idx[::-1]
        L = math.sqrt(sum(k * k for k in n)); n = [int(round(k / L * 32767)) for k in n]
        b = bytearray(b'\xFC') + struct.pack('<HH', F_FLAT, C_HOLE if out[1] == 0 and out[0] == 0 else C_NAC)
        b += struct.pack('<3h', *n) + struct.pack('<3h', *A) + bytes([len(idx)])
        b += b''.join(struct.pack('<H', i) for i in idx)
        return bytes(b)

    halves = []
    for sx in (-1, 1):
        ks = list(range(0, NSIDE // 2 + 1))                      # 0（上）..6（下）
        if sx < 0: ks = [0] + list(range(NSIDE - 1, NSIDE // 2 - 1, -1))
        fb = bytearray()
        for ri in range(len(rings) - 1):
            for j in range(len(ks) - 1):
                q = [rings[ri][ks[j]], rings[ri][ks[j + 1]], rings[ri + 1][ks[j + 1]], rings[ri + 1][ks[j]]]
                q = list(dict.fromkeys(q))
                if len(q) < 3: continue
                cen = [sum(P(i)[t] for i in q) / len(q) for t in range(3)]
                fb += face(q, (cen[0], cen[1] - axis_u, 0))
        fb += face([rings[0][k] for k in ks], (0, 0, 1))         # 進氣口（深色）
        fb += face([rings[-1][k] for k in ks], (0, 0, -1))       # 噴嘴（深色）
        halves.append(bytes(fb))
    buf = bytearray(b'\x82\x00') + struct.pack('<HH', len(V), NAC_SLOT * 8)
    for x, u, f in V: buf += struct.pack('<3h', x, f, u)
    assert NAC_SLOT + len(V) <= 900
    return bytes(buf), halves[0], halves[1]


def raise_fin(d):
    """尾翼根部（原版 up 12/11/15）的頂點沿前後緣搬到引擎艙頂 up FIN_ROOT：KC-10 的垂直尾翼是坐在引擎上，
    尾翼不再穿進引擎艙。只搬只有尾翼面用到的頂點（平面還是 x = 0，平面點不用改）。"""
    d = bytearray(d); pe, secs, code, c = code_of(d)
    ops, _, _ = sh_scale.walk(c)
    n = 0
    for a, nv, lim in LOD_BUFS:
        V = [list(struct.unpack_from('<hhh', c, a + 6 + 6 * i)) for i in range(nv)]   # (x, fwd, up)
        faces = []; fpos = {}
        for p, t in ops.items():
            if t != 'FC' or not a < p < lim: continue
            fl = struct.unpack_from('<H', c, p + 1)[0]; q = p + 5
            if fl & 0x60: q += 6 + (3 if fl & 0x200 else 6)
            k = c[q]; q += 1
            idx = [struct.unpack_from('<H', c, q + 2 * i)[0] for i in range(k)] if fl & 0x400 else list(c[q:q + k])
            if all(i < nv for i in idx): faces.append(idx); fpos[tuple(idx)] = p
        allfin = [f for f in faces if all(V[i][0] == 0 and V[i][1] <= -60 for i in f)]
        fin = [f for f in allfin if max(V[i][2] for i in f) >= 34]
        # 中、低 LOD 尾翼前面的小三角（背鰭）在引擎艙裡面，拿掉
        for f in allfin:
            if f in fin: continue
            p = fpos[tuple(f)]; e = face_end(c, p)
            c[p] = 0x38; struct.pack_into('<h', c, p + 1, e - (p + 3)); c[p + 3:e] = b'\x1E' * (e - p - 3)
        roots = {i for f in fin for i in f if V[i][2] < FIN_ROOT}
        for r in sorted(roots):
            assert all(f in allfin for f in faces if r in f), ('shared fin root', hex(a), V[r])
            # 同一面上相鄰、比它高的尾翼頂點（前緣或後緣）
            nb = set()
            for f in fin:
                if r in f:
                    j = f.index(r)
                    for m in (f[j - 1], f[(j + 1) % len(f)]):
                        if V[m][2] > FIN_ROOT: nb.add(m)
            assert len(nb) == 1, (hex(a), V[r], [V[m] for m in nb])
            t = V[nb.pop()]; s_ = (FIN_ROOT - V[r][2]) / (t[2] - V[r][2])
            V[r] = [0, int(round(V[r][1] + (t[1] - V[r][1]) * s_)), FIN_ROOT]
            struct.pack_into('<3h', c, a + 6 + 6 * r, *V[r]); n += 1
    R.check_relocs(bytes(d), pe, code, c)
    d[code['ro']:code['ro'] + code['vs']] = c
    print('fin root vertices raised', n)
    return bytes(d)


def node_targets(c, p):
    L = NODE_LEN[c[p]]; h = lambda q: struct.unpack_from('<h', c, q)[0]
    return L, p + L - 2 + h(p + L - 4), p + L + h(p + L - 2)


def node_copy(c, p, at):
    """把 p 處的節點複製到新位置 at（CODE 位移），重算兩個 rel。"""
    L, ta, tb = node_targets(c, p)
    b = bytearray(c[p:p + L]); struct.pack_into('<hh', b, L - 4, ta - (at + L - 2), tb - (at + L))
    return bytes(b)


def add_tail_engine(d):
    """尾引擎區塊（插在簽章前）：
      * 尾翼的位置（每個 LOD）：載入頂點（眼睛低於 HIDE_U 時收成一點）→ 6C x：左半 / 尾翼 / 右半。
      * 每個 LOD 的根節點前面（最先畫）：眼睛低於 HIDE_U 時才載入真的頂點 → 6C x：遠的半邊先畫。
        從下面看，引擎被機身、水平尾翼蓋住的地方就照常被蓋住，機尾後面露出來的部分照樣看得到。
      6C（cmp [眼睛+var], val）≥ 時先 A 後 B，最後載入的頂點有效，用來選「畫 / 收成一點」。"""
    from f18g_growler import grow_vas
    d = bytearray(grow_vas(bytes(d), 0x1000))      # 尾引擎約 2.9 KB；硬桿在後面再 grow 0x2000
    pe, secs, code, c = code_of(d)
    tail = c.find(R.SIG); assert tail > 0
    assert c[FIN6C:FIN6C + 6] == bytes.fromhex('6c0006000000') and c[FIN6C + 10] == 0x38
    buf, left, right = nacelle()
    blk = bytearray()
    nv = struct.unpack_from('<H', buf, 2)[0]
    coll = bytearray(buf[:6]) + struct.pack('<3h', 0, sc(-90), sc(NAC_UC)) * nv
    six = lambda var, val, A, B, at: struct.pack('<HHhhh', 0x6C, var, val, A - (at + 8), B - (at + 10))
    o_coll = len(blk); blk += coll + b'\x1E'
    o_real = len(blk); blk += buf + b'\x1E'
    o_left = len(blk); blk += left + b'\x1E'
    o_right = len(blk); blk += right + b'\x1E'
    o_late = len(blk); blk += six(8, sc(HIDE_U), o_coll, o_real, o_late) + b'\x1E'     # 高：真的；低：一點
    o_early = len(blk); blk += six(8, sc(HIDE_U), o_real, o_coll, o_early) + b'\x1E'   # 高：一點；低：真的
    o_halves = len(blk); blk += six(6, 0, o_left, o_right, o_halves) + b'\x1E'
    h = lambda p: struct.unpack_from('<h', c, p)[0]
    hooks = []        # (位址, 原本長度, 區塊入口)
    # 尾翼位置
    fins = [('6c', FIN6C, FIN6C + 10)] + [('faces', a, e) for a, e in FIN_FACES]
    for kind, a, e in fins:
        o = len(blk); hooks.append((a, e, o))
        blk += b'\x12\x00' + struct.pack('<h', o_late - (o + 4))
        n1 = len(blk); blk += bytes(10) + b'\x1E'
        n2 = len(blk); blk += bytes(10) + b'\x1E'
        of = len(blk)
        if kind == '6c': blk += node_copy(c, FIN6C, tail + of) + b'\x1E'
        else: blk += c[a:e] + b'\x1E'
        blk[n1:n1 + 10] = six(6, 0, o_left, n2, n1)
        blk[n2:n2 + 10] = six(6, 0, of, o_right, n2)
    # 根節點
    for a, n, _ in LOD_BUFS:
        p = a + 6 + 6 * struct.unpack_from('<H', c, a + 2)[0]
        while c[p] == 0xF6: p += 7
        L = NODE_LEN[c[p]]; assert c[p + 1] == 0 and c[p + L] == 0x38, hex(p)
        o = len(blk); hooks.append((p, p + L, o))
        blk += b'\x12\x00' + struct.pack('<h', o_early - (o + 4))
        blk += b'\x12\x00' + struct.pack('<h', o_halves - (o + 8))
        blk += node_copy(c, p, tail + len(blk)) + b'\x1E'
    # 掛勾：原位置 12 → 區塊入口、38 → 原本結尾
    for a, e, o in hooks:
        assert e - a >= 7
        c[a:a + 2] = b'\x12\x00'; struct.pack_into('<h', c, a + 2, tail + o - (a + 4))
        c[a + 4] = 0x38; struct.pack_into('<h', c, a + 5, e - (a + 7))
        c[a + 7:e] = b'\x1E' * (e - a - 7)
    R.check_relocs(bytes(d), pe, code, c)
    out = insert_blocks(d, pe, secs, code, c, tail, bytes(blk))
    _, _, so = pe_sections(out); so = sorted(so, key=lambda x: x['va'])
    for x, y in zip(so, so[1:]): assert x['va'] + x['vs'] <= y['va'], f"{x['name']} VA 重疊 {y['name']}"
    assert len(out) < 65536, len(out)
    print('tail engine block', len(blk), 'bytes, verts', nv, 'file', len(out))
    return out


def rename_pic(d):
    d = bytearray(d); old = b'\xE2\x00' + b'_kc135.PIC'.ljust(14, b'\0'); new = b'\xE2\x00' + b'_kc10.PIC'.ljust(14, b'\0')
    n = d.count(old); assert n >= 1
    return bytes(d.replace(old, new)), n


def build_pic(b):
    b = bytearray(b); po, ps = struct.unpack_from('<II', b, 10); n = 0
    for i in range(po, po + ps):
        if b[i] in G.GREENS: b[i] = min(159, b[i] + SHIFT); n += 1
    print('pic pixels recoloured', n)
    return bytes(b)


def configure_refuel(d_scaled):
    """kc135_refuel 的常數換成放大後的值（硬桿長度、加油框不變）。"""
    pe, secs, code, c = code_of(d_scaled)
    R.PIVOT = (0, sc(-2), sc(-63))
    R.HINGE_UP, R.HINGE_FWD = R.PIVOT[1] * R.U, R.PIVOT[2] * R.U
    R.HDR = bytes(c[8:14])
    R.BELLY_UP = R.EYE_BELOW = sc(-7)
    R.LIGHT_F = [sc(30 + 5 * j) for j in range(7)]
    R.REAR_LIGHTS = [tuple(sc(v) for v in t) for t in ((-66, -68, 1, 3), (-71, -74, 2, 4))]
    R.REAR_F0 = -64 * S
    R.ORIG_R = struct.unpack_from('<i', c, R.F2TBL)[0]
    R.GROW = 0x2000


def build(src, dst, pic_in=None, pic_out=None, preview=None, tmp='/tmp'):
    d = open(src, 'rb').read()
    d = remove_outer(d)
    d = raise_fin(d)
    G.BODY = BODY
    d = G.build_sh(d)
    d = sh_scale.scale_file(d, S)
    configure_refuel(d)
    # 尾引擎先插（區塊離主 LOD 根節點 0x1461 要在 rel16 ±32 KB 內），硬桿和 x86 插在它後面
    d = add_tail_engine(d)
    a = os.path.join(tmp, 'kc10_a.SH'); b = os.path.join(tmp, 'kc10_b.SH')
    open(a, 'wb').write(d)
    print(R.build(a, b, preview))
    out, n = rename_pic(open(b, 'rb').read()); print('texture names', n)
    open(dst, 'wb').write(out)
    if preview:
        p, _ = rename_pic(open(preview, 'rb').read()); open(preview, 'wb').write(p)
    if pic_in: open(pic_out, 'wb').write(build_pic(open(pic_in, 'rb').read()))


if __name__ == '__main__':
    a = sys.argv[1:]
    build(a[0], a[1], a[2] if len(a) > 2 else None, a[3] if len(a) > 3 else None, a[4] if len(a) > 4 else None,
          tmp=os.environ.get('TMPDIR', '/tmp'))
