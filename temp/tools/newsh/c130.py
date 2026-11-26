#!/usr/bin/env python3
"""C-130H / MC-130H Hercules (new shapes, mass-upgrade thread 2026-11-27).  The stock C130/MC130/MC130X PTs used
an12a.SH (an Antonov An-12).  Real: length 97.8 ft (MC-130H 99.8 ft with the radome nose), span 132.6 ft, high wing,
four T56s with 4-blade 13.5 ft props, upswept rear fuselage with the ramp, main wheels in side sponsons (drawn while
the gear is down), nose leg retracts forward.  C-130H light grey; MC-130H dark gunship grey.
Donor container A47.SH (AN12A.SH has no _PLgearPos import).
Built in feet from the nose (s aft), x right, z up from the fuselage centreline, 3 SH units per ft.
Usage: c130.py C|MC OUTDIR"""
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, HERE)
import numpy as np
import core, geo, props
from mesh import Mesh

U = 3.0; S0 = 46.0
GLASS, BLACK, TYRE, GREY, EXH = 74, 68, 68, 147, 158
WH = 7.3          # wing reference height


def P(s, x=0.0, z=0.0): return (x * U, (S0 - s) * U, z * U)


def st(s, w, zt, zb, **k):
    d = dict(y=(S0 - s) * U, w=w * U, zt=zt * U, zb=zb * U); d.update({kk: (v * U if kk == 'zc' else v) for kk, v in k.items()}); return d


def upper(rings): return [[p for p in r[:4]] + [r[4]] + [r[8]] + [p for p in r[9:]] for r in rings]


def body(M, mc, SK):
    d = 2.0 if mc else 0.0
    N = ([st(0.0, 0.3, 0.6, -0.8, zc=-0.1, n=2.0), st(1.2, 2.2, 1.8, -2.4, zc=-0.3, n=2.0), st(2.6, 3.6, 3.0, -3.9, zc=-0.4, n=2.1)] if mc else
         [st(0.0, 0.3, 0.4, -0.6, zc=-0.1, n=2.0), st(0.8, 2.0, 1.4, -2.4, zc=-0.4, n=2.0)])
    S = N + [st(3.0 + d, 4.1, 3.8, -4.4, zc=-0.3, n=2.2), st(7.0 + d, 6.2, 6.0, -6.0, zc=0.0, n=2.5), st(14.0 + d, 7.0, 6.8, -6.4, zc=0.0, n=2.7),
             st(36.0 + d, 7.0, 6.8, -6.4, zc=0.0, n=2.7), st(60.0 + d, 7.0, 6.8, -6.4, zc=0.0, n=2.7), st(70.0 + d, 6.4, 6.8, -3.6, zc=1.6, n=2.6), st(82.0 + d, 4.2, 6.6, 1.2, zc=3.8, n=2.4),
             st(92.0 + d, 2.0, 6.3, 4.4, zc=5.4, n=2.2), st(97.6 + d, 0.6, 6.0, 5.2, zc=5.6, n=2.0)]
    geo.fuselage(M, S, K=12, col=SK, nose=None, tail='cap')
    # cockpit glazing band
    C = [st(4.0 + d, 5.0, 5.0, 2.0, zc=2.0, n=2.2), st(5.6 + d, 6.0, 6.0, 2.2, zc=2.2, n=2.4), st(8.0 + d, 6.55, 6.45, 2.4, zc=2.4, n=2.6)]
    geo.loft(M, upper([geo.ring_pts(c['y'], c['w'] + 0.08 * U, c['zt'] + 0.08 * U, c['zb'], c['zc'], 12, c['n']) for c in C]), GLASS, False, None, None)
    # sponsons for the main gear
    for sx in (1, -1):
        Sp = [st(36.0 + d, 0.4, -3.0, -6.0, zc=-4.5, n=2.0), st(40.0 + d, 1.9, -2.6, -7.0, zc=-4.6, n=2.4), st(56.0 + d, 1.9, -2.6, -7.0, zc=-4.6, n=2.4),
              st(61.0 + d, 0.4, -3.0, -6.0, zc=-4.5, n=2.0)]
        rings = [[(px + sx * 6.6 * U, py, pz) for px, py, pz in geo.ring_pts(c['y'], c['w'], c['zt'], c['zb'], c['zc'], 8, c['n'])] for c in Sp]
        geo.loft(M, rings, SK, True, None, None)
    return d


