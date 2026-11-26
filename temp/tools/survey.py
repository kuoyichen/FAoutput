#!/usr/bin/env python3
"""Quick look at a stock SH for the mass upgrade: PTs using it, PT stations + thrust, C4 parts, vertex buffers,
flame blocks, stock render.  Usage: survey.py NAME [NAME...]  (writes ../work/survey/NAME.png)"""
import os, re, struct, subprocess, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
from pt_edit import get_hp, get_field
from sh_inspect import load, thunks
from up_gear import part_uvs

def pts_using(name):
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'PT', '*.PT'))):
        if re.search(rb'"' + name.encode() + rb'\.SH"', open(p, 'rb').read(), re.I): out.append(os.path.basename(p)[:-3])
    return out

def layout(p):
    t = open(os.path.join(ROOT, 'PT', p + '.PT'), encoding='latin1').read(); out = []; i = 4
    while True:
        try: h = get_hp(t, i)
        except Exception: break
        m = re.search(r':defaultTypeName%d\s*\n\s*string "([^"]*)"' % i, t)
        if h['flags'] != '$8': out.append((i, h['flags'], h['x'], h['u'], h['f'], h['count'], h['loc'], m.group(1) if m else '-'))
        i += 1
    try: th = (get_field(t, 'PLANE', 73), get_field(t, 'PLANE', 74))
    except Exception: th = None
    return th, out

for name in sys.argv[1:]:
    path = os.path.join(ROOT, 'SH', name + '.SH')
    d, pe, secs, code, c = load(path)
    print(f'== {name}.SH {len(d)} B; textures', sorted(set(m.lower() for m in re.findall(rb'_[A-Za-z0-9]{1,7}', d) if len(m) > 2))[:6])
    print('   vars', sorted(set(thunks(d, secs, code, c).values())))
    for p in pts_using(name):
        th, L = layout(p); print(f'   PT {p} thrust {th}'); [print('      ', r) for r in L]
    tail = c.find(b'\x01\x02\x03\x02\x01\x02\x03\x02\x01')
    for p in [i for i in range(len(c) - 16) if c[i:i + 2] == b'\xc4\x00']:
        t = p + 16 + struct.unpack_from('<h', c, p + 14)[0]
        if 0 <= t < len(c) - 6 and c[t] == 0x82 and c[t + 1] == 0:
            n = struct.unpack_from('<H', c, t + 2)[0]
            V = [struct.unpack_from('<3h', c, t + 6 + 6 * i) for i in range(n)]
            uv, e = part_uvs(c, t)
            print(f'   C4 {p:#x} pos {struct.unpack_from("<3h", c, p + 2)} -> {t:#x} n {n} x{min(v[0] for v in V)}..{max(v[0] for v in V)} f{min(v[1] for v in V)}..{max(v[1] for v in V)} u{min(v[2] for v in V)}..{max(v[2] for v in V)} tex {len(uv)}')
    p = 0
    while p < tail:
        if c[p] == 0x82 and c[p + 1] == 0:
            n, s = struct.unpack_from('<HH', c, p + 2)
            if 20 <= n < 900 and s == 0 and p + 6 + 6 * n <= tail:
                V = [struct.unpack_from('<3h', c, p + 6 + 6 * i) for i in range(n)]
                print(f'   abs 82 {p:#x} n {n} x {max(abs(v[0]) for v in V)} f {min(v[1] for v in V)}..{max(v[1] for v in V)} u {min(v[2] for v in V)}..{max(v[2] for v in V)}')
                p += 6 + 6 * n; continue
        p += 1
    try:
        import f16; print('   flames', [hex(x) for x in f16.flame_parts(path)])
    except Exception as e: print('   flames: none', e)
    os.makedirs(os.path.join(HERE, '..', 'work', 'survey'), exist_ok=True)
    pic = os.path.join(ROOT, 'PIC', '_' + name + '.PIC')
    subprocess.run([sys.executable, '-c', f'''
import sys; sys.path.insert(0, {HERE!r})
import shview as V
V.views({path!r}, {pic if os.path.exists(pic) else None!r}, {os.path.join(HERE, '..', 'work', 'survey', name + '.png')!r}, vars={{'_PLgearPos': 0, '_PLafterBurner': 1}},
        vlist=[(1.5708, 0.0), (0.6, -0.35), (0, 0), (-0.7, 0.45)], W=560, H=340)'''])
