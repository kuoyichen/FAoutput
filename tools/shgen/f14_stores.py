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
import f18_stores as S
from f18g_growler import orient, FLAT, GREY

T, A9, A7, A54, NONE = S.TANK, S.AIM9, S.AIM7, S.AIM54, S.NONE
# (station, rank, default kind, attach x, up, fwd); every store ends 10 units behind its attach fwd.
# Pairs: left rank 1, right rank 2 (FA fires the right one first); belly: rear pair first-loaded, front pair last.
S.SLOTS = {
    'BRL': (4, 1, A7, (-6, -8, -20)), 'BRR': (4, 2, A7, (6, -8, -20)),
    'BFL': (4, 3, A7, (-6, -8, 16)),  'BFR': (4, 4, A7, (6, -8, 16)),
    'TL': (5, 1, T, (-13, -12, 7)),   'TR': (5, 2, T, (13, -12, 7)),
    'GL': (6, 1, A54, (-26, -7, 19)), 'GR': (7, 1, A54, (26, -7, 19)),
    'SL': (8, 1, A9, (-33, -3, 13)),  'SR': (8, 2, A9, (33, -3, 13)),
}

# curved glove pylon: cross-section from the glove (local 0, 0) down and inboard to the AIM-54 (-4, -10);
# each point carries its fore/aft extent (local fwd from, to).  Right side; the left one is mirrored.
GLOVE = [((0, 0), (-13, 14)), ((0, -4), (-12, 13)), ((-1, -7), (-11, 12)), ((-3, -9), (-10, 11)), ((-4, -10), (-9, 10))]


def glove_pylon(side):
    V, F = [], []
    for (dx, u), (f0, f1) in GLOVE: V += [(side * dx, f0, u), (side * dx, f1, u)]
    for k in range(len(GLOVE) - 1):
        q = [2*k, 2*k+1, 2*k+3, 2*k+2]
        F += [(FLAT, GREY, q), (FLAT, GREY, q[::-1])]          # thin plate, one face per side
    end = [2*k for k in range(len(GLOVE))]                       # front and rear edges closed by the two quads
    return V, F


S.PYLONS = {'pyGR': glove_pylon(1), 'pyGL': glove_pylon(-1), 'pyT': S.pylon(2, (5, -5), (6, -6))}


def f14_pylon_units():
    out = [('pyGR', 'pyGR', (30, 3, 20), -1), ('pyGL', 'pyGL', (-30, 3, 20), -1)]
    for s in ('TL', 'TR'):
        x, u, f = S.SLOTS[s][3]; ps = (x + (1 if x < 0 else 0), u, f + 13)   # slab is x -1..0: centre it
        out.append(('py' + s, 'pyT', ps, u + 1))
    return out


S.PYLON_UNITS = f14_pylon_units

if __name__ == '__main__':
    S.main()
