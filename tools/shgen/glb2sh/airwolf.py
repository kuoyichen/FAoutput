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
GROW = 0x3000      # file stays far below FA's 64 KB SH limit

# ---- HOKUT.SH layout (CODE offsets) ----
R0, R1 = 0x5A, 0x478E                 # high LOD: main 82 .. old gear parts end (0x478E = '1E 1E' before LOD2)
# header rel16s: 0x10 (F2 trailer, from 0x12) and 0x46 (A6 detail skip, from 0x48) -> copies inside the new block
LOD_RELS = [0x3A, 0x42]               # C8 LOD switches -> point them at the texture op (0x4A) + high LOD
TEX_OP = 0x4A                         # E2 00 '_hokut.PIC' (renamed to _AIRWOLF.PIC)
PART_HDR = bytes.fromhex('ffff00006a0008008900 3300b500'.replace(' ', ''))
VARS = {'GEARDOWN': 0x6350, 'GEARPOS': 0x6356, 'RESUME': 0x635C}

BLACK, WHITE, GLASS, TYRE, METAL, HUB, INTERIOR = 0x44, 0x91, 0x9D, 0x3A, 0x34, 0x37, 0x9F
GEAR_W = 0x91                         # white gear struts and hubs
GLASS_UV = (150, 86, 32)              # stipple glass patch in _AIRWOLF.PIC (u, v, size)
# PIC layout (see make_pic): 3 main-rotor frames 84x84 at u = 0/86/172, v 0..83; 3 tail-rotor frames 48x48 at v 86
MR_UV = [(0, 0, 84), (86, 0, 84), (172, 0, 84)]
TR_UV = [(0, 86, 48), (50, 86, 48), (100, 86, 48)]
ROTOR_Z, ROTOR_R = 22, 57
TR_C, TR_R, TR_X = (-82, 10), 12, 8   # tail rotor centre (fwd, up), radius, plane x (right side)

BODY_STA = [41, 39, 36, 32, 27.5, 22.5, 17, 11, 5, -1, -8, -15, -22, -30, -38]
BOOM_STA = [-47, -54, -62, -70, -77, -83]
RING = (6, 4, 2)                      # half ring segments: top->widest, widest->lowest, lowest->bottom (24 points)
EP_X = 16.3                           # tail end plates (stabiliser tips)
BULKHEAD_Y, FLOOR_Z = 15, -4.0
TAIL_END = -86.5
SPON_STA = [14, 8, 2, -4, -10, -15, -19]


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


def prism(M, centre, axis, r, length, n, col, cap_col=None, rot0=0.0, rz=None, col_fn=None):
    """n-gon prism along a coordinate axis; r (and rz for an elliptic section, along the second section axis)"""
    axis = np.asarray(axis, float); c = np.asarray(centre, float)
    u = np.array([0, 0, 1.0]) if abs(axis[2]) < 0.9 else np.array([1.0, 0, 0])
    u = u - axis * np.dot(u, axis); u /= np.linalg.norm(u); v = np.cross(axis, u)
    rz = r if rz is None else rz
    rings = []
    for s in (-0.5, 0.5):
        rings.append([M.add(c + axis*s*length + r*np.cos(a)*u + rz*np.sin(a)*v)
                      for a in rot0 + np.arange(n) * 2*np.pi/n])
    a, b = rings
    for k in range(n):
        ang = rot0 + (k + 0.5) * 2*np.pi/n
        nrm = np.cos(ang)*u/r + np.sin(ang)*v/rz; nrm /= np.linalg.norm(nrm)
        cc = col_fn(nrm) if col_fn else col
        M.F.append(([a[k], a[(k+1) % n], b[(k+1) % n], b[k]], cc, False, tuple(nrm)))
    M.F.append((a[::-1], cap_col or col, False, tuple(-axis)))
    M.F.append((b, cap_col or col, False, tuple(axis)))
    return rings


