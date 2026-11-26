#!/usr/bin/env python3
"""Twin-engine Navy patrol / ASW aircraft (new shapes, mass-upgrade thread 2026-11-27).  The stock S2/S3/P2 PTs used
s2trk.SH / s3vik.SH / a26in.SH, all the same B-26 Invader geometry.
  S2  S-2E Tracker: 43.5 ft, span 72.6 ft, high wing, two R-1820 radials (3-blade 10.2 ft props), tricycle gear
      retracting aft into the nacelles, retractable radome under the rear fuselage omitted; Light Gull Grey over white.
  S3  S-3B Viking: 53.3 ft, span 68.7 ft, high wing, two TF34 pods under the wings, tall fin, tricycle gear;
      Light Gull Grey over white.
  P2  P-2H Neptune: 91.7 ft (with the MAD boom), span 103.9 ft, mid wing, two R-3350 radials (4-blade 15.2 ft props)
      plus two J34 jet pods outboard, glazed nose, MAD tail boom; Glossy Sea Blue.
Built in feet from the nose (s aft), x right, z up from the fuselage centreline, 3 SH units per ft.
Usage: twin.py S2|S3|P2 OUTDIR"""
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, HERE)
import numpy as np
import core, geo, props
from mesh import Mesh

U = 3.0
GLASS, BLACK, TYRE, GREY, EXH = 74, 68, 68, 147, 158

K = dict(
    S2=dict(S0=18.0, fus=[(0.0, 0.4, 0.6, -0.8, 0.0), (1.5, 2.2, 2.4, -2.6, 0.0), (5.0, 3.0, 3.4, -3.3, 0.1), (12.0, 3.1, 3.6, -3.4, 0.1),
                          (22.0, 2.8, 3.4, -3.0, 0.3), (32.0, 1.8, 2.9, -1.6, 0.6), (40.5, 0.9, 2.5, 0.0, 1.0), (43.0, 0.4, 2.3, 0.8, 1.3)],
            canopy=(4.0, 9.5, 2.6, 3.3, 4.2), wing=dict(h=3.6, root=(13.0, 10.5, 1.8), mid=(14.0, 13.0, 9.0, 1.4), tip=(36.3, 15.5, 5.4, 0.6), dih=4.0),
            tail=dict(h=1.6, root=(34.0, 6.0), tip=(11.0, 37.0, 3.4)), fin=((2.6, 31.0, 10.0), (13.5, 38.0, 4.0)),
            eng=[dict(x=8.2, kind='prop', s=7.5, w=2.3, len=14.0, R=5.1, blades=3)], gear=dict(s=18.0, x=8.2, L=None, nose=5.0, ground=8.6),
            top=148, bot=144),
    S3=dict(S0=24.0, fus=[(0.0, 0.5, 0.8, -0.9, 0.0), (2.0, 2.4, 2.4, -2.8, 0.0), (6.0, 3.3, 3.6, -3.6, 0.0), (14.0, 3.5, 4.0, -3.8, 0.1),
                          (30.0, 3.3, 3.9, -3.5, 0.3), (42.0, 2.0, 3.4, -1.4, 0.8), (50.0, 1.0, 3.0, 0.6, 1.4), (53.0, 0.5, 2.8, 1.6, 1.9)],
            canopy=(5.0, 10.5, 2.8, 3.5, 4.4), wing=dict(h=4.0, root=(17.5, 12.5, 2.0), mid=(14.0, 19.0, 9.0, 1.4), tip=(34.3, 25.0, 4.6, 0.6), dih=2.0),
            tail=dict(h=2.5, root=(43.0, 8.5), tip=(13.0, 48.5, 4.0)), fin=((3.3, 38.5, 13.0), (18.0, 48.0, 5.6)), sweep=15.0,
            eng=[dict(x=8.0, kind='jet', s=15.0, w=2.1, len=11.0)], gear=dict(s=25.0, x=6.0, L=None, nose=6.0, ground=8.2),
            top=148, bot=144),
    P2=dict(S0=36.0, fus=[(0.0, 0.5, 0.8, -1.0, 0.0), (2.5, 2.8, 3.0, -3.2, 0.0), (8.0, 4.0, 4.6, -4.6, 0.1), (20.0, 4.3, 5.0, -5.0, 0.2),
                          (45.0, 4.0, 4.8, -4.5, 0.4), (65.0, 2.4, 4.2, -2.0, 1.0), (79.0, 1.2, 3.4, 0.6, 1.8), (84.0, 0.8, 3.0, 1.6, 2.2)],
            canopy=(11.0, 16.5, 3.6, 4.4, 5.6), wing=dict(h=-0.5, root=(30.0, 15.5, 2.8), mid=(26.0, 33.0, 11.0, 1.9), tip=(51.9, 38.5, 5.6, 0.7), dih=4.0),
            tail=dict(h=2.6, root=(73.0, 10.5), tip=(17.0, 78.0, 5.0)), fin=((4.0, 66.0, 18.0), (21.0, 79.0, 6.5)),
            eng=[dict(x=12.5, kind='prop', s=24.0, w=3.0, len=22.0, R=7.6, blades=4), dict(x=31.0, kind='jet', s=30.0, w=1.6, len=11.0)],
            gear=dict(s=34.0, x=12.5, L=None, nose=8.0, ground=11.0), boom=(84.0, 91.7), glazed=True, top=141, bot=141))


