#!/usr/bin/env python3
"""New bomb shapes (Kuoyi's symmetric SH/MK82.SH and SH/MK84.SH, 2026-11-21) for the other store-carrying SHs:
the F/A-18 variants (F18C/E/F/T/U, built by f18v_upgrade.py) and the F-14 family (F14, F14J, FIR, FBC).
F18.SH itself was done by f18_bombs.py (F18-26); the shapes come from the same f18_bombs.bomb().

The store slots are found from the file itself: every slot stub `F0 00 68 imm32 E8 rel32` that calls the shared
store routine is followed by an i16 table, one entry per kind (relative to the table), pointing at that kind's
list `C4 ... rel16 00 00`.  So each kind's C4s are repointed, nothing is rebuilt.

  --mode state  (F/A-18 variants; files are 61-64.5 KB with no room to grow): the falling-tank state table
                (per aircraft & 127, 16 B per tank slot, after the fall routine) is cut to aircraft & 63 by one
                byte (`and edx, 0x7f` -> `0x3f`); a tank still falls, and the object pointer kept in each entry
                still guards against two aircraft sharing one entry.  Its upper half is then never written, and
                the new MK-82 and MK-84 parts go there.  MK-84 takes the AIM-54 kind (these jets never carry the
                Phoenix; it was already drawn with the AIM-120 shape): name entry 'AIM-5' -> 'MK-84'.
  --mode f14    (F-14 family, 65024 B, 91 B free): the F-14 carries the AIM-54, so MK-84 takes the AGM kind
                (HARM shape; a Tomcat carries no AGMs): name entry 'AGM-' -> 'MK-84', any AGM then falls to the
                generic AIM-120 shape.  The new MK-84 is written over the HARM part, the new MK-82 over the old
                MK-82 part (both smaller), the rest of each old part zeroed.
Usage: python3 store_bombs.py in.SH out.SH --mode state|f14
"""
import os, re, struct, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sh_subdivide import pe_sections
import f18_bombs as B
import f18_stores as S


def slots(c):
    st = [(m.start(), m.start() + 12 + struct.unpack_from('<i', c, m.start() + 8)[0])
          for m in re.finditer(rb'\xf0\x00\x68....\xe8', bytes(c), re.S)]
    sub = Counter(t for _, t in st).most_common(1)[0][0]
    out = []
    for off, t in st:
        if t != sub: continue
        imm = struct.unpack_from('<I', c, off + 3)[0]
        if imm >> 24: continue                                   # pylon stub (2-entry table)
        out.append(off + 12)                                     # kind table
    return out


def kind_c4(c, tables, kind):
    """C4 addresses of every slot's list for `kind`."""
    r = []
    for tb in tables:
        L = tb + struct.unpack_from('<h', c, tb + 2 * kind)[0]
        assert c[L] == 0xC4 and c[L + 1] == 0, hex(L)
        r.append(L)
    return r


def target(c, i): return i + 16 + struct.unpack_from('<h', c, i + 14)[0]
def retarget(c, i, t): struct.pack_into('<h', c, i + 14, t - (i + 16))


def main(src, dst, mode):
    d = bytearray(open(src, 'rb').read())
    pe, opt, secs = pe_sections(d); code = next(s for s in secs if s['name'] == 'CODE')
    c = bytearray(d[code['ro']:code['ro'] + code['vs']])
    tables = slots(c)
    bomb_c4 = kind_c4(c, tables, S.BOMB)
    old82 = {target(c, i) for i in bomb_c4}; assert len(old82) == 1; old82 = old82.pop()
    HDR = bytes(c[old82 - 6:old82])
    mk82 = B.part(*B.bomb('MK82.SH'), HDR)
    mk84 = B.part(*B.bomb('MK84.SH'), HDR)
    allc4 = [i for i in range(len(c) - 16) if c[i] == 0xC4 and c[i + 1] == 0 and 0 <= target(c, i) < len(c) - 2]
    users = lambda t: [i for i in allc4 if target(c, i) == t]

    def part_len(t):                                         # up to the next part's header
        nxt = min(x for x in {target(c, i) for i in allc4} if x > t)
        return nxt - 6 - (t - 6)

    if mode == 'state':
        k84 = S.AIM54
        m = [x.start() for x in re.finditer(rb'\x83\xe2\x7f\x6b\xd2', bytes(c))]; assert len(m) == 1, m
        h = [x.start() for x in re.finditer(rb'\xe8\x00\x00\x00\x00\x5e\x81\xc6', bytes(c))]; assert len(h) == 1
        nk = c[m[0] + 5]
        state = h[0] + 5 + struct.unpack_from('<i', c, h[0] + 8)[0]          # HERE + STATEOFF
        size = 128 * nk * 16
        assert not any(c[state:state + size]), 'state table not zero'
        c[m[0] + 2] = 0x3F
        free = state + size // 2
        free += free % 2
        blob = mk82 + mk84
        assert len(blob) <= size // 2, (len(blob), size // 2)
        c[free:free + len(blob)] = blob
        new82, new84 = free + 6, free + len(mk82) + 6
        name_old, name_new = b'AIM-5\x08', b'MK-84\x08'
        print(f'state table {state:#x} ({nk} slots x 128) -> x 64; parts at {free:#x}: MK82 {len(mk82)} B, MK84 {len(mk84)} B, '
              f'{size // 2 - len(blob)} B left')
    else:
        k84 = S.ARM
        harm = {target(c, i) for i in kind_c4(c, tables, S.ARM)}; assert len(harm) == 1; harm = harm.pop()
        for t, b in ((old82, mk82), (harm, mk84)):
            n = part_len(t); assert len(b) <= n, (len(b), n)
            assert set(users(t)) <= set(kind_c4(c, tables, S.BOMB if t == old82 else S.ARM)), 'part shared'
            c[t - 6:t - 6 + n] = b + b'\0' * (n - len(b))
            print(f'{t:#x}: {len(b)} of {n} B')
        new82, new84 = old82, harm
        name_old, name_new = b'AGM-\x00\x04', b'MK-84\x04'
    for i in bomb_c4: retarget(c, i, new82)
    for i in kind_c4(c, tables, k84): retarget(c, i, new84)
    k = bytes(c).find(name_old); assert k > 0 and bytes(c).count(name_old) == 1
    c[k:k + 6] = name_new
    d[code['ro']:code['ro'] + code['vs']] = c
    assert len(d) < 65536
    open(dst, 'wb').write(d)
    print(dst, len(d), 'B')


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], a[1], a[a.index('--mode') + 1])