def iprism(M, pts, axis, a0, a1, col, cap_col=None):
    """prism with an integer cross-section (vertices are whole feet in the SH, so anything thinner than a few
    feet must be laid out on the integer grid or it collapses when rounded).  pts: (s, t) polygon in the
    plane across `axis` (0 = x: (fwd, up), 1 = fwd: (x, up), 2 = up: (x, fwd)); runs from a0 to a1."""
    def P3(st, a):
        s_, t_ = st
        return {0: (a, s_, t_), 1: (s_, a, t_), 2: (s_, t_, a)}[axis]
    pts = [np.array(p, float) for p in pts]
    c = np.mean(pts, 0)
    r0 = [M.add(P3(p, a0)) for p in pts]; r1 = [M.add(P3(p, a1)) for p in pts]
    n = len(pts)
    for k in range(n):
        m = (pts[k] + pts[(k+1) % n]) / 2 - c
        M.F.append(([r0[k], r0[(k+1) % n], r1[(k+1) % n], r1[k]], col, False, P3(m, 0.0)))
    ax = np.zeros(3); ax[axis] = 1 if a1 > a0 else -1
    M.F.append((r0, cap_col or col, False, tuple(-ax))); M.F.append((r1, cap_col or col, False, tuple(ax)))


DIAMOND = [(1, 0), (0, 1), (-1, 0), (0, -1)]
OCTAGON = [(2, 1), (1, 2), (-1, 2), (-2, 1), (-2, -1), (-1, -2), (1, -2), (2, -1)]     # radius ~2.2, whole feet


def body_rings(M, sec, stations, every=1):
    out = []
    for y in stations:
        h = sec.half_ring(y, *RING)
        full = [(x, y, z) for x, z in h] + [(-x, y, z) for x, z in h[-2:0:-1]]
        out.append([M.add(p) for p in full[::every]])
    return out


