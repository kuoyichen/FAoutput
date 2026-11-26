#!/usr/bin/env python3
"""E-2C Hawkeye (E2C.SH) upgrade (mass-upgrade thread, 2026-11-26).  Big-jet scale (1.45 units per ft, 57.6 ft
long).  Stock faults: the rotodome hung in the air (its pylon stopped at u 9-10, dome bottom at 16) and the gear
stopped 14 units above the F2 ground line (the Hawkeye sat on its belly line, floating 9 ft in game).  Steps:
rotodome pylon added as a fixed unit (streamlined, swept) -> 3D gear: single main wheels from the nacelles, twin nose
wheels with launch-bar brace; gear lengthened so the belly clears the deck by ~3 ft, F2 ymin -28 -> -18.
Usage: e2.py OUTDIR"""
import os, sys, struct, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
import std
from pt_edit import set_station

PARTS = {'R': 0x4929, 'L': 0x4868, 'N': 0x49ea}
G = -18


def pylon_shape():
    from f18g_growler import orient, FLAT, GREY
    V = [(-1.5, 9, 0), (1.5, 9, 0), (1.5, -10, 0), (-1.5, -10, 0), (-1, 4, 12), (1, 4, 12), (1, -7, 12), (-1, -7, 12)]
    V = [tuple(round(a) for a in v) for v in V]
    q = [[0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7], [4, 5, 6, 7]]
    return V, orient(V, [(FLAT, GREY, f) for f in q])


def stores_extra(S):
    S.PYLONS['rdm'] = pylon_shape()
    S.SLOTS = {}; S.FALL_SLOTS = {}
    S.PYLON_UNITS = lambda: [('pyRDM', 'rdm', (0, 4, -11), 16)]


def gear():
    m = lambda s: dict(top=(0, 0, 0), bot=(0, 0, G + 7 + 3), wheel=(2 * s, 0, G + 7 + 3), r=3, w=(-1, 1), sr=1.1,
                       braces=[((0, 0, -5), (0, 6, 0))])
    return {'R': m(1), 'L': m(-1),
            'N': dict(top=(0, 0, 0), bot=(0, 0, G + 7 + 2), wheel=(0, 0, G + 7 + 2), r=2, w=(-1, 1), twin=2, sr=0.9,
                      braces=[((0, 0, -6), (0, 7, -9))])}


def build(out):
    os.makedirs(out, exist_ok=True)
    pt = os.path.join(out, 'layout.PT')                   # configure needs one station; it is cleared again
    t = open(os.path.join(ROOT, 'PT', 'A4E.PT'), encoding='latin1', newline='').read()     # E2.PT has no hp4
    t = set_station(t, 4, 0x1701, 0, -16, 0, 'F150.GAS', 1, 1, 0)
    for i in (5, 6): t = set_station(t, i, 8, 0, 0, 0, None, 0, 1, 1)
    open(pt, 'w', encoding='latin1', newline='').write(t)
    src = os.path.join(out, 'E2C_y.SH'); shutil.copy(os.path.join(ROOT, 'SH', 'E2C.SH'), src); std.set_f2_ymin(src, G)
    s, p = std.chain(src, os.path.join(ROOT, 'PIC', '_E2C.PIC'), out, 'E2C', 'E2C', pt=pt, extra=stores_extra,
                     parts=PARTS, gear=gear())
    std.render(s, p, os.path.join(out, 'preview_E2C.png'))


if __name__ == '__main__':
    build(sys.argv[1])
