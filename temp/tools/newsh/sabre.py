#!/usr/bin/env python3
"""Swept-wing nose-intake jets (new shapes, mass-upgrade thread 2026-11-27); the stock PTs all used f86.SH (a MiG-15/17):
  F   F-86F Sabre: 37.5 ft long, 37.1 ft span, round nose intake, bubble canopy, 35 deg wing, no afterburner.
  D   F-86D/K "Sabre Dog": 40.3 ft, radome above a chin intake, afterburner.
  84F F-84F Thunderstreak: 43.4 ft, 33.6 ft span, oval nose intake, framed canopy, 40 deg wing, taller fin.
All natural metal, tricycle gear (main legs retract inward, nose leg aft).
Built in feet from the nose (s aft), x right, z up from the thrust line, 3 SH units per ft.
Usage: sabre.py KIND OUTDIR"""
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, HERE)
import numpy as np
import core, geo
from mesh import Mesh

U = 3.0
METAL, GLASS, BLACK, TYRE, GREY, RADOME, FLAME, CORE, PANEL = 150, 74, 68, 68, 147, 54, 180, 164, 59
S0 = 17.0


def P(s, x=0.0, z=0.0): return (x * U, (S0 - s) * U, z * U)


def st(s, w, zt, zb, **k):
    d = dict(y=(S0 - s) * U, w=w * U, zt=zt * U, zb=zb * U); d.update({kk: (v * U if kk == 'zc' else v) for kk, v in k.items()}); return d


def upper(rings): return [[p for p in r[:4]] + [r[4]] + [r[8]] + [p for p in r[9:]] for r in rings]


K = dict(
    F=dict(L=37.5, span=18.55, sweep=35.0, wle=12.0, wch=9.5, tch=4.3, dih=3.0, fs=1.0, canopy='bubble', ab=False, radome=False,
           fin=(27.5, 9.0, 8.5, 3.6), tail=(30.0, 5.5, 6.4, 2.6), gear=(16.5, 4.1), nose=4.5, ground=6.3),
    D=dict(L=40.3, span=18.6, sweep=35.0, wle=14.2, wch=9.6, tch=4.3, dih=3.0, fs=1.0, canopy='bubble', ab=True, radome=True,
           fin=(30.0, 9.0, 8.7, 3.6), tail=(32.6, 5.5, 6.4, 2.6), gear=(18.7, 4.1), nose=6.0, ground=6.3),
    **{'84F': dict(L=43.4, span=16.8, sweep=40.0, wle=15.0, wch=10.5, tch=4.0, dih=3.5, fs=1.05, canopy='framed', ab=False, radome=False,
                   fin=(31.5, 10.5, 10.0, 3.8), tail=(35.5, 6.0, 6.8, 2.8), gear=(20.0, 3.9), nose=5.5, ground=6.5),
       '84E': dict(L=38.1, span=18.2, sweep=0.0, wle=13.0, wch=8.6, tch=5.2, dih=3.0, fs=0.95, canopy='framed', ab=False, radome=False,
                   fin=(29.5, 8.0, 8.0, 3.6), tail=(32.5, 5.0, 6.6, 3.2), gear=(17.0, 4.6), nose=5.0, ground=6.3, tsw=8.0, fsw=25.0,
                   tiptank=True),
       '100': dict(L=47.0, span=19.4, sweep=45.0, wle=17.0, wch=12.5, tch=4.0, dih=0.0, fs=1.05, canopy='bubble', ab=True, radome=False,
                   fin=(34.0, 12.0, 10.5, 3.6), tail=(40.5, 7.0, 9.0, 2.6), gear=(24.0, 5.1), nose=6.5, ground=6.6, th=-0.6)})


