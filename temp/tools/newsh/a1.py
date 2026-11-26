#!/usr/bin/env python3
"""A-1H Skyraider (new shape, mass-upgrade thread 2026-11-27).  The stock A1.PT used kin.SH (a T-28-like trainer).
Real: length 38.8 ft, span 50 ft, R-3350 cowl, deep fuselage with a long framed canopy, big fin, 4-blade 13.5 ft prop,
main gear retracting aft, retracting tail wheel, Light Gull Grey overall.
Built in feet from the nose (s aft), x right, z up from the thrust line, 3 SH units per ft.
Usage: a1.py OUTDIR"""
import os, sys, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, HERE)
import numpy as np
import core, geo, props
from mesh import Mesh

U = 3.0                   # SH units per ft
S0 = 10.0                 # ft from the nose to the origin (about the CG)
BLUE, GLASS, BLACK, TYRE, GREY, METAL, EXH = 152, 74, 68, 68, 147, 150, 158   # BLUE = the skin colour (light gull grey)


def P(s, x=0.0, z=0.0): return (x * U, (S0 - s) * U, z * U)


def st(s, w, zt, zb, **k):
    d = dict(y=(S0 - s) * U, w=w * U, zt=zt * U, zb=zb * U); d.update({kk: (v * U if kk == 'zc' else v) for kk, v in k.items()}); return d


def body(M):
    S = [st(1.2, 2.2, 2.1, -2.3, zc=-0.1, n=2.0), st(2.0, 2.45, 2.4, -2.6, zc=-0.1, n=2.0), st(4.5, 2.45, 2.5, -2.75, zc=-0.15, n=2.1),
         st(7.0, 2.35, 2.6, -3.1, zc=-0.2, n=2.3), st(10.5, 2.25, 2.75, -3.3, zc=-0.2, n=2.5), st(15.0, 2.05, 2.85, -3.1, zc=-0.1, n=2.6),
         st(20.0, 1.7, 2.7, -2.5, zc=0.1, n=2.5), st(26.0, 1.15, 2.3, -1.4, zc=0.4, n=2.3), st(32.0, 0.65, 1.95, -0.3, zc=0.7, n=2.2),
         st(37.5, 0.25, 1.7, 0.5, zc=1.0, n=2.0)]
    geo.fuselage(M, S, K=16, col=BLUE, nose='cap', tail=P(38.8, 0, 1.1))
    M.F[-17] = (M.F[-17][0], BLACK, False, M.F[-17][3])        # cowl front: dark engine face
    sp = [geo.ring_pts(P(1.25)[1], 0.85 * U, 0.75 * U, -0.95 * U, -0.1 * U, 8, 2.0),
          geo.ring_pts(P(0.6)[1], 0.5 * U, 0.4 * U, -0.6 * U, -0.1 * U, 8, 2.0)]
    geo.loft(M, sp, BLUE, True, None, P(0.0, 0, -0.1))
    # long framed canopy
    C = [st(11.0, 1.0, 2.95, 2.5, zc=2.5, n=2.0), st(11.8, 1.3, 4.05, 2.5, zc=2.5, n=2.6), st(13.5, 1.4, 4.45, 2.5, zc=2.5, n=2.6),
         st(16.0, 1.3, 4.3, 2.5, zc=2.5, n=2.6), st(17.6, 0.9, 3.55, 2.5, zc=2.5, n=2.4)]
    rings = [geo.ring_pts(c['y'], c['w'], c['zt'], c['zb'], c['zc'], 12, c['n']) for c in C]
    rings = [[p for p in r[:4]] + [r[4]] + [r[8]] + [p for p in r[9:]] for r in rings]
    geo.loft(M, rings, GLASS, False, None, None)
    for sx in (1, -1):        # exhaust stacks
        geo.prism(M, [(sx * 2.4 * U, -0.3 * U), (sx * 2.65 * U, -0.3 * U), (sx * 2.65 * U, -1.2 * U), (sx * 2.4 * U, -1.2 * U)], 1,
                  P(4.2)[1], P(6.2)[1], EXH)
    # dive brakes / belly: centreline pylon
    geo.prism(M, [(-0.25 * U, -3.1 * U), (0.25 * U, -3.1 * U), (0.25 * U, -3.6 * U), (-0.25 * U, -3.6 * U)], 1, P(9.5)[1], P(14.5)[1], BLUE)


