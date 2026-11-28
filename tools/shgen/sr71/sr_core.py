"""New-shape SH builder (mass-upgrade thread, 2026-11-27): a generated high LOD (fuselage lofts, lifting
surfaces, canopy, gear parts, propeller / rotor discs) wrapped into a donor SH's PE file.

Method = the Airwolf pipeline (tools/shgen/glb2sh, proven in game: gear C4 parts with the 14-byte part header,
rotor discs with op 40 frames, F6 Gouraud normals, painter tree from bsp.Order):
  * donor keeps: PE wrapper, header ops (F2, C8 LOD switches, A6 detail skip, E2 texture), the import thunks
    (_PLgearDown, _PLgearPos, ... , do_start_interp), the F2 trailer and the signature
  * replaced: everything from the first 82 up to the trailer (all of the donor's LODs); the C8 switches point at
    the E2 op, so the new high LOD is drawn at every distance; A6 points at a '1E 1E' in the new block
  * header: CODE+4 bounding radius, CODE+8 EXT (x, up, fwd) ~2.3x the extents, trailer radius + bbox from the
    new geometry (ground = lowest wheel point)
Mesh coordinates: (x right, y fwd, z up), SH units.
"""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, os.path.join(HERE, '..', 'shuttle'))
for p in (os.path.join(REPO, 'tools', 'shgen', 'glb2sh'), os.path.join(REPO, 'tools', 'shgen'), os.path.join(HERE, '..'), HERE):
    if p not in sys.path: sys.path.insert(0, p)
import numpy as np
import bsp
from bsp import Face, Obj, Order, count
from shasm import Asm
from mesh import Mesh
from sh_subdivide import pe_sections
from f18g_growler import grow_vas

from sh_inspect import load, thunks
import hdr

bsp.EPS = 0.6
SAR = lambda k: b'\x66\xC1\xF8' + bytes([k])
NEG = b'\x66\xF7\xD8'
PART_HDR_PREFIX = bytes.fromhex('ffff00006a000800')        # + EXT (3 words) = 14 bytes before each part 82
GLASS_UV = None                                            # (u, v, size) of a glass texture patch, or None = flat


# ------------------------------------------------------------------ face bytes
def fbytes(ids, V, col, nrm, flat):
    P = np.array([V[i] for i in ids], float)
    fl = 0x270 | (0x01 if flat else 0x03)
    if any(i > 255 for i in ids): fl |= 0x400
    n = nrm
    nn = [int(round(n[0] * 32767)), int(round(n[2] * 32767)), int(round(n[1] * 32767))]
    cen = P.mean(0); pt = [int(round(cen[0])), int(round(cen[2])), int(round(cen[1]))]
    if any(abs(x) > 127 for x in pt): fl &= ~0x200
    b = bytearray(struct.pack('<BHH', 0xFC, fl, col)) + struct.pack('<hhh', *nn)
    b += struct.pack('<bbb', *pt) if fl & 0x200 else struct.pack('<hhh', *pt)
    b.append(len(ids))
    b += b''.join(struct.pack('<H', i) for i in ids) if fl & 0x400 else bytes(ids)
    return bytes(b)


def tex_face(ids, V, nrm, uv):
    P = np.array([V[i] for i in ids], float)
    nn = [int(round(nrm[0] * 32767)), int(round(nrm[2] * 32767)), int(round(nrm[1] * 32767))]
    cen = P.mean(0); pt = [int(round(cen[0])), int(round(cen[2])), int(round(cen[1]))]
    fl = 0x64C
    if any(abs(x) > 127 for x in pt): fl &= ~0x200
    b = bytearray(struct.pack('<BHH', 0xFC, fl, 0)) + struct.pack('<hhh', *nn)
    b += struct.pack('<bbb', *pt) if fl & 0x200 else struct.pack('<hhh', *pt)
    b.append(len(ids)); b += b''.join(struct.pack('<H', i) for i in ids)
    b += b''.join(struct.pack('<HH', u, v) for u, v in uv)
    return bytes(b)


