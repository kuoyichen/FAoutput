#!/usr/bin/env python3
"""F-8E Crusader (new shape, mass-upgrade thread 2026-11-27).  The stock F8J.PT used f8.SH (a crude 82-face block).
Real: length 54.25 ft, span 35.7 ft, chin intake under the radome, shoulder wing swept 42 deg with 5 deg anhedral,
low all-moving tailplane, tall fin, J57 with afterburner, tricycle gear (main legs in the fuselage, retract forward;
nose leg retracts aft), Light Gull Grey over white.
Built in feet from the nose (s aft), x right, z up from the thrust line, 3 SH units per ft.
Donor container: F86.SH (F8.SH has a non-standard layout: F2 does not point at the trailer).
Usage: f8.py OUTDIR"""
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, HERE)
import numpy as np
import core, geo
from mesh import Mesh

U = 3.0
S0 = 28.0
TOP, BELLY, GLASS, BLACK, TYRE, GREY, RADOME, FLAME, CORE = 148, 144, 74, 68, 68, 147, 151, 180, 164


def P(s, x=0.0, z=0.0): return (x * U, (S0 - s) * U, z * U)


def st(s, w, zt, zb, **k):
    d = dict(y=(S0 - s) * U, w=w * U, zt=zt * U, zb=zb * U); d.update({kk: (v * U if kk == 'zc' else v) for kk, v in k.items()}); return d


def skin(c, n): return BELLY if n[2] < -0.35 else TOP


def body(M):
    S = [st(3.3, 1.8, 1.9, -2.3, zc=-0.2, n=2.2), st(5.0, 2.1, 2.2, -2.55, zc=-0.2, n=2.3), st(9.0, 2.3, 2.4, -2.65, zc=-0.2, n=2.5),
         st(16.0, 2.55, 2.5, -2.7, zc=-0.1, n=2.6), st(24.0, 2.7, 2.65, -2.6, zc=0.0, n=2.7), st(34.0, 2.6, 2.45, -2.4, zc=0.0, n=2.6),
         st(44.0, 2.2, 2.2, -2.0, zc=0.1, n=2.4), st(50.0, 1.85, 1.9, -1.75, zc=0.1, n=2.2), st(53.8, 1.6, 1.65, -1.55, zc=0.05, n=2.0)]
    geo.fuselage(M, S, K=16, col=skin, nose='cap', tail='cap')
    M.F[-1] = (M.F[-1][0], BLACK, False, M.F[-1][3])           # nozzle
    M.F[-2] = (M.F[-2][0], BLACK, False, M.F[-2][3])           # intake face
    # radome above the chin intake
    R = [st(0.0, 0.05, 0.85, 0.75, zc=0.8, n=2.0), st(1.2, 0.85, 1.55, 0.05, zc=0.8, n=2.0), st(2.6, 1.45, 2.0, -0.4, zc=0.75, n=2.0),
         st(3.6, 1.8, 2.05, -0.6, zc=0.7, n=2.1)]
    rings = [geo.ring_pts(r['y'], r['w'], r['zt'], r['zb'], r['zc'], 12, r['n']) for r in R]
    geo.loft(M, rings, RADOME, True, P(-0.2, 0, 0.8), None)
    # intake lip (under the radome)
    I = [st(2.7, 1.75, -0.3, -2.25, zc=-1.25, n=2.2), st(3.5, 1.85, -0.2, -2.4, zc=-1.3, n=2.2)]
    rings = [geo.ring_pts(r['y'], r['w'], r['zt'], r['zb'], r['zc'], 12, r['n']) for r in I]
    geo.loft(M, rings, skin, False, 'cap', None)
    M.F[-1] = (M.F[-1][0], BLACK, False, M.F[-1][3])
    # canopy and spine
    C = [st(8.6, 0.8, 2.6, 2.0, zc=2.0, n=2.0), st(9.6, 1.2, 3.4, 2.0, zc=2.0, n=2.0), st(11.5, 1.35, 3.75, 2.0, zc=2.0, n=2.2),
         st(14.0, 1.2, 3.6, 2.0, zc=2.0, n=2.2), st(15.6, 0.9, 3.2, 2.0, zc=2.0, n=2.2)]
    rings = [geo.ring_pts(c['y'], c['w'], c['zt'], c['zb'], c['zc'], 12, c['n']) for c in C]
    rings = [[p for p in r[:4]] + [r[4]] + [r[8]] + [p for p in r[9:]] for r in rings]
    geo.loft(M, rings, GLASS, False, None, None)
    Sp = [st(15.4, 0.9, 3.2, 2.2, zc=2.2, n=2.2), st(22.0, 0.75, 3.0, 2.3, zc=2.3, n=2.2), st(38.0, 0.5, 2.75, 2.2, zc=2.2, n=2.0)]
    rings = [geo.ring_pts(c['y'], c['w'], c['zt'], c['zb'], c['zc'], 12, c['n']) for c in Sp]
    rings = [[p for p in r[:4]] + [r[4]] + [r[8]] + [p for p in r[9:]] for r in rings]
    geo.loft(M, rings, TOP, True, None, P(40.0, 0, 2.3))


