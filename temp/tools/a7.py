#!/usr/bin/env python3
"""A-7 Corsair II (A7, A7D, A7V) upgrade (mass-upgrade thread, 2026-11-26).  Stock A7.SH is to scale (46.7 x 38 ft).
Steps: PT -> wing pylons at the real inboard / middle / outboard positions (stock outboard pair sat at 90 % span),
the inboard single stations drawn on their own side -> stores -> 3D gear (main legs slanting out of the fuselage
with the wheel outboard, twin nose wheels).  LIGHTN.PT (English Electric Lightning stand-in that borrowed a7.SH)
is pointed at an unchanged copy A7L.SH, so the A-7 stores never show on it; the PIC keeps the stock gear art.
Usage: a7.py OUTDIR"""
import os, sys, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
from pt_edit import set_hp

PARTS = {'R': 0x3bf5, 'L': 0x3d76, 'N': 0x3f86}


def make_pt(name, dst):
    t = open(os.path.join(ROOT, 'PT', name + '.PT'), encoding='latin1', newline='').read()
    if name == 'LIGHTN':
        t = t.replace('a7.SH', 'a7l.SH')
    else:
        t = set_hp(t, 5, x=-17); t = set_hp(t, 6, x=17); t = set_hp(t, 7, x=28); t = set_hp(t, 8, x=39, f=-13)
    open(dst, 'w', encoding='latin1', newline='').write(t)


def stores_extra(S):
    for k in (S.AIM54, S.AIM7, S.AAM, S.JDAM): S.SHAPES[k] = S.SHAPES[S.AIM9]
    for st in (5, 6):
        n_, rank, kd, a = S.SLOTS['R%d' % st]
        S.SLOTS['L%d' % st] = (st, 1, kd, a); del S.SLOTS['R%d' % st]
    S.FALL_SLOTS = {k: i for i, k in enumerate([k for k in ('L5', 'L6') if k in S.SLOTS])}


def gear_spec(sh, pic):
    import up_gear as U
    g = {'R': dict(top=(-5, 0, 0), bot=(-3, 0, -11), wheel=(0, 0, -11), r=3, w=(-1, 1), sr=0.9, braces=[((-4, 0, -5), (-6, 7, 0))]),
         'L': dict(top=(5, 0, 0), bot=(3, 0, -11), wheel=(0, 0, -11), r=3, w=(-1, 1), sr=0.9, braces=[((4, 0, -5), (6, 7, 0))]),
         'N': dict(top=(2, 0, 0), bot=(2, 0, -10), wheel=(2, 0, -10), r=3, w=(-1, 1), twin=2, sr=0.8, braces=[((2, 0, -5), (2, -7, 0))])}
    spec = dict(parts=PARTS, gear=g, strip=None)
    spec.update(U.auto_hubs(sh, pic, PARTS, rm=12, rn=10, keep_old=True)); spec['clear'] = []
    return spec


def build(out):
    os.makedirs(out, exist_ok=True)
    import up_stores, up_gear
    for n in ('A7', 'A7D', 'A7V', 'LIGHTN'): make_pt(n, os.path.join(out, n + '.PT'))
    shutil.copy(os.path.join(ROOT, 'SH', 'A7.SH'), os.path.join(out, 'A7L.SH'))
    s1 = os.path.join(out, 's1.SH'); pic = os.path.join(ROOT, 'PIC', '_A7.PIC')
    import f18v_upgrade; f18v_upgrade.intake_lip = lambda d: 200     # chin intake: the fuselage AIM-9 rails stay where the PT puts them
    up_stores.run(os.path.join(ROOT, 'SH', 'A7.SH'), os.path.join(out, 'A7.PT'), s1, stores_extra)
    up_gear.run(s1, pic, os.path.join(out, 'A7.SH'), os.path.join(out, '_A7.PIC'), gear_spec(s1, pic))


if __name__ == '__main__':
    build(sys.argv[1])
