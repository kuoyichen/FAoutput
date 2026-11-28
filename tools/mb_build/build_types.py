"""Build tools/mb_assets/types.json for the Mission Builder.
types: object type file (OT/NT/PT) -> SH shape name (first string after ':shape').
spots: SH name -> parking points from the SH F2 collision table: named points (flag 0xC0) with ids
0x11, 0x12 and 0x19..0x2C (17, 18, 25..44) = the places FA parks aircraft on runways and carrier decks.
Each spot is [id, x, up, fwd] in feet (x right, fwd = nose of the runway / ship).
usage: python tools/mb_build/build_types.py   (run from the repo root)"""
import os, re, json, glob
from f2dump import f2
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
types = {}
for d in ('OT', 'NT', 'PT'):
    for f in glob.glob(os.path.join(R, d, '*.' + d)):
        s = open(f, 'rb').read().decode('latin1')
        m = re.search(r':shape\s*\n\s*string\s+"([^"]+)"', s)
        if m: types[os.path.basename(f).upper()] = m.group(1).upper().replace('.SH', '')
spots = {}
for f in glob.glob(os.path.join(R, 'SH', '*.SH')):
    try: t = f2(open(f, 'rb').read())
    except Exception: t = None
    if not t: continue
    pts = []
    for r in t[2]:
        fl, i, x0, x1, y0, y1, z0, z1 = r
        if fl & 0xC0 == 0xC0 and (i in (17, 18) or 25 <= i <= 44):
            pts.append([i, (x0 + x1) // 2, y1, (z0 + z1) // 2])
    if pts: spots[os.path.basename(f).upper()[:-3]] = pts
out = {'types': dict(sorted(types.items())), 'spots': dict(sorted(spots.items()))}
open(os.path.join(R, 'tools', 'mb_assets', 'types.json'), 'w').write(json.dumps(out, separators=(',', ':')))
print(len(types), 'types,', len(spots), 'shapes with parking spots:', ' '.join(sorted(spots)))