class DeepOrder(Order):
    """bsp.Order with a deeper split limit (big multi-part meshes hit depth 40 and fell back to a cyclic list)."""
    MAXD = 40

    def build(s, faces, objs, depth=0):
        faces = [f for f in faces if f is not None]
        els = faces + objs
        if not els: return ('leaf', [], [])
        E = bsp.occl_graph(els)
        comps = bsp.sccs(E)
        big = [c for c in comps if len(c) > 1]
        if not big or depth > s.MAXD:
            # i -> j means i may obscure j, so j is drawn first. Tarjan pops a component only after
            # every component it reaches, so its output order is already the draw order.
            # a cycle left at the depth limit is drawn with the faces sorted by plane offset (n . centre): a detail
            # sitting on the hull (window, windscreen, exhaust) has the larger offset, so it is drawn after the hull
            def key(v):
                e = els[v]
                return e.d if isinstance(e, Face) else -1e9
            order = [els[v] for c in comps for v in (sorted(c, key=key) if len(c) > 1 else c)]
            return ('list', order)
        comp = max(big, key=len)
        cf = [els[v] for v in comp if isinstance(els[v], Face)]
        co = [els[v] for v in comp if not isinstance(els[v], Face)]
        best = None
        planes = [(f.n, f.d) for f in cf]
        for o in co:
            for ax in range(3):
                for val in (o.lo[ax], o.hi[ax]):
                    n = np.zeros(3); n[ax] = 1; planes.append((n, val))
        for n, d in planes:
            sp = fr = bk = 0
            for f in faces:
                k = f.side(n, d); sp += k == 'S'; fr += k == 'F'; bk += k == 'B'
            ost = sum(o.side(n, d) == 'S' for o in objs)
            # progress: plane must split the component
            cs = [els[v].side(n, d) for v in comp]
            if not (any(k in 'FS' for k in cs) and any(k in 'BS' for k in cs)) and not any(k == 'C' for k in cs): continue
            score = sp * 10 + ost * 30 + abs(fr - bk) * 0.05
            if best is None or score < best[0]: best = (score, n, d)
        if best is None: return ('list', [els[v] for c in comps for v in (sorted(c, key=lambda v: els[v].d if isinstance(els[v], Face) else -1e9) if len(c) > 1 else c)])
        _, n, d = best
        F, B, coF, coB = [], [], [], []
        for f in faces:
            k = f.side(n, d)
            if k == 'F': F.append(f)
            elif k == 'B': B.append(f)
            elif k == 'C': (coF if np.dot(f.n, n) > 0 else coB).append(f)
            else:
                a, b = s.split(f, n, d)
                if a: F.append(a)
                if b: B.append(b)
        OF, OB = [], []
        for o in objs:
            k = o.side(n, d)
            if k == 'F': OF.append(o)
            elif k == 'B': OB.append(o)
            else: (OF if np.dot((o.lo + o.hi) / 2, n) - d >= 0 else OB).append(o)
        return ('node', n, d, s.build(B, OB, depth+1), s.build(F, OF, depth+1), coF, coB)


class Tree:
    def __init__(s, V): s.V = V

    def emit(s, a, t):
        if t[0] == 'list':
            for e in t[1]:
                if isinstance(e, Face): s.face(a, e)
                else: e.emit(a)
            return
        if t[0] == 'leaf': return
        _, n, d, A, Bt, coF, coB = t
        la, lb, lend = a.new('A'), a.new('B'), a.new('E')
        p = np.array(n) * d
        nn = [int(round(n[0] * 32767)), int(round(n[2] * 32767)), int(round(n[1] * 32767))]
        dd = [-int(round(p[0])), -int(round(p[2])), -int(round(p[1]))]
        a.node3(nn, dd, la, lb); a.jmp(lend)
        a.label(la)
        for f in coB: s.face(a, f)
        s.emit(a, A); a.ret()
        a.label(lb)
        for f in coF: s.face(a, f)
        s.emit(a, Bt); a.ret()
        a.label(lend)

    def face(s, a, f):
        col, flat = f.col
        if isinstance(col, tuple) and col[0] == 'tex': a.emit(tex_face(f.ids, s.V, f.n, col[1]))
        else: a.emit(fbytes(f.ids, s.V, col, f.n, flat))


