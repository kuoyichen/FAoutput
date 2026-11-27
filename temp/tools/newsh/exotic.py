#!/usr/bin/env python3
"""Exotic US jets (new shapes, mass-upgrade thread 2026-11-27).  Stock stand-ins: F12 used s71.SH, B70 b70.SH (both
the Aurora delta), F23 f22n.SH (an F-22).
  F12  YF-12A / F-12B: 101.6 ft, span 55.6 ft, chined fuselage, delta wing, two J58 nacelles with inlet spikes and
       fins on top, afterburners, black.
  B70  XB-70A Valkyrie: 189 ft, span 105 ft, slender forebody with canards, big delta wing over a box engine bay with
       six afterburning J93s, twin fins, white.
  F23  YF-23A: 67.4 ft, span 43.6 ft, diamond wing, chined forebody, engine humps above the wing with the intakes
       under it, V-tails (50 deg), two afterburners, grey.
Container: F86.SH (gear + afterburner imports).  Built in feet from the nose (s aft), x right, z up, 3 SH units per ft.
Usage: exotic.py F12|B70|F23 OUTDIR"""
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, HERE)
import numpy as np
import core, geo, sabre
from mesh import Mesh

U = 3.0
GLASS, BLACK, TYRE, GREY = 74, 68, 68, 147


def upper(rings): return [[p for p in r[:4]] + [r[4]] + [r[8]] + [p for p in r[9:]] for r in rings]


