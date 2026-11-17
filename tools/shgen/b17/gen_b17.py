#!/usr/bin/env python3
"""Build a B-17G Flying Fortress SH from FA's A47 (AC-47) SH.

What is kept from A47.SH: the file wrapper (PE sections, imports, header ops, CE block, F2 trailer,
signature and import thunks), the texture (_A47.PIC, renamed _B17.PIC), the two animated propeller frames
of the texture and the three textured landing-gear parts with their retract control.
What is new: the whole airframe for all three LODs (fuselage with glazed nose and cockpit, four engines,
B-17 wing / tailplane / fin with dorsal fillet, top / chin / ball / tail turrets with guns, national
insignia), the rudder (3 states, _PLrudder), split flaps (_PLleftFlap/_PLrightFlap) and an opening bomb
bay (object flag 0x200 at obj+0x16F, the bay-door flag FA's flight model uses).
Draw order: faces + parts are ordered by the occlusion-graph compiler in ../glb2sh/bsp.py.

Usage: python3 gen_b17.py A47.SH out/B17.SH [lod_preview.png]
"""
import os, sys, struct, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..')); sys.path.insert(0, os.path.join(HERE, '..', 'glb2sh'))
import numpy as np
import bsp
from bsp import Face, Obj, Order, count
bsp.EPS = 0.6
bsp.OBJ_SIDE = True
from shasm import Asm
from sh_subdivide import pe_sections
from f18g_growler import grow_vas
import b17_geom as G

PIC_NAME = b'_B17.PIC'
PB = 668                     # vertex-table slot of the part buffers (parts are drawn one at a time)
MAXV = PB                    # main LOD must stay below the part slots
EXT = (500, 140, 420)        # header words CODE+8 (copied before each C4 part): stock SHs have ~2.2-2.4x the
                             # model's |x|, |up|, |fwd| extents (A47: 442, 124, 357); B-17 |fwd| reaches 184
# A47 offsets
A47_GEAR = {'gearL': 0x2a92, 'gearR': 0x2b53, 'tail': 0x2c14}     # 6-byte extents header before each 82
A47_TRAILER = 0x4184
SAR = lambda k: b'\x66\xC1\xF8' + bytes([k])
NEG = b'\x66\xF7\xD8'


# ------------------------------------------------------------------ faces for the order compiler
class SFace(Face):
    """a face with FA flags, colour, optional u8 UVs and pre/post bytecode (texture switches)"""
    def __init__(s, ids, P, col, nrm=None, fl=0x261, uvd=None, pre=b'', post=b''):
        super().__init__(ids, P, col, nrm)
        s.fl = fl; s.uvd = uvd; s.pre = pre; s.post = post; s.smooth = False


class SOrder(Order):
    def split(s, f, n, d):
        ids, P = f.ids, f.P; v = P @ n - d; EPS = bsp.EPS
        fr, bk = [], []
        uvd = dict(f.uvd) if f.uvd else None
        for k in range(len(ids)):
            i, j = k, (k + 1) % len(ids)
            if v[i] >= -EPS: fr.append(ids[i])
            if v[i] <= EPS: bk.append(ids[i])
            if (v[i] > EPS and v[j] < -EPS) or (v[i] < -EPS and v[j] > EPS):
                t = v[i] / (v[i] - v[j]); p = P[i] + t * (P[j] - P[i])
                ni = s.add_vertex(p, ids[i], ids[j], t); fr.append(ni); bk.append(ni)
                if uvd:
                    a, b = uvd[ids[i]], uvd[ids[j]]
                    uvd[ni] = (round(a[0] + t * (b[0] - a[0])), round(a[1] + t * (b[1] - a[1])))
        s.splits += 1
        def mk(l):
            l = [x for k, x in enumerate(l) if s.V[x] != s.V[l[k - 1]]]
            if len(set(map(tuple, (s.V[i] for i in l)))) < 3: return None
            g = SFace(l, [s.V[i] for i in l], f.col, f.n, f.fl, uvd, f.pre, f.post)
            if np.dot(g.n, f.n) < 0.5: g.n = f.n; g.d = float(np.dot(f.n, g.P.mean(0)))
            return g
        return mk(fr), mk(bk)


