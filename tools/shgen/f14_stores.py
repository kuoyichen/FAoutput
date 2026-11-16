#!/usr/bin/env python3
"""Loadout stores for F14.SH (same machinery as f18_stores.py: runtime station read, FA weapon models,
stores inserted into the model's BSP).  F14.PT hardpoints:
  hp4  AIM-7  x4  belly tunnel (no pylons for now)      hp5  F250.GAS x2  under the intakes (short pylons)
  hp6  AIM-54 x1  left glove pylon (curved)             hp7  AIM-54 x1   right glove pylon
  hp8  AIM-9  x2  shoulder rails of the glove pylons
x / fwd from the PT, heights fitted to the model (glove underside up ~3, nacelle bottom ~-11, tunnel -7).
Usage: python3 f14_stores.py F14.SH out.SH [--static]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import math
import f18_stores as S
import fa_weapons
from f18g_growler import orient, lathe, FLAT, GREY

T, A9, A7, A54, NONE = S.TANK, S.AIM9, S.AIM7, S.AIM54, S.NONE
# Kuoyi's F14.PT (2026-11-16, second version) gives each weapon's centre (where FA launches it), x / up / fwd:
#   hp4 AIM-7 x4 (5, -6, 42)  hp5 tank x2 (16, -14, 19)  hp6 AIM-54 x2 (28, -7, 30)  hp7 AIM-9 x2 (30, -1, 30)
# The PT has one point for the four AIM-7s: that is the front pair (x +-4); the rear pair sits 40 behind it.
# Stores are FA's own models at their own size, centred on those points (as F18-11); attach = store top.
# Cross sections (fwd 25): tunnel roof up -6.7 for |x| < 7 (-6.3 at fwd 45, so the AIM-7s are half recessed),
# nacelles x 9..20 with bottom -9.5 (-10 at fwd 19), glove underside up 2..4 at x 20..34, main gear x 21..28, fwd 0..8.
PT = {4: (4, -7, 36), 5: (16, -14, 19), 6: (28, -7, 18), 7: (30, -1, 18)}   # AIM-54 / AIM-9 moved back 6 twice (Kuoyi)
TANK_R = 3.5                 # Kuoyi: use the F/A-18 tank (tank480, radius 3.5)
TANK_PITCH = 2               # Kuoyi: tank nose up 2 degrees (4 was too much) to follow the nacelle bottom (it rises toward the front)


def tank():
    """The F/A-18 tank480, nose up TANK_PITCH degrees about its centre: each ring is raised by fwd * tan(pitch)
    (a shear, so the rings stay planar on the integer grid)."""
    r = 3.5; e = r * .7; t = math.tan(math.radians(TANK_PITCH))
    sec = [(0, r), (e, e), (r, 0), (e, -e), (0, -r), (-e, -e), (-r, 0), (-e, e)]
    st = [(25, 0, -r), (21, .35, -r), (16, .65, -r), (11, .88, -r), (6, 1, -r), (-11, 1, -r), (-17, .75, -r),
          (-22, .45, -r), (-25, .3, -r)]
    V, F, _ = lathe(sec, [(f, k, dz + f * t) for f, k, dz in st], S.WHITE)
    return V, F


S.SHAPES[T] = tank


def aim7():
    """FA's SPAR model with X fins (two side by side fit in the tunnel) and its red bands painted blue."""
    V, F = S._W('SPAR.SH', 36, 45)()
    return V, [(fl, {161: 169, 162: 170}.get(col, col), q) for fl, col, q in F]   # band underside 162 (dark red) too


S.SHAPES[A7] = aim7
A54_LEN = round(.8 * 47) + 3   # Kuoyi: AIM-54 at 80% of FA's PHENX (47 long), then 3 longer


A54_FIN_ROLL = 45            # fins in X: clear of the pylon and the tunnel roof