def wings(M):
    dz = np.tan(np.radians(-5.0)); sw = np.tan(np.radians(42.0))
    def W(x, ch, t): return dict(s=x * U, le=(S0 - (19.0 + sw * (x - 2.4))) * U, chord=ch * U, h=(2.15 + dz * (x - 2.4)) * U, t=t * U)
    geo.surface(M, [W(2.4, 15.0, 1.0), W(9.0, 10.5, 0.75), W(16.8, 5.2, 0.45), W(17.85, 4.2, 0.35)], skin, smooth=True)
    def Hs(x, le, ch, t): return dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=-0.7 * U, t=t * U)
    geo.surface(M, [Hs(1.6, 43.5, 9.0, 0.6), Hs(6.0, 47.6, 5.4, 0.45), Hs(9.3, 51.0, 2.6, 0.3)], skin)
    def Fv(z, le, ch, t): return dict(s=z * U, le=(S0 - le) * U, chord=ch * U, h=0.0, t=t * U)
    geo.surface(M, [Fv(2.0, 38.5, 13.5, 0.7), Fv(6.0, 44.0, 8.2, 0.55), Fv(11.0, 50.0, 3.6, 0.35), Fv(11.6, 51.0, 2.4, 0.3)],
                TOP, mirror=False, vertical=True)
    for sx in (1, -1):     # ventral strakes
        geo.plate(M, [P(44.0, sx * 1.2, -1.9), P(50.0, sx * 1.1, -1.7), P(50.0, sx * 1.6, -3.0), P(46.5, sx * 1.7, -3.0)], (sx, 0, -0.3), TOP)


def main_gear(sx):
    M = Mesh(); L = 2.9 * U; r = 1.3 * U
    geo.strut(M, (0, 0, 0), (sx * 2.2 * U, 0, -L + 0.3 * U), 0.3 * U, GREY)
    geo.plate(M, [(0, 1.0 * U, 0), (0, -1.0 * U, 0), (sx * 1.9 * U, -1.0 * U, -L + 0.8 * U), (sx * 1.9 * U, 1.0 * U, -L + 0.8 * U)],
              (sx, 0, -0.3), TOP)
    geo.wheel(M, (sx * 2.6 * U, 0, -L), r, 0.75 * U, TYRE, GREY)
    return M


def nose_gear():
    M = Mesh(); L = 2.9 * U
    geo.strut(M, (0, 0, 0), (0, 0, -L + 0.2 * U), 0.22 * U, GREY)
    geo.wheel(M, (0, 0, -L), 0.9 * U, 0.5 * U, TYRE, GREY)
    return M


def flame():
    M = Mesh()
    rings = [geo.ring_pts(0.0, 1.45 * U, 1.45 * U, -1.45 * U, 0, 8, 2.0), geo.ring_pts(-3.0 * U, 1.1 * U, 1.1 * U, -1.1 * U, 0, 8, 2.0)]
    geo.loft(M, rings, FLAME, False, None, (0, -9.0 * U, 0))
    rings = [geo.ring_pts(-0.2 * U, 0.8 * U, 0.8 * U, -0.8 * U, 0, 6, 2.0)]
    geo.loft(M, rings + [geo.ring_pts(-1.5 * U, 0.6 * U, 0.6 * U, -0.6 * U, 0, 6, 2.0)], CORE, False, None, (0, -5.0 * U, 0))
    return M


def build(out):
    os.makedirs(out, exist_ok=True)
    M = Mesh(); body(M); wings(M)
    g = [core.Gear(n, main_gear(sx), P(30.0, sx * 2.3, -2.0), field=0x0A, neg=False) for sx, n in ((1, 'R'), (-1, 'L'))]
    g.append(core.Gear('N', nose_gear(), P(9.5, 0, -2.4), field=0x0A, neg=True))
    g.append(core.Gear('AB', flame(), P(53.9, 0, 0.05), var='AB', anim=False))
    core.build(os.path.join(REPO, 'SH', 'F86.SH'), os.path.join(out, 'F8N.SH'), M, g, [],
               smooth_ok=lambda c: c not in (BLACK, GLASS), ground=None)
    t = open(os.path.join(REPO, 'PT', 'F8J.PT'), encoding='latin1', newline='').read()
    t = re.sub(r'string "f8\.SH"', 'string "f8n.SH"', t, flags=re.I)
    open(os.path.join(out, 'F8J.PT'), 'w', encoding='latin1', newline='').write(t)


if __name__ == '__main__':
    build(sys.argv[1])