def face_bytes(f, V):
    ids = f.ids; P = np.array([V[i] for i in ids], float)
    fl = f.fl
    if any(i > 255 for i in ids): fl |= 0x400
    n = f.n; nrm = [int(round(n[0] * 32767)), int(round(n[2] * 32767)), int(round(n[1] * 32767))]
    small = [V[i] for i in ids if all(abs(x) <= 127 for x in V[i])]
    pv = small[0] if small else V[ids[0]]; pt = [int(pv[0]), int(pv[2]), int(pv[1])]   # a vertex on the plane (x, up, fwd)
    if fl & 0x200 and any(abs(x) > 127 for x in pt): fl &= ~0x200
    b = bytearray(f.pre) + struct.pack('<BHH', 0xFC, fl, f.col) + struct.pack('<hhh', *nrm)
    b += struct.pack('<bbb', *pt) if fl & 0x200 else struct.pack('<hhh', *pt)
    b.append(len(ids))
    b += b''.join(struct.pack('<H', i) for i in ids) if fl & 0x400 else bytes(ids)
    if fl & 4:
        for i in ids: b += bytes(max(0, min(255, int(x))) for x in f.uvd[i])
    return bytes(b + f.post)


def emit_tree(a, t, V):
    if t[0] == 'list':
        for e in t[1]:
            if isinstance(e, Face): a.emit(face_bytes(e, V))
            else: e.emit(a)
        return
    if t[0] == 'leaf': return
    _, n, d, A, B, coF, coB = t
    la, lb, lend = a.new('A'), a.new('B'), a.new('E')
    p = np.array(n) * d
    nn = [int(round(n[0] * 32767)), int(round(n[2] * 32767)), int(round(n[1] * 32767))]
    dd = [-int(round(p[0])), -int(round(p[2])), -int(round(p[1]))]
    a.node3(nn, dd, la, lb); a.jmp(lend)
    a.label(la)
    for f in coB: a.emit(face_bytes(f, V))
    emit_tree(a, A, V); a.ret()
    a.label(lb)
    for f in coF: a.emit(face_bytes(f, V))
    emit_tree(a, B, V); a.ret()
    a.label(lend)


# ------------------------------------------------------------------ assembler helpers
class BAsm(Asm):
    def cond_eq(s, var, val, then_fn):
        """if word [var] == val (imm8, sign extended): run then_fn bytecode"""
        L_then, L_else, L_end = s.new(), s.new(), s.new()
        s.emit(b'\xF0\x00\x66\x83\x3D'); s.abs32(var); s.emit(bytes([val & 0xFF]))
        s.emit(b'\x0F\x85'); s.rel32_to(L_else)
        s.f0_resume(L_then, 'RESUME')
        s.label(L_then); then_fn()
        s.emit(b'\xF0\x00'); s.label(L_else); s.f0_resume(L_end, 'RESUME')
        s.label(L_end)

    def bay_if(s, open_fn, closed_fn):
        """object flag 0x200 (bomb bay open) of the object being drawn: obj = [0x553848 + [0x580bec]*4]"""
        L_open, L_closed, L_x, L_end = s.new(), s.new(), s.new(), s.new()
        s.emit(b'\xF0\x00')
        s.emit(b'\x0F\xB7\x05' + struct.pack('<I', 0x580BEC))            # movzx eax, word [0x580bec]
        s.emit(b'\x85\xC0\x0F\x84'); s.rel32_to(L_x)                       # test eax,eax ; jz closed
        s.emit(b'\x8B\x04\x85' + struct.pack('<I', 0x553848))             # mov eax, [eax*4+0x553848]
        s.emit(b'\x85\xC0\x0F\x84'); s.rel32_to(L_x)
        s.emit(b'\xF6\x80' + struct.pack('<I', 0x170) + b'\x02')           # test byte [eax+0x170], 2
        s.emit(b'\x0F\x84'); s.rel32_to(L_x)
        s.f0_resume(L_open, 'RESUME')
        s.label(L_open); open_fn(); s.jmp(L_end)
        s.emit(b'\xF0\x00'); s.label(L_x); s.f0_resume(L_closed, 'RESUME')
        s.label(L_closed); closed_fn()
        s.label(L_end)

    def anim2(s, frames):
        """40 00 switch between two frames (frame counter mod 2); each frame = bytes"""
        L0, L1, Le = s.new(), s.new(), s.new()
        s.emit(b'\x40\x00\x02\x00'); s.rel16(L0, -2); s.rel16(L1, -2)
        s.label(L0); s.emit(frames[0]); s.emit(b'\x48\x00'); s.rel16(Le)
        s.label(L1); s.emit(frames[1])
        s.label(Le)


