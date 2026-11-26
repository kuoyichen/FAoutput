#!/usr/bin/env python3
"""B-52H/D Stratofortress (B52.SH; B5G.SH for EB-52) upgrade (mass-upgrade thread, 2026-11-26).  Stock shape is to
the big-jet scale (1.5 units per ft: 163 x 185 ft).  The stock gear stopped 14 units (9 ft) above the F2 ground
line, so the bomber floated; the real 40.7 ft height puts the ground at -19.  Steps: 3D gear from the three static
gear blocks (KC-135 method, F2 ymin -28 -> -19): four twin-wheel main trucks side by side in two pairs (front and
rear bays), single-wheel outriggers near the wing tips.  No afterburner; internal bay + pylon stores left as FA
draws them (PT pylon stations are drawn by the stock pylon geometry).
Usage: b52.py OUTDIR [B52|B5G]"""
import os, sys, struct, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
import std

G = -19


def gear():
    g = {}
    for k, x, f in (('R', 9, 39), ('L', -9, 39), ('RB', 9, -32), ('LB', -9, -32)):
        g[k] = dict(top=(x, f, -8), bot=(x, f, G + 4), wheel=(x, f, G + 4), r=4, w=(-1, 1), twin=3, sr=1.2,
                    braces=[((x, f, -12), (x, f + (8 if f > 0 else -8), -8))])
    for k, s in (('OR', 1), ('OL', -1)):
        g[k] = dict(top=(111 * s, -35, 3), bot=(111 * s, -35, G + 2), wheel=(111 * s, -35, G + 2), r=2, w=(-1, 1), sr=0.8)
    return g


def blocks(path):
    from sh_inspect import load, thunks
    d, pe, secs, code, c = load(path); th = thunks(d, secs, code, c)
    gd = struct.pack('<I', 0x1000 + next(k for k, v in th.items() if v == '_PLgearDown'))
    out = []; q = -1
    while True:
        q = c.find(gd, q + 1)
        if q < 0: break
        on = struct.unpack_from('<I', c, q + 8)[0] - 0x1000
        out.append(on + 4 + struct.unpack_from('<h', c, on + 2)[0])
    return out[:3]                                   # LOD0: left outrigger, right outrigger, mains


def build(out, sh='B52'):
    import up_gear
    os.makedirs(out, exist_ok=True)
    src = os.path.join(ROOT, 'SH', sh + '.SH'); pic = os.path.join(ROOT, 'PIC', '_' + sh + '.PIC')
    ol, orr, mains = blocks(src)
    cur = os.path.join(out, sh + '_g0.SH'); shutil.copy(src, cur)
    parts = {}
    parts.update(std.stub_parts(cur, cur, ['R', 'L', 'RB', 'LB'], t=mains))
    parts.update(std.stub_parts(cur, cur, ['OL'], t=ol))
    parts.update(std.stub_parts(cur, cur, ['OR'], t=orr))
    std.set_f2_ymin(cur, G)
    spec = dict(parts=parts, gear=gear(), strip=None, span_end={k: v + 14 for k, v in parts.items()})
    h = up_gear.auto_hubs(cur, pic, parts, rm=12, rn=8); spec.update(hub_main=h['hub_main'], hub_nose=h['hub_nose'], clear=[])
    up_gear.run(cur, pic, os.path.join(out, sh + '.SH'), os.path.join(out, '_' + sh + '.PIC'), spec)
    std.render(os.path.join(out, sh + '.SH'), os.path.join(out, '_' + sh + '.PIC'), os.path.join(out, 'preview_' + sh + '.png'))


if __name__ == '__main__':
    for s in (sys.argv[2:] or ['B52', 'B5G']): build(sys.argv[1], s)
