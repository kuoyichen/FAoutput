"""B-17G geometry for the SH generator (gen_b17.py).

Coordinates: SH vertex units, x right, y forward, z up (the order of an 82 vertex buffer).
Scale: 4 units per foot, the same scale as FA's A47 (C-47) model, so the B-17 is about 415 units
across the wings and 300 units long.  Dimensions below are in feet: `s` = station from the nose tip
(aft positive), `y` = span (right positive), `z` = height above the fuselage centreline.
Origin = station 32 ft (wing centre section), on the fuselage centreline.

FA has no z-buffer, so the shape is built from pieces that touch but do not pass through each other:
wing roots, fin, tailplane and turrets start on the fuselage surface, and each nacelle is a pod ahead of
the wing leading edge plus a fairing on top of the wing and one below it, whose edges lie on the wing
skin.  That keeps the draw-order compiler from cutting faces (each cut costs vertices; FA allows 900 per
object and stock models stay under ~640).

Every face carries an outward hint so its winding can be set the FA way (sum PxP points inward).
"""
import math
import numpy as np

U = 4.0                      # SH units per foot
S0 = 32.0                    # station of the origin

OLIVE, OLIVE_D, GREY, GLASS, DARK, BLACK = 0x6C, 0x6D, 0x98, 0x86, 0x9D, 0x3C
TYRE = 0x9E


def P(s, y, z):
    """feet (station, span, height) -> SH units (x, fwd, up)"""
    return (y * U, (S0 - s) * U, z * U)


def newell(Pts):
    Pts = np.array(Pts, float); n = np.zeros(3)
    for k in range(len(Pts)): n += np.cross(Pts[k], Pts[(k + 1) % len(Pts)])
    return n


class Mesh:
    def __init__(s, name=''):
        s.name = name; s.V = []; s.F = []      # F: dict(ids, col, out (hint, x/fwd/up), tag)

    def v(s, p):
        s.V.append(tuple(float(x) for x in p)); return len(s.V) - 1

    def face(s, ids, col, out, tag=''):
        s.F.append(dict(ids=list(ids), col=col, out=np.array(out, float), tag=tag))

    def plate(s, ids, col, tag=''):
        """two-sided flat panel: both windings"""
        n = newell([s.V[i] for i in ids])
        s.face(ids, col, n, tag); s.face(ids[::-1], col, -n, tag)


# ---------------------------------------------------------------- fuselage
# station, half width, top, bottom (feet)
FUS = [
    (0.0, 1.0, 0.2, -1.6),
    (1.2, 2.1, 1.3, -2.6),
    (3.0, 2.9, 2.2, -3.4),
    (5.5, 3.4, 2.9, -3.9),
    (9.0, 3.7, 3.4, -4.1),
    (12.5, 3.8, 3.8, -4.2),
    (16.0, 3.9, 5.1, -4.3),
    (19.5, 3.9, 5.3, -4.3),
    (26.0, 3.9, 5.0, -4.3),
    (36.0, 3.9, 4.8, -4.2),
    (44.0, 3.6, 4.4, -3.8),
    (50.0, 3.2, 3.9, -3.1),
    (56.0, 2.6, 3.2, -2.1),
    (62.0, 2.0, 2.6, -1.2),
    (68.0, 1.4, 2.1, -0.4),
    (72.5, 1.0, 1.8, 0.1),
]
BAY = (26.0, 36.0)           # bomb bay = the two bottom faces of this fuselage segment
TAILGUN = (72.5, 75.0)       # tail gun housing behind the last station


def ring_angles(n):
    """angles (deg) from top, going down the right side then up the left side; n even"""
    return [90 - 360.0 * k / n for k in range(n)]


def ring_pt(st, a, ex=2.6):
    s, w, zt, zb = st
    zc, h = (zt + zb) / 2, (zt - zb) / 2
    c, si = math.cos(math.radians(a)), math.sin(math.radians(a))
    x = w * math.copysign(abs(c) ** (2 / ex), c)
    z = zc + h * math.copysign(abs(si) ** (2 / ex), si)
    return (s, x, z)


