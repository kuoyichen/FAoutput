#!/usr/bin/env python3
"""F-22A Raptor upgrade (mass-upgrade thread, 2026-11-26).  Base SH/ATF.SH (+ _ATF.PIC), PT/F22.PT.
Shape (F-22A: span 44.5 ft, wing LE 42 deg, taper 0.17, 3.25 deg anhedral, stabilator span 29 ft; scale 189 u = 62.1 ft):
  * wing tips out from |x| 63.5 to 67.7 with 3.25 deg anhedral outboard of the body side (|x| 18)
  * stabilator tips moved 2 in / 4 back -> LE sweep ~41 deg (was ~33)
  * dorsal spine up to 3 higher between canopy and fins, canopy 1.5 taller
  * fins 10 % lower (fin top was ~5 units above the real height)
PT: F119-PW-100 x2 (26,000 lbf MIL / 35,000 lbf AB each); underwing pylons at 32 % / 59 % semispan.
Stores: only the 4 underwing pylons are drawn (main / side bay weapons stay hidden inside the closed bays)."""
import math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
from pt_edit import set_hp, set_field
import morph

TAN_AN = math.tan(math.radians(3.25))

def warp(v):
    x, f, u = v; ax = abs(x); sg = 1 if x >= 0 else -1
    if 13 <= ax <= 30 and u > 5 and -50 < f < -5:               # canted fins: shrink 10 % about the root (14, 4)
        return (sg * (14 + (ax - 14) * 0.9), f, 4 + (u - 4) * 0.9)
    if ax <= 14 and 2 <= u <= 9 and -52 < f < 48:               # deeper dorsal: the real spine stays high to the fins
        k = (f + 52) / 52 if f < 0 else (1.0 if f < 27 else (48 - f) / 21)
        return (x, f, u + 3 * k * min(1.0, (u - 1) / 3))
    if ax <= 9 and u >= 11 and 45 <= f <= 82:                   # canopy bubble a little taller
        return (x, f, u + 1.5)
    if ax > 18 and -6 <= u <= 4:
        if f <= -50 and ax >= 40:                               # stabilator tip
            return (sg * (ax - 2), f - 4, u)
        if f > -42:                                             # wing
            s = min(1.0, (ax - 18) / (63.5 - 18))
            nx = 18 + s * (67.7 - 18) if ax <= 63.5 else ax + 4.2
            return (sg * nx, f, u - (nx - 18) * TAN_AN)
    return v

def make_pt(src, dst):
    t = open(src, encoding='latin1', newline='').read()
    t = set_hp(t, 7, x=22); t = set_hp(t, 8, x=40)
    t = set_field(t, 'PLANE', 73, 52000); t = set_field(t, 'PLANE', 74, 70000)
    open(dst, 'w', encoding='latin1', newline='').write(t)

ABS_BUFS = [0x80, 0x323c, 0x3337, 0x3433, 0x352e, 0x3c12, 0x4b83]

def stores_extra(S):
    for k in [k for k in S.SLOTS if S.SLOTS[k][0] in (4, 5, 6)]: del S.SLOTS[k]
    S.FALL_SLOTS = {k: i for i, k in enumerate(['R7', 'L7', 'R8', 'L8'])}
    for k in (S.ARM, S.LGB, S.BOMB, S.JDAM, S.AIM54): S.SHAPES[k] = S.SHAPES[S.AAM]

if __name__ == '__main__':
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    make_pt(os.path.join(ROOT, 'PT', 'F22.PT'), os.path.join(out, 'F22.PT'))
    morph.apply(os.path.join(ROOT, 'SH', 'ATF.SH'), os.path.join(out, 'm1.SH'), warp, ABS_BUFS)

def build(out):
    import up_stores
    up_stores.run(os.path.join(out, 'm1.SH'), os.path.join(out, 'F22.PT'), os.path.join(out, 's1.SH'), stores_extra)
    import up_ab2
    up_ab2.run(os.path.join(out, 's1.SH'), os.path.join(ROOT, 'PIC', '_ATF.PIC'), os.path.join(out, 's2.SH'), os.path.join(out, 's2.PIC'),
               old=0x381d, length=66)            # nozzle exit ~ fwd -64, part starts at -48: ~50 visible (0.27 L)

GEAR = dict(
    # stock billboards: R 0x30ac (C4 (14,-10,-17) roll -gearPos/2), L 0x3117 (C4 (-11,-7,-22) roll gearPos/2),
    # nose 0x31df (C4 (0,-9,59) pitch).  Ground at world up -23.  F-22 tyres: main 37x11.5 in (r ~4.7 u), nose 23.5x7.5 (r ~3)
    parts={'R': 0x30ac, 'L': 0x3117, 'N': 0x31df},
    span_end={'R': 0x3111, 'L': 0x316e, 'N': 0x3236},
    gear={
        'R': dict(top=(-3, 16, 4), bot=(-3, 16, -9), wheel=(0, 16, -9), r=4, w=(-1, 1), braces=[((-3, 16, -3), (-3, 23, 4))]),
        'L': dict(top=(3, 21, 2), bot=(3, 21, -12), wheel=(0, 21, -12), r=4, w=(-1, 1), braces=[((3, 21, -6), (3, 28, 2))]),
        'N': dict(top=(2, 4, 0), bot=(2, 4, -11), wheel=(0, 4, -11), r=3, w=(-1, 1), braces=[((2, 4, -5), (1, -3, 0))]),
    },
    hub_main=(55, 22, 14), hub_nose=(140, 24, 8), clear=[(39, 2, 72, 43), (131, 6, 149, 43)], strip=None)   # old billboard art (only those parts use it)

def build_gear(out):
    import up_gear
    up_gear.run(os.path.join(out, 's2.SH'), os.path.join(out, 's2.PIC'), os.path.join(out, 's3.SH'), os.path.join(out, 's3.PIC'), GEAR)
