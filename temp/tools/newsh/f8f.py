#!/usr/bin/env python3
"""F8F-1 Bearcat (new shape, mass-upgrade thread 2026-11-27).  The stock F8F.PT used alz.SH (a T-28-like
trainer shape).  Real: length 28.25 ft, span 35.8 ft, R-2800 cowl 4.6 ft, bubble canopy, 4-blade 12.6 ft prop,
inward-retracting main gear (track 10.8 ft), retracting tail wheel, Glossy Sea Blue overall.
Built in feet from the nose (s aft), x right, z up from the thrust line, 3 SH units per ft.
Usage: f8f.py OUTDIR"""
import os, sys, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, HERE)
import numpy as np
import core, geo, props
from mesh import Mesh

U = 3.0                   # SH units per ft
S0 = 10.0                 # ft from the nose to the origin (about the CG)
BLUE, GLASS, BLACK, TYRE, GREY, METAL, EXH = 141, 74, 68, 68, 147, 150, 158


def P(s, x=0.0, z=0.0): return (x * U, (S0 - s) * U, z * U)


def st(s, w, zt, zb, **k):
    d = dict(y=(S0 - s) * U, w=w * U, zt=zt * U, zb=zb * U); d.update({kk: (v * U if kk == 'zc' else v) for kk, v in k.items()}); return d


def body(M):
    # cowl (round), fuselage swelling to the cockpit, tapering tail cone; ring K=16
    S = [st(0.9, 2.05, 1.95, -2.05, zc=0, n=2.0), st(1.6, 2.3, 2.25, -2.3, zc=0, n=2.0), st(3.5, 2.35, 2.35, -2.35, zc=0, n=2.0),
         st(5.2, 2.3, 2.35, -2.4, zc=-0.05, n=2.1), st(8.0, 2.2, 2.4, -2.5, zc=-0.2, n=2.3),
         st(11.0, 2.05, 2.5, -2.45, zc=-0.2, n=2.4), st(14.0, 1.85, 2.35, -2.2, zc=-0.1, n=2.4),
         st(17.5, 1.45, 2.05, -1.7, zc=0.1, n=2.3), st(21.0, 1.0, 1.75, -1.1, zc=0.3, n=2.2),
         st(24.5, 0.6, 1.5, -0.5, zc=0.5, n=2.1), st(27.6, 0.25, 1.25, 0.0, zc=0.6, n=2.0)]
    geo.fuselage(M, S, K=16, col=BLUE, nose='cap', tail=P(28.25, 0, 0.7))
    M.F[-17] = (M.F[-17][0], BLACK, False, M.F[-17][3])        # cowl front cap: dark (engine face)
    # spinner
    sp = [geo.ring_pts(P(0.95)[1], 0.9 * U, 0.9 * U, -0.9 * U, 0, 8, 2.0), geo.ring_pts(P(0.3)[1], 0.55 * U, 0.55 * U, -0.55 * U, 0, 8, 2.0)]
    geo.loft(M, sp, BLUE, True, None, P(-0.6, 0, 0))
    # bubble canopy: windscreen 10.4 ft, bubble to 15.6 ft, top z 4.3
    C = [st(10.3, 0.9, 2.45, 1.9, zc=1.9, n=2.0), st(10.9, 1.35, 3.6, 1.9, zc=1.9, n=2.0), st(12.0, 1.45, 4.25, 1.9, zc=1.9, n=2.0),
         st(13.6, 1.35, 4.2, 1.9, zc=1.9, n=2.0), st(15.0, 1.0, 3.6, 1.9, zc=1.9, n=2.0), st(16.2, 0.35, 2.4, 1.9, zc=1.9, n=2.0)]
    rings = [geo.ring_pts(s['y'], s['w'], s['zt'], s['zb'], s['zc'], 12, s['n']) for s in C]
    rings = [[p for p in r[:4]] + [r[4]] + [r[8]] + [p for p in r[9:]] for r in rings]     # upper half + base points
    geo.loft(M, rings, GLASS, False, None, None)
    # exhaust stacks (dark) on the cowl sides
    for sx in (1, -1):
        geo.prism(M, [(sx * 2.2 * U, -0.3 * U), (sx * 2.45 * U, -0.3 * U), (sx * 2.45 * U, -1.0 * U), (sx * 2.2 * U, -1.0 * U)], 1,
                  P(4.2)[1], P(5.4)[1], EXH)


