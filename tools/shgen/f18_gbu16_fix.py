"""F18-16 -> F18-18: replace the GBU-16 (PAVE.SH) store part in place.  F18-16 turned the whole PAVE 45 deg,
which laid FA's 6 x 8 diamond body on a flat side (6 x 6, looked flat).  Now only fins/canards turn (X fins),
the body keeps PAVE's own cross-section.  Exact duplicate faces dropped so the part fits its old slot."""
import sys, struct, hashlib
sys.path.insert(0, sys.argv[3])
import fa_weapons as w
from f18g_growler import faces_bytes, BASE
def pb(V, F):
    b = bytearray(struct.pack('<BBHH', 0x82, 0, len(V), BASE*8))
    for v in V: b += struct.pack('<hhh', *v)
    b += faces_bytes(V, F) + b'\0\0'; return b + b'\0' * (len(b) % 2)
src, dst = sys.argv[1], sys.argv[2]
d = bytearray(open(src, 'rb').read())
V, F = w.load('PAVE.SH', None, roll=45)                      # F18-16's part: whole store turned
key = struct.pack('<BBHH', 0x82, 0, len(V), BASE*8) + b''.join(struct.pack('<hhh', *v) for v in V)
i = d.find(key); assert i > 0 and d.find(key, i+1) < 0, 'old GBU part not found once'
hdr = bytes(d[i-6:i]); j = d.find(hdr + b'\x82\x00', i + 6)   # next store part (its extents header + 82)
assert d[j-2:j] == b'\0\0' or d[j-3:j-1] == b'\0\0'
old = bytes(d[i:j])
new = pb(*w.load('PAVE.SH', None, roll=45, fins_only=True))
assert len(new) <= len(old), (len(new), len(old))
d[i:i+len(old)] = new + b'\0' * (len(old) - len(new))
open(dst, 'wb').write(d)
print(f'GBU part at file {i:#x}: {len(old)} -> {len(new)} B, top {w.LAST_TOP}; md5', hashlib.md5(d).hexdigest())
