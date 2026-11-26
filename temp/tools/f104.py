#!/usr/bin/env python3
"""F-104S (F104.SH), F-104A (F10A.SH) and F-104G (F10D.SH) Starfighter upgrade (mass-upgrade thread, 2026-11-26).  Stock shape is to scale (55 ft long,
tip tanks part of the airframe).  Steps: PT (centreline store raised to the belly, the rest stays; F104S: under-fuselage AIM-9 rails, inner pylons,
Sparrow/Aspide outer pylons, tip tanks) -> stores (tip station not drawn again) -> animated afterburner (J79)
-> 3D gear: main legs slanting out from the fuselage with the wheel outboard, single nose wheel.
Usage: f104.py OUTDIR"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
import std
from pt_edit import set_hp

PARTS = {'R': 0x4b53, 'L': 0x4d4d, 'N': 0x4f47}


def stores_extra(S):
    for k in (S.AIM54, S.AAM, S.JDAM, S.ARM): S.SHAPES[k] = S.SHAPES[S.AIM9]
    for k in [k for k, v in S.SLOTS.items() if abs(v[3][0]) > 34]: S.SLOTS.pop(k)    # tip tanks are airframe
    S.FALL_SLOTS = {k: i for i, k in enumerate([k for k in ('C4', 'R6', 'L6') if k in S.SLOTS])}


GEAR = {'R': dict(top=(1, 0, 0), bot=(9, 0, -5), wheel=(11, 0, -5), r=3, w=(-1, 1), sr=0.8, braces=[((5, 0, -3), (1, -6, 0))]),
        'L': dict(top=(-1, 0, 0), bot=(-9, 0, -5), wheel=(-11, 0, -5), r=3, w=(-1, 1), sr=0.8, braces=[((-5, 0, -3), (-1, -6, 0))]),
        'N': dict(top=(0, 0, 0), bot=(0, 0, -5), wheel=(0, 0, -5), r=2, w=(-1, 1), sr=0.7, braces=[((0, 0, -3), (0, 5, 0))])}


VAR = {'F104': 'F104S', 'F10A': 'F104', 'F10D': 'F104G'}     # SH -> PT (same geometry, own textures)


def build(out):
    from pt_edit import get_hp
    os.makedirs(out, exist_ok=True)
    for sh, p in VAR.items():
        pt = os.path.join(out, p + '.PT')
        t = open(os.path.join(ROOT, 'PT', p + '.PT'), encoding='latin1', newline='').read()
        if get_hp(t, 4)['x'] == '0': t = set_hp(t, 4, u=-10)      # centreline tank up against the belly: clear of the ground
        open(pt, 'w', encoding='latin1', newline='').write(t)
        s, pic = std.chain(os.path.join(ROOT, 'SH', sh + '.SH'), os.path.join(ROOT, 'PIC', '_' + sh + '.PIC'), out, sh, sh,
                           pt=pt, extra=stores_extra, parts=PARTS, gear=GEAR, flame=70)
        std.render(s, pic, os.path.join(out, 'preview_' + sh + '.png'))


if __name__ == '__main__':
    build(sys.argv[1])
