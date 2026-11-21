#!/usr/bin/env python3
"""F/A-18 parked wing fold (Kuoyi 2026-11-20, same rules as the F-14 parked oversweep in f14_park_sweep.py / F14-50):
the outer wing panels fold up when the aircraft sits on the ground (runway, carrier deck, rooftop), stopped,
gear down; they spread again as soon as it moves, and within 3 s when the afterburner is lit (catapult launch,
speed 0).

Geometry (main LOD only):
  * Hinge line x = ±H (parallel to the centreline, like the real jet), just outboard of the hp7 pylon (x 41..42).
  * Every main-LOD wing face that crosses the hinge is clipped there.  The inboard piece is rewritten in place
    (same plane, same draw-order slot in the BSP), using new hinge vertices loaded at slot HSLOT before the body is
    drawn; the outboard piece goes into a new C4 part (one per side) whose origin is the hinge point.  UVs are
    interpolated along the cut edges, so the texture is unchanged when spread.
  * The C4 roll of each panel part is written every frame by the x86 below (+ = up for x > 0, - for x < 0).
  * The wingtip AIM-9 slot (stores R8 / L8 from f18_stores.py) is taken out of the body's tree and called from
    inside the panel part, its C4 positions turned into panel-local ones, so the missile folds with the wing.

Draw order: the panels are separated from everything else by a 45 deg plane through each hinge line
((x - H) + (up - uh) >= 0 on the right): that holds for any fold angle 0..~100 deg, and the stores below the wing
(hp7 at x 42, fins to 45) stay on the body side.

Entry: the root hook at the start of the main LOD (`12 00 -> BODY` written by f18_stores.py) is too far from the
new block for rel16, so it becomes an F0 trampoline (push block VA; push do_start_interp; ret), and the block
ends with another trampoline back to where the hook continued.

x86 (fold progress per aircraft, table of 16 x 8 B, object index & 15): same test as F14-50:
  parked = gear down (obj+0x16F bit 0x40) && |speed obj+0x34| < 1 ft/s && y - [obj+0x2F] <= AGL_MAX
  afterburner (bit 0x20) -> target 0 (spread) regardless of speed.  Fold over FOLD_MS, unfold over UNF_MS,
  snap to the target when the aircraft is new or unseen > 1 s (a jet parked at mission start is already folded).
Usage: python3 f18_wing_fold.py in.SH out.SH [--folded]   (--folded: static roll = full fold, for previews)
"""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, parse_face, insert_blocks, main_lod
from f18g_growler import grow_vas
from f18_stores import find_thunk
import keystone

SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])
H = 44                   # hinge |x|
UH = 1                   # hinge height (wing surface there is up 1..2)
FOLD_DEG = 95            # real jet: panels fold to about vertical
FOLD = round(FOLD_DEG * 65536 / 360)
AGL_MAX = 24 * 256       # F-18 bbox ymin -21 ft + 3 ft
FOLD_MS = 4000
UNF_MS = 3000
HSLOT = 463              # hinge vertices: 463..479 are free in F18 (parts: 337-462, stores 480+, gear 594+)
OVERLAP = 1              # panel faces start this far inboard of the hinge: FA places C4 parts to whole units
                         # (eye fraction dropped), so an exact joint shows a 1-unit seam on one side (F18-21)
PSLOT = 700              # panel part vertices
MAIN_END = 0x39e5        # end of the main LOD body bytecode (first part buffer); set per file by layout()
ROOT_HOOK = 0xe15        # `12 00 rel -> BODY; 38 -> 0xe27; 1E..` (f18_stores.py hook of the main root); layout()
MAIN_AT = 0x80           # main-LOD vertex buffer (82 00 n 0); F18C/E/T have it at 0x81; layout()
TIP_ST = 8               # wingtip station (PT hardpoint) whose store folds with the panel (F18U: 7)


def layout(c):
    """Find MAIN_AT, MAIN_END and ROOT_HOOK in this file (every F/A-18 variant has its own offsets)."""
    global MAIN_AT, MAIN_END, ROOT_HOOK
    L = main_lod(c)
    MAIN_AT, MAIN_END = L[0][0], L[1][0]
    r = L[0][3]
    while c[r] == 0xF6: r += 7
    ROOT_HOOK = r