# ------------------------------------------------------------------ meshes -> faces
def collect(meshes, decals=(), V=None):
    """returns V (int tuples), faces (SFace); appends to V when given (shared vertex buffer)"""
    if V is None: V = []
    index = {v: i for i, v in enumerate(V)}
    def vid(p):
        q = tuple(int(round(x)) for x in p)
        if q not in index: index[q] = len(V); V.append(q)
        return index[q]
    faces = []
    for M in meshes:
        for f in M.F:
            ids = [vid(M.V[i]) for i in f['ids']]
            ids = [x for k, x in enumerate(ids) if x != ids[k - 1]]
            if len(set(ids)) < 3: continue
            for tri in planar_pieces(ids, V):
                Pp = [V[i] for i in tri]
                n = -G.newell(Pp)                       # FA: sum PxP points inward
                if np.linalg.norm(n) < 1e-6: continue
                if np.dot(n, f['out']) < 0: tri = tri[::-1]
                faces.append(SFace(tri, [V[i] for i in tri], f['col']))
    pic = b'\xE2\x00' + PIC_NAME.ljust(14, b'\0')
    for pts, eid, uv, out in decals:
        ids = [vid(p) for p in pts]
        n = -G.newell([V[i] for i in ids])
        if np.dot(n, out) < 0: ids = ids[::-1]; uv = uv[::-1]
        faces.append(SFace(ids, [V[i] for i in ids], 0, None, 0x14C, dict(zip(ids, uv)),
                           b'\xE0\x00' + struct.pack('<H', eid), pic))
    return V, faces


def planar_pieces(ids, V):
    if len(ids) == 3: return [ids]
    P = np.array([V[i] for i in ids], float)
    n = G.newell(P); L = np.linalg.norm(n)
    if L > 0:
        n /= L; dev = np.abs((P - P.mean(0)) @ n).max()
        if dev <= 0.45: return [ids]
    # fan split into triangles
    return [[ids[0], ids[k], ids[k + 1]] for k in range(1, len(ids) - 1)]


# ------------------------------------------------------------------ parts
def part_bytes(M, two_sided_cols=None):
    """82 buffer at PB + flat faces + ret; M faces oriented like collect()"""
    V, faces = collect([M])
    b = bytearray(struct.pack('<BBHH', 0x82, 0, len(V), PB * 8))
    for v in V: b += struct.pack('<hhh', *v)
    VV = {PB + i: v for i, v in enumerate(V)}
    for f in faces:
        f.ids = [PB + i for i in f.ids]
        b += face_bytes(f, VV)
    return bytes(b + b'\x00\x00'), V


def gear_part(c, hdr_off):
    """copy an A47 gear part (82 buffer + textured faces) and move it to slot PB"""
    p = hdr_off + 6
    n, t = struct.unpack_from('<HH', c, p + 2); base = t // 8
    out = bytearray(struct.pack('<BBHH', 0x82, 0, n, PB * 8)) + c[p + 6:p + 6 + 6 * n]
    q = p + 6 + 6 * n
    from sh_subdivide import parse_face
    while c[q] == 0xFC:
        f = parse_face(c, q); raw = bytearray(c[q:f['end']])
        assert f['fl'] & 0x400
        k = 1 + 4 + (6 + (3 if f['fl'] & 0x200 else 6) if f['fl'] & 0x60 else 0) + 1
        for j in range(f['n']):
            struct.pack_into('<H', raw, k + 2 * j, f['idx'][j] - base + PB)
        out += raw; q = f['end']
    return bytes(out + b'\x00\x00')