class Fuselage:
    """lofted rings; also answers 'where is the skin' for parts that sit on it"""
    def __init__(s, n, stations):
        s.n = n; s.st = stations; s.A = ring_angles(n)
        s.R = [[ring_pt(t, a) for a in s.A] for t in stations]      # (s, y, z) feet

    def ring_at(s, sta):
        st = [t[0] for t in s.st]
        sta = min(max(sta, st[0]), st[-1])
        for i in range(len(st) - 1):
            if st[i] <= sta <= st[i + 1]:
                t = (sta - st[i]) / (st[i + 1] - st[i])
                return [(sta, a[1] + t * (b[1] - a[1]), a[2] + t * (b[2] - a[2])) for a, b in zip(s.R[i], s.R[i + 1])]

    def side_y(s, sta, z, side=1):
        """|y| of the skin at station sta, height z, on the right (side=1) or left"""
        R = s.ring_at(sta); n = len(R)
        best = 0.0
        for k in range(n):
            a, b = R[k], R[(k + 1) % n]
            if (a[2] - z) * (b[2] - z) <= 0 and a[2] != b[2]:
                t = (z - a[2]) / (b[2] - a[2]); y = a[1] + t * (b[1] - a[1])
                if y * side > best: best = y * side
        return best

    def top_z(s, sta, y, top=True):
        """height of the skin at station sta, span y (top or bottom)"""
        R = s.ring_at(sta); n = len(R)
        best = None
        for k in range(n):
            a, b = R[k], R[(k + 1) % n]
            if (a[1] - y) * (b[1] - y) <= 0 and a[1] != b[1]:
                t = (y - a[1]) / (b[1] - a[1]); z = a[2] + t * (b[2] - a[2])
                if best is None or (z > best if top else z < best): best = z
        return best

    def mesh(s, detail=True):
        M = Mesh('fus'); n = s.n; A = s.A
        ids = [[M.v(P(*p)) for p in ring] for ring in s.R]
        nose = M.v(P(-0.25, 0, -0.5))
        for i in range(len(s.st) - 1):
            s1, s2 = s.st[i][0], s.st[i + 1][0]
            for k in range(n):
                a1, a2 = A[k], A[(k + 1) % n]
                mid = math.radians(a1 - 180 / n)          # angles run downwards; avoids the wrap at the last face
                out = (math.cos(mid), 0, math.sin(mid))
                col = OLIVE if math.sin(mid) > -0.45 else GREY
                if detail:
                    if s2 <= 5.5 and math.sin(mid) > -0.75: col = GLASS                 # glazed nose
                    if 12.5 <= s1 and s2 <= 16.0 and math.sin(mid) > 0.25: col = GLASS  # cockpit glazing
                tag = ''
                if (s1, s2) == BAY and math.sin(mid) < -0.8:
                    tag = 'bayL' if math.cos(mid) < 0 else 'bayR'
                M.face([ids[i][k], ids[i][(k + 1) % n], ids[i + 1][(k + 1) % n], ids[i + 1][k]], col, out, tag)
        for k in range(n):        # nose cap (fan); the tail is closed by the tail-gun housing
            M.face([nose, ids[0][(k + 1) % n], ids[0][k]], GLASS if detail else OLIVE, (0, 1, 0))
        M.ids = ids
        return M


# ---------------------------------------------------------------- wings
WING_Z0, DIHEDRAL = -1.7, 4.5
ENG_Y = (15.0, 29.0)          # inboard / outboard nacelle span stations
NAC_R = 2.5
TIP = {50.4: (34.3, 38.9, 0.8), 51.2: (35.0, 38.6, 0.6), 51.9: (36.3, 38.0, 0.3)}


