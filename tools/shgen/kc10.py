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
FAT = 1.15                       # KC10_4：機身截面（x、上下）再胖 15%（Kuoyi：只要讓 KC-10 胖一點）
SX, SU, SF = S * FAT, S * FAT, S   # 三軸倍率 (x, 上, 前)
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
NAC_RINGS = ((-66, 3.7), (-68, 4.6), (-72, 5.0), (-82, 5.0), (-100, 5.0), (-108, 4.3), (-114, 3.4))
# 貼圖照 KC-135 翼下引擎（_KC135.PIC）：整流罩 u 165..227、後段 u 78..163（往後增加），v 130（上）..78（下）；
# 這兩塊貼圖大多是透明（只有蒙皮線和標誌），底色是 Gouraud 的機身灰（0x02 + F6）。進氣口用風扇圖（中心 204,56）。
NAC_SPLIT = -82                  # 整流罩 / 後段分界
COWL_U, AFT_U, NAC_V = (165, 227), (78, 163), (130, 78)
FAN_UV = (204, 56, 23, 18)       # 中心 u, v、半徑 u, v
F_TEX = 0x05EE                   # 照原版引擎艙 0x7EE（去掉 0x200：平面點 i16）：Gouraud 底色 + 貼圖 + u8 UV
TEXTURE, FAN, USE_F6 = False, False, True   # 貼圖版會讓 FA 載入時當機（KC10_2/3B..3K），正式版不用貼圖
EXH_TEX = False   # 測試：噴嘴用風扇貼圖（從後面看得到的貼圖面）
TEX_SEGS = None   # 測試：只有這些環段用貼圖（None = 全部）
# KC10-3B：側面 0x5EC/0x5EE（原版引擎艙的旗標）會讓 FA 當掉，進氣口 0x564 沒事。
# SIDE_MODE 'gouraud' = 原版貼圖 + Gouraud 底色（F_TEX）；'baked' = 把 KC-135 引擎艙貼圖烤成不透明（透明處填 BAKED_FILL）
# 放到 PIC 空白區（u 0..63、v 536..567），面用 0x464（照進氣口 0x564，但 UV 是 u16，因為 v > 255）
SIDE_MODE = 'gouraud'
BAKED_COWL_U, BAKED_AFT_U, BAKED_V = (0, 23), (24, 63), (536, 567)
BAKED_FILL = 154
F_BAKED = 0x0464   # 測試開關（KC10 當機找原因用）
F_FAN = 0x0564                   # 照原版進氣口 0x764：色號 0 的貼圖面
NSIDE = 12
HIDE_U = 10                      # 原版座標：眼睛低於這個高度（水平尾翼 8..11、機背 12）就先畫尾引擎
FIN_ROOT = NAC_UC + 5            # 尾翼根部搬到引擎艙頂
THUNK_PUSH = 0x3D99               # 原本 F0 的 `push do_start_interp 跳板`（運算元有重定位）
NODE_LEN = {0x06: 18, 0x0C: 14, 0x0E: 14, 0x10: 14, 0x6C: 10}
F_FLAT = 0x0461                  # u16 索引 + 背面剔除 + 打光 + 單色；平面點用 i16（放大後超過 i8）