def mesh_faces(M, V, smooth_ok=lambda col: True):
    """Mesh -> bsp Faces with (col, flat); a smooth face stays smooth only if all its vertices carry one colour."""
    vcol = {}
    for ids, col, smooth, nrm in M.F:
        for i in ids: vcol.setdefault(i, set()).add(col if not isinstance(col, tuple) else -1)
    faces = []
    for ids, col, smooth, nrm in M.F:
        P = [V[i] for i in ids]
        keep = [k for k in range(len(ids)) if P[k] != P[k - 1]]
        ids = [ids[k] for k in keep]
        if len(set(V[i] for i in ids)) < 3: continue
        flat = (not smooth) or isinstance(col, tuple) or not smooth_ok(col) or any(len(vcol[i]) > 1 for i in ids)
        try: f = Face(ids, [V[i] for i in ids], (col, flat), nrm)
        except Exception: continue
        if not np.isfinite(f.n).all(): continue
        # non-planar polygons (twisted wing panels, rounded vertices) make cycles the painter tree cannot split:
        # triangulate them (fan from the first vertex)
        parts = [ids]
        if len(ids) > 3 and np.abs(np.array([V[i] for i in ids], float) @ f.n - f.d).max() > 0.25:
            parts = [[ids[0], ids[k], ids[k + 1]] for k in range(1, len(ids) - 1)]
        for pid in parts:
            if len(set(V[i] for i in pid)) < 3: continue
            try: g = Face(pid, [V[i] for i in pid], (col, flat), nrm)
            except Exception: continue
            if not np.isfinite(g.n).all(): continue
            if nrm is not None and np.dot(g.n, nrm) < 0:
                pid = pid[::-1]; g = Face(pid, [V[i] for i in pid], (col, flat), nrm)
            g.smooth = smooth
            faces.append(g)
    return faces


def vertex_normals(faces, nV):
    VN = [np.zeros(3) for _ in range(nV)]
    for f in faces:
        if not f.col[1]:
            for i in f.ids: VN[i] += f.n
    for f in faces:
        for i in f.ids:
            if not VN[i].any(): VN[i] = f.n.copy()
    return VN


def shift_tree(t, b):
    seen = set()
    def fx(f):
        if id(f) in seen: return
        seen.add(id(f)); f.ids = [i + b for i in f.ids]
    def walk(t):
        if t[0] == 'list':
            for e in t[1]:
                if isinstance(e, Face): fx(e)
            return
        if t[0] == 'leaf': return
        for f in t[5] + t[6]: fx(f)
        walk(t[3]); walk(t[4])
    walk(t)


# ------------------------------------------------------------------ parts and discs
class Gear:
    """A retracting gear part: mesh in its own frame (pivot at origin, x right, y fwd, z up), drawn by C4 at
    pos while _PLgearDown == 1; the C4 angle `field` (0x08 heading, 0x0A pitch, 0x0C roll) = _PLgearPos >> 1
    (negated if neg): 0 down .. 16383 (90 deg) up."""
    def __init__(s, name, M, pos, field=0x0A, neg=False, shift=1, var='GEARDOWN', anim=True):
        s.name, s.M, s.pos, s.field, s.neg, s.shift = name, M, tuple(int(round(v)) for v in pos), field, neg, shift
        s.var, s.anim = var, anim      # anim=False: a static part drawn while `var` != 0 (e.g. var='AB' for a flame)


class Disc:
    """Animated textured disc (propeller / rotor): 4 corners (mesh coords), normal, frames [(u0, v0, size)]."""
    def __init__(s, name, corners, nrm, frames):
        s.name, s.corners, s.nrm, s.frames = name, corners, nrm, frames