def wing_le(y): return 21.0 + 0.27 * (y - 3.0) if y <= 49.5 else TIP[round(y, 1)][0]
def wing_te(y): return 40.0 - 0.03 * max(0.0, y - 20.0) if y <= 49.5 else TIP[round(y, 1)][1]
def wing_t(y): return 3.4 - 0.05 * (y - 3.0) if y <= 49.5 else TIP[round(y, 1)][2]
def wing_z(y): return WING_Z0 + (abs(y) - 3.0) * math.tan(math.radians(DIHEDRAL))


def wing_sections(detail):
    ys = [None, ENG_Y[0] - NAC_R - 0.3, ENG_Y[0] + NAC_R + 0.3, ENG_Y[1] - NAC_R - 0.3, ENG_Y[1] + NAC_R + 0.3]
    if detail == 2: ys += [41.0, 47.5, 50.4, 51.2, 51.9]
    elif detail == 1: ys += [47.5, 51.9]
    else: ys = [None, 51.9]
    return ys


def wing_pts(y):
    """aerofoil points at span y (feet): LE, upper 30 %, TE, lower 30 %"""
    le, te, t, z = wing_le(y), wing_te(y), wing_t(y), wing_z(y); c = te - le
    return [(le, y, z), (le + 0.3 * c, y, z + 0.6 * t), (te, y, z), (le + 0.3 * c, y, z - 0.4 * t)]


def wing(side, fus, detail=2):
    """root row on the fuselage skin"""
    M = Mesh('wing'); sg = 1 if side > 0 else -1
    rows = []
    for y in wing_sections(detail):
        if y is None:     # root: each point moved onto the fuselage side
            pts = [(s, fus.side_y(s, z, sg) * sg, z) for s, _, z in wing_pts(3.8)]
        else:
            pts = [(s, sg * yy, z) for s, yy, z in wing_pts(y)]
        rows.append([M.v(P(*p)) for p in pts])
    for i, (a, b) in enumerate(zip(rows, rows[1:])):          # tag = spanwise strip number
        M.face([a[0], a[1], b[1], b[0]], OLIVE, (0, 0.3, 1), i)
        M.face([a[1], a[2], b[2], b[1]], OLIVE, (0, -0.1, 1), i)
        M.face([a[2], a[3], b[3], b[2]], GREY, (0, -0.1, -1), i)
        M.face([a[3], a[0], b[0], b[3]], GREY, (0, 0.3, -1), i)
    M.face(rows[-1], GREY, (sg, 0, 0), len(rows) - 2)
    return M


def wing_surface_z(s, y, upper=True):
    """height of the wing skin (feet) at station s, span y (inside one straight strip)"""
    le, u, te, lo = wing_pts(abs(y))
    q = u if upper else lo
    if s <= q[0]: t = (s - le[0]) / (q[0] - le[0]); return le[2] + t * (q[2] - le[2])
    t = (s - q[0]) / (te[0] - q[0]); return q[2] + t * (te[2] - q[2])


