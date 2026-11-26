#!/usr/bin/env python3
"""F-101B / RF-101C Voodoo (new shapes, mass-upgrade thread 2026-11-27).  The stock PTs used buc.SH / rf1.SH (a
Blackburn Buccaneer).  Real: 67.4 ft (RF-101C 69.3 ft, long camera nose), span 39.7 ft, 36 deg mid wing with the
intakes in the wing roots, T-tail, two J57s with afterburners side by side, tandem two-seat canopy (B) or single seat (RF).
F-101B ADC grey, RF-101C natural metal.  Tricycle gear: main legs retract inward, nose leg aft.
Built in feet from the nose (s aft), x right, z up from the thrust line, 3 SH units per ft.
Usage: voodoo.py B|RF OUTDIR"""
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, HERE)
import numpy as np
import core, geo, sabre
from mesh import Mesh

U = 3.0; S0 = 34.0
GLASS, BLACK, TYRE, GREY, RADOME, PANEL = 74, 68, 68, 147, 54, 59


def P(s, x=0.0, z=0.0): return (x * U, (S0 - s) * U, z * U)


def st(s, w, zt, zb, **k):
    d = dict(y=(S0 - s) * U, w=w * U, zt=zt * U, zb=zb * U); d.update({kk: (v * U if kk == 'zc' else v) for kk, v in k.items()}); return d


def upper(rings): return [[p for p in r[:4]] + [r[4]] + [r[8]] + [p for p in r[9:]] for r in rings]


def body(M, rf, SK):
    d = 1.9 if rf else 0.0          # the RF nose is ~1.9 ft longer
    if rf:
        N = [st(0.0, 0.3, 0.5, -0.6, zc=0.0, n=2.0), st(2.0, 1.2, 1.2, -1.4, zc=-0.1, n=2.8), st(6.5, 1.85, 1.85, -2.1, zc=-0.1, n=3.0)]
    else:
        N = [st(0.0, 0.08, 0.1, -0.1, zc=0.0, n=2.0), st(2.0, 0.9, 0.9, -0.95, zc=0.0, n=2.0), st(4.6, 1.75, 1.75, -1.9, zc=-0.05, n=2.1)]
    S = N + [st(9.0 + d, 2.3, 2.3, -2.5, zc=-0.1, n=2.3), st(17.0 + d, 2.7, 2.55, -2.8, zc=-0.1, n=2.4), st(25.0 + d, 3.3, 2.6, -2.8, zc=-0.1, n=2.6),
             st(36.0 + d, 3.9, 2.5, -2.6, zc=-0.05, n=2.8), st(50.0 + d, 3.4, 2.3, -2.3, zc=0.0, n=2.8), st(60.0 + d, 3.0, 2.5, -2.0, zc=0.15, n=2.7),
             st(66.8 + d, 2.6, 2.35, -1.75, zc=0.2, n=2.6)]
    geo.fuselage(M, S, K=16, col=SK, nose=None, tail='cap')
    M.F[-1] = (M.F[-1][0], BLACK, False, M.F[-1][3])
    if not rf:        # radome colour on the first two ring bands
        for i in range(32): M.F[i] = (M.F[i][0], RADOME, M.F[i][2], M.F[i][3])
    else:             # camera windows on the nose sides
        for sx in (1, -1):
            geo.plate(M, [P(3.6, sx * 1.62, 0.3), P(5.2, sx * 1.8, 0.3), P(5.2, sx * 1.8, -0.7), P(3.6, sx * 1.62, -0.7)], (sx, 0, 0), BLACK)
    c0 = 11.0 + d
    if rf:
        C = [st(c0, 0.9, 2.8, 2.0, zc=2.0, n=2.0), st(c0 + 1.0, 1.25, 3.6, 2.0, zc=2.0, n=2.4), st(c0 + 3.0, 1.3, 3.85, 2.0, zc=2.0, n=2.6),
             st(c0 + 5.2, 1.1, 3.55, 2.0, zc=2.0, n=2.4), st(c0 + 6.4, 0.8, 3.0, 2.0, zc=2.0, n=2.2)]
    else:
        C = [st(c0, 0.9, 2.8, 2.0, zc=2.0, n=2.0), st(c0 + 1.0, 1.25, 3.6, 2.0, zc=2.0, n=2.4), st(c0 + 3.5, 1.35, 3.95, 2.0, zc=2.0, n=2.6),
             st(c0 + 7.0, 1.35, 3.95, 2.0, zc=2.0, n=2.6), st(c0 + 9.2, 1.1, 3.55, 2.0, zc=2.0, n=2.4), st(c0 + 10.4, 0.8, 3.0, 2.0, zc=2.0, n=2.2)]
    geo.loft(M, upper([geo.ring_pts(c['y'], c['w'], c['zt'], c['zb'], c['zc'], 12, c['n']) for c in C]), GLASS, False, None, None)
    ce = C[-1]['y'] / U
    Sp = [st(S0 - ce - 0.1, 0.8, 3.0, 2.0, zc=2.0, n=2.2), st(40.0 + d, 0.9, 2.85, 2.0, zc=2.0, n=2.2), st(52.0 + d, 0.6, 2.55, 2.0, zc=2.0, n=2.0)]
    geo.loft(M, upper([geo.ring_pts(c['y'], c['w'], c['zt'], c['zb'], c['zc'], 12, c['n']) for c in Sp]), SK, True, None, None)
    geo.plate(M, [P(c0 - 3.0, -0.5, 2.3), P(c0 - 3.0, 0.5, 2.3), P(c0 - 0.05, 0.75, 2.62), P(c0 - 0.05, -0.75, 2.62)], (0, 0.2, 1), PANEL)
    # wing-root intakes
    for sx in (1, -1):
        geo.prism(M, [(P(25.0 + d)[1], 0.5 * U), (P(25.0 + d)[1], -1.25 * U), (P(33.0 + d)[1], -1.0 * U), (P(33.0 + d)[1], 0.2 * U)], 0,
                  sx * 2.6 * U, sx * 4.3 * U, SK((0, 0, 0), (0, 0, 1)))
        geo.plate(M, [P(24.95 + d, sx * 2.9, 0.35), P(24.95 + d, sx * 4.2, 0.35), P(24.95 + d, sx * 4.2, -1.1), P(24.95 + d, sx * 2.9, -1.1)],
                  (0, 1, 0), BLACK)
    return d


