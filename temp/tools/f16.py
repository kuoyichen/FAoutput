#!/usr/bin/env python3
"""F-16 family upgrade (mass-upgrade thread, 2026-11-26): F16.SH (F16 F16C F16E F16F), F16F.SH (F31F),
F16E.SH (F16G F16U F31E).
Steps: PT (tip launcher on the wing tip, centreline lower) -> stores (wing stations 3/4/5 = PT hp5/6/7 at the real
butt lines 85/120/157 in, which the stock PT already has; tip AIM-9/120) -> animated afterburner -> 3D gear:
main legs slant out from the fuselage with the wheel inboard of the leg foot, single nose wheel on the intake.
Usage: f16.py OUTDIR [F16|F16F|F16E]"""
import os, sys, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
from pt_edit import set_hp

VAR = {'F16': dict(pts=['F16', 'F16C', 'F16E', 'F16F'], parts={'R': 0x4bf4, 'L': 0x49f4, 'N': 0x4e5c}),
       'F16F': dict(pts=['F31F'], parts={'R': 0x48e4, 'L': 0x46e4, 'N': 0x4b2a}),
       'F16E': dict(pts=['F16G', 'F16U', 'F31E'], parts={'R': 0x4f34, 'L': 0x4d58, 'N': 0x5156})}


def make_pt(src, dst):
    t = open(src, encoding='latin1', newline='').read()
    t = set_hp(t, 4, x=0, u=-18, f=0)                # centreline (300-gal tank / ECM pod), belly up -10
    t = set_hp(t, 8, x=51, u=1, f=-12)               # wing-tip LAU-129 rail (stock x 54 hung outside the tip)
    open(dst, 'w', encoding='latin1', newline='').write(t)


def stores_extra(S):
    # file room (F16.SH is 37 KB before stores): AIM-7 / AIM-54 never on an F-16 -> AIM-120 bytes; JDAM drawn with
    # the GBU (Paveway) shape, stored once
    S.SHAPES[S.AIM54] = S.SHAPES[S.AIM7] = S.SHAPES[S.AAM]
    S.SHAPES[S.JDAM] = S.SHAPES[S.LGB]


def gear_spec(sh_path, pic_path, parts):
    import up_gear as U
    # part frame: main gear part at (+-6, up -8, fwd -9), ground at part up -13; nose part at (0, -8, 33)
    g = {'R': dict(top=(0, 4, 0), bot=(6, 4, -10), wheel=(4, 4, -10), r=3, w=(-1, 1), sr=0.7,
                   braces=[((3, 4, -4), (0, 12, 0))]),
         'L': dict(top=(0, 4, 0), bot=(-6, 4, -10), wheel=(-4, 4, -10), r=3, w=(-1, 1), sr=0.7,
                   braces=[((-3, 4, -4), (0, 12, 0))]),
         'N': dict(top=(1, 0, 0), bot=(1, 0, -11), wheel=(0, 0, -11), r=2, w=(-1, 0), sr=0.8,
                   braces=[((1, 0, -6), (0, -7, 0))])}
    spec = dict(parts=parts, gear=g, strip=None)
    spec.update(U.auto_hubs(sh_path, pic_path, parts, rm=12, rn=9))
    spec['clear'] = []                              # already cleared before the afterburner step (build)
    return spec


def flame_part(path):
    """Stock F-16 flame: F0 (cmp _PLafterBurner,1; jne; push on-path) -> 12 00 rel16 -> 12-point cross plume 82."""
    import struct
    from sh_inspect import load, thunks
    d, pe, secs, code, c = load(path)
    ab = next(k for k, v in thunks(d, secs, code, c).items() if v == '_PLafterBurner')
    p = c.find(struct.pack('<I', 0x1000 + ab)) - 5
    assert c[p:p + 2] == b'\xf0\x00' and c[p + 12] == 0x68, hex(p)
    on = struct.unpack_from('<I', c, p + 13)[0] - 0x1000
    assert c[on:on + 2] == b'\x12\x00', hex(on)
    t = on + 4 + struct.unpack_from('<h', c, on + 2)[0]
    assert c[t] == 0x82 and struct.unpack_from('<H', c, t + 2)[0] in (8, 12), hex(t)
    return t


def build(sh, out):
    v = VAR[sh]; os.makedirs(out, exist_ok=True)
    for p in v['pts']:
        make_pt(os.path.join(ROOT, 'PT', p + '.PT'), os.path.join(out, p + '.PT'))
    import up_stores, up_gear
    U = up_gear
    up_stores.run(os.path.join(ROOT, 'SH', sh + '.SH'), os.path.join(out, v['pts'][-1] + '.PT'), os.path.join(out, 's1.SH'), stores_extra)
    import up_ab2
    # the old gear billboards' PIC areas are freed first (they are replaced by the 3D gear), so the flame frames fit
    # even where the stock PIC has no free 41x61 area (F16E)
    pre = U.auto_hubs(os.path.join(out, 's1.SH'), os.path.join(ROOT, 'PIC', '_' + sh + '.PIC'), v['parts'], rm=12, rn=9)['clear']
    from f14_gear import read_pic, put
    pb = bytearray(open(os.path.join(ROOT, 'PIC', '_' + sh + '.PIC'), 'rb').read()); P = read_pic(pb)
    for a in pre:
        for y in range(a[1], a[3] + 1):
            for x in range(a[0], a[2] + 1): put(pb, P, x, y, 255)
    open(os.path.join(out, 's1.PIC'), 'wb').write(pb)
    up_ab2.run(os.path.join(out, 's1.SH'), os.path.join(out, 's1.PIC'), os.path.join(out, 's2.SH'), os.path.join(out, 's2.PIC'),
               old=flame_part(os.path.join(out, 's1.SH')), length=70, ignore=pre)
    up_gear.run(os.path.join(out, 's2.SH'), os.path.join(out, 's2.PIC'), os.path.join(out, 's3.SH'), os.path.join(out, 's3.PIC'), gear_spec(os.path.join(out, 's2.SH'), os.path.join(out, 's2.PIC'), v['parts']))


if __name__ == '__main__':
    build(sys.argv[2] if len(sys.argv) > 2 else 'F16', sys.argv[1])
