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
from f18g_growler import lathe, FIN, DARK, GREY, alq218
import f18_wing_fold as W

# store centres (x, up, fwd): F18F.PT stations (hp5 tank x 22, hp7 x 34, hp9 centre) + PT_DROP, as the PT stores are drawn
TANK_C = (22, -7, 6)
POD_W = (34, -6, 3)
POD_C = (0, -10, -4)
PROP_FWD = 22                     # prop disc, ahead of the pod centre
PROP_UP = 0
TIP = (69, 1, -17)                # ALQ-218 centre, x > 0 side (F18G v9)


def pod():
    """ALQ-99: rounded box section 6 wide x 7 deep (deeper below the axis), rounded tail, nose necking into a spinner."""
    sec = [(-2, 3), (2, 3), (3, 2), (3, -2), (2, -4), (-2, -4), (-3, -2), (-3, 2)]
    V, F, _ = lathe(sec, [(-23, .5, 0), (-21, .85, 0), (-18, 1, 0), (15, 1, 0), (18, .8, 0), (21, .4, 0), (25, 0, 0)])
    return V, F


def prop():
    """Two 1 x 1 blades right at the axis (Kuoyi 2026-11-22: smallest possible), both sides drawn; turns about the
    fwd axis (C4 roll)."""
    V, F = [], []
    for s in (1, -1):
        b = len(V)
        V += [(0, 0, 0), (s, 0, 0), (s, 0, s), (0, 0, s)]
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
            units.append(('fs' + name + s, part, (xs, top if part == 'tankW' else u, 0), None))
            if part != 'tankW':
                S.SPIN['fs' + name + s] = (part, (xs, u, 0), 'prop', (xs, u + PROP_UP, f + PROP_FWD))
    # draw order (Kuoyi 2026-11-22 in game: seen from the side the outer AGM-88 was covered by the pod / tank behind
    # it): each wing's stores are ONE unit with its own sub-tree: inboard -> outboard chain split by x planes between
    # the stations (eye outboard: inner stores first), each store against its pylon by a plane at the store top
    S.GROUPS = {}
    agm = next(k for k, v in S.SLOTS.items() if k[0] == 'R' and v[3][0] > 40)[1:]      # outer wing slot station
    agm_top = S.SLOTS['R' + agm][3][1]
    def item(store, pylon, top):
        return ('node', (0, 16384, 0), (0, -top, 0), ('seq', [store]), ('seq', [pylon]))
    for s, sg in (('R', 1), ('L', -1)):
        tk = item(('c4', ('P', 'tankW'), (sg * TANK_C[0], u_top(TANK_C, 3.5), 0)), ('c4', ('P', 'fpT'), (sg * TANK_C[0], u_top(TANK_C, 3.5), 0)), u_top(TANK_C, 3.5))
        pd = item(('call', 'Xfs' + 'A' + s), ('c4', ('P', 'fpA'), (sg * POD_W[0], POD_W[1] + 3, 0)), POD_W[1] + 3)
        hm = item(('call', s + agm), ('call', 'py' + s + agm), agm_top)
        xp = lambda b: ((16384 * sg, 0, 0), (-b * sg, 0, 0))
        tr = ('node', *xp(28), tk, pd)
        tr = ('node', *xp(42), tr, hm)
        S.GROUPS['W' + s] = (['fpT' + s, 'fsT' + s, 'fpA' + s, 'fsA' + s, s + agm, 'py' + s + agm], tr)
    S.GROUPS['WC'] = (['fpC', 'fsC'], item(('call', 'XfsC'), ('c4', ('P', 'fpC'), (0, POD_C[1] + 3, 0)), POD_C[1] + 3))
    # the wing groups go where place_units puts them (the wing's branch), but always split from the wing by a plane at
    # its underside (eye below -> drawn after the wing): fewest painter errors over the sh_order views, gear down
    P0 = S.PLACER
    def placer(c, ROOT, ugeo, ubox):
        plan, refs = P0(c, ROOT, ugeo, ubox) if P0 else S.place_units(c, ROOT, ubox)
        for T in plan:
            plan[T] = [(u, (0, -16384, 0), (0, 0, 0)) if u in ('WR', 'WL') else (u, n, dd)
                       for u, n, dd in plan[T]]
        return plan, refs
    S.PLACER = placer
    S.PYLONS['tip'] = alq218()            # wingtip ALQ-218 (as F18G v9), drawn by the folding panels
    S.PYLON_UNITS = lambda: base_units() + units
    make0 = S.make
    def make(d, *a, **k):                  # the tip pod part's offset is known once the stores block is laid out
        out, at = make0(d, *a, **k)
        W.TIP_FIXED = (at[('P', 'tip')], TIP)
        print('  tip pod part at', hex(at[('P', 'tip')]), 'pos', TIP)
        return out, at
    S.make = make
    S.FALL_SLOTS = {}                     # nothing to jettison: the tanks are fixed structure (Kuoyi 2026-11-22)
    print('  fixed units', [u[0] for u in units], 'spinning', list(S.SPIN))


def u_top(c, r): return round(c[1] + r)


if __name__ == '__main__':
    U.EXTRA = extra
    sys.argv = [sys.argv[0], 'F18G'] + sys.argv[1:]
    U.main()