def build(donor, out, M, gears=(), discs=(), pic_name=None, pic_src=None, pic_out=None, grow=0x3000, smooth_ok=lambda c: True,
          ground=None):
    d = bytearray(open(donor, 'rb').read())
    d = bytearray(grow_vas(d, grow))
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    c = bytearray(d[code['ro']:code['ro'] + code['vs']])
    H, _ = hdr.parse(donor)                                    # CODE offsets do not move with grow_vas
    d0, _, secs0, code0, c0 = load(donor)
    th = {v: k for k, v in thunks(d0, secs0, code0, c0).items()}
    R0, R1 = H['r0'], H['trailer']
    VARS = {'GEARDOWN': th['_PLgearDown'], 'GEARPOS': th['_PLgearPos'], 'RESUME': th['do_start_interp']}
    if '_PLafterBurner' in th: VARS['AB'] = th['_PLafterBurner']

    # disc vertices in the main buffer
    dv = {}
    for D in discs: dv[D.name] = [M.add(p) for p in D.corners]
    V = [tuple(int(round(x)) for x in p) for p in M.V]
    faces = mesh_faces(M, V, smooth_ok)
    VN = [list(n) for n in vertex_normals(faces, len(V))]
    vcol = {}
    for f in faces:
        for i in f.ids:
            if not isinstance(f.col[0], tuple): vcol.setdefault(i, f.col[0])

    def add_vertex(p, i, j, t):
        V.append(tuple(int(round(x)) for x in p))
        VN.append(list((1 - t) * np.array(VN[i]) + t * np.array(VN[j]))); vcol[len(V) - 1] = vcol.get(i, 150)
        return len(V) - 1

    # gear parts: own buffers (shared slots after the main buffer)
    part_data = {}
    for G in gears:
        PV = [tuple(int(round(x)) for x in p) for p in G.M.V]
        pf = mesh_faces(G.M, PV, smooth_ok)
        pvn = [np.array(n) for n in vertex_normals(pf, len(PV))]
        pcol = {}
        for f in pf:
            for i in f.ids: pcol.setdefault(i, f.col[0])
        def addv(p, i, j, t, PV=PV, pvn=pvn, pcol=pcol):
            PV.append(tuple(int(round(x)) for x in p)); pvn.append((1 - t) * pvn[i] + t * pvn[j]); pcol[len(PV) - 1] = pcol.get(i, 150)
            return len(PV) - 1
        pt = DeepOrder(PV, addv).build(pf, [])
        P = np.array(PV, float)
        part_data[G.name] = dict(G=G, PV=PV, pvn=pvn, pt=pt, pcol=pcol, lo=P.min(0), hi=P.max(0))

    objs = []
    for G in gears:
        pdat = part_data[G.name]; px, py, pz = G.pos
        def e(a, G=G):
            ops = SAR(G.shift) + (NEG if G.neg else b'')
            if not G.anim:
                a.cond(G.var, 'RESUME', lambda: a.c4((G.pos[0], G.pos[2], G.pos[1]), (0, 0, 0), 'part_' + G.name))
                return
            a.cond(G.var, 'RESUME', lambda: a.patch_c4('GEARPOS', G.field, ops, 'RESUME',
                                                         lambda: a.c4((G.pos[0], G.pos[2], G.pos[1]), (0, 0, 0), 'part_' + G.name)))
        objs.append(Obj('gear_' + G.name, pdat['lo'] + G.pos, pdat['hi'] + G.pos, e))
    for D in discs:
        ids = dv[D.name]; Pc = np.array([M.V[i] for i in ids])
        def e(a, D=D, ids=ids):
            for sgn in (1, -1):
                n = np.array(D.nrm, float) * sgn
                q = list(ids); flip = np.dot(Face(q, [V[i] for i in q], 0).n, n) < 0
                if flip: q = q[::-1]
                labs = [a.new('F') for _ in D.frames]
                a.emit(struct.pack('<BBH', 0x40, 0, len(D.frames)))
                for L in labs: a.rel16(L, -2)
                L_next = a.new('N')
                for L, (u0, v0, sz) in zip(labs, D.frames):
                    a.label(L)
                    uv = [(u0 + sz - 1, v0), (u0, v0), (u0, v0 + sz - 1), (u0 + sz - 1, v0 + sz - 1)]
                    if flip: uv = uv[::-1]
                    a.emit(tex_face(q, V, n, uv))
                    a.emit(b'\x48\x00'); a.rel16(L_next)
                a.label(L_next)
        lo = Pc.min(0) - 0.4; hi = Pc.max(0) + 0.4
        objs.append(Obj(D.name, lo, hi, e))

    B = DeepOrder(V, add_vertex)
    tree = B.build(faces, objs)
    nn, nf = count(tree)
    base = len(V)
    for k, pd in part_data.items(): shift_tree(pd['pt'], base)
    nslots = base + (max(len(pd['PV']) for pd in part_data.values()) if part_data else 0)
    print(f'main: {nn} plane nodes, {nf} faces, {B.splits} splits, {len(V)} vertices; slots {nslots}')
    if nslots > 880: sys.exit('too many vertex slots')

    allP = np.array(V[:base] + [tuple(np.array(v) + pd['G'].pos) for pd in part_data.values() for v in pd['PV']], float)
    ext = np.abs(allP).max(0)                                   # (x, fwd, up)
    EXT = (int(ext[0] * 2.3) + 4, int(ext[2] * 2.3) + 4, int(ext[1] * 2.3) + 4)     # (x, up, fwd)
    part_hdr = PART_HDR_PREFIX + struct.pack('<3H', *EXT)

    def assemble(delta):
        a = Asm(R0)
        for k, v in VARS.items(): a.ext[k] = v + delta
        a.emit(struct.pack('<BBHH', 0x82, 0, len(V), 0))
        for v in V: a.emit(struct.pack('<hhh', *v))
        for i, n in enumerate(VN):
            n = np.array([n[0], n[2], n[1]]); L = np.linalg.norm(n) or 1
            a.emit(struct.pack('<BHBbbb', 0xF6, i, vcol.get(i, 150) & 0xFF, *[int(round(x * 127 / L)) for x in n]))
        a.emit(b'\x38'); a.rel16('AFTER_TRL')
        a.label('TRL'); a.emit(bytes(c[R1:R1 + 18]))
        a.label('RET1E'); a.emit(b'\x1e\x1e')
        a.label('AFTER_TRL')
        Tree(V).emit(a, tree)
        a.ret()
        for k, pd in part_data.items():
            a.emit(part_hdr)
            a.label('part_' + k)
            a.emit(struct.pack('<BBHH', 0x82, 0, len(pd['PV']), base * 8))
            for v in pd['PV']: a.emit(struct.pack('<hhh', *v))
            for i, n in enumerate(pd['pvn']):
                n = np.array([n[0], n[2], n[1]]); L = np.linalg.norm(n) or 1
                a.emit(struct.pack('<BHBbbb', 0xF6, base + i, pd['pcol'].get(i, 150) & 0xFF, *[int(round(x * 127 / L)) for x in n]))
            GV = {i + base: v for i, v in enumerate(pd['PV'])}
            Tree(GV).emit(a, pd['pt'])
            a.ret()
        out_b, rel = a.link(); labels.update(a.labels)
        return out_b, rel

    labels = {}
    blob, _ = assemble(0)
    delta = len(blob) - (R1 - R0)
    blob, relocs = assemble(delta)
    nc = bytearray(c[:R0] + blob + c[R1:])
    T = R1 + delta                                             # the trailer, moved
    assert nc[T + 18:T + 27] == bytes([1, 2, 3, 2, 1, 2, 3, 2, 1]), 'trailer not before the signature'
    T = labels['TRL']                                          # SR-71: trailer copy near the start (CODE > 32 KB)
    for p in (H['f2'],):
        assert 0x12 + struct.unpack_from('<h', c, p)[0] == R1
        struct.pack_into('<h', nc, p, T - (p + 2))
    print('CODE', len(nc), 'trailer copy at', hex(T))
    tgt = H['e2'] if H['e2'] is not None else R0
    for p in H['c8']: struct.pack_into('<h', nc, p, tgt - (p + 2))
    if H['a6']: struct.pack_into('<h', nc, H['a6'], labels['RET1E'] - (H['a6'] + 2))
    if pic_name and H['e2'] is not None:
        nm = pic_name.encode(); assert len(nm) <= 13
        nc[H['e2'] + 2:H['e2'] + 16] = nm + b'\0' * (14 - len(nm))
    # header radius / EXT, trailer radius + bbox
    R = int(np.ceil(1.15 * np.linalg.norm(allP, axis=1).max()))
    struct.pack_into('<H', nc, 4, R)
    struct.pack_into('<3H', nc, 8, *EXT)
    gz = ground if ground is not None else int(np.floor(allP[:, 2].min()))
    bb = [int(allP[:, 0].min()), int(allP[:, 0].max()), gz, int(np.ceil(allP[:, 2].max())), int(allP[:, 1].min()), int(allP[:, 1].max())]
    struct.pack_into('<i', nc, T, R); struct.pack_into('<6h', nc, T + 4, *bb)
    room = nxt - code['va']
    print(f'high LOD {R1 - R0} -> {len(blob)} bytes ({delta:+d}); CODE {len(nc)} / room {room}; radius {R} EXT {EXT} bbox {bb}')
    if len(nc) > room: sys.exit('CODE does not fit')
    if len(nc) > 0x7F00: print('WARNING: CODE over 32 KB')

    outb = rebuild(d, pe, secs, code, nc, delta, relocs, R0, R1)
    assert len(outb) < 65536, len(outb)
    open(out, 'wb').write(outb)
    print(f'{out}: {len(outb)} bytes')
    return dict(V=V, slots=nslots, labels=labels)


