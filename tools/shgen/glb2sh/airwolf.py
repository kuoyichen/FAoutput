#!/usr/bin/env python3
"""AIRWOLF.SH: an Airwolf helicopter built on the Ka-52 (HOKUT.SH) from Kuoyi's Airwolf.glb.

Kept from HOKUT.SH: the PE wrapper, header, import thunks (_PLgearDown, _PLgearPos, do_start_interp), trailer.
Replaced: the whole high-LOD block (CODE 0x5A..0x478E: body, rotors, gear control and the old billboard gear
parts).  The two LOD-switch targets in the header are pointed at the high LOD, so the old Ka-52 medium/low
LODs are never drawn (they stay in the file, unused).

New high LOD (one 82 buffer, slots 0..N):
  * fuselage lofted from the GLB (voxel solid -> cross sections, 20-point rings, 10-point rings on the boom),
    sponsons (8-point rings, both sides), gun pods, fin / stabiliser / end plates, rotor mast
  * colours from the nearest GLB material: grey and black -> black, white -> white, glass -> dark glass
  * main rotor and tail rotor = textured discs, 3 blur frames chosen by op `40 00 n rel...` (as in HOKUT)
  * tricycle gear: 3 parts (strut + wheel) drawn by C4 when _PLgearDown == 1, pitch = _PLgearPos / 2
    (retracts forward, like the Bell 222)
Draw order: occlusion graph + 06 plane nodes only at cycles (bsp.py), parts/rotors as boxes.
Usage: python3 airwolf.py Airwolf.glb SH/HOKUT.SH out/AIRWOLF.SH [preview.png]
"""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree
from skimage import measure
from aw_glb import AW, BODY, BODY_SKIP
from glbload import voxel_solid
from loft import Sections, resample
from geom import Mesh, hull2, simplify_poly
import bsp
from bsp import Face, Obj, Order, count
bsp.EPS = float(os.environ.get('AW_EPS', 1.5))   # loft quads are not planar after rounding; 1.5 ft tolerance keeps splits low
from shasm import Asm
from sh_subdivide import pe_sections
import f14_glb as F
from f18g_growler import grow_vas
GROW = 0x1000

# ---- HOKUT.SH layout (CODE offsets) ----
R0, R1 = 0x5A, 0x478E                 # high LOD: main 82 .. old gear parts end (0x478E = '1E 1E' before LOD2)
HDR_RELS = [0x10, 0x46]               # header rel16 fields that point past the region (trailer, A6 target)
LOD_RELS = [0x3A, 0x42]               # C8 LOD switches -> point them at the texture op (0x4A) + high LOD
TEX_OP = 0x4A                         # E2 00 '_hokut.PIC' (renamed to _AIRWOLF.PIC)
PART_HDR = bytes.fromhex('ffff00006a0008008900 3300b500'.replace(' ', ''))
VARS = {'GEARDOWN': 0x6350, 'GEARPOS': 0x6356, 'RESUME': 0x635C}

BLACK, WHITE, GLASS, TYRE, METAL, HUB = 0x44, 0x91, 0x9D, 0x3A, 0x34, 0x37
# PIC layout (see make_pic): 3 main-rotor frames 84x84 at u = 0/86/172, v 0..83; 3 tail-rotor frames 48x48 at v 86
MR_UV = [(0, 0, 84), (86, 0, 84), (172, 0, 84)]
TR_UV = [(0, 86, 48), (50, 86, 48), (100, 86, 48)]
ROTOR_Z, ROTOR_R = 22, 57
TR_C, TR_R, TR_X = (-82, 10), 12, 8   # tail rotor centre (fwd, up), radius, plane x (right side)

BODY_STA = [40, 38, 35, 31, 27, 22, 17, 11, 5, 0, -6, -12, -18, -24, -30, -36, -41]
BOOM_STA = [-47, -54, -62, -70, -77, -83]
TAIL_END = -86.5
SPON_STA = [14, 10, 5, 0, -5, -10, -15, -19]


# ------------------------------------------------------------------ geometry
def ring(contour, K, start='top'):
    """resample a closed contour (x, z) to K points, starting at its top point, going towards +x first"""
    P = np.asarray(contour, float)
    if np.allclose(P[0], P[-1]): P = P[:-1]
    i0 = np.argmax(P[:, 1]); P = np.roll(P, -i0, axis=0)
    if P[1, 0] < P[-1, 0]: P = np.r_[P[:1], P[1:][::-1]]
    Q = resample(np.r_[P, P[:1]], K)
    return Q[:K]


