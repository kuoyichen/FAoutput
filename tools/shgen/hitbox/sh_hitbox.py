"""Give an aircraft SH per-part hit boxes (F2 collision records) that follow its shape.
usage: python sh_hitbox.py IN.SH OUT.SH [nboxes=14] [lib]   (set FAOUTPUT=repo folder when not run from tools/shgen)

FA tests a bullet first against the SH F2 bbox, then (if the table has records) against each
record box, nearest hit wins; no record hit = miss (FA.EXE 0x42CDB1..0x42CEC3).
Stock aircraft SH have no records, so the whole bbox (wing tip to wing tip, gear to fin top) counts.
This script builds boxes from the drawn faces (swing wings sampled at 5 sweeps, gear up) by greedy
volume-minimising splits, writes a new table (radius, bbox, records flag 0x80 id 0x24, 00 00)
just before the CODE signature and points CODE+0x10 (F2 rel16) at it. The old table stays unused.
Use together with fa_gun_hitbox.py: stock FA.EXE still grows every box by 70 for bullets.
"""
import sys, os, json, struct, subprocess
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from boxes import sample, split
src, dst = sys.argv[1], sys.argv[2]
N = int(sys.argv[3]) if len(sys.argv) > 3 else 14
REPO = os.environ.get('FAOUTPUT', os.path.join(HERE, '../../..'))
lib = sys.argv[4] if len(sys.argv) > 4 else os.path.join(REPO, 'tools/fa_sh_lib.js')

sys.path.insert(0, os.path.join(REPO, 'tools/shgen'))
from sh_subdivide import pe_sections, insert_blocks
SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])
j = json.loads(subprocess.run(['node', os.path.join(HERE, 'sh_tris.cjs'), lib, src], capture_output=True, check=True).stdout)
P = np.vstack([sample(j['tris']), np.array(j['mainVerts'])])
d = bytearray(open(src, 'rb').read()); pe, opt, secs = pe_sections(d)
code = next(s for s in secs if s['name'] == 'CODE'); c = bytearray(d[code['ro']:code['ro'] + code['vs']])
room = min(s['va'] for s in secs if s['va'] > code['va']) - code['va'] - code['vs']
if 18 + 14*N > room:
    N = (room - 18) // 14; print(f'only {room} bytes free in CODE: using {N} boxes')
assert N >= 2, 'no room for hit boxes'
bx = split(P, N)
assert c[0x0E:0x10] == b'\xf2\x00', 'no F2 table'
t = 0x12 + struct.unpack_from('<H', c, 0x10)[0]
radius = struct.unpack_from('<i', c, t)[0]; bb = list(struct.unpack_from('<6h', c, t + 4))
assert not c[t + 0x10] & 0x80, 'this SH already has F2 records'
recs = []
for lo, hi in bx:
    lo = np.floor(lo).astype(int) - 1; hi = np.ceil(hi).astype(int) + 1     # 1 unit margin
    r = [lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]]
    for k in range(3): bb[2*k] = min(bb[2*k], r[2*k]); bb[2*k+1] = max(bb[2*k+1], r[2*k+1])
    recs.append(r)
tbl = struct.pack('<i6h', radius, *bb) + b''.join(bytes([0x80, 0x24]) + struct.pack('<6h', *map(int, r)) for r in recs) + b'\0\0'
sig = bytes(c).find(SIG); assert sig > 0
out = insert_blocks(d, pe, secs, code, c, sig, tbl)
pe2, opt2, secs2 = pe_sections(out); code2 = next(s for s in secs2 if s['name'] == 'CODE')
struct.pack_into('<H', out, code2['ro'] + 0x10, sig - 0x12)
nxt = min(s['va'] for s in secs2 if s['va'] > code2['va'])
assert code2['vs'] <= nxt - code2['va'], 'CODE no longer fits before the next section'
assert len(out) < 65536, f'SH would be {len(out)} bytes; FA needs < 65536'
open(dst, 'wb').write(out)
vb = np.prod([bb[1]-bb[0], bb[3]-bb[2], bb[5]-bb[4]]); vr = sum(np.prod([r[1]-r[0], r[3]-r[2], r[5]-r[4]]) for r in recs)
print(f'{dst}: {len(recs)} boxes ({vr/vb:.0%} of bbox volume), {len(out)} bytes')
for r in recs: print('  x %4d..%4d  up %4d..%4d  fwd %4d..%4d' % tuple(r))
