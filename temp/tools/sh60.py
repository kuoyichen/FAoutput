#!/usr/bin/env python3
"""SH-60 Seahawk (SH60.SH, PT SH60) (mass-upgrade thread, 2026-11-26).  Like ah64.py: heli SHs have no imports,
so the PT default fit is drawn static.  Real SH-60B/F weapon pylons are stubs on the lower fuselage sides behind the
cabin: right Mk 46 torpedo, left a 120-gal tank inboard and a Mk 46 outboard (PT hp4 / hp3 / hp5).  Body side
x +-12, bottom up -12 at fwd -5..10; stubs at up -6, stores hang below them.
Usage: sh60.py OUTDIR"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
from pt_edit import set_hp

GREY, DARK = 150, 160
F0, U = -4, -7                       # store fwd centre, attach (store top) up
XR, XL, XO = 16, -16, -22            # right torpedo, left tank, left outboard torpedo


def torpedo():
    from fs_core import lathe, FLAT
    r = 1.6; e = r * .7
    sec = [(0, r), (e, e), (r, 0), (e, -e), (0, -r), (-e, -e), (-r, 0), (-e, e)]
    V, F, rings = lathe(sec, [(12.5, .4, -r), (11.5, .85, -r), (10, 1, -r), (-9, 1, -r), (-11, .7, -r), (-12.5, .7, -r)], GREY)
    for k in (0, 2, 4, 6):                                       # tail fins inside the shroud ring
        x, z = sec[k]; tip = (round(x * 1.5), -12, round(-r + z * 1.5)); V.append(tip)
        tri = [rings[3][k], rings[4][k], len(V) - 1]
        F += [(FLAT, DARK, tri), (FLAT, DARK, tri[::-1])]
    return V, F


def tank():
    from fs_core import lathe
    r = 2.2; e = r * .7
    sec = [(0, r), (e, e), (r, 0), (e, -e), (0, -r), (-e, -e), (-r, 0), (-e, e)]
    V, F, _ = lathe(sec, [(11, 0, -r), (9, .6, -r), (6, 1, -r), (-7, 1, -r), (-10, .5, -r), (-11, 0, -r)], GREY)
    return V, F


def stub(x0, x1):
    """Horizontal pylon stub from the body side (x0) out past the store (x1), local to the store attach point."""
    from fs_core import orient, FLAT
    V = [(x, f, u) for x in (x0, x1) for f in (-4, 5) for u in (0, 2)]
    q = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]
    return V, orient(V, [(FLAT, GREY, x) for x in q])


def stores_extra(S):
    tp, tk = torpedo(), tank()
    for k in list(S.SHAPES): S.SHAPES[k] = (lambda v: (lambda: v))(tp)
    S.SHAPES[S.TANK] = (lambda: tk)
    S.SLOTS = {'R4': (4, 1, S.AAM, (XR, U, F0)), 'L3': (3, 1, S.TANK, (XL, U, F0)), 'L5': (5, 1, S.AAM, (XO, U, F0))}
    S.FALL_SLOTS = {}
    S.PYLONS = {'stR': stub(11 - XR, XR + 1 - XR), 'stL': stub(XO - XL - 1, -11 - XL)}   # body side x +-11
    S.PYLON_UNITS = lambda: [('pyR', 'stR', (XR, U, F0), U + 2), ('pyL', 'stL', (XL, U, F0), U + 2)]


def build(out):
    import up_stores, shutil, std
    os.makedirs(out, exist_ok=True)
    t = open(os.path.join(ROOT, 'PT', 'SH60.PT'), encoding='latin1', newline='').read()
    for i, x in ((3, XL), (4, XR), (5, XO)): t = set_hp(t, i, x=x, u=U - 3, f=F0)
    open(os.path.join(out, 'SH60.PT'), 'w', encoding='latin1', newline='').write(t)
    up_stores.run(os.path.join(ROOT, 'SH', 'SH60.SH'), os.path.join(ROOT, 'PT', 'AH64D.PT'), os.path.join(out, 'SH60.SH'), stores_extra, static=True)
    shutil.copy(os.path.join(ROOT, 'PIC', '_SH60.PIC'), os.path.join(out, '_SH60.PIC'))
    std.render(os.path.join(out, 'SH60.SH'), os.path.join(out, '_SH60.PIC'), os.path.join(out, 'preview_SH60.png'))


if __name__ == '__main__':
    build(sys.argv[1])
