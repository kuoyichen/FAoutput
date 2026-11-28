#!/usr/bin/env python3
"""SR-71 Blackbird (thread "修好 SR-71 黑鳥機頭", 2026-11-28).

Kuoyi first hand-morphed A10.SH into an SR-71 (length 304 units, nose not right).  A10.SH has no _PLafterBurner
import, so afterburner flames are impossible there without touching FA.EXE; this script builds the whole aircraft
procedurally instead (newsh / shuttle pipeline, donor F86.SH: gear + afterburner imports) at the same length:
  * chined forebody: one loft whose ring has a sharp chine edge; aft of s 58 ft the chine becomes the inner wing
    that runs into the nacelles
  * J58 nacelles with open inlet lip, dark duct and protruding conical spike, ejector nozzle
  * outer wings, inward-canted fins on the nacelles, pilot canopy + RSO window
  * 3D gear: 3-wheel main bogies retracting inwards (roll), twin nose wheel retracting forward
  * afterburner flames (drawn while _PLafterBurner)
Feet: s = aft from the nose tip, x right, z up (wing plane z 0).  U SH units per foot.
Usage: sr71.py OUTDIR [NAME]"""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, os.path.join(HERE, '..', 'shuttle')); sys.path.insert(0, HERE)
import numpy as np
import sr_core as core, geo, bsp
bsp.EPS = float(os.environ.get('EPS', '1.5'))
from mesh import Mesh

L_FT = 107.4
U = 304.0 / L_FT               # Kuoyi's A10-based SR-71 is 304 units long
S0 = 54.0                      # origin 54 ft aft of the nose tip
BODY, SPIKE, DUCT, GLASS, FRAME = 158, 157, 160, 74, 159
TYRE, GREY, FLAME, CORE = 160, 150, 182, 189
NAC_X = 14.5                   # nacelle axis (ft from the centreline), z 0
GZ = -7.0                      # ground (wheel bottoms), ft
FLAME_R, FLAME_L = 4.3, 44.0    # flame sheet half width / length, ft (SR71_1 cone was 22 ft)


def P(s, x=0.0, z=0.0): return (x * U, (S0 - s) * U, z * U)


# ------------------------------------------------------------------ fuselage + chines
def chine_ring(s, wb, zt, zb, wc, zch, zs, lo=None):
    """right half from the top to the bottom, then mirrored: rounded body top, shoulder at (wb, zs), sharp chine
    edge at (wc, zch), flatter lower surface back to the keel."""
    y = (S0 - s) * U
    lo = lo if lo is not None else zch - 0.3 * (zch - zb)
    half = [(0.0, zt), (0.5 * wb, zt - 0.1 * (zt - zs)), (0.85 * wb, zs + 0.45 * (zt - zs)), (wb, zs),
            (wb + 0.55 * (wc - wb), zch + 0.3 * (zs - zch)), (wc, zch),
            (wb + 0.5 * (wc - wb), lo), (0.95 * wb, zb + 0.35 * (lo - zb)), (0.5 * wb, zb + 0.05 * (lo - zb))]
    ring = half + [(0.0, zb)] + [(-x, z) for x, z in half[:0:-1]]
    return [(x * U, y, z * U) for x, z in ring]


#      s     wb    zt     zb     wc     zch    zs
# SR71_4 (Kuoyi + 3-view): central body 1.5x (wb, zt, zb, zs), chine edge pushed out by the body growth; chine
# planform from the 3-view: full width (flat) from the wing junction forward to just behind the cockpit (s ~28),
# then an ogive curve to the nose tip (SR71_3 narrowed almost linearly from s 36).
FUS = [(1.2, 0.42, 0.36, -0.45, 1.10, -0.09, 0.03),
       (4.0, 1.08, 0.93, -1.08, 2.85, -0.20, 0.07),
       (9.0, 1.95, 1.80, -1.95, 4.85, -0.35, 0.09),
       (15.0, 2.70, 2.55, -2.62, 6.30, -0.45, 0.15),
       (21.0, 3.30, 3.15, -3.08, 7.25, -0.50, 0.20),
       (28.0, 3.75, 3.60, -3.38, 7.90, -0.50, 0.27),
       (36.0, 4.05, 3.82, -3.60, 8.10, -0.45, 0.30),
       (45.0, 4.23, 3.93, -3.72, 8.20, -0.35, 0.27),
       (51.0, 4.32, 4.00, -3.75, 8.25, -0.25, 0.22),
       (56.0, 4.38, 4.02, -3.75, 9.90, -0.10, 0.18),
       (61.0, 4.41, 4.02, -3.75, 11.6, 0.00, 0.15),
       (75.0, 4.41, 3.99, -3.68, 11.6, 0.00, 0.15),
       (95.0, 4.05, 3.60, -3.30, 11.6, 0.00, 0.15),
       (97.5, 3.50, 3.20, -2.90, 4.10, 0.00, 0.15),
       (102.5, 2.25, 2.17, -1.72, 2.40, 0.00, 0.15),
       (106.6, 0.68, 0.75, -0.38, 0.75, 0.05, 0.15)]


