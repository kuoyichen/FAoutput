#!/usr/bin/env python3
"""US helicopters (new shapes, mass-upgrade thread 2026-11-27).  Stock stand-ins: UH1/UH1B used uh1.SH (a wheeled
Lynx-like heli), CMCHE (OH-58D) uh1.SH, OH6/MD500 gaz.SH (Gazelle), CH53/HH3 sfr.SH (Super Frelon).
  UH1D  UH-1D Huey: 41.9 ft fuselage+boom, 48 ft 2-blade rotor, skids, olive drab.
  UH1B  UH-1B gunship: 39 ft, 44 ft rotor, side-mounted M16 kit (rocket pods + twin M60s), olive drab.
  OH58  OH-58D Kiowa Warrior: 33.8 ft, 35 ft 4-blade rotor, mast-mounted sight ball, skids, side pylons, olive drab.
  OH6   OH-6A Cayuse / MD 500: 23 ft egg-shaped cabin, 26.3 ft 4-blade rotor, skids, olive drab.
  CH53  CH-53D Sea Stallion: 67.2 ft fuselage, 72.3 ft 6-blade rotor, side sponsons, retractable gear drawn fixed, grey.
  HH3   HH-3E Jolly Green Giant: 54.8 ft, 62 ft 5-blade rotor, boat hull, sponsons, SEA camouflage.
Donor container HOKUT.SH (it has the gear imports; the stock heli SHs have none).  Rotors are textured blur discs
(main: normal up; tail: normal sideways), 3 frames as the propellers.
Built in feet from the nose (s aft), x right, z up, 3 SH units per ft.
Usage: heli.py KIND OUTDIR"""
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, HERE)
import numpy as np
import core, geo, props
from mesh import Mesh

U = 3.0
GLASS, BLACK, TYRE, GREY, EXH, OLIVE, DGREY = 74, 68, 68, 147, 158, 106, 152


def upper(rings): return [[p for p in r[:4]] + [r[4]] + [r[8]] + [p for p in r[9:]] for r in rings]


