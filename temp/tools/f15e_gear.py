#!/usr/bin/env python3
"""F-15E / F-15I 3D gear: as the F-15C (f15_gear.py), parts 2 units further aft in the part frame; hub textures go
where the stock main / nose wheel billboards were (only those faces use these PIC areas)."""
import sys, up_gear as U
spec = dict(
    parts={'R': 0x428c, 'L': 0x4120, 'N': 0x434d},
    span_end={'R': 0x433e, 'L': 0x41d2, 'N': 0x4445},
    gear={
        'R': dict(top=(-2, -2, 0), bot=(-2, -2, -12), wheel=(1, -2, -12), r=4, w=(-1, 1),
                  braces=[((-2, -2, -6), (-4, -9, 0))]),
        'L': dict(top=(2, -2, 0), bot=(2, -2, -12), wheel=(-1, -2, -12), r=4, w=(-1, 1),
                  braces=[((2, -2, -6), (4, -9, 0))]),
        'N': dict(top=(2, -1, 0), bot=(2, -1, -16), wheel=(0, -1, -16), r=3, w=(-1, 1),
                  braces=[((2, -1, -8), (1, 8, 0))]),
    },
    hub_main=(202, 125, 14), hub_nose=(132, 165, 10), clear=[(184, 96, 220, 155), (110, 133, 154, 197)],
    strip=(48, 53, 14, 34))
if __name__ == '__main__':
    U.run(*sys.argv[1:5], spec)