def build(g):
    M = Mesh()
    # 1. fuselage: 24-point rings on the cabin, every second point (12) on the boom
    T, _ = g.grp(BODY, BODY_SKIP)
    S, lo, vox = voxel_solid(T, vox=0.5, lo=(-14, -100, -12), hi=(14, 46, 22))
    sec = Sections(S, lo, vox)
    rings = body_rings(M, sec, BODY_STA)
    boom = body_rings(M, sec, BOOM_STA, 2)
    K = len(rings[0]); KB = len(boom[0])
    nose = M.add((0, 42.3, float(np.mean([M.V[i][2] for i in rings[0]]))))
    loft(M, rings, None, close_front=nose)
    a, b = rings[-1], boom[0]
    for j in range(KB):
        M.F.append(([a[2*j], a[2*j+1], b[j]], None, True, None))
        M.F.append(([a[2*j+1], a[(2*j+2) % K], b[(j+1) % KB]], None, True, None))
        M.F.append(([a[2*j+1], b[(j+1) % KB], b[j]], None, True, None))
    tail = M.add((0, TAIL_END, float(np.mean([M.V[i][2] for i in boom[-1]]))))
    loft(M, boom, None, close_back=tail)
    M.cabin = sec                                      # for the interior plates
    M.nbody = len(M.F)

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
        loft(M, rs, None, close_front=f, close_back=bk)
    M.nspon = len(M.F)
    # 3. wingtip gun pods (black top / white bottom), pylons, 3 barrels each side (2 thin above, 1 thick below)
    topbot = lambda n: BLACK if n[2] > -0.2 else WHITE
    for side in (1, -1):
        Pp = g.points([59]) * np.array([side, 1, 1])
        plate(M, Pp, (0, 0, 1), 4, (BLACK, WHITE))
        xc = side * 22
        iprism(M, [(xc + dx, -2 + dz) for dx, dz in DIAMOND], 1, -2, 11, METAL)                  # thick, lower
        for xo in (-1, 1):                                                                        # thin, upper
            x0 = xc + xo
            iprism(M, [(x0, 0), (x0 + side, 0), (x0, 1)], 1, -3, 7, METAL)
    # 4. three rocket tubes under the belly
    for x in (-2, 0, 2):
        iprism(M, [(x + dx, -7 + dz) for dx, dz in DIAMOND], 1, 0, 13, BLACK, cap_col=TYRE)
    # 5. tail: stabiliser up to the end plates, end plates touching its tips, fin down to the boom
    P = g.points([250])
    fin = P[(np.abs(P[:, 0]) < 2.5) & ((P[:, 1] < -57) | (P[:, 2] > 12))]
    plate(M, fin, (1, 0, 0), 6, BLACK)
    stab = P[(np.abs(P[:, 0]) < 16.5) & (P[:, 1] > -57) & (P[:, 2] < 10)].copy()
    stab[:, 0] = np.clip(stab[:, 0], -EP_X, EP_X)
    plate(M, stab, (0, 0, 1), 6, (BLACK, WHITE))
    for side in (1, -1):
        ep = P[P[:, 0] * side > 14].copy(); ep[:, 0] = side * EP_X
        plate(M, ep, (side, 0, 0), 5, BLACK)
    # 6. rotor mast and tail rotor hub
    prism(M, (0, 0, 20), (0, 0, 1), 1.5, 5, 4, BLACK, rot0=np.pi/4)
    prism(M, (TR_X - 1.2, TR_C[0], TR_C[1]), (1, 0, 0), 1.0, 2.4, 4, BLACK, rot0=np.pi/4)
    # 7. dark cockpit interior seen through the glass: bulkhead behind the seats and a floor
    h = sec.half_ring(BULKHEAD_Y, 3, 2, 1) * 0.92
    bh = np.array([(x, BULKHEAD_Y, z) for x, z in h] + [(-x, BULKHEAD_Y, z) for x, z in h[-2:0:-1]])
    plate(M, bh, (0, 1, 0), 8, INTERIOR)
    fl = np.array([(x, y, FLOOR_Z) for x in (-4.5, 4.5) for y in (BULKHEAD_Y, 36)])
    plate(M, fl, (0, 0, 1), 4, INTERIOR)
    return M


COLOUR_GROUPS = [187, 192, 205, 3, 197, 198, 199, 202, 216, 217, 232, 17, 55, 56, 250]


def colours(g, M):
    """per face: material of the GLB skin hit by a ray through the face centre along its normal (the outermost
    hit, looking both ways), falling back to nearby triangles. GLB grey and black -> BLACK (Kuoyi: the grey is
    black), white -> WHITE, glass -> GLASS."""
    T, Mt = g.grp(COLOUR_GROUPS, BODY_SKIP)
    lum = {}
    for m in set(Mt.tolist()):
        mt = g.J['materials'][m] if m is not None else {}
        c = mt.get('pbrMetallicRoughness', {}).get('baseColorFactor', [0.5, 0.5, 0.5, 1])
        lum[m] = GLASS if (c[3] < 0.5 or 'Glass' in mt.get('name', '')) else (WHITE if np.mean(c[:3]) > 0.45 else BLACK)
    L = np.array([lum[m] for m in Mt])
    A0, E1, E2 = T[:, 0], T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
    C = T.mean(1); tree = cKDTree(C)
    def cast(o, d):
        P = np.cross(d, E2); det = (E1 * P).sum(1); ok = np.abs(det) > 1e-9
        inv = np.where(ok, 1 / np.where(ok, det, 1), 0); S = o - A0
        u = (S * P).sum(1) * inv; Q = np.cross(S, E1); v = (Q @ d) * inv; t = (E2 * Q).sum(1) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1)
        return t, hit
    out = []
    for ids, col, smooth, nrm in M.F:
        if col is None:
            P = np.array([M.V[i] for i in ids]); cen = P.mean(0)
            fn = -sum(np.cross(P[k], P[(k+1) % len(P)]) for k in range(len(P))); fn /= np.linalg.norm(fn) + 1e-12
            near = tree.query_ball_point(cen, 8.0)
            col = None
            if near:
                idx = np.array(near)
                sub = (A0[idx], E1[idx], E2[idx])
                Pc = np.cross(fn, sub[2]); det = (sub[1] * Pc).sum(1); ok = np.abs(det) > 1e-9
                inv = np.where(ok, 1 / np.where(ok, det, 1), 0); S = cen - sub[0]
                u = (S * Pc).sum(1) * inv; Q = np.cross(S, sub[1]); v = (Q @ fn) * inv; t = (sub[2] * Q).sum(1) * inv
                hit = ok & (u >= -0.02) & (v >= -0.02) & (u + v <= 1.04) & (np.abs(t) < 6)
                if hit.any():
                    k = np.argmax(np.where(hit, t, -1e9))          # outermost along the outward normal
                    col = L[idx[k]]
            if col is None:
                d, ix = tree.query(cen, k=12)
                vals, cnt = np.unique(L[ix], return_counts=True); col = vals[np.argmax(cnt)]
            col = int(col)
        out.append((ids, col, smooth, nrm))
    M.F = out
    repaint(M)