def sc(v): return sh_scale.sc(v, S)
def scx(v): return sh_scale.sc(v, SX)
def scu(v): return sh_scale.sc(v, SU)
def scf(v): return sh_scale.sc(v, SF)


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
    """回傳 (82 緩衝 + F6 bytes, 左半面 bytes, 右半面 bytes)；座標已放大。"""
    V = []; NRM = []
    def vert(x, u, f, n): V.append((x, u, f)); NRM.append(n); return NAC_SLOT + len(V) - 1
    rings = []
    f0, f1 = NAC_RINGS[0][0], NAC_RINGS[-1][0]
    for f, r in NAC_RINGS:
        ring = []
        for k in range(NSIDE):
            a = 2 * math.pi * k / NSIDE
            ring.append(vert(scx(r * math.sin(a)), scu(NAC_UC + r * math.cos(a)), scf(f), (math.sin(a), math.cos(a), 0)))
        rings.append(ring)
    P = lambda i: V[i - NAC_SLOT]
    axis_u = NAC_UC * SU

    def ring_u(ri, seg_front):
        """第 ri 環的 u；seg_front = 這個面在分界前面（整流罩）。"""
        f = NAC_RINGS[ri][0]
        if seg_front: a, b, lo, hi = f0, NAC_SPLIT, *(BAKED_COWL_U if SIDE_MODE == 'baked' else COWL_U)
        else: a, b, lo, hi = NAC_SPLIT, f1, *(BAKED_AFT_U if SIDE_MODE == 'baked' else AFT_U)
        return lo + (hi - lo) * (f - a) / (b - a)

    def face(idx, out, flags, col, uv=None):
        """out = 朝外的大概方向；照 (B−A)×(C−A) 排頂點順序（UV 跟著反），法向量用三點叉積。"""
        A, B, C = P(idx[0]), P(idx[1]), P(idx[2])
        e1 = [B[t] - A[t] for t in range(3)]; e2 = [C[t] - A[t] for t in range(3)]
        n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]]
        if sum(n[t] * out[t] for t in range(3)) < 0:
            n = [-k for k in n]; idx = idx[::-1]; uv = uv[::-1] if uv else uv
        L = math.sqrt(sum(k * k for k in n)); n = [int(round(k / L * 32767)) for k in n]
        b = bytearray(b'\xFC') + struct.pack('<HH', flags, col)
        if flags & 0x200:                                          # 平面點 i8：取平面上離原點最近的點（原版貼圖面都這樣）
            nn = sum(k * k for k in n); dq = sum(n[t] * A[t] for t in range(3))
            pt = [int(round(n[t] * dq / nn)) for t in range(3)]
            assert max(abs(k) for k in pt) <= 127, pt
            b += struct.pack('<3h', *n) + struct.pack('<3b', *pt) + bytes([len(idx)])
        else: b += struct.pack('<3h', *n) + struct.pack('<3h', *A) + bytes([len(idx)])
        b += b''.join(struct.pack('<H', i) for i in idx)
        if uv and flags & 0x100: b += b''.join(bytes([int(round(u)), int(round(v))]) for u, v in uv)
        elif uv: b += b''.join(struct.pack('<HH', int(round(u)), int(round(v))) for u, v in uv)
        return bytes(b)

    halves = []
    NV = BAKED_V if SIDE_MODE == 'baked' else NAC_V
    vk = lambda j: NV[0] + (NV[1] - NV[0]) * j / (NSIDE // 2)
    side_flags = F_BAKED if SIDE_MODE == 'baked' else F_TEX
    side_col = 0 if SIDE_MODE == 'baked' else BODY
    for sx in (-1, 1):
        ks = list(range(0, NSIDE // 2 + 1))                      # 0（上）..6（下）
        if sx < 0: ks = [0] + list(range(NSIDE - 1, NSIDE // 2 - 1, -1))
        fb = bytearray()
        for ri in range(len(rings) - 1):
            front = NAC_RINGS[ri + 1][0] >= NAC_SPLIT
            ua, ub = ring_u(ri, front), ring_u(ri + 1, front)
            for j in range(len(ks) - 1):
                q = [rings[ri][ks[j]], rings[ri][ks[j + 1]], rings[ri + 1][ks[j + 1]], rings[ri + 1][ks[j]]]
                uv = [(ua, vk(j)), (ua, vk(j + 1)), (ub, vk(j + 1)), (ub, vk(j))]
                cen = [sum(P(i)[t] for i in q) / len(q) for t in range(3)]
                fb += face(q, (cen[0], cen[1] - axis_u, 0), side_flags, side_col, uv) if TEXTURE and (TEX_SEGS is None or ri in TEX_SEGS) else face(q, (cen[0], cen[1] - axis_u, 0), F_FLAT, BODY)
        cu, cv, ru, rv = FAN_UV
        fan = []
        for k in ks:
            a = 2 * math.pi * k / NSIDE
            fan.append((cu + ru * math.sin(a), cv - rv * math.cos(a)))
        fb += face([rings[0][k] for k in ks], (0, 0, 1), F_FAN, 0, fan) if FAN else face([rings[0][k] for k in ks], (0, 0, 1), F_FLAT, C_HOLE)   # 進氣口（風扇貼圖）
        if EXH_TEX: fb += face([rings[-1][k] for k in ks], (0, 0, -1), F_FAN, 0, fan)   # 測試：噴嘴也用風扇貼圖
        else: fb += face([rings[-1][k] for k in ks], (0, 0, -1), F_FLAT, C_HOLE)       # 噴嘴（深色）
        halves.append(bytes(fb))
    buf = bytearray(b'\x82\x00') + struct.pack('<HH', len(V), NAC_SLOT * 8)
    for x, u, f in V: buf += struct.pack('<3h', x, f, u)
    for i, (nx, nu, nf) in enumerate(NRM if USE_F6 else []):                        # F6：Gouraud 底色要每點的色號和法向量
        buf += b'\xF6' + struct.pack('<HB3b', NAC_SLOT + i, BODY, int(round(nx * 127)), int(round(nu * 127)), int(round(nf * 127)))
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
      * 尾翼的位置（每個 LOD）：眼睛高於 HIDE_U → 載入頂點 → 6C x：左半 / 尾翼 / 右半；否則只畫尾翼。
      * 每個 LOD 的根節點前面（最先畫）：眼睛低於 HIDE_U 才載入頂點、畫兩半（遠的先），再跑原本的根節點。
        從下面看，引擎被機身、水平尾翼蓋住的地方就照常被蓋住，機尾後面露出來的部分照樣看得到。
      高低用一小段 F0 x86 選（不能像 KC10-1 那樣把頂點收成一點：貼圖面退化成一點會讓 FA 當掉，KC10-2）。"""
    from f18g_growler import grow_vas
    d = bytearray(grow_vas(bytes(d), 0x1000))      # 尾引擎約 2.9 KB；硬桿在後面再 grow 0x2000
    pe, secs, code, c = code_of(d)
    tail = c.find(R.SIG); assert tail > 0
    assert c[FIN6C:FIN6C + 6] == bytes.fromhex('6c0006000000') and c[FIN6C + 10] == 0x38
    buf, left, right = nacelle()
    assert c[THUNK_PUSH] == 0x68 and (THUNK_PUSH + 1) in R.reloc_sites(bytes(d), pe, code)
    blk = bytearray()
    nv = struct.unpack_from('<H', buf, 2)[0]
    six = lambda var, val, A, B, at: struct.pack('<HHhhh', 0x6C, var, val, A - (at + 8), B - (at + 10))

    def f0_select(at, A, B):
        """F0 x86（48 byte，放在區塊位移 at）：眼睛高度 word[0x51cdac] ≥ HIDE_U 時接著跑 A，否則跑 B。
        不用重定位：call/pop 取自己位址；do_start_interp 的跳板位址從原本 F0 的 push 運算元讀（載入時已重定位）。"""
        x = bytearray(b'\xF0\x00\xE8\x00\x00\x00\x00\x5B')            # call base; base: pop ebx
        x += b'\x66\xA1' + struct.pack('<I', 0x51CDAC)                     # mov ax, [eye up]
        x += b'\x66\x3D' + struct.pack('<h', scu(HIDE_U))                   # cmp ax, HIDE_U
        x += b'\x7D\x08'                                                   # jge hi
        x += b'\x81\xC3' + struct.pack('<i', B - (at + 7)) + b'\xEB\x06'  # add ebx, B; jmp go
        x += b'\x81\xC3' + struct.pack('<i', A - (at + 7))                 # hi: add ebx, A
        x += b'\x53\xE8\x00\x00\x00\x00\x5B'                             # go: push ebx; call b2; b2: pop ebx
        x += b'\xFF\xB3' + struct.pack('<i', (THUNK_PUSH + 1) - (tail + at + 40)) + b'\xC3'   # push [thunk]; ret
        assert len(x) == 48
        return bytes(x)

    o_real = len(blk); blk += buf + b'\x1E'
    o_left = len(blk); blk += left + b'\x1E'
    o_right = len(blk); blk += right + b'\x1E'
    o_halves = len(blk); blk += six(6, 0, o_left, o_right, o_halves) + b'\x1E'
    hooks = []        # (位址, 原本長度, 區塊入口)
    # 尾翼位置：眼睛高 → 載入、左半 / 尾翼 / 右半；眼睛低 → 只畫尾翼（引擎已經在最前面畫過）
    fins = [('6c', FIN6C, FIN6C + 10)] + [('faces', a, e) for a, e in FIN_FACES]
    def fin_bytes(kind, a, e, at):
        return (node_copy(c, FIN6C, tail + at) if kind == '6c' else bytes(c[a:e])) + b'\x1E'
    for kind, a, e in fins:
        o = len(blk); hooks.append((a, e, o)); blk += bytes(48)
        o_full = len(blk)
        blk += b'\x12\x00' + struct.pack('<h', o_real - (o_full + 4))
        n1 = len(blk); blk += bytes(10) + b'\x1E'
        n2 = len(blk); blk += bytes(10) + b'\x1E'
        of = len(blk); blk += fin_bytes(kind, a, e, of)
        blk[n1:n1 + 10] = six(6, 0, o_left, n2, n1)
        blk[n2:n2 + 10] = six(6, 0, of, o_right, n2)
        o_fin = len(blk); blk += fin_bytes(kind, a, e, o_fin)
        blk[o:o + 48] = f0_select(o, o_full, o_fin)
    # 根節點：眼睛低 → 先載入、畫兩半（遠的先），再跑原本的根節點；眼睛高 → 直接跑原本的根節點
    for a, n, _ in LOD_BUFS:
        p = a + 6 + 6 * struct.unpack_from('<H', c, a + 2)[0]
        while c[p] == 0xF6: p += 7
        L = NODE_LEN[c[p]]; assert c[p + 1] == 0 and c[p + L] == 0x38, hex(p)
        o = len(blk); hooks.append((p, p + L, o)); blk += bytes(48)
        o_low = len(blk)
        blk += b'\x12\x00' + struct.pack('<h', o_real - (o_low + 4))
        blk += b'\x12\x00' + struct.pack('<h', o_halves - (o_low + 8))
        o_root = len(blk); blk += node_copy(c, p, tail + o_root) + b'\x1E'
        blk[o:o + 48] = f0_select(o, o_root, o_low)
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
    if SIDE_MODE == 'baked':
        w, h = struct.unpack_from('<II', b, 2); rt = struct.unpack_from('<I', b, 0x22)[0]
        rows = [struct.unpack_from('<I', b, rt + 4 * r)[0] for r in range(h)]
        px = lambda u, v: rows[h - 1 - v] + u
        src = bytes(b)
        for v in range(BAKED_V[0], BAKED_V[1] + 1):
            t = (v - BAKED_V[0] + 0.5) / (BAKED_V[1] - BAKED_V[0] + 1)
            sv = int(NAC_V[0] + (NAC_V[1] - NAC_V[0]) * t)
            for u in range(BAKED_COWL_U[0], BAKED_AFT_U[1] + 1):
                if u <= BAKED_COWL_U[1]: lo, hi, a, z = *COWL_U, *BAKED_COWL_U
                else: lo, hi, a, z = *AFT_U, *BAKED_AFT_U
                su = int(lo + (hi - lo) * (u - a + 0.5) / (z - a + 1))
                assert src[px(u, v)] == 255, (u, v)
                k = src[px(su, sv)]
                b[px(u, v)] = BAKED_FILL if k == 255 else k
    return bytes(b)


def configure_refuel(d_scaled):
    """kc135_refuel 的常數換成放大後的值（硬桿長度、加油框不變）。"""
    pe, secs, code, c = code_of(d_scaled)
    R.PIVOT = (0, scu(-2), scf(-63))
    R.HINGE_UP, R.HINGE_FWD = R.PIVOT[1] * R.U, R.PIVOT[2] * R.U
    R.HDR = bytes(c[8:14])
    R.BELLY_UP = R.EYE_BELOW = scu(-7)
    R.LIGHT_F = [scf(30 + 5 * j) for j in range(7)]
    R.REAR_LIGHTS = [(scf(a), scf(b), scx(x0), scx(x1)) for a, b, x0, x1 in ((-66, -68, 1, 3), (-71, -74, 2, 4))]
    R.REAR_F0 = -64 * SF
    R.REAR_SLOPE = 8 / 15 * SU / SF
    R.ORIG_R = struct.unpack_from('<i', c, R.F2TBL)[0]
    R.GROW = 0x2000


def build(src, dst, pic_in=None, pic_out=None, preview=None, tmp='/tmp'):
    d = open(src, 'rb').read()
    d = remove_outer(d)
    d = raise_fin(d)
    G.BODY = BODY
    d = G.build_sh(d)
    d = sh_scale.scale_file(d, (SX, SU, SF))
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