def wings(M):
    # low wing, 5.5 deg dihedral from the root, slight LE taper; rounded tip
    dz = np.tan(np.radians(5.5))
    def W(x, le, ch, t): return dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=(-1.75 + dz * (x - 2.0)) * U, t=t * U)
    geo.surface(M, [W(1.5, 6.0, 9.0, 1.3), W(6.0, 6.5, 7.9, 1.05), W(14.5, 7.6, 5.4, 0.6), W(17.3, 8.3, 4.0, 0.45),
                    W(17.9, 8.9, 2.6, 0.35)], BLUE, smooth=True)
    # horizontal tail (span 13 ft) and fin
    def Hs(x, le, ch, t): return dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=1.05 * U, t=t * U)
    geo.surface(M, [Hs(0.3, 23.2, 4.6, 0.5), Hs(4.0, 23.9, 3.6, 0.4), Hs(6.5, 24.8, 2.4, 0.3)], BLUE)
    def Fv(z, le, ch, t): return dict(s=z * U, le=(S0 - le) * U, chord=ch * U, h=0.0, t=t * U)
    geo.surface(M, [Fv(1.2, 21.5, 6.6, 0.55), Fv(4.5, 23.6, 4.5, 0.45), Fv(6.9, 25.2, 2.8, 0.35), Fv(7.4, 25.9, 1.6, 0.3)],
                BLUE, mirror=False, vertical=True)


def main_gear(sx):
    """leg + fairing door + wheel, pivot at the wing (part origin), down: wheel 5.0 ft below the pivot"""
    M = Mesh()
    L = 4.9 * U; r = 1.3 * U
    geo.strut(M, (0, 0, 0), (0, 0, -L + 0.4 * U), 0.32 * U, GREY)
    geo.plate(M, [(sx * 0.4 * U, 0.9 * U, -0.3 * U), (sx * 0.4 * U, -0.9 * U, -0.3 * U), (sx * 0.4 * U, -0.9 * U, -L + 1.5 * U),
                  (sx * 0.4 * U, 0.9 * U, -L + 1.5 * U)], (sx, 0, 0), BLUE)
    geo.wheel(M, (-sx * 0.35 * U, 0, -L), r, 0.75 * U, TYRE, GREY)
    return M


def tail_gear():
    M = Mesh(); L = 7.0 * U
    geo.strut(M, (0, 0, 0), (0, -0.6 * U, -L + 0.3 * U), 0.25 * U, GREY)
    geo.wheel(M, (0, -0.6 * U, -L), 0.55 * U, 0.4 * U, TYRE, GREY, n=6)
    return M


def build(out):
    os.makedirs(out, exist_ok=True)
    M = Mesh(); body(M); wings(M)
    g = []
    for sx, name in ((1, 'R'), (-1, 'L')):
        g.append(core.Gear(name, main_gear(sx), P(8.4, sx * 5.4, -1.95), field=0x0C, neg=(sx > 0)))
    g.append(core.Gear('T', tail_gear(), P(24.6, 0, -0.6), field=0x0A, neg=False))
    R = 6.3 * U; yp = P(0.7)[1]
    disc = core.Disc('prop', [(R, yp, R), (-R, yp, R), (-R, yp, -R), (R, yp, -R)], (0, 1, 0), props.FRAMES)
    donor = os.path.join(REPO, 'SH', 'ALZ.SH')
    props.make(os.path.join(REPO, 'PIC', '_ALZ.PIC'), os.path.join(out, '_F8FN.PIC'), blades=4)
    core.build(donor, os.path.join(out, 'F8FN.SH'), M, g, [disc], pic_name='_F8FN.PIC',
               smooth_ok=lambda c: c not in (BLACK, GLASS))
    import re
    t = open(os.path.join(REPO, 'PT', 'F8F.PT'), encoding='latin1', newline='').read()
    t = re.sub(r'string "alz\.SH"', 'string "f8fn.SH"', t, flags=re.I)
    open(os.path.join(out, 'F8F.PT'), 'w', encoding='latin1', newline='').write(t)


if __name__ == '__main__':
    build(sys.argv[1])
