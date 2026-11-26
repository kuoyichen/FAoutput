#!/usr/bin/env python3
"""P-51D Mustang (new shape, mass-upgrade thread 2026-11-27).  The stock F51.SH is a fictional tip-tank trainer
shape, not a Mustang.  Real: length 32.25 ft, span 37 ft, Merlin inline nose with a pointed spinner, bubble canopy,
belly radiator scoop, 4-blade 11.2 ft prop, inward-retracting main gear (track 11.8 ft), retracting tail wheel,
natural metal overall.
Built in feet from the nose (s aft), x right, z up from the thrust line, 3 SH units per ft.
Usage: p51.py OUTDIR"""
import os, sys, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, HERE)
import numpy as np
import core, geo, props
from mesh import Mesh

U = 3.0                   # SH units per ft
S0 = 10.0                 # ft from the nose to the origin (about the CG)
BLUE, GLASS, BLACK, TYRE, GREY, METAL, EXH = 150, 74, 68, 68, 147, 150, 158   # BLUE = the skin colour (natural metal)


def P(s, x=0.0, z=0.0): return (x * U, (S0 - s) * U, z * U)


def st(s, w, zt, zb, **k):
    d = dict(y=(S0 - s) * U, w=w * U, zt=zt * U, zb=zb * U); d.update({kk: (v * U if kk == 'zc' else v) for kk, v in k.items()}); return d


def body(M):
    S = [st(2.0, 1.05, 1.15, -1.3, zc=-0.1, n=2.0), st(3.2, 1.3, 1.45, -1.75, zc=-0.15, n=2.2), st(6.0, 1.45, 1.7, -2.0, zc=-0.15, n=2.4),
         st(9.0, 1.5, 1.9, -2.1, zc=-0.1, n=2.5), st(12.5, 1.48, 2.05, -2.15, zc=-0.05, n=2.5), st(16.0, 1.32, 1.95, -2.1, zc=0.0, n=2.4),
         st(20.0, 1.05, 1.7, -1.7, zc=0.1, n=2.3), st(24.0, 0.75, 1.45, -1.05, zc=0.25, n=2.2), st(28.0, 0.45, 1.25, -0.35, zc=0.45, n=2.1),
         st(31.5, 0.18, 1.1, 0.3, zc=0.7, n=2.0)]
    geo.fuselage(M, S, K=16, col=BLUE, nose='cap', tail=P(32.25, 0, 0.75))
    # pointed spinner
    sp = [geo.ring_pts(P(2.05)[1], 1.0 * U, 1.0 * U - 0.1 * U, -1.0 * U - 0.1 * U, -0.1 * U, 8, 2.0),
          geo.ring_pts(P(1.0)[1], 0.7 * U, 0.6 * U, -0.8 * U, -0.1 * U, 8, 2.0)]
    geo.loft(M, sp, BLUE, True, None, P(-0.2, 0, -0.1))
    # chin carburettor intake
    geo.prism(M, [(-0.45 * U, -1.6 * U), (0.45 * U, -1.6 * U), (0.35 * U, -2.05 * U), (-0.35 * U, -2.05 * U)], 1, P(3.2)[1], P(5.5)[1], BLUE, cap=BLACK)
    # belly radiator scoop
    B = [st(13.2, 0.85, -1.7, -2.95, zc=-2.3, n=2.2), st(15.5, 0.95, -1.7, -3.05, zc=-2.3, n=2.2), st(18.5, 0.9, -1.6, -2.9, zc=-2.2, n=2.2),
         st(21.0, 0.55, -1.3, -2.1, zc=-1.6, n=2.0)]
    rings = [geo.ring_pts(b['y'], b['w'], b['zt'], b['zb'], b['zc'], 8, b['n']) for b in B]
    geo.loft(M, rings, BLUE, True, 'cap', P(22.0, 0, -1.5))
    M.F[-9] = (M.F[-9][0], BLACK, False, M.F[-9][3])          # scoop mouth: dark
    # bubble canopy
    C = [st(10.2, 0.75, 2.15, 1.75, zc=1.75, n=2.0), st(10.9, 1.05, 3.1, 1.75, zc=1.75, n=2.0), st(12.0, 1.15, 3.55, 1.75, zc=1.75, n=2.0),
         st(13.6, 1.1, 3.5, 1.75, zc=1.75, n=2.0), st(15.2, 0.75, 2.9, 1.75, zc=1.75, n=2.0), st(16.6, 0.3, 2.1, 1.75, zc=1.75, n=2.0)]
    rings = [geo.ring_pts(c['y'], c['w'], c['zt'], c['zb'], c['zc'], 12, c['n']) for c in C]
    rings = [[p for p in r[:4]] + [r[4]] + [r[8]] + [p for p in r[9:]] for r in rings]
    geo.loft(M, rings, GLASS, False, None, None)
    # exhaust stacks along the nose
    for sx in (1, -1):
        geo.prism(M, [(sx * 1.38 * U, 0.35 * U), (sx * 1.6 * U, 0.35 * U), (sx * 1.6 * U, -0.05 * U), (sx * 1.38 * U, -0.05 * U)], 1,
                  P(3.6)[1], P(6.4)[1], EXH)