# ---------------------------------------------------------------- engines
def nacelle(y, detail=True):
    """pod ahead of the wing + fairings above and below it whose edges lie on the wing skin.
    Returns (mesh, prop position (x, up, fwd) in SH units)."""
    M = Mesh('nac'); n = 8
    ya = abs(y)
    le, te = wing_le(ya), wing_te(ya); c = te - le
    zc = wing_z(ya) + 0.25
    sf = le - 8.0
    ang = [2 * math.pi * k / n for k in range(n)]           # from the top, towards +y
    def ring(sta, r, dz=0.0):
        return [M.v(P(sta, y + r * math.sin(a), zc + dz + r * math.cos(a))) for a in ang]
    pod = [ring(sf, 2.1), ring(sf + 1.2, NAC_R)] if False else [ring(sf + 0.4, 2.3)]
    lr = [M.v(P(le, y + 2.4 * math.sin(a), (wing_z(y) if k in (2, 6) else zc + 2.4 * math.cos(a))))
          for k, a in enumerate(ang)]          # last ring: its side points are the wing leading edge
    pod.append(lr)
    for a, b in zip(pod, pod[1:]):
        for k in range(n):
            am = ang[k] + math.pi / n
            col = OLIVE if math.cos(am) > -0.4 else GREY
            M.face([a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]], col, (math.sin(am), 0, math.cos(am)), 'pod')
    M.face(pod[0], DARK, (0, 1, 0), 'pod')
    def half(sta, r, dz, upper, ks):
        out = []
        for k in ks:
            a = ang[k]; yy = y + r * math.sin(a); zz = zc + dz + r * math.cos(a)
            zw = wing_surface_z(sta, yy, upper)
            if k in (2, 6): zz = zw + (0.3 if upper else -0.3)     # just off the skin so the face order is clear
            elif upper and zz < zw + 0.25: zz = zw + 0.25
            elif not upper and zz > zw - 0.25: zz = zw - 0.25
            out.append(M.v(P(sta, yy, zz)))
        return out
    for upper, sta, r, dz, end in (() if not detail else ((True, le + 0.3 * c, 1.9, 0.5, (le + 0.65 * c, 0.4)),
                                   (False, le + 0.3 * c, 1.6, -0.3, (le + 0.5 * c, -0.4)))):
        ks = [6, 7, 0, 1, 2] if upper else [2, 3, 4, 5, 6]
        r0 = [lr[k] for k in ks]; r1 = half(sta, r, dz, upper, ks)
        col = OLIVE if upper else GREY
        for k in range(4):
            am = ang[ks[k]] + math.pi / n
            M.face([r0[k], r0[k + 1], r1[k + 1], r1[k]], col, (math.sin(am), -0.2, math.cos(am)), 'up' if upper else 'lo')
        # tail of the fairing: a point on the wing skin behind the ridge
        es, edz = end
        tip = M.v(P(es, y, wing_surface_z(es, y, upper) + edz + (0.2 if upper else -0.2)))
        for k in range(4):
            am = ang[ks[k]] + math.pi / n
            M.face([r1[k], r1[k + 1], tip], col, (math.sin(am), -1, math.cos(am)), 'up' if upper else 'lo')
    if not detail: M.face(lr, GREY, (0, -1, 0), 'pod')
    prop = P(sf - 0.6, y, zc)
    return M, (round(prop[0]), round(prop[2]), round(prop[1]))


# ---------------------------------------------------------------- tail
STAB = [(None, 60.0, 73.0, 1.2), (15.0, 65.0, 72.2, 0.8), (19.5, 67.3, 71.8, 0.55),
        (21.0, 68.8, 71.4, 0.35), (21.6, 70.0, 71.0, 0.2)]
STAB_Z = 0.9
HINGE = 71.0
# fin outline (station, height) from the dorsal fillet over the top to the rudder hinge
FIN_LE = [(44.0, None), (50.0, 4.9), (55.5, 5.9), (58.5, 7.2), (62.5, 9.6), (65.5, 11.3), (67.6, 12.1), (69.6, 12.4), (70.9, 12.3)]
FIN_T = 0.5                   # half thickness (ft)
RUDDER = [(1.8, 74.2), (5.0, 74.4), (8.5, 74.2), (10.5, 73.6), (11.6, 72.6), (12.2, 71.2)]   # z, TE


def stab(side, fus, detail=True):
    M = Mesh('stab'); sg = 1 if side > 0 else -1
    sec = STAB if detail else [STAB[0], STAB[2], STAB[-1]]
    rows = []
    for y, le, te, t in sec:
        c = te - le; z = STAB_Z
        pts = [(le, y, z), (le + 0.3 * c, y, z + 0.5 * t), (te, y, z), (le + 0.3 * c, y, z - 0.5 * t)]
        if y is None: pts = [(s, fus.side_y(min(s, fus.st[-1][0]), zz, sg) * sg, zz) for s, _, zz in pts]
        else: pts = [(s, sg * yy, zz) for s, yy, zz in pts]
        rows.append([M.v(P(*p)) for p in pts])
    for i, (a, b) in enumerate(zip(rows, rows[1:])):          # tag = spanwise strip number
        M.face([a[0], a[1], b[1], b[0]], OLIVE, (0, 0.3, 1), i)
        M.face([a[1], a[2], b[2], b[1]], OLIVE, (0, -0.1, 1), i)
        M.face([a[2], a[3], b[3], b[2]], GREY, (0, -0.1, -1), i)
        M.face([a[3], a[0], b[0], b[3]], GREY, (0, 0.3, -1), i)
    M.face(rows[-1], GREY, (sg, 0, 0), len(rows) - 2)
    return M


