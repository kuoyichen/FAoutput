#!/usr/bin/env python3
"""EA-18G Growler stores for F18G.SH (copied from F18F.SH).

Adds, as three shared sub-parts placed with C4 (so each shape is stored once):
  * 480-gal fuel tank      (hexagonal, pointed nose, tapered tail)  -> inboard stations, x = ±27
  * ALQ-99 jammer pod      (box section, pointed nose, flat tail) -> midboard x = ±40 and centerline
  * ALQ-218 wingtip pod    (square-section rod, short nose/tail cones, 4 swept fins front and rear) -> x = ±69
CODE only has ~1.7 KB free before .idata, hence the shared parts, flat-shaded faces (0x261, no F6 needed)
and minimal facet counts.  Fins are drawn as two culled faces (front and back).

Draw order: the main BSP root (06 node at ROOT; everything incl. flaps and gear is drawn under it) is
replaced by a call to a new block of plane tests.  Each side's stores are drawn after the body when the
eye is on their side, below or in front (x + up - fwd < -20, mirrored for the right), otherwise before it;
the centerline pod is drawn after the body only from below.  x planes (±33, ±55) order stores on a side.
If CODE has too little room before .idata, the later sections are moved up in VA (grow_vas).
Usage: python3 f18g_growler.py in/F18G.SH out/F18G.SH
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, main_lod, insert_blocks
from f14_nose import face_bytes

SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])
BASE = 480                 # vertex-table slot for the part vertices (gear parts end at 463)
FLAT, FIN = 0x261, 0x261   # flat colour, light from normal, back-face culled
GREY, DARK = 150, 156


def orient(V, faces, cen=None):
    """FA wants ΣP×P (in x,y,z) to point inward: flip faces whose sum points away from the centre."""
    cen = cen or [sum(p[k] for p in V) / len(V) for k in range(3)]
    out = []
    for fl, col, idx in faces:
        P = [V[i] for i in idx]; n = [0, 0, 0]
        for k in range(len(P)):
            p, q = P[k], P[(k+1) % len(P)]
            n[0] += p[1]*q[2]-p[2]*q[1]; n[1] += p[2]*q[0]-p[0]*q[2]; n[2] += p[0]*q[1]-p[1]*q[0]
        fc = [sum(p[k] for p in P) / len(P) - cen[k] for k in range(3)]
        if sum(n[k]*fc[k] for k in range(3)) > 0: idx = idx[::-1]
        out.append((fl, col, idx))
    return out


def lathe(sec, stations, col=GREY):
    """Revolve-style body: cross-section `sec` [(x, up)] scaled at each station (fwd, scale, up offset).
    A station with scale 0 is a single tip vertex; an end that is not a tip gets a flat cap.
    Returns (V, faces, ring vertex ids per station)."""
    V, rings = [], []
    for fwd, k, dz in stations:
        if k == 0: V.append((0, round(fwd), round(dz))); rings.append([len(V) - 1] * len(sec))
        else:
            rings.append([])
            for x, z in sec: V.append((round(x * k), round(fwd), round(z * k + dz))); rings[-1].append(len(V) - 1)
    F, n = [], len(sec)
    for A, B in zip(rings, rings[1:]):
        for j in range(n):
            q = [A[j], A[(j+1) % n], B[(j+1) % n], B[j]]
            q = [v for i, v in enumerate(q) if v != q[i-1]]
            F.append((FLAT, col, q))
    for st, r in ((stations[0], rings[0]), (stations[-1], rings[-1])):
        if st[1]: F.append((FLAT, col, list(r)))
    return V, orient(V, F), rings


def tank():
    """480-gal tank (inboard, the bigger store): octagon radius 5, nose rounded with two extra rings,
    tail closed by one ring and a point."""
    sec = [(0, 5), (4, 4), (5, 0), (4, -4), (0, -5), (-4, -4), (-5, 0), (-4, 4)]
    V, F, _ = lathe(sec, [(28, 0, -1), (26, .45, -.5), (22, .8, 0), (14, 1, 0), (-12, 1, 0), (-20, .6, .5), (-25, 0, 1)])
    return V, F


def alq99():
    """ALQ-99 jammer pod (midboard and centerline): narrower box section 5 x 6, nose rounded with
    two extra rings, flat tail."""
    sec = [(-2.5, 2.5), (2.5, 2.5), (2.5, -3.5), (-2.5, -3.5)]
    V, F, _ = lathe(sec, [(24, 0, -.5), (22, .45, -.3), (19, .8, 0), (14, 1, 0), (-22, 1, 0)])
    return V, F


def alq218():
    """ALQ-218 wingtip pod: square section (corners at ±45°), rounded nose and tail, four small swept
    fins on the front shoulder and four on the rear shoulder (2/3 of the first version)."""
    sec = [(2, 2), (2, -2), (-2, -2), (-2, 2)]
    st = [(15, 0, 0), (13.5, .6, 0), (12, 1, 0), (9, 1, 0), (6, 1, 0), (-6, 1, 0), (-9, 1, 0), (-12, 1, 0), (-13.5, .6, 0), (-15, 0, 0)]
    V, F, rings = lathe(sec, st)
    for k, (x, z) in enumerate(sec):        # fin = root on the corner ridge + tip out along the diagonal, swept back
        for front, rear in ((3, 4), (6, 7)):
            tip = (round(x * 1.95), round(st[rear][0]), round(z * 1.95)); V.append(tip)
            tri = [rings[front][k], rings[rear][k], len(V) - 1]
            F += [(FIN, DARK, tri), (FIN, DARK, tri[::-1])]
    return V, F


def part_bytes(V, F):
    b = bytearray(struct.pack('<BBHH', 0x82, 0, len(V), BASE*8))
    for v in V: b += struct.pack('<hhh', *v)
    for fl, col, idx in F:
        b += face_bytes(fl, col, [BASE+i for i in idx], [V[i] for i in idx])
    return b + b'\x00\x00'


# instance positions (x, up, fwd) in vertex units
STORES = {
    'Ltip': ('218', (-69, 1, -17)), 'Lalq': ('99', (-40, -2, -6)), 'Ltank': ('tank', (-27, -2, -2)),
    'C':    ('99', (0, -10, -2)),
    'Rtank': ('tank', (27, -2, -2)), 'Ralq': ('99', (40, -2, -6)), 'Rtip': ('218', (69, 1, -17)),
}


def grow_vas(d, delta):
    """Move every section after CODE up by `delta` in virtual address so a longer CODE fits.
    FA's SH loader (0x41E990) maps RVAs to sections by each section's own VA, so a consistent shift is safe:
    section VAs, data directories, import descriptors and thunks, relocation pages and relocated dwords
    that point into the moved sections are all updated.  ImageBase is 0, so absolute = RVA."""
    d = bytearray(d)
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE')
    lo = min(s['va'] for s in secs if s['va'] > code['va'])
    def off(rva):
        for s in sorted(secs, key=lambda s: -s['va']):     # CODE may already overlap the next VA
            if s['va'] <= rva < s['va'] + max(s['vs'], s['rs']): return s['ro'] + rva - s['va']
        raise ValueError(hex(rva))
    # relocations: fix values first (old layout), collect entries with new target RVAs
    rel = next(s for s in secs if s['name'] == '.reloc')
    rdir = pe + 24 + 96 + 8*5; rva, rsz = struct.unpack_from('<II', d, rdir)
    ents, p = [], off(rva)
    while p < off(rva) + rsz:
        page, sz = struct.unpack_from('<II', d, p)
        if sz < 8: break
        for k in range((sz-8)//2):
            e = struct.unpack_from('<H', d, p+8+2*k)[0]
            if e >> 12: ents.append((e >> 12, page + (e & 0xFFF)))
        p += sz
    for t, r in ents:
        o = off(r); v = struct.unpack_from('<I', d, o)[0]
        if v >= lo: struct.pack_into('<I', d, o, v + delta)
    # imports
    irva = struct.unpack_from('<I', d, pe+24+96+8)[0]
    if irva:
        q = off(irva)
        while struct.unpack_from('<I', d, q+12)[0]:
            oft, _, _, name, ft = struct.unpack_from('<5I', d, q)
            for th in (oft, ft):
                if not th: continue
                t = off(th)
                while True:
                    v = struct.unpack_from('<I', d, t)[0]
                    if not v: break
                    if not v & 0x80000000 and v >= lo: struct.pack_into('<I', d, t, v + delta)
                    t += 4
            struct.pack_into('<5I', d, q, *(x + delta if x >= lo else x for x in (oft, _, _, name, ft)))
            q += 20
    # rebuild the relocation table with shifted pages
    tbl = bytearray(); pages = {}
    for t, r in sorted(((t, r + delta if r >= lo else r) for t, r in ents), key=lambda x: x[1]):
        pages.setdefault(r & ~0xFFF, []).append((t << 12) | (r & 0xFFF))
    for pg, es in sorted(pages.items()):
        if len(es) % 2: es.append(0)
        tbl += struct.pack('<II', pg, 8 + 2*len(es)) + b''.join(struct.pack('<H', e) for e in es)
    o = off(rva); d[o:o+rsz] = b'\x00' * rsz; d[o:o+len(tbl)] = tbl
    # data directories, section headers, SizeOfImage
    for k in range(16):
        a = pe + 24 + 96 + 8*k; r = struct.unpack_from('<I', d, a)[0]
        if r >= lo: struct.pack_into('<I', d, a, r + delta)
    struct.pack_into('<I', d, rdir + 4, len(tbl))
    for s in secs:
        if s['va'] >= lo: struct.pack_into('<I', d, s['hdr'] + 12, s['va'] + delta)
    soi = struct.unpack_from('<I', d, pe+24+56)[0]; struct.pack_into('<I', d, pe+24+56, soi + delta)
    return bytes(d)


def build(d):
    """Hook the stores into SH bytes `d`; returns (new file or None if CODE is too small, bytes needed, room)."""
    d = bytearray(d)
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    c = bytearray(d[code['ro']:code['ro']+code['vs']])
    o0, n, _, e = main_lod(c)[0]
    ROOT = e
    while c[ROOT] == 0xF6: ROOT += 7
    assert c[ROOT] == 0x06 and c[ROOT+1] == 0 and c[ROOT+18] == 0x38, 'root is not the expected 06 node + 38'
    TA = ROOT + 16 + struct.unpack_from('<h', c, ROOT+14)[0]; TB = ROOT + 18 + struct.unpack_from('<h', c, ROOT+16)[0]
    parts = {'tank': part_bytes(*tank()), '99': part_bytes(*alq99()), '218': part_bytes(*alq218())}
    tail = bytes(c).find(SIG)

    # layout: nodes and leaves first, then the part bodies
    order = ['PL', 'PR', 'PC', 'BODY', 'LG', 'LOUT', 'RG', 'ROUT'] + list(STORES)
    size = {k: 20 for k in order}
    size.update({k: 18 for k in STORES})
    at, p = {}, tail
    for k in order: at[k] = p; p += size[k]
    for k in parts: at['P' + k] = p; p += len(parts[k])

    def node(k, nrm, dd, a, b):     # Σ n·(eye+d) ≥ 0 → draw a then b, else b then a (eye = x, up, fwd)
        o = at[k]
        return struct.pack('<BB6h', 0x06, 0, nrm[0], dd[0], nrm[1], dd[1], nrm[2], dd[2]) + \
            struct.pack('<hh', at[a] - (o+16), at[b] - (o+18)) + b'\x00\x00'
    X, UP, Q = (16384, 0, 0), (0, 16384, 0), 8192
    blk = bytearray()
    # Left stores are drawn after the body (so they cover it, and the lowered flaps) when the eye is to the
    # left, below or in front: x + up - fwd < -20.  Same for the right with -x.  The centerline pod is drawn
    # after the body only from below (up < -9), so the nose gear still covers it from the front.
    blk += node('PL', (Q, Q, -Q), (20, 0, 0), 'LG', 'PR')
    blk += node('PR', (-Q, Q, -Q), (-20, 0, 0), 'RG', 'PC')
    blk += node('PC', UP, (0, 9, 0), 'C', 'BODY')
    o = at['BODY']; blk += bytes(c[ROOT:ROOT+14]) + struct.pack('<hh', TA - (o+16), TB - (o+18)) + b'\x00\x00'
    blk += node('LG', X, (33, 0, 0), 'LOUT', 'Ltank')        # farther store first
    blk += node('LOUT', X, (55, 0, 0), 'Ltip', 'Lalq')
    blk += node('RG', X, (-33, 0, 0), 'Rtank', 'ROUT')
    blk += node('ROUT', X, (-55, 0, 0), 'Ralq', 'Rtip')
    for k, (pt, pos) in STORES.items():
        o = at[k]
        blk += struct.pack('<BB6h', 0xC4, 0, *pos, 0, 0, 0) + struct.pack('<h', at['P' + pt] - (o+16)) + b'\x00\x00'
    for k in parts: blk += parts[k]
    assert len(blk) == p - tail
    patch = b'\x12\x00' + struct.pack('<h', at['PL'] - (ROOT+4)) + b'\x38' + struct.pack('<h', ROOT + 18 - (ROOT+7))
    c[ROOT:ROOT+18] = patch + b'\x1e' * (18 - len(patch))
    room = nxt - code['va'] - len(c)
    nv = max(len(tank()[0]), len(alq99()[0]), len(alq218()[0]))
    print({k: len(v) for k, v in parts.items()}, 'total', len(blk), 'room', room, 'max part verts', nv)
    if BASE + nv > 900: sys.exit('vertex table over 900')
    if len(blk) > room: return None, len(blk), room
    return insert_blocks(d, pe, secs, code, c, tail, bytes(blk)), len(blk), room


def main():
    src, dst = sys.argv[1], sys.argv[2]
    d = open(src, 'rb').read()
    out, need, room = build(d)
    if out is None:     # grow first (no CODE/.idata overlap yet, so every value >= old .idata VA is unambiguous)
        delta = (need - room + 0xFFF) // 0x1000 * 0x1000
        print(f'moving .idata/.reloc/$$DOSX up by {delta:#x} to make room')
        out, need, room = build(grow_vas(d, delta))
    out = out.replace(b'\xe2\x00_f18f.PIC', b'\xe2\x00_f18g.PIC')      # use the Growler's own texture file
    open(dst, 'wb').write(out)
    print('wrote', dst)


if __name__ == '__main__':
    main()
