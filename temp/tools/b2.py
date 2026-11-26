#!/usr/bin/env python3
"""B-2A Spirit (B2.SH, also TR-3A) upgrade (mass-upgrade thread, 2026-11-26).  Stock shape to the fighter scale
(172 ft span).  Weapons internal, no afterburner.  Step: 3D gear on the stock C4 gear parts: main gear as four-wheel
bogies, twin nose wheels, on the F2 ground line.
Usage: b2.py OUTDIR"""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
import std

PARTS = {'R': 0x350e, 'L': 0x33fd, 'N': 0x3579}
C4 = {'R': 0x2eef, 'L': 0x2f3c, 'N': 0x2fd9}
GROUND = -32


def gear(pos):
    gl = lambda k: GROUND - pos[k]
    m = lambda k: dict(top=(0, 4, 0), bot=(0, 4, gl(k) + 5), wheel=(0, 4, gl(k) + 5), r=5, w=(-1, 1), twin=3, quad=-11, sr=1.3,
                       braces=[((0, 4, gl(k) // 2), (0, 14, 0))])
    return {'R': m('R'), 'L': m('L'),
            'N': dict(top=(0, 0, 0), bot=(0, 0, gl('N') + 3), wheel=(0, 0, gl('N') + 3), r=3, w=(-1, 1), twin=2, sr=1.0,
                      braces=[((0, 0, gl('N') // 2), (0, 8, 0))])}


def build(out):
    from sh_inspect import load
    src = os.path.join(ROOT, 'SH', 'B2.SH'); c = load(src)[4]
    pos = {k: struct.unpack_from('<3h', c, p + 2)[1] for k, p in C4.items()}
    s, p = std.chain(src, os.path.join(ROOT, 'PIC', '_B2.PIC'), out, 'B2', 'B2', parts=PARTS, gear=gear(pos))
    std.render(s, p, os.path.join(out, 'preview_B2.png'))


if __name__ == '__main__':
    build(sys.argv[1])
