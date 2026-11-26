#!/usr/bin/env python3
"""F-15E Strike Eagle / F-15I Ra'am upgrade (mass-upgrade thread, 2026-11-26).
Steps: PT (realistic stations; thrust already F100-PW-229) -> stores (CFT tangential MK-82 x4 in two rows,
centreline GBU-10, wing pylon 600-gal tank + 2 AIM-9 rails, fixed LANTIRN pods under the intakes)
-> animated afterburner -> 3D gear with spinning wheels.
Usage: f15e.py OUTDIR [E|I]"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
from pt_edit import set_hp
import f15c

VAR = {'E': dict(sh='F15E', pic='_F15E', pts=['F15E', 'F15E2']),
       'I': dict(sh='F15I', pic='_F15I', pts=['F15I'])}


def make_pt(src, dst):
    t = open(src, encoding='latin1', newline='').read()
    # SH units (~3.1 u/ft); belly -13, CFT lower edge x 16..21 up -12 from fwd -31 to 35, intake lip fwd 42
    t = set_hp(t, 4, x=0, u=-20, f=-4)               # centreline (GBU-10 / tank)
    t = set_hp(t, 5, x=19, u=-19, f=14)              # CFT lower tangential row, front pair (rear pair drawn 30 behind)
    t = set_hp(t, 6, x=30, u=-12, f=2)               # wing pylon (600-gal tank / bombs), as the F-15C
    t = set_hp(t, 7, x=25, u=-8, f=4)                # inboard LAU-114 rail AIM-9
    t = set_hp(t, 8, x=35, u=-8, f=4)                # outboard rail
    open(dst, 'w', encoding='latin1', newline='').write(t)


def pod(length, r, nose_black=True):
    """LANTIRN pod hanging from a short pylon: octagon body radius r along fwd, nose at +length/2 with a dark
    sensor window, pylon plate from the body top up 3 units (into the intake underside)."""
    from f18g_growler import lathe, orient
    e = round(r * .7)
    sec = [(0, r), (e, e), (r, 0), (e, -e), (0, -r), (-e, -e), (-r, 0), (-e, e)]
    h = length / 2
    V, F, rings = lathe(sec, [(h, .5, 0), (h - 1, .9, 0), (h - 3, 1, 0), (-h + 2, 1, 0), (-h, .7, 0)], 150)
    if nose_black:                                   # front cap: FLIR / tracker window, solid black (lighting rule)
        cap = set(rings[0])
        F = [((fl & ~0x22) | 0x01, 160, idx) if set(idx) == cap else (fl, col, idx) for fl, col, idx in F]
    n = len(V)
    V += [(0, round(h - 4), r), (0, round(-h + 4), r), (0, round(-h + 5), r + 3), (0, round(h - 5), r + 3)]
    F += [(0x661, 152, [n, n + 1, n + 2, n + 3]), (0x661, 152, [n + 3, n + 2, n + 1, n])]
    return V, F


def stores_extra(S):
    import f18v_upgrade as U
    S.SHAPES[S.TANK] = f15c.tank600(S)
    for k in (S.ARM, S.AIM54):                       # never carried by the F-15E: AIM-120 bytes, stored once
        S.SHAPES[k] = S.SHAPES[S.AAM]
    st, rank, kd, (x, u, f) = S.SLOTS['R5']
    S.SLOTS['R5b'] = (st, 4, kd, (x, u, f - 30)); S.SLOTS['L5b'] = (st, 3, kd, (-x, u, f - 30))
    fus = {'R5', 'L5', 'R5b', 'L5b'}
    S.PLACER = lambda c, ROOT, ugeo, ubox: U.placer(c, ROOT, ugeo, ubox, fus)
    S.FALL_SLOTS = {'C4': 0, 'R6': 1, 'L6': 2}
    # AN/AAQ-13 navigation pod under the right intake, AN/AAQ-14 targeting pod under the left, noses at fwd 46
    S.PYLONS['nav'] = pod(20, 2); S.PYLONS['tgt'] = pod(24, 2)
    old = S.PYLON_UNITS
    S.PYLON_UNITS = lambda: old() + [('pyNAV', 'nav', (11, -16, 36), -12), ('pyTGT', 'tgt', (-11, -16, 34), -12)]


def build(var, out):
    v = VAR[var]; os.makedirs(out, exist_ok=True)
    for p in v['pts']:
        make_pt(os.path.join(ROOT, 'PT', p + '.PT'), os.path.join(out, p + '.PT'))
    import up_stores, up_ab, up_gear, f15e_gear
    up_stores.run(os.path.join(ROOT, 'SH', v['sh'] + '.SH'), os.path.join(out, v['pts'][0] + '.PT'), os.path.join(out, 's1.SH'), stores_extra)
    import subprocess
    subprocess.run([sys.executable, os.path.join(HERE, 'up_ab.py'), os.path.join(out, 's1.SH'), os.path.join(ROOT, 'PIC', v['pic'] + '.PIC'),
                    os.path.join(out, 's2.SH'), os.path.join(out, 's2.PIC')], check=True)
    up_gear.run(os.path.join(out, 's2.SH'), os.path.join(out, 's2.PIC'), os.path.join(out, 's3.SH'), os.path.join(out, 's3.PIC'), f15e_gear.spec)


if __name__ == '__main__':
    build(sys.argv[2] if len(sys.argv) > 2 else 'E', sys.argv[1])
