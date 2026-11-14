#!/usr/bin/env python3
"""修正面的「平面上的點」（背面剔除用）偏離面本身的 SH。

用法：python3 sh_fixpt.py 輸入.SH 輸出.SH [門檻=2]
  * FA 的背面剔除（FC 處理程式 0x4D43DC）算 n·(眼睛 − 平面點)，< 0 就不畫。
    平面點如果離面 d 個單位，攝影機在面和那個點之間的 d 單位厚的區域時就會判斷錯：
    該藏的背面被畫出來（蓋在機身上），或該畫的面消失。遠處看那個區域只是一條線，
    靠近（從機頭或機尾貼近看）才會變成一大片，所以問題只在近距離外部視角出現。
  * 依檔案順序掃描（82 更新頂點表、FC 用當下的頂點表），只處理有法向量且有 0x40 剔除旗標的面。
    只改各 LOD 主體（target 0 的 82 緩衝）的面；零件緩衝（起落架、襟翼等）之後的面不動，
    它們的平面點在原廠檔裡就跟零件座標對不上（SU35B 也一樣），不是這次的問題。
  * 面的頂點離存的平面超過門檻時，把平面點換成面上「最靠背面」的頂點（n·P 最小），
    這樣面絕不會被誤剔除，殘差小於 1 單位。法向量不動（法向量也錯時先跑 sh_renormal.py）。
  * 旗標 0x200 的平面點是 i8，超出 −128..127 的頂點不能用，改挑範圍內的頂點。
  * 位元組長度不變，直接覆寫。
"""
import struct, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, parse_face, FACE_OPS

SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])


def fix(d, thr=2.0):
    d = bytearray(d)
    pe, opt, secs = pe_sections(d)
    s = next(s for s in secs if s['name'] == 'CODE'); ro, vs = s['ro'], s['vs']
    c = bytes(d[ro:ro+vs]); stop = c.find(SIG)
    V = {}; out = []; inpart = False
    o = c.find(b'\xE2\x00') + 16          # 標頭裡沒有頂點，避免假的 82
    while o < stop - 6:
        op = c[o]
        if op == 0x82 and c[o+1] == 0:
            n, t = struct.unpack_from('<HH', c, o+2)
            if 0 < n < 900 and t % 8 == 0 and t // 8 + n <= 900 and o + 6 + 6*n <= stop:
                if t == 0: V = {}
                inpart = t != 0                   # 零件緩衝之後的面用零件座標（C4 會先扣掉位置），不動
                for k in range(n): V[t//8 + k] = struct.unpack_from('<hhh', c, o+6+6*k)
                o += 6 + 6*n; continue
        if op == 0xFC:
            f = parse_face(c, o)
            ok = f and not inpart and f['fl'] & 0x40 and not f['fl'] & 0xF000 and (f['fl'] & 0xFF) in FACE_OPS \
                and len(set(f['idx'])) == f['n'] and all(i in V for i in f['idx']) and f['end'] <= stop
            if ok:
                P = np.array([V[i] for i in f['idx']], float)          # (x, 前, 上)
                nn = np.array(struct.unpack_from('<hhh', c, o+5), float)  # (x, 上, 前)
                if np.linalg.norm(nn) < 30000: o += 1; continue          # 不是真的面
                small = f['fl'] & 0x200; pfmt = '<bbb' if small else '<hhh'
                pt = np.array(struct.unpack_from(pfmt, c, o+11), float)
                Pu = P[:, [0, 2, 1]]                                      # → (x, 上, 前)
                dist = (Pu - pt) @ nn / 32767
                if np.ptp(P, 0).max() > 0 and abs(dist).max() > thr:
                    cand = [p for p in Pu if not small or all(-128 <= v <= 127 for v in p)]
                    if cand:
                        q = min(cand, key=lambda p: p @ nn)
                        new = tuple(int(v) for v in q)
                        struct.pack_into(pfmt, d, ro+o+11, *new)
                        out.append((o, tuple(int(v) for v in pt), new, round(float(abs(dist).max()), 1)))
                o = f['end']; continue
        o += 1
    return bytes(d), out


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    thr = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
    d, out = fix(open(sys.argv[1], 'rb').read(), thr)
    open(sys.argv[2], 'wb').write(d)
    for o, a, b, dv in out: print(f'CODE+{o:#06x}  平面點 {a} → {b}（原本離面 {dv} 單位）')
    print(f'修正 {len(out)} 個面')
