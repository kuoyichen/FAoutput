#!/usr/bin/env python3
"""EA-18G Growler stores for F18G.SH (copied from F18F.SH).

Adds, as three shared sub-parts placed with C4 (so each shape is stored once):
  * 480-gal fuel tank      (octagonal, pointed nose, tapered tail)  -> inboard stations, x = ±27
  * ALQ-99 jammer pod      (box section, pointed nose, flat tail) -> midboard x = ±40 and centerline
  * ALQ-218 wingtip pod    (square-section rod, short nose/tail cones, 4 swept fins front and rear) -> x = ±69
CODE only has ~1.7 KB free before .idata, hence the shared parts, flat-shaded faces (0x261, no F6 needed)
and minimal facet counts.  Fins are drawn as two culled faces (front and back).

Stores hang on pylons below the wing (store tops at up -2, wing at up 2-3); inside the tank and ALQ-99
parts a plane node at the store top orders store and pylon.
Draw order: the main BSP root (06 node at ROOT; everything incl. flaps and gear is drawn under it) is
replaced by a call to nested plane tests (eye = x, up, fwd, eye position in model units, A then B when
Σn·(eye+d) ≥ 0 -- checked in FA.EXE at 0x4d2450; C4 subtracts the part position from the eye).  Each store
group is drawn after the body when its plane says the eye can see it in front of the body: underwing groups
from below, their own side or the front at wing level; wingtip pods except low from the far side;
the centerline pod from below.
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
    sec = [(0, 4), (3, 3), (4, 0), (3, -3), (0, -4), (-3, -3), (-4, 0), (-3, 3)]
    V, F, _ = lathe(sec, [(22, 0, -1), (21, .45, -.5), (18, .8, 0), (11, 1, 0), (-10, 1, 0), (-16, .6, .5), (-20, 0, 1)])
    return V, F, pylon(V, (6, -8, 3), (10, -11, 9)), 3


def alq99():
    """ALQ-99 jammer pod (midboard and centerline): narrower box section 5 x 6, nose rounded with
    two extra rings, flat tail."""
    sec = [(-2.5, 2.5), (2.5, 2.5), (2.5, -3.5), (-2.5, -3.5)]
    V, F, _ = lathe(sec, [(24, 0, -.5), (22, .45, -.3), (19, .8, 0), (14, 1, 0), (-22, 1, 0)])
    return V, F, pylon(V, (10, -10, 2), (13, -13, 6)), 2


def pylon(V, bot, top):
    """Pylon on top of a store: a 2-wide slab from the store top (fwd bot[0]..bot[1] at up bot[2]) up to the
    wing (fwd top[0]..top[1] at up top[2]); the leading edge rakes forward going up.  Appends its 8 vertices
    to V and returns its four side faces (top and bottom are hidden against the wing and the store)."""
    b = len(V)
    for (f, r, u) in (bot, top):
        for x in (-1, 0): V += [(x, f, u), (x, r, u)]     # 1 unit thick (vertex coordinates are integers)
    # b+0 bot L front, +1 bot L rear, +2 bot R front, +3 bot R rear, +4..+7 the same on top
    q = [[b, b+1, b+5, b+4], [b+2, b+3, b+7, b+6], [b, b+2, b+6, b+4], [b+1, b+3, b+7, b+5]]
    P = V[b:]; cen = [sum(p[k] for p in P) / len(P) for k in range(3)]
    return orient(V, [(FLAT, GREY, f) for f in q], cen)


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


def faces_bytes(V, F):
    return b''.join(face_bytes(fl, col, [BASE+i for i in idx], [V[i] for i in idx]) for fl, col, idx in F)


def part_bytes(V, F, PY=None, top=0):
    """82 vertex buffer + faces.  With a pylon PY, a plane node at the store top (up = top) draws the store
    then the pylon when the eye is above it, else the pylon then the store, so the two never show through."""
    b = bytearray(struct.pack('<BBHH', 0x82, 0, len(V), BASE*8))
    for v in V: b += struct.pack('<hhh', *v)
    if not PY: return b + faces_bytes(V, F) + b'\x00\x00'
    n = len(b); A = faces_bytes(V, F) + b'\x00\x00'; oA = n + 20; oB = oA + len(A)
    b += struct.pack('<BB6h', 0x06, 0, 0, 0, 16384, -top, 0, 0) + struct.pack('<hh', oA - (n+16), oB - (n+18)) + b'\x00\x00'
    return b + A + faces_bytes(V, PY) + b'\x00\x00'


# instance positions (x, up, fwd) in vertex units.  The wing is a single surface at up ≈ 3 (x = 27) and
# ≈ 2 (x = 40); the store tops sit at up -2 and the pylons reach up to the wing.  The belly is at up -7/-8.
STORES = {
    'Ltip': ('218', (-69, 1, -17)), 'Lalq': ('99', (-40, -4, -6)), 'Ltank': ('tank', (-27, -6, -2)),
    'C':    ('99', (0, -12, -2)),
    'Rtank': ('tank', (27, -6, -2)), 'Ralq': ('99', (40, -4, -6)), 'Rtip': ('218', (69, 1, -17)),
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
    order = ['PR', 'PRT', 'PL', 'PLT', 'PC', 'BODY', 'LG', 'RG'] + list(STORES)
    size = {k: 20 for k in order}
    size.update({k: 18 for k in STORES})
    at, p = {}, tail
    for k in order: at[k] = p; p += size[k]
    for k in parts: at['P' + k] = p; p += len(parts[k])

    def node(k, nrm, dd, a, b):     # Σ n·(eye+d) ≥ 0 → draw a then b, else b then a (eye = x, up, fwd)
        o = at[k]
        return struct.pack('<BB6h', 0x06, 0, nrm[0], dd[0], nrm[1], dd[1], nrm[2], dd[2]) + \
            struct.pack('<hh', at[a] - (o+16), at[b] - (o+18)) + b'\x00\x00'
    X = (16384, 0, 0)
    blk = bytearray()
    # Each group is drawn after everything nested inside it (so it covers the body, flaps and gear) when its
    # "after" plane is ≥ 0, otherwise before.  Groups: right underwing, right tip, left underwing, left tip,
    # centerline, then the body.  Directions for a distant eye:
    #   underwing (left):  -0.15 x - up + 0.08 fwd ≥ 0 → seen from below the wing, from the left or the front at
    #                      wing level; from any height above the wing, the far side or the rear they go first
    #   wingtip (left):    -x + 1.2 up ≥ 0            → everywhere except low from the right, where the fuselage hides it
    #   centerline:        up ≤ -9                    → only from below
    blk += node('PR', (2458, -16384, 1311), (-18, -2, 0), 'PRT', 'RG')
    blk += node('PRT', (10923, 13107, 0), (-20, 0, 0), 'PL', 'Rtip')
    blk += node('PL', (-2458, -16384, 1311), (18, -2, 0), 'PLT', 'LG')
    blk += node('PLT', (-10923, 13107, 0), (20, 0, 0), 'PC', 'Ltip')
    blk += node('PC', (0, -16384, 0), (0, 9, 0), 'BODY', 'C')
    o = at['BODY']; blk += bytes(c[ROOT:ROOT+14]) + struct.pack('<hh', TA - (o+16), TB - (o+18)) + b'\x00\x00'
    blk += node('LG', X, (33, 0, 0), 'Lalq', 'Ltank')        # farther store first
    blk += node('RG', X, (-33, 0, 0), 'Rtank', 'Ralq')
    for k, (pt, pos) in STORES.items():
        o = at[k]
        blk += struct.pack('<BB6h', 0xC4, 0, *pos, 0, 0, 0) + struct.pack('<h', at['P' + pt] - (o+16)) + b'\x00\x00'
    for k in parts: blk += parts[k]
    assert len(blk) == p - tail
    patch = b'\x12\x00' + struct.pack('<h', at['PR'] - (ROOT+4)) + b'\x38' + struct.pack('<h', ROOT + 18 - (ROOT+7))
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