def fin(fus, detail=True):
    """slab of constant thickness: two flat sides (triangulated), LE / top strip; root on the fuselage top"""
    M = Mesh('fin')
    le = FIN_LE if detail else [FIN_LE[0], FIN_LE[3], FIN_LE[6], FIN_LE[-1]]
    root_st = [HINGE] + [t[0] for t in fus.st if FIN_LE[0][0] < t[0] < HINGE][::-1] + [FIN_LE[0][0]]
    sides = {}
    for sg in (1, -1):
        y = sg * FIN_T
        root = [M.v(P(s, y, fus.top_z(s, y))) for s in root_st]                    # aft -> fwd along the skin
        outl = [M.v(P(s, y, z)) for s, z in le[1:]]                                 # fwd -> aft over the top
        sides[sg] = (root, outl)
        poly = root + outl
        for a, b, c in ear_clip([M.V[i] for i in poly]):
            M.face([poly[a], poly[b], poly[c]], OLIVE, (sg, 0, 0))
    (rr, orr), (rl, ol) = sides[1], sides[-1]
    er = [rr[-1]] + orr; el = [rl[-1]] + ol
    for k in range(len(er) - 1):
        d = np.array(M.V[er[k + 1]]) - np.array(M.V[er[k]])
        M.face([er[k], er[k + 1], el[k + 1], el[k]], OLIVE, (0, d[2], -d[1]))
    M.face([rr[0], orr[-1], ol[-1], rl[0]], OLIVE, (0, -1, 0))
    return M