def rebuild(d, pe, secs, code, nc, delta, new_relocs, R0, R1):
    """f14_glb.rebuild, but relocations pointing into the replaced region (unreachable donor LOD code) are
    dropped instead of fatal."""
    rel = next(s for s in secs if s['name'] == '.reloc')
    rdir = pe + 24 + 96 + 8 * 5; rva, rsz = struct.unpack_from('<II', d, rdir)
    ents, p = [], rel['ro'] + (rva - rel['va'])
    while p < rel['ro'] + (rva - rel['va']) + rsz:
        page, sz = struct.unpack_from('<II', d, p)
        if sz < 8: break
        for k in range((sz - 8) // 2):
            e = struct.unpack_from('<H', d, p + 8 + 2 * k)[0]
            if e >> 12: ents.append(page + (e & 0xFFF))
        p += sz
    cva = code['va']; out_r = []
    for r in ents:
        off = r - cva
        if not 0 <= off < code['vs']: out_r.append(r); continue
        if R0 <= off < R1: continue
        if off >= R1: off += delta
        val = struct.unpack_from('<I', nc, off)[0] - cva
        if R0 <= val < R1: continue
        if R1 <= val < code['vs']: struct.pack_into('<I', nc, off, val + delta + cva)
        out_r.append(off + cva)
    out_r += [o + cva for o in new_relocs]
    tbl = bytearray(); pages = {}
    for r in sorted(out_r): pages.setdefault(r & ~0xFFF, []).append((3 << 12) | (r & 0xFFF))
    for pg, es in sorted(pages.items()):
        if len(es) % 2: es.append(0)
        tbl += struct.pack('<II', pg, 8 + 2 * len(es)) + b''.join(struct.pack('<H', e) for e in es)
    if len(tbl) > rel['rs']: sys.exit('reloc table too big')
    falign = struct.unpack_from('<I', d, pe + 24 + 36)[0]
    new_rs = (len(nc) + falign - 1) // falign * falign
    shift = new_rs - code['rs']
    out = bytearray(d[:code['ro']]) + nc + b'\x00' * (new_rs - len(nc))
    for s in sorted(secs, key=lambda s: s['ro']):
        if s['ro'] > code['ro']: out += d[s['ro']:s['ro'] + s['rs']]
    out += d[max(s['ro'] + s['rs'] for s in secs):]
    struct.pack_into('<I', out, code['hdr'] + 8, len(nc)); struct.pack_into('<I', out, code['hdr'] + 16, new_rs)
    for s in secs:
        if s['ro'] > code['ro']: struct.pack_into('<I', out, s['hdr'] + 20, s['ro'] + shift)
    soc = struct.unpack_from('<I', out, pe + 24 + 4)[0]; struct.pack_into('<I', out, pe + 24 + 4, soc + shift)
    rel_ro = rel['ro'] + shift + (rva - rel['va'])
    out[rel_ro:rel_ro + rel['rs']] = b'\x00' * rel['rs']
    out[rel_ro:rel_ro + len(tbl)] = tbl
    struct.pack_into('<I', out, rdir + 4, len(tbl))
    return bytes(out)