def fuselage(M):
    rings = [chine_ring(*st) for st in FUS]
    f0 = len(M.F)
    geo.loft(M, rings, BODY, True, P(0.0, 0.0, -0.05), 'cap')
    # SR71_3: geo.loft's normal hint is radial from the ring centre; the flat chine top faces (rounded to whole
    # units) then got a horizontal hint, the winding came out facing DOWN and FA culled them from above (chines
    # missing in game).  Hint = outward perpendicular of the ring edge (rings run clockwise in (x, z)).
    K = len(rings[0])
    for j in range(len(rings) - 1):
        for k in range(K):
            n = np.zeros(3)
            for r in (rings[j], rings[j + 1]):
                (x0, _, z0), (x1, _, z1) = r[k], r[(k + 1) % K]
                e = np.array([-(z1 - z0), 0.0, x1 - x0]); L = np.linalg.norm(e)
                if L > 1e-9: n += e / L
            n /= (np.linalg.norm(n) or 1)
            i = f0 + j * K + k
            M.F[i] = (M.F[i][0], M.F[i][1], M.F[i][2], tuple(n))
    M.F[-1] = (M.F[-1][0], DUCT, False, M.F[-1][3])


def canopy(M):
    """pilot canopy: steep windscreen + glass hood (upper half of a small loft); RSO windows = 2 small plates."""
    def ring(s, w, zt, zb):
        r = geo.ring_pts((S0 - s) * U, w * U, zt * U, zb * U, zb * U, 12, 2.2)
        return [p for p in r[:4]] + [r[4]] + [r[8]] + [p for p in r[9:]]
    C = [(16.2, 0.77, 2.90, 2.3), (18.0, 1.60, 4.55, 2.3), (19.2, 1.82, 5.00, 2.3), (24.0, 1.90, 5.15, 2.6),
         (28.5, 1.33, 4.40, 3.0), (31.0, 0.63, 3.90, 3.3)]       # SR71_4: on the 1.5x body
    rs = [ring(*c) for c in C]
    def col(c, n):
        s = S0 - c[1] / U
        return GLASS if 16.0 < s < 25.0 else BODY
    geo.loft(M, rs, col, False, None, None)
    for sx in (1, -1):        # RSO side windows
        q = [P(33.0, sx * 3.75, 1.3), P(35.6, sx * 3.75, 1.3), P(35.6, sx * 3.5, 1.9), P(33.0, sx * 3.5, 1.9)]
        ids = [M.add(p) for p in q]
        M.F.append((ids, GLASS, False, (sx * 0.93, 0, 0.37)))


# ------------------------------------------------------------------ nacelles, spikes, fins, wings
NAC = [(57.0, 3.20), (59.0, 3.62), (64.0, 4.00), (74.0, 4.30), (90.0, 4.30), (97.0, 4.00), (101.0, 3.75)]


def nacelle(M, sx):
    dx = sx * NAC_X
    rings = [[(px + dx * U, py, pz) for px, py, pz in geo.ring_pts((S0 - s) * U, r * U, r * U, -r * U, 0.0, 10, 2.0)] for s, r in NAC]
    geo.loft(M, rings, BODY, True, None, None)
    # inlet: dark duct face just inside the lip, facing forward
    duct = [(px + dx * U, py, pz) for px, py, pz in geo.ring_pts((S0 - 57.6) * U, 3.05 * U, 3.05 * U, -3.05 * U, 0.0, 10, 2.0)]
    ids = [M.add(p) for p in duct]
    M.F.append((ids, DUCT, False, (0, 1.0, 0)))
    # lip: short ring from the duct face out to the lip edge (front annulus)
    lip_o = rings[0]
    io = [M.V[i] for i in ids]
    for k in range(10):
        f = [M.add(io[k]), M.add(io[(k + 1) % 10]), M.add(lip_o[(k + 1) % 10]), M.add(lip_o[k])]
        M.F.append((f, BODY, False, (0, 1.0, 0)))
    # nozzle: dark exhaust face with a lighter inner ring (ejector flaps)
    noz = [(px + dx * U, py, pz) for px, py, pz in geo.ring_pts((S0 - 101.0) * U, 3.75 * U, 3.75 * U, -3.75 * U, 0.0, 10, 2.0)]
    M.F.append(([M.add(p) for p in noz], DUCT, False, (0, -1.0, 0)))
    inner = [(px + dx * U, py, pz) for px, py, pz in geo.ring_pts((S0 - 101.05) * U, 2.6 * U, 2.6 * U, -2.6 * U, 0.0, 8, 2.0)]
    M.F.append(([M.add(p) for p in inner], 185, False, (0, -1.0, 0)))


