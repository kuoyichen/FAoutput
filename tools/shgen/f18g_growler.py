#!/usr/bin/env python3
"""EA-18G Growler stores for F18G.SH (copied from F18F.SH).

Adds, as three shared sub-parts placed with C4 (so each shape is stored once):
  * 480-gal fuel tank      (hexagonal, pointed nose, tapered tail)  -> inboard stations, x = ±27
  * ALQ-99 jammer pod      (box section, pointed nose, flat tail) -> midboard x = ±40 and centerline
  * ALQ-218 wingtip pod    (square-section rod, short nose/tail cones, 4 swept fins front and rear) -> x = ±69
CODE only has ~1.7 KB free before .idata, hence the shared parts, flat-shaded faces (0x261, no F6 needed)
and minimal facet counts.  Fins are drawn as two culled faces (front and back).

Draw order: the main BSP root (06 node at ROOT) is replaced by a call to a new block:
  S : eye above up=-1 ? stores first, then body : body first, then stores
  stores: split by x planes (0, ±33, ±55) so farther stores are drawn first.
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


def tank():
    """480-gal tank: 6-sided, nose tip +26, full ring at +8, tail ring at -20 tapered to 55 %, flat tail cap."""
    r = 4; hexr = [(0, r), (3, 2), (3, -2), (0, -r), (-3, -2), (-3, 2)]
    V = [(0, 26, 0)] + [(x, 8, z) for x, z in hexr] + [(round(x*.55), -20, round(z*.55)) for x, z in hexr]
    F = []
    for k in range(6):
        a, b = 1 + k, 1 + (k+1) % 6
        F += [(FLAT, GREY, [0, a, b]), (FLAT, GREY, [a, a+6, b+6, b])]
    F.append((FLAT, GREY, list(range(7, 13))))
    return V, orient(V, F)


def alq99():
    """ALQ-99: box section 6 wide x 7 high, nose cone to a point at +24, flat tail at -22."""
    sec = [(-3, 3), (3, 3), (3, -4), (-3, -4)]
    V = [(0, 24, -1)] + [(x, 14, z) for x, z in sec] + [(x, -22, z) for x, z in sec]
    F = []
    for k in range(4):
        a, b = 1 + k, 1 + (k+1) % 4
        F += [(FLAT, GREY, [0, a, b]), (FLAT, GREY, [a, a+4, b+4, b])]
    F.append((FLAT, GREY, [5, 6, 7, 8]))
    return V, orient(V, F)


def alq218():
    """ALQ-218 wingtip pod: square section (corners at ±45°, radius 2), short nose/tail cones,
    four swept triangular fins on the nose cone and four on the tail cone."""
    d = 2; c = [(d, d), (d, -d), (-d, -d), (-d, d)]
    R = lambda p: tuple(round(v) for v in p)
    V = [(0, 15, 0)] + [R((x, 11, z)) for x, z in c] + [R((x, -11, z)) for x, z in c] + [(0, -15, 0)]
    F = []
    for k in range(4):
        a, b = 1 + k, 1 + (k+1) % 4
        F += [(FLAT, GREY, [0, a, b]), (FLAT, GREY, [a, a+4, b+4, b]), (FLAT, GREY, [a+4, 9, b+4])]
    F = orient(V, F)
    for k, (x, z) in enumerate(c):          # fin tips: 3 out along the corner diagonal, swept back
        V.append(R((x * 2.4, 9, z * 2.4))); fa = len(V) - 1
        V.append(R((x * 2.4, -13, z * 2.4))); ra = len(V) - 1
        for tri in ([0, 1 + k, fa], [9, 5 + k, ra]):
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


def main():
    src, dst = sys.argv[1], sys.argv[2]
    d = bytearray(open(src, 'rb').read())
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
    order = ['S', 'BODY', 'ST', 'X2', 'LG', 'LOUT', 'RG', 'ROUT'] + list(STORES)
    size = {'S': 20, 'BODY': 20, 'ST': 20, 'X2': 20, 'LG': 20, 'LOUT': 20, 'RG': 20, 'ROUT': 20}
    size.update({k: 18 for k in STORES})
    at, p = {}, tail
    for k in order: at[k] = p; p += size[k]
    for k in parts: at['P' + k] = p; p += len(parts[k])

    def node(k, nrm, dd, a, b):
        o = at[k]
        return struct.pack('<BB6h', 0x06, 0, nrm[0], dd[0], nrm[1], dd[1], nrm[2], dd[2]) + \
            struct.pack('<hh', at[a] - (o+16), at[b] - (o+18)) + b'\x00\x00'
    X, UP = (16384, 0, 0), (0, 16384, 0)
    blk = bytearray()
    blk += node('S', UP, (0, 1, 0), 'ST', 'BODY')            # eye_up ≥ -1: stores, then body
    o = at['BODY']; blk += bytes(c[ROOT:ROOT+14]) + struct.pack('<hh', TA - (o+16), TB - (o+18)) + b'\x00\x00'
    blk += node('ST', X, (0, 0, 0), 'LG', 'X2')              # eye_x ≥ 0: left group first
    blk += node('X2', X, (0, 0, 0), 'C', 'RG')
    blk += node('LG', X, (33, 0, 0), 'LOUT', 'Ltank')
    blk += node('LOUT', X, (55, 0, 0), 'Ltip', 'Lalq')
    blk += node('RG', X, (-33, 0, 0), 'Rtank', 'ROUT')
    blk += node('ROUT', X, (-55, 0, 0), 'Ralq', 'Rtip')
    for k, (pt, pos) in STORES.items():
        o = at[k]
        blk += struct.pack('<BB6h', 0xC4, 0, *pos, 0, 0, 0) + struct.pack('<h', at['P' + pt] - (o+16)) + b'\x00\x00'
    for k in parts: blk += parts[k]
    assert len(blk) == p - tail
    patch = b'\x12\x00' + struct.pack('<h', at['S'] - (ROOT+4)) + b'\x38' + struct.pack('<h', ROOT + 18 - (ROOT+7))
    c[ROOT:ROOT+18] = patch + b'\x1e' * (18 - len(patch))
    room = nxt - code['va'] - len(c)
    nv = max(len(tank()[0]), len(alq99()[0]), len(alq218()[0]))
    print({k: len(v) for k, v in parts.items()}, 'total', len(blk), 'room', room, 'max part verts', nv)
    if len(blk) > room: sys.exit(f'not enough room: need {len(blk)}, have {room}')
    if BASE + nv > 900: sys.exit('vertex table over 900')
    open(dst, 'wb').write(insert_blocks(d, pe, secs, code, c, tail, bytes(blk)))
    print('wrote', dst)


if __name__ == '__main__':
    main()
