#!/usr/bin/env python3
"""F-15C 3D gear: single main wheels (34.5x9.75 in tyre ~ r4 w2) outboard of the oleo, single nose wheel (22x7.75 ~ r3)
on a cantilever axle, forward drag brace (nose gear retracts forward).  Part-local (x, fwd, up); ground at up -16 (main) / -19 (nose)."""
import sys, up_gear as U
spec = dict(
    parts={'R': 0x4973, 'L': 0x47a5, 'N': 0x4a34},
    span_end={'R': 0x4a34, 'L': 0x4866, 'N': 0x4b2c},
    gear={
        'R': dict(top=(-2, 0, 0), bot=(-2, 0, -12), wheel=(1, 0, -12), r=4, w=(-1, 1),
                  braces=[((-2, 0, -6), (-4, -7, 0))]),
        'L': dict(top=(2, 0, 0), bot=(2, 0, -12), wheel=(-1, 0, -12), r=4, w=(-1, 1),
                  braces=[((2, 0, -6), (4, -7, 0))]),
        'N': dict(top=(2, 1, 0), bot=(2, 1, -16), wheel=(0, 1, -16), r=3, w=(-1, 1),
                  braces=[((2, 1, -8), (1, 10, 0))]),
    },
    hub_main=(140, 87, 14), hub_nose=(178, 87, 10), clear=[(122, 58, 196, 117)], strip=(102, 105, 212, 220))
if __name__ == '__main__':
    a = sys.argv[1:] or ['../work/f15/s2.SH', '../work/f15/s2.PIC', '../work/f15/s3.SH', '../work/f15/s3.PIC']
    U.run(*a, spec)
