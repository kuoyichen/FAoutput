#!/usr/bin/env python3
"""F-15C Eagle upgrade (mass-upgrade thread, 2026-11-26).
Steps: PT (realistic stations + F100-PW-220 thrust) -> stores (4 fuselage AIM-7/120, wing pylon tank + 2 rails,
centreline tank) -> afterburner (animated, grows) -> 3D gear with spinning wheels.
Usage: f15c.py OUTDIR"""
import os, sys, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
from pt_edit import set_hp, set_field, get_hp

def make_pt(src, dst):
    t = open(src, encoding='latin1', newline='').read()
    # stations, in SH units (1 unit ~ 0.31 ft); store centre is drawn 5 above the PT launch point (PT_DROP)
    t = set_hp(t, 4, x=0, u=-19, f=-4)              # centreline 600-gal tank under the flat belly (up -12)
    t = set_hp(t, 5, x=13, u=-20, f=30)              # fuselage AIM-7/120 under the intake corners (front pair; rear pair drawn at f -25)
    t = set_hp(t, 6, x=30, u=-12, f=2)               # wing pylon 600-gal tank, ~45% semispan
    t = set_hp(t, 7, x=25, u=-8, f=4)                # inboard LAU-114 rail AIM-9
    t = set_hp(t, 8, x=35, u=-8, f=4)                # outboard rail
    # F100-PW-220 x2: 14,590 lbf MIL, 23,770 lbf AB each
    t = set_field(t, 'PLANE', 73, 29180)
    t = set_field(t, 'PLANE', 74, 47540)
    open(dst, 'w', encoding='latin1', newline='').write(t)

# ---------------------------------------------------------------- stores
def tank600(S):
    """F-15 600-gal tank: ~19.6 ft x 2.6 ft (63 x 4.2 units), pointed nose, short tail cone, no fins."""
    def f():
        r = 4; e = round(r * .7)
        sec = [(0, r), (e, e), (r, 0), (e, -e), (0, -r), (-e, -e), (-r, 0), (-e, e)]
        st = [(31, 0, -r), (27, .35, -r), (21, .7, -r), (15, .92, -r), (9, 1, -r), (-15, 1, -r), (-22, .8, -r),
              (-28, .5, -r), (-32, .25, -r)]
        V, F, rings = S.lathe(sec, st, S.WHITE)
        return V, F
    return f


def stores_extra(S):
    import f18v_upgrade as U
    S.SHAPES[S.TANK] = tank600(S)
    for k in (S.ARM, S.LGB, S.BOMB, S.JDAM, S.AIM54):     # F-15C never carries these: same bytes as AIM-120, stored once
        S.SHAPES[k] = S.SHAPES[S.AAM]
    # rear fuselage pair (count 4 on hp5): ranks 3/4, 55 units behind the front pair, behind the main gear wells
    st, rank, kd, (x, u, f) = S.SLOTS['R5']
    S.SLOTS['R5b'] = (st, 4, kd, (x, u, f - 55)); S.SLOTS['L5b'] = (st, 3, kd, (-x, u, f - 55))
    fus = {'R5', 'L5', 'R5b', 'L5b'}
    S.PLACER = lambda c, ROOT, ugeo, ubox: U.placer(c, ROOT, ugeo, ubox, fus)
    S.FALL_SLOTS = {'C4': 0, 'R6': 1, 'L6': 2}           # only the tanks fall when jettisoned


if __name__ == '__main__':
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    make_pt(os.path.join(ROOT, 'PT', 'F15.PT'), os.path.join(out, 'F15.PT'))
    print('PT ok')
    import up_stores
    up_stores.run(os.path.join(ROOT, 'SH', 'F15.SH'), os.path.join(out, 'F15.PT'), os.path.join(out, 's1.SH'), stores_extra)