def build(kind, out):
    os.makedirs(out, exist_ok=True)
    S0 = {'F12': 55.0, 'B70': 100.0, 'F23': 34.0}[kind]
    def P(s, x=0.0, z=0.0): return (x * U, (S0 - s) * U, z * U)
    def st(s, w, zt, zb, zc=None, n=2.3): return dict(y=(S0 - s) * U, w=w * U, zt=zt * U, zb=zb * U, zc=((zt + zb) / 2 if zc is None else zc) * U, n=n)
    def rl(S, K=12, dx=0.0): return [[(px + dx * U, py, pz) for px, py, pz in geo.ring_pts(c['y'], c['w'], c['zt'], c['zb'], c['zc'], K, c['n'])] for c in S]
    def Wsec(x, le, ch, t, h): return dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=h * U, t=t * U)
    def Fv(z, le, ch, t, x=0.0): return dict(s=z * U, le=(S0 - le) * U, chord=ch * U, h=x * U, t=t * U)
    M = Mesh(); g = []
    if kind == 'F12':
        C = BLACK; col = 64
        S = [st(0.0, 0.1, 0.1, -0.1, 0.0, 2.0), st(8.0, 1.6, 1.3, -1.1, 0.0, 1.5), st(20.0, 3.2, 2.2, -1.9, 0.0, 1.3), st(35.0, 5.2, 2.7, -2.3, 0.0, 1.25),
             st(55.0, 6.0, 2.7, -2.3, 0.0, 1.3), st(80.0, 4.0, 2.4, -2.0, 0.0, 1.5), st(97.0, 1.6, 1.8, -1.4, 0.2, 2.0), st(101.0, 0.6, 1.4, -0.8, 0.3, 2.0)]
        geo.loft(M, rl(S, 16), col, True, None, 'cap')
        Cn = [st(17.0, 0.9, 2.2, 1.6, 1.6, 2.0), st(18.5, 1.25, 3.1, 1.6, 1.6, 2.2), st(23.0, 1.3, 3.2, 1.6, 1.6, 2.4), st(28.0, 0.8, 2.7, 1.8, 1.8, 2.0)]
        geo.loft(M, upper(rl(Cn)), GLASS, False, None, None)
        geo.surface(M, [Wsec(5.0, 42.0, 56.0, 2.2, 0.0), Wsec(13.0, 62.0, 36.0, 1.6, 0.0), Wsec(27.8, 88.0, 7.0, 0.5, 0.0)], col, smooth=True)
        for sx in (1, -1):
            N = [st(36.5, 0.15, 0.15, -0.15, 0.0, 2.0), st(42.0, 1.6, 1.6, -1.6, 0.0, 2.0), st(44.0, 2.7, 2.7, -2.7, 0.0, 2.0), st(46.0, 3.0, 3.0, -3.0, 0.0, 2.0),
                 st(80.0, 3.2, 3.2, -3.2, 0.0, 2.0), st(98.0, 2.6, 2.6, -2.6, 0.0, 2.0)]
            geo.loft(M, rl(N, 12, sx * 13.0), col, True, None, 'cap'); M.F[-1] = (M.F[-1][0], BLACK, False, M.F[-1][3])
            geo.surface(M, [Fv(2.8, 82.0, 14.0, 0.6, sx * 13.0), Fv(13.0, 91.0, 6.0, 0.4, sx * 13.0)], col, mirror=False, vertical=True)
            g.append(core.Gear('A' + 'RL'[sx < 0], sabre.flame(), P(98.3, sx * 13.0, 0.0), var='AB', anim=False))
            g.append(core.Gear('RL'[sx < 0], sabre.main_gear(sx, 9.0 - 2.3 - 1.15), P(62.0, sx * 7.5, -2.3), field=0x0C, neg=(sx > 0)))
        g.append(core.Gear('N', sabre.nose_gear(9.0 - 2.0 - 0.8), P(24.0, 0, -2.0), field=0x0A, neg=True))
        name, pts = 'F12N', [('F12.PT', 's71')]
    elif kind == 'B70':
        col = 144
        S = [st(0.0, 0.1, 0.1, -0.1, 0.0, 2.0), st(10.0, 2.2, 2.0, -2.2, 0.0, 2.0), st(25.0, 3.6, 3.4, -3.6, 0.0, 2.2), st(45.0, 4.2, 4.0, -4.0, 0.0, 2.4),
             st(90.0, 4.2, 4.0, -3.0, 0.0, 2.4), st(150.0, 3.8, 3.6, -2.0, 0.3, 2.2), st(180.0, 3.0, 3.0, -1.2, 0.6, 2.0), st(188.0, 2.0, 2.4, -0.6, 0.8, 2.0)]
        geo.loft(M, rl(S, 10), col, True, None, 'cap')
        Cn = [st(24.0, 2.2, 3.6, 2.6, 2.6, 2.0), st(27.0, 3.0, 5.0, 2.6, 2.6, 2.4), st(34.0, 3.0, 5.2, 2.6, 2.6, 2.4), st(60.0, 1.2, 4.2, 2.6, 2.6, 2.0)]
        geo.loft(M, upper(rl(Cn)), GLASS, False, None, None)
        geo.surface(M, [Wsec(3.5, 48.0, 9.0, 0.8, 1.0), Wsec(14.4, 54.0, 4.5, 0.4, 1.0)], col)          # canards
        geo.surface(M, [Wsec(4.0, 92.0, 96.0, 3.6, 0.0), Wsec(32.0, 140.0, 46.0, 1.8, 0.0), Wsec(52.5, 176.0, 9.0, 0.6, 0.0)], col, smooth=True)
        B = [st(78.0, 6.0, -0.5, -4.0, None, 3.0), st(92.0, 10.5, -0.5, -9.0, None, 4.0), st(170.0, 10.5, -0.5, -8.5, None, 4.0), st(189.0, 10.0, -0.5, -8.5, None, 4.0)]
        geo.loft(M, rl(B, 8), col, True, 'cap', 'cap')
        M.F[-1] = (M.F[-1][0], BLACK, False, M.F[-1][3]); M.F[-2] = (M.F[-2][0], BLACK, False, M.F[-2][3])
        for sx in (1, -1):
            geo.surface(M, [Fv(0.5, 158.0, 28.0, 1.2, sx * 6.5), Fv(15.5, 176.0, 12.0, 0.6, sx * 6.5)], col, mirror=False, vertical=True)
            for i, xx in enumerate((3.5, 8.0)):
                g.append(core.Gear('A%d%s' % (i, 'RL'[sx < 0]), sabre.flame(), P(189.2, sx * xx, -4.8), var='AB', anim=False))
            g.append(core.Gear('RL'[sx < 0], sabre.main_gear(sx, 16.0 - 8.5 - 1.15), P(118.0, sx * 9.0, -8.5), field=0x0A, neg=False))
        g.append(core.Gear('N', sabre.nose_gear(16.0 - 3.6 - 0.8), P(62.0, 0, -3.6), field=0x0A, neg=True))
        name, pts = 'B70N', [('B70.PT', 'b70')]
    else:   # F23
        col = 150
        S = [st(0.0, 0.1, 0.1, -0.1, 0.0, 2.0), st(5.0, 1.6, 1.2, -1.2, 0.0, 1.5), st(12.0, 2.8, 2.0, -1.8, 0.0, 1.4), st(22.0, 3.0, 2.4, -2.0, 0.0, 1.6),
             st(40.0, 2.6, 2.0, -1.8, 0.0, 1.8), st(60.0, 1.8, 1.4, -1.2, 0.0, 2.0), st(64.5, 1.0, 1.0, -0.8, 0.0, 2.0)]
        geo.loft(M, rl(S, 16), col, True, None, 'cap')
        Cn = [st(9.0, 0.9, 2.0, 1.4, 1.4, 2.0), st(10.5, 1.2, 3.1, 1.4, 1.4, 2.2), st(14.0, 1.3, 3.3, 1.4, 1.4, 2.4), st(18.5, 0.8, 2.6, 1.6, 1.6, 2.0)]
        geo.loft(M, upper(rl(Cn)), GLASS, False, None, None)
        geo.surface(M, [Wsec(2.5, 20.0, 40.0, 1.4, 0.0), Wsec(12.0, 28.0, 22.0, 1.0, 0.0), Wsec(21.8, 36.5, 4.5, 0.4, 0.0)], col, smooth=True)
        for sx in (1, -1):
            N = [st(24.0, 2.6, 2.6, 0.3, None, 2.4), st(30.0, 2.8, 3.2, 0.3, None, 2.6), st(56.0, 2.6, 3.0, 0.3, None, 2.6), st(67.0, 2.0, 2.3, 0.3, None, 2.6)]
            geo.loft(M, rl(N, 12, sx * 5.8), col, True, None, 'cap'); M.F[-1] = (M.F[-1][0], BLACK, False, M.F[-1][3])
            I = [st(25.0, 1.8, -0.3, -2.4, None, 3.0), st(36.0, 1.8, -0.3, -2.2, None, 3.0)]
            geo.loft(M, rl(I, 8, sx * 5.8), col, True, 'cap', None); M.F[-1] = (M.F[-1][0], BLACK, False, M.F[-1][3])
            g.append(core.Gear('A' + 'RL'[sx < 0], sabre.flame(), P(67.2, sx * 5.8, 1.6), var='AB', anim=False))
            g.append(core.Gear('RL'[sx < 0], sabre.main_gear(sx, 7.0 - 2.0 - 1.15), P(38.0, sx * 6.0, -2.0), field=0x0C, neg=(sx > 0)))
        dz = np.tan(np.radians(50.0))      # V-tails as a high-dihedral pair
        geo.surface(M, [Wsec(5.8, 52.0, 12.0, 0.6, 2.6), Wsec(5.8 + 9.0 * np.cos(np.radians(50.0)), 58.0, 5.0, 0.4, 2.6 + 9.0 * np.sin(np.radians(50.0)))], col)
        g.append(core.Gear('N', sabre.nose_gear(7.0 - 1.9 - 0.8), P(10.0, 0, -1.9), field=0x0A, neg=True))
        name, pts = 'F23N', [('F23.PT', 'f22n')]
    core.build(os.path.join(REPO, 'SH', 'F86.SH'), os.path.join(out, name + '.SH'), M, g, [], smooth_ok=lambda c: c not in (BLACK, GLASS), grow=0x5000)
    for pt, old in pts:
        t = open(os.path.join(REPO, 'PT', pt), encoding='latin1', newline='').read()
        t = re.sub(r'string "%s\.SH"' % old, 'string "%s.SH"' % name.lower(), t, flags=re.I)
        open(os.path.join(out, pt), 'w', encoding='latin1', newline='').write(t)


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
