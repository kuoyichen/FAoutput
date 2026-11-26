#!/usr/bin/env python3
"""A-37B Dragonfly upgrade (mass-upgrade thread, 2026-11-26).  Stock A37.SH: span 37.3 ft over the tip tanks (real
38.4), kept.  Steps: PT -> the two pylon pairs moved in from the tip (stock x 44 / 50, real A-37B has four pylons
per wing spread across the panel: shown here as the middle / outer pair, x 30 / 40) -> stores (the 95-gal tip
tanks are part of the airframe, so the PT tip station is not drawn again) -> 3D gear: short trailing main legs in
the wing with the wheel inboard, single nose wheel.  No afterburner (J85-GE-17A).
Usage: a37.py OUTDIR"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
from pt_edit import set_hp

PARTS = {'R': 0x319a, 'L': 0x326d, 'N': 0x3348}


def make_pt(dst):
    t = open(os.path.join(ROOT, 'PT', 'A37.PT'), encoding='latin1', newline='').read()
    t = set_hp(t, 4, x=30, u=-10, f=6); t = set_hp(t, 5, x=40, u=-9, f=4)
    open(dst, 'w', encoding='latin1', newline='').write(t)


def stores_extra(S):
    for k in (S.AIM54, S.AIM7, S.AAM, S.JDAM, S.ARM): S.SHAPES[k] = S.SHAPES[S.AIM9]
    for k in ('R6', 'L6'): S.SLOTS.pop(k, None)          # tip tanks are drawn by the airframe
    S.FALL_SLOTS = {k: i for i, k in enumerate([k for k in ('R4', 'L4') if k in S.SLOTS])}


def gear_spec(sh, pic):
    import up_gear as U
    g = {'R': dict(top=(0, 1, 0), bot=(0, -1, -6), wheel=(-2, -1, -6), r=3, w=(-1, 1), sr=0.7, braces=[((0, 0, -3), (0, 4, 0))]),
         'L': dict(top=(0, 1, 0), bot=(0, -1, -6), wheel=(2, -1, -6), r=3, w=(-1, 1), sr=0.7, braces=[((0, 0, -3), (0, 4, 0))]),
         'N': dict(top=(0, 0, 0), bot=(0, 0, -2), wheel=(0, 0, -2), r=2, w=(-1, 1), sr=0.6)}
    spec = dict(parts=PARTS, gear=g, strip=None)
    spec.update(U.auto_hubs(sh, pic, PARTS, rm=10, rn=8))
    return spec


def build(out):
    os.makedirs(out, exist_ok=True)
    import up_stores, up_gear
    make_pt(os.path.join(out, 'A37.PT'))
    s1 = os.path.join(out, 's1.SH'); pic = os.path.join(ROOT, 'PIC', '_A37.PIC')
    up_stores.run(os.path.join(ROOT, 'SH', 'A37.SH'), os.path.join(out, 'A37.PT'), s1, stores_extra)
    up_gear.run(s1, pic, os.path.join(out, 'A37.SH'), os.path.join(out, '_A37.PIC'), gear_spec(s1, pic))


if __name__ == '__main__':
    build(sys.argv[1])
