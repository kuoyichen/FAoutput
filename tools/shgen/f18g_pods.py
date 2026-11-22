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
from f18g_growler import lathe, FIN, DARK, GREY, FLAT, alq218
import f18_wing_fold as W

# store centres (x, up, fwd): F18F.PT stations (hp5 tank x 22, hp7 x 34, hp9 centre) + PT_DROP, as the PT stores are drawn
TANK_C = (22, -7, 6)
POD_W = (34, -6, 3)
POD_C = (0, -10, -4)
PROP_FWD = 22                     # prop disc, ahead of the pod centre
PROP_UP = 2                       # = POD_AXIS: turbine on the spinner, high on the pod
GEAR_X = 17                       # |x| just outboard of the main gear (wheel x 8..16)
TIP = (69, 1, -17)                # ALQ-218 centre, x > 0 side (F18G v9)


# ALQ-99 side profile (Kuoyi 2026-11-22, photo): flat top along the whole pod, belly straight then sweeping up in a long
# curve under the front to a neck that sits HIGH (axis near the top line), small spinner + turbine there; rounded tail.
# stations: (fwd, top, bottom, half width), pod centre frame (x, fwd, up)
POD_ST = [(-23, 2, -2, 1.5), (-21.5, 3, -3.5, 2.5), (-19, 3, -4, 3), (2, 3, -4, 3), (7, 3, -3.6, 3), (11, 3, -2.8, 2.9),
          (14.5, 3, -1.6, 2.6), (17.5, 2.8, -.2, 2.1), (19.5, 2.5, .8, 1.4), (21, 2.4, 1.3, 1), (23, 2.7, 1.3, .9)]
POD_TIP = (25, 2)          # spinner tip (fwd, up)
POD_AXIS = 2               # turbine axis height (up), on the spinner


def pod():
    """ALQ-99 lofted from POD_ST: 8-point rounded-box sections, flat cap at the tail, spinner point at the front."""
    V, rings = [], []
    for f, tp, bt, w in POD_ST:
        h = tp - bt; k = min(1, h / 3)
        sec = [(-w * .6, tp), (w * .6, tp), (w, tp - .3 * h * k), (w, bt + .35 * h * k), (w * .6, bt), (-w * .6, bt),
               (-w, bt + .35 * h * k), (-w, tp - .3 * h * k)]
        r = []
        for x, u in sec:
            v = (round(x), round(f), round(u))
            if v not in V: V.append(v)
            r.append(V.index(v))
        rings.append((f, (tp + bt) / 2, r))
    V.append((0, POD_TIP[0], POD_TIP[1])); tip = len(V) - 1
    F = []
    def add(q, f, axis_u):
        q = [v for i, v in enumerate(q) if v != q[i - 1]]
        if len(set(q)) < 3: return
        P = [V[i] for i in q]; n = [0, 0, 0]
        for i in range(len(P)):                  # file order (x, fwd, up); FA wants the winding sum pointing inside
            a_, b_ = P[i], P[(i + 1) % len(P)]
            n[0] += a_[1]*b_[2] - a_[2]*b_[1]; n[1] += a_[2]*b_[0] - a_[0]*b_[2]; n[2] += a_[0]*b_[1] - a_[1]*b_[0]
        c = [sum(p[j] for p in P) / len(P) for j in range(3)]
        out = (c[0], c[1] - f, c[2] - axis_u)    # from the local axis point outwards
        if sum(n[j] * out[j] for j in range(3)) > 0: q = q[::-1]
        F.append((FLAT, GREY, q))
    for (fa, ua, A), (fb, ub, B) in zip(rings, rings[1:]):
        for j in range(8): add([A[j], A[(j + 1) % 8], B[(j + 1) % 8], B[j]], (fa + fb) / 2, (ua + ub) / 2)
    fl, ul, L = rings[-1]
    for j in range(8): add([L[j], L[(j + 1) % 8], tip], fl + 1, POD_AXIS)
    f0, u0, R0 = rings[0]
    add(list(R0), f0 + 3, u0)                    # tail cap
    return V, F


def tank():
    """EA-18G 480-gal tank, 25% fatter than the F/A-18F one (r 4.4), longer, pointed nose, BLUNT tail (flat cap);
    top at local up 0 (hangs from the pylon bottom)."""
    r = 4.4; e = r * .7
    sec = [(0, r), (e, e), (r, 0), (e, -e), (0, -r), (-e, -e), (-r, 0), (-e, e)]
    st = [(31, 0, -r), (27, .35, -r), (21, .65, -r), (15, .88, -r), (9, 1, -r), (-14, 1, -r), (-20, .9, -r), (-24, .75, -r)]
    V, F, rings = lathe(sec, st, GREY)
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
    S.PYLONS['tankW'] = shift(tank(), TANK_C[2])
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
    # the wing groups go where place_units puts them (the wing's branch).  Right: split from it by a plane at the wing
    # underside (eye below -> drawn after).  Left: that branch also draws the LEFT MAIN GEAR (part 0x351e; the right
    # gear is in the body branch, drawn before the right wing from the right), so it is split by an x plane just
    # outboard of the gear: eye outboard -> stores after the gear (Kuoyi 2026-11-22: the gear showed through the
    # stores from slightly above the left side).  The wing's top surface is ordered against both by the original
    # node 0x31d8 (from above it is drawn last).
    P0 = S.PLACER
    def placer(c, ROOT, ugeo, ubox):
        plan, refs = P0(c, ROOT, ugeo, ubox) if P0 else S.place_units(c, ROOT, ubox)
        for T in plan:
            plan[T] = [(u, (0, -16384, 0), (0, 0, 0)) if u == 'WR' else
                       (u, (-16384, 0, 0), (GEAR_X, 0, 0)) if u == 'WL' else (u, n, dd) for u, n, dd in plan[T]]
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