def aim54():
    """AIM-54 built to the real round (Kuoyi 2026-11-16: separate long delta wings and small square tail fins).
    Real: length 4.0 m, diameter 0.38 m, span 0.9 m; nose 22 %, wings from 46 % to 80 % of the length (pure
    triangles), a gap, then small square tail fins on the last 14 %.  Here A54_LEN units long, octagonal body
    (flat to flat 4), pointed nose cone, blue band ahead of the wings, fins reaching 5 from the axis.
    Frame as fa_weapons.load: body top at up 0, LAST_TOP = height of the top above FA's origin."""
    import math
    tip, tail = 27, 27 - A54_LEN                                  # fwd of nose tip and tail end (centre ~ fwd 6)
    at = lambda frac: round(tip - frac * A54_LEN)                 # fwd at a fraction of the length from the nose
    SEC = [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)]   # octagon, top edge at up 2
    AX = -2                                                       # axis height: body top at up 0
    nose, band0, band1 = at(.24) - 1, at(.40), at(.44)          # nose cone starts 1 further back (Kuoyi)
    rings = [tail, band0, band1, nose]
    V, rid = [], []
    for f in rings:
        rid.append([])
        for x, u in SEC: V.append((x, f, u + AX)); rid[-1].append(len(V) - 1)
    V.append((0, tip, AX)); T = len(V) - 1
    light = (.45, .25, .85)
    def shade(q, band=False):
        P = [V[i] for i in q]; n = [0, 0, 0]
        for k in range(len(P)):
            a, b = P[k], P[(k + 1) % len(P)]
            n[0] += a[1]*b[2]-a[2]*b[1]; n[1] += a[2]*b[0]-a[0]*b[2]; n[2] += a[0]*b[1]-a[1]*b[0]
        c = [sum(p[j] for p in P) / len(P) for j in range(3)]
        if n[0] * c[0] + n[2] * (c[2] - AX) < 0: n = [-v for v in n]          # outward
        m = sum(v * v for v in n) ** .5 or 1
        d = (n[0] * light[0] + n[1] * light[1] + n[2] * light[2]) / m
        if band: return 169 if d > -.2 else 170
        return 144 + round(11 * (d + 1) / 2)
    F = []
    for k in range(len(rings) - 1):
        A, B = rid[k], rid[k + 1]
        for j in range(8):
            q = [A[j], A[(j + 1) % 8], B[(j + 1) % 8], B[j]]
            F.append((FLAT, shade(q, k == 1), q))
    for j in range(8):
        q = [rid[-1][j], rid[-1][(j + 1) % 8], T]
        F.append((FLAT, shade(q), q))
    F.append((FLAT, 143, list(rid[0])))                                       # tail cap
    G = orient(V, F, [0, (tail + tip) / 2, AX])
    # fins, outline (radial distance from the axis, fwd); root inside the body
    wing = [(1.4, at(.38)), (5.7, at(.80)), (1.4, at(.80))]                   # pure delta wing (Kuoyi): root LE moved forward 46->38 %, tip at the trailing edge
    tailfin = [(1.4, at(.86)), (5.7, at(.89)), (5.7, tail), (1.4, tail)]       # small square tail fin
    for k in range(4):
        a = math.radians(A54_FIN_ROLL + 90 * k); ca, sa = math.cos(a), math.sin(a)
        for outline, col in ((wing, 147), (tailfin, 146)):
            q = []
            for rr, f in outline:
                V.append((round(rr * ca), f, round(rr * sa) + AX)); q.append(len(V) - 1)
            G += [(FLAT, col, q), (FLAT, col, q[::-1])]                         # thin fin: one face per side
    fa_weapons.LAST_TOP = 1                         # body top 1 above FA's origin (the axis stays where it was)
    return V, G


S.SHAPES[A54] = aim54


def att(st, kind, side=1, dfwd=0):
    x, u, f = PT[st]
    top = TANK_R if kind == T else S.top_of(kind)
    return (side * x, round(u + top), f + dfwd)


# Tunnel roof (x < 7): up -7.0 from fwd -32 to 0, rising to -6.4 at fwd 36.  Kuoyi: AIM-7s back 6 and a bit inward;
# the rear pair was buried 2 units in the roof (top -5 at fwd 2), so it now hangs from the roof at fwd -4 (up -7).
A7REAR = -40                 # rear AIM-7 pair: one missile length (36) plus a gap behind the front pair
def a7(side, rear):
    x, u, f = att(4, A7, side, A7REAR if rear else 0)
    return (x, u - 1 if rear else u, f)
S.SLOTS = {
    'BRL': (4, 1, A7, a7(-1, 1)), 'BRR': (4, 2, A7, a7(1, 1)),
    'BFL': (4, 3, A7, a7(-1, 0)), 'BFR': (4, 4, A7, a7(1, 0)),
    'TL': (5, 1, T, att(5, T, -1)),            'TR': (5, 2, T, att(5, T, 1)),
    'GL': (6, 1, A54, att(6, A54, -1)), 'GR': (6, 2, A54, att(6, A54, 1)),   # PT x is +28 (Kuoyi): right fires first like the other pairs
    'SL': (7, 1, A9, att(7, A9, -1)),          'SR': (7, 2, A9, att(7, A9, 1)),
}
# The tunnel stations also take AIM-54s (Kuoyi): Phoenix (fins +-5, 41 long) on x +-5, same fwd as the AIM-7s,
# rear pair 3 further back (the pairs are 2 apart); top on the tunnel roof like the AIM-7s.
for s_, (st_, rk_, kd_, (x_, u_, f_)) in list(S.SLOTS.items()):
    if st_ == 4: S.KIND_POS[(s_, A54)] = ((5 if x_ > 0 else -5), u_, f_ - 3 if s_[1] == 'R' else f_)
GX = PT[6][0]
GLOVE_UNDER = 2.5            # glove underside at x 22..27


