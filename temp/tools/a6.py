#!/usr/bin/env python3
"""A-6E / A-6 (A6, A6V) Intruder and EA-6B Prowler (EA6) upgrade (mass-upgrade thread, 2026-11-26).
Stock shapes are to scale (54 x 53 ft).  Steps: PT -> the four wing stations moved inboard of the wing fold
(stock x 50 / 63 sat on the folding outer panels; real pylons are at ~ +-23 / +-35), each single station drawn on
its own side -> stores (EA-6B has no weapon stations: fixed ALQ-99 pods on the centreline and inner pylons,
300-gal tanks outboard, its standard fit) -> 3D gear (single main wheels outboard of the fuselage legs, twin nose
wheels).  No afterburner (J52).
Usage: a6.py OUTDIR"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
from pt_edit import set_hp

SH = {'A6': dict(pts=['A6'], parts={'R': 0x3f2e, 'L': 0x3dcd, 'N': 0x40fa}, ml=-18, nl=-13),
      'A8': dict(pts=['A6V'], parts={'R': 0x3f2e, 'L': 0x3dcd, 'N': 0x40fa}, ml=-18, nl=-13),
      'A6B': dict(pts=['EA6'], parts={'R': 0x41c1, 'L': 0x4060, 'N': 0x439d}, ml=-19, nl=-13)}


def make_pt(name, dst):
    t = open(os.path.join(ROOT, 'PT', name + '.PT'), encoding='latin1', newline='').read()
    if name != 'EA6':
        for i, x, f in ((4, -23, -6), (5, 23, -6), (6, -35, -12), (7, 35, -12)): t = set_hp(t, i, x=x, u=-10, f=f)
    open(dst, 'w', encoding='latin1', newline='').write(t)


def plate(V, F, top, h, f0, f1):
    n = len(V); V = V + [(0, f0, top), (0, f1, top), (0, f1 - 2, top + h), (0, f0 + 2, top + h)]
    return V, F + [(0x661, 152, [n, n + 1, n + 2, n + 3]), (0x661, 152, [n + 3, n + 2, n + 1, n])]


def stores_extra_for(sh):
    def ex(S):
        for k in (S.AIM54, S.AIM7, S.AAM, S.JDAM): S.SHAPES[k] = S.SHAPES[S.AIM9]
        if sh == 'A6B':
            import f18g_growler as G
            Va, Fa = G.alq99(); Vt, Ft = G.tank()
            S.PYLONS['alq'] = plate(Va, Fa, 2, 3, 12, -16)
            S.PYLONS['tnk'] = plate(Vt, Ft, 4, 3, 8, -10)
            S.SLOTS = {}; S.FALL_SLOTS = {}         # no weapon stations on the Prowler: only the fixed fit
            S.PYLON_UNITS = lambda: [('pyALQC', 'alq', (0, -17, -10), -12), ('pyALQR', 'alq', (23, -3, -6), 2),
                                             ('pyALQL', 'alq', (-23, -3, -6), 2), ('pyTNKR', 'tnk', (35, -5, -12), 2),
                                             ('pyTNKL', 'tnk', (-35, -5, -12), 2)]
        else:
            for st in (4, 5, 6, 7):                 # single stations: rank 1 drawn where the PT puts it
                n_, rank, kd, a = S.SLOTS['R%d' % st]
                S.SLOTS['L%d' % st] = (st, 1, kd, a); del S.SLOTS['R%d' % st]
            S.FALL_SLOTS = {}
    return ex


def gear_spec(sh, pic, v):
    import up_gear as U
    m, n = v['ml'] + 4, v['nl'] + 3                 # wheel centres: main r 4, nose r 3, on the stock ground lines
    g = {'R': dict(top=(0, 0, 0), bot=(0, 0, m), wheel=(2, 0, m), r=4, w=(-1, 1), sr=0.9, braces=[((0, 0, m // 2), (0, 6, 0))]),
         'L': dict(top=(0, 0, 0), bot=(0, 0, m), wheel=(-2, 0, m), r=4, w=(-1, 1), sr=0.9, braces=[((0, 0, m // 2), (0, 6, 0))]),
         'N': dict(top=(0, 0, 0), bot=(0, 0, n), wheel=(0, 0, n), r=3, w=(-1, 1), twin=2, sr=0.8, braces=[((0, 0, n // 2), (0, -7, 0))])}
    spec = dict(parts=v['parts'], gear=g, strip=None)
    spec.update(U.auto_hubs(sh, pic, v['parts'], rm=12, rn=10))
    return spec


def build(out):
    os.makedirs(out, exist_ok=True)
    import up_stores, up_gear
    for sh, v in SH.items():
        for p in v['pts']: make_pt(p, os.path.join(out, p + '.PT'))
        s1 = os.path.join(out, sh + '_s1.SH'); pic = os.path.join(ROOT, 'PIC', '_' + sh + '.PIC')
        up_stores.run(os.path.join(ROOT, 'SH', sh + '.SH'), os.path.join(out, 'A6.PT' if sh == 'A6B' else v['pts'][0] + '.PT'), s1, stores_extra_for(sh))
        up_gear.run(s1, pic, os.path.join(out, sh + '.SH'), os.path.join(out, '_' + sh + '.PIC'), gear_spec(s1, pic, v))


if __name__ == '__main__':
    build(sys.argv[1])