def body(M, k):
    L = k['L']; f = k['fs']; q = L / 37.5
    def s_(x): return x * q
    if k['radome']:
        S = [st(2.6, 1.6, -0.1, -2.1, zc=-1.1, n=2.2), st(3.6, 1.85, 1.9, -2.3, zc=-0.2, n=2.2)]
    else:
        S = [st(0.0, 1.35 * f, 1.25 * f, -1.45 * f, zc=-0.1, n=2.0), st(1.4, 1.75 * f, 1.8 * f, -1.95 * f, zc=-0.1, n=2.1)]
    S += [st(s_(5.0), 2.1 * f, 2.3 * f, -2.35 * f, zc=-0.05, n=2.2), st(s_(10.0), 2.35 * f, 2.45 * f, -2.55 * f, zc=-0.05, n=2.3),
          st(s_(16.0), 2.45 * f, 2.5 * f, -2.6 * f, zc=-0.05, n=2.3), st(s_(24.0), 2.2 * f, 2.25 * f, -2.25 * f, zc=0.0, n=2.2),
          st(s_(31.0), 1.6 * f, 1.75 * f, -1.6 * f, zc=0.05, n=2.1), st(L - 0.6, 1.25 * f, 1.35 * f, -1.25 * f, zc=0.05, n=2.0)]
    geo.fuselage(M, S, K=16, col=METAL, nose='cap', tail='cap')
    M.F[-1] = (M.F[-1][0], BLACK, False, M.F[-1][3]); M.F[-2] = (M.F[-2][0], BLACK, False, M.F[-2][3])
    if k['radome']:
        R = [st(0.0, 0.05, 0.75, 0.65, zc=0.7, n=2.0), st(1.2, 1.0, 1.55, -0.1, zc=0.7, n=2.0), st(2.7, 1.6, 1.95, -0.5, zc=0.7, n=2.0),
             st(3.8, 1.85, 2.0, -0.6, zc=0.7, n=2.1)]
        geo.loft(M, [geo.ring_pts(r['y'], r['w'], r['zt'], r['zb'], r['zc'], 12, r['n']) for r in R], RADOME, True, P(-0.2, 0, 0.7), None)
    c0 = s_(6.6) if not k['radome'] else s_(7.6)
    if k['canopy'] == 'bubble':
        C = [st(c0, 0.75, 2.6, 1.95, zc=1.95, n=2.0), st(c0 + 0.9, 1.15, 3.45, 1.95, zc=1.95, n=2.0), st(c0 + 2.4, 1.3, 3.85, 1.95, zc=1.95, n=2.0),
             st(c0 + 4.2, 1.2, 3.75, 1.95, zc=1.95, n=2.0), st(c0 + 5.6, 0.75, 3.15, 1.95, zc=1.95, n=2.0), st(c0 + 6.6, 0.3, 2.35, 1.95, zc=1.95, n=2.0)]
    else:
        C = [st(c0, 0.85, 2.7, 2.0, zc=2.0, n=2.0), st(c0 + 1.0, 1.2, 3.5, 2.0, zc=2.0, n=2.4), st(c0 + 2.6, 1.3, 3.75, 2.0, zc=2.0, n=2.6),
             st(c0 + 4.6, 1.2, 3.6, 2.0, zc=2.0, n=2.6), st(c0 + 6.0, 0.95, 3.25, 2.0, zc=2.0, n=2.4)]
        Sp = [st(c0 + 5.9, 0.95, 3.25, 2.0, zc=2.0, n=2.4), st(c0 + 12.0, 0.7, 2.75, 2.0, zc=2.0, n=2.2), st(s_(27.0), 0.4, 2.3, 1.9, zc=1.9, n=2.0)]
        geo.loft(M, upper([geo.ring_pts(c['y'], c['w'], c['zt'], c['zb'], c['zc'], 12, c['n']) for c in Sp]), METAL, True, None, None)
    geo.loft(M, upper([geo.ring_pts(c['y'], c['w'], c['zt'], c['zb'], c['zc'], 12, c['n']) for c in C]), GLASS, False, None, None)
    # anti-glare panel ahead of the windscreen
    geo.plate(M, [P(c0 - 3.0, -0.5, 2.35 * f), P(c0 - 3.0, 0.5, 2.35 * f), P(c0 - 0.05, 0.7, 2.62), P(c0 - 0.05, -0.7, 2.62)], (0, 0.2, 1), PANEL)


def wings(M, k):
    L = k['L']; q = L / 37.5
    dz = np.tan(np.radians(k['dih'])); sw = np.tan(np.radians(k['sweep'])); b = k['span']
    def W(x, ch, t): return dict(s=x * U, le=(S0 - (k['wle'] + sw * (x - 2.3))) * U, chord=ch * U, h=(-1.1 + dz * (x - 2.3)) * U, t=t * U)
    r, tp = k['wch'], k['tch']
    geo.surface(M, [W(2.3, r, 1.15), W(2.3 + 0.45 * (b - 2.3), r + 0.45 * (tp - r), 0.75), W(b - 0.6, tp + 0.4, 0.45), W(b, tp, 0.35)],
                METAL, smooth=True)
    if k.get('tiptank'):       # 230-gal tip tanks
        for sx in (1, -1):
            x = sx * (b + 0.9); le = k['wle'] + sw * (b - 2.3); z = -1.1 + dz * (b - 2.3)
            T = [st(le - 3.2, 0.1, 0.1, -0.1, zc=0), st(le - 1.6, 0.85, 0.85, -0.85, zc=0), st(le + 3.0, 1.05, 1.05, -1.05, zc=0),
                 st(le + 7.0, 0.8, 0.8, -0.8, zc=0), st(le + 9.0, 0.2, 0.2, -0.2, zc=0)]
            rings = [[(px + x * U, py, pz + z * U) for px, py, pz in geo.ring_pts(t['y'], t['w'], t['zt'], t['zb'], t['zc'], 8, 2.0)] for t in T]
            geo.loft(M, rings, METAL, True, P(le - 3.6, x / 1.0, z), P(le + 9.6, x, z))
    tl, tc, tsp, ttc = k['tail']; tsw = np.tan(np.radians(k.get('tsw', k['sweep'])))
    def Hs(x, ch, t): return dict(s=x * U, le=(S0 - (tl + tsw * (x - 1.0))) * U, chord=ch * U, h=k.get('th', 1.4) * U, t=t * U)
    geo.surface(M, [Hs(1.0, tc, 0.5), Hs(tsp, ttc, 0.3)], METAL)
    fl, fc, fh, ftc = k['fin']
    def Fv(z, le, ch, t): return dict(s=z * U, le=(S0 - le) * U, chord=ch * U, h=0.0, t=t * U)
    geo.surface(M, [Fv(1.5, fl, fc, 0.6), Fv(fh * 0.55, fl + (fh * 0.55 - 1.5) * np.tan(np.radians(k.get('fsw', k['sweep'] + 5))), fc * 0.7, 0.45),
                    Fv(fh, fl + (fh - 1.5) * np.tan(np.radians(k.get('fsw', k['sweep'] + 5))), ftc, 0.3)], METAL, mirror=False, vertical=True)


