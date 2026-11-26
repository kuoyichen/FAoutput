#!/usr/bin/env python3
"""A-10A/C Thunderbolt II upgrade (mass-upgrade thread, 2026-11-26).  Base SH/A1G.SH (grey, used by A10/A10C PT;
SH/A10.SH = same geometry, green, used by A10E).  Scale: span 57.5 ft = 162 u (2.83 u/ft); +x = right (GAU-8 muzzle is left).
Shape: 7 deg dihedral on the outer wing panels (outboard of the gear pods, |x| > 28); GAU-8 barrel cluster 3x3 and
2 units longer (was a 1x2 stub).  Gear: single mains on the pod struts, nose wheel offset to the right of the strut
(the real nose gear sits right of centre, the gun on the left).  PT: TF34-GE-100A 2 x 9,065 lbf; wing stations at
real pylon spans (3/9 just outboard of the pods, 2/10, 1/11 on the outer panel)."""
import math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
from pt_edit import set_hp, set_field, get_hp
import morph

TAN = math.tan(math.radians(7))

def warp(v):
    x, f, u = v; ax = abs(x)
    if ax > 28 and f > -40 and -9 <= u <= 3:                    # outer wing panels (not the fins at |x| 28-30, f < -50)
        return (x, f, u + (ax - 28) * TAN)
    if f >= 68 and -1 <= x <= 0 and -6 <= u <= -4:              # GAU-8 muzzle: 3x3 cluster, 2 longer
        return (-0.5 + (x + 0.5) * 3, f + 2 if f > 68 else f, -5 + (u + 5) * 1.5)
    return v

def make_pt(src, dst):
    t = open(src, encoding='latin1', newline='').read()
    for i, nx in ((4, 29), (5, 40), (6, 50)):
        x = int(get_hp(t, i)['x'])
        if x: t = set_hp(t, i, x=nx if x > 0 else -nx)
    t = set_field(t, 'PLANE', 73, 18130)
    open(dst, 'w', encoding='latin1', newline='').write(t)

GEAR = dict(
    parts={'R': 0x3bc5, 'L': 0x3b04, 'N': 0x3d3c},
    span_end={'R': 0x3c77, 'L': 0x3bb6, 'N': 0x3dee},
    gear={
        'R': dict(top=(41, 1, 0), bot=(41, 1, -10), wheel=(44, 1, -10), r=4, w=(-1, 1), braces=[((41, 1, -5), (41, 6, 0))]),
        'L': dict(top=(-41, 1, 0), bot=(-41, 1, -10), wheel=(-44, 1, -10), r=4, w=(-1, 1), braces=[((-41, 1, -5), (-41, 6, 0))]),
        'N': dict(top=(0, 1, 0), bot=(0, 1, -15), wheel=(3, 1, -15), r=3, w=(-1, 1), braces=[((0, 1, -7), (0, -6, 0))]),
    },
    hub_main=(177, 175, 14), hub_nose=(15, 130, 10), clear=[(133, 138, 193, 212), (0, 101, 31, 159)], strip=None)

def stores_extra(S):
    for k in (S.AIM54,): S.SHAPES[k] = S.SHAPES[S.AAM]

def build(var, sh, pic, out):
    os.makedirs(out, exist_ok=True)
    make_pt(os.path.join(ROOT, 'PT', var + '.PT'), os.path.join(out, var + '.PT'))
    morph.apply(os.path.join(ROOT, 'SH', sh), os.path.join(out, 'm1.SH'), warp, [0x80, 0x3def, 0x3eac, 0x3f3f, 0x3ffc])
    import up_stores, up_gear
    up_stores.run(os.path.join(out, 'm1.SH'), os.path.join(out, var + '.PT'), os.path.join(out, 's1.SH'), stores_extra)
    up_gear.run(os.path.join(out, 's1.SH'), os.path.join(ROOT, 'PIC', pic), os.path.join(out, 's3.SH'), os.path.join(out, 's3.PIC'), GEAR)

if __name__ == '__main__':
    build('A10', 'A1G.SH', '_A1G.PIC', '../work/a10')
    build('A10E', 'A10.SH', '_A10.PIC', '../work/a10e')
    make_pt(os.path.join(ROOT, 'PT', 'A10C.PT'), '../work/a10/A10C.PT')