def prop_part():
    """animated propeller disc: A47's two blur frames (texture u 0-76 / 78-154, v 215-291), both sides"""
    R = 23
    corners = [(-R, -R), (R, -R), (R, R), (-R, R)]        # (dx, dz)
    uvs = [(76, 215), (0, 215), (0, 291), (76, 291)]
    V = [(dx, 0, dz) for dx, dz in corners] + [(0, 6, 0), (-3, 1, -3), (3, 1, -3), (3, 1, 3), (-3, 1, 3)]
    b = bytearray(struct.pack('<BBHH', 0x82, 0, len(V), PB * 8))
    for v in V: b += struct.pack('<hhh', *v)
    def disc(frame):
        o = bytearray()
        for sgn, order in ((1, [0, 1, 2, 3]), (-1, [3, 2, 1, 0])):
            # front side (normal +fwd) and back side
            o += struct.pack('<BHH', 0xFC, 0x064C, 0) + struct.pack('<hhh', 0, 0, 32767 * sgn) + struct.pack('<bbb', 0, 0, 0)
            ids = order if sgn > 0 else order
            # winding: FA sum PxP points inward -> for normal +fwd (y) need Newell along -y
            P = [V[i] for i in ids]
            nn = -G.newell(P)
            if nn[1] * sgn < 0: ids = ids[::-1]
            o.append(4); o += b''.join(struct.pack('<H', PB + i) for i in ids)
            for i in ids:
                u, v = uvs[i]; o += struct.pack('<HH', u + 78 * frame, v)
        return bytes(o)
    a = BAsm(0)
    a.emit(bytes(b))
    a.anim2([disc(0), disc(1)])
    # spinner (dark pyramid) in front of the disc
    sp = G.Mesh('spinner')
    for p in V[4:]: sp.v(p)
    for k in range(4):
        i, j = 1 + k, 1 + (k + 1) % 4
        cen = np.mean([sp.V[i], sp.V[j]], 0)
        sp.face([0, i, j], G.DARK, (cen[0], 1, cen[2]))
    _, sf = collect([sp])
    VV = {PB + i: v for i, v in enumerate(V)}
    for f in sf:
        # collect() renumbered vertices in insertion order (spinner verts = V[4:]); map back
        f.ids = [PB + 4 + i for i in f.ids]
        a.emit(face_bytes(f, VV))
    a.ret()
    blob, rel = a.link(); assert not rel
    return blob


# ------------------------------------------------------------------ objects in the draw order
def obj_from(name, pts, emit, pad=1.0):
    P = np.array(pts, float)
    return Obj(name, P.min(0) - pad, P.max(0) + pad, emit)


# test switches (bisecting in-game problems): B17_FEAT = comma list of the moving parts to include
# (props, gear, flaps, rudder, bay; default all). Left out: no x86 block / C4 for it (rudder neutral,
# bay closed). B17_NODECAL=1 -> no insignia.
FEAT = set(os.environ.get('B17_FEAT', 'props,gear,flaps,rudder,bay').split(','))
NODECAL = os.environ.get('B17_NODECAL') == '1'


def prop_obj(pos):
    x, up, fwd = pos
    return Obj('prop', (x - 24, fwd - 1, up - 24), (x + 24, fwd + 7, up + 24), lambda a: a.c4(pos, (0, 0, 0), 'p_prop'))


def gear_obj(side):
    """A47 gear parts: gearL part sits at x = -90 in its own frame, gearR at +90 (A47 placed them at +-45)"""
    gx = round(G.ENG_Y[0] * G.U); gf = round((G.S0 - 27.5) * G.U)
    def gear(pos, field, ops, part):
        return lambda a: a.cond_eq('GEARDOWN', 1, lambda: a.patch_c4('GEARPOS', field, ops, 'RESUME',
                                                                     lambda: a.c4(pos, (0, 0, 0), part)))
    if side > 0:
        return Obj('gearR', (gx - 8, gf - 10, -33), (gx + 8, gf + 10, -10), gear((gx - 90, -7, gf), 0x0A, SAR(1), 'p_gearR'))
    return Obj('gearL', (-gx - 8, gf - 10, -33), (-gx + 8, gf + 10, -10), gear((90 - gx, -7, gf), 0x0A, SAR(1), 'p_gearL'))


