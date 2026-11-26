"""Header layout of a stock SH (CODE offsets): F2 trailer rel, C8 LOD switches, A6 detail skip, E2 texture op,
high-LOD start (first 82 after the header) and end (first lower-LOD target)."""
import struct, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from sh_inspect import load


def parse(path):
    d, pe, secs, code, c = load(path)
    assert c[0x0e:0x10] == b'\xf2\x00'
    H = dict(f2=0x10, trailer=0x12 + struct.unpack_from('<h', c, 0x10)[0], c8=[], a6=None, e2=None)
    p = c.find(b'.asm\0') + 5
    while p < 0x100:
        op = c[p]
        if c[p + 1] != 0: p += 1; continue
        if op == 0xC8: H['c8'].append(p + 6); p += 8
        elif op == 0xA6: H['a6'] = p + 2; p += 6
        elif op == 0xE2: H['e2'] = p; p += 16
        elif op == 0x82: break
        else: p += 2
    H['r0'] = p
    tg = [q + 2 + struct.unpack_from('<h', c, q)[0] for q in H['c8']]
    H['r1'] = min(tg) if tg else None
    H['a6t'] = H['a6'] + 2 + struct.unpack_from('<h', c, H['a6'])[0] if H['a6'] else None
    return H, c


if __name__ == '__main__':
    for p in sys.argv[1:]:
        H, c = parse(p)
        print(os.path.basename(p), {k: (hex(v) if isinstance(v, int) else [hex(x) for x in v] if isinstance(v, list) else v) for k, v in H.items()},
              c[H['r1'] - 4:H['r1'] + 4].hex() if H['r1'] else '')