def wings(M, d, SK):
    sw = np.tan(np.radians(36.0)); dz = np.tan(np.radians(-1.0))
    def W(x, ch, t): return dict(s=x * U, le=(S0 - (26.0 + d + sw * (x - 3.6))) * U, chord=ch * U, h=(-0.4 + dz * (x - 3.6)) * U, t=t * U)
    geo.surface(M, [W(3.6, 16.5, 1.3), W(11.0, 11.0, 0.85), W(19.2, 6.0, 0.45), W(19.85, 5.2, 0.35)], SK, smooth=True)
    def Fv(z, le, ch, t): return dict(s=z * U, le=(S0 - le - d) * U, chord=ch * U, h=0.0, t=t * U)
    geo.surface(M, [Fv(2.2, 49.0, 14.5, 0.8), Fv(7.0, 53.5, 10.2, 0.65), Fv(13.6, 59.4, 6.6, 0.5)], SK, mirror=False, vertical=True)
    def Hs(x, le, ch, t): return dict(s=x * U, le=(S0 - le - d) * U, chord=ch * U, h=13.5 * U, t=t * U)
    geo.surface(M, [Hs(0.2, 59.0, 7.2, 0.5), Hs(4.5, 61.8, 5.0, 0.4), Hs(9.0, 64.8, 2.8, 0.3)], SK)


def build(kind, out):
    rf = kind == 'RF'; os.makedirs(out, exist_ok=True)
    C1, C2 = (150, 150) if rf else (148, 145)
    def SK(c, n): return C2 if n[2] < -0.4 else C1
    M = Mesh(); d = body(M, rf, SK); wings(M, d, SK)
    G = 7.0; wz = -0.4 - np.tan(np.radians(1.0)) * 3.0
    g = [core.Gear(n, sabre.main_gear(sx, G + wz - 1.15), P(37.0 + d, sx * 6.6, wz), field=0x0C, neg=(sx > 0)) for sx, n in ((1, 'R'), (-1, 'L'))]
    g.append(core.Gear('N', sabre.nose_gear(G - 2.4 - 0.8), P(9.5 + d, 0, -2.4), field=0x0A, neg=True))
    for sx, n in ((1, 'AR'), (-1, 'AL')):
        g.append(core.Gear(n, sabre.flame(), P(67.4 + d, sx * 1.35, 0.2), var='AB', anim=False))
    name = 'RF101N' if rf else 'F101N'
    core.build(os.path.join(REPO, 'SH', 'F86.SH'), os.path.join(out, name + '.SH'), M, g, [], smooth_ok=lambda c: c not in (BLACK, GLASS))
    pt, old = ('RF101C.PT', 'rf1') if rf else ('F101B.PT', 'buc')
    t = open(os.path.join(REPO, 'PT', pt), encoding='latin1', newline='').read()
    t = re.sub(r'string "%s\.SH"' % old, 'string "%s.SH"' % name.lower(), t, flags=re.I)
    open(os.path.join(out, pt), 'w', encoding='latin1', newline='').write(t)


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