def tailwheel_obj():
    tf = round((G.S0 - 67.5) * G.U)
    return Obj('tail', (-4, tf - 6, -33), (4, tf + 6, -2),
               lambda a: a.cond_eq('GEARDOWN', 1, lambda: a.patch_c4('GEARPOS', 0x0A, SAR(1) + NEG, 'RESUME',
                                                                      lambda: a.c4((0, -2, tf), (0, 0, 0), 'p_tail'))))


def rudder_obj():
    def rud(a):
        a.cond_eq('RUDDER', 1, lambda: a.call('p_rudP'))
        a.cond_eq('RUDDER', 0, lambda: a.call('p_rud0'))
        a.cond_eq('RUDDER', -1, lambda: a.call('p_rudM'))
    if 'rudder' not in FEAT: rud = lambda a: a.call('p_rud0')
    return obj_from('rudder', G.rudder(1).V + G.rudder(-1).V + G.rudder(0).V, rud)


def flap_obj(side):
    if side > 0: return obj_from('flapR', G.flap(1).V, lambda a: a.cond_eq('RFLAP', -1, lambda: a.call('p_flapR')))
    return obj_from('flapL', G.flap(-1).V, lambda a: a.cond_eq('LFLAP', -1, lambda: a.call('p_flapL')))


def bay_obj(fus, fm):
    bc, bo = G.bay_parts(fus, fm)
    if 'bay' not in FEAT: return obj_from('bay', bc.V + bo.V, lambda a: a.call('p_bayC'), pad=0.5)
    return obj_from('bay', bc.V + bo.V, lambda a: a.bay_if(lambda: a.call('p_bayO'), lambda: a.call('p_bayC')), pad=0.5)


# hand-made draw-order nodes: ('node', n, d, A, B, [], []) -> eye with n.eye >= d draws A then B
def plane_node(n, p, A, B):
    n = np.array(n, float); n /= np.linalg.norm(n)
    return ('node', n, float(np.dot(n, p)), A, B, [], [])


def attach(inner, item, n, p):
    """item sits on the n side of a plane through p: drawn after `inner` when the eye is on that side"""
    return plane_node(n, p, inner, item)


def front_to_back(items):
    """items = [(station ft, tree)] along the fuselage; order them by the eye's station"""
    if len(items) == 1: return items[0][1]
    k = len(items) // 2
    mid = (items[k - 1][0] + items[k][0]) / 2
    # eye behind `mid`: the front items are farther away -> drawn first
    return plane_node((0, -1, 0), G.P(mid, 0, 0), front_to_back(items[:k]), front_to_back(items[k:]))


def sub(M, tags):
    S = G.Mesh(M.name); S.V = M.V; S.F = [f for f in M.F if f['tag'] in tags]
    return S


def wing_side(sg, wm, nacs, wd, comp):
    """one wing side in spanwise segments: root strip | inboard nacelle strip | middle strip |
    outboard nacelle strip | outer wing (+ insignia).  In a nacelle segment the fairings sit above /
    below the chord plane and the pod ahead of the leading edge; segments are ordered by span planes."""
    nstrip = max(f['tag'] for f in wm.F) + 1
    dh = math.radians(G.DIHEDRAL)
    up = (-sg * math.sin(dh), 0, math.cos(dh))
    segs = []          # (outer boundary span ft, tree)
    segs.append(comp([sub(wm, {0})]))
    for k, (strip, nac) in enumerate(((1, nacs[0]), (3, nacs[1]))):
        y = G.ENG_Y[k]; le = G.wing_le(y)
        p = G.P(le, sg * y, G.wing_z(y))
        t = comp([sub(wm, {strip})])
        t = attach(t, comp([sub(nac, {'up'})]), up, p)
        t = attach(t, comp([sub(nac, {'lo'})]), tuple(-c for c in up), p)
        t = attach(t, comp([sub(nac, {'pod'})]), (0, 1, 0), G.P(le, 0, 0))
        segs.append(t)
        if k == 0: segs.append(comp([sub(wm, {2})]))
    segs.append(comp([sub(wm, set(range(4, nstrip)))], decals=wd))
    bounds = [G.ENG_Y[0] - G.NAC_R - 0.3, G.ENG_Y[0] + G.NAC_R + 0.3, G.ENG_Y[1] - G.NAC_R - 0.3, G.ENG_Y[1] + G.NAC_R + 0.3]
    def lat(lo, hi):           # segments lo..hi-1; eye outboard of a boundary: the inner ones first
        if hi - lo == 1: return segs[lo]
        m = (lo + hi) // 2
        return plane_node((sg, 0, 0), G.P(0, sg * bounds[m - 1], 0), lat(lo, m), lat(m, hi))
    return lat(0, len(segs))


