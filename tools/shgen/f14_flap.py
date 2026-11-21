#!/usr/bin/env python3
"""F-14 flaps: draw a lowered trailing-edge flap on each main-LOD wing panel, only when
the flaps are down AND the wing is fully spread (wing C4 heading == 0).

  * flap state = obj flag bit 0x100 at [obj+0x16F] (FA.EXE 0x4ab626 sets _PLleftFlap/_PLrightFlap = -1 from it)
    obj = [0x553848 + word[0x580BEC]*4]; no new import needed
  * "fully spread" = the wing C4 heading word (C4+8) is 0. The swing F0 (and the parked
    oversweep sub of f14_park_sweep.py) write it before the part is drawn, so an oversweep or any
    sweep > 0 hides the flap
  * flap = one planar trapezoid per wing (two faces, top and bottom), hinge 2 units ahead of the
    trailing edge, deflected 37 deg down (direction (fwd -4, up -3)), chord 10 inboard / 5 outboard,
    span x 1..52 in the wing part frame (left; right is mirrored). Wing texture (flags 0x6fd, col 152)
    with UVs taken from the trailing-edge strip of the wing's own UV mapping
  * hook: the wing part's first op (82, 16 vertices, 102 bytes) moves into the new block; its place
    holds an F0 trampoline to the block, a 06 node (eye above the flap: flap first, else wing first)
    and the flap faces. The block reloads the wing vertices + 4 flap vertices (slot 800), then x86
    picks: flap shown -> the node, else straight to the original wing tree
Usage: python3 f14_flap.py in.SH out.SH
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, insert_blocks, parse_face
from f18g_growler import grow_vas
from f14_nose import face_bytes

SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])
SIDES = {'L': dict(c4=0x3790, sx=1), 'R': dict(c4=0x39FE, sx=-1)}
FL, COL = 0x6FD, 152
SLOT = 800
X0, X1 = 1, 52                       # flap span (left wing part frame)
TE = lambda x: -26 - 6 * (x + 11) / 69   # trailing edge fwd at x (left part, vertex (-11,-26) -> (58,-32))
DIR_IN, DIR_OUT = (-8, -6), (-4, -3)     # flap chord vector (fwd, up): inboard 10, outboard 5, 37 deg


def code_of(d):
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE')
    c = bytearray(d[code['ro']:code['ro'] + code['vs']])
    return pe, secs, code, c


def wing_uv_map(c, part):
    """least-squares affine (x, fwd) -> (u, v) from the textured faces of the wing part"""
    n = struct.unpack_from('<H', c, part + 2)[0]; base = struct.unpack_from('<H', c, part + 4)[0] // 8
    V = [struct.unpack_from('<3h', c, part + 6 + 6 * k) for k in range(n)]
    rows = []
    p = part + 6 + 6 * n
    for o in range(p, p + 0x400):
        if c[o] != 0xFC: continue
        f = parse_face(c, o)
        if not f or f['col'] != COL or not f['uv'] or not all(0 <= i - base < n for i in f['idx']): continue
        if any(abs(V[i - base][0]) > 60 for i in f['idx']): continue     # wingtip pieces map their own texture
        for i, uv in zip(f['idx'], f['uv']): rows.append((V[i - base][0], V[i - base][1], uv))
    import numpy as np
    A = np.array([[x, y, 1] for x, y, _ in rows], float)
    cu = np.linalg.lstsq(A, np.array([uv[0] for *_, uv in rows], float), rcond=None)[0]
    cv = np.linalg.lstsq(A, np.array([uv[1] for *_, uv in rows], float), rcond=None)[0]
    return lambda x, y: (int(round(max(0, cu @ (x, y, 1)))), int(round(max(0, cv @ (x, y, 1))))), len(rows)


def flap_geom(sx):
    a_f, b_f = round(TE(X0) + 2), round(TE(X1) + 2)
    A = (X0, a_f, 0); B = (X1, b_f, 0)
    D = (X0, a_f + DIR_IN[0], DIR_IN[1]); C = (X1, b_f + DIR_OUT[0], DIR_OUT[1])
    P = [A, B, C, D]
    P = [(sx * x, y, z) for x, y, z in P]
    return P


def build(d):
    pe, secs, code, c = code_of(d)
    tail = c.find(SIG)
    nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    # do_start_interp thunk: from the swing F0 of the left wing (push ret; push thunk; ret right before the C4)
    c4L = SIDES['L']['c4']
    assert c[c4L - 11] == 0x68 and c[c4L - 6] == 0x68 and c[c4L - 1] == 0xC3
    thunk_old = struct.unpack_from('<I', c, c4L - 5)[0]
    VA = lambda off: code['va'] + off
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)

    def x86(c4va, nf, root, thunk):
        src = f"""
            movzx ecx, word ptr [0x580bec]
            mov eax, dword ptr [ecx*4 + 0x553848]
            test byte ptr [eax + 0x170], 1
            jz no
            cmp word ptr [{c4va + 8:#x}], 0
            jne no
            push {nf:#x}
            jmp go
        no:
            push {root:#x}
        go:
            push {thunk:#x}
            ret
        """
        return bytes(ks.asm(src, 0)[0])

    probe = x86(0x11111111, 0x22222222, 0x33333333, 0x44444444)
    offs = {k: probe.find(struct.pack('<I', v)) for k, v in
            (('c4', 0x11111111 + 8), ('nf', 0x22222222), ('root', 0x33333333), ('thunk', 0x44444444))}
    assert all(o > 0 for o in offs.values()), offs

    per = {}
    for side, S in SIDES.items():
        c4 = S['c4']; assert c[c4] == 0xC4
        part = c4 + 16 + struct.unpack_from('<h', c, c4 + 14)[0]
        assert c[part] == 0x82 and struct.unpack_from('<H', c, part + 2)[0] == 16, hex(part)
        root = part + 6 + 16 * 6
        assert c[root] in (0x06, 0x0C, 0x0E, 0x10), hex(root)
        uvmap, nuv = wing_uv_map(c, part)
        per[side] = dict(c4=c4, part=part, root=root, uvmap=uvmap, nuv=nuv)

    FACES_LEN = 2 * 39 + 1
    blk_len = 0
    for side in SIDES: per[side]['blk'] = blk_len; blk_len += 6 + 4 * 6 + 102 + 2 + len(probe) + FACES_LEN
    blk_len += blk_len % 2
    room = nxt - code['va'] - len(c)
    if blk_len > room:
        return None, blk_len - room
    L = blk_len
    thunk_new = thunk_old + L
    print('  thunk', hex(thunk_old), '->', hex(thunk_new), 'block', L, 'room', room)
    relocs = []
    blk = bytearray()
    for side, S in SIDES.items():
        q = per[side]; part = q['part']; sx = S['sx']
        P = flap_geom(sx)
        # flap UVs: trailing-edge strip of the wing texture (LE -> TE + chord, TE side -> TE)
        uvm = q['uvmap']                               # uv map is in the side's own part frame (x already mirrored in P)
        A, B, C, D = P
        tex = {0: uvm(A[0], TE(X0) + 8), 1: uvm(B[0], TE(X1) + 4), 2: uvm(C[0], TE(X1)), 3: uvm(D[0], TE(X0))}
        idx = [SLOT + i for i in range(4)]
        # FA: face winding sum P x P points inward (x, y, z); top face outward = up/back
        def oriented(order, out):
            Q = [P[i] for i in order]
            n = [0, 0, 0]
            for k in range(4):
                p, r = Q[k], Q[(k + 1) % 4]
                n[0] += p[1]*r[2]-p[2]*r[1]; n[1] += p[2]*r[0]-p[0]*r[2]; n[2] += p[0]*r[1]-p[1]*r[0]
            if sum(n[k] * out[k] for k in range(3)) > 0: order = order[::-1]
            return order
        # flap plane normal (vertex frame x, fwd, up): up-and-back side = (0, -3, 4)/5 -> outward for top
        top = oriented([0, 1, 2, 3], (0, -3, 4)); bot = oriented([0, 1, 2, 3], (0, 3, -4))
        faces = b''.join(face_bytes(FL, COL, [idx[i] for i in o], [P[i] for i in o], [tex[i] for i in o]) for o in (top, bot)) + b'\x1e'
        assert len(faces) == FACES_LEN, len(faces)
        # area at the old 82: T0 (13) | NF node (18 + 1E) | FJ (13): F0 jump to the flap faces in the block
        T0, NF, FJ = part, part + 13, part + 32
        node = struct.pack('<BB6h', 0x06, 0, 0, 0, 16384, 0, 0, 0) + struct.pack('<hh', FJ - (NF + 16), q['root'] - (NF + 18)) + b'\x1e'
        b0 = len(blk); assert b0 == q['blk']
        FACES = tail + b0 + 6 + 4 * 6 + 102 + 2 + len(probe)
        f0jmp = lambda at, to: (b'\xf0\x00\x68' + struct.pack('<I', VA(to)) + b'\x68' + struct.pack('<I', thunk_new) + b'\xc3',
                                [at + 3 - tail, at + 8 - tail])
        t0, r0 = f0jmp(T0, tail + b0); fj, r1 = f0jmp(FJ, FACES)
        relocs += r0 + r1
        area = t0 + node + fj
        assert len(area) <= 102, len(area)
        orig82 = bytes(c[part:part + 102])
        c[part:part + 102] = bytes(area) + b'\x00' * (102 - len(area))
        # block: flap vertices, wing vertices, F0 chooser, flap faces
        blk += struct.pack('<BBHH', 0x82, 0, 4, SLOT * 8) + b''.join(struct.pack('<3h', *p) for p in P)
        blk += orig82
        f0 = len(blk)
        blk += b'\xf0\x00' + x86(VA(q['c4']), VA(NF), VA(q['root']), thunk_new)
        for k, o in offs.items(): relocs.append(f0 + 2 + o)
        assert tail + len(blk) == FACES
        blk += faces
        q.update(P=P, tex=tex, area=len(area), NF=NF)
    blk += b'\x00' * (L - len(blk))
    out = insert_blocks(d, pe, secs, code, c, tail, bytes(blk), relocs)
    return out, per


def main():
    src, dst = sys.argv[1:3]
    d = bytes(open(src, 'rb').read())
    out, per = build(d)
    if out is None:
        d = bytes(grow_vas(d, 0x1000))
        out, per = build(d)          # build() re-reads CODE from the grown file
    assert out is not None and len(out) < 65536, len(out or b'')
    open(dst, 'wb').write(out)
    for s, q in per.items():
        print(s, 'part', hex(q['part']), 'root', hex(q['root']), 'uv pts', q['nuv'], 'flap', q['P'], 'uv', q['tex'], 'area', q['area'])
    print(f'{dst}: {len(out)} B')


if __name__ == '__main__':
    main()
