#!/usr/bin/env python3
"""F-5E Tiger II (F5EV.SH: F5E, F5A PTs) and F5EE.SH (F5ED PT) upgrade (mass-upgrade thread, 2026-11-26).
Stock shapes are to scale (48.7 ft long, 29 ft over the tip rails).  Steps: PT stays (centreline, inboard /
outboard pylons, wing-tip AIM-9 rails) -> stores -> animated afterburner (twin J85 plume) -> 3D gear: short main
legs on the fuselage sides with the wheel outboard, single nose wheel on the long nose leg, all on the F2 ground
line.
Usage: f5.py OUTDIR"""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
import std

VAR = {'F5EV': dict(pt='F5E', parts={'R': 0x367a, 'L': 0x36e5, 'N': 0x3750}, c4={'R': 0x298b, 'L': 0x2f11, 'N': 0x2688}),
       'F5EE': dict(pt='F5ED', parts={'R': 0x3981, 'L': 0x39ec, 'N': 0x3a57}, c4={'R': 0x2c60, 'L': 0x3218, 'N': 0x296a})}
GROUND = -18


def stores_extra(S):
    for k in (S.AIM54, S.AIM7, S.AAM, S.JDAM, S.ARM): S.SHAPES[k] = S.SHAPES[S.AIM9]
    S.FALL_SLOTS = {k: i for i, k in enumerate([k for k in ('C4', 'R5', 'L5') if k in S.SLOTS])}


def gear(pos):
    gl = lambda k: GROUND - pos[k]
    m = lambda s, k: dict(top=(0, -1, 0), bot=(0, -1, gl(k) + 3), wheel=(2 * s, -1, gl(k) + 3), r=3, w=(-1, 1), sr=0.8,
                          braces=[((0, -1, gl(k) // 2), (0, -7, 0))])
    return {'R': m(1, 'R'), 'L': m(-1, 'L'),
            'N': dict(top=(0, 0, 0), bot=(0, 0, gl('N') + 2), wheel=(0, 1, gl('N') + 2), r=2, w=(-1, 1), sr=0.7,
                      braces=[((0, 0, gl('N') // 2), (0, -6, 0))])}


def build(out):
    from sh_inspect import load
    for sh, v in VAR.items():
        src = os.path.join(ROOT, 'SH', sh + '.SH'); c = load(src)[4]
        pos = {k: struct.unpack_from('<3h', c, p + 2)[1] for k, p in v['c4'].items()}
        s, p = std.chain(src, os.path.join(ROOT, 'PIC', '_' + sh + '.PIC'), out, sh, sh, pt=os.path.join(ROOT, 'PT', v['pt'] + '.PT'),
                         extra=stores_extra, parts=v['parts'], gear=gear(pos), flame=60)
        std.render(s, p, os.path.join(out, 'preview_' + sh + '.png'))


if __name__ == '__main__':
    build(sys.argv[1])
