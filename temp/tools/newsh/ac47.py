#!/usr/bin/env python3
"""AC-47D Spooky (new shape, mass-upgrade thread 2026-11-27).  The stock AC47.PT used a47.SH (a turboprop
transport, not a C-47).  Real: length 64.5 ft, span 95 ft, two R-1830 nacelles 9 ft off the centreline with
3-blade 11.5 ft props, main gear retracting forward into the nacelles (wheels half exposed), fixed tail wheel,
three SUU-11 / GAU-2 miniguns firing from the left side, SEA camouflage with black undersides.
Built in feet from the nose (s aft), x right, z up from the thrust line, 3 SH units per ft.
Usage: ac47.py OUTDIR"""
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, HERE)
import numpy as np
import core, geo, props
from mesh import Mesh

U = 3.0
S0 = 25.0
TAN, GREEN, DGREEN, BLACK, GLASS, TYRE, GREY, EXH = 86, 104, 99, 68, 74, 68, 147, 158


def P(s, x=0.0, z=0.0): return (x * U, (S0 - s) * U, z * U)


def st(s, w, zt, zb, **k):
    d = dict(y=(S0 - s) * U, w=w * U, zt=zt * U, zb=zb * U); d.update({kk: (v * U if kk == 'zc' else v) for kk, v in k.items()}); return d


def camo(c, n):
    """SEA three-tone camouflage on top and sides, black underneath"""
    if n[2] < -0.45: return BLACK
    x, y, z = c[0] / U, c[1] / U, c[2] / U
    v = np.sin(x / 4.0 + y / 6.0) + np.sin(y / 3.8 - z / 3.0 + x / 7.0) * 0.8
    return TAN if v > 0.55 else DGREEN if v < -0.6 else GREEN


def body(M):
    S = [st(0.6, 1.4, 1.2, -1.6, zc=-0.2, n=2.0), st(2.0, 2.6, 2.4, -2.7, zc=-0.2, n=2.0), st(4.5, 3.6, 3.6, -3.6, zc=-0.1, n=2.2),
         st(8.0, 4.05, 4.1, -3.95, zc=0.0, n=2.3), st(14.0, 4.15, 4.25, -4.0, zc=0.0, n=2.4), st(30.0, 4.05, 4.15, -3.85, zc=0.1, n=2.4),
         st(40.0, 3.4, 3.8, -3.0, zc=0.3, n=2.3), st(50.0, 2.3, 3.2, -1.5, zc=0.7, n=2.2), st(57.0, 1.3, 2.7, -0.1, zc=1.1, n=2.1),
         st(63.0, 0.5, 2.3, 1.0, zc=1.6, n=2.0)]
    geo.fuselage(M, S, K=16, col=camo, nose=P(-0.1, 0, -0.2), tail=P(64.5, 0, 1.9))
    # cockpit windscreen band
    C = [st(3.4, 3.3, 3.45, 1.4, zc=1.4, n=2.0), st(4.6, 3.75, 3.95, 1.5, zc=1.5, n=2.2), st(6.6, 4.1, 4.2, 1.6, zc=1.6, n=2.3)]
    rings = [geo.ring_pts(c['y'], c['w'] + 0.05 * U, c['zt'] + 0.05 * U, c['zb'], c['zc'], 12, c['n']) for c in C]
    rings = [[p for p in r[:4]] + [r[4]] + [r[8]] + [p for p in r[9:]] for r in rings]
    geo.loft(M, rings, GLASS, False, None, None)
    # cabin windows (both sides) and the three left-side miniguns
    for s in (15.0, 18.5, 22.0, 25.5, 29.0, 32.5, 36.0):
        for sx in (1, -1):
            w = geo.interp(S, P(s)[1], 'w') / U + 0.06
            geo.prism(M, [(P(s - 0.7)[1], 1.9 * U), (P(s + 0.7)[1], 1.9 * U), (P(s + 0.7)[1], 0.9 * U), (P(s - 0.7)[1], 0.9 * U)],
                      0, sx * (w - 0.3) * U, sx * (w + 0.08) * U, GLASS)
    for s in (18.5, 22.0, 25.5):
        geo.strut(M, P(s, -3.2, 1.0), P(s, -6.2, 1.0), 0.28 * U, BLACK, n=6)
        geo.strut(M, P(s, -3.6, 1.0), P(s, -4.6, 1.0), 0.55 * U, GREY)
    # fixed tail wheel
    geo.strut(M, P(55.0, 0, 0.2), P(55.3, 0, -8.6), 0.3 * U, GREY)
    geo.wheel(M, P(55.3, 0, -8.7), 0.8 * U, 0.55 * U, TYRE, GREY, n=8)


