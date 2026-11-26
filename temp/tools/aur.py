#!/usr/bin/env python3
"""Aurora (AUR.SH, fictional US hypersonic jet) upgrade (mass-upgrade thread, 2026-11-26).  The stock shape already
has the animated 3-frame afterburner (the reference for the other ports).  Step: 3D gear on the stock C4 parts:
the main part holds both main legs (abs x +12 and -14, one billboard part), drawn as two twin-wheel legs in one
part (up_gear pair), single nose wheel, on the F2 ground line (-29).
Usage: aur.py OUTDIR"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
import std

PARTS = {'R': 0x2493, 'N': 0x25aa}
GM, GN = -13, -27          # ground in part frames (main part up -16, nose part up -2)


def gear():
    return {'R': dict(top=(0, 2, 0), bot=(0, 2, GM + 3), wheel=(0, 2, GM + 3), r=3, w=(-1, 1), twin=2, sr=1.0, pair=(-26, 0, 0),
                      braces=[((0, 2, GM // 2), (0, 9, 0))]),
            'N': dict(top=(0, -3, 0), bot=(0, -3, GN + 3), wheel=(0, -3, GN + 3), r=3, w=(-1, 1), twin=2, sr=1.0,
                      braces=[((0, -3, GN // 2), (0, -11, 0))])}


def build(out):
    s, p = std.chain(os.path.join(ROOT, 'SH', 'AUR.SH'), os.path.join(ROOT, 'PIC', '_AUR.PIC'), out, 'AUR', 'AUR', parts=PARTS, gear=gear())
    std.render(s, p, os.path.join(out, 'preview_AUR.png'))


if __name__ == '__main__':
    build(sys.argv[1])