def ear_clip(pts):
    """triangulate a planar simple polygon lying in an x = const plane: returns index triples"""
    P2 = [(p[1], p[2]) for p in pts]
    idx = list(range(len(P2)))
    area = sum(P2[i][0] * P2[(i + 1) % len(P2)][1] - P2[(i + 1) % len(P2)][0] * P2[i][1] for i in range(len(P2)))
    sgn = 1 if area > 0 else -1
    def cross(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    def inside(p, a, b, c):
        return cross(a, b, p) * sgn > 0 and cross(b, c, p) * sgn > 0 and cross(c, a, p) * sgn > 0
    tris = []
    for _ in range(1000):
        if len(idx) <= 3: break
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            if cross(P2[i0], P2[i1], P2[i2]) * sgn <= 1e-9: continue
            if any(inside(P2[j], P2[i0], P2[i1], P2[i2]) for j in idx if j not in (i0, i1, i2)): continue
            tris.append((i0, i1, i2)); idx.pop(k); break
        else:
            break
    if len(idx) == 3: tris.append(tuple(idx))
    return tris


def rudder(state):
    """rudder part (body coordinates), deflected 0 / +1 (trailing edge to the right) / -1"""
    M = Mesh('rudder'); ang = math.radians(16 * state)
    top = []
    for z, te in RUDDER:
        d = te - HINGE
        top.append(M.v(P(HINGE + d * math.cos(ang), d * math.sin(ang), z)))
    h0 = M.v(P(HINGE, 0, RUDDER[0][0])); h1 = M.v(P(HINGE, 0, RUDDER[-1][0]))
    M.plate([h1] + top[::-1] + [h0], OLIVE)
    return M


# ---------------------------------------------------------------- flaps (split flaps, extended state only)
FLAP = (4.5, 31.0)


def flap(side):
    M = Mesh('flap'); sg = 1 if side > 0 else -1
    ys = [FLAP[0], ENG_Y[0], ENG_Y[1], FLAP[1]]
    hinge, tip = [], []
    for y in ys:
        le, te = wing_le(y), wing_te(y); c = te - le
        hs = te - 0.25 * c; L = 0.25 * c; a = math.radians(40)
        zh = wing_surface_z(hs, y, False) - 0.1
        hinge.append(M.v(P(hs, sg * y, zh)))
        tip.append(M.v(P(hs + L * math.cos(a), sg * y, zh - L * math.sin(a))))
    for k in range(len(ys) - 1):
        M.plate([hinge[k], hinge[k + 1], tip[k + 1], tip[k]], GREY)
    return M


# ---------------------------------------------------------------- bomb bay parts
def bay_parts(fus, fm):
    """closed doors (the two fuselage bottom faces) and open bay (black ceiling + doors hanging down)"""
    closed = Mesh('bayC'); opened = Mesh('bayO')
    for f in fm.F:
        if f['tag'] in ('bayL', 'bayR'):
            closed.face([closed.v(fm.V[i]) for i in f['ids']], f['col'], f['out'])
    i0 = [t[0] for t in fus.st].index(BAY[0]); i1 = i0 + 1
    kb = fus.A.index(-90.0); kr, kl = kb - 1, (kb + 1) % fus.n
    hr0, hr1, hl0, hl1 = (P(*fus.R[i][k]) for i, k in ((i0, kr), (i1, kr), (i0, kl), (i1, kl)))
    opened.face([opened.v(p) for p in (hr0, hr1, hl1, hl0)], BLACK, (0, 0, -1))
    for h0, h1, sg in ((hr0, hr1, 1), (hl0, hl1, -1)):
        w = abs(h0[0])
        ids = [opened.v(h0), opened.v(h1), opened.v((h1[0] + sg * 0.6, h1[1], h1[2] - w)),
               opened.v((h0[0] + sg * 0.6, h0[1], h0[2] - w))]
        opened.plate(ids, OLIVE_D)
    return closed, opened


# ---------------------------------------------------------------- turrets and guns
def dome(M, fus, s, r, h, col, n=6, up=1, base_col=None):
    """faceted dome on the fuselage top (up=+1) or bowl under it (up=-1); base ring on the skin"""
    b, m = [], []
    for k in range(n):
        a = 2 * math.pi * k / n; ss, yy = s + r * math.cos(a), r * math.sin(a)
        b.append(M.v(P(ss, yy, fus.top_z(ss, yy, up > 0))))
    zb0 = fus.top_z(s, 0, up > 0)
    for k in range(n):
        a = 2 * math.pi * k / n
        m.append(M.v(P(s + 0.8 * r * math.cos(a), 0.8 * r * math.sin(a), zb0 + up * 0.6 * h)))
    top = M.v(P(s, 0, zb0 + up * h))
    for k in range(n):
        a = 2 * math.pi * (k + 0.5) / n
        out = (math.sin(a), -math.cos(a), up * 0.4)
        M.face([b[k], b[(k + 1) % n], m[(k + 1) % n], m[k]], base_col or col, out)
        M.face([m[k], m[(k + 1) % n], top], col, (math.sin(a), -math.cos(a), up * 1.2))
    return zb0


def gun_pair(M, s0, s1, y, z, sep=0.7):
    """two barrels shown as one thin two-sided horizontal plate"""
    M.plate([M.v(P(s0, y - sep / 2, z)), M.v(P(s1, y - sep / 2, z)), M.v(P(s1, y + sep / 2, z)), M.v(P(s0, y + sep / 2, z))], BLACK)


def chin_box(M, fus, s0, s1, w, depth):
    """box hanging under the nose: its top edges sit on the skin, no top face"""
    c = {}
    zbot = fus.top_z(s1, 0, False) - depth
    for i, s in enumerate((s0, s1)):
        for j, y in enumerate((-w, w)):
            c[i, j, 1] = M.v(P(s, y, fus.top_z(s, y, False))); c[i, j, 0] = M.v(P(s, y, zbot))
    M.face([c[0, 0, 0], c[0, 1, 0], c[0, 1, 1], c[0, 0, 1]], OLIVE_D, (0, 1, 0))
    M.face([c[1, 0, 0], c[1, 0, 1], c[1, 1, 1], c[1, 1, 0]], OLIVE_D, (0, -1, 0))
    M.face([c[0, 1, 0], c[1, 1, 0], c[1, 1, 1], c[0, 1, 1]], OLIVE_D, (1, 0, 0))
    M.face([c[0, 0, 0], c[0, 0, 1], c[1, 0, 1], c[1, 0, 0]], OLIVE_D, (-1, 0, 0))
    M.face([c[0, 0, 0], c[1, 0, 0], c[1, 1, 0], c[0, 1, 0]], OLIVE_D, (0, 0, -1))
    return zbot


def tail_housing(M, fus):
    """tail-gun housing: closes the end of the fuselage and tapers back to a glazed end"""
    s0, s1 = TAILGUN
    last = fus.R[-1]; n = len(last)
    zc = (fus.st[-1][2] + fus.st[-1][3]) / 2
    front = [M.v(P(s0, y, z)) for _, y, z in last]
    back = [M.v(P(s1, y * 0.75, zc + (z - zc) * 0.8)) for _, y, z in last]
    for k in range(n):
        a = math.radians(fus.A[k] - 180 / n)
        M.face([front[k], front[(k + 1) % n], back[(k + 1) % n], back[k]], OLIVE_D, (math.cos(a), -0.3, math.sin(a)))
    M.face(back, GLASS, (0, -1, 0))
    return zc


def turrets(fus, detail=True):
    """separate meshes: top (Sperry), chin (Bendix), ball (Sperry), tail (Cheyenne)"""
    T, C, B, H = Mesh('top'), Mesh('chin'), Mesh('ball'), Mesh('tail')
    z = dome(T, fus, 20.5, 2.0, 2.2, GLASS, base_col=OLIVE_D)
    if detail: gun_pair(T, 17.6, 19.6, 0, z + 1.2)
    zb = chin_box(C, fus, 1.6, 4.4, 1.3, 1.6)
    if detail: gun_pair(C, -0.2, 1.6, 0, zb + 0.7, 0.9)
    z = dome(B, fus, 42.5, 2.1, 2.6, OLIVE_D, up=-1)
    if detail: gun_pair(B, 39.0, 41.0, 0, z - 1.9, 0.6)
    zc = tail_housing(H, fus)
    if detail: gun_pair(H, TAILGUN[1], TAILGUN[1] + 1.6, 0, zc, 0.8)
    return dict(top=T, chin=C, ball=B, tail=H)


def decals(fus):
    """national insignia (E0 texture 3 / 4): upper left wing, lower right wing, both fuselage sides.
    Returns (corner points SH units, E0 id, uv list, outward hint), lifted off the skin."""
    out = []
    def wing_quad(y0, y1, side, top):
        sg = 1 if side > 0 else -1; pts = []
        for y, f in ((y0, 0.18), (y0, 0.62), (y1, 0.62), (y1, 0.18)):
            le, te = wing_le(y), wing_te(y); s = le + f * (te - le)
            pts.append(P(s, sg * y, wing_surface_z(s, y, top) + (0.3 if top else -0.3)))
        return pts
    out.append((wing_quad(41.5, 47.0, -1, True), 3, [(127, 0), (127, 127), (0, 127), (0, 0)], (0, 0, 1)))
    out.append((wing_quad(41.5, 47.0, 1, False), 4, [(0, 0), (0, 127), (127, 127), (127, 0)], (0, 0, -1)))
    for sg in (1, -1):
        pts = [P(s, sg * (fus.side_y(s, z, sg) + 0.3), z) for s, z in ((50.5, 1.4), (55.5, 1.1), (55.5, -1.7), (50.5, -2.0))]
        uv = [(0, 0), (127, 0), (127, 127), (0, 127)] if sg > 0 else [(127, 0), (0, 0), (0, 127), (127, 127)]
        out.append((pts, 3, uv, (sg, 0, 0)))
    return out
