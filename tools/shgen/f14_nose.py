#!/usr/bin/env python3
"""F-14 機鼻重畫：從原始 SH/F14.SH 產生 SHX/F14N.SH。做法說明見 skill/SH_edit_note.MD。

  * y=95 接合環（機身往前接機鼻的那一圈 13 點）修圓，駕駛艙前緣左邊照右邊鏡像，碰到的面重算法向量
  * 原本 y ≥ 95 的機鼻面（30 個）全部改成 `38 rel16` 跳過；左側機砲口的兩個小貼圖搬到新機鼻區塊最後畫
  * 新機鼻：接合環照實機側視和俯視線型縮成 6 個環圈（STATIONS），再接到機鼻尖，每個新點都有 F6 光影
  * 機鼻下 pod（凸多面體，11 點 9 面，寬 2 呎、高 2 呎、長 9 呎，y 89～98）
  * 畫面順序：主體 BSP 根節點（CODE+0x1007）換成呼叫新區塊，先用 06 測試眼睛在 y=95 前或後決定機身和機鼻/pod 的先後，
    再測試眼睛是否在機鼻底面（上 = -8）以下決定機鼻和 pod 的先後
用法：python3 f14_nose.py SH/F14.SH SHX/F14N.SH
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, parse_face, main_lod, FACE_OPS, insert_blocks

SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])
ROOT = 0x1007          # 主體 BSP 根節點（0C 00 …，14 位元組），後面 0x1015 是 38 跳到零件
POD_BASE = 480         # pod 頂點放在頂點表的位置（零件用到 470）

# 左上半照右上半鏡像：頂點 ← 鏡像來源
MIRROR_V = {60: 61, 162: 169, 63: 62, 157: 163, 76: 94, 210: 171, 214: 174}


NOSE_BASE = 500        # 新機鼻頂點放在頂點表的位置
# y=95 接合環（機身往前接機鼻的那一圈），從上中央順時針（從前面看）一圈 13 點：(左右頂點) → 新位置 (x, z)，左邊 x 取負
RING95 = {(72,): (0, 7), (169, 162): (3, 7), (61, 60): (3, 7), (171, 210): (6, 4), (170, 211): (7, 2),
          (202, 229): (6, -5), (263, 332): (4, -7), (290, 333): (2, -8)}
RING_ORDER = [72, 169, 171, 170, 202, 263, 290, 333, 332, 229, 211, 210, 162]
GUN_DECALS = (0x2AFC, 0x2FA2)          # 左側機砲口的小貼圖（色號 0 透明）
# 機鼻側面和俯視的線型（照實機側視圖）：從 y=95 到機鼻尖，t = (y-95)/30
#   上緣 z = 尖端 + 10·r(t, 0.6)，下緣 z = 尖端 - 5·r(t, 0.5)，半寬 = 7·r(t, 0.6)，r(t,a) = (1-t)(1+a·t)
#   都是凸的尖拱線：上緣接著擋風玻璃前的下斜一路彎下來，下緣從機鼻下方一路往上收到尖端，尖端在中線偏下
STATIONS = [100, 105, 110, 115, 119, 122]
TIP = (0, 125, -3)
def r_(t, a): return (1 - t) * (1 + a * t)


def nose(V):
    """回傳 (新頂點, F6 法向量, 面 [(旗標, 色號, 索引)], y=95 環的 F6 [(頂點, 法向量)])。
    每一環都是 y=95 環照比例縮小（剖面形狀一樣），環和環之間接四邊形，最後一環接到機鼻尖。"""
    base = [V[i] for i in RING_ORDER]; c0 = -0.5
    NV, NN = [], []
    def nrm(x, z, c, slope):
        v = (x, z - c, slope * (abs(x) + abs(z - c) + 1)); L = sum(t*t for t in v) ** 0.5 or 1
        return tuple(round(t*127/L) for t in v)
    rings = [[i for i in RING_ORDER]]
    for y in STATIONS:
        t = (y - 95) / 30; top = TIP[2] + 10 * r_(t, 0.6); bot = TIP[2] - 5 * r_(t, 0.5); ws = r_(t, 0.6)
        cz = (top + bot) / 2; r = []
        for (x, _, z) in base:
            u = (z + 8) / 15; X, Z = x * ws, bot + u * (top - bot)
            NV.append((round(X), y, round(Z))); NN.append(nrm(X, Z, cz, 0.3 + t))
            r.append(('n', len(NV)-1))
        rings.append(r)
    NV.append(TIP); NN.append((0, -10, 126)); tip = ('n', len(NV)-1)
    ring0 = [(i, nrm(V[i][0], V[i][2], c0, 0.2)) for i in RING_ORDER]
    ids = lambda r: r if isinstance(r, int) else NOSE_BASE + r[1]
    faces, n = [], len(RING_ORDER)
    for a, b in zip(rings, rings[1:]):
        for k in range(n):
            faces.append((0x273, 0x98, [ids(a[k]), ids(a[(k+1) % n]), ids(b[(k+1) % n]), ids(b[k])]))
    for k in range(n):
        faces.append((0x273, 0x98, [ids(rings[-1][k]), ids(rings[-1][(k+1) % n]), ids(tip)]))
    # 繞向：FA 的面在 (x,y,z) 下 ΣP×P 朝內；以機鼻中心軸判斷
    allv = dict(V); allv.update({NOSE_BASE+k: v for k, v in enumerate(NV)})
    out = []
    for fl, col, idx in faces:
        P = [allv[i] for i in idx]; m = [0, 0, 0]
        for k in range(len(P)):
            p, q = P[k], P[(k+1) % len(P)]
            m[0] += p[1]*q[2]-p[2]*q[1]; m[1] += p[2]*q[0]-p[0]*q[2]; m[2] += p[0]*q[1]-p[1]*q[0]
        cy = sum(p[1] for p in P) / len(P); cz = -0.5 - 2.5 * (cy - 95) / 30
        fc = [sum(p[0] for p in P) / len(P), 0.3, sum(p[2] for p in P) / len(P) - cz]
        if sum(m[k]*fc[k] for k in range(3)) > 0: idx = idx[::-1]
        out.append((fl, col, idx))
    return NV, NN, out, ring0


def normal_point(P, fl):
    """FC 面的法向量（x、上、前，長度 32767，朝外）和平面上的點。FA 的面在 (x,y,z) 下 ΣP×P 朝內。"""
    n = [0, 0, 0]
    for k in range(len(P)):
        p, q = P[k], P[(k+1) % len(P)]
        n[0] += p[1]*q[2]-p[2]*q[1]; n[1] += p[2]*q[0]-p[0]*q[2]; n[2] += p[0]*q[1]-p[1]*q[0]
    L = sum(x*x for x in n) ** 0.5 or 1
    nrm = [round(-n[0]/L*32767), round(-n[2]/L*32767), round(-n[1]/L*32767)]
    cen = [sum(p[k] for p in P) / len(P) for k in range(3)]
    pt = [round(cen[0]), round(cen[2]), round(cen[1])]
    if fl & 0x200: pt = [max(-128, min(127, v)) for v in pt]
    return nrm, pt


def face_bytes(fl, col, idx, P, uv=None):
    if any(i > 255 for i in idx): fl |= 0x400
    b = bytearray(struct.pack('<BHH', 0xFC, fl, col))
    if fl & 0x60:
        nrm, pt = normal_point(P, fl)
        b += struct.pack('<hhh', *nrm) + (struct.pack('<bbb', *pt) if fl & 0x200 else struct.pack('<hhh', *pt))
    b.append(len(idx))
    b += b''.join(struct.pack('<H', i) for i in idx) if fl & 0x400 else bytes(idx)
    if fl & 4:
        b += b''.join(bytes(u) if fl & 0x100 else struct.pack('<HH', *u) for u in uv)
    return b


def pod():
    """回傳 (頂點, F6 法向量（x、上、前）, 面 [(旗標, 色號, 索引)])，索引從 0 起算。"""
    # 頂點座標以 1 呎為單位，尺寸減半後剖面只能用五邊形：寬 2、高 2，底下一條龍骨
    ring = [(-1, -8), (1, -8), (1, -9), (0, -10), (-1, -9)]
    V, N = [], []
    def add(p, n): V.append(p); L = sum(x*x for x in n) ** 0.5; N.append(tuple(round(x*127/L) for x in n)); return len(V) - 1
    R = add((0, 89, -8), (0, -60, -110))
    M = [add((x, 91, z), (x, z+9, -0.4)) for x, z in ring]
    F = [add((x, 98, z), (x, z+9, 0.4)) for x, z in ring]
    body, win, fl = 0x98, 0x9B, 0x273
    faces = []
    for k in range(1, 5):  # 環的邊 k → k+1；0→1 是貼在機鼻底面的上緣，不畫
        a, b = k, (k+1) % 5
        faces.append((fl, body, [R, M[a], M[b]]))
        faces.append((fl, body, [M[a], F[a], F[b], M[b]]))
    faces.append((0x271, win, list(F)))    # 前面的窗：單色、不用 Gouraud
    # 繞向：FA 的面在 (x,y,z) 下 ΣP×P 朝內；不對就反轉
    cen = [sum(p[k] for p in V) / len(V) for k in range(3)]
    out = []
    for fl_, col, idx in faces:
        P = [V[i] for i in idx]; n = [0, 0, 0]
        for k in range(len(P)):
            p, q = P[k], P[(k+1) % len(P)]
            n[0] += p[1]*q[2]-p[2]*q[1]; n[1] += p[2]*q[0]-p[0]*q[2]; n[2] += p[0]*q[1]-p[1]*q[0]
        fc = [sum(p[k] for p in P) / len(P) - cen[k] for k in range(3)]
        if sum(n[k]*fc[k] for k in range(3)) > 0: idx = idx[::-1]
        out.append((fl_, col, idx))
    return V, N, out


def main():
    src, dst = sys.argv[1], sys.argv[2]
    d = bytearray(open(src, 'rb').read())
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    c = bytearray(d[code['ro']:code['ro']+code['vs']])
    bufs = main_lod(c); o0, main_n, _, main_e = bufs[0]
    stop = next((b[0] for b in bufs if b[2] < 0), None) or (bufs[1][0] if len(bufs) > 1 else len(c))
    V = {i: struct.unpack_from('<hhh', c, o0+6+6*i) for i in range(main_n)}
    F6 = {}; p = main_e
    while c[p] == 0xF6: F6[struct.unpack_from('<H', c, p+1)[0]] = p; p += 7
    faces, o = {}, main_e
    while o < stop - 6:
        f = parse_face(c, o) if c[o] == 0xFC else None
        ok = f and ((f['fl'] & 0x200 and not f['fl'] & 0xF000 and (f['fl'] & 0xFF) in FACE_OPS) or (not f['fl'] & 0x200 and (f['fl'] & 0xFF) in FACE_OPS and f['fl'] < 0x1000))
        if ok and all(i < main_n for i in f['idx']) and len(set(f['idx'])) == f['n'] and f['end'] <= stop:
            faces[o] = f; o = f['end']; continue
        o += 1
    # 檢查法向量公式：和原檔每個面存的法向量同方向
    agree = sum(1 for f in faces.values() if f['fl'] & 0x60 and
                sum(a*b for a, b in zip(normal_point([V[i] for i in f['idx']], f['fl'])[0], struct.unpack_from('<hhh', f['head'], 4))) > 0)
    print(f'法向量公式和原檔同方向：{agree}/{sum(1 for f in faces.values() if f["fl"] & 0x60)} 個面')

    # 1. 搬頂點：駕駛艙前緣左邊照右邊鏡像，y=95 接合環修圓
    for i, s_ in MIRROR_V.items():
        x, y, z = V[s_]; V[i] = (-x, y, z)
    for ids, (x, z) in RING95.items():
        for k, i in enumerate(ids): V[i] = ((x, -x)[k], 95, z) if k < 2 else None
    for i in range(main_n): struct.pack_into('<hhh', c, o0+6+6*i, *V[i])
    moved = set(MIRROR_V) | {i for ids in RING95 for i in ids}
    # 2. 機鼻（y ≥ 95 的面）全部拿掉，機砲口的小貼圖搬到新機鼻區塊裡（在機鼻之後畫）
    front = [f for f in faces.values() if all(V[i][1] >= 95 for i in f['idx'])]
    decals = [bytes(c[f['o']:f['end']]) for f in front if f['o'] in GUN_DECALS]
    for f in front:
        o, e = f['o'], f['end']; c[o:e] = b'\x38' + struct.pack('<h', e - (o + 3)) + b'\x1e' * (e - o - 3)
    # 3. 碰到搬動頂點的面重算法向量
    for f in faces.values():
        if f in front or not f['fl'] & 0x60 or not set(f['idx']) & moved: continue
        nrm, pt = normal_point([V[i] for i in f['idx']], f['fl'])
        struct.pack_into('<hhh', c, f['o']+5, *nrm)
        struct.pack_into('<bbb' if f['fl'] & 0x200 else '<hhh', c, f['o']+11, *pt)
    # 4. 新機鼻
    NV, NN, NF, ring0 = nose(V)
    allv = dict(V); allv.update({NOSE_BASE+k: v for k, v in enumerate(NV)})
    def vid(r): return r if isinstance(r, int) and r < 1000 else NOSE_BASE + r[1]
    noseb = bytearray(struct.pack('<BBHH', 0x82, 0, len(NV), NOSE_BASE*8))
    for v in NV: noseb += struct.pack('<hhh', *v)
    for k, n in enumerate(NN): noseb += struct.pack('<BHBbbb', 0xF6, NOSE_BASE+k, 0x98, *n)
    for i, n in ring0: noseb += struct.pack('<BHBbbb', 0xF6, i, 0x98, *n)
    nf = 0
    for fl, col, idx in NF:
        P = [allv[i] for i in idx]
        q = [k for k in range(len(P)) if P[k] != P[k-1]]        # 四捨五入後重疊的點拿掉
        idx = [idx[k] for k in q]; P = [P[k] for k in q]
        if len(set(P)) < 3: continue
        noseb += face_bytes(fl, col, idx, P); nf += 1
    for b in decals: noseb += b
    noseb += b'\x00\x00'
    # 5. pod
    PV, PN, PF = pod()
    podb = bytearray(struct.pack('<BBHH', 0x82, 0, len(PV), POD_BASE*8))
    for v in PV: podb += struct.pack('<hhh', *v)
    for k, n in enumerate(PN): podb += struct.pack('<BHBbbb', 0xF6, POD_BASE+k, 0x98, *n)
    allv.update({POD_BASE+k: v for k, v in enumerate(PV)})
    for fl, col, idx in PF:
        ids = [POD_BASE+i for i in idx]; podb += face_bytes(fl, col, ids, [allv[i] for i in ids])
    podb += b'\x00\x00'
    # 6. 根節點換成呼叫新區塊：
    #    S:  06 眼睛在 y=95 前面？ 是 → 先機身 BODY 再 NP；否 → 先 NP 再機身
    #    NP: 06 眼睛在機鼻底面（上 = -8）以下？ 是 → 先機鼻再 pod；否 → 先 pod 再機鼻
    assert c[ROOT] == 0x0C and c[ROOT+1] == 0 and c[ROOT+14] == 0x38, '根節點不是預期的 0C … 38'
    tail = bytes(c).find(SIG)
    TA = ROOT + 12 + struct.unpack_from('<h', c, ROOT+10)[0]; TB = ROOT + 14 + struct.unpack_from('<h', c, ROOT+12)[0]
    S = tail; BODY = S + 20; NP = BODY + 16; NOSE = NP + 20; POD = NOSE + len(noseb)
    def node(at, n, d, a, b):   # 06 00 n1 d1 n2 d2 n3 d3 relA relB 00 00
        return struct.pack('<BB6h', 0x06, 0, n[0], d[0], n[1], d[1], n[2], d[2]) + struct.pack('<hh', a - (at+16), b - (at+18)) + b'\x00\x00'
    body = bytearray(c[ROOT:ROOT+10]) + struct.pack('<hh', TA - (BODY+12), TB - (BODY+14)) + b'\x00\x00'
    blocks = node(S, (0, 0, 16384), (0, 0, -95), BODY, NP) + body + node(NP, (0, -16384, 0), (0, 8, 0), NOSE, POD) + noseb + podb
    patch = bytearray(b'\x12\x00') + struct.pack('<h', S - (ROOT + 4)) + b'\x38' + struct.pack('<h', ROOT + 14 - (ROOT + 7))
    c[ROOT:ROOT+14] = patch + b'\x1e' * (14 - len(patch))
    room = nxt - code['va'] - len(c)
    if len(blocks) > room: sys.exit(f'空間不夠：需要 {len(blocks)}，只有 {room}')
    if NOSE_BASE + len(NV) > 900: sys.exit('頂點表超過 900')
    out = insert_blocks(d, pe, secs, code, c, tail, blocks)
    open(dst, 'wb').write(out)
    print(f'{dst}: 拿掉機鼻 {len(front)} 面；新機鼻 {len(NV)} 點 {nf} 面（+機砲口貼圖 {len(decals)}）；pod {len(PV)} 點 {len(PF)} 面；新增 {len(blocks)} 位元組（空間 {room}）')

if __name__ == '__main__': main()