def wings(M):
    # low wing: flat centre section to 6 ft, 6 deg dihedral outboard, square tips; under-wing pylons
    dz = np.tan(np.radians(6.0))
    def hz(x): return -2.0 + dz * max(0.0, x - 6.0)
    def W(x, le, ch, t): return dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=hz(x) * U, t=t * U)
    geo.surface(M, [W(2.2, 8.8, 11.0, 1.7), W(6.0, 9.0, 10.4, 1.5), W(15.0, 10.4, 8.0, 1.0), W(24.2, 12.0, 5.6, 0.6),
                    W(25.0, 12.4, 4.8, 0.5)], BLUE, smooth=True)
    for x in (8.5, 10.5, 12.5, 14.5, 16.5, 18.5):
        for sx in (1, -1):
            z = hz(x) - 0.45
            geo.prism(M, [(sx * x * U - 0.15 * U, z * U), (sx * x * U + 0.15 * U, z * U), (sx * x * U + 0.15 * U, (z - 0.4) * U),
                          (sx * x * U - 0.15 * U, (z - 0.4) * U)], 1, P(11.2)[1], P(14.0)[1], GREY)
    def Hs(x, le, ch, t): return dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=1.6 * U, t=t * U)
    geo.surface(M, [Hs(0.3, 32.0, 5.8, 0.6), Hs(5.5, 32.8, 4.6, 0.45), Hs(8.6, 34.0, 3.0, 0.35), Hs(9.1, 34.6, 2.0, 0.3)], BLUE)
    def Fv(z, le, ch, t): return dict(s=z * U, le=(S0 - le) * U, chord=ch * U, h=0.0, t=t * U)
    geo.surface(M, [Fv(1.8, 29.2, 9.4, 0.7), Fv(5.5, 32.0, 6.6, 0.55), Fv(8.8, 34.4, 4.2, 0.4), Fv(9.8, 35.6, 2.4, 0.3)],
                BLUE, mirror=False, vertical=True)


def main_gear(sx):
    """leg + fairing door + wheel, pivot at the wing (part origin), down: wheel 5.0 ft below the pivot"""
    M = Mesh()
    L = 5.5 * U; r = 1.5 * U
    geo.strut(M, (0, 0, 0), (0, 0, -L + 0.4 * U), 0.32 * U, GREY)
    geo.plate(M, [(sx * 0.4 * U, 0.9 * U, -0.3 * U), (sx * 0.4 * U, -0.9 * U, -0.3 * U), (sx * 0.4 * U, -0.9 * U, -L + 1.5 * U),
                  (sx * 0.4 * U, 0.9 * U, -L + 1.5 * U)], (sx, 0, 0), BLUE)
    geo.wheel(M, (-sx * 0.35 * U, 0, -L), r, 0.75 * U, TYRE, GREY)
    return M


def tail_gear():
    M = Mesh(); L = 8.5 * U
    geo.strut(M, (0, 0, 0), (0, -0.6 * U, -L + 0.3 * U), 0.25 * U, GREY)
    geo.wheel(M, (0, -0.6 * U, -L), 0.55 * U, 0.4 * U, TYRE, GREY, n=6)
    return M


def build(out):
    os.makedirs(out, exist_ok=True)
    M = Mesh(); body(M); wings(M)
    g = []
    for sx, name in ((1, 'R'), (-1, 'L')):
        g.append(core.Gear(name, main_gear(sx), P(11.2, sx * 7.0, -2.2), field=0x0A, neg=True))
    g.append(core.Gear('T', tail_gear(), P(33.6, 0, -0.1), field=0x0A, neg=False))
    R = 6.75 * U; yp = P(0.9)[1]
    disc = core.Disc('prop', [(R, yp, R), (-R, yp, R), (-R, yp, -R), (R, yp, -R)], (0, 1, 0), props.FRAMES)
    donor = os.path.join(REPO, 'SH', 'KIN.SH')
    props.make(os.path.join(REPO, 'PIC', '_KIN.PIC'), os.path.join(out, '_A1N.PIC'), blades=4)
    core.build(donor, os.path.join(out, 'A1N.SH'), M, g, [disc], pic_name='_A1N.PIC',
               smooth_ok=lambda c: c not in (BLACK, GLASS))
    import re
    t = open(os.path.join(REPO, 'PT', 'A1.PT'), encoding='latin1', newline='').read()
    t = re.sub(r'string "kin\.SH"', 'string "a1n.SH"', t, flags=re.I)
    open(os.path.join(out, 'A1.PT'), 'w', encoding='latin1', newline='').write(t)

if __name__ == '__main__':
    build(sys.argv[1])