def spike(M, sx):
    dx = sx * NAC_X
    prof = [(51.5, 0.7), (54.5, 1.45), (57.6, 2.15)]
    rings = [[(px + dx * U, py, pz) for px, py, pz in geo.ring_pts((S0 - s) * U, r * U, r * U, -r * U, 0.0, 8, 2.0)] for s, r in prof]
    geo.loft(M, rings, SPIKE, True, P(48.5, dx, 0.0), None)


def surface(M, secs, col, **kw):
    """geo.surface with correct normal hints.  SR71_3: geo.surface hints point from the section centre to the face
    (mostly fore/aft), so flat upper/lower and fin side faces could get either winding and be culled in FA.  Here
    the hint is from the closest point of the section's chord line (LE -> TE) to the face centre."""
    f0 = len(M.F)
    out = geo.surface(M, secs, col, **kw)
    where = {}
    for rings in out:
        for r in rings:
            for i in r: where[i] = r
    for fi in range(f0, len(M.F)):
        ids, c_, sm, h = M.F[fi]
        P = np.array([M.V[i] for i in ids]); c = P.mean(0)
        rs = []
        for i in ids:
            r = where.get(i)
            if r is not None and not any(r is q for q in rs): rs.append(r)
        if len(rs) != 2 or len(ids) != 4: continue          # caps keep their spanwise hint
        n = np.zeros(3)
        for r in rs:
            m = np.mean([M.V[i] for i in ids if i in r], 0)           # this face's edge on ring r
            le, te = np.array(M.V[r[0]]), np.array(M.V[r[4]]); d = te - le
            t = np.clip(np.dot(m - le, d) / np.dot(d, d), 0, 1); n += m - (le + t * d)
        L = np.linalg.norm(n)
        if L > 1e-9: M.F[fi] = (ids, c_, sm, tuple(n / L))
    return out


def wings(M):
    def W(x, le, ch, t, h=0.0): return dict(s=x * U, le=(S0 - le) * U, chord=ch * U, h=h * U, t=t * U)
    # outer wing from inside the nacelle to the tip (slight negative camber droop at the tip)
    surface(M, [W(NAC_X, 60.0, 36.5, 1.0), W(19.0, 70.5, 26.0, 0.8, -0.1), W(24.5, 80.5, 15.0, 0.5, -0.25),
                    W(27.8, 87.5, 6.5, 0.3, -0.35)], BODY, smooth=False)


def fins(M, sx):
    cant = np.tan(np.radians(15.0))
    def F(z, le, ch, t): return dict(s=z * U, le=(S0 - le) * U, chord=ch * U, h=(sx * (NAC_X - cant * (z - 4.1))) * U, t=t * U)
    surface(M, [F(3.6, 81.0, 17.5, 0.6), F(7.5, 86.0, 11.5, 0.45), F(11.6, 91.5, 5.5, 0.3)], BODY, mirror=False, vertical=True)


# ------------------------------------------------------------------ gear and flames
def main_gear(sx, Lz):
    """pivot at the origin (wing underside), axle Lz ft below; three wheels side by side."""
    M = Mesh(); L = Lz * U; r = 1.3 * U
    geo.strut(M, (0, 0, 0), (0, 0, -L + 0.3 * U), 0.32 * U, GREY)
    geo.strut(M, (0, 0.35 * U, -0.6 * U), (0, -0.9 * U, -L + 0.9 * U), 0.14 * U, GREY)      # drag brace
    geo.prism(M, [(-1.65 * U, -0.12 * U), (1.65 * U, -0.12 * U), (1.65 * U, 0.12 * U), (-1.65 * U, 0.12 * U)], 1, -0.25 * U, 0.25 * U, GREY)
    M.V = [tuple(v) for v in M.V]
    # move the axle bar (last 8 vertices) down to the axle
    for i in range(len(M.V) - 8, len(M.V)):
        x, y, z = M.V[i]; M.V[i] = (x, y, z - L)
    for cx in (-1.1, 0.0, 1.1):
        geo.wheel(M, (cx * U, 0, -L), r, 0.75 * U, TYRE, TYRE, n=6)
    M.F = [(f[0], f[1], False if f[1] == TYRE else f[2], *f[3:]) for f in M.F]
    return M