def build(kind, out):
    k = K[kind]; S0 = k['S0']; os.makedirs(out, exist_ok=True)
    def P(s, x=0.0, z=0.0): return (x * U, (S0 - s) * U, z * U)
    def st(s, w, zt, zb, zc, n=2.3): return dict(y=(S0 - s) * U, w=w * U, zt=zt * U, zb=zb * U, zc=zc * U, n=n)
    def SK(c, n): return k['bot'] if n[2] < -0.45 else k['top']
    def upper(rings): return [[p for p in r[:4]] + [r[4]] + [r[8]] + [p for p in r[9:]] for r in rings]
    M = Mesh()
    S = [st(*f) for f in k['fus']]
    geo.fuselage(M, S, K=12, col=SK, nose=None, tail='cap')
    if k.get('glazed'):
        for i in range(12): M.F[i] = (M.F[i][0], GLASS, False, M.F[i][3])
    a, b, z0, z1, z2 = k['canopy']
    C = [st(a, geo.interp(S, P(a)[1], 'w') / U * 0.75, z1, z0, z0, 2.0), st(a + 1.5, geo.interp(S, P(a + 1.5)[1], 'w') / U * 0.85, z2, z0, z0, 2.4),
         st(b - 1.0, geo.interp(S, P(b - 1.0)[1], 'w') / U * 0.85, z2, z0, z0, 2.4), st(b, geo.interp(S, P(b)[1], 'w') / U * 0.6, z1, z0, z0, 2.2)]
    geo.loft(M, upper([geo.ring_pts(c['y'], c['w'], c['zt'], c['zb'], c['zc'], 12, c['n']) for c in C]), GLASS, False, None, None)
    if k.get('boom'):
        s0, s1 = k['boom']
        geo.loft(M, [geo.ring_pts(P(s0 - 0.5)[1], 0.7 * U, 2.6 * U, 1.4 * U, 2.0 * U, 8, 2.0), geo.ring_pts(P(s1 - 1.0)[1], 0.4 * U, 2.4 * U, 1.6 * U, 2.0 * U, 8, 2.0)],
                 SK, True, None, P(s1, 0, 2.0))
    w = k['wing']; dz = np.tan(np.radians(w['dih'])); sw = np.tan(np.radians(k.get('sweep', 0.0)))
    def hz(x): return w['h'] + dz * max(0.0, x - 3.0)
    def W(x, le, ch, t): return dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=hz(x) * U, t=t * U)
    rx = geo.interp(S, P(w['root'][0] + 3)[1], 'w') / U - 0.3
    geo.surface(M, [W(rx, w['root'][0], w['root'][1], w['root'][2]), W(*w['mid']), W(*w['tip'])], SK, smooth=True)
    t = k['tail']
    def Hs(x, le, ch, tt): return dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=t['h'] * U, t=tt * U)
    geo.surface(M, [Hs(0.6, t['root'][0], t['root'][1], 0.8), Hs(t['tip'][0], t['tip'][1], t['tip'][2], 0.4)], SK)
    (z0f, le0, c0), (z1f, le1, c1) = k['fin']
    def Fv(z, le, ch, tt): return dict(s=z * U, le=(S0 - le) * U, chord=ch * U, h=0.0, t=tt * U)
    geo.surface(M, [Fv(z0f, le0, c0, 1.0), Fv(z1f, le1, c1, 0.5)], SK, mirror=False, vertical=True)
    discs, flames = [], []
    for e in k['eng']:
        for sx in (1, -1):
            x = sx * e['x']; hzz = hz(e['x'])
            if e['kind'] == 'prop':
                cz = hzz - 1.4
                N = [st(e['s'], e['w'] * 0.6, cz + e['w'] * 0.6, cz - e['w'] * 0.6, cz, 2.0), st(e['s'] + 1.0, e['w'], cz + e['w'], cz - e['w'], cz, 2.0),
                     st(e['s'] + e['len'] * 0.45, e['w'] * 0.95, hzz + 0.3, cz - e['w'] * 1.05, cz, 2.4), st(e['s'] + e['len'], 0.5, hzz, hzz - 0.6, hzz - 0.3, 2.0)]
                rings = [[(px + x * U, py, pz) for px, py, pz in geo.ring_pts(c['y'], c['w'], c['zt'], c['zb'], c['zc'], 10, c['n'])] for c in N]
                geo.loft(M, rings, SK, True, 'cap', None)
                M.F[-1] = (M.F[-1][0], BLACK, False, M.F[-1][3])
                R = e['R'] * U; x0, yp, zc = x * U, P(e['s'] - 0.6)[1], cz * U
                discs.append((core.Disc('p%d%s' % (len(discs), 'R' if sx > 0 else 'L'), [(x0 + R, yp, zc + R), (x0 - R, yp, zc + R), (x0 - R, yp, zc - R),
                                                                                       (x0 + R, yp, zc - R)], (0, 1, 0), props.FRAMES), e['blades']))
            else:     # jet pod on a pylon
                cz = hzz - 2.4 - e['w']
                N = [st(e['s'], e['w'] * 0.9, cz + e['w'] * 0.9, cz - e['w'] * 0.9, cz, 2.0), st(e['s'] + 1.2, e['w'], cz + e['w'], cz - e['w'], cz, 2.0),
                     st(e['s'] + e['len'] - 2.0, e['w'] * 0.9, cz + e['w'] * 0.9, cz - e['w'] * 0.9, cz, 2.0), st(e['s'] + e['len'], e['w'] * 0.6, cz + e['w'] * 0.6, cz - e['w'] * 0.6, cz, 2.0)]
                rings = [[(px + x * U, py, pz) for px, py, pz in geo.ring_pts(c['y'], c['w'], c['zt'], c['zb'], c['zc'], 10, c['n'])] for c in N]
                geo.loft(M, rings, SK, True, 'cap', 'cap')
                M.F[-1] = (M.F[-1][0], BLACK, False, M.F[-1][3]); M.F[-2] = (M.F[-2][0], BLACK, False, M.F[-2][3])
                geo.prism(M, [(P(e['s'] + 2.0)[1], (hzz - 0.2) * U), (P(e['s'] + e['len'] - 2.5)[1], (hzz - 0.2) * U),
                              (P(e['s'] + e['len'] - 2.5)[1], (cz + e['w'] * 0.8) * U), (P(e['s'] + 3.0)[1], (cz + e['w'] * 0.8) * U)],
                          0, (x - 0.2) * U, (x + 0.2) * U, k['top'])
    gq = k['gear']; G = gq['ground']
    def main_gear(Lf):
        Mg = Mesh(); L = Lf * U
        geo.strut(Mg, (0, 0, 0), (0, 0, -L + 0.3 * U), 0.32 * U, GREY)
        for dx in (-0.55, 0.55): geo.wheel(Mg, (dx * U, 0, -L), 1.35 * U, 0.65 * U, TYRE, GREY)
        return Mg
    def nose_gear(Lf):
        Mg = Mesh(); L = Lf * U
        geo.strut(Mg, (0, 0, 0), (0, 0, -L + 0.2 * U), 0.25 * U, GREY)
        geo.wheel(Mg, (0, 0, -L), 0.95 * U, 0.55 * U, TYRE, GREY)
        return Mg
    # main legs hang from the inner nacelle / wing underside
    e0 = k['eng'][0]; mz = (hz(gq['x']) - 1.4 - e0['w']) if e0['kind'] == 'prop' else hz(gq['x']) - 0.8
    g = [core.Gear(n, main_gear(G + mz - 1.35), P(gq['s'], sx * gq['x'], mz), field=0x0A, neg=True) for sx, n in ((1, 'R'), (-1, 'L'))]
    nz = geo.interp(S, P(gq['nose'])[1], 'zb') / U + 0.3
    g.append(core.Gear('N', nose_gear(G + nz - 0.95), P(gq['nose'], 0, nz), field=0x0A, neg=True))
    name = {'S2': 'S2N', 'S3': 'S3N', 'P2': 'P2N'}[kind]
    donor = os.path.join(REPO, 'SH', 'A47.SH')
    D = [d for d, _ in discs]
    if D:
        props.make(os.path.join(REPO, 'PIC', '_A47.PIC'), os.path.join(out, '_%s.PIC' % name), blades=discs[0][1])
    core.build(donor, os.path.join(out, name + '.SH'), M, g, D, pic_name=('_%s.PIC' % name) if D else None,
               smooth_ok=lambda c: c not in (BLACK, GLASS), grow=0x5000)
    pt, old = {'S2': ('S2.PT', 's2trk'), 'S3': ('S3.PT', 's3vik'), 'P2': ('P2.PT', 'a26in')}[kind]
    tx = open(os.path.join(REPO, 'PT', pt), encoding='latin1', newline='').read()
    tx = re.sub(r'string "%s\.SH"' % old, 'string "%s.SH"' % name.lower(), tx, flags=re.I)
    open(os.path.join(out, pt), 'w', encoding='latin1', newline='').write(tx)


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
