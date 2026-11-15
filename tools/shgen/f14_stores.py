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
# The PT has one point for the four AIM-7s: that is the front pair (x +-4); the rear pair sits right behind it.
# Stores are FA's own models at their own size, centred on those points (as F18-11); attach = store top.
# Cross sections (fwd 25): tunnel roof up -6.7 for |x| < 7 (-6.3 at fwd 45, so the AIM-7s are half recessed),
# nacelles x 9..20 with bottom -9.5 (-10 at fwd 19), glove underside up 2..4 at x 20..34, main gear x 21..28, fwd 0..8.
PT = {4: (5, -6, 42), 5: (16, -14, 19), 6: (28, -7, 24), 7: (30, -1, 24)}   # AIM-54 / AIM-9 moved back 6 (Kuoyi)
TANK_R = 3.5                 # Kuoyi: use the F/A-18 tank (tank480, radius 3.5)


def aim7():
    """FA's SPAR model with X fins (two side by side fit in the tunnel) and its red bands painted blue."""
    V, F = S._W('SPAR.SH', 36, 45)()
    return V, [(fl, 169 if col == 161 else col, q) for fl, col, q in F]


S.SHAPES[A7] = aim7


def att(st, kind, side=1, dfwd=0):
    x, u, f = PT[st]
    top = TANK_R if kind == T else S.top_of(kind)
    return (side * x, round(u + top), f + dfwd)


A7REAR = -40                 # rear AIM-7 pair: one missile length (36) plus a gap behind the front pair
S.SLOTS = {
    'BRL': (4, 1, A7, att(4, A7, -1, A7REAR)), 'BRR': (4, 2, A7, att(4, A7, 1, A7REAR)),
    'BFL': (4, 3, A7, att(4, A7, -1)),         'BFR': (4, 4, A7, att(4, A7, 1)),
    'TL': (5, 1, T, att(5, T, -1)),            'TR': (5, 2, T, att(5, T, 1)),
    'GL': (6, 2, A54, att(6, A54, -1)),        'GR': (6, 1, A54, att(6, A54, 1)),   # PT x is -28: FA fires the left one first (Kuoyi saw it)
    'SL': (7, 1, A9, att(7, A9, -1)),          'SR': (7, 2, A9, att(7, A9, 1)),
}
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
        out.append(("py" + s, part, (x, u, 24), u + 9))     # pylon fwd 10..36: under the glove, clear of the gear
    return out


S.PYLON_UNITS = f14_pylon_units


def placer(c, ROOT, ugeo, ubox):
    import sh_order
    big = sorted(ugeo, key=lambda u: -(ubox[u][1][0] - ubox[u][0][0]) * (ubox[u][1][1] - ubox[u][0][1]) * (ubox[u][1][2] - ubox[u][0][2]))
    pyl = [u for u in big if u.startswith('py')]; rest = [u for u in big if not u.startswith('py')]
    plan, refs, *_ = sh_order.place(c, ROOT, ugeo, ubox, pyl + rest)
    return plan, refs


S.PLACER = placer

if __name__ == '__main__':
    S.main()
