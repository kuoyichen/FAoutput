#!/usr/bin/env python3
"""F-35A / B / C from the F-22 shape (ATF.SH), mass-upgrade thread 2026-11-26.
The stock F35A.SH is Kuoyi's edit of the Yak-141 (twin tail booms, no afterburner); the F-35 is a single-engine
cousin of the F-22 (same design language: caret-type intakes beside the canopy, diamond wing, canted fins,
all-moving stabilators reaching past the nozzle, internal bays), so ATF.SH is warped to F-35 proportions.
Scale kept at the F-22's 3.04 u/ft.  F-35A: length 51.4 ft (156 u), span 35 ft (106 u), wing 460 ft^2,
LE sweep 34 deg, taper ~0.25 (tip chord 16 u), single round nozzle ~4 ft; fins canted 20 deg.
F-35C: span 43 ft (131 u), wing 668 ft^2, bigger stabilators, folding outer wing.
Body map (ATF fwd -> F-35 fwd): nose 117 -> 84, windscreen 80 -> 64, intake lip 62 -> 42, wing LE root 33 -> 18,
wing TE root -38 -> -29, nozzle exit -47 -> -64; aft body narrows to the single nozzle (x * 0.42), nozzle 1.8x taller."""
import math, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
import numpy as np
import morph, nodes as NODES
from sh_inspect import load

BODY_F = [(-200, -205), (-72, -75), (-56, -70), (-47, -64), (-38, -29), (33, 18), (62, 42), (80, 64), (117, 84), (300, 267)]
lerp = lambda pts, v: float(np.interp(v, [a for a, b in pts], [b for a, b in pts]))

class Shape:
    def __init__(s, var='A'):
        s.var = var
        if var == 'C':      # span 131: tip x 65.5; bigger chord (area 668 ft^2), tip chord ~ 20 u
            s.wing = dict(x0=19, x1=65.5, le0=22, le1=-9, te0=-31, te1=-29 + 0)
            s.stab = dict(x0=14, x1=36, le0=-44, le1=-58, te0=-72, te1=-66)
        else:
            s.wing = dict(x0=19, x1=53, le0=18, le1=-5, te0=-28.6, te1=-21)
            s.stab = dict(x0=14, x1=31, le0=-45, le1=-56.5, te0=-72, te1=-65)

    def warp(s, v):
        x, f, u = v; ax = abs(x); sg = 1 if x >= 0 else -1
        # fins (ATF: root u~4-9 x 13-17, tip u 36 x 27-29; LE -11 -> -24, TE -50 -> -37)
        if 12 <= ax <= 30 and (u > 4.5 or (u >= 4 and ax <= 17)) and -52 < f < -5:
            h = min(1.0, max(0.0, (u - 4) / 32)); le, te = -11 - 13 * h, -50 + 13 * h
            c = (f - te) / (le - te)
            nle, nte = -30 - 14 * h, -55 + 1 * h
            return (sg * (11 + 6.5 * h), nte + c * (nle - nte), 7 + 18 * h)
        if ax >= 17 and -6 <= u <= 4 and f < -40:                      # stabilators
            W = s.stab; t = min(1.2, max(0.0, (ax - 19) / 28)); le, te = -38 - 19 * t, -72 + 9 * t
            c = (f - te) / (le - te)
            nle, nte = W['le0'] + (W['le1'] - W['le0']) * t, W['te0'] + (W['te1'] - W['te0']) * t
            return (sg * (W['x0'] + (W['x1'] - W['x0']) * t), nte + c * (nle - nte), u)
        if ax > 18 and -6 <= u <= 4 and f >= -42:                       # wing
            W = s.wing; t = (ax - 18) / 45.5; le, te = 33 - 45 * t, -38 + 11 * t
            c = (f - te) / (le - te)
            nle, nte = W['le0'] + (W['le1'] - W['le0']) * t, W['te0'] + (W['te1'] - W['te0']) * t
            return (sg * (W['x0'] + (W['x1'] - W['x0']) * t), nte + c * (nle - nte), u)
        # body
        nf = lerp(BODY_F, f)
        k = 1.0 if f >= -38 else (0.42 if f <= -47 else 1 - 0.58 * (-38 - f) / 9)
        nu = u * 1.15
        if ax <= 16 and u > 1.5 and -47 < f < 50:                       # deep F-35 dorsal: stays high to the tail
            kk = (f + 47) / 15 if f < -32 else (1.0 if f < 27 else (50 - f) / 23)
            nu += 6 * kk * min(1.0, (u - 1.5) / 3)
        if f <= -45 and ax < 16: nu = u * 1.8
        return (x * k, nf, nu)

