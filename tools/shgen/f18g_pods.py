#!/usr/bin/env python3
"""EA-18G (F18G) fixed stores on top of the f18v_upgrade build (Kuoyi 2026-11-22):
  * ALQ-99 jammer pods on the middle wing stations (x ±34) and the centreline, each with a small ram-air turbine
    propeller on its nose that turns while the jet moves (f18_stores.SPIN: an F0 stub sets the prop C4 roll)
  * 480-gal tanks on the inboard wing stations (x ±22)
  All five are fixed structure (not PT hardpoints: nothing to drop or fire), on pylons of the current shape
  (f18_stores.pylon, fitted into the wing / belly like the PT stations); no jettison animation (FALL_SLOTS = {}).
  The PT keeps only the weapons: fuselage AIM-120 pair and outer-wing AGM-88 pair (tools/shgen/f18g_pt.py).
Usage: python3 f18g_pods.py base.SH in.PIC F18G.PT out.SH out.PIC [folded_preview.SH]
  base.SH = stock F18F.SH with its six _f18f.PIC names changed to _f18g.PIC (stock F18G is the same file).
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import f18v_upgrade as U
import f18_stores as S
from f18g_growler import lathe, FIN, DARK, GREY

# store centres (x, up, fwd): F18F.PT stations (hp5 tank x 22, hp7 x 34, hp9 centre) + PT_DROP, as the PT stores are drawn
TANK_C = (22, -7, 6)
POD_W = (34, -6, 3)
POD_C = (0, -10, -4)
PROP_FWD = 22                     # prop disc, ahead of the pod centre
PROP_UP = 0


def pod():
    """ALQ-99: rounded box section 6 wide x 7 deep (deeper below the axis), rounded tail, nose necking into a spinner."""
    sec = [(-2, 3), (2, 3), (3, 2), (3, -2), (2, -4), (-2, -4), (-3, -2), (-3, 2)]
    V, F, _ = lathe(sec, [(-23, .5, 0), (-21, .85, 0), (-18, 1, 0), (15, 1, 0), (18, .8, 0), (21, .4, 0), (25, 0, 0)])
    return V, F


def prop():
    """Two twisted blades (radius 1..4, chord 2), both sides drawn; turns about the fwd axis (C4 roll)."""
    V, F = [], []
    for s in (1, -1):
        b = len(V)
        V += [(-s, 1, s), (s, 0, s), (s, 0, 4 * s), (-s, 1, 4 * s)]
        q = [b, b + 1, b + 2, b + 3]
        F += [(FIN, DARK, q), (FIN, DARK, q[::-1])]
    return V, F


def shift(VF, df):
    V, F = VF
    return [(x, f + df, u) for x, f, u in V], F


def pylon_for(P, x, f, top):
    """Current pylon shape (as f18v_upgrade.configure): from the store top `top` up into the wing / belly."""
    und = next((v for df in sorted(range(-30, 31), key=abs) for v in [U.under(P, x, f + df, top)] if v is not None), None)
    assert und is not None, ('no surface above', x, f)
    hgt = round(und + 1 - top)
    if x == 0: return S.pylon(hgt, (f + 6, f - 6), (f + 7, f - 7)), und
    ch = U.chord(P, x, top, und)
    le, te = ch if ch else (f + 8, f - 12)
    tp = (min(f + 7, le - 2), max(f - 12, te + 7))
    if tp[0] - tp[1] < 6: tp = (tp[1] + 6, tp[1])
    return S.pylon(hgt, (f + 7, f - 12), tp), und


def extra(d):
    P = U.main_polys(d)
    base_units = S.PYLON_UNITS
    units = []
    S.PYLONS['tankW'] = shift(S.tank480(), TANK_C[2])
    S.PYLONS['podW'] = shift(pod(), POD_W[2])
    S.PYLONS['podC'] = shift(pod(), POD_C[2])
    S.PYLONS['prop'] = prop()
    for name, (x, u, f), part, top in (('T', TANK_C, 'tankW', u_top(TANK_C, 3.5)), ('A', POD_W, 'podW', None),
                                        ('C', POD_C, 'podC', None)):
        top = POD_W[1] + 3 if part == 'podW' else POD_C[1] + 3 if part == 'podC' else round(u + 3.5)
        py, und = pylon_for(P, x, f, top)
        S.PYLONS['fp' + name] = py
        print(f'  fixed {part} at ({x},{u},{f}) top {top} underside {und:.1f} pylon h {round(und + 1 - top)}')
        sides = (('R', x), ('L', -x)) if x else (('', 0),)
        for s, xs in sides:
            units.append(('fp' + name + s, 'fp' + name, (xs, top, 0), top + 3))
            units.append(('fs' + name + s, part, (xs, u, 0), None))
            if part != 'tankW':
                S.SPIN['fs' + name + s] = (part, (xs, u, 0), 'prop', (xs, u + PROP_UP, f + PROP_FWD))
    S.PYLON_UNITS = lambda: base_units() + units
    S.FALL_SLOTS = {}                     # nothing to jettison: the tanks are fixed structure (Kuoyi 2026-11-22)
    print('  fixed units', [u[0] for u in units], 'spinning', list(S.SPIN))


def u_top(c, r): return round(c[1] + r)


if __name__ == '__main__':
    U.EXTRA = extra
    sys.argv = [sys.argv[0], 'F18G'] + sys.argv[1:]
    U.main()
