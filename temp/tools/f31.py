#!/usr/bin/env python3
"""F-31 (fictional operational X-31, F31W.SH) upgrade (mass-upgrade thread, 2026-11-26).  Stock span 20.7 ft vs the
real X-31's 23.8 ft: wing (|x| > 5) widened x 1.19 with planes, parts and F2 box.  Steps: morph -> PT stations
moved out with the wing -> stores -> animated afterburner (F404; the stock flame is a C4 part between the three
thrust-vectoring paddles, F-22 style) -> 3D gear: main legs from the fuselage with the wheel outboard, single nose
wheel, on the F2 ground line.
Usage: f31.py OUTDIR"""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
import std
from pt_edit import set_hp

K = 1.19
def warp(v):
    x, f, u = v
    if abs(x) > 5: x = (5 + (abs(x) - 5) * K) * (1 if x > 0 else -1)
    return (x, f, u)
WX = lambda x: round(warp((x, 0, 0))[0])
ABS = [0x81, 0x376d, 0x503e]
PARTS = {'R': 0x2b6b, 'L': 0x2c82, 'N': 0x2e04}
C4 = {'R': 0x2a2b, 'L': 0x1f10, 'N': 0x1ffd}
GROUND = -18


def stores_extra(S):
    for k in (S.AIM54, S.AIM7, S.JDAM, S.ARM): S.SHAPES[k] = S.SHAPES[S.AAM]
    S.FALL_SLOTS = {}


def gear(pos):
    gl = lambda k: GROUND - pos[k]
    m = lambda s, k: dict(top=(0, 0, 0), bot=(2 * s, 0, gl(k) + 3), wheel=(4 * s, 0, gl(k) + 3), r=3, w=(-1, 1), sr=0.8,
                          braces=[((s, 0, gl(k) // 2), (0, -6, 0))])
    return {'R': m(1, 'R'), 'L': m(-1, 'L'),
            'N': dict(top=(0, 0, 0), bot=(0, 0, gl('N') + 2), wheel=(0, 1, gl('N') + 2), r=2, w=(-1, 1), sr=0.7,
                      braces=[((0, 0, gl('N') // 2), (0, 6, 0))])}


def build(out):
    from sh_inspect import load
    os.makedirs(out, exist_ok=True); pt = os.path.join(out, 'F31.PT')
    t = open(os.path.join(ROOT, 'PT', 'F31.PT'), encoding='latin1', newline='').read()
    for i, x in ((4, 11), (5, 22)): t = set_hp(t, i, x=WX(x))
    t = set_hp(t, 6, x=WX(27), u=-15, f=-16)     # stock x 35 rail hung outside the wing tip (x 31): outer wing pylon
    open(pt, 'w', encoding='latin1', newline='').write(t)
    src = os.path.join(ROOT, 'SH', 'F31W.SH'); c = load(src)[4]
    pos = {k: struct.unpack_from('<3h', c, p + 2)[1] for k, p in C4.items()}
    s, p = std.chain(src, os.path.join(ROOT, 'PIC', '_F31W.PIC'), out, 'F31W', 'F31W', pt=pt, extra=stores_extra,
                     parts=PARTS, gear=gear(pos), flame=65, flame_at=[0x3699], morph=(warp, ABS, ABS))
    std.render(s, p, os.path.join(out, 'preview_F31W.png'))


if __name__ == '__main__':
    build(sys.argv[1])
