#!/usr/bin/env python3
"""把一個 SH 的頂點修改（原檔 → 改過的）套到另一個同系列的 SH 上，再重算法向量。

用法：python3 sh_morph.py F18C.SH F18E.SH F18.SH 輸出.SH
  * 三個檔案的 82 頂點緩衝要依順序一一對應，點數和目標格可以不同
  * 目標檔的點如果在原檔同一個緩衝裡找得到相同座標，就照原檔→改過的位移搬動
  * 找不到的點（例如雙座座艙），用最近 6 個已對應點的位移做反距離加權內插，左右對稱
  * 原檔→改過的完全沒動的緩衝就不動；最後呼叫 sh_renormal 重算動到的面
"""
import struct, sys, os, tempfile
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections
import sh_renormal

SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])


def bufs(path):
    d = open(path, 'rb').read(); pe, opt, secs = pe_sections(d); s = next(x for x in secs if x['name'] == 'CODE')
    c = d[s['ro']:s['ro']+s['vs']]; o = c.find(b'\xE2\x00') + 16; sig = c.find(SIG); out = []
    while o < sig - 6:
        if c[o] == 0x82 and c[o+1] == 0:
            n, t = struct.unpack_from('<HH', c, o+2)
            if 0 < n < 900 and t % 8 == 0 and t // 8 + n <= 900:
                out.append((o, t // 8, np.array([struct.unpack_from('<hhh', c, o+6+6*k) for k in range(n)])))
                o += 6 + 6*n; continue
        o += 1
    return d, s['ro'], out


def main(fa, fb, ft, fo):
    _, _, A = bufs(fa); _, _, B = bufs(fb); dT, ro, T = bufs(ft)
    if len(A) != len(B) or len(A) != len(T):
        sys.exit('頂點緩衝的數量對不起來')
    out = bytearray(dT); moved = interp = 0
    for (_, _, PA), (_, _, PB), (o, _, PT) in zip(A, B, T):
        if not (PA != PB).any(): continue
        disp = np.zeros((len(PT), 3)); known = np.zeros(len(PT), bool)
        for i, p in enumerate(PT):
            m = np.where((PA == p).all(1))[0]
            if len(m): disp[i] = PB[m[0]] - PA[m[0]]; known[i] = True
        K, KD = PT[known], disp[known]
        KK, DD = np.r_[K, K * [-1, 1, 1]], np.r_[KD, KD * [-1, 1, 1]]
        for i, p in enumerate(PT):
            if known[i]: continue
            q = np.array([abs(p[0]), p[1], p[2]], float)
            dist = np.linalg.norm(KK - q, axis=1); idx = np.argsort(dist)[:6]
            w = 1 / (dist[idx]**2 + 1); dq = (DD[idx] * w[:, None]).sum(0) / w.sum()
            dq[0] = 0 if p[0] == 0 else (-dq[0] if p[0] < 0 else dq[0])
            disp[i] = dq; interp += 1
        NP = np.round(PT + disp).astype(int)
        for k in range(len(PT)): struct.pack_into('<hhh', out, ro + o + 6 + 6*k, *NP[k])
        moved += int((NP != PT).any(1).sum())
    print(f'搬動 {moved} 點（其中內插 {interp} 點）')
    tmp = tempfile.NamedTemporaryFile(suffix='.SH', delete=False); tmp.write(out); tmp.close()
    sh_renormal.main(ft, tmp.name, fo); os.unlink(tmp.name)


if __name__ == '__main__':
    if len(sys.argv) != 5: sys.exit(__doc__)
    main(*sys.argv[1:5])
