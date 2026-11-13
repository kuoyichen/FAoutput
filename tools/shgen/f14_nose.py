#!/usr/bin/env python3
"""F-14 機鼻修正：讓機鼻左右對稱，並在機鼻下加 TCS/IRST pod。從原始 SH/F14.SH 產生 SHX/F14N.SH。

原檔的機鼻上半部右邊比左邊寬 1 呎，拓樸也不一樣（左邊多一個五邊形和兩個小三角形）；右下則比左下多一道折線。
這裡把左上半改成右上半的鏡像、右下改成左下的鏡像：
  * 搬動頂點座標：直接改 82 頂點緩衝裡的值，並把 F6 每點光影的法向量換成對應點的鏡像
  * 碰到搬動頂點的面都重算法向量和平面上的點（FC 面的 3×i16 法向量 + 3×i8/i16 點，順序是 x、上、前）
  * 換掉的面：一樣長就原地改寫，不一樣長就用 sh_subdivide.py 的掛勾（`12 00 rel16` 呼叫新區塊 + `38 rel16` 跳過）
  * 刪掉的面：改成 `38 rel16` 跳過
pod（凸多面體，21 點，寬 4 呎、高 4 呎、長 17 呎，y 90～107）：FA 的 SH 是 BSP，照順序畫（後畫的蓋前面）。主體的根節點在 CODE+0x1007（0C 平面測試），
把它換成呼叫新區塊：`06` 平面測試眼睛是否在機鼻底面（上 = -8）以下，在下面就先畫機身再畫 pod，否則先畫 pod 再畫機身。
pod 的每個面都開背面剔除（旗標 0x40），凸物體自己不用排序。
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
# 換掉的面（偏移：新的頂點順序；None = 刪掉）。順序都已經考慮鏡像後要反轉繞向
REPLACE = {
    0x2B29: [212, 278, 168, 162],       # 左上五邊形 → 右邊 [169,168,278,172] 的鏡像
    0x2B3D: [210, 212, 162],            # 左上 → 右邊 [169,172,171] 的鏡像
    0x2C75: None, 0x2BC1: None,         # 左上多出來的兩個小三角形
    0x2EAE: 'mirror:0x3121',            # 右下兩個面 → 左下 [269,229,332,331] 的鏡像
    0x2F2C: None,
}
MIRROR_IDX = {269: 277, 229: 202, 332: 263, 331: 276}


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
    ring = [(-1, -8), (1, -8), (2, -9), (2, -11), (1, -12), (-1, -12), (-2, -11), (-2, -9)]
    sq = [(-1, -9), (1, -9), (1, -11), (-1, -11)]
    V, N = [], []
    def add(p, n): V.append(p); L = sum(x*x for x in n) ** 0.5; N.append(tuple(round(x*127/L) for x in n)); return len(V) - 1
    R = add((0, 90, -8), (0, -60, -110))
    M = [add((x, 94, z), (x, z+10, -0.6)) for x, z in ring]
    F = [add((x, 105, z), (x, z+10, 0.6)) for x, z in ring]
    C = [add((x, 107, z), (x*0.4, (z+10)*0.4, 1.5)) for x, z in sq]
    body, win, fl = 0x98, 0x9B, 0x273
    faces = []
    for k in range(1, 8):  # 環的邊 k → k+1；0→1 是貼在機鼻底面的上緣，不畫
        a, b = k, (k+1) % 8
        faces.append((fl, body, [R, M[a], M[b]]))
        faces.append((fl, body, [M[a], F[a], F[b], M[b]]))
    cham = [([F[0], F[1], C[1], C[0]]), ([F[1], F[2], C[1]]), ([F[2], F[3], C[2], C[1]]), ([F[3], F[4], C[2]]),
            ([F[4], F[5], C[3], C[2]]), ([F[5], F[6], C[3]]), ([F[6], F[7], C[0], C[3]]), ([F[7], F[0], C[0]])]
    faces += [(fl, body, q) for q in cham]
    faces.append((0x271, win, list(C)))    # 前面的窗：單色、不用 Gouraud
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

    # 1. 搬頂點（左上半 = 右上半鏡像）
    for i, s in MIRROR_V.items():
        x, y, z = V[s]; V[i] = (-x, y, z); struct.pack_into('<hhh', c, o0+6+6*i, *V[i])
        if i in F6 and s in F6:
            col = c[F6[s]+3]; nx, nu, nf = struct.unpack_from('<bbb', c, F6[s]+4)
            c[F6[i]+3] = col; struct.pack_into('<bbb', c, F6[i]+4, -nx, nu, nf)
    # 2. 碰到搬動頂點的面重算法向量
    for f in faces.values():
        if f['o'] in REPLACE or not f['fl'] & 0x60 or not set(f['idx']) & set(MIRROR_V): continue
        nrm, pt = normal_point([V[i] for i in f['idx']], f['fl'])
        struct.pack_into('<hhh', c, f['o']+5, *nrm)
        struct.pack_into('<bbb' if f['fl'] & 0x200 else '<hhh', c, f['o']+11, *pt)
    # 3. 換掉 / 刪掉的面
    tail = bytes(c).find(SIG); blocks = bytearray(); hooks = []
    def hook(o, end, blk):
        hooks.append((o, end, tail + len(blocks))); blocks.extend(blk)
    for o, new in REPLACE.items():
        f = faces[o]; col = struct.unpack_from('<H', c, o+3)[0]
        if new is None:
            c[o:f['end']] = b'\x38' + struct.pack('<h', f['end'] - (o + 3)) + b'\x1e' * (f['end'] - o - 3); continue
        uv = None
        if isinstance(new, str):
            m = faces[int(new.split(':')[1], 16)]
            new = [MIRROR_IDX[i] for i in m['idx']][::-1]; uv = m['uv'][::-1] if m['uv'] else None
            fl = (f['fl'] & ~0x100) | (m['fl'] & 0x100)
        else:
            fl = f['fl']
        b = face_bytes(fl & ~0x400, col, new, [V[i] for i in new], uv)
        if len(b) == f['end'] - o: c[o:f['end']] = b
        else: hook(o, f['end'], b + b'\x00\x00')
    # 4. pod：根節點換成呼叫新區塊
    assert c[ROOT] == 0x0C and c[ROOT+1] == 0 and c[ROOT+14] == 0x38, '根節點不是預期的 0C … 38'
    PV, PN, PF = pod()
    TA = ROOT + 12 + struct.unpack_from('<h', c, ROOT+10)[0]; TB = ROOT + 14 + struct.unpack_from('<h', c, ROOT+12)[0]
    S = tail + len(blocks)
    A = S + 18 + 2; root = bytearray(c[ROOT:ROOT+10]) + struct.pack('<hh', TA - (A+12), TB - (A+14)) + b'\x00\x00'
    B = A + len(root)
    node = struct.pack('<BB6h', 0x06, 0, 0, 0, -16384, 8, 0, 0) + struct.pack('<hh', A - (S+16), B - (S+18)) + b'\x00\x00'
    podb = bytearray(struct.pack('<BBHH', 0x82, 0, len(PV), POD_BASE*8))
    for v in PV: podb += struct.pack('<hhh', *v)
    for k, n in enumerate(PN): podb += struct.pack('<BHBbbb', 0xF6, POD_BASE+k, 0x98, *n)
    allv = dict(V); allv.update({POD_BASE+k: v for k, v in enumerate(PV)})
    for fl, col, idx in PF:
        ids = [POD_BASE+i for i in idx]; podb += face_bytes(fl, col, ids, [allv[i] for i in ids])
    podb += b'\x00\x00'
    hook(ROOT, ROOT+14, node + root + podb)
    for o, end, start in hooks:
        patch = bytearray(b'\x12\x00') + struct.pack('<h', start - (o + 4))
        patch += b'\x38' + struct.pack('<h', end - (o + 7))
        c[o:end] = patch + b'\x1e' * (end - o - len(patch))
    room = nxt - code['va'] - len(c)
    if len(blocks) > room: sys.exit(f'空間不夠：需要 {len(blocks)}，只有 {room}')
    out = insert_blocks(d, pe, secs, code, c, tail, blocks)
    open(dst, 'wb').write(out)
    print(f'{dst}: 搬動 {len(MIRROR_V)} 點、換掉/刪掉 {len(REPLACE)} 個面；pod {len(PV)} 點 {len(PF)} 面；新增 {len(blocks)} 位元組（空間 {room}）')


if __name__ == '__main__': main()
