#!/usr/bin/env python3
"""A-4E / A-4M Skyhawk upgrade (mass-upgrade thread, 2026-11-26).  Stock A4.SH is already to scale (121 x 80 u =
40.3 x 26.5 ft).  Steps: PT -> the real five stations (centreline + inboard and outboard wing pairs; the stock PT had
one single station at x 17 and two single outboard ones), each PT keeping its own stores -> stores -> 3D gear (main
wheels outboard of the legs, single nose wheel on the long nose leg).  No afterburner (J52).
Usage: a4.py OUTDIR"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
from pt_edit import set_station

PARTS = {'R': 0x4329, 'L': 0x449e, 'N': 0x4624}
DEFAULTS = {'A4E': ('F350.GAS', 'MK82HD.JT', 'LAU61.JT'), 'A4M': ('F350.GAS', 'MK82HD.JT', 'AGM65G.JT')}


def make_pt(name, dst):
    t = open(os.path.join(ROOT, 'PT', name + '.PT'), encoding='latin1', newline='').read()
    d = DEFAULTS[name]
    t = set_station(t, 4, 0x1701, 0, -19, -4, d[0], 23, 1, 0)       # centreline (300-gal tank / bomb)
    t = set_station(t, 5, 0x5e5, 14, -17, -10, d[1], 23, 2, 4)      # inboard pylons
    t = set_station(t, 6, 0x5e5, 25, -17, -13, d[2], 10, 2, 4)      # outboard pylons
    open(dst, 'w', encoding='latin1', newline='').write(t)


def stores_extra(S):
    for k in (S.AIM54, S.AIM7, S.AAM, S.JDAM, S.ARM): S.SHAPES[k] = S.SHAPES[S.AIM9]
    S.FALL_SLOTS = {k: i for i, k in enumerate([k for k in ('C4', 'R5', 'L5') if k in S.SLOTS])}


def gear_spec(sh, pic):
    import up_gear as U
    g = {'R': dict(top=(0, -1, 0), bot=(0, -1, -13), wheel=(2, -1, -13), r=3, w=(0, 1), sr=0.8, braces=[((0, -1, -6), (0, 5, 0))]),
         'L': dict(top=(0, -1, 0), bot=(0, -1, -13), wheel=(-2, -1, -13), r=3, w=(-1, 0), sr=0.8, braces=[((0, -1, -6), (0, 5, 0))]),
         'N': dict(top=(2, 1, 0), bot=(2, 1, -14), wheel=(0, 1, -14), r=2, w=(-1, 0), sr=0.8, braces=[((2, 1, -7), (1, -5, 0))])}
    spec = dict(parts=PARTS, gear=g, strip=None)
    spec.update(U.auto_hubs(sh, pic, PARTS, rm=12, rn=9))
    for k in spec['span_end']: spec['span_end'][k] = max(spec['span_end'][k], PARTS[k] + 30)
    return spec


def build(out):
    os.makedirs(out, exist_ok=True)
    import up_stores, up_gear
    for n in DEFAULTS: make_pt(n, os.path.join(out, n + '.PT'))
    s1 = os.path.join(out, 's1.SH'); pic = os.path.join(ROOT, 'PIC', '_A4.PIC')
    up_stores.run(os.path.join(ROOT, 'SH', 'A4.SH'), os.path.join(out, 'A4E.PT'), s1, stores_extra)
    up_gear.run(s1, pic, os.path.join(out, 'A4.SH'), os.path.join(out, '_A4.PIC'), gear_spec(s1, pic))


if __name__ == '__main__':
    build(sys.argv[1])