def repaint(M):
    """Kuoyi v3 notes: windows symmetric like the real one (wrap-around windscreen, a black post, one big side
    window per side, no small upper window), no black stripe in the white belly.  Fuselage and sponson faces on the
    left take the colour of their mirror face on the right; the windows and the belly are then painted by rule."""
    cen = [np.array([M.V[i] for i in ids]).mean(0) for ids, *_ in M.F[:M.nspon]]
    C = np.array(cen); right = np.where(C[:, 0] >= 0)[0]
    tree = cKDTree(C[right] * [1, 1, 1])
    F = list(M.F)
    for k, (ids, col, smooth, nrm) in enumerate(M.F[:M.nspon]):
        x, y, z = C[k]
        if x < -0.3:
            d, j = tree.query((-x, y, z)); col = M.F[right[j]][1]
        ax = abs(x)
        if col == GLASS: col = BLACK
        if k < M.nbody:
            if 27.5 < y < 32 and z > 0.5: col = GLASS                       # windscreen, lower front
            elif 22.5 < y < 27.5 and z > 3 and ax < 8: col = GLASS          # windscreen, upper
            elif 11 < y < 22.5 and ax > 6 and 1.5 < z < 9.5: col = GLASS    # side (door) window
            elif -38 < y < 22 and z < -1: col = WHITE                       # belly
        else:                                                               # sponson undersides white
            P = np.array([M.V[i] for i in ids]); fn = -sum(np.cross(P[i], P[(i+1) % len(P)]) for i in range(len(P)))
            if fn[2] < -0.2 * np.linalg.norm(fn): col = WHITE
        F[k] = (ids, col, smooth, nrm)
    M.F = F


# ------------------------------------------------------------------ parts
def gear_part(r_wheel, w_wheel, strut, n_wheel, x_off=0.0):
    """part in its own frame: pivot at origin, strut down to the axle (0, 0, -strut)"""
    M = Mesh()
    iprism(M, DIAMOND, 2, 0, -strut + 1, GEAR_W)                                                   # white strut
    iprism(M, [(f, -strut + u) for f, u in OCTAGON], 0, -w_wheel, w_wheel, TYRE)                   # black tyre, black sides (Kuoyi)
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
        if col == GLASS: a.emit(glass_face(f.ids, s.V, f.n))
        else: a.emit(fbytes(f.ids, s.V, col, f.n, flat))


