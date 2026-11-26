#!/usr/bin/env python3
"""F-117A Nighthawk upgrade (mass-upgrade thread, 2026-11-26).  Stock F117.SH is 63 ft long (real 65.9 ft) but
56.7 ft across the tips (real 43.3 ft): the whole shape is narrowed x 0.73 (planform, V-tails, bay doors, gear and
BSP planes follow), which also brings the leading-edge sweep from 63 to the real 67.5 deg.  No external stores (the
two GBU-27s ride in the internal bays, the stock doors already animate), no afterburner (F404 without AB)
-> 3D gear: single main wheels outboard of the legs, single nose wheel.
Usage: f117.py OUTDIR"""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
import morph

KX = 0.73
ABS = [0x81, 0x28cb, 0x398e]
warp = lambda v: (v[0] * KX, v[1], v[2])
PARTS = {'R': 0x2238, 'L': 0x238a, 'N': 0x27b2}


def gear_spec(sh, pic):
    import up_gear as U
    g = {'R': dict(top=(0, 0, 0), bot=(0, 0, -13), wheel=(2, 0, -13), r=4, w=(-1, 1), sr=0.8, braces=[((0, 0, -7), (0, 6, 0))]),
         'L': dict(top=(0, 0, 0), bot=(0, 0, -13), wheel=(-2, 0, -13), r=4, w=(-1, 1), sr=0.8, braces=[((0, 0, -7), (0, 6, 0))]),
         'N': dict(top=(0, 0, 0), bot=(0, 0, -14), wheel=(0, 0, -14), r=3, w=(-1, 1), sr=0.8, braces=[((0, 0, -7), (0, -6, 0))])}
    spec = dict(parts=PARTS, gear=g, strip=None)
    spec.update(U.auto_hubs(sh, pic, PARTS, rm=12, rn=8))
    return spec


def build(out):
    os.makedirs(out, exist_ok=True)
    import up_gear
    src = os.path.join(ROOT, 'SH', 'F117.SH'); m0 = os.path.join(out, 'm0.SH')
    morph.apply(src, m0, warp, ABS)
    morph.remap(src, m0, warp, ABS, [{}, {'_PLgearDown': 0, '_PLbayOpen': 1, '_PLbayDoorPos': 30}])
    pic = os.path.join(ROOT, 'PIC', '_F117.PIC')
    up_gear.run(m0, pic, os.path.join(out, 'F117.SH'), os.path.join(out, '_F117.PIC'), gear_spec(m0, pic))


if __name__ == '__main__':
    build(sys.argv[1])
