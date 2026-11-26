#!/usr/bin/env python3
"""F-14 flaps: draw a lowered trailing-edge flap on each main-LOD wing panel, only when
the flaps are down AND the wing is fully spread (wing C4 heading == 0).

  * flap state = obj flag bit 0x100 at [obj+0x16F] (FA.EXE 0x4ab626 sets _PLleftFlap/_PLrightFlap = -1 from it)
    obj = [0x553848 + word[0x580BEC]*4]; no new import needed
  * "fully spread" = the wing C4 heading word (C4+8) is 0. The swing F0 (and the parked
    oversweep sub of f14_park_sweep.py) write it before the part is drawn, so an oversweep or any
    sweep > 0 hides the flap
  * flap = the wing's own trailing-edge band (the faces between the line root(-20) -> tip(-28) and the
    trailing edge), span x 1..52 (left part frame; right mirrored), rotated about its front edge ~33 deg
    down. v2 (F14-55, Kuoyi: the real flap leaves a gap in the wing): the band faces of each surface are
    hooked: flap hidden -> strip + inboard piece + outboard piece (looks as before), flap shown -> only
    the two end pieces, so the wing has a notch where the flap was. The hook reads a flag byte the
    chooser writes (1 = flap shown). A second band face on the same surface becomes a 38 jump over itself
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
X0, X1 = 1, 52                           # flap span (left wing part frame, right = -x)
DIR_IN, DIR_OUT = (-5, -3), (-3, -2)     # flap chord after deflection (fwd, up): inboard 6, outboard 4


def code_of(d):
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE')
    c = bytearray(d[code['ro']:code['ro'] + code['vs']])
    return pe, secs, code, c


def line(p, q):
    return lambda x: p[1] + (q[1] - p[1]) * (x - p[0]) / (q[0] - p[0])


def wing_info(c, part):
    """vertices, uv map and the trailing-band faces per surface"""
    n = struct.unpack_from('<H', c, part + 2)[0]; base = struct.unpack_from('<H', c, part + 4)[0] // 8
    V = [struct.unpack_from('<3h', c, part + 6 + 6 * k) for k in range(n)]
    faces = []
    for o in range(part + 6 + 6 * n, part + 0x400):
        if c[o] != 0xFC: continue
        f = parse_face(c, o)
        if not f or f['col'] != COL or not f['uv'] or not all(0 <= i - base < n for i in f['idx']): continue
        f['P'] = [V[i - base] for i in f['idx']]
        faces.append(f)
    rootx = min((p[0] for p in V), key=lambda x: abs(x))       # root is the x nearest 0 among... (fixed below)
    xs = sorted(set(p[0] for p in V))
    sx = 1 if max(xs) > 0 and max(xs) > -min(xs) else -1
    rootx = min(xs) if sx > 0 else max(xs)
    if sx > 0: rootx = -11
    tipx = 58 * sx
    Fl = line((rootx, -20), (tipx, -28)); TEl = line((rootx, -26), (tipx, -32))
    band = [f for f in faces if all(abs(p[0]) <= 58 and p[1] <= Fl(p[0]) + 0.5 for p in f['P'])]
    uvs = {}
    for f in faces:
        if any(abs(p[0]) > 60 for p in f['P']): continue
        for p, uv in zip(f['P'], f['uv']): uvs.setdefault((p[0], p[1]), uv)
    import numpy as np
    rows = list(uvs.items())
    A = np.array([[x, y, 1] for (x, y), _ in rows], float)
    cu = np.linalg.lstsq(A, np.array([uv[0] for _, uv in rows], float), rcond=None)[0]
    cv = np.linalg.lstsq(A, np.array([uv[1] for _, uv in rows], float), rcond=None)[0]
    uvm = lambda x, y: uvs.get((x, y)) or (int(round(max(0, cu @ (x, y, 1)))), int(round(max(0, cv @ (x, y, 1)))))
    surf = {}
    for f in band:
        nup = struct.unpack_from('<3h', f['head'], 4)[1]
        surf.setdefault('top' if nup > 0 else 'bot', []).append(f)
    return dict(V=V, sx=sx, rootx=rootx, tipx=tipx, F=Fl, TE=TEl, surf=surf, uvm=uvm)


def oriented(P, order, out):
    """FA: face winding sum P x P (x, y, z) points inward -> flip if it points along `out`"""
    Q = [P[i] for i in order]; n = [0, 0, 0]
    for k in range(len(Q)):
        p, r = Q[k], Q[(k + 1) % len(Q)]
        n[0] += p[1]*r[2]-p[2]*r[1]; n[1] += p[2]*r[0]-p[0]*r[2]; n[2] += p[0]*r[1]-p[1]*r[0]
    return order[::-1] if sum(n[k] * out[k] for k in range(3)) > 0 else order


def build(d):
    pe, secs, code, c = code_of(d)
    tail = c.find(SIG)
    nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    c4L = SIDES['L']['c4']
    assert c[c4L - 11] == 0x68 and c[c4L - 6] == 0x68 and c[c4L - 1] == 0xC3
    thunk_old = struct.unpack_from('<I', c, c4L - 5)[0]
    VA = lambda off: code['va'] + off
    I = lambda v: struct.pack('<I', v)

    # hand-encoded (keystone turns e.g. `push 0xff9b` into push imm8 = 0xffffff9b); returns (bytes, reloc offsets)
    def chooser(c4va, nf, root, thunk, flag):
        b = (b'\xc6\x05' + I(flag) + b'\x00'                 # mov byte [flag], 0
             + b'\x0f\xb7\x0d\xec\x0b\x58\x00'              # movzx ecx, word [0x580bec]
             + b'\x8b\x04\x8d\x48\x38\x55\x00'              # mov eax, [ecx*4 + 0x553848]
             + b'\xf6\x80\x70\x01\x00\x00\x01'              # test byte [eax + 0x170], 1
             + b'\x74\x17'                                    # jz no
             + b'\x66\x83\x3d' + I(c4va + 8) + b'\x00'         # cmp word [c4 + 8], 0
             + b'\x75\x0d'                                    # jne no
             + b'\xfe\x05' + I(flag)                          # inc byte [flag]
             + b'\x68' + I(nf) + b'\xeb\x05'                   # push nf; jmp go
             + b'\x68' + I(root)                               # no: push root
             + b'\x68' + I(thunk) + b'\xc3')                    # go: push thunk; ret
        return b, [2, 33, 42, 47, 54, 59]

    def hook(flag, orig, alt, thunk):
        b = (b'\x80\x3d' + I(flag) + b'\x00'                 # cmp byte [flag], 0
             + b'\x68' + I(orig)                               # push orig
             + b'\x74\x07'                                    # je go
             + b'\xc7\x04\x24' + I(alt)                          # mov dword [esp], alt
             + b'\x68' + I(thunk) + b'\xc3')                    # go: push thunk; ret
        return b, [2, 8, 17, 22]

    per = {}
    for side, S in SIDES.items():
        c4 = S['c4']; assert c[c4] == 0xC4
        part = c4 + 16 + struct.unpack_from('<h', c, c4 + 14)[0]
        assert c[part] == 0x82 and struct.unpack_from('<H', c, part + 2)[0] == 16, hex(part)
        root = part + 6 + 16 * 6
        assert c[root] in (0x06, 0x0C, 0x0E, 0x10), hex(root)
        w = wing_info(c, part); assert w['sx'] == S['sx']
        assert set(w['surf']) == {'top', 'bot'}, w['surf'].keys()
        per[side] = dict(c4=c4, part=part, root=root, w=w)

    def gen(L):
        """block bytes, relocs (relative to tail), patches {offset: bytes} for code before tail"""
        thunk_new = thunk_old + L
        relocs, patches = [], {}
        blk = bytearray()
        here = lambda: tail + len(blk)
        def f0jmp(at, to):
            relocs.extend([at + 3 - tail, at + 8 - tail])
            return b'\xf0\x00\x68' + struct.pack('<I', VA(to)) + b'\x68' + struct.pack('<I', thunk_new) + b'\xc3'
        FLAG = tail + L - 2                       # flag byte at the very end of the block
        info = {}
        for side, S in SIDES.items():
            q = per[side]; part = q['part']; w = q['w']; sx = S['sx']
            x0, x1 = sx * X0, sx * X1
            F0p, F1p = (x0, round(w['F'](x0)), 0), (x1, round(w['F'](x1)), 0)
            T0p, T1p = (x0, round(w['TE'](x0)), 0), (x1, round(w['TE'](x1)), 0)
            Dp = (x0, F0p[1] + DIR_IN[0], DIR_IN[1]); Cp = (x1, F1p[1] + DIR_OUT[0], DIR_OUT[1])
            NV = [F0p, F1p, Cp, Dp, T0p, T1p]           # slots 800..805
            sl = {p: SLOT + i for i, p in enumerate(NV)}
            uvm = w['uvm']
            def face(pts, uvs, out):
                o = oriented(pts, list(range(len(pts))), out)
                idx = []
                for i in o:
                    p = pts[i]
                    idx.append(sl[p] if p in sl else SLOT - 1000)   # placeholder, replaced below
                return o
            def mkface(pts, uvlist, out, vidx):
                o = oriented(pts, list(range(len(pts))), out)
                return face_bytes(FL, COL, [vidx[i] for i in o], [pts[i] for i in o], [uvlist[i] for i in o])
            # flap (deflected strip): A=F0p B=F1p C D ; uv: hinge = band front, C/D = trailing edge
            fP = [F0p, F1p, Cp, Dp]; fuv = [uvm(x0, round(w['F'](x0))), uvm(x1, round(w['F'](x1))), uvm(x1, T1p[1]), uvm(x0, T0p[1])]
            fidx = [SLOT + 0, SLOT + 1, SLOT + 2, SLOT + 3]
            flapfaces = mkface(fP, fuv, (0, -3, 4), fidx) + mkface(fP, fuv, (0, 3, -4), fidx) + b'\x1e'
            # --- area at the old 82 ---
            T0a = part; NF = part + 13; FJ = part + 32; ST = part + 45
            # --- block ---
            b_start = here()
            blk += struct.pack('<BBHH', 0x82, 0, len(NV), SLOT * 8) + b''.join(struct.pack('<3h', *p) for p in NV)
            blk += bytes(c[part:part + 102]) if 'orig82' not in q else q['orig82']
            ch_at = here()
            chs, ro = chooser(VA(q['c4']), VA(NF), VA(q['root']), thunk_new, VA(FLAG))
            blk += b'\xf0\x00' + chs
            relocs.extend(ch_at + 2 + k - tail for k in ro)
            FACES = here(); blk += flapfaces
            area = f0jmp(T0a, b_start)
            node = struct.pack('<BB6h', 0x06, 0, 0, 0, 16384, 0, 0, 0) + struct.pack('<hh', FJ - (NF + 16), q['root'] - (NF + 18)) + b'\x1e'
            area += node + f0jmp(FJ, FACES)
            # --- band surfaces ---
            hooks = []
            for sname, out in (('top', (0, 0, 1)), ('bot', (0, 0, -1))):
                fs = sorted(w['surf'][sname], key=lambda f: -(f['end'] - f['o']))
                hf, others = fs[0], fs[1:]
                assert hf['end'] - hf['o'] >= 29 + 2 and c[hf['end']] == 0x1E
                pts = {}
                for f in fs:
                    for p, uv in zip(f['P'], f['uv']): pts.setdefault(p, uv)
                rootpts = sorted({p for p in pts if p[0] == w['rootx']}, key=lambda p: -p[1])
                tipF = next(p for p in pts if p[0] == w['tipx'] and p[1] == -28)
                tipT = next(p for p in pts if p[0] == w['tipx'] and p[1] == -32)
                vidx = {p: SLOT + i for i, p in enumerate(NV)}
                for f in fs:
                    for p, i in zip(f['P'], f['idx']): vidx.setdefault(p, i)
                uvd = dict(pts); uvd.update({F0p: fuv[0], F1p: fuv[1], T0p: fuv[3], T1p: fuv[2]})
                def poly(ps): return mkface(ps, [uvd[p] for p in ps], out, [vidx[p] for p in ps])
                strip = poly([F0p, T0p, T1p, F1p])
                pieces = poly(rootpts + [T0p, F0p]) + poly([F1p, T1p, tipT, tipF])
                hooks.append((sname, hf, others, strip, pieces))
            # top strip lives in the area (after FJ), followed by an F0 jump to its pieces in the block
            for sname, hf, others, strip, pieces in hooks:
                if sname == 'top' and len(area) + len(strip) + 13 <= 102:
                    ORIG = part + len(area)
                    area += strip
                    ALT = here(); area += f0jmp(part + len(area), ALT)
                    blk += pieces
                else:
                    ORIG = here(); blk += strip
                    ALT = here(); blk += pieces
                back = here(); blk += f0jmp(back, hf['end'])
                hk, ro = hook(VA(FLAG), VA(ORIG), VA(ALT), thunk_new)
                hb = b'\xf0\x00' + hk
                assert len(hb) <= hf['end'] - hf['o'], (len(hb), hf['end'] - hf['o'])
                patches[hf['o']] = hb + b'\x00' * (hf['end'] - hf['o'] - len(hb))
                relocs.extend(hf['o'] + 2 + k - tail for k in ro)
                for f in others:            # 38 rel16: jump to the face's end (its 1E)
                    patches[f['o']] = b'\x38' + struct.pack('<h', f['end'] - (f['o'] + 3))
                info[side, sname] = (hex(hf['o']), [hex(f['o']) for f in others], len(strip), len(pieces))
            assert len(area) <= 102, len(area)
            patches[part] = bytes(area) + b'\x00' * (102 - len(area))
            info[side] = dict(NV=NV, area=len(area))
        blk += b'\x00' * (L - len(blk)) if len(blk) <= L else b''
        return blk, relocs, patches, info

    blk, *_ = gen(0)
    L = len(blk) + 2; L += L % 2
    room = nxt - code['va'] - len(c)
    if L > room:
        return None, L - room
    blk, relocs, patches, info = gen(L)
    assert len(blk) == L, (len(blk), L)
    for o, b in patches.items(): c[o:o + len(b)] = b
    print('  block', L, 'room', room)
    out = insert_blocks(d, pe, secs, code, c, tail, bytes(blk), relocs)
    return out, info


def main():
    src, dst = sys.argv[1:3]
    d = bytes(open(src, 'rb').read())
    out, info = build(d)
    if out is None:
        d = bytes(grow_vas(d, 0x1000))
        out, info = build(d)          # build() re-reads CODE from the grown file
    assert out is not None and len(out) < 65536, len(out or b'')
    open(dst, 'wb').write(out)
    for k, v in info.items(): print(k, v)
    print(f'{dst}: {len(out)} B')


if __name__ == '__main__':
    main()
