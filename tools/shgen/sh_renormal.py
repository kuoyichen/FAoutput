#!/usr/bin/env python3
"""頂點改過的 SH：比對原檔，重算有動到頂點的面的法向量和平面上的點。

用法：python3 sh_renormal.py 原檔.SH 改過頂點.SH 輸出.SH
  * 從標頭後（第一個 E2 貼圖名稱之後）依檔案順序掃描：遇到 82 就更新頂點表（兩個檔各一份），遇到 FC 面就檢查它用到的頂點有沒有改
  * 只處理「用原檔頂點算出的法向量和原檔存的法向量一致」的面（cos > 0.9），以排除掃描到的假面
  * 平面上的點：原檔如果用的是面的某個頂點，就用改過後同一個頂點；否則用重心
  * 位元組長度不變，直接覆寫
"""
import struct, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, parse_face, FACE_OPS

SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])


def code_of(d):
    pe, opt, secs = pe_sections(d)
    s = next(s for s in secs if s['name'] == 'CODE')
    return s['ro'], s['vs']


def newell(P):
    n = np.zeros(3)
    for k in range(len(P)): n += np.cross(P[k], P[(k+1) % len(P)])
    return n


def normal_fa(P):
    """FA 存的法向量（x、上、前，朝外，長度 32767）：ΣP×P 在 (x,y,z) 下朝內"""
    n = -newell(np.array(P, float)); L = np.linalg.norm(n)
    if L < 1e-9: return None
    n = n / L
    return np.array([n[0], n[2], n[1]])


def main(fa, fb, fo):
    A = open(fa, 'rb').read(); B = bytearray(open(fb, 'rb').read())
    ro, vs = code_of(A); assert code_of(B) == (ro, vs) and len(A) == len(B), '兩個檔案的結構不同'
    ca, cb = A[ro:ro+vs], B[ro:ro+vs]
    stop = ca.find(SIG)
    VA, VB = {}, {}
    stats = dict(faces=0, moved=0, fixed=0, skipped=0)
    o = ca.find(b'\xE2\x00') + 16        # 標頭（到第一個貼圖名稱）裡沒有頂點，避免假的 82
    while o < stop - 6:
        op = ca[o]
        if op == 0x82 and ca[o+1] == 0:
            n, t = struct.unpack_from('<HH', ca, o+2)
            if 0 < n < 900 and t % 8 == 0 and t // 8 + n <= 900 and o + 6 + 6*n <= stop:
                for k in range(n):
                    VA[t//8 + k] = struct.unpack_from('<hhh', ca, o+6+6*k)
                    VB[t//8 + k] = struct.unpack_from('<hhh', cb, o+6+6*k)
                o += 6 + 6*n; continue
        if op == 0xFC:
            f = parse_face(ca, o)
            ok = f and f['fl'] & 0x60 and not f['fl'] & 0xF000 and (f['fl'] & 0xFF) in FACE_OPS \
                and len(set(f['idx'])) == f['n'] and all(i in VA for i in f['idx']) and f['end'] <= stop
            if ok:
                PA = [VA[i] for i in f['idx']]; PB = [VB[i] for i in f['idx']]
                stored = np.array(struct.unpack_from('<hhh', ca, o+5), float)
                na = normal_fa(PA)
                if na is None or np.dot(na, stored / (np.linalg.norm(stored) or 1)) < 0.9:
                    o += 1; continue        # 不是真的面（或原檔法向量本來就不一致），不動
                stats['faces'] += 1
                if PA != PB:
                    stats['moved'] += 1
                    nb = normal_fa(PB)
                    if nb is None: stats['skipped'] += 1; o = f['end']; continue
                    small = f['fl'] & 0x200
                    pfmt = '<bbb' if small else '<hhh'
                    pa = struct.unpack_from(pfmt, ca, o+11)
                    # 原檔的平面點：如果是某個頂點 (x、上、前)，就沿用同一個頂點
                    cand = [k for k, p in enumerate(PA) if (p[0], p[2], p[1]) == tuple(pa)]
                    if cand: q = PB[cand[0]]; pt = (q[0], q[2], q[1])
                    else:
                        c = np.mean(np.array(PB, float), 0); pt = (round(c[0]), round(c[2]), round(c[1]))
                    if small and any(abs(v) > 127 for v in pt):
                        c = np.mean(np.array(PB, float), 0); pt = (round(c[0]), round(c[2]), round(c[1]))
                        if any(abs(v) > 127 for v in pt): stats['skipped'] += 1; o = f['end']; continue
                    struct.pack_into('<hhh', B, ro+o+5, *[int(round(v*32767)) for v in nb])
                    struct.pack_into(pfmt, B, ro+o+11, *pt)
                    stats['fixed'] += 1
                o = f['end']; continue
        o += 1
    open(fo, 'wb').write(B)
    print(f"面 {stats['faces']}；頂點有動的面 {stats['moved']}；已重算 {stats['fixed']}；略過 {stats['skipped']}")


if __name__ == '__main__':
    if len(sys.argv) != 4: sys.exit(__doc__)
    main(*sys.argv[1:4])