def build(kind, out):
    os.makedirs(out, exist_ok=True)
    S0 = {'UH1D': 12.0, 'UH1B': 11.0, 'OH58': 9.0, 'OH6': 6.0, 'CH53': 25.0, 'HH3': 20.0}[kind]
    def P(s, x=0.0, z=0.0): return (x * U, (S0 - s) * U, z * U)
    def st(s, w, zt, zb, zc=None, n=2.3): return dict(y=(S0 - s) * U, w=w * U, zt=zt * U, zb=zb * U, zc=(zt + zb) / 2 * U if zc is None else zc * U, n=n)
    def lofts(M, S, col, K=12, nose=None, tail=None):
        return geo.loft(M, [geo.ring_pts(c['y'], c['w'], c['zt'], c['zb'], c['zc'], K, c['n']) for c in S], col, True, nose, tail)
    M = Mesh(); discs = []
    camo = None
    if kind == 'HH3':
        def camo(c, n):
            if n[2] < -0.5: return 148
            x, y, z = c[0] / U, c[1] / U, c[2] / U
            v = np.sin(x / 4.0 + y / 6.0) + np.sin(y / 3.8 - z / 3.0 + x / 7.0) * 0.8
            return 86 if v > 0.55 else 108 if v < -0.6 else 105
    SK = camo or {'UH1D': OLIVE, 'UH1B': OLIVE, 'OH58': OLIVE, 'OH6': OLIVE, 'CH53': 150}[kind]
    SKc = SK if not callable(SK) else 105

    def skids(x, z, s0, s1, cross):
        for sx in (1, -1):
            geo.strut(M, P(s0, sx * x, z), P(s1, sx * x, z), 0.22 * U, DGREY, n=6)
            geo.strut(M, P(s0 - 0.8, sx * x, z + 0.6), P(s0, sx * x, z), 0.2 * U, DGREY, n=6)
            for cs, cz in cross: geo.strut(M, P(cs, sx * x, z), P(cs, sx * x * 0.45, cz), 0.18 * U, DGREY, n=6)

    def rotor(s, z, R, blades, name='main'):
        x0, y0, zz = 0.0, P(s)[1], z * U; r = R * U
        discs.append(core.Disc(name, [(x0 + r, y0 + r, zz), (x0 - r, y0 + r, zz), (x0 - r, y0 - r, zz), (x0 + r, y0 - r, zz)], (0, 0, 1), props.FRAMES))
        geo.strut(M, P(s, 0, z - 2.0), P(s, 0, z - 0.1), 0.3 * U, DGREY, n=6)
        geo.prism(M, geo.ngon(0.7 * U, 6, 0, y0), 2, (z - 0.5) * U, (z + 0.15) * U, DGREY)

    def tail_rotor(s, z, R, x):
        y0 = P(s)[1]; zz = z * U; r = R * U; xx = x * U
        discs.append(core.Disc('tail', [(xx, y0 + r, zz + r), (xx, y0 - r, zz + r), (xx, y0 - r, zz - r), (xx, y0 + r, zz - r)], (np.sign(x), 0, 0), props.FRAMES))
        geo.strut(M, P(s, 0, z), P(s, x, z), 0.2 * U, DGREY, n=6)

    if kind in ('UH1D', 'UH1B'):
        k = 1.0 if kind == 'UH1D' else 0.93
        S = [st(0.0, 1.2, 0.6, -1.4, n=2.0), st(1.4, 2.7, 2.3, -2.6, n=2.2), st(4.0, 4.0, 3.0, -3.0, n=2.6), st(13.0 * k, 4.1, 3.0, -3.0, n=2.8),
             st(15.5 * k, 3.5, 3.2, -2.6, n=2.6), st(19.0 * k, 2.0, 2.8, -0.8, n=2.3), st(21.0 * k, 1.3, 2.0, -0.2, n=2.2),
             st(39.5 * k, 0.55, 1.6, 0.5, n=2.0)]
        ids = lofts(M, S, SK, K=12, nose=P(-0.2, 0, -0.5), tail='cap')
        for i in range(12): M.F[i] = (M.F[i][0], GLASS, False, M.F[i][3])          # nose glazing
        for sx in (1, -1):        # cockpit side windows and the cabin door window
            w = 4.15
            geo.prism(M, [(P(2.0)[1], 2.4 * U), (P(5.6)[1], 2.6 * U), (P(5.6)[1], -0.2 * U), (P(2.6)[1], -0.6 * U)], 0, sx * (w - 0.6) * U, sx * w * U, GLASS)
            geo.prism(M, [(P(7.0 * k)[1], 2.2 * U), (P(9.8 * k)[1], 2.2 * U), (P(9.8 * k)[1], 0.4 * U), (P(7.0 * k)[1], 0.4 * U)], 0, sx * (w - 0.5) * U, sx * (w + 0.05) * U, GLASS)
        H = [st(7.0 * k, 1.0, 3.2, 2.8, n=2.0), st(8.5 * k, 2.0, 4.6, 2.8, n=2.4), st(17.0 * k, 1.9, 4.6, 2.6, n=2.4), st(20.0 * k, 1.0, 3.6, 2.2, n=2.0)]
        lofts(M, H, SK, K=12, tail='cap')
        geo.prism(M, geo.ngon(0.8 * U, 8, 0, 4.1 * U), 1, P(20.0 * k)[1], P(20.8 * k)[1], EXH)       # exhaust
        Fv = lambda z, le, ch, t: dict(s=z * U, le=(S0 - le) * U, chord=ch * U, h=0.0, t=t * U)
        geo.surface(M, [Fv(1.3, 36.5 * k, 3.6, 0.6), Fv(5.8, 39.2 * k, 2.6, 0.45)], SK, mirror=False, vertical=True)
        Hs = lambda x, le, ch, t: dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=0.9 * U, t=t * U)
        geo.surface(M, [Hs(0.5, 28.0 * k, 2.4, 0.35), Hs(4.7, 28.4 * k, 1.8, 0.3)], SK)
        skids(4.2, -5.2, 2.5, 15.5 * k, [(5.0, -2.9), (12.0 * k, -2.9)])
        rotor(11.5 * k, 6.8, 24.0 if kind == 'UH1D' else 22.0, 2)
        tail_rotor(39.8 * k, 5.0, 4.25, -0.9)
        if kind == 'UH1B':        # M16 armament: rocket pods + twin M60s on outriggers
            for sx in (1, -1):
                geo.strut(M, P(8.5, sx * 3.8, -1.0), P(8.5, sx * 6.6, -1.0), 0.2 * U, DGREY, n=6)
                rp = [geo.ring_pts(P(6.0)[1], 0.75 * U, -0.3 * U, -1.8 * U, -1.05 * U, 8, 2.0), geo.ring_pts(P(10.5)[1], 0.75 * U, -0.3 * U, -1.8 * U, -1.05 * U, 8, 2.0)]
                geo.loft(M, [[(px + sx * 6.0 * U, py, pz) for px, py, pz in r] for r in rp], DGREY, True, 'cap', 'cap')
                for dz in (-0.2, 0.4):
                    geo.strut(M, P(5.0, sx * 6.9, dz), P(10.0, sx * 6.9, dz), 0.12 * U, BLACK, n=4)
        ground = -5.42
    elif kind == 'OH58':
        S = [st(0.0, 1.0, 0.6, -1.2, n=2.0), st(1.6, 2.3, 2.1, -2.2, n=2.2), st(4.0, 2.6, 2.6, -2.4, n=2.4), st(8.5, 2.5, 2.6, -2.4, n=2.6),
             st(11.0, 1.6, 2.4, -1.0, n=2.3), st(13.0, 0.9, 1.6, 0.0, n=2.0), st(29.5, 0.45, 1.2, 0.4, n=2.0)]
        lofts(M, S, SK, K=12, nose=P(-0.2, 0, -0.4), tail='cap')
        for i in range(24): M.F[i] = (M.F[i][0], GLASS, False, M.F[i][3])
        H = [st(5.0, 0.9, 3.0, 2.4, n=2.0), st(6.2, 1.3, 4.0, 2.4, n=2.4), st(11.5, 1.2, 3.8, 2.2, n=2.4), st(13.5, 0.7, 3.0, 1.8, n=2.0)]
        lofts(M, H, SK, K=12, tail='cap')
        Fv = lambda z, le, ch, t: dict(s=z * U, le=(S0 - le) * U, chord=ch * U, h=0.0, t=t * U)
        geo.surface(M, [Fv(-2.4, 27.6, 2.6, 0.4), Fv(4.6, 28.5, 2.0, 0.35)], SK, mirror=False, vertical=True)
        Hs = lambda x, le, ch, t: dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=0.8 * U, t=t * U)
        geo.surface(M, [Hs(0.4, 22.0, 2.0, 0.3), Hs(3.2, 22.3, 1.6, 0.25)], SK)
        skids(3.3, -4.4, 1.5, 10.5, [(3.0, -2.3), (8.5, -2.3)])
        rotor(7.0, 6.2, 17.5, 4)
        # mast-mounted sight ball
        ms = [geo.ring_pts(P(6.2)[1], 0.05 * U, 8.6 * U, 8.5 * U, 8.55 * U, 8, 2.0), geo.ring_pts(P(6.4)[1], 1.0 * U, 9.4 * U, 7.6 * U, 8.5 * U, 8, 2.0),
              geo.ring_pts(P(7.6)[1], 1.0 * U, 9.4 * U, 7.6 * U, 8.5 * U, 8, 2.0)]
        geo.loft(M, ms, DGREY, True, None, P(8.2, 0, 8.5)); geo.strut(M, P(7.0, 0, 6.3), P(7.0, 0, 7.7), 0.25 * U, DGREY, n=6)
        tail_rotor(28.8, 1.8, 2.75, -0.7)
        for sx in (1, -1):    # universal pylons with a rocket pod / Hellfire pair
            geo.strut(M, P(6.0, sx * 2.4, -0.6), P(6.0, sx * 4.4, -0.6), 0.2 * U, DGREY, n=6)
            rp = [geo.ring_pts(P(4.5)[1], 0.6 * U, -0.8 * U, -2.0 * U, -1.4 * U, 8, 2.0), geo.ring_pts(P(8.0)[1], 0.6 * U, -0.8 * U, -2.0 * U, -1.4 * U, 8, 2.0)]
            geo.loft(M, [[(px + sx * 4.4 * U, py, pz) for px, py, pz in r] for r in rp], DGREY, True, 'cap', 'cap')
        ground = -4.62
    elif kind == 'OH6':
        S = [st(0.0, 0.8, 0.5, -0.8, n=2.0), st(1.0, 2.2, 2.0, -2.0, n=2.0), st(3.0, 2.6, 2.8, -2.3, n=2.0), st(6.0, 2.5, 3.0, -2.2, n=2.0),
             st(8.5, 1.8, 2.6, -1.6, n=2.0), st(10.0, 0.8, 1.6, -0.2, n=2.0), st(22.0, 0.35, 1.0, 0.4, n=2.0)]
        lofts(M, S, SK, K=12, nose=P(-0.2, 0, -0.2), tail='cap')
        for i in range(36): M.F[i] = (M.F[i][0], GLASS if (i % 12) in (0, 1, 2, 3, 8, 9, 10, 11) or i < 12 else M.F[i][1], False, M.F[i][3])
        Fv = lambda z, le, ch, t: dict(s=z * U, le=(S0 - le) * U, chord=ch * U, h=0.0, t=t * U)
        geo.surface(M, [Fv(1.0, 20.0, 2.0, 0.3), Fv(4.0, 21.2, 1.4, 0.25)], SK, mirror=False, vertical=True)
        geo.surface(M, [Fv(0.6, 20.0, 1.8, 0.3), Fv(-2.2, 21.0, 1.2, 0.25)], SK, mirror=False, vertical=True)
        Hs = lambda x, le, ch, t: dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=4.0 * U, t=t * U)
        geo.surface(M, [Hs(0.3, 20.0, 1.6, 0.25), Hs(2.6, 20.4, 1.2, 0.2)], SK)
        skids(2.6, -3.9, 0.8, 8.5, [(2.0, -2.0), (7.0, -1.8)])
        rotor(5.0, 4.6, 13.15, 4)
        geo.strut(M, P(5.0, 0, 2.9), P(5.0, 0, 3.4), 0.9 * U, SK, n=8)
        tail_rotor(21.0, 1.0, 2.15, -0.6)
        ground = -4.12
    else:     # CH53 / HH3
        big = kind == 'CH53'
        L = 67.2 if big else 54.8
        S = ([st(0.0, 1.5, 0.5, -2.0, n=2.0), st(2.0, 4.0, 2.6, -4.0, n=2.2), st(6.0, 5.2, 4.2, -4.8, n=2.6), st(12.0, 5.3, 4.8, -4.9, n=2.8),
              st(38.0, 5.3, 4.8, -4.9, n=2.8), st(46.0, 4.4, 4.8, -2.0, n=2.6), st(54.0, 2.4, 4.6, 1.0, n=2.3), st(64.0, 1.2, 4.4, 2.4, n=2.0)]
             if big else
             [st(0.0, 1.3, 0.4, -1.8, n=2.0), st(2.0, 3.4, 2.2, -3.8, n=2.2), st(6.0, 4.4, 3.8, -4.4, n=2.6), st(12.0, 4.6, 4.4, -4.6, n=2.8),
              st(32.0, 4.6, 4.4, -4.6, n=2.8), st(40.0, 3.6, 4.2, -2.0, n=2.6), st(46.0, 2.0, 4.0, 0.6, n=2.3), st(51.5, 1.0, 3.8, 1.8, n=2.0)])
        lofts(M, S, SK, K=12, nose=P(-0.2, 0, -0.8), tail='cap')
        for i in range(12): M.F[i] = (M.F[i][0], GLASS, False, M.F[i][3])
        H = [st(7.0, 1.5, 5.4, 4.0, n=2.0), st(9.0, 3.2, 7.2, 4.0, n=2.4), st(24.0, 3.2, 7.4, 4.0, n=2.4), st(30.0, 1.8, 6.4, 4.0, n=2.0)]
        lofts(M, H, SK, K=12, tail='cap')
        for sx in (1, -1):      # engine pods on the sides of the transmission housing
            E = [st(8.0, 1.2, 6.4, 4.0, n=2.0), st(9.0, 1.3, 6.6, 3.8, n=2.0), st(17.0, 1.3, 6.6, 3.8, n=2.0), st(19.0, 0.9, 6.2, 4.2, n=2.0)]
            geo.loft(M, [[(px + sx * 4.4 * U, py, pz) for px, py, pz in geo.ring_pts(c['y'], c['w'], c['zt'], c['zb'], c['zc'], 8, 2.0)] for c in E],
                     SKc, True, 'cap', 'cap')
            M.F[-2] = (M.F[-2][0], BLACK, False, M.F[-2][3])
            Sp = [st(16.0, 0.4, -1.4, -4.0, n=2.0), st(18.5, 2.8, -0.8, -4.4, n=2.4), st(28.0, 2.6, -0.8, -4.2, n=2.4), st(32.0, 0.4, -1.6, -3.6, n=2.0)]
            geo.loft(M, [[(px + sx * (5.0 if big else 4.4) * U, py, pz) for px, py, pz in geo.ring_pts(c['y'], c['w'], c['zt'], c['zb'], c['zc'], 8, 2.4)] for c in Sp],
                     SK, True, None, None)
            for s in range(12, 30, 3):
                w = geo.interp(S, P(s)[1], 'w') / U + 0.05
                geo.prism(M, [(P(s)[1], 2.4 * U), (P(s + 1.4)[1], 2.4 * U), (P(s + 1.4)[1], 1.0 * U), (P(s)[1], 1.0 * U)], 0, sx * (w - 0.5) * U, sx * w * U, GLASS)
        Fv = lambda z, le, ch, t: dict(s=z * U, le=(S0 - le) * U, chord=ch * U, h=0.0, t=t * U)
        fl = L - 6.5
        geo.surface(M, [Fv(3.5, fl - 1.5, 6.0, 0.9), Fv(13.0, fl + 2.2, 4.4, 0.6)], SK, mirror=False, vertical=True)
        Hs = lambda x, le, ch, t: dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=(10.5 if big else 5.0) * U, t=t * U)
        if big: geo.surface(M, [Hs(0.5, fl + 1.4, 4.0, 0.5), Hs(8.0, fl + 2.4, 2.8, 0.35)], SK, mirror=False)
        else: geo.surface(M, [Hs(0.5, fl, 3.4, 0.5), Hs(6.0, fl + 0.8, 2.4, 0.35)], SK)
        G = -9.4 if big else -8.4
        for sx in (1, -1):        # main wheels under the sponsons, nose wheels
            mx = (5.4 if big else 4.6)
            geo.strut(M, P(23.0, sx * mx, -3.8), P(23.0, sx * mx, G + 1.3), 0.3 * U, DGREY, n=6)
            for dx in (-0.45, 0.45): geo.wheel(M, P(23.0, sx * mx + dx, G + 1.3), 1.3 * U, 0.7 * U, TYRE, GREY)
        geo.strut(M, P(6.0, 0, -4.0), P(6.0, 0, G + 0.95), 0.25 * U, DGREY, n=6)
        for dx in (-0.4, 0.4): geo.wheel(M, P(6.0, dx, G + 0.95), 0.95 * U, 0.55 * U, TYRE, GREY)
        rotor(16.0, 10.0, 36.15 if big else 31.0, 6 if big else 5)
        tail_rotor(L - 2.2, 12.0 if big else 9.5, 8.0 if big else 5.3, -1.4)
        ground = G
    name = {'UH1D': 'UH1DN', 'UH1B': 'UH1BN', 'OH58': 'OH58N', 'OH6': 'OH6N', 'CH53': 'CH53N', 'HH3': 'HH3N'}[kind]
    blades = {'UH1D': 2, 'UH1B': 2, 'OH58': 4, 'OH6': 4, 'CH53': 6, 'HH3': 5}[kind]
    props.make(os.path.join(REPO, 'PIC', '_HOKUT.PIC'), os.path.join(out, '_%s.PIC' % name), blades=blades)
    core.build(os.path.join(REPO, 'SH', 'HOKUT.SH'), os.path.join(out, name + '.SH'), M, [], discs, pic_name='_%s.PIC' % name,
               smooth_ok=lambda c: c not in (BLACK, GLASS), grow=0x5000, ground=None)
    pts = {'UH1D': [('UH1.PT', 'uh1')], 'UH1B': [('UH1B.PT', 'uh1')], 'OH58': [('CMCHE.PT', 'uh1')], 'OH6': [('OH6.PT', 'gaz'), ('MD500.PT', 'gaz')],
           'CH53': [('CH53.PT', 'sfr')], 'HH3': [('HH3.PT', 'sfr')]}[kind]
    for pt, old in pts:
        tx = open(os.path.join(REPO, 'PT', pt), encoding='latin1', newline='').read()
        tx = re.sub(r'string "%s\.SH"' % old, 'string "%s.SH"' % name.lower(), tx, flags=re.I)
        open(os.path.join(out, pt), 'w', encoding='latin1', newline='').write(tx)


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