def build_lod(detail):
    """detail 2 = high, 1 = medium, 0 = low.  Returns (V, tree, (fuselage, fuselage mesh, props)).
    Draw order: the fuselage, each wing side (wing + nacelles + props + gear + flap), each tailplane, the
    fin + rudder, and each turret are ordered by the face compiler on their own; these groups are then put
    together with hand-made plane nodes (left / right of the fuselage sides, above / below, fore / aft)."""
    n = {2: 8, 1: 6, 0: 6}[detail]
    pick = {2: range(len(G.FUS)), 1: (0, 2, 4, 6, 8, 9, 11, 13, 15), 0: (0, 3, 7, 10, 13, 15)}[detail]
    fus = G.Fuselage(n, [G.FUS[i] for i in pick])
    fm = fus.mesh(detail >= 1)
    body = G.Mesh('fusb'); body.V = fm.V
    body.F = [f for f in fm.F if not (detail >= 1 and f['tag'] in ('bayL', 'bayR'))]
    tur = G.turrets(fus, detail == 2)
    dec = G.decals(fus) if detail == 2 and not NODECAL else []
    V = []; stats = [0, 0]
    def comp(meshes, objs=(), decals=()):
        _, faces = collect(meshes, decals, V)
        B = SOrder(V, lambda p, i, j, t: (V.append(tuple(int(round(x)) for x in p)), len(V) - 1)[1])
        t = B.build(faces, list(objs)); stats[0] += B.splits; stats[1] += len(faces)
        if os.environ.get("B17DBG"): print("  group", [getattr(m, "name", "?") for m in meshes], len(faces), "faces", B.splits, "splits")
        return t
    T_fus = comp([body], decals=dec[2:])
    T_tail = comp([tur['tail']])
    bottom = [(3.0, comp([tur['chin']]))] if detail else []
    if detail: bottom.append((31.0, comp([], [bay_obj(fus, fm)])))
    if detail: bottom.append((42.5, comp([tur['ball']])))
    if detail and 'gear' in FEAT: bottom.append((67.5, comp([], [tailwheel_obj()])))
    fin = comp([G.fin(fus, detail >= 1)] + ([] if detail else [G.rudder(0)]), [rudder_obj()] if detail else [])
    top = plane_node((0, -1, 0), (0, 0, 0), comp([tur['top']]), fin) if detail else fin   # eye behind s=32: turret, then fin
    centre = attach(T_fus, T_tail, (0, -1, 0), G.P(G.TAILGUN[0], 0, 0))
    if bottom: centre = attach(centre, front_to_back(bottom), (0, 0, -1), G.P(0, 0, -3.0))
    pa, pb = np.array(G.P(20.0, 0, 5.0)), np.array(G.P(71.0, 0, 1.9))
    d = pb - pa
    centre = attach(centre, top, (0, -d[2], d[1]) if d[1] > 0 else (0, d[2], -d[1]), pa)
    props = []; sides = {}
    for sg in (1, -1):
        wm = G.wing(sg, fus, detail); nacs = []; prs = []
        for y in G.ENG_Y:
            m, pr = G.nacelle(sg * y, detail >= 1); nacs.append(m); props.append(pr); prs.append(pr)
        wd = [q for q in dec[:2] if (q[0][0][0] > 0) == (sg > 0)]
        if not detail:
            wing_t = comp([wm] + nacs, (), wd)
        else:
            wing_t = wing_side(sg, wm, nacs, wd, comp)
            # the moving parts are boxes that overlap much of the wing, so the face compiler can't order
            # them: they go around the wing with hand planes (gear and flap below it, props ahead of it)
            gl = [gear_obj(sg)] if 'gear' in FEAT else []
            fl = [flap_obj(sg)] if 'flaps' in FEAT else []
            if gl or fl:
                lower = plane_node((0, -1, 0), G.P(34.0, 0, 0), ('list', gl), ('list', fl))
                dh = math.radians(G.DIHEDRAL)
                wing_t = attach(wing_t, lower, (sg * math.sin(dh), 0, -math.cos(dh)), G.P(40.0, sg * 3.8, G.wing_z(3.8)))
            for pr in (prs if 'props' in FEAT else []):
                x, up, fw = pr
                wing_t = attach(wing_t, ('list', [prop_obj(pr)]), (0, 1, 0), (x, fw - 1.5, up))
        stab_t = comp([G.stab(sg, fus, detail == 2)])
        sides[sg] = plane_node((0, -1, 0), G.P(50.0, 0, 0), wing_t, stab_t)     # eye behind s=50: wing, then tailplane
    tree = attach(centre, sides[-1], (-1, 0, 0), (-15, 0, 0))
    tree = attach(tree, sides[1], (1, 0, 0), (15, 0, 0))
    print(f'LOD{detail}: {len(V)} verts, {stats[1]} faces, {stats[0]} splits')
    if len(V) > MAXV: sys.exit(f'too many vertices ({len(V)} > {MAXV})')
    return V, tree, (fus, fm, props)


