#!/usr/bin/env python3
"""F-29 (fictional operational X-29, F29.SH) upgrade (mass-upgrade thread, 2026-11-26).  Steps: PT (middle wing pair hp5 moved under the forward-swept wing: stock f 15 sat ahead of the leading edge) ->
stores -> animated afterburner (F404) -> 3D gear: F-5 style main legs from the fuselage with the wheel outboard,
single nose wheel, all on the F2 ground line.
Usage: f29.py OUTDIR"""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
import std
from pt_edit import set_hp

PARTS = {'R': 0x2e82, 'L': 0x2fe3, 'N': 0x3116}
C4 = {'R': 0x2986, 'L': 0x28d7, 'N': 0x29d3}
GROUND = -27


def stores_extra(S):
    for k in (S.AIM54, S.AIM7, S.JDAM, S.ARM): S.SHAPES[k] = S.SHAPES[S.AAM]
    S.FALL_SLOTS = {}


def gear(pos):
    gl = lambda k: GROUND - pos[k]
    m = lambda s, k: dict(top=(2 * s, 0, 0), bot=(8 * s, 0, gl(k) + 3), wheel=(10 * s, 0, gl(k) + 3), r=3, w=(-1, 1), sr=0.8,
                          braces=[((5 * s, 0, gl(k) // 2), (2 * s, -7, 0))])
    return {'R': m(1, 'R'), 'L': m(-1, 'L'),
            'N': dict(top=(0, 0, 0), bot=(0, 0, gl('N') + 2), wheel=(0, 1, gl('N') + 2), r=2, w=(-1, 1), sr=0.7,
                      braces=[((0, 0, gl('N') // 2), (0, 6, 0))])}


def build(out):
    from sh_inspect import load
    src = os.path.join(ROOT, 'SH', 'F29.SH'); c = load(src)[4]
    pos = {k: struct.unpack_from('<3h', c, p + 2)[1] for k, p in C4.items()}
    os.makedirs(out, exist_ok=True); pt = os.path.join(out, 'F29.PT')
    t = open(os.path.join(ROOT, 'PT', 'F29.PT'), encoding='latin1', newline='').read()
    open(pt, 'w', encoding='latin1', newline='').write(set_hp(set_hp(t, 5, u=-10, f=-6), 6, u=-10))
    s, p = std.chain(src, os.path.join(ROOT, 'PIC', '_F29.PIC'), out, 'F29', 'F29', pt=pt,
                     extra=stores_extra, parts=PARTS, gear=gear(pos), flame=65)
    std.render(s, p, os.path.join(out, 'preview_F29.png'))


if __name__ == '__main__':
    build(sys.argv[1])
