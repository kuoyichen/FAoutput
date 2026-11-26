#!/usr/bin/env python3
"""Generic animated afterburner (sh_ab_flame.py method) for any SH that has FA's stock flame block:
`F0 (cmp _PLafterBurner) ... 12 00 rel16 -> 82 00 10 00 (16 points) + 8 FC faces`.
The profile (F0, CALL, OLD, nozzle / old tail y, face flags) is found in the file; the 3 flame frames go to
41x61 PIC areas that are all 0xFF and used by no textured face.  New length = old length x 57/35 (F-14/F-18 ratio).
Usage: up_ab.py in.SH in.PIC out.SH out.PIC [--grow 3000]"""
import os, struct, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools', 'shgen')); sys.path.insert(0, HERE)
import sh_ab_flame as A
from sh_inspect import load, thunks
from shview import loadpic
import numpy as np


def used_uv(path):
    """UV rectangles of every textured face (all LODs and parts), from the web editor's parser."""
    import json
    return json.loads(subprocess.run(['node', os.path.join(HERE, 'uvboxes.cjs'), path], capture_output=True, text=True, check=True).stdout)


def find_profile(c, th):
    ab = next(k for k, v in th.items() if v == '_PLafterBurner')
    for p in range(len(c) - 30):
        if c[p:p+2] != b'\xf0\x00': continue
        blk = c[p:p+40]
        if struct.pack('<I', 0x1000 + ab) not in blk: continue
        # the F0 returns to the bytecode right after itself; then 12 00 rel16
        for q in range(p + 10, p + 40):
            if c[q:q+2] == b'\x12\x00':
                t = q + 4 + struct.unpack_from('<h', c, q + 2)[0]
                if 0 < t < len(c) and c[t] == 0x82 and struct.unpack_from('<H', c, t + 2)[0] == 16:
                    V = [struct.unpack_from('<3h', c, t + 6 + 6 * i) for i in range(16)]
                    ys = sorted({v[1] for v in V})
                    fl = struct.unpack_from('<H', c, t + 6 + 96 + 1)[0]
                    if len(ys) == 2: return dict(F0=p, CALL=q, OLD=t, NOZ=ys[1], OTAIL=ys[0], FL=fl)
                break
    return None


def free_slots(path, pic, n=3, need_ff=True):
    img = loadpic(pic); h, w = img.shape
    used = np.zeros((h, w), bool)
    for u0, v0, u1, v1 in used_uv(path): used[max(0, v0):v1 + 1, max(0, u0):u1 + 1] = True
    ok = ((img == 255) if need_ff else True) & ~used
    # integral image for rectangle checks
    S = np.zeros((h + 1, w + 1), int); S[1:, 1:] = np.cumsum(np.cumsum(ok, 0), 1)
    full = lambda u, v, W, H: S[v + H, u + W] - S[v, u + W] - S[v + H, u] + S[v, u] == W * H
    out = []; taken = np.zeros((h, w), bool)
    for v in range(0, h - 61):
        for u in range(0, w - 41):
            if full(u, v, 41, 61) and not taken[v:v + 61, u:u + 41].any():
                out.append((u, v, False)); taken[v:v + 61, u:u + 41] = True
                if len(out) == n: return out
    for v in range(0, h - 41):          # rotated 61 x 41
        for u in range(0, w - 61):
            if full(u, v, 61, 41) and not taken[v:v + 41, u:u + 61].any():
                out.append((u, v, True)); taken[v:v + 41, u:u + 61] = True
                if len(out) == n: return out
    return out


def run(src, psrc, dst, pdst, grow=3000, ratio=57 / 35):
    d, pe, secs, code, c = load(src)
    th = thunks(d, secs, code, c)
    P = find_profile(c, th)
    assert P, 'no stock flame block'
    # flame length: F-14 / F-18 approved length is ~31% of the aircraft length (F-14 60 of 191, F-18 57 of 173)
    from sh_subdivide import main_lod
    o, n, _, _ = main_lod(c)[0]
    ys = [struct.unpack_from('<h', c, o + 6 + 6 * k + 2)[0] for k in range(n)]
    P['TAIL'] = round(P['NOZ'] - 0.31 * (max(ys) - min(ys)))
    P['SLOTS'] = free_slots(src, psrc)
    if len(P['SLOTS']) < 3: P['SLOTS'] = free_slots(src, psrc, need_ff=False)   # painted but unused texels (F18T)
    assert len(P['SLOTS']) == 3, ('PIC has no room for 3 flame frames', P['SLOTS'])
    print('afterburner profile', {k: (hex(v) if k in ('F0', 'CALL', 'OLD', 'FL') else v) for k, v in P.items()})
    A.PROFILES['AUTO'] = P
    args = ['AUTO', src, psrc, dst, pdst] + (['--grow', str(grow)] if grow else [])
    sys.argv = ['sh_ab_flame.py'] + args
    A.main()


if __name__ == '__main__':
    a = sys.argv[1:]
    run(a[0], a[1], a[2], a[3], int(a[5]) if len(a) > 5 and a[4] == '--grow' else 3000)


def free_rects(path, pic, sizes, need_ff=True, avoid=(), vmax=None):
    """Top-left corners of free (0xFF, no textured face) rectangles of the given (w, h) sizes, not overlapping."""
    img = loadpic(pic); h, w = img.shape
    used = np.zeros((h, w), bool)
    for u0, v0, u1, v1 in list(used_uv(path)) + list(avoid): used[max(0, v0):v1 + 1, max(0, u0):u1 + 1] = True
    ok = ((img == 255) if need_ff else True) & ~used
    out = []
    for W, H in sizes:
        S = np.zeros((h + 1, w + 1), int); S[1:, 1:] = np.cumsum(np.cumsum(ok, 0), 1)
        hit = None
        for v in range(0, min(h, vmax or h) - H):
            for u in range(0, w - W):
                if S[v + H, u + W] - S[v, u + W] - S[v + H, u] + S[v, u] == W * H: hit = (u, v); break
            if hit: break
        assert hit, ('no free', W, H)
        out.append(hit); ok[hit[1]:hit[1] + H, hit[0]:hit[0] + W] = False
    return out
