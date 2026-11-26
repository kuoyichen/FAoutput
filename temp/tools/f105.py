#!/usr/bin/env python3
"""F-105D Thunderchief (F105.SH) upgrade (mass-upgrade thread, 2026-11-26).  Stock shape is far too small: 47 ft
long / 28 ft span / 15 ft tall vs the real 64.4 / 34.9 / 19.7 ft -> every absolute vertex buffer (body, fin and
flap pieces, flames, all LODs) scaled x 1.25, fwd 1.37, up 1.3 with the BSP planes, part positions and F2 box
(the resting height follows the longer gear).  Steps: morph -> PT stations scaled the same way (outer pylons out
to the real 60 % semispan; bomb-bay fuel tank stays internal) -> stores (single outer stations on their own side)
-> animated afterburner (J75) -> 3D gear: main legs in the wing roots with the wheel inboard, single nose wheel.
Usage: f105.py OUTDIR"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
import std
from pt_edit import set_hp, scale_eye

KX, KF, KU = 1.25, 1.37, 1.3
warp = lambda v: (v[0] * KX, v[1] * KF, v[2] * KU)
ABS = [0x81, 0x20a7, 0x20fc, 0x2151, 0x21a6, 0x220f, 0x2285, 0x2310, 0x2386, 0x2411, 0x24d5, 0x32bc, 0x347d, 0x355d]
LODS = [0x81, 0x24d5, 0x355d]
PARTS = {'R': 0x1ed8, 'L': 0x1f6e, 'N': 0x2004}
GROUND = -25                                     # stock F2 ymin -19 x 1.3


def make_pt(dst):
    t = open(os.path.join(ROOT, 'PT', 'F105.PT'), encoding='latin1', newline='').read()
    t = scale_eye(t, KX, KU, KF)                 # cockpit eye follows the bigger shape
    t = set_hp(t, 4, u=-20, f=7)
    t = set_hp(t, 5, u=-26, f=12)                # centreline MER
    t = set_hp(t, 6, x=20, u=-15, f=12)          # inboard pylons (450-gal tanks)
    t = set_hp(t, 7, x=31, u=-15, f=2)           # outboard pylons (single: ECM right, AIM-9 left)
    t = set_hp(t, 8, x=-31, u=-15, f=2)
    open(dst, 'w', encoding='latin1', newline='').write(t)


def stores_extra(S):
    for k in (S.AIM54, S.AIM7, S.AAM, S.JDAM): S.SHAPES[k] = S.SHAPES[S.AIM9]
    S.SLOTS.pop('C4', None)                       # bomb-bay fuel tank: internal
    for st in (7, 8):
        if 'R%d' % st in S.SLOTS:
            n_, rank, kd, a = S.SLOTS['R%d' % st]
            S.SLOTS['L%d' % st] = (st, 1, kd, a); del S.SLOTS['R%d' % st]
    S.FALL_SLOTS = {k: i for i, k in enumerate([k for k in ('C5', 'R6', 'L6') if k in S.SLOTS])}


def gear(pos):
    gl = lambda k: GROUND - pos[k]
    m = lambda s: dict(top=(0, 0, 0), bot=(0, 0, gl('R') + 4), wheel=(-2 * s, 0, gl('R') + 4), r=4, w=(-1, 1), sr=0.9,
                       braces=[((0, 0, gl('R') // 2), (0, -8, 0))])
    return {'R': m(1), 'L': m(-1),
            'N': dict(top=(0, 0, 0), bot=(0, 1, gl('N') + 3), wheel=(0, 1, gl('N') + 3), r=3, w=(-1, 1), sr=0.8,
                      braces=[((0, 0, gl('N') // 2), (0, -7, 0))])}


def build(out):
    import struct
    from sh_inspect import load
    os.makedirs(out, exist_ok=True); pt = os.path.join(out, 'F105.PT'); make_pt(pt)
    C4 = {0x1c29: 'R', 0x1763: 'L', 0x1501: 'N'}
    _, _, _, _, c = load(os.path.join(ROOT, 'SH', 'F105.SH'))
    pos = {k: round(struct.unpack_from('<3h', c, p + 2)[1] * KU) for p, k in C4.items()}
    sh, pic = std.chain(os.path.join(ROOT, 'SH', 'F105.SH'), os.path.join(ROOT, 'PIC', '_F105.PIC'), out, 'F105', 'F105',
                        pt=pt, extra=stores_extra, parts=PARTS, gear=gear(pos), flame=85, morph=(warp, ABS, LODS))
    std.render(sh, pic, os.path.join(out, 'preview_F105.png'))


if __name__ == '__main__':
    build(sys.argv[1])
