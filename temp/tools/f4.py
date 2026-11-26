#!/usr/bin/env python3
"""F-4 Phantom II family upgrade (mass-upgrade thread, 2026-11-26).
The five stock F-4 SHs are one geometry with five textures (F4B F4D F4G F4J F4X differ only in the PIC name).
Steps per SH: wing span to the real 38 ft 5 in (|x| > 13 scaled 0.892, stock 42 ft; BSP planes + gear C4s follow)
-> PT: every F-4 PT gets the real 9-station layout (centreline, 4 Sparrow wells in two pairs, inboard pylons
with AIM-9 rails, inboard pylon stores, outboard tanks), keeping each PT's own default stores
-> stores -> animated afterburner on both engines (+ LOD1) -> 3D gear: single main wheels inboard of the wing legs,
twin nose wheels.
Usage: f4.py OUTDIR [F4G ...]"""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
from pt_edit import set_station
import morph

SHS = {'F4G': ['F4', 'F4E'], 'F4J': ['F4B', 'F4F', 'F4J', 'F4M'], 'F4D': ['F4EE'], 'F4B': ['F4EV'], 'F4X': ['F4X']}
ABS = [0x80, 0x5801, 0x5964, 0x5b64]          # absolute vertex buffers (LOD0, LOD1 gear, LOD1 flame, LOD1)
LODS = [0x80, 0x5b64]
K = 0.892                                       # (57.6 - 13) / (63 - 13): real half span 19.2 ft = 57.6 u

def warp(v):
    x, f, u = v
    if abs(x) > 13 and f > -55:                 # wing only (the stabilator, fwd < -60, is already right)
        x = (13 + (abs(x) - 13) * K) * (1 if x > 0 else -1)
    return (x, f, u)

WX = lambda x: round(warp((x, 0, 0))[0])
# per PT: default stores for (centreline, Sparrow wells, AIM-9 rails, inboard pylon, outboard pylon); None = empty
DEFAULTS = {
    'F4':   ('F500.GAS', 'AIM7.JT', None, 'AGM88.JT', 'F350.GAS'),       # F-4G Wild Weasel: HARM inboard
    'F4E':  None, 'F4EE': None, 'F4EV': None, 'F4F': None,              # already this layout: keep
    'F4B':  ('F500.GAS', 'AIM7E.JT', 'AIM9B.JT', 'LAU61.JT', 'F350.GAS'),
    'F4J':  (None, 'AIM7E.JT', 'AIM9B.JT', None, 'F350.GAS'),
    'F4M':  (None, 'AIM7.JT', 'AIM9D.JT', None, 'F350.GAS'),
    'F4X':  (None, 'AIM7.JT', 'AIM9D.JT', None, 'F350.GAS'),
}


def make_pt(name, dst):
    t = open(os.path.join(ROOT, 'PT', name + '.PT'), encoding='latin1', newline='').read()
    import re
    cur = lambda i: (lambda m: m.group(1) if m else None)(re.search(r':defaultTypeName%d\r?\n\s*string "([^"]*)"' % i, t))
    dfl = DEFAULTS[name] or (cur(4), cur(5), cur(6), cur(7), cur(8))
    # SH units; belly -9, wing underside -8; real stations: Sparrow wells semi-recessed under the fuselage corners
    rows = [(4, 0x1701, 0, -20, 0, dfl[0], 43, 1, 0),             # centreline 600-gal
            (5, 0x445, 13, -15, 18, dfl[1], 21, 4, 1),            # Sparrow wells: front pair (rear pair 48 behind)
            (6, 0x85, WX(26), -19, -9, dfl[2], 11, 4, 4),         # LAU-7 rails on the inboard pylons
            (7, 0x15a5, WX(26), -20, -9, dfl[3], 60, 2, 4),       # inboard pylon store
            (8, 0x1705, WX(38), -19, -20, dfl[4], 69, 2, 4)]      # outboard pylon 370-gal tank
    for r in rows: t = set_station(t, *r)
    open(dst, 'w', encoding='latin1', newline='').write(t)


