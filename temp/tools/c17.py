#!/usr/bin/env python3
"""C-17A Globemaster III (C1G.SH) upgrade (mass-upgrade thread, 2026-11-26).  Stock shape to scale.  No stores, no
afterburner.  Step: 3D gear on the stock C4 parts: each main gear pod as a four-wheel bogie (the real gear has
two legs of three wheels a side), twin nose wheels, on the F2 ground line.
Usage: c17.py OUTDIR"""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
import std

PARTS = {'R': 0x3510, 'L': 0x35d1, 'N': 0x3692}
C4 = {'R': 0x2d9f, 'L': 0x2d04, 'N': 0x34e1}
GROUND = -53


def gear(pos):
    gl = lambda k: GROUND - pos[k]
    m = lambda k: dict(top=(0, -8, 0), bot=(0, -8, gl(k) + 5), wheel=(0, -8, gl(k) + 5), r=5, w=(-2, 2), twin=5, tri=True, quad=-13, tandem=True, sr=1.3,
                       braces=[((0, -8, gl(k) // 2), (0, -20, 0))])
    return {'R': m('R'), 'L': m('L'),
            'N': dict(top=(0, 0, 0), bot=(0, 0, gl('N') + 4), wheel=(0, 0, gl('N') + 4), r=4, w=(-1, 1), twin=3, sr=1.2,
                      braces=[((0, 0, gl('N') // 2), (0, 10, 0))])}


def build(out):
    from sh_inspect import load
    src = os.path.join(ROOT, 'SH', 'C1G.SH'); c = load(src)[4]
    pos = {k: struct.unpack_from('<3h', c, p + 2)[1] for k, p in C4.items()}
    s, p = std.chain(src, os.path.join(ROOT, 'PIC', '_C1G.PIC'), out, 'C1G', 'C1G', parts=PARTS, gear=gear(pos))
    std.render(s, p, os.path.join(out, 'preview_C1G.png'))


if __name__ == '__main__':
    build(sys.argv[1])