def nacelles(M):
    for sx in (1, -1):
        x = sx * 9.0
        S = [st(9.0, 2.05, 0.4, -3.6, zc=-1.6, n=2.0), st(10.0, 2.35, 0.75, -3.95, zc=-1.6, n=2.0), st(14.0, 2.3, 0.7, -4.1, zc=-1.7, n=2.2),
             st(20.0, 1.9, 0.2, -4.2, zc=-2.2, n=2.3), st(25.0, 1.1, -1.4, -3.9, zc=-2.6, n=2.2), st(28.5, 0.35, -2.3, -3.3, zc=-2.8, n=2.0)]
        rings = [[(px + x * U, py, pz) for px, py, pz in geo.ring_pts(s['y'], s['w'], s['zt'], s['zb'], s['zc'], 12, s['n'])] for s in S]
        geo.loft(M, rings, camo, True, 'cap', P(29.2, x, -2.9))
        M.F[-13] = (M.F[-13][0], BLACK, False, M.F[-13][3])        # engine face
        for sy in (1, -1):    # exhaust
            geo.prism(M, [(x * U + sy * 1.7 * U, -2.9 * U), (x * U + sy * 2.05 * U, -2.9 * U), (x * U + sy * 2.05 * U, -3.4 * U),
                          (x * U + sy * 1.7 * U, -3.4 * U)], 1, P(12.0)[1], P(15.0)[1], EXH)


def wings(M):
    dz = np.tan(np.radians(5.0))
    def hz(x): return -3.0 + dz * max(0.0, x - 9.0)
    def W(x, le, ch, t): return dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=hz(x) * U, t=t * U)
    geo.surface(M, [W(3.5, 16.8, 14.6, 2.6), W(9.0, 17.3, 13.4, 2.3), W(30.0, 20.5, 8.8, 1.3), W(45.5, 23.4, 5.2, 0.7),
                    W(47.5, 24.4, 3.6, 0.55)], camo, smooth=True)
    def Hs(x, le, ch, t): return dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=2.4 * U, t=t * U)
    geo.surface(M, [Hs(0.3, 54.0, 9.0, 0.9), Hs(8.0, 55.6, 6.8, 0.65), Hs(12.6, 57.6, 4.2, 0.45), Hs(13.3, 58.6, 2.6, 0.35)], camo)
    def Fv(z, le, ch, t): return dict(s=z * U, le=(S0 - le) * U, chord=ch * U, h=0.0, t=t * U)
    geo.surface(M, [Fv(2.6, 48.0, 15.0, 1.0), Fv(5.0, 52.5, 10.6, 0.85), Fv(12.0, 56.6, 6.4, 0.6), Fv(15.0, 58.6, 3.6, 0.45),
                    Fv(15.6, 59.6, 2.0, 0.35)], camo, mirror=False, vertical=True)


def main_gear(sx):
    """twin-strut leg + wheel under the nacelle; folds forward (wheel stays half below the nacelle)"""
    M = Mesh()
    L = 3.8 * U; r = 2.1 * U
    for dx in (-0.9, 0.9):
        geo.strut(M, (dx * U, 0, 0), (dx * U, 0, -L + 0.3 * U), 0.22 * U, GREY)
    geo.strut(M, (-0.9 * U, 0, -L + 0.3 * U), (0.9 * U, 0, -L + 0.3 * U), 0.2 * U, GREY)
    geo.wheel(M, (0, 0, -L), r, 0.95 * U, TYRE, GREY, n=10)
    return M


def build(out):
    os.makedirs(out, exist_ok=True)
    M = Mesh(); body(M); nacelles(M); wings(M)
    g = [core.Gear(name, main_gear(sx), P(17.0, sx * 9.0, -3.6), field=0x0A, neg=False) for sx, name in ((1, 'R'), (-1, 'L'))]
    discs = []
    R = 5.75 * U
    for sx, name in ((1, 'pR'), (-1, 'pL')):
        x0 = sx * 9.0 * U; yp = P(8.4)[1]; zc = -1.6 * U
        discs.append(core.Disc(name, [(x0 + R, yp, zc + R), (x0 - R, yp, zc + R), (x0 - R, yp, zc - R), (x0 + R, yp, zc - R)],
                               (0, 1, 0), props.FRAMES))
    props.make(os.path.join(REPO, 'PIC', '_A47.PIC'), os.path.join(out, '_AC47N.PIC'), blades=3)
    core.build(os.path.join(REPO, 'SH', 'A47.SH'), os.path.join(out, 'AC47N.SH'), M, g, discs, pic_name='_AC47N.PIC',
               smooth_ok=lambda c: c not in (BLACK, GLASS))
    t = open(os.path.join(REPO, 'PT', 'AC47.PT'), encoding='latin1', newline='').read()
    t = re.sub(r'string "a47\.SH"', 'string "ac47n.SH"', t, flags=re.I)
    open(os.path.join(out, 'AC47.PT'), 'w', encoding='latin1', newline='').write(t)


if __name__ == '__main__':
    build(sys.argv[1])
