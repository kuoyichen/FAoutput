#!/usr/bin/env python3
"""Redraw the general-purpose bombs on an F18.SH built by f18_stores.py, from Kuoyi's symmetric SH/MK82.SH and
SH/MK84.SH (2026-11-21; FA's factory MK82.SH was lopsided: x -2 / +3 at the same station).

In place, no rebuild (F18.SH carries later binary edits: GBU-16 fix, wing fold, st5 position):
  * MK-82 (kind BOMB) part -> new MK82.SH shape.
  * MK-84 gets its own shape: the AIM-54 kind (an F/A-18 never carries the Phoenix) is reused.  Its name-table
    entry 'AIM-5' becomes 'MK-84' (it is scanned before 'MK-8' -> BOMB), so the routine returns that kind for
    an MK-84 and the AIM-54 falls through to 'AIM-' -> AIM-120 shape.  Its C4 lists now point at the MK84 part.
  * Space: the parts MK82 | SPAR | PHENX | GB27 sit back to back; they are written again in that order
    (MK82 new, SPAR as is, MK84 new in place of PHENX, GB27 with its duplicate vertices merged, lossless)
    and every C4 that targets them is repointed.  File size and section layout do not change.
  * Bomb shapes: vertices with the same coordinates merged, degenerate / duplicate faces dropped; each fin
    (faces in the x = 0 or axis plane) is its bigger face drawn from both sides (fa_weapons.load turned both
    faces of each FA fin pair the same way, so a fin showed from one side only).
Usage: python3 f18_bombs.py in/F18.SH out/F18.SH [--agm65]
--agm65 (Kuoyi 2026-11-21, F18-27): MK-82 and MK-84 look alike, so every MK-8x (and CBU) bomb is drawn as the MK-84
  (name 'MK-8' -> AIM-54 kind, now the MK-84 part) and the old MK-82 part / BOMB kind becomes the AGM-65 Maverick
  (SH/MAVRK.SH; name 'AGM-6' -> BOMB kind, ahead of 'AGM-' -> HARM).
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sh_subdivide import pe_sections
from f18g_growler import faces_bytes, BASE, orient
import fa_weapons as FW


OLD_NAMES = (b'AIM-9\x02AIM-7\x07AIM-5\x08GBU-3\x09AIM-\x00\x03AGM-\x00\x04GBU-\x00\x05MK-8\x00\x06CBU-\x00\x06')
AGM65_NAMES = (b'AIM-9\x02AIM-7\x07MK-8\x00\x08GBU-3\x09AIM-\x00\x03AGM-6\x06AGM-\x00\x04GBU-\x00\x05CBU-\x00\x08')


def dedup(V, F, top):
    """Merge equal vertices; drop degenerate / repeated faces; fins (axis-plane faces) get both sides."""
    m, NV, idx = {}, [], []
    for v in V:
        if v not in m: m[v] = len(NV); NV.append(v)
        idx.append(m[v])
    out, seen, fins = [], set(), {}
    def add(fl, col, r):
        k = min(tuple(r[i:] + r[:i]) for i in range(len(r)))
        if (col, k) not in seen: seen.add((col, k)); out.append((fl, col, r))
    def area(P):
        n = [0, 0, 0]
        for k in range(len(P)):
            p, q = P[k], P[(k + 1) % len(P)]
            n[0] += p[1]*q[2]-p[2]*q[1]; n[1] += p[2]*q[0]-p[0]*q[2]; n[2] += p[0]*q[1]-p[1]*q[0]
        return sum(x * x for x in n) ** .5
    for fl, col, q in F:
        r = []
        for i in q:
            j = idx[i]
            if not r or r[-1] != j: r.append(j)
        while len(r) > 1 and r[0] == r[-1]: r.pop()
        if len(set(r)) < 3 or len(set(r)) != len(r): continue
        P = [NV[i] for i in r]
        if area(P) == 0: continue
        cx = sum(p[0] for p in P) / len(P); cf = sum(p[1] for p in P) / len(P); cu = sum(p[2] for p in P) / len(P) + top
        if all(p[0] == 0 for p in P): key = ('x', cu > 0, cf > 0)
        elif all(p[2] == -top for p in P): key = ('u', cx > 0, cf > 0)
        else: add(fl, col, r); continue
        # FA draws each fin as two overlapping faces of opposite winding (one per side, slightly different
        # outlines from rounding); fa_weapons.load turned both the same way.  Keep the bigger one, both sides.
        # boxes in the fin plane: (fwd, distance from the axis); a face overlapping a kept one by more than half
        # is the other side of the same fin (Maverick: wing and tail fin are separate faces of one group)
        j = 2 if key[0] == 'x' else 0
        bx = (min(p[1] for p in P), max(p[1] for p in P), min(p[j] for p in P), max(p[j] for p in P))
        lst = fins.setdefault(key, [])
        for n, (a, b2, f2) in enumerate(lst):
            iw = min(bx[1], b2[1]) - max(bx[0], b2[0]); ih = min(bx[3], b2[3]) - max(bx[2], b2[2])
            sz = lambda b: (b[1] - b[0]) * (b[3] - b[2])
            if iw > 0 and ih > 0 and iw * ih > .5 * min(sz(bx), sz(b2)):
                if area(P) > a: lst[n] = (area(P), bx, (fl, col, r))
                break
        else: lst.append((area(P), bx, (fl, col, r)))
    for lst in fins.values():
        for a, bx, (fl, col, r) in lst: add(fl, col, r); add(fl, col, r[::-1])
    used = sorted({i for _, _, q in out for i in q}); mm = {v: k for k, v in enumerate(used)}
    return [NV[i] for i in used], [(fl, col, [mm[i] for i in q]) for fl, col, q in out]


def part(V, F, HDR):
    b = bytearray(struct.pack('<BBHH', 0x82, 0, len(V), BASE * 8))
    for v in V: b += struct.pack('<hhh', *v)
    b += faces_bytes(V, F) + b'\0\0'
    return HDR + bytes(b) + b'\0' * (len(b) % 2)


def bomb(name, length=None, centre=False):
    """length: scale to this many units (fwd extent); centre: put the middle of that extent on the attach point."""
    V, F = FW.load(name, length)
    if centre:
        m = round((min(v[1] for v in V) + max(v[1] for v in V)) / 2)
        V = [(x, f - m, u) for x, f, u in V]
    return dedup(V, F, FW.LAST_TOP)


def merge_part(p, end):
    """Lossless: merge duplicate vertices of an existing part (82 buffer + FC faces / 06 nodes / 00 00 runs).
    FC faces keep their size (indices stay u16 above slot 255), so every relative jump inside shifts evenly."""
    n = struct.unpack_from('<H', p, 2)[0]; base = struct.unpack_from('<H', p, 4)[0] // 8
    V = [struct.unpack_from('<hhh', p, 6 + 6 * k) for k in range(n)]
    m, NV, idx = {}, [], []
    for v in V:
        if v not in m: m[v] = len(NV); NV.append(v)
        idx.append(m[v])
    code = bytearray(p[6 + 6 * n:end])
    q = 0
    while q < len(code):
        op = code[q]
        if op == 0 and q + 1 < len(code) and code[q + 1] == 0: q += 2
        elif op == 0x06 and code[q + 1] == 0: q += 18
        elif op == 0xFC:
            fl = struct.unpack_from('<H', code, q + 1)[0]; r = q + 5
            if fl & 0x60: r += 6 + (3 if fl & 0x200 else 6)
            k = code[r]; r += 1
            assert fl & 0x400, 'u8 indices'
            for i in range(k):
                j = struct.unpack_from('<H', code, r + 2 * i)[0] - base
                struct.pack_into('<H', code, r + 2 * i, base + idx[j])
            r += 2 * k
            assert not fl & 4
            q = r
        elif op == 0 and q == len(code) - 1: q += 1          # pad byte
        else: raise ValueError('op %02x at +%x' % (op, q))
    b = bytearray(struct.pack('<BBHH', 0x82, 0, len(NV), base * 8))
    for v in NV: b += struct.pack('<hhh', *v)
    return bytes(b + code)


def main(src, dst, agm65=False):
    d = bytearray(open(src, 'rb').read())
    pe, opt, secs = pe_sections(d); code = next(s for s in secs if s['name'] == 'CODE')
    c = bytearray(d[code['ro']:code['ro'] + code['vs']])
    refs = {}
    for i in range(len(c) - 16):
        if c[i] == 0xC4 and c[i + 1] == 0:
            t = i + 16 + struct.unpack_from('<h', c, i + 14)[0]
            if 0 <= t < len(c) - 2 and c[t] == 0x82 and c[t + 1] == 0: refs.setdefault(t, []).append(i)
    # identify the four parts by their old shapes
    def find(V, F):
        vb = struct.pack('<BBHH', 0x82, 0, len(V), BASE * 8) + b''.join(struct.pack('<hhh', *v) for v in V)
        a = bytes(c).find(vb + faces_bytes(V, F)); assert a > 0 and a in refs; return a
    old_mk82 = os.path.join(HERE, 'data', 'MK82_factory.SH')
    FW.SHDIR = os.path.dirname(old_mk82); a_mk = find(*FW.load(os.path.basename(old_mk82)))
    FW.SHDIR = os.path.join(HERE, '..', '..', 'SH')
    a_sp, a_ph, a_gb = (find(*FW.load(n)) for n in ('SPAR.SH', 'PHENX.SH', 'GB27.SH'))
    order = sorted(refs)
    assert [t for t in order if a_mk <= t <= a_gb] == [a_mk, a_sp, a_ph, a_gb], 'parts not back to back'
    g_end = order[order.index(a_gb) + 1] - 6           # header of the next part
    HDR = bytes(c[a_mk - 6:a_mk])
    lo = a_mk - 6
    first = ('AGM65', part(*bomb('MAVRK.SH'), HDR)) if agm65 else ('MK82', part(*bomb('MK82.SH'), HDR))
    new = [first + ([a_mk],),
           ('SPAR', bytes(c[a_sp - 6:a_ph - 6]), [a_sp]),
           ('MK84', part(*bomb('MK84.SH'), HDR), [a_ph]),
           ('GB27', HDR + merge_part(bytes(c[a_gb:g_end]), g_end - a_gb), [a_gb])]
    blob, at = b'', {}
    for nm, b, olds in new:
        if len(b) % 2: b += b'\0'
        for o in olds: at[o] = lo + len(blob) + 6
        print(f'{nm:5s} {len(b):5d} B at {lo + len(blob) + 6:#x}')
        blob += b
    room = g_end - lo
    print('region', room, 'used', len(blob), 'free', room - len(blob))
    assert len(blob) <= room
    c[lo:g_end] = blob + b'\0' * (room - len(blob))
    for o, srcs in refs.items():
        if o in at:
            for i in srcs: struct.pack_into('<h', c, i + 14, at[o] - (i + 16))
    # name table: 'AIM-' '5' kind 8  ->  'MK-8' '4' kind 8
    if agm65:      # every MK-8x and CBU bomb drawn as the MK-84; the BOMB kind (old MK-82 part) is the AGM-65
        k = bytes(c).find(OLD_NAMES); assert k > 0
        c[k:k + len(AGM65_NAMES)] = AGM65_NAMES
    else:
        k = bytes(c).find(b'AIM-5\x08'); assert k > 0 and bytes(c).count(b'AIM-5\x08') == 1
        c[k:k + 6] = b'MK-84\x08'
    d[code['ro']:code['ro'] + code['vs']] = c
    assert len(d) < 65536
    open(dst, 'wb').write(d)
    print(dst, len(d), 'B')


if __name__ == '__main__':
    main(*sys.argv[1:3], agm65='--agm65' in sys.argv)