def section2(S, lo, vox, y, xside=None, close=2):
    sl = S[:, int(round((y - lo[1]) / vox)), :].copy()
    if xside is not None:
        xs = lo[0] + np.arange(S.shape[0]) * vox
        sl[(xs * xside) <= 0.5, :] = False
    sl = ndimage.binary_closing(np.pad(sl, close+1), iterations=close)[close+1:-close-1, close+1:-close-1]
    sl = ndimage.binary_fill_holes(sl)
    cs = measure.find_contours(np.pad(sl.astype(float), 1), 0.5)
    if not cs: return None
    c = max(cs, key=len)
    return (c - 1) * vox + lo[[0, 2]]


def loft(M, rings, col_fn, close_front=None, close_back=None):
    """rings: list of lists of vertex ids (same K, consecutive rings go aft)."""
    K = len(rings[0])
    for a, b in zip(rings, rings[1:]):
        for k in range(K):
            M.F.append(([a[k], a[(k+1) % K], b[(k+1) % K], b[k]], None, True, None))
    if close_front is not None:
        for k in range(K): M.F.append(([close_front, rings[0][(k+1) % K], rings[0][k]], None, True, None))
    if close_back is not None:
        for k in range(K): M.F.append(([rings[-1][k], rings[-1][(k+1) % K], close_back], None, True, None))


def plate(M, P3, n_out, verts, col=None):
    c = P3.mean(0); _, _, Vt = np.linalg.svd(P3 - c); e1, e2, nrm = Vt
    if np.dot(nrm, n_out) < 0: nrm = -nrm
    H = simplify_poly(hull2(np.c_[(P3 - c) @ e1, (P3 - c) @ e2]), verts)
    ids = [M.add(c + h[0]*e1 + h[1]*e2) for h in H]
    # FA winding: sum PxP inward -> pick the order whose computed normal matches nrm
    f = Face(ids, [M.V[i] for i in ids], 0)
    if np.dot(f.n, nrm) < 0: ids = ids[::-1]
    cf, cb = col if isinstance(col, tuple) else (col, col)
    M.F.append((ids, cf, False, tuple(nrm))); M.F.append((ids[::-1], cb, False, tuple(-nrm)))
    return ids


def prism(M, centre, axis, r, length, n, col, cap_col=None, rot0=0.0):
    """n-gon prism along axis (unit, one of the coordinate axes) centred at centre"""
    axis = np.asarray(axis, float); c = np.asarray(centre, float)
    u = np.array([0, 0, 1.0]) if abs(axis[2]) < 0.9 else np.array([1.0, 0, 0])
    u = u - axis * np.dot(u, axis); u /= np.linalg.norm(u); v = np.cross(axis, u)
    rings = []
    for s in (-0.5, 0.5):
        rings.append([M.add(c + axis*s*length + r*(np.cos(a)*u + np.sin(a)*v))
                      for a in rot0 + np.arange(n) * 2*np.pi/n])
    a, b = rings
    for k in range(n):
        ang = rot0 + (k + 0.5) * 2*np.pi/n
        M.F.append(([a[k], a[(k+1) % n], b[(k+1) % n], b[k]], col, False, tuple(np.cos(ang)*u + np.sin(ang)*v)))
    M.F.append((a[::-1], cap_col or col, False, tuple(-axis)))
    M.F.append((b, cap_col or col, False, tuple(axis)))
    # fix winding by geometry
    return rings