def remap_nodes(path_in, path_out, shp, starts):
    vs = [{}, {'_PLafterBurner': 1, '_PLbayOpen': 1, '_PLbayDoorPos': 100, '_PLgearDown': 0, '_PLleftFlap': 30, '_PLrightFlap': 30, '_PLbrake': 1}]
    N, C4 = NODES.collect_all(path_in, starts, vs)
    d, pe, secs, code, c = load(path_out); d = bytearray(d); ro = code['ro']
    h = lambda p: struct.unpack_from('<h', c, p)[0]
    cl = lambda v: max(-32768, min(32767, int(round(v))))
    for p, op in N.items():
        if op == 6:
            dx, du, df = h(p + 4), h(p + 8), h(p + 12)
            x, f, u = shp.warp((-dx, -df, -du))
            for off, val in ((4, -x), (8, -u), (12, -f)): struct.pack_into('<h', d, ro + p + off, cl(val))
        elif op == 0x0C:   # up, fwd
            x, f, u = shp.warp((0, -h(p + 8), -h(p + 4)))
            struct.pack_into('<h', d, ro + p + 4, cl(-u)); struct.pack_into('<h', d, ro + p + 8, cl(-f))
        elif op == 0x0E:   # x, fwd
            x, f, u = shp.warp((-h(p + 4), -h(p + 8), 0))
            struct.pack_into('<h', d, ro + p + 4, cl(-x)); struct.pack_into('<h', d, ro + p + 8, cl(-f))
        elif op == 0x10:   # x, up
            x, f, u = shp.warp((-h(p + 4), 0, -h(p + 8)))
            struct.pack_into('<h', d, ro + p + 4, cl(-x)); struct.pack_into('<h', d, ro + p + 8, cl(-u))
    for p in C4:
        X, U, F = struct.unpack_from('<3h', c, p + 2)
        x, f, u = shp.warp((X, F, U)) if not (abs(X) > 18 and -6 <= U <= 4) else (X, lerp(BODY_F, F), U)
        struct.pack_into('<3h', d, ro + p + 2, cl(x), cl(u), cl(f))
    open(path_out, 'wb').write(d)
    return N, C4

ABS = [0x80, 0x323c, 0x3337, 0x3433, 0x352e, 0x3c12, 0x4b83]

def base(var, out):
    os.makedirs(out, exist_ok=True)
    shp = Shape(var)
    src = os.path.join(ROOT, 'SH', 'ATF.SH'); dst = os.path.join(out, 'm1.SH')
    morph.apply(src, dst, shp.warp, ABS)
    N, C4 = remap_nodes(src, dst, shp, ABS[:1] + ABS[5:])
    print(f'{len(N)} plane nodes, {len(C4)} C4 parts moved')
    return dst



# ---------------------------------------------------------------- variants
from pt_edit import set_hp, set_field
import shutil

VAR = {   # PT files: ASTOVL / ASTOVLV = F-35A, ASTOVLF = F-35B, F22N = F-35C
    'A': dict(pts=['ASTOVL', 'ASTOVLV'], sh='F35A', thrust=(28000, 43000), st=((6, 22), (7, 32), (8, 44))),
    'B': dict(pts=['ASTOVLF'], sh='F35B', thrust=(27000, 41000), st=((6, 22), (7, 32), (8, 44))),
    'C': dict(pts=['F22N'], sh='F35C', thrust=(28000, 43000), st=((6, 26), (7, 38), (8, 52))),
}

def part_edit(path, offs, fn):
    d, pe, secs, code, c = load(path); d = bytearray(d)
    for o in offs:
        n = struct.unpack_from('<H', c, o + 2)[0]
        for i in range(n):
            p = code['ro'] + o + 6 + 6 * i; v = struct.unpack_from('<3h', d, p)
            struct.pack_into('<3h', d, p, *[int(round(a)) for a in fn(v)])
    open(path, 'wb').write(d)

def set_tex(path, name):
    d = bytearray(open(path, 'rb').read()); i = d.find(b'\xe2\x00_ATF.PIC')
    assert i > 0; nm = name.encode() + b'\0' * (14 - len(name)); d[i + 2:i + 16] = nm; open(path, 'wb').write(d)

