#!/usr/bin/env python3
"""Make the FIR / FBC (F-14 colour variants) from the current F14.SH: same file, the colour scheme of the
factory variant (Kuoyi 2026-11-21: FIR.SH / FBC.SH are the F-14 with a different top colour; FIR tan, FBC black).

  * faces (FC) and vertex shades (F6) at the same CODE offset with the same vertex indices as in the
    factory variant take the variant's colour (the new F14.SH keeps every original face it did not replace
    at its original offset)
  * new or moved faces / F6 records use the variant's dominant colour mapping of the factory F-14 colours
    (FIR: 152 -> 91, 155 -> 92; FBC: 152/155/178 -> 159)
  * the texture name `_f14.PIC` in the E2 op becomes `_fir.PIC` / `_fbc.PIC`
Usage: python3 f14_reskin.py F14.SH factory_variant.SH out.SH
"""
import os, struct, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, parse_face

SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])


def code_of(d):
    code = next(s for s in pe_sections(d)[2] if s['name'] == 'CODE')
    return code, bytearray(d[code['ro']:code['ro'] + code['vs']])


def items(c):
    """{offset: ('FC', colour, idx, colour_offset)} and F6 records after every 82 buffer"""
    tail = c.find(SIG); out = {}
    for o in range(tail):
        if c[o] == 0xFC:
            f = parse_face(c, o)
            if f and f['end'] <= tail and f['col'] < 256: out[o] = ('FC', f['col'], tuple(f['idx']), o + 3)
        elif c[o] == 0x82 and c[o + 1] == 0:
            n = struct.unpack_from('<H', c, o + 2)[0]
            if not 0 < n < 900: continue
            p = o + 6 + 6 * n
            while p + 7 <= tail and c[p] == 0xF6:
                out[p] = ('F6', c[p + 3], struct.unpack_from('<H', c, p + 1)[0], p + 3); p += 7
    return out


def main():
    src, var, dst = sys.argv[1:4]
    d = bytearray(open(src, 'rb').read()); v = open(var, 'rb').read()
    code, c = code_of(d); _, cv = code_of(v)
    name = 'fir' if 'FIR' in os.path.basename(var).upper() else 'fbc'
    A, V = items(c), items(cv)
    # dominant mapping from the matched items: factory F-14 colour is unknown here, so learn it from the
    # matched pairs (current F14 colour -> variant colour)
    pairs = Counter((A[o][1], V[o][1]) for o in A if o in V and A[o][0] == V[o][0] and A[o][2] == V[o][2])
    best = {}
    for (a, b), n in pairs.most_common():
        best.setdefault(a, b)
    best = {a: b for a, b in best.items() if a != b}
    nm = nn = 0
    for o, (k, col, idx, co) in A.items():
        if o in V and V[o][0] == k and V[o][2] == idx:
            if c[co] != V[o][1]: c[co] = V[o][1]; nm += 1
        elif col in best:
            c[co] = best[col]; nn += 1
    pic = b'_f14.PIC'; k = c.count(pic) + c.count(b'_F14.PIC')
    c = c.replace(pic, ('_%s.PIC' % name).encode()).replace(b'_F14.PIC', ('_%s.PIC' % name.upper()).encode())
    d[code['ro']:code['ro'] + code['vs']] = c
    open(dst, 'wb').write(d)
    print(f'{dst}: {name} matched recoloured {nm}, mapped {nn} new items with {best}, PIC names {k}; pairs {pairs.most_common(8)}')


if __name__ == '__main__':
    main()