def wings(M):
    dz = np.tan(np.radians(5.0))
    def W(x, le, ch, t): return dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=(-1.6 + dz * (x - 1.5)) * U, t=t * U)
    geo.surface(M, [W(1.4, 7.3, 8.8, 1.35), W(5.5, 7.8, 7.9, 1.1), W(12.0, 9.0, 6.0, 0.75), W(17.6, 10.2, 4.3, 0.5),
                    W(18.5, 10.9, 3.0, 0.4)], BLUE, smooth=True)
    def Hs(x, le, ch, t): return dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=0.75 * U, t=t * U)
    geo.surface(M, [Hs(0.3, 27.0, 4.6, 0.5), Hs(4.0, 27.7, 3.5, 0.4), Hs(6.2, 28.6, 2.3, 0.3), Hs(6.6, 29.1, 1.5, 0.3)], BLUE)
    def Fv(z, le, ch, t): return dict(s=z * U, le=(S0 - le) * U, chord=ch * U, h=0.0, t=t * U)
    geo.surface(M, [Fv(1.1, 24.0, 7.6, 0.55), Fv(4.0, 27.2, 4.6, 0.45), Fv(6.3, 29.0, 2.9, 0.35), Fv(6.9, 29.8, 1.7, 0.3)],
                BLUE, mirror=False, vertical=True)


def main_gear(sx):
    """leg + fairing door + wheel, pivot at the wing (part origin), down: wheel 5.0 ft below the pivot"""
    M = Mesh()
    L = 4.5 * U; r = 1.2 * U
    geo.strut(M, (0, 0, 0), (0, 0, -L + 0.4 * U), 0.32 * U, GREY)
    geo.plate(M, [(sx * 0.4 * U, 0.9 * U, -0.3 * U), (sx * 0.4 * U, -0.9 * U, -0.3 * U), (sx * 0.4 * U, -0.9 * U, -L + 1.5 * U),
                  (sx * 0.4 * U, 0.9 * U, -L + 1.5 * U)], (sx, 0, 0), BLUE)
    geo.wheel(M, (-sx * 0.35 * U, 0, -L), r, 0.75 * U, TYRE, GREY)
    return M


def tail_gear():
    M = Mesh(); L = 6.4 * U
    geo.strut(M, (0, 0, 0), (0, -0.6 * U, -L + 0.3 * U), 0.25 * U, GREY)
    geo.wheel(M, (0, -0.6 * U, -L), 0.55 * U, 0.4 * U, TYRE, GREY, n=6)
    return M


def build(out):
    os.makedirs(out, exist_ok=True)
    M = Mesh(); body(M); wings(M)
    g = []
    for sx, name in ((1, 'R'), (-1, 'L')):
        g.append(core.Gear(name, main_gear(sx), P(9.0, sx * 5.9, -1.6), field=0x0C, neg=(sx > 0)))
    g.append(core.Gear('T', tail_gear(), P(28.0, 0, -0.4), field=0x0A, neg=False))
    R = 5.6 * U; yp = P(1.9)[1]
    disc = core.Disc('prop', [(R, yp, R), (-R, yp, R), (-R, yp, -R), (R, yp, -R)], (0, 1, 0), props.FRAMES)
    donor = os.path.join(REPO, 'SH', 'F51.SH')
    props.make(os.path.join(REPO, 'PIC', '_F51.PIC'), os.path.join(out, '_P51N.PIC'), blades=4)
    core.build(donor, os.path.join(out, 'P51N.SH'), M, g, [disc], pic_name='_P51N.PIC',
               smooth_ok=lambda c: c not in (BLACK, GLASS))
    import re
    t = open(os.path.join(REPO, 'PT', 'F51.PT'), encoding='latin1', newline='').read()
    t = re.sub(r'string "f51\.SH"', 'string "p51n.SH"', t, flags=re.I)
    open(os.path.join(out, 'F51.PT'), 'w', encoding='latin1', newline='').write(t)


if __name__ == '__main__':
    build(sys.argv[1])
