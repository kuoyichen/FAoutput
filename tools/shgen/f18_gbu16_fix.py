#!/usr/bin/env python3
"""F18-16 -> F18-19: replace the GBU-16 (PAVE.SH) store part in place with the balanced body.
F18-16 turned PAVE's 6 wide x 8 deep diamond body 45 deg -> a tilted, lopsided rhombus that looks flat.
fa_weapons.load(balance=True) makes the body as deep as wide at each station first, so after the same 45 deg
turn it is an even square whose corners line up with the X fins.  Fins, faces and draw order are unchanged.
usage: f18_gbu16_fix.py F18-16.SH F18-19.SH"""
import os, sys, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa_weapons as w
from f18g_growler import faces_bytes, BASE

def pb(V, F):
    b = bytearray(struct.pack('<BBHH', 0x82, 0, len(V), BASE*8))
    for v in V: b += struct.pack('<hhh', *v)
    b += faces_bytes(V, F) + b'\0\0'; return bytes(b + b'\0' * (len(b) % 2))

src, dst = sys.argv[1], sys.argv[2]
d = bytearray(open(src, 'rb').read())
old = pb(*w.load('PAVE.SH', None, roll=45))
i = d.find(old); assert i > 0 and d.find(old, i+1) < 0, 'old GBU part not found once'
V, F = w.load('PAVE.SH', None, roll=45, balance=True)
new = pb(V, F)
seen = set(); k = 0
while len(new) > len(old):          # one more vertex survives the rounding: drop an exact duplicate face (draws nothing new)
    key = lambda g: (g[0], g[1], tuple(g[2]))
    dup = next(j for j, g in enumerate(F) if key(g) in {key(h) for h in F[:j]})
    F = F[:dup] + F[dup+1:]; new = pb(V, F); k += 1
print('dropped', k, 'duplicate face(s)')
assert len(new) <= len(old), (len(new), len(old))
d[i:i+len(old)] = new + b'\0' * (len(old) - len(new))
open(dst, 'wb').write(d)
print(f'GBU part at file {i:#x}: {len(old)} -> {len(new)} B, top {w.LAST_TOP}; md5', hashlib.md5(d).hexdigest())