def lod_code(a, V, tree):
    a.emit(struct.pack('<BBHH', 0x82, 0, len(V), 0))
    for v in V: a.emit(struct.pack('<hhh', *v))
    emit_tree(a, tree, V)
    a.ret()


# ------------------------------------------------------------------ whole CODE section
def build_code(c, sig, lods):
    """c = A47 CODE bytes (possibly after grow_vas), sig = signature offset. Returns (new CODE, reloc offsets)"""
    # import thunks after the signature: ff 25 [IAT] (gearDown, gearPos, leftFlap, rightFlap, rudder, do_start_interp)
    names = ['GEARDOWN', 'GEARPOS', 'LFLAP', 'RFLAP', 'RUDDER', 'RESUME']
    tail = bytes(c[sig:])
    trailer = bytearray(c[A47_TRAILER:sig])
    hdr = bytearray(c[:0x80])
    fus, fm, props = lods[2][2]
    phdr = b'\xff\xff\x00\x00\xe8\x00\x08\x00' + struct.pack('<3H', *EXT)     # (first 8 bytes: A47's part prefix)

    def assemble(base_sig):
        a = BAsm(0)
        a.emit(bytes(hdr))
        for k, nm in enumerate(names): a.ext[nm] = base_sig + 10 + 6 * k
        a.label('main'); lod_code(a, *lods[2][:2])
        # parts
        def part(label, blob, with_hdr=True):
            if with_hdr: a.emit(phdr[-6:])
            a.label(label); a.emit(blob)
        a.emit(phdr[:8])
        part('p_prop', prop_part())
        for k, nm in (('gearL', 'p_gearL'), ('gearR', 'p_gearR')):
            part(nm, gear_part(c, A47_GEAR[k]))
        tailM = tail_wheel(); part('p_tail', part_bytes(tailM)[0])
        for st, nm in ((1, 'p_rudP'), (0, 'p_rud0'), (-1, 'p_rudM')):
            part(nm, part_bytes(G.rudder(st))[0], False)
        part('p_flapR', part_bytes(G.flap(1))[0], False); part('p_flapL', part_bytes(G.flap(-1))[0], False)
        bc, bo = G.bay_parts(fus, fm)
        part('p_bayC', part_bytes(bc)[0], False); part('p_bayO', part_bytes(bo)[0], False)
        a.label('noshow'); a.emit(b'\x1e\x1e')
        a.label('trailer'); a.emit(bytes(trailer))     # read through the F2 pointer (rel16 from CODE+0x10)
        a.label('med'); lod_code(a, *lods[1][:2])
        a.label('low'); lod_code(a, *lods[0][:2])
        return a
    a = assemble(0x80)
    size = a.here()
    a = assemble(size)
    assert a.here() == size
    blob, relocs = a.link()
    nc = bytearray(blob) + tail
    print('sizes', {k: hex(v) for k, v in a.labels.items() if k in ('main','p_prop','noshow','med','low','trailer')})
    # header: F2 -> trailer, C8 -> low / medium, A6 -> noshow
    for off, lab in ((0x10, 'trailer'), (0x60, 'low'), (0x68, 'med'), (0x6c, 'noshow')):
        struct.pack_into('<h', nc, off, a.labels[lab] - (off + 2))
    struct.pack_into('<3H', nc, 8, *EXT)
    # CODE+4: bounding radius (stock: ~0.9-1x the farthest vertex; A47 232). Too small and FA treats the
    # plane as fully on screen in close views and skips clipping -> crash. Use the farthest vertex + margin.
    allV = np.array(lods[2][0], float)
    R = max(232, int(np.ceil(1.2 * np.linalg.norm(allV, axis=1).max())))     # stock ratio ~1.1-1.2
    struct.pack_into('<H', nc, 4, R)
    print('radius', R, 'EXT', EXT)
    # CE wingtip points (x, up, fwd) * 256 : left tip stored with negative x like A47
    tip = G.P(G.wing_te(51.9), 51.9, G.wing_z(51.9))
    for off, sx in ((0x14 + 0x0E, -1), (0x14 + 0x1A, 1)):
        struct.pack_into('<3i', nc, off, int(sx * tip[0] * 256), int(round(tip[2])) * 256, int(round(tip[1])) * 256)
    # trailer bounding box (x min/max, up min/max, fwd min/max), gear-down ground level kept at -32
    allV = np.array(lods[2][0])
    bb = [int(allV[:, 0].min()), int(allV[:, 0].max()), -32, int(allV[:, 2].max()), int(allV[:, 1].min()), int(allV[:, 1].max())]
    struct.pack_into('<6h', nc, a.labels['trailer'] + 4, *bb)
    # E2 texture names
    i = 0
    while True:
        i = nc.find(b'\xE2\x00_A47.PIC', i)
        if i < 0: break
        nc[i + 2:i + 16] = PIC_NAME.ljust(14, b'\0'); i += 16
    relocs += [len(blob) + 12 + 6 * k for k in range(len(names))]
    print(f'CODE {len(nc)} bytes (main {a.labels["p_prop"] - 0x80}, med {a.labels["low"] - a.labels["med"]}, low {len(blob) - a.labels["low"]})')
    return bytes(nc), relocs, bb


