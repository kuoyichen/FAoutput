#!/usr/bin/env python3
"""F6F-5 Hellcat (new shape and new F6F.PT copied from F8F.PT, mass-upgrade thread 2026-11-27, Kuoyi's request).
Real: length 33.6 ft, span 42.8 ft (square tips), deep R-2800 cowl with chin intake, framed canopy on a raised
turtledeck, flat centre section then 7.5 deg dihedral, 3-blade 13.1 ft prop, main gear retracting aft
(track 11 ft), retracting tail wheel, Glossy Sea Blue overall.
Built in feet from the nose (s aft), x right, z up from the thrust line, 3 SH units per ft.
Usage: f6f.py OUTDIR"""
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
    # deep cowl with chin intake, deep fuselage, raised turtledeck behind the cockpit; ring K=16
    S = [st(0.9, 2.15, 2.05, -2.45, zc=-0.1, n=2.0), st(1.7, 2.45, 2.4, -2.85, zc=-0.15, n=2.1), st(3.8, 2.5, 2.5, -2.95, zc=-0.2, n=2.1),
         st(5.6, 2.45, 2.55, -2.9, zc=-0.25, n=2.2), st(8.5, 2.35, 2.7, -2.85, zc=-0.3, n=2.4),
         st(11.5, 2.2, 2.85, -2.7, zc=-0.2, n=2.6), st(15.0, 1.95, 3.1, -2.4, zc=0.0, n=2.6),
         st(19.0, 1.55, 2.9, -1.8, zc=0.3, n=2.5), st(23.0, 1.15, 2.5, -1.15, zc=0.5, n=2.3),
         st(27.0, 0.75, 2.1, -0.5, zc=0.7, n=2.2), st(31.0, 0.4, 1.75, 0.1, zc=0.9, n=2.0), st(33.0, 0.2, 1.5, 0.5, zc=1.0, n=2.0)]
    geo.fuselage(M, S, K=16, col=BLUE, nose='cap', tail=P(33.6, 0, 1.0))
    M.F[-17] = (M.F[-17][0], BLACK, False, M.F[-17][3])        # cowl front cap: dark (engine face)
    sp = [geo.ring_pts(P(0.95)[1], 0.85 * U, 0.85 * U - 0.1 * U, -0.85 * U - 0.1 * U, -0.1 * U, 8, 2.0),
          geo.ring_pts(P(0.35)[1], 0.5 * U, 0.4 * U, -0.6 * U, -0.1 * U, 8, 2.0)]
    geo.loft(M, sp, BLUE, True, None, P(-0.45, 0, -0.1))
    # chin intake (dark) under the cowl lip
    geo.prism(M, [(-1.0 * U, -2.3 * U), (1.0 * U, -2.3 * U), (0.8 * U, -2.75 * U), (-0.8 * U, -2.75 * U)], 1, P(0.85)[1], P(1.0)[1], BLACK)
    # framed canopy: flat windscreen at 11 ft, sliding hood to 15.5 ft (top z 3.95), blends into the turtledeck
    C = [st(10.6, 1.05, 2.9, 2.4, zc=2.4, n=2.0), st(11.5, 1.35, 4.15, 2.4, zc=2.4, n=2.6), st(13.2, 1.4, 4.35, 2.4, zc=2.4, n=2.6),
         st(15.0, 1.25, 4.15, 2.4, zc=2.4, n=2.6), st(16.4, 0.9, 3.35, 2.4, zc=2.4, n=2.4)]
    rings = [geo.ring_pts(s['y'], s['w'], s['zt'], s['zb'], s['zc'], 12, s['n']) for s in C]
    rings = [[p for p in r[:4]] + [r[4]] + [r[8]] + [p for p in r[9:]] for r in rings]
    geo.loft(M, rings, GLASS, False, None, None)
    # exhaust stacks (dark) on the cowl sides, behind the cowl flaps
    for sx in (1, -1):
        geo.prism(M, [(sx * 2.3 * U, -0.9 * U), (sx * 2.55 * U, -0.9 * U), (sx * 2.55 * U, -1.6 * U), (sx * 2.3 * U, -1.6 * U)], 1,
                  P(4.4)[1], P(5.8)[1], EXH)


