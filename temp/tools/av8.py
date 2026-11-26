#!/usr/bin/env python3
"""AV-8B Harrier II (AV8) and Harrier GR7 (HAR7) upgrade (mass-upgrade thread, 2026-11-26).  One stock SH (AV8.SH).
Steps: whole shape scaled 0.93 (stock 49.7 ft long / 32.7 ft span vs real 46.3 / 30.3 ft; BSP planes and part
positions follow) -> PT stations scaled with it -> stores (AV8: single-sided inner stations drawn on their own
side; fixed GAU-12 gun pod + ammo pod under the belly) -> 3D gear: single nose wheel, twin main wheels on the
centreline, wing outriggers, every wheel on the stock main-gear ground line.  HAR7 gets its own copy HAR7.SH
(its PT has a different station list) with the same texture.
Usage: av8.py OUTDIR"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
from pt_edit import set_hp
import morph

S_ = 0.93
ABS = [0x80, 0x341d, 0x3fc7, 0x4311]
LODS = [0x80, 0x341d, 0x4311]
warp = lambda v: tuple(a * S_ for a in v)
PARTS = {'N': 0x33bf, 'M': 0x32a8, 'R': 0x31ed, 'L': 0x312c}
GROUND = -18                                     # stock main-gear wheel bottom (world up)


def make_pt(name, dst):
    t = open(os.path.join(ROOT, 'PT', name + '.PT'), encoding='latin1', newline='').read()
    if name == 'AV8':
        t = set_hp(t, 5, x=-19); t = set_hp(t, 6, x=19); t = set_hp(t, 7, x=26, f=-20); t = set_hp(t, 8, x=30, f=-23)
        t = set_hp(t, 4, u=-16, f=-2)
    else:                                         # GR7: Sidewinder pylons ahead of the outriggers, then two wing pairs
        t = set_hp(t, 4, x=23, f=-14); t = set_hp(t, 5, x=26, f=-20); t = set_hp(t, 6, x=30, f=-23)
        t = t.replace('av8.SH', 'har7.SH').replace('AV8.SH', 'HAR7.SH')
    open(dst, 'w', encoding='latin1', newline='').write(t)


def gunpod(length=30, r=2):
    from f18g_growler import lathe
    e = round(r * .7)
    sec = [(0, r), (e, e), (r, 0), (e, -e), (0, -r), (-e, -e), (-r, 0), (-e, e)]
    h = length / 2
    V, F, _ = lathe(sec, [(h, .5, 0), (h - 2, 1, 0), (-h + 3, 1, 0), (-h, .6, 0)], 150)
    return V, F


def stores_extra_for(name):
    def ex(S):
        for k in (S.AIM54, S.AIM7, S.AAM, S.ARM, S.JDAM): S.SHAPES[k] = S.SHAPES[S.AIM9]
        if name == 'AV8':
            # hp5 (left, MK-82 pair) and hp6 (right, Maverick) are single stations: draw rank 1 on the PT side
            for st in (5, 6):
                n_, rank, kd, a = S.SLOTS['R%d' % st]
                S.SLOTS['L%d' % st] = (st, 1, kd, a); del S.SLOTS['R%d' % st]
            S.PYLONS['gun'] = gunpod(); S.PYLONS['amm'] = gunpod()
            old = S.PYLON_UNITS
            S.PYLON_UNITS = lambda: old() + [('pyGUN', 'gun', (-6, -13, 0), -11), ('pyAMM', 'amm', (6, -13, 0), -11)]
            S.FALL_SLOTS = {k: i for i, k in enumerate([k for k in ('R7', 'L7') if k in S.SLOTS])}
        else:
            S.FALL_SLOTS = {k: i for i, k in enumerate([k for k in ('R5', 'L5') if k in S.SLOTS])}
    return ex


def gear_spec(sh, pic, pos):
    import up_gear as U
    gl = lambda k: GROUND - pos[k]                 # ground in each part's frame
    g = {'N': dict(top=(1, -1, 0), bot=(1, -1, gl('N') + 3), wheel=(-1, -1, gl('N') + 3), r=3, w=(-1, 1)),
         'M': dict(top=(0, 0, 0), bot=(0, 0, gl('M') + 3), wheel=(0, 0, gl('M') + 3), r=3, w=(-1, 1), twin=3, sr=0.9,
                   braces=[((0, 0, -3), (0, 6, 0))]),
         'R': dict(top=(1, 0, 0), bot=(1, 0, gl('R') + 2), wheel=(-1, 0, gl('R') + 2), r=2, w=(-1, 1), sr=0.6),
         'L': dict(top=(-1, 0, 0), bot=(-1, 0, gl('L') + 2), wheel=(1, 0, gl('L') + 2), r=2, w=(-1, 1), sr=0.6)}
    spec = dict(parts=PARTS, gear=g, strip=None)
    spec.update(U.auto_hubs(sh, pic, PARTS, rm=12, rn=12))
    return spec


def build(out):
    os.makedirs(out, exist_ok=True)
    import up_stores, up_gear, struct
    from sh_inspect import load
    src = os.path.join(ROOT, 'SH', 'AV8.SH'); m0 = os.path.join(out, 'm0.SH')
    morph.apply(src, m0, warp, ABS)
    morph.remap(src, m0, warp, LODS)
    _, _, _, _, c = load(m0)
    C4 = {0x17f0: 'N', 0x1d6f: 'M', 0x1aa8: 'R', 0x20e4: 'L'}
    pos = {k: struct.unpack_from('<3h', c, p + 2)[1] for p, k in C4.items()}     # up of each gear part
    print('gear part up', pos)
    for name, shn in (('AV8', 'AV8'), ('HAR7', 'HAR7')):
        make_pt(name, os.path.join(out, name + '.PT'))
        s1 = os.path.join(out, shn + '_s1.SH')
        up_stores.run(m0, os.path.join(out, name + '.PT'), s1, stores_extra_for(name))
        up_gear.run(s1, os.path.join(ROOT, 'PIC', '_AV8.PIC'), os.path.join(out, shn + '.SH'), os.path.join(out, '_AV8.PIC'),
                    gear_spec(s1, os.path.join(ROOT, 'PIC', '_AV8.PIC'), pos))


if __name__ == '__main__':
    build(sys.argv[1])