def build(g):
    M = Mesh()
    # 1. fuselage
    T, _ = g.grp(BODY, BODY_SKIP)
    S, lo, vox = voxel_solid(T, vox=0.5, lo=(-14, -100, -12), hi=(14, 46, 22))
    sec = Sections(S, lo, vox)
    rings = []
    for y in BODY_STA:
        h = sec.half_ring(y, 5, 3, 2)
        full = [(x, y, z) for x, z in h] + [(-x, y, z) for x, z in h[-2:0:-1]]
        rings.append([M.add(p) for p in full])
    boom = []
    for y in BOOM_STA:
        h = sec.half_ring(y, 5, 3, 2)
        full = [(x, y, z) for x, z in h] + [(-x, y, z) for x, z in h[-2:0:-1]]
        boom.append([M.add(p) for p in full[::2]])
    nose = M.add((0, 42.3, float(np.mean([M.V[i][2] for i in rings[0]]))))
    loft(M, rings, None, close_front=nose)
    # transition 20 -> 10
    a, b = rings[-1], boom[0]
    for j in range(10):
        M.F.append(([a[2*j], a[2*j+1], b[j]], None, True, None))
        M.F.append(([a[2*j+1], a[(2*j+2) % 20], b[(j+1) % 10]], None, True, None))
        M.F.append(([a[2*j+1], b[(j+1) % 10], b[j]], None, True, None))
    tail = M.add((0, TAIL_END, float(np.mean([M.V[i][2] for i in boom[-1]]))))
    loft(M, boom, None, close_back=tail)

    # 2. sponsons (right group, mirrored)
    Ts, _ = g.grp([55, 56])
    Ss, los, vs = voxel_solid(Ts, vox=0.5, lo=(-24, -26, -8), hi=(24, 18, 6))
    for side in (1, -1):
        rs = []
        for y in SPON_STA:
            c = section2(Ss, los, vs, y, xside=side)
            if c is None or len(c) < 8: continue
            R = ring(c, 8)
            if side < 0: R = R[::-1]
            rs.append([M.add((x, y, z)) for x, z in R])
        ctr_f = np.mean([M.V[i] for i in rs[0]], 0); ctr_b = np.mean([M.V[i] for i in rs[-1]], 0)
        f = M.add((ctr_f[0], SPON_STA[0] + 2.5, ctr_f[2])); bk = M.add((ctr_b[0], SPON_STA[-1] - 3, ctr_b[2]))
        if side > 0: loft(M, rs, None, close_front=f, close_back=bk)
        else: loft(M, rs, None, close_front=f, close_back=bk)
    # 3. gun pods + pylons
    for side in (1, -1):
        prism(M, (side*23.3, -1.6, -1.6), (0, 1, 0), 1.6, 24, 6, BLACK, rot0=np.pi/6)
        Pp = g.points([59]); Pp = Pp * np.array([side, 1, 1])
        plate(M, Pp, (0, 0, 1), 4, BLACK)
    # 4. tail surfaces
    P = g.points([250])
    fin = P[(np.abs(P[:, 0]) < 2.5) & ((P[:, 1] < -57) | (P[:, 2] > 12))]
    plate(M, fin, (1, 0, 0), 6, BLACK)
    stab = P[(np.abs(P[:, 0]) < 14) & (P[:, 1] > -57) & (P[:, 2] < 10)]
    plate(M, stab, (0, 0, 1), 6, (BLACK, WHITE))     # black on top, white below
    for side in (1, -1):
        ep = P[P[:, 0] * side > 14]
        plate(M, ep, (side, 0, 0), 4, BLACK)
    # 5. rotor mast
    prism(M, (0, 0, 20), (0, 0, 1), 1.5, 5, 4, BLACK, rot0=np.pi/4)
    prism(M, (TR_X - 1.2, TR_C[0], TR_C[1]), (1, 0, 0), 1.0, 2.4, 4, BLACK, rot0=np.pi/4)
    return M


COLOUR_GROUPS = [187, 192, 205, 3, 197, 198, 199, 202, 216, 217, 232, 17, 55, 56, 250]


def colours(g, M):
    """per face: colour of the nearby GLB skin triangles that face the same way (area / distance weighted).
    GLB grey and black -> BLACK (Kuoyi: the grey is black), white -> WHITE, glass -> GLASS."""
    T, Mt = g.grp(COLOUR_GROUPS, BODY_SKIP)
    C = T.mean(1); N = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); A = np.linalg.norm(N, axis=1)
    N = N / (A[:, None] + 1e-12); tree = cKDTree(C)
    lum = {}
    for m in set(Mt.tolist()):
        mt = g.J['materials'][m] if m is not None else {}
        c = mt.get('pbrMetallicRoughness', {}).get('baseColorFactor', [0.5, 0.5, 0.5, 1])
        lum[m] = GLASS if (c[3] < 0.5 or 'Glass' in mt.get('name', '')) else (WHITE if np.mean(c[:3]) > 0.45 else BLACK)
    out = []
    for ids, col, smooth, nrm in M.F:
        if col is None:
            P = np.array([M.V[i] for i in ids]); cen = P.mean(0)
            fn = -sum(np.cross(P[k], P[(k+1) % len(P)]) for k in range(len(P))); fn /= np.linalg.norm(fn) + 1e-12
            d, ix = tree.query(cen, k=200, distance_upper_bound=6)
            votes = {}
            for dd, i in zip(d, ix):
                if not np.isfinite(dd): break
                if abs(np.dot(N[i], fn)) < 0.4: continue
                k = lum[Mt[i]]; votes[k] = votes.get(k, 0) + A[i] / (dd + 1.0)
            col = max(votes, key=votes.get) if votes else BLACK
        out.append((ids, col, smooth, nrm))
    M.F = out