def wings(M):
    # low-mid wing: flat centre section to 6.5 ft, then 7.5 deg dihedral; square-cut tips
    dz = np.tan(np.radians(7.5))
    def hz(x): return -1.6 + dz * max(0.0, x - 6.5)
    def W(x, le, ch, t): return dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=hz(x) * U, t=t * U)
    geo.surface(M, [W(1.8, 6.6, 9.8, 1.55), W(6.5, 6.8, 9.2, 1.4), W(13.0, 7.6, 7.4, 0.95), W(20.6, 8.7, 5.2, 0.55),
                    W(21.4, 9.0, 4.4, 0.45)], BLUE, smooth=True)
    # horizontal tail (span 15.5 ft) and a big fin
    def Hs(x, le, ch, t): return dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=1.3 * U, t=t * U)
    geo.surface(M, [Hs(0.3, 27.6, 5.2, 0.55), Hs(4.5, 28.3, 4.1, 0.45), Hs(7.3, 29.4, 2.6, 0.3), Hs(7.75, 30.0, 1.6, 0.3)], BLUE)
    def Fv(z, le, ch, t): return dict(s=z * U, le=(S0 - le) * U, chord=ch * U, h=0.0, t=t * U)
    geo.surface(M, [Fv(1.6, 25.6, 7.6, 0.6), Fv(5.0, 28.0, 5.4, 0.5), Fv(7.6, 29.8, 3.6, 0.4), Fv(8.4, 30.8, 2.0, 0.3)],
                BLUE, mirror=False, vertical=True)


def main_gear(sx):
    """leg + fairing door + wheel, pivot at the wing (part origin), down: wheel 5.0 ft below the pivot"""
    M = Mesh()
    L = 5.35 * U; r = 1.35 * U
    geo.strut(M, (0, 0, 0), (0, 0, -L + 0.4 * U), 0.32 * U, GREY)
    geo.plate(M, [(sx * 0.4 * U, 0.9 * U, -0.3 * U), (sx * 0.4 * U, -0.9 * U, -0.3 * U), (sx * 0.4 * U, -0.9 * U, -L + 1.5 * U),
                  (sx * 0.4 * U, 0.9 * U, -L + 1.5 * U)], (sx, 0, 0), BLUE)
    geo.wheel(M, (-sx * 0.35 * U, 0, -L), r, 0.75 * U, TYRE, GREY)
    return M


def tail_gear():
    M = Mesh(); L = 7.8 * U
    geo.strut(M, (0, 0, 0), (0, -0.6 * U, -L + 0.3 * U), 0.25 * U, GREY)
    geo.wheel(M, (0, -0.6 * U, -L), 0.55 * U, 0.4 * U, TYRE, GREY, n=6)
    return M


def build(out):
    os.makedirs(out, exist_ok=True)
    M = Mesh(); body(M); wings(M)
    g = []
    for sx, name in ((1, 'R'), (-1, 'L')):
        g.append(core.Gear(name, main_gear(sx), P(8.6, sx * 5.5, -1.9), field=0x0A, neg=True))
    g.append(core.Gear('T', tail_gear(), P(29.6, 0, -0.2), field=0x0A, neg=False))
    R = 6.55 * U; yp = P(0.6)[1]
    disc = core.Disc('prop', [(R, yp, R), (-R, yp, R), (-R, yp, -R), (R, yp, -R)], (0, 1, 0), props.FRAMES)
    donor = os.path.join(REPO, 'SH', 'ALZ.SH')
    props.make(os.path.join(REPO, 'PIC', '_ALZ.PIC'), os.path.join(out, '_F6FN.PIC'), blades=3)
    core.build(donor, os.path.join(out, 'F6FN.SH'), M, g, [disc], pic_name='_F6FN.PIC',
               smooth_ok=lambda c: c not in (BLACK, GLASS))
    import re
    t = open(os.path.join(REPO, 'PT', 'F8F.PT'), encoding='latin1', newline='').read()
    t = re.sub(r'string "alz\.SH"', 'string "f6fn.SH"', t, flags=re.I)
    t = t.replace('string "F8F"', 'string "F6F"').replace('string "F 8F Bearcat"', 'string "F 6F Hellcat"')
    t = t.replace('string "F8F.PT"', 'string "F6F.PT"')
    open(os.path.join(out, 'F6F.PT'), 'w', encoding='latin1', newline='').write(t)


if __name__ == '__main__':
    build(sys.argv[1])