def nose_gear(Lz):
    M = Mesh(); L = Lz * U; r = 1.05 * U
    geo.strut(M, (0, 0, 0), (0, 0, -L + 0.2 * U), 0.26 * U, GREY)
    geo.strut(M, (0, 0, -0.5 * U), (0, 1.3 * U, -L + 0.6 * U), 0.12 * U, GREY)
    for cx in (-0.55, 0.55):
        geo.wheel(M, (cx * U, 0, -L), r, 0.55 * U, TYRE, TYRE, n=6)
    M.F = [(f[0], f[1], False if f[1] == TYRE else f[2], *f[3:]) for f in M.F]
    return M


def flame():
    """J58 afterburner plume: orange outer cone, yellow core, one bright shock-diamond ring."""
    M = Mesh()
    ring = lambda y, r, K: geo.ring_pts(y * U, r * U, r * U, -r * U, 0.0, K, 2.0)
    geo.loft(M, [ring(0.0, 3.3, 10), ring(-4.0, 2.7, 10), ring(-9.0, 2.0, 10)], FLAME, False, None, (0, -22.0 * U, 0))
    geo.loft(M, [ring(-0.2, 2.1, 8), ring(-3.0, 1.2, 8), ring(-4.5, 1.6, 8)], CORE, False, None, (0, -9.5 * U, 0))
    return M


def dedupe(M):
    """merge vertices that round to the same SH unit (lips, caps and plates add copies)."""
    key, remap, V = {}, [], []
    for v in M.V:
        k = tuple(int(round(x)) for x in v)
        if k not in key: key[k] = len(V); V.append(v)
        remap.append(key[k])
    F = []
    for ids, col, sm, n in M.F:
        q = [remap[i] for i in ids]
        q = [q[k] for k in range(len(q)) if q[k] != q[k - 1]]
        if len(set(q)) >= 3: F.append((q, col, sm, n))
    M.V, M.F = V, F
    return M


def build(outdir, name='SR71'):
    os.makedirs(outdir, exist_ok=True)
    M = Mesh()
    fuselage(M); canopy(M); wings(M)
    for sx in (1, -1):
        nacelle(M, sx); spike(M, sx); fins(M, sx)
    dedupe(M); print('verts', len(M.V), 'faces', len(M.F))
    if os.environ.get('DRY'): return
    g = []
    for sx in (1, -1):        # SR71_2: F-14 style animated flame (3 frames + 3 s grow), twice the SR71_1 length
        G = core.Gear('A' + 'RL'[sx < 0], None, P(101.1, sx * NAC_X, 0.0), var='AB', anim=False)
        G.flame = (int(round(FLAME_R * U)), int(round(FLAME_L * U))); g.append(G)
    mz = -1.6                                     # inner wing underside at x 8.4
    for sx in (1, -1):
        g.append(core.Gear('RL'[sx < 0], main_gear(sx, mz - GZ - 1.3), P(65.0, sx * 8.4, mz), field=0x0C, neg=(sx > 0)))
    nz = -3.3                                    # SR71_4: belly of the 1.5x body at s 27
    g.append(core.Gear('N', nose_gear(nz - GZ - 1.05), P(27.0, 0, nz), field=0x0A, neg=True))
    out = os.path.join(outdir, name + '.SH')
    import sr_flame
    sr_flame.write_pic(os.path.join(outdir, '_SR71.PIC'), os.path.join(outdir, 'pic_preview.png'))
    r = core.build(os.path.join(REPO, 'SH', 'F86.SH'), out, M, g, [], pic_name='_sr71.PIC',
                   smooth_ok=lambda c: c not in (DUCT, GLASS, TYRE, FLAME, CORE, 185), grow=0x5000)
    fix_header(out)
    return out


def fix_header(path):
    """shuttle lessons: trailer radius stored << 8 (SHUT-21) and the op 78 box must cover the model (SHUT-23)."""
    from sh_subdivide import pe_sections
    d = bytearray(open(path, 'rb').read())
    pe, opt, secs = pe_sections(d); code = next(s for s in secs if s['name'] == 'CODE')
    c0 = code['ro']
    R = struct.unpack_from('<H', d, c0 + 4)[0]
    p78 = d.find(b'\x78\x00', c0 + 0x40, c0 + 0x60); assert p78 == c0 + 0x4E, hex(p78 - c0)
    struct.pack_into('<3h', d, p78 + 4, R, R, R)
    T = 0x12 + struct.unpack_from('<h', d, c0 + 0x10)[0]
    assert d[c0 + T - 3] == 0x38, 'F2 must point at the trailer copy'
    struct.pack_into('<i', d, c0 + T, R << 8)
    open(path, 'wb').write(d)
    print('header: radius', R, 'op78 box', R, 'trailer', R << 8)


if __name__ == '__main__':
    build(*sys.argv[1:])