def stores_extra(S):
    import f18v_upgrade as U
    for k in (S.AIM54, S.AAM, S.JDAM): S.SHAPES[k] = S.SHAPES[S.AIM7]     # no AIM-120 / AIM-54 / JDAM on a Phantom
    st, rank, kd, (x, u, f) = S.SLOTS['R5']
    S.SLOTS['R5b'] = (st, 4, kd, (x, u, f - 48)); S.SLOTS['L5b'] = (st, 3, kd, (-x, u, f - 48))
    fus = {'R5', 'L5', 'R5b', 'L5b'}
    S.PLACER = lambda c, ROOT_, ugeo, ubox: U.placer(c, ROOT_, ugeo, ubox, fus)
    S.FALL_SLOTS = {'C4': 0, 'R8': 1, 'L8': 2}


PARTS = {'R': 0x3cb5, 'L': 0x3de1, 'N': 0x3f78}

def gear_spec(sh_path, pic_path):
    import up_gear as U
    g = {'R': dict(top=(1, 1, 0), bot=(1, 1, -8), wheel=(-1, 1, -8), r=4, w=(-1, 1), braces=[((1, 1, -4), (1, -6, 0))]),
         'L': dict(top=(-1, 1, 0), bot=(-1, 1, -8), wheel=(1, 1, -8), r=4, w=(-1, 1), braces=[((-1, 1, -4), (-1, -6, 0))]),
         'N': dict(top=(0, 0, 0), bot=(0, 0, -10), wheel=(0, 0, -10), r=2, w=(-1, 1), twin=3, sr=0.8,
                   braces=[((0, 0, -5), (0, -6, 0))])}
    spec = dict(parts=PARTS, gear=g, strip=None)
    spec.update(U.auto_hubs(sh_path, pic_path, PARTS, rm=12, rn=8)); spec['clear'] = []
    return spec


def build(sh, out):
    os.makedirs(out, exist_ok=True)
    import up_stores, up_gear, up_ab2, f16
    from f14_gear import read_pic, put
    for p in SHS[sh]: make_pt(p, os.path.join(out, p + '.PT'))
    tpl = os.path.join(out, 'layout.PT'); make_pt('F4E', tpl)
    src = os.path.join(ROOT, 'SH', sh + '.SH'); m0 = os.path.join(out, 'm0.SH'); m1 = os.path.join(out, 'm1.SH')
    morph.apply(src, m0, warp, ABS)
    morph.remap(src, m0, warp, LODS)
    up_stores.run(m0, tpl, m1, stores_extra)
    pic = os.path.join(ROOT, 'PIC', '_' + sh + '.PIC')
    pre = up_gear.auto_hubs(m1, pic, PARTS, rm=12, rn=8)['clear']
    pb = bytearray(open(pic, 'rb').read()); P = read_pic(pb)
    for a in pre:
        for y in range(a[1], a[3] + 1):
            for x in range(a[0], a[2] + 1): put(pb, P, x, y, 255)
    cur_sh, cur_pic = m1, os.path.join(out, 'm1.PIC'); open(cur_pic, 'wb').write(pb)
    slots = None
    _, _, _, _, c = __import__('sh_inspect').load(m1)
    tex = lambda t: struct.unpack_from('<H', c, t + 6 + 6 * struct.unpack_from('<H', c, t + 2)[0] + 1)[0] & 4
    for k, old in enumerate([t for t in f16.flame_parts(m1) if tex(t)]):        # LOD1 flame is flat colour: left
        nsh, npic = os.path.join(out, 'f%d.SH' % k), os.path.join(out, 'f%d.PIC' % k)
        slots = up_ab2.run(cur_sh, cur_pic, nsh, npic, old=old, length=60, ignore=pre, slots=slots)
        cur_sh, cur_pic = nsh, npic
    up_gear.run(cur_sh, cur_pic, os.path.join(out, 's3.SH'), os.path.join(out, 's3.PIC'), gear_spec(cur_sh, cur_pic))


if __name__ == '__main__':
    for sh in (sys.argv[2:] or list(SHS)): build(sh, os.path.join(sys.argv[1], sh))