def wings(M, d, SK):
    dz = np.tan(np.radians(2.0))
    def W(x, le, ch, t): return dict(s=x * U, le=(S0 - le - d) * U, chord=ch * U, h=(WH + dz * max(0, x - 7.0)) * U, t=t * U)
    geo.surface(M, [W(3.0, 35.8, 16.4, 2.6), W(24.0, 36.6, 14.2, 2.2), W(64.0, 40.0, 8.6, 1.1), W(66.3, 40.8, 6.4, 0.8)], SK, smooth=True)
    def Hs(x, le, ch, t): return dict(s=x * U, le=(S0 - le - d) * U, chord=ch * U, h=6.4 * U, t=t * U)
    geo.surface(M, [Hs(1.0, 84.0, 13.0, 1.0), Hs(14.0, 86.5, 9.5, 0.75), Hs(25.6, 89.5, 6.0, 0.5), Hs(26.4, 90.4, 4.2, 0.4)], SK)
    def Fv(z, le, ch, t): return dict(s=z * U, le=(S0 - le - d) * U, chord=ch * U, h=0.0, t=t * U)
    geo.surface(M, [Fv(6.0, 73.0, 21.0, 1.3), Fv(14.0, 80.5, 15.0, 1.1), Fv(26.5, 88.0, 9.5, 0.75), Fv(28.6, 89.6, 6.4, 0.55)],
                SK, mirror=False, vertical=True)
    eng = []
    for xa in (16.4, 32.4):
        for sx in (1, -1):
            x = sx * xa; hz = WH + dz * (xa - 7.0)
            S = [st(27.6, 1.2, hz - 0.6, hz - 2.6, zc=hz - 1.6, n=2.0), st(28.6, 1.8, hz + 0.2, hz - 3.4, zc=hz - 1.5, n=2.2),
                 st(33.0, 1.9, hz + 0.5, hz - 3.8, zc=hz - 1.5, n=2.4), st(45.0, 1.6, hz + 0.6, hz - 3.2, zc=hz - 1.3, n=2.3),
                 st(52.0, 0.6, hz + 0.4, hz - 1.0, zc=hz - 0.2, n=2.0)]
            rings = [[(px + x * U, py - d * U, pz) for px, py, pz in geo.ring_pts(c['y'], c['w'], c['zt'], c['zb'], c['zc'], 8, c['n'])] for c in S]
            geo.loft(M, rings, SK, True, 'cap', None)
            M.F[-1] = (M.F[-1][0], BLACK, False, M.F[-1][3])
            eng.append((x, hz - 1.5))
    return eng


def main_gear(sx):
    """tandem wheels under the sponson (drawn while the gear is down)"""
    M = Mesh()
    for dy in (3.5, -3.5):
        geo.strut(M, (0, dy * U, 0), (0, dy * U, -1.8 * U), 0.3 * U, GREY)
        geo.wheel(M, (0, dy * U, -2.3 * U), 1.9 * U, 1.2 * U, TYRE, GREY, n=10)
    return M


def nose_gear():
    M = Mesh(); L = 2.4 * U
    for dx in (-0.55, 0.55):
        geo.wheel(M, (dx * U, 0, -L), 1.2 * U, 0.7 * U, TYRE, GREY)
    geo.strut(M, (0, 0, 0), (0, 0, -L + 0.2 * U), 0.3 * U, GREY)
    return M


def build(kind, out):
    mc = kind == 'MC'; os.makedirs(out, exist_ok=True)
    C1, C2 = (154, 154) if mc else (149, 149)
    def SK(c, n): return C2 if n[2] < -0.5 else C1
    M = Mesh(); d = body(M, mc, SK); eng = wings(M, d, SK)
    g = [core.Gear(n, main_gear(sx), P(48.0 + d, sx * 6.6, -7.0), var='GEARDOWN', anim=False) for sx, n in ((1, 'R'), (-1, 'L'))]
    g.append(core.Gear('N', nose_gear(), P(8.5 + d, 0, -6.0), field=0x0A, neg=False))
    R = 6.75 * U; discs = []
    for i, (x, z) in enumerate(eng):
        x0, yp, zc = x * U, P(27.2 + d)[1], z * U
        discs.append(core.Disc('p%d' % i, [(x0 + R, yp, zc + R), (x0 - R, yp, zc + R), (x0 - R, yp, zc - R), (x0 + R, yp, zc - R)], (0, 1, 0), props.FRAMES))
    name = 'MC130N' if mc else 'C130N'
    props.make(os.path.join(REPO, 'PIC', '_A47.PIC'), os.path.join(out, '_%s.PIC' % name), blades=4)
    core.build(os.path.join(REPO, 'SH', 'A47.SH'), os.path.join(out, name + '.SH'), M, g, discs, pic_name='_%s.PIC' % name,
               smooth_ok=lambda c: c not in (BLACK, GLASS), grow=0x5000)
    for pt in (('MC130.PT', 'MC130X.PT') if mc else ('C130.PT',)):
        t = open(os.path.join(REPO, 'PT', pt), encoding='latin1', newline='').read()
        t = re.sub(r'string "an12a\.SH"', 'string "%s.SH"' % name.lower(), t, flags=re.I)
        open(os.path.join(out, pt), 'w', encoding='latin1', newline='').write(t)


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