def code_of(d):
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE')
    return pe, secs, code, bytearray(d[code['ro']:code['ro'] + code['vs']])


def main_faces(c):
    """Main-LOD vertex buffer (slot 0) and every FC face of the main body reached by a linear walk of the BSP
    region (faces are leaves between nodes; parse_face validates them)."""
    n = struct.unpack_from('<H', c, MAIN_AT + 2)[0]
    V = [struct.unpack_from('<hhh', c, MAIN_AT + 6 + 6 * k) for k in range(n)]     # (x, fwd, up)
    faces = []
    p = MAIN_AT + 6 + 6 * n
    while p < MAIN_END:
        if c[p] == 0xFC:
            f = parse_face(c, p)
            if f and f['fl'] & 0x400 and all(i < n for i in f['idx']) and f['end'] <= MAIN_END:
                faces.append(f); p = f['end']; continue
        p += 1
    return V, faces


def clip(P, s, H=None):
    if H is None: H = globals()['H']
    """P: [(xyz, uv, idx)], s = +1 / -1 side.  Returns (inner, outer) polygons; cut points are on x = s*H, rounded
    (idx None)."""
    inner, outer = [], []
    k = len(P)
    for i in range(k):
        a, b = P[i], P[(i + 1) % k]
        ia, ib = s * a[0][0] <= H, s * b[0][0] <= H
        (inner if ia else outer).append(a)
        if ia != ib:
            t = (H - s * a[0][0]) / (s * b[0][0] - s * a[0][0])
            q = (s * H, round(a[0][1] + t * (b[0][1] - a[0][1])), round(a[0][2] + t * (b[0][2] - a[0][2])))
            uv = tuple(round(a[1][j] + t * (b[1][j] - a[1][j])) for j in range(2))
            inner.append((q, uv, None)); outer.append((q, uv, None))
    dedup = lambda L: [L[i] for i in range(len(L)) if L[i][0] != L[i - 1][0]]
    return dedup(inner), dedup(outer)


def face_bytes(f, idx, uv, wide):
    fl = f['fl'] if wide else f['fl'] & ~0x400
    u8 = fl & 0x100 and all(0 <= v <= 255 for t in uv for v in t)    # u8 UV faces stay u8 when they still fit
    if not u8: fl &= ~0x100
    b = bytearray([0xFC]) + struct.pack('<HH', fl, f['col']) + f['head'][4:]
    b += bytes([len(idx)])
    b += b''.join(struct.pack('<H', i) for i in idx) if wide else bytes(idx)
    b += b''.join(struct.pack('<BB' if u8 else '<HH', *t) for t in uv)
    return b


def fold_x86(nx_rel_tbl, nx_rel_r, nx_rel_l):
    """F0 body after `push contVA` (first instruction, so viewers that follow the first push still work).
    ebx = VA of label nx; table / C4 roll fields addressed relative to it."""
    return f"""
        pushfd
        pushad
        call nx
    nx:
        pop ebx
        xor edi, edi
        xor eax, eax
        mov ecx, dword ptr [0x51ce26]
        test ecx, ecx
        jle done
        movzx edx, word ptr [0x580bec]
        cmp cx, dx
        jne done
        mov esi, dword ptr [edx*4 + 0x553848]
        test esi, esi
        je done
        cmp byte ptr [esi], 4
        jne done
        mov ecx, edx
        test byte ptr [esi + 0x16f], 0x40
        jz notp
        mov edx, dword ptr [esi + 0x34]
        add edx, 0xff
        cmp edx, 0x1fe
        ja notp
        mov edx, dword ptr [esi + 0x15]
        sub edx, dword ptr [esi + 0x2f]
        cmp edx, {AGL_MAX}
        jg notp
        mov edi, 1024
    notp:
        test byte ptr [esi + 0x16f], 0x20
        jz noab
        xor edi, edi
    noab:
        mov eax, ecx
        and eax, 15
        lea edx, [ebx + eax*8 + {nx_rel_tbl}]
        push edx
        push ecx
        call dword ptr [0x593758]
        pop ecx
        pop edx
        cmp word ptr [edx], cx
        jne snap
        mov esi, eax
        sub esi, dword ptr [edx + 4]
        cmp esi, 1000
        ja snap
        mov dword ptr [edx + 4], eax
        movzx eax, word ptr [edx + 2]
        cmp eax, edi
        jl up
        imul esi, esi, {round(1024 * 1024 / UNF_MS)}
        shr esi, 10
        sub eax, esi
        cmp eax, edi
        jge store
        mov eax, edi
        jmp store
    up:
        imul esi, esi, {round(1024 * 1024 / FOLD_MS)}
        shr esi, 10
        add eax, esi
        cmp eax, edi
        jle store
        mov eax, edi
        jmp store
    snap:
        mov word ptr [edx], cx
        mov dword ptr [edx + 4], eax
        mov eax, edi
    store:
        mov word ptr [edx + 2], ax
        imul eax, eax, {FOLD}
        sar eax, 10
    done:
        mov word ptr [ebx + {nx_rel_r}], ax
        neg eax
        mov word ptr [ebx + {nx_rel_l}], ax
        popad
        popfd
    """