def glass_face(ids, V, n):
    """see-through window: textured with the stipple glass patch (0xFF texels are transparent)"""
    P = np.array([V[i] for i in ids], float); n = np.asarray(n, float)
    e1 = np.cross(n, [0, 0, 1.0])
    if np.linalg.norm(e1) < 0.3: e1 = np.cross(n, [0, 1.0, 0])
    e1 /= np.linalg.norm(e1); e2 = np.cross(n, e1)
    q = np.c_[P @ e1, P @ e2] * 2.0; q -= q.min(0)
    m = q.max()
    if m > GLASS_UV[2] - 1: q *= (GLASS_UV[2] - 1) / m
    uv = [(GLASS_UV[0] + int(round(x)), GLASS_UV[1] + int(round(y))) for x, y in q]
    return tex_face(ids, V, n, uv)


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
        # Gouraud only on white: black 0x44 sits in a short palette ramp and smooth shading ran into the
        # neighbouring colours (rainbow bands in game, v2)
        flat = (not smooth) or col != WHITE or any(len(vcol[i]) > 1 for i in ids)
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
        'nose':  dict(piv=(0, 34, -6), strut=2, r=2, w=1, n=8, xo=0.0),      # axle at -8, tyre bottom at -10
        'right': dict(piv=(16, -5, -5), strut=2, r=2, w=1, n=8, xo=0.0),
        'left':  dict(piv=(-16, -5, -5), strut=2, r=2, w=1, n=8, xo=0.0),
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
                n = np.array(nrm_up, float) * sgn
                # FA's polygon fill only draws a face whose winding agrees with its normal (as for the body
                # and the glass); v1/v2 had the rotor winding reversed, so neither side was ever drawn
                q = list(ids); flip = np.dot(Face(q, [V[i] for i in q], 0).n, n) < 0
                if flip: q = q[::-1]
                labs = [a.new('F') for _ in frames]
                a.emit(struct.pack('<BBH', 0x40, 0, len(frames)))
                for L in labs: a.rel16(L, -2)
                L_next = a.new('N')
                for L, (u0, v0, sz) in zip(labs, frames):
                    a.label(L)
                    uv = [(u0 + sz - 1, v0), (u0, v0), (u0, v0 + sz - 1), (u0 + sz - 1, v0 + sz - 1)]
                    if flip: uv = uv[::-1]
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
    if base > 860: sys.exit('too many vertex slots')     # vertex table holds 900

    def assemble(delta):
        a = Asm(R0)
        for k, v in VARS.items(): a.ext[k] = v + delta
        a.emit(struct.pack('<BBHH', 0x82, 0, len(V), 0))
        for v in V: a.emit(struct.pack('<hhh', *v))
        for i, n in enumerate(VNl):
            n = np.array([n[0], n[2], n[1]]); L = np.linalg.norm(n) or 1
            a.emit(struct.pack('<BHBbbb', 0xF6, i, vcolour.get(i, BLACK), *[int(round(x * 127 / L)) for x in n]))
        # CODE is now longer than a rel16 can span: keep copies of the 18-byte F2 trailer and a '1E 1E'
        # (A6 detail-skip target) here, near the header, and point the header at them
        L_tree = a.new('T'); a.jmp(L_tree)
        a.label('TRAILER'); a.emit(trailer)
        a.label('RET1E'); a.emit(b'\x1e\x1e')
        a.label(L_tree)
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
        out = a.link(); labels.update(a.labels)
        return out

    labels = {}
    t0 = 0x12 + struct.unpack_from('<h', c, 0x10)[0]
    trailer = bytes(c[t0:t0 + 18])
    assert c[t0 + 18:t0 + 27] == bytes([1, 2, 3, 2, 1, 2, 3, 2, 1]), 'trailer not before the signature'
    blob, _ = assemble(0)
    delta = len(blob) - (R1 - R0)
    blob, relocs = assemble(delta)
    nc = bytearray(c[:R0] + blob + c[R1:])
    struct.pack_into('<h', nc, 0x10, labels['TRAILER'] - 0x12)
    struct.pack_into('<h', nc, 0x46, labels['RET1E'] - 0x48)
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
