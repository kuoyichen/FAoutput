#!/usr/bin/env python3
"""B-1B / B-1A Lancer (B1.SH) upgrade (mass-upgrade thread, 2026-11-26).  Stock shape is to scale (146 ft long).
Weapons are all internal (three bays), so no stores are drawn.  Steps: animated afterburner on the four F101 plumes
(one 32-point block) -> 3D gear: the stock gear is one static block under _PLgearDown (flat billboards); it becomes
gosubs to stub parts: each main gear a four-wheel bogie (two twin-wheel axles on a beam, up_gear quad), twin nose
wheels, all on the F2 ground line.
Usage: b1.py OUTDIR"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
import std

G = -31                                          # F2 ymin


def gear():
    g = {}
    for k, s in (('R', 1), ('L', -1)):
        g[k] = dict(top=(12 * s, 2, -16), bot=(12 * s, 2, G + 5), wheel=(12 * s, 2, G + 5), r=5, w=(-1, 1),
                    twin=3, quad=-11, sr=1.4, braces=[((12 * s, 2, -22), (12 * s, 12, -16))])
    g['N'] = dict(top=(0, 186, -14), bot=(0, 186, G + 3), wheel=(0, 186, G + 3), r=3, w=(-1, 1), twin=2, sr=1.0,
                  braces=[((0, 186, -22), (0, 196, -14))])
    return g


def build(out):
    s, p = std.chain(os.path.join(ROOT, 'SH', 'B1.SH'), os.path.join(ROOT, 'PIC', '_B1.PIC'), out, 'B1', 'B1',
                     gear=gear(), flame=90, stub=True, rm=12, rn=8)
    std.render(s, p, os.path.join(out, 'preview_B1.png'))


if __name__ == '__main__':
    build(sys.argv[1])
