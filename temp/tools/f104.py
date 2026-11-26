#!/usr/bin/env python3
"""F-104S Starfighter (F104.SH) upgrade (mass-upgrade thread, 2026-11-26).  Stock shape is to scale (55 ft long,
tip tanks part of the airframe).  Steps: PT (centreline store raised to the belly, the rest stays: under-fuselage AIM-9 rails, inner pylons,
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
    for k in ('R8', 'L8'): S.SLOTS.pop(k, None)           # tip tanks are airframe
    S.FALL_SLOTS = {k: i for i, k in enumerate([k for k in ('C4', 'R6', 'L6') if k in S.SLOTS])}


GEAR = {'R': dict(top=(1, 0, 0), bot=(9, 0, -5), wheel=(11, 0, -5), r=3, w=(-1, 1), sr=0.8, braces=[((5, 0, -3), (1, -6, 0))]),
        'L': dict(top=(-1, 0, 0), bot=(-9, 0, -5), wheel=(-11, 0, -5), r=3, w=(-1, 1), sr=0.8, braces=[((-5, 0, -3), (-1, -6, 0))]),
        'N': dict(top=(0, 0, 0), bot=(0, 0, -5), wheel=(0, 0, -5), r=2, w=(-1, 1), sr=0.7, braces=[((0, 0, -3), (0, 5, 0))])}


def build(out):
    os.makedirs(out, exist_ok=True); pt = os.path.join(out, 'F104S.PT')
    t = open(os.path.join(ROOT, 'PT', 'F104S.PT'), encoding='latin1', newline='').read()
    t = set_hp(t, 4, u=-10)                          # centreline tank up against the belly: clear of the ground line
    open(pt, 'w', encoding='latin1', newline='').write(t)
    sh, pic = std.chain(os.path.join(ROOT, 'SH', 'F104.SH'), os.path.join(ROOT, 'PIC', '_F104.PIC'), out, 'F104', 'F104',
                        pt=pt, extra=stores_extra, parts=PARTS, gear=GEAR, flame=70)
    std.render(sh, pic, os.path.join(out, 'preview_F104.png'))


if __name__ == '__main__':
    build(sys.argv[1])