def main_gear(sx, Lf):
    M = Mesh(); L = Lf * U; r = 1.15 * U
    geo.strut(M, (0, 0, 0), (0, 0, -L + 0.3 * U), 0.28 * U, GREY)
    geo.plate(M, [(sx * 0.35 * U, 0.9 * U, -0.2 * U), (sx * 0.35 * U, -0.9 * U, -0.2 * U), (sx * 0.35 * U, -0.9 * U, -L + 1.3 * U),
                  (sx * 0.35 * U, 0.9 * U, -L + 1.3 * U)], (sx, 0, 0), METAL)
    geo.wheel(M, (-sx * 0.3 * U, 0, -L), r, 0.65 * U, TYRE, GREY)
    return M


def nose_gear(Lf):
    M = Mesh(); L = Lf * U
    geo.strut(M, (0, 0, 0), (0, 0, -L + 0.2 * U), 0.22 * U, GREY)
    geo.wheel(M, (0, 0, -L), 0.8 * U, 0.45 * U, TYRE, GREY)
    return M


def flame():
    M = Mesh()
    geo.loft(M, [geo.ring_pts(0.0, 1.2 * U, 1.2 * U, -1.2 * U, 0, 8, 2.0), geo.ring_pts(-2.5 * U, 0.95 * U, 0.95 * U, -0.95 * U, 0, 8, 2.0)],
             FLAME, False, None, (0, -7.5 * U, 0))
    geo.loft(M, [geo.ring_pts(-0.2 * U, 0.65 * U, 0.65 * U, -0.65 * U, 0, 6, 2.0), geo.ring_pts(-1.3 * U, 0.5 * U, 0.5 * U, -0.5 * U, 0, 6, 2.0)],
             CORE, False, None, (0, -4.2 * U, 0))
    return M


OUT = {'F': ('F86N', [('F86F.PT', 'f86')]), 'D': ('F86DN', [('F86D.PT', 'f86'), ('F86K.PT', 'f86')]),
       '84F': ('F84FN', [('F84F.PT', 'f86')]), '84E': ('F84EN', [('F84E.PT', 'f84')]), '100': ('F100N', [('F100D.PT', 'mig21')])}


def build(kind, out):
    k = K[kind]; os.makedirs(out, exist_ok=True)
    M = Mesh(); body(M, k); wings(M, k)
    gs, gx = k['gear']; G = k['ground']
    wz = -1.1 + np.tan(np.radians(k['dih'])) * (gx - 2.3)
    g = [core.Gear(n, main_gear(sx, G + wz - 1.15), P(gs, sx * gx, wz), field=0x0C, neg=(sx > 0)) for sx, n in ((1, 'R'), (-1, 'L'))]
    nz = -2.2 if not k['radome'] else -2.2
    g.append(core.Gear('N', nose_gear(G + nz - 0.8), P(k['nose'], 0, nz), field=0x0A, neg=True))
    if k['ab']: g.append(core.Gear('AB', flame(), P(k['L'] - 0.55, 0, 0.05), var='AB', anim=False))
    name, pts = OUT[kind]
    core.build(os.path.join(REPO, 'SH', 'F86.SH'), os.path.join(out, name + '.SH'), M, g, [], smooth_ok=lambda c: c not in (BLACK, GLASS))
    for pt, old in pts:
        t = open(os.path.join(REPO, 'PT', pt), encoding='latin1', newline='').read()
        t = re.sub(r'string "%s\.SH"' % old, 'string "%s.SH"' % name.lower(), t, flags=re.I)
        open(os.path.join(out, pt), 'w', encoding='latin1', newline='').write(t)


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
