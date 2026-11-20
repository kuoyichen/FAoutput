#!/usr/bin/env python3
"""F18-16 -> F18-20: replace the GBU-16 (PAVE.SH) store part in place with the balanced body.
F18-16 turned PAVE's 6 wide x 8 deep diamond body 45 deg -> a tilted, lopsided rhombus that looks flat.
fa_weapons.load(balance=True) makes the body as deep as wide at each station first, so after the same 45 deg
turn it is an even square whose corners line up with the X fins.  Fin faces get both sides, and 06 nodes on the two 45 deg planes draw far fin, body, near fin.
usage: f18_gbu16_fix.py F18-16.SH F18-20.SH"""
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
V, F = w.load('PAVE.SH', None, roll=45, balance=True)       # even body, fins two-sided, grouped
new = struct.pack('<BBHH', 0x82, 0, len(V), BASE*8) + b''.join(struct.pack('<hhh', *v) for v in V)
new += w.xfin_code(V, F, w.LAST_GROUPS, w.LAST_TOP, faces_bytes)
new += b'\0' * (len(new) % 2)
assert len(new) <= len(old), (len(new), len(old))
d[i:i+len(old)] = new + b'\0' * (len(old) - len(new))
open(dst, 'wb').write(d)
print(f'GBU part at file {i:#x}: {len(old)} -> {len(new)} B, top {w.LAST_TOP}; md5', hashlib.md5(d).hexdigest())