def tank267():
    """F-14 267-gal tank: fat (radius 4.5, about the intake width), blunt round nose, short tail cone."""
    r = 4.5
    sec = [(r * math.sin(a), r * math.cos(a)) for a in (2 * math.pi * k / 12 for k in range(12))]
    st = [(19, 0, -r), (18.3, .45, -r), (17, .7, -r), (15, .88, -r), (12, 1, -r), (-7, 1, -r), (-11, .85, -r),
          (-14.5, .62, -r), (-17.5, .38, -r), (-19, .2, -r)]         # centred on fwd 0 (the PT point)
    V, F, _ = lathe(sec, st, S.WHITE)
    return V, F




def solid(sections, col=GREY):
    """Closed plate along a polyline: sections [(x_out, u_out, x_in, u_in, fwd0, fwd1)] from top to bottom
    (x, u of the two faces of the plate, fore/aft extent).  Each segment between two sections is convex and
    oriented about its own centre, so the bent plate is closed and back-face culled."""
    V = []
    for xo, uo, xi, ui, f0, f1 in sections:
        V += [(xo, f0, uo), (xo, f1, uo), (xi, f0, ui), (xi, f1, ui)]
    F = []
    for k in range(len(sections) - 1):
        a, b = 4 * k, 4 * k + 4
        seg = [(FLAT, col, [a, a+1, b+1, b]), (FLAT, col, [a+2, a+3, b+3, b+2]),     # outer, inner side
               (FLAT, col, [a, a+2, b+2, b]), (FLAT, col, [a+1, a+3, b+3, b+1])]     # front, rear edge
        if k == 0: seg.append((FLAT, col, [a, a+1, a+3, a+2]))
        if k == len(sections) - 2: seg.append((FLAT, col, [b, b+1, b+3, b+2]))
        cen = [sum(V[i][j] for i in range(a, b + 4)) / 8 for j in range(3)]
        F += orient(V, seg, cen)
    return V, F


def glove_pylon(side):
    """Seen from the front the glove pylon leaves the glove, bends outboard and drops straight to the AIM-54;
    1 unit thick (Kuoyi: a third of the first one).  Local x 0 = AIM-54 centre line, up 0 = AIM-54 top; side +1 right, -1 left."""
    H = GLOVE_UNDER + 1 - S.SLOTS['GR'][3][1]                     # store top up into the glove
    cl = [(-4, H, -14, 4), (-3, .7 * H, -13, 6), (-1.3, .45 * H, -12, 8), (0, .24 * H, -11, 10), (0, 0, -10, 12)]   # leading edge raked: bottom forward, top back (Kuoyi)
    secs = []
    for i, (x, u, f0, f1) in enumerate(cl):
        a, b = cl[max(i - 1, 0)], cl[min(i + 1, len(cl) - 1)]
        tx, tu = b[0] - a[0], b[1] - a[1]; L = math.hypot(tx, tu); nx, nu = -tu / L, tx / L   # normal, outboard side
        if nx < 0: nx, nu = -nx, -nu
        secs.append((side * round(x + nx), round(u + nu), side * round(x), round(u), f0, f1))   # 1 unit thick
    V, F = solid(secs)
    return V, F


def small_pylon(h, f0, f1, half=1):
    """Short tank pylon: 2 units thick, from the tank top (up 0) up into the nacelle (up h), swept front edge."""
    return solid([(half, h, -half, h, f0 - 1, f1), (half, 0, -half, 0, f0 + 1, f1 - 1)])


S.PYLONS = {'pyGR': glove_pylon(1), 'pyGL': glove_pylon(-1)}    # tanks hang close under the nacelles: no pylon


def f14_pylon_units():
    out = []
    for s, part in (('GR', 'pyGR'), ('GL', 'pyGL')):
        x, u, f = S.SLOTS[s][3]
        out.append(("py" + s, part, (x, u, 18), u + 9))     # pylon fwd 4..30 (Kuoyi asked to move back; may touch the main gear)
    return out


S.PYLON_UNITS = f14_pylon_units


def placer(c, ROOT, ugeo, ubox):
    import sh_order
    big = sorted(ugeo, key=lambda u: -(ubox[u][1][0] - ubox[u][0][0]) * (ubox[u][1][1] - ubox[u][0][1]) * (ubox[u][1][2] - ubox[u][0][2]))
    pyl = [u for u in big if u.startswith('py')]; rest = [u for u in big if not u.startswith('py')]
    plan, refs, *_ = sh_order.place(c, ROOT, ugeo, ubox, pyl + rest)
    return plan, refs


S.PLACER = placer
S.FALL_SLOTS = {'TL': 0, 'TR': 1}   # Kuoyi: jettisoned tanks fall away (drawn for 2 s, down and back)

if __name__ == '__main__':
    S.main()