def make_pts(var, out):
    V = VAR[var]
    for p in V['pts']:
        t = open(os.path.join(ROOT, 'PT', p + '.PT'), encoding='latin1', newline='').read()
        from pt_edit import get_hp
        for i, x in V['st']:
            if int(get_hp(t, i)['x']) != 0: t = set_hp(t, i, x=x)
        t = set_field(t, 'PLANE', 73, V['thrust'][0]); t = set_field(t, 'PLANE', 74, V['thrust'][1])
        t = t.replace('string "f35a.SH"', f'string "{V["sh"].lower()}.SH"')
        open(os.path.join(out, p + '.PT'), 'w', encoding='latin1', newline='').write(t)

def gear_spec(var):
    g = dict(
        parts={'R': 0x30ac, 'L': 0x3117, 'N': 0x31df}, span_end={'R': 0x3111, 'L': 0x316e, 'N': 0x3236},
        gear={
            'R': dict(top=(-3, 16, 4), bot=(-3, 16, -7), wheel=(0, 16, -7), r=4, w=(-1, 1), braces=[((-3, 16, -3), (-3, 23, 4))]),
            'L': dict(top=(3, 21, 2), bot=(3, 21, -11), wheel=(0, 21, -11), r=4, w=(-1, 1), braces=[((3, 21, -6), (3, 28, 2))]),
            'N': dict(top=(2, 4, 0), bot=(2, 4, -11), wheel=(0, 4, -11), r=3, w=(-1, 1), braces=[((2, 4, -5), (1, -3, 0))]),
        },
        hub_main=(55, 22, 14), hub_nose=(140, 24, 8), clear=[(39, 2, 72, 43), (131, 6, 149, 43)], strip=None)
    if var == 'C':     # carrier: twin nose wheels with the strut between, launch-bar brace forward
        g['gear']['N'] = dict(top=(0, 4, 0), bot=(0, 4, -11), wheel=(0, 4, -11), r=3, w=(-1, 0), twin=2,
                              braces=[((0, 4, -9), (0, 12, -4))])
    return g

def door_extra(S, top_u, hinge_f, length=17, half=6):
    """F-35B lift-fan door (hinged at its aft edge, drawn over a black fan opening) as two fixed units."""
    from fs_core import orient, FLAT
    Vd = [(-half, 0, 0), (half, 0, 0), (half, length, 0), (-half, length, 0)]
    Fd = [(0x661, 154, [0, 1, 2, 3]), (0x661, 152, [3, 2, 1, 0])]
    Vh = [(-half + 1, 1, 0), (half - 1, 1, 0), (half - 1, length - 1, 0), (-half + 1, length - 1, 0)]
    Fh = [(0x641, 160, [0, 1, 2, 3])]
    S.PYLONS['door'] = (Vd, Fd); S.PYLONS['hole'] = (Vh, Fh)
    old = S.PYLON_UNITS
    S.PYLON_UNITS = lambda: old() + [('pyHOLE', 'hole', (0, top_u, hinge_f), top_u + 1), ('pyDOOR', 'door', (0, top_u + 1, hinge_f), top_u + 12)]

def prism(stations, sec, col):
    """Fairing along fwd: stations [(fwd, base up, scale)], section [(x, up above base)] (scale 0 = tip)."""
    from fs_core import orient, FLAT
    V, R = [], []
    for f, b, k in stations:
        if k == 0: V.append((0, round(f), round(b))); R.append([len(V) - 1] * len(sec)); continue
        R.append([]);
        for x, z in sec: V.append((round(x * k), round(f), round(b + z * k))); R[-1].append(len(V) - 1)
    F = []
    for A, B in zip(R, R[1:]):
        for j in range(len(sec)):
            q = [A[j], A[(j + 1) % len(sec)], B[(j + 1) % len(sec)], B[j]]
            q = [v for i, v in enumerate(q) if v != q[i - 1]]
            if len(q) >= 3: F.append((FLAT, col, q))
    for (f, b, k), r in ((stations[0], R[0]), (stations[-1], R[-1])):
        if k: F.append((FLAT, 160 if f == stations[0][0] else col, list(r)))
    return V, orient(V, F)