# ------------------------------------------------------------------ parts
def gear_part(r_wheel, w_wheel, strut, n_wheel, x_off=0.0):
    """part in its own frame: pivot at origin, strut down to the axle (0, 0, -strut)"""
    M = Mesh()
    prism(M, (0, 0, -strut/2), (0, 0, 1), 0.6, strut, 4, METAL, rot0=np.pi/4)
    prism(M, (x_off, 0, -strut), (1, 0, 0), r_wheel, w_wheel, n_wheel, TYRE, cap_col=HUB, rot0=np.pi/n_wheel)
    return M


def part_faces(M):
    V = [tuple(int(round(x*2))/2 for x in p) for p in M.V]
    return V


# ------------------------------------------------------------------ bytecode
def fbytes(ids, V, col, nrm, flat, base_fl=0x270):
    P = np.array([V[i] for i in ids], float)
    fl = base_fl | (0x01 if flat else 0x03)
    if any(i > 255 for i in ids): fl |= 0x400
    n = nrm
    nn = [int(round(n[0]*32767)), int(round(n[2]*32767)), int(round(n[1]*32767))]
    cen = P.mean(0); pt = [int(round(cen[0])), int(round(cen[2])), int(round(cen[1]))]
    if any(abs(x) > 127 for x in pt): fl &= ~0x200
    b = bytearray(struct.pack('<BHH', 0xFC, fl, col)) + struct.pack('<hhh', *nn)
    b += struct.pack('<bbb', *pt) if fl & 0x200 else struct.pack('<hhh', *pt)
    b.append(len(ids))
    b += b''.join(struct.pack('<H', i) for i in ids) if fl & 0x400 else bytes(ids)
    return bytes(b)


def tex_face(ids, V, nrm, uv):
    """textured rotor face, flags as HOKUT's rotor discs (0x64C: normal, short point, u16 idx, u16 UV)"""
    P = np.array([V[i] for i in ids], float)
    nn = [int(round(nrm[0]*32767)), int(round(nrm[2]*32767)), int(round(nrm[1]*32767))]
    cen = P.mean(0); pt = [int(round(cen[0])), int(round(cen[2])), int(round(cen[1]))]
    fl = 0x64C
    if any(abs(x) > 127 for x in pt): fl &= ~0x200
    b = bytearray(struct.pack('<BHH', 0xFC, fl, 0)) + struct.pack('<hhh', *nn)
    b += struct.pack('<bbb', *pt) if fl & 0x200 else struct.pack('<hhh', *pt)
    b.append(len(ids)) ; b += b''.join(struct.pack('<H', i) for i in ids)
    b += b''.join(struct.pack('<HH', u, v) for u, v in uv)
    return bytes(b)


class Tree:
    """painter-order tree emitter for a face set (+objects) with F/FlatInfo"""
    def __init__(s, V, info): s.V = V; s.info = info      # info: id(face) -> (col, flat)

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
        nn = [int(round(n[0]*32767)), int(round(n[2]*32767)), int(round(n[1]*32767))]
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
        a.emit(fbytes(f.ids, s.V, col, f.n, flat))


def mesh_faces(M, V, add_vertex=None):
    """Mesh -> bsp Faces with (col, flat).  Smooth faces whose vertices all share the colour stay smooth."""
    vcol = {}
    for ids, col, smooth, nrm in M.F:
        for i in ids: vcol.setdefault(i, set()).add(col)
    faces = []
    for ids, col, smooth, nrm in M.F:
        P = [V[i] for i in ids]
        keep = [k for k in range(len(ids)) if P[k] != P[k-1]]
        ids = [ids[k] for k in keep]
        if len(set(V[i] for i in ids)) < 3: continue
        flat = (not smooth) or any(len(vcol[i]) > 1 for i in ids)
        f = Face(ids, [V[i] for i in ids], (col, flat), nrm)
        if nrm is not None and np.dot(f.n, nrm) < 0:      # winding against the intended normal: flip
            ids = ids[::-1]; f = Face(ids, [V[i] for i in ids], (col, flat), nrm)
        f.smooth = smooth
        faces.append(f)
    return faces


