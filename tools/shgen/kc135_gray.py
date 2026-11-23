#!/usr/bin/env python3
"""KC-135 外觀更新（Kuoyi 2026-11-23）：起落架改短、引擎艙往上提、改成現行美軍的灰色塗裝。

原因：原版 KC135.SH 的引擎艙掛得很低（內側艙底 up −14、外側 −11），所以 FA 的起落架要畫到 up −17
（F2 碰撞盒 ymin −34 ft）才不會讓引擎碰地，結果機腹離地很高、起落架很長。

改法（全部原地改位元組，檔案大小不變）：
  1. 引擎艙：兩個 LOD 的頂點緩衝（CODE 0x82、0x4C71）裡，內側艙（|x| 36..52、up ≤ −6）往上 INNER_UP，
     外側艙（|x| 66..82、up ≤ −3）往上 OUTER_UP；只用到這些頂點的面，平面點（pt）的 up 一起加。
  2. 起落架：三個貼圖看板零件（主輪 L 0x42BC、R 0x438D，鼻輪 0x445E）底部頂點往上 GEAR_CUT，
     頂部頂點的 UV 往底部那頭移同樣比例，等於把貼圖上半段的支柱裁掉，輪子大小不變。
  3. F2 碰撞盒 ymin：−34 → −(17 − GEAR_CUT)·2 ft，FA 用它決定停在地上的高度。
  4. 顏色：面顏色 105（綠）和 148（淺灰機腹）改成 BODY（灰階 144..159 那一組，FA 依此打光）。
     _KC135.PIC 裡的綠色（96..111）依亮度換成灰階。
用法：python3 kc135_gray.py 輸入KC135.SH 輸出.SH 輸入_KC135.PIC 輸出.PIC
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, main_lod
from kc135_refuel import check_relocs

LODS = ((0x82, 491), (0x4C71, 269))
INNER_UP, OUTER_UP = 4, 3
GEAR = (0x42BC, 0x438D, 0x445E)
GEAR_CUT = 5
F2TBL = 0x73E4
BODY = 155
GREENS = range(96, 112)
GREYS = range(144, 160)


def walk_faces(c, starts):
    """從每個起點走 BSP（兩邊都走、F0 跟 push 的位址），回傳 {面位址: (flag, 位置資訊)}。"""
    h = lambda p: struct.unpack_from('<h', c, p)[0]
    seen = set(); F = {}

    def exe(p, depth=0):
        if depth > 80: return
        for _ in range(20000):
            if p in seen or not (0 <= p < len(c) - 2): return
            seen.add(p); op = c[p]
            if op == 0 and c[p+1] == 0: return
            if op == 0x1E: return
            if op == 0x82 and c[p+1] == 0:
                n, t = struct.unpack_from('<HH', c, p+2); p += 6 + 6*n
            elif op == 0xFC:
                fl = struct.unpack_from('<H', c, p+1)[0]; q = p + 5; nq = ptq = None
                if fl & 0x60:
                    nq = q; q += 6; ptq = q; q += 3 if fl & 0x200 else 6
                k = c[q]; q += 1; iq = q
                idx = [struct.unpack_from('<H', c, q+2*i)[0] for i in range(k)] if fl & 0x400 else list(c[q:q+k])
                q += 2*k if fl & 0x400 else k
                uvq = q if fl & 4 else None
                if fl & 4: q += k * (2 if fl & 0x100 else 4)
                F[p] = dict(fl=fl, idx=idx, ptq=ptq, uvq=uvq, end=q); p = q
            elif op == 0xF6: p += 7
            elif op == 0x06 and c[p+1] == 0: exe(p+16+h(p+14), depth+1); exe(p+18+h(p+16), depth+1); p += 18
            elif op in (0x0C, 0x0E, 0x10) and c[p+1] == 0: exe(p+12+h(p+10), depth+1); exe(p+14+h(p+12), depth+1); p += 14
            elif op == 0x6C and c[p+1] == 0: exe(p+8+h(p+6), depth+1); exe(p+10+h(p+8), depth+1); p += 10
            elif op == 0x12 and c[p+1] == 0: exe(p+4+h(p+2), depth+1); p += 4
            elif op == 0x38: p = p + 3 + h(p+1)
            elif op == 0x48 and c[p+1] == 0: p = p + 4 + h(p+2)
            elif op == 0xC4 and c[p+1] == 0: exe(p+16+h(p+14), depth+1); p += 16
            elif op == 0xF0 and c[p+1] == 0:
                for q in range(p+2, p+200):
                    if c[q] == 0x68:
                        v = struct.unpack_from('<I', c, q+1)[0] - 0x1000
                        if 0 < v < len(c): exe(v, depth+1)
                return
            else:
                return
    for s in starts: exe(s)
    return F


def get_uv(c, f, i):
    if f['fl'] & 0x100: return list(c[f['uvq'] + 2*i:f['uvq'] + 2*i + 2])
    return list(struct.unpack_from('<HH', c, f['uvq'] + 4*i))


def set_uv(c, f, i, uv):
    if f['fl'] & 0x100: c[f['uvq'] + 2*i:f['uvq'] + 2*i + 2] = bytes(int(round(x)) for x in uv)
    else: struct.pack_into('<HH', c, f['uvq'] + 4*i, *(int(round(x)) for x in uv))


def build_sh(d):
    d = bytearray(d)
    pe, opt, secs = pe_sections(d); code = next(s for s in secs if s['name'] == 'CODE')
    c = bytearray(d[code['ro']:code['ro'] + code['vs']])
    assert struct.unpack_from('<i6h', c, F2TBL)[3] == -34
    starts = []
    for a, n, _, e in main_lod(c):
        R = e
        while c[R] == 0xF6: R += 7
        starts.append(R)
    F = walk_faces(c, starts)

    # 1. 引擎艙
    moved = []
    for a, n in LODS:
        assert c[a] == 0x82 and struct.unpack_from('<H', c, a+2)[0] == n
        mv = {}
        for i in range(n):
            q = a + 6 + 6*i; x, f, u = struct.unpack_from('<hhh', c, q)
            dz = INNER_UP if 36 <= abs(x) <= 52 and u <= -6 else OUTER_UP if 66 <= abs(x) <= 82 and u <= -3 else 0
            if dz: struct.pack_into('<h', c, q + 4, u + dz); mv[i] = dz
        moved.append((a, mv))
    npt = 0
    for p, f in F.items():
        # 面屬於哪個 LOD：在第二個緩衝之後的就是低細節
        a, mv = moved[1] if p > LODS[1][0] else moved[0]
        if f['ptq'] is None or not f['idx'] or any(i not in mv for i in f['idx']): continue
        dz = mv[f['idx'][0]]
        if f['fl'] & 0x200: c[f['ptq'] + 1] = (c[f['ptq'] + 1] + dz) & 0xFF
        else: struct.pack_into('<h', c, f['ptq'] + 2, struct.unpack_from('<h', c, f['ptq'] + 2)[0] + dz)
        npt += 1

    # 2. 起落架
    for g in GEAR:
        n, t = struct.unpack_from('<HH', c, g+2); base = t // 8
        V = [list(struct.unpack_from('<hhh', c, g + 6 + 6*i)) for i in range(n)]
        bottom = min(v[2] for v in V)
        gf = [f for p, f in F.items() if g < p < g + 6 + 6*n + 400 and all(base <= i < base + n for i in f['idx'])]
        assert gf, hex(g)
        for f in gf:
            k = len(f['idx']); P = [V[i - base] for i in f['idx']]; UV = [get_uv(c, f, j) for j in range(k)]
            for j in range(k):
                if P[j][2] - bottom <= 1: continue           # 底部頂點
                # 同一條邊上相鄰的底部頂點
                nb = [m for m in ((j-1) % k, (j+1) % k) if P[m][2] - bottom <= 1]
                if not nb: continue
                m = nb[0]; H = P[j][2] - P[m][2]; s = GEAR_CUT / H
                set_uv(c, f, j, [UV[j][r] + (UV[m][r] - UV[j][r]) * s for r in range(2)])
        for i, v in enumerate(V):
            if v[2] - bottom <= 1: struct.pack_into('<h', c, g + 6 + 6*i + 4, v[2] + GEAR_CUT)

    # 3. F2 ymin
    struct.pack_into('<h', c, F2TBL + 8, -(17 - GEAR_CUT) * 2)

    # 4. 顏色
    ncol = 0
    for p, f in F.items():
        if c[p+3] in (105, 148): c[p+3] = BODY; ncol += 1

    check_relocs(bytes(d), pe, code, c)
    d[code['ro']:code['ro'] + code['vs']] = c
    print(f'nacelle verts moved {[len(m) for _, m in moved]}, face pts {npt}, recoloured faces {ncol}')
    return bytes(d)


def build_pic(b, pal):
    b = bytearray(b)
    w, h = struct.unpack_from('<II', b, 2); po, ps = struct.unpack_from('<II', b, 10)
    lum = lambda k: 0.3*pal[3*k] + 0.59*pal[3*k+1] + 0.11*pal[3*k+2]
    ratio = lum(BODY) / lum(105)
    m = {g: min(GREYS, key=lambda k: abs(lum(k) - lum(g) * ratio)) for g in GREENS}
    n = 0
    for i in range(po, po + ps):
        if b[i] in m: b[i] = m[b[i]]; n += 1
    print('pic pixels recoloured', n, m)
    return bytes(b)


if __name__ == '__main__':
    a = sys.argv[1:]
    pal = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'PIC', 'PALETTE.PAL'), 'rb').read()[:768]
    open(a[1], 'wb').write(build_sh(open(a[0], 'rb').read()))
    if len(a) > 3: open(a[3], 'wb').write(build_pic(open(a[2], 'rb').read(), pal))