def gun_extra(S):
    """F-35A GAU-22/A: fairing on the left shoulder behind the canopy, muzzle (black) at its front end."""
    sec = [(-2.5, -1.5), (-2.5, 1.5), (-1.2, 3), (1.2, 3), (2.5, 1.5), (2.5, -1.5)]     # base on the skin
    st = [(34, 6, .8), (31, 7, 1), (24, 8, 1), (16, 9, 1), (8, 10, .9), (2, 11, .6), (-6, 11, 0)]
    S.PYLONS['gun'] = prism(st, sec, 154)
    old = S.PYLON_UNITS
    S.PYLON_UNITS = lambda: old() + [('pyGUN', 'gun', (-9, 0, 0), 14)]


def hook_extra(S):
    """F-35C tail hook: stowed shaft in a belly fairing aft of the bays, black hook point at its end."""
    sec = [(-1.5, 1), (-1.5, -1.5), (-1, -3), (1, -3), (1.5, -1.5), (1.5, 1)]
    st = [(-30, -7, 0), (-34, -7, 1), (-46, -6, 1), (-58, -5, 1), (-61, -5, .8)]
    Vh, Fh = prism(st, sec, 152)
    n = len(Vh); Vh = Vh + [(-1, -61, -7), (1, -61, -7), (1, -64, -10), (-1, -64, -10)]
    from fs_core import FLAT
    Fh = Fh + [(FLAT, 160, [n, n + 1, n + 2, n + 3]), (FLAT, 160, [n + 3, n + 2, n + 1, n])]
    S.PYLONS['hook'] = (Vh, Fh)
    old = S.PYLON_UNITS
    S.PYLON_UNITS = lambda: old() + [('pyHOOK', 'hook', (0, 0, 0), -4)]


def stores_extra_for(var, top=None):
    def ex(S):
        for k in [k for k in S.SLOTS if S.SLOTS[k][0] in (4, 5)]: del S.SLOTS[k]
        S.FALL_SLOTS = {k: i for i, k in enumerate([k for k in ('R6', 'L6', 'R7', 'L7') if k in S.SLOTS])}
        for k in (S.AIM54,): S.SHAPES[k] = S.SHAPES[S.AAM]
        if var == 'B': door_extra(S, *top)
        if var == 'A': gun_extra(S)
        if var == 'C': hook_extra(S)
    return ex

def top_at(path, f0, f1):
    d, pe, secs, code, c = load(path)
    n = struct.unpack_from('<H', c, 0x80 + 2)[0]
    V = [struct.unpack_from('<3h', c, 0x80 + 6 + 6 * i) for i in range(n)]
    return max(v[2] for v in V if abs(v[0]) <= 4 and f0 <= v[1] <= f1)

def build(var, out):
    os.makedirs(out, exist_ok=True)
    m1 = base(var, out)
    part_edit(m1, [0x373e, 0x37ad], lambda v: (v[0] * 0.42, v[1], v[2]))     # 2D nozzle flaps -> one nozzle
    # the two flat F-22 plumes become one cross-shaped round-engine plume: right one horizontal x -5..5,
    # left one turned vertical (up -5..5); same faces, same textures
    part_edit(m1, [0x381d], lambda v: (((v[0] - 6.5) * 0.85), v[1], v[2]) if v[0] > 0 else (v[2], v[1], (-v[0] - 7) * 0.85))
    make_pts(var, out)
    import up_stores, up_ab2, up_gear
    top = None
    if var == 'B':
        tu = top_at(m1, 10, 28); top = (tu, 10); print('lift-fan door top', tu)
    up_stores.run(m1, os.path.join(out, VAR[var]['pts'][0] + '.PT'), os.path.join(out, 's1.SH'), stores_extra_for(var, top))
    up_ab2.run(os.path.join(out, 's1.SH'), os.path.join(ROOT, 'PIC', '_ATF.PIC'), os.path.join(out, 's2.SH'), os.path.join(out, 's2.PIC'),
               old=0x381d, length=52)
    up_gear.run(os.path.join(out, 's2.SH'), os.path.join(out, 's2.PIC'), os.path.join(out, 's3.SH'), os.path.join(out, 's3.PIC'), gear_spec(var))
    sh = VAR[var]['sh']
    set_tex(os.path.join(out, 's3.SH'), f'_{sh}.PIC')
    shutil.copy(os.path.join(out, 's3.SH'), os.path.join(out, sh + '.SH')); shutil.copy(os.path.join(out, 's3.PIC'), os.path.join(out, f'_{sh}.PIC'))


if __name__ == '__main__':
    for v in (sys.argv[1:] or ['A', 'B', 'C']): build(v, f'../work/f35{v.lower()}')
