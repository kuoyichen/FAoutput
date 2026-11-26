#!/usr/bin/env python3
"""Big-jet scale (1.5 units per ft) US support aircraft (mass-upgrade thread, 2026-11-26): VC-25 (AFO.SH),
E-8C JSTARS (JSTRT.SH), E-3 Sentry (AWACS.SH), P-3C Orion (P3C.SH).  Stock fault on the first three: F2 ymin far
below the wheels (VC-25 -52 vs wheels -26, E-3 -38 vs -18, E-8 -32 vs -16), so they floated 7-17 ft in game.
Steps: 3D gear (four-wheel main bogies on the VC-25 / E-8 / E-3, twin-wheel P-3 mains, twin nose wheels) on the ground line, F2 ymin set to it
(707s: gear lengthened to the real ~4.5 ft belly clearance, ground -20).  No afterburners, no stores.
Usage: bigjets.py OUTDIR [AFO JSTRT AWACS P3C]"""
import os, sys, struct, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
import std


def tw(top, gl, r, dx, sr, back=8, fwd=0, quad=None, pair=None):
    x, f, _ = top
    g = dict(top=top, bot=(x, f + fwd, gl + r), wheel=(x, f + fwd, gl + r), r=r, w=(-1, 1), twin=dx, sr=sr,
             braces=[((x, f + fwd, (top[2] + gl) // 2), (x, f + back, top[2]))])
    if quad: g['quad'] = quad
    if pair: g['pair'] = pair
    return g


VAR = {
    'AFO': dict(G=-26, parts={'R': 0x4d32, 'L': 0x5017, 'N': 0x52fc}, c4={'R': 0x2c98, 'L': 0x4517, 'N': 0x2e13},
                gear=lambda gl: {'R': tw((0, -4, 0), gl('R'), 3, 3, 1.3, -18, quad=-9, pair=(19, 10, 1)), 'L': tw((0, -4, 0), gl('L'), 3, 3, 1.3, -18, quad=-9, pair=(-18, 10, 1)),
                                 'N': tw((0, 0, 0), gl('N'), 2, 2, 1.0, 8)}),
    'JSTRT': dict(G=-20, parts={'R': 0x43d5, 'L': 0x44a6, 'N': 0x4577}, c4={'R': 0x26c5, 'L': 0x343b, 'N': 0x35de},
                  gear=lambda gl: {'R': tw((0, 4, 0), gl('R'), 3, 3, 1.2, -10, quad=-8), 'L': tw((0, 4, 0), gl('L'), 3, 3, 1.2, -10, quad=-8),
                                   'N': tw((0, 0, 0), gl('N'), 2, 2, 0.9, 8)}),
    'AWACS': dict(G=-20, stub=True,
                  gear=lambda gl: {'R': tw((9, -22, -10), -20, 3, 3, 1.2, -36, quad=-8), 'L': tw((-9, -22, -10), -20, 3, 3, 1.2, -36, quad=-8),
                                   'N': tw((0, 74, -9), -20, 2, 2, 0.9, 82)}),
    'P3C': dict(G=-31, parts={'R': 0x3347, 'L': 0x3408, 'N': 0x34c9}, c4={'R': 0x293f, 'L': 0x15b6, 'N': 0x1283},
                gear=lambda gl: {'R': tw((0, 0, 0), gl('R'), 4, 3, 1.2, 10), 'L': tw((0, 0, 0), gl('L'), 4, 3, 1.2, 10),
                                 'N': tw((0, 0, 0), gl('N'), 3, 2, 1.0, 8)}),
}


def build(out, sh):
    from sh_inspect import load
    v = VAR[sh]; os.makedirs(out, exist_ok=True)
    src = os.path.join(out, sh + '_y.SH'); shutil.copy(os.path.join(ROOT, 'SH', sh + '.SH'), src); std.set_f2_ymin(src, v['G'])
    c = load(src)[4]
    pos = {k: struct.unpack_from('<3h', c, p + 2)[1] for k, p in v.get('c4', {}).items()}
    gl = lambda k: v['G'] - pos.get(k, 0)
    s, p = std.chain(src, os.path.join(ROOT, 'PIC', '_' + sh + '.PIC'), out, sh, sh, parts=v.get('parts'),
                     gear=v['gear'](gl), stub=v.get('stub'), rm=10, rn=8)
    std.render(s, p, os.path.join(out, 'preview_' + sh + '.png'))


if __name__ == '__main__':
    for sh in (sys.argv[2:] or list(VAR)): build(sys.argv[1], sh)