def tail_wheel():
    """tail wheel part (frame of the C4: strut top at the origin), olive strut + black tyre"""
    M = G.Mesh('tailwheel')
    r = 4.5; cz = -16.5
    ring = [M.v((0.0, r * math.cos(2 * math.pi * k / 8), cz + r * math.sin(2 * math.pi * k / 8))) for k in range(8)]
    M.plate(ring, G.TYRE)
    s = [M.v(p) for p in ((0, -1.5, 9), (0, 1.5, 9), (0, 1.5, cz), (0, -1.5, cz))]
    M.plate(s, G.OLIVE_D)
    return M


def write_pe(d, nc, code_relocs):
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE')
    rel = next(s for s in secs if s['name'] == '.reloc')
    rdir = pe + 24 + 96 + 8 * 5; rva, rsz = struct.unpack_from('<II', d, rdir)
    cva = code['va']
    tbl = bytearray(); pages = {}
    for r in sorted(set(o + cva for o in code_relocs)):
        pages.setdefault(r & ~0xFFF, []).append((3 << 12) | (r & 0xFFF))
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


def main(src, dst):
    d = open(src, 'rb').read()
    lods = {k: build_lod(k) for k in (2, 1, 0)}
    for attempt in range(2):
        pe, opt, secs = pe_sections(d)
        code = next(s for s in secs if s['name'] == 'CODE')
        c = d[code['ro']:code['ro'] + code['vs']]
        sig = c.find(bytes([1, 2, 3, 2, 1, 2, 3, 2, 1]))
        nc, relocs, bb = build_code(c, sig, lods)
        nxt = min(s['va'] for s in secs if s['va'] > code['va'])
        room = nxt - code['va']
        if len(nc) <= room: break
        grow = (len(nc) - room + 0xFFF) // 0x1000 * 0x1000
        print(f'CODE needs {len(nc)} > {room}: moving later sections up by {grow:#x}')
        d = grow_vas(d, grow)
    else:
        sys.exit('CODE still too big')
    out = write_pe(d, nc, relocs)
    open(dst, 'wb').write(out)
    print(f'{dst}: {len(out)} bytes; bbox {bb}')


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
