"""F2 ymin vs lowest drawn point (gear down) for SH files: resting height = ground - ymin, so the lowest wheel
point should equal ymin (higher -> floats, lower -> sinks).  Usage: groundchk.py SH..."""
import sys, struct
import shview as V
from sh_inspect import load
for p in sys.argv[1:]:
    c = load(p)[4]; t = 0x12 + struct.unpack_from('<H', c, 0x10)[0]; ymin = struct.unpack_from('<h', c, t + 8)[0]
    s = V.SH(p, {'_PLgearDown': 1, '_PLgearPos': 0})
    F = s.faces(eye=(0, -4000, 0))
    lo = min(v[1] for f in F for v in f['P'])
    print(f'{p}: F2 ymin {ymin}, lowest point {lo:.1f}  ({"OK" if abs(lo - ymin) <= 1.5 else "FLOATS" if lo > ymin else "SINKS"})')