def find_tip_stubs(c, tail):
    """f18_stores.py slot stubs for station 8 (wingtip): `F0 00 68 imm32(8 | rank<<8 | kind<<16) E8 rel32` + an i16
    table of C4 lists per kind.  Returns {side: (stub offset, [list offsets])}."""
    out = {}
    for rank, s in ((2, +1), (1, -1)):
        hits = [i for i in range(tail - 12) if c[i:i+3] == b'\xf0\x00\x68' and c[i+3] == TIP_ST and c[i+4] == rank and c[i+6] == 0
                and c[i+7] == 0xE8]
        assert len(hits) == 1, (rank, hits)
        o = hits[0]; tb = o + 12
        tgts = [tb + struct.unpack_from('<h', c, tb + 2 * k)[0] for k in range(16)]
        first = min(t for t in tgts if t > tb and c[t] == 0xC4 and c[t+1] == 0)
        nk = (first - tb) // 2
        lists = sorted(t for t in set(tgts[:nk]) if c[t] == 0xC4 and c[t+1] == 0)
        assert lists[0] == tb + 2 * nk and all(c[t+16:t+18] == b'\x00\x00' for t in lists), hex(o)
        out[s] = (o, lists)
    return out


def build(d, folded=False, grown=False):
    pe, secs, code, c = code_of(d)
    nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    tail = bytes(c).find(SIG)
    thunk_old = find_thunk(c, tail)               # do_start_interp
    layout(c)
    # the hook at the main root
    assert c[ROOT_HOOK:ROOT_HOOK+2] == b'\x12\x00' and c[ROOT_HOOK+4] == 0x38, c[ROOT_HOOK:ROOT_HOOK+8].hex()
    BODY = ROOT_HOOK + 4 + struct.unpack_from('<h', c, ROOT_HOOK + 2)[0]
    CONT = ROOT_HOOK + 7 + struct.unpack_from('<h', c, ROOT_HOOK + 5)[0]
    assert c[BODY] in (0x06, 0x0C, 0x0E, 0x10) and c[CONT] == 0x38, (hex(BODY), hex(CONT))

    V, faces = main_faces(c)
    hinge = {}                                   # (x, fwd, up) -> slot
    inner_new, parts = {}, {+1: [], -1: []}
    canon = {}                                   # (side, top surface) -> cut points already used
    def snap(poly, s, top):
        """Cut points of neighbouring faces on the same surface that round to within 1 unit become one vertex:
        the rounded cut of two non-collinear edges otherwise leaves a sliver crack (F18-21/22, x>0 underside)."""
        L = canon.setdefault((s, top), [])
        out = []
        for q, uv, i in poly:
            if i is None:
                m = next((p for p in L if p[0] == q[0] and abs(p[1] - q[1]) <= 1 and abs(p[2] - q[2]) <= 1), None)
                if m is None: L.append(q)
                else: q = m
            out.append((q, uv, i))
        return out
    for f in faces:
        P = [(V[i], f['uv'][k] if f['uv'] else (0, 0), i) for k, i in enumerate(f['idx'])]
        xs = [p[0][0] for p in P]
        top = struct.unpack_from('<3h', f['head'], 4)[1] > 0
        for s in (+1, -1):
            if max(s * x for x in xs) <= H - OVERLAP: continue
            assert min(s * x for x in xs) > -H, 'face crosses both hinges'
            assert f['uv'] is not None, 'expects a textured face'
            inn = snap(clip(P, s)[0], s, top)
            out = snap(clip(P, s, H - OVERLAP)[1], s, top)   # panel reaches OVERLAP inboard of the hinge (no seam)
            if len(out) >= 3: parts[s].append((f, out, top))
            if max(s * x for x in xs) <= H: continue
            if len(inn) >= 3:
                idx = [i if i is not None else hinge.setdefault(q, HSLOT + len(hinge)) for q, uv, i in inn]
                inner_new[f['o']] = (s, idx, [t[1] for t in inn])
            else:
                inner_new[f['o']] = (s, None, None)
    # T-vertices: a vertex of a neighbouring panel face lying just outside an edge (within 1 unit) is added to
    # that edge, so the two faces meet instead of leaving a sliver (original F18 has one at (39,-10)-(46,-7)-(52,-3)
    # on the x>0 underside; folded it shows as a light crack).
    import numpy as np
    for s in (+1, -1):
        for n_, (f, poly, top) in enumerate(parts[s]):
            others = {q for g, pp, t in parts[s] if t == top and g is not f for q, _, _ in pp}
            A = np.array([[q[0], q[1], 1] for q, _, _ in poly], float)
            U = np.array([uv for _, uv, _ in poly], float)
            coef = np.linalg.lstsq(A, U, rcond=None)[0]
            k = 0
            while k < len(poly):
                a, b = poly[k][0], poly[(k + 1) % len(poly)][0]
                ex, ef = b[0] - a[0], b[1] - a[1]; L2 = ex * ex + ef * ef
                best = None
                for q in others:
                    t = ((q[0] - a[0]) * ex + (q[1] - a[1]) * ef) / L2 if L2 else -1
                    dist = abs((q[0] - a[0]) * ef - (q[1] - a[1]) * ex) / L2 ** 0.5 if L2 else 9
                    if 0.05 < t < 0.95 and 0 < dist < 1.0 and q not in (a, b):
                        new = poly[:k + 1] + [(q, None, None)] + poly[k + 1:]
                        P2 = [p[0] for p in new]
                        cr = [(P2[(j+1) % len(P2)][0] - P2[j][0]) * (P2[(j+2) % len(P2)][1] - P2[(j+1) % len(P2)][1]) -
                              (P2[(j+1) % len(P2)][1] - P2[j][1]) * (P2[(j+2) % len(P2)][0] - P2[(j+1) % len(P2)][0]) for j in range(len(P2))]
                        if all(x >= 0 for x in cr) or all(x <= 0 for x in cr): best = q; break
                if best is not None:
                    uv = tuple(int(round(v)) for v in np.array([best[0], best[1], 1.0]) @ coef)
                    poly.insert(k + 1, (best, uv, None))
                    print(f'  panel face {f["o"]:#x}: T-vertex {best} added')
                k += 1
        parts[s] = [(f, poly) for f, poly, top in parts[s]]
    assert HSLOT + len(hinge) <= 480, len(hinge)
    print(f'hinge |x|={H}: {len(hinge)} new hinge vertices, {len(inner_new)} faces clipped, '
          f'panel faces R {len(parts[1])} L {len(parts[-1])}')

    # ---- inboard pieces in place.  A piece that grew (quad -> pentagon, triangle -> quad) keeps a fan piece that
    # fits its slot; the leftover triangle goes into the slot of a removed (wholly outboard) face of the same wing
    # surface (same side, closest normal), i.e. drawn from a nearby leaf of the same surface.
    fo = {x['o']: x for x in faces}
    nrm = lambda f: struct.unpack_from('<3h', f['head'], 4)
    def put(o, end, nb):
        assert len(nb) == end - o or len(nb) + 3 <= end - o, (hex(o), len(nb), end - o)
        c[o:o+len(nb)] = nb
        if len(nb) < end - o: c[o+len(nb):o+len(nb)+3] = b'\x38' + struct.pack('<h', end - (o + len(nb) + 3))
    removed = [o for o, (s_, idx, uv) in inner_new.items() if idx is None]
    leftovers = []
    for o, (s_, idx, uv) in inner_new.items():
        f = fo[o]; size = f['end'] - o
        if idx is None:
            c[o:o+3] = b'\x38' + struct.pack('<h', f['end'] - (o + 3)); continue
        nb = face_bytes(f, idx, uv, True)
        if len(nb) == size or len(nb) + 3 <= size: put(o, f['end'], nb); continue
        k = len(idx) - 1                             # fan: first k vertices stay, triangle (0, k-1, k) moves
        assert len(face_bytes(f, idx[:k], uv[:k], True)) <= size and k == len(idx) - 1, hex(o)
        put(o, f['end'], face_bytes(f, idx[:k], uv[:k], True))
        leftovers.append((f, s_, [idx[0], idx[k-1], idx[k]], [uv[0], uv[k-1], uv[k]]))
    for f, s_, idx, uv in leftovers:
        nb = face_bytes(f, idx, uv, True); n0 = nrm(f)
        cand = [o for o in removed if inner_new[o][0] == s_ and (fo[o]['end'] - o == len(nb) or fo[o]['end'] - o >= len(nb) + 3)]
        o = max(cand, key=lambda o: sum(a * b for a, b in zip(nrm(fo[o]), n0)))
        assert sum(a * b for a, b in zip(nrm(fo[o]), n0)) > 0.9 * 32767 ** 2, ('no same-surface slot', hex(f['o']))
        removed.remove(o)
        put(o, fo[o]['end'], nb)
        print(f'  face {f["o"]:#x}: leftover triangle drawn in removed slot {o:#x}')
    far = []
    # ---- wingtip AIM-9 slots: out of the body tree, into the panel parts (panel-local C4 positions)
    stubs = find_tip_stubs(c, tail)
    for s, (o, lists) in stubs.items():
        calls = [i for i in range(tail - 4) if c[i:i+2] == b'\x12\x00' and i + 4 + struct.unpack_from('<h', c, i+2)[0] == o]
        assert len(calls) == 1, (s, calls)
        i = calls[0]; c[i:i+4] = b'\x38\x01\x00\x1e'          # jump over the call (to what followed it)
        for t in lists:
            x, u, fw = struct.unpack_from('<3h', c, t + 2)
            struct.pack_into('<3h', c, t + 2, x - s * H, u - UH, fw)

    # ---- new block
    hdr_src = next(t for t in (i + 16 + struct.unpack_from('<h', c, i+14)[0] for i in range(MAIN_END, tail - 16)
                               if c[i] == 0xC4 and c[i+1] == 0) if c[t] == 0x82 and c[t+1] == 0)
    HDR = bytes(c[hdr_src-6:hdr_src])

    def part_bytes(s, at):
        """at = offset of the part's 82 (after HDR).  Panel-local coords: origin (s*H, fwd 0, UH)."""
        pv = []
        fb = bytearray()
        for f, poly in parts[s]:
            idx = []
            for q, uv, _ in poly:
                lq = (q[0] - s * H, q[1], q[2] - UH)
                if lq not in pv: pv.append(lq)
                idx.append(PSLOT + pv.index(lq))
            # plane point (i8 x, up, fwd when 0x200) moves into the panel frame too
            f2 = dict(f); head = bytearray(f['head'])
            if f['fl'] & 0x60:
                if f['fl'] & 0x200:
                    px, pu, pf = struct.unpack_from('<3b', head, 10)
                    struct.pack_into('<3b', head, 10, px - s * H, pu - UH, pf)
                else:
                    px, pu, pf = struct.unpack_from('<3h', head, 10)
                    struct.pack_into('<3h', head, 10, px - s * H, pu - UH, pf)
            f2['head'] = bytes(head)
            fb += face_bytes(f2, idx, [t[1] for t in poly], True)
        b = bytearray(struct.pack('<BBHH', 0x82, 0, len(pv), PSLOT * 8)) + b''.join(struct.pack('<3h', *v) for v in pv)
        b += fb
        # tip store after the panel: tail jump (F0 trampoline; the stub is out of rel16 reach) into the slot stub,
        # whose C4 list ends with 00 00 = the end of this part
        jmp_at = at + len(b)
        b += b'\xf0\x00' + b'\x68' + struct.pack('<I', VA(stubs[s][0])) + b'\x68' + struct.pack('<I', VA(thunk_new)) + b'\xc3'
        relocs.extend([jmp_at + 3 - tail, jmp_at + 8 - tail])
        return bytes(b)

    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    asm = lambda src: bytes(ks.asm(src, 0)[0])
    # layout: [F0 00][push contVA][x86 ... push thunk; ret][82 hinge][nodeR][nodeL][leafR][leafL][tbl][HDR partR][HDR partL]
    x0 = fold_x86(0x1000, 0x1000, 0x1000)
    probe = asm(x0)
    pre = 7 + 2                                   # pushfd pushad call(5) -> nx at +7 of the x86 (after push contVA)
    X86_AT = 2 + 5                                # after F0 00 + push imm32
    x86_len = len(probe) + 5 + 1                  # + push thunk + ret
    o = tail
    lay = {}
    lay['F0'] = o; o += X86_AT + x86_len
    lay['HV'] = o; o += 6 + 6 * len(hinge)
    lay['NR'] = o; o += 18                        # executed inline after the 82, then falls into BACK
    lay['BACK'] = o; o += 13
    o += o % 2
    lay['BODYT'] = o; o += 13                     # BODY is out of rel16 reach: F0 tail jump to it
    o += o % 2
    lay['NL'] = o; o += 20
    lay['LR'] = o; o += 18
    lay['LL'] = o; o += 18
    for i, (fo, nb, end) in enumerate(far):
        lay['OV', i] = o; o += len(nb) + 13
    o += o % 2
    lay['TBL'] = o; o += 16 * 8
    VA = lambda off: code['va'] + off
    relocs, thunk_new = [], 0
    lay['PR'] = o + len(HDR); pr = part_bytes(+1, lay['PR']); o += len(HDR) + len(pr); o += o % 2
    lay['PL'] = o + len(HDR); pl = part_bytes(-1, lay['PL']); o += len(HDR) + len(pl); o += o % 2
    L = o - tail
    ks_ = sorted(lay.items(), key=lambda kv: kv[1]); print('  layout', [(str(k), v - tail) for k, v in ks_], 'end', L)
    room = nxt - code['va'] - len(c)
    print(f'  block {L} B, room {room} B')
    if L > room:
        assert not grown
        return None, L - room
    thunk_new = thunk_old + L
    relocs = []
    pr = part_bytes(+1, lay['PR']); pl = part_bytes(-1, lay['PL'])
    nx = lay['F0'] + X86_AT + 7                   # label nx inside the x86
    roll_r, roll_l = lay['LR'] + 12, lay['LL'] + 12
    x86 = asm(fold_x86(lay['TBL'] - nx, roll_r - nx, roll_l - nx))
    assert len(x86) == len(probe), (len(x86), len(probe))
    blk = bytearray()
    blk += b'\xf0\x00' + b'\x68' + struct.pack('<I', VA(lay['HV']))
    blk += x86 + b'\x68' + struct.pack('<I', VA(thunk_new)) + b'\xc3'
    relocs += [lay['F0'] + 3 - tail, lay['F0'] + X86_AT + len(x86) + 1 - tail]
    assert len(blk) == lay['HV'] - tail
    blk += struct.pack('<BBHH', 0x82, 0, len(hinge), HSLOT * 8)
    for q, sl in sorted(hinge.items(), key=lambda kv: kv[1]): blk += struct.pack('<3h', *q)
    # nodes: value = n.(eye + d), >= 0 -> A then B
    k45 = 11585
    def node(at, n, dd, a, b):
        return struct.pack('<BB6h', 0x06, 0, n[0], dd[0], n[1], dd[1], n[2], dd[2]) + \
            struct.pack('<hh', a - (at + 16), b - (at + 18)) + b'\x00\x00'
    assert len(blk) == lay['NR'] - tail
    blk += node(lay['NR'], (k45, k45, 0), (-H, -UH, 0), lay['NL'], lay['LR'])[:18]
    # after the body and panels: back to where the root hook continued (CONT)
    assert len(blk) == lay['BACK'] - tail
    blk += b'\xf0\x00' + b'\x68' + struct.pack('<I', VA(CONT)) + b'\x68' + struct.pack('<I', VA(thunk_new)) + b'\xc3'
    relocs += [lay['BACK'] + 3 - tail, lay['BACK'] + 8 - tail]
    blk += b'\x00' * (lay['BODYT'] - tail - len(blk))
    blk += b'\xf0\x00' + b'\x68' + struct.pack('<I', VA(BODY)) + b'\x68' + struct.pack('<I', VA(thunk_new)) + b'\xc3'
    relocs += [lay['BODYT'] + 3 - tail, lay['BODYT'] + 8 - tail]
    blk += b'\x00' * (lay['NL'] - tail - len(blk))
    blk += node(lay['NL'], (-k45, k45, 0), (H, -UH, 0), lay['BODYT'], lay['LL'])
    roll0 = FOLD if folded else 0
    for at, s, part in ((lay['LR'], +1, lay['PR']), (lay['LL'], -1, lay['PL'])):
        blk += struct.pack('<BB6h', 0xC4, 0, s * H, UH, 0, 0, 0, s * roll0) + struct.pack('<h', part - (at + 16)) + b'\x00\x00'
    for i, (fo, nb, end) in enumerate(far):      # face copy, then F0 back to the end of the original face
        assert len(blk) == lay['OV', i] - tail
        blk += nb
        q = len(blk) + tail
        blk += b'\xf0\x00' + b'\x68' + struct.pack('<I', VA(end)) + b'\x68' + struct.pack('<I', VA(thunk_new)) + b'\xc3'
        relocs += [q + 3 - tail, q + 8 - tail]
        c[fo:fo+13] = b'\xf0\x00' + b'\x68' + struct.pack('<I', VA(lay['OV', i])) + b'\x68' + struct.pack('<I', VA(thunk_new)) + b'\xc3'
        relocs += [fo + 3 - tail, fo + 8 - tail]
    blk += b'\x00' * (lay['TBL'] - tail - len(blk))
    blk += bytes(16 * 8)
    blk += HDR + pr + b'\x00' * ((lay['PL'] - len(HDR)) - (lay['PR'] + len(pr)))
    blk += HDR + pl
    blk += b'\x00' * (L - len(blk))
    assert len(blk) == L
    # root hook -> F0 trampoline to the block (13 bytes over the 18-byte hook area; CONT jump kept after it)
    t = bytearray(b'\xf0\x00' + b'\x68' + struct.pack('<I', VA(lay['F0'])) + b'\x68' + struct.pack('<I', VA(thunk_new)) + b'\xc3')
    c[ROOT_HOOK:ROOT_HOOK + len(t)] = t
    relocs += [ROOT_HOOK + 3 - tail, ROOT_HOOK + 8 - tail]
    return insert_blocks(d, pe, secs, code, c, tail, bytes(blk), relocs), lay


def main():
    src, dst = sys.argv[1:3]
    d = bytes(open(src, 'rb').read())
    out, lay = build(d, '--folded' in sys.argv)
    if out is None:
        d = grow_vas(d, 0x1000)
        out, lay = build(d, '--folded' in sys.argv, grown=True)
    assert len(out) < 65536, len(out)
    open(dst, 'wb').write(out)
    print(f'{dst}: {len(out)} B')


if __name__ == '__main__':
    main()