def vertex_normals(faces, nV):
    VN = [np.zeros(3) for _ in range(nV)]
    for f in faces:
        for i in f.ids: VN[i] += f.n
    return VN


def main(glb_path, src, dst, preview=None):
    d = bytearray(open(src, 'rb').read())
    d = bytearray(grow_vas(d, GROW))        # CODE needs more than HOKUT's 0x7000 bytes of VA (+0x1000 worked for F14-37)
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    c = bytearray(d[code['ro']:code['ro'] + code['vs']])
    assert c[R1:R1+4] == b'\x1e\x1e\x82\x00', 'not HOKUT.SH?'
    g = AW(glb_path)
    M = build(g); colours(g, M)
    # rotor discs: vertices (not faces) in the main buffer
    mr = [M.add((x, y, ROTOR_Z)) for x, y in ((ROTOR_R, ROTOR_R), (-ROTOR_R, ROTOR_R), (-ROTOR_R, -ROTOR_R), (ROTOR_R, -ROTOR_R))]
    tr = [M.add((TR_X, TR_C[0] + dy, TR_C[1] + dz)) for dy, dz in ((TR_R, TR_R), (-TR_R, TR_R), (-TR_R, -TR_R), (TR_R, -TR_R))]
    V = [tuple(int(round(x)) for x in p) for p in M.V]
    faces = mesh_faces(M, V)
    VNl = [list(n) for n in vertex_normals(faces, len(V))]
    vcolour = {}
    for f in faces:
        for i in f.ids: vcolour.setdefault(i, f.col[0])

    def add_vertex(p, i, j, t):
        V.append(tuple(int(round(x)) for x in p))
        VNl.append(list((1-t)*np.array(VNl[i]) + t*np.array(VNl[j]))); vcolour[len(V)-1] = vcolour.get(i, BLACK)
        return len(V) - 1

    # gear parts (own buffers, slots after the main buffer; filled in later)
    gears = {
        'nose':  dict(piv=(0, 34, -6), strut=6.5, r=2.2, w=1.6, n=8, xo=0.0),
        'right': dict(piv=(16, -5, -5), strut=6.5, r=2.6, w=2.0, n=8, xo=0.0),
        'left':  dict(piv=(-16, -5, -5), strut=6.5, r=2.6, w=2.0, n=8, xo=0.0),
    }
    objs = []
    def gear_obj(name, G):
        px, py, pz = G['piv']; r = G['r']; s = G['strut']
        def e(a):
            a.cond('GEARDOWN', 'RESUME',
                   lambda: a.patch_c4('GEARPOS', 0x0A, F.SAR(1), 'RESUME', lambda: a.c4((px, pz, py), (0, 0, 0), 'part_' + name)))   # C4 pos is (x, up, fwd)
        return Obj('gear_' + name, (px - G['w'], py - r - 1, pz - s - r), (px + G['w'], py + s + r + 1, pz + 1), e)
    for k, G in gears.items(): objs.append(gear_obj(k, G))

    def rotor_obj(name, ids, lo, hi, nrm_up, frames):
        def e(a):
            L_end = a.new('R')
            for sgn in (1, -1):
                q = ids if sgn > 0 else ids[::-1]
                n = np.array(nrm_up, float) * sgn
                labs = [a.new('F') for _ in frames]
                a.emit(struct.pack('<BBH', 0x40, 0, len(frames)))
                for L in labs: a.rel16(L, -2)
                L_next = a.new('N')
                for L, (u0, v0, sz) in zip(labs, frames):
                    a.label(L)
                    uv = [(u0 + sz - 1, v0), (u0, v0), (u0, v0 + sz - 1), (u0 + sz - 1, v0 + sz - 1)]
                    if sgn < 0: uv = uv[::-1]
                    a.emit(tex_face(q, V, n, uv))
                    a.emit(b'\x48\x00'); a.rel16(L_next)
                a.label(L_next)
        return Obj(name, lo, hi, e)
    objs.append(rotor_obj('main_rotor', mr, (-ROTOR_R, -ROTOR_R, ROTOR_Z - 0.4), (ROTOR_R, ROTOR_R, ROTOR_Z + 0.4), (0, 0, 1), MR_UV))
    objs.append(rotor_obj('tail_rotor', tr, (TR_X - 0.4, TR_C[0] - TR_R, TR_C[1] - TR_R), (TR_X + 0.4, TR_C[0] + TR_R, TR_C[1] + TR_R), (1, 0, 0), TR_UV))

    B = Order(V, add_vertex)
    tree = B.build(faces, objs)
    nn, nf = count(tree)
    print(f'main: {nn} plane nodes, {nf} faces, {B.splits} splits, {len(V)} vertices')

    # parts
    part_data = {}
    base = len(V)
    for k, G in gears.items():
        PM = gear_part(G['r'], G['w'], G['strut'], G['n'], G['xo'])
        PV = [tuple(int(round(x)) for x in p) for p in PM.V]
        PV0 = list(PV)
        pf = mesh_faces(PM, PV)
        pvn = vertex_normals(pf, len(PV))
        def addv(p, i, j, t, PV=PV, pvn=pvn):
            PV.append(tuple(int(round(x)) for x in p)); pvn.append((1-t)*pvn[i] + t*pvn[j]); return len(PV) - 1
        PB = Order(PV, addv); pt = PB.build(pf, [])
        part_data[k] = (base, PV, pvn, pt)          # parts are drawn one at a time: they share the slots
    base += max(len(v[1]) for v in part_data.values())
    for k, (pb, PV, pvn, pt) in part_data.items(): shift_tree(pt, pb)
    print(f'vertex slots used: {base} (gear parts {len(V)}..{base-1})')
    if base > 700: sys.exit('too many vertex slots')

    def assemble(delta):
        a = Asm(R0)
        for k, v in VARS.items(): a.ext[k] = v + delta
        a.emit(struct.pack('<BBHH', 0x82, 0, len(V), 0))
        for v in V: a.emit(struct.pack('<hhh', *v))
        for i, n in enumerate(VNl):
            n = np.array([n[0], n[2], n[1]]); L = np.linalg.norm(n) or 1
            a.emit(struct.pack('<BHBbbb', 0xF6, i, vcolour.get(i, BLACK), *[int(round(x * 127 / L)) for x in n]))
        Tree(V, None).emit(a, tree)
        a.ret()
        for k, (pb, PV, pvn, pt) in part_data.items():
            a.emit(PART_HDR)                       # C4 parts need this header right before their 82 (as in HOKUT)
            a.label('part_' + k)
            # part ids are local; shift by its slot base
            a.emit(struct.pack('<BBHH', 0x82, 0, len(PV), pb * 8))
            for v in PV: a.emit(struct.pack('<hhh', *v))
            for i, n in enumerate(pvn):
                n = np.array([n[0], n[2], n[1]]); L = np.linalg.norm(n) or 1
                a.emit(struct.pack('<BHBbbb', 0xF6, pb + i, METAL, *[int(round(x * 127 / L)) for x in n]))
            GV = {i + pb: v for i, v in enumerate(PV)}
            Tree(GV, None).emit(a, pt)
            a.ret()
        return a.link()

    blob, _ = assemble(0)
    delta = len(blob) - (R1 - R0)
    blob, relocs = assemble(delta)
    nc = bytearray(c[:R0] + blob + c[R1:])
    for p in HDR_RELS:
        struct.pack_into('<h', nc, p, struct.unpack_from('<h', nc, p)[0] + delta)
    for p in LOD_RELS:
        struct.pack_into('<h', nc, p, TEX_OP - (p + 2))
    nc[TEX_OP+2:TEX_OP+16] = b'_AIRWOLF.PIC\0\0'
    room = nxt - code['va']
    print(f'high LOD {R1-R0} -> {len(blob)} bytes ({delta:+d}); CODE {len(nc)} / room {room}')
    if len(nc) > room: sys.exit('CODE does not fit')
    F.R0, F.R1 = R0, R1
    out = F.rebuild(d, pe, secs, code, nc, delta, relocs)
    open(dst, 'wb').write(out)
    print(f'{dst}: {len(out)} bytes')


def shift_tree(t, b):
    """renumber part-local vertex ids to global slots (in place)"""
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


if __name__ == '__main__':
    if len(sys.argv) < 4: sys.exit(__doc__)
    main(*sys.argv[1:5])
