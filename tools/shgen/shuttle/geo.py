"""Geometry primitives for new shapes (mesh coords: x right, y fwd, z up; SH units).
Every face gets an outward normal hint, so the winding is fixed by core.mesh_faces."""
import numpy as np
from mesh import Mesh


def lerp(a, b, t): return a + (b - a) * t


def interp(stations, y, key):
    ys = [s['y'] for s in stations]; vs = [s[key] for s in stations]
    if ys[0] > ys[-1]: ys, vs = ys[::-1], vs[::-1]
    return float(np.interp(y, ys, vs))


def ring_pts(y, w, zt, zb, zc=None, K=16, n=2.4, nb=None):
    """superellipse ring (x, y, z), starting at the top and going towards +x; upper half exponent n,
    lower half nb (default n)."""
    zc = (zt + zb) / 2 if zc is None else zc
    nb = n if nb is None else nb
    out = []
    for k in range(K):
        a = 2 * np.pi * k / K
        s, c = np.sin(a), np.cos(a)
        e = n if c >= 0 else nb
        x = w * np.sign(s) * abs(s) ** (2 / e)
        z = zc + (zt - zc if c >= 0 else zc - zb) * np.sign(c) * abs(c) ** (2 / e)
        out.append((x, y, z))
    return out


def loft(M, rings, col, smooth=True, nose=None, tail=None, axis=None):
    """rings: lists of 3D points (same K, going aft).  col: int or fn(centre, normal) -> int.
    nose / tail: closing points (fans) or None (open; 'cap' = flat cap)."""
    ids = [[M.add(p) for p in r] for r in rings]
    K = len(rings[0])
    def colour(P, n): return col(P.mean(0), n) if callable(col) else col
    def add(f, ax_c):
        P = np.array([M.V[i] for i in f]); c = P.mean(0)
        n = c - ax_c; n[1] = 0 if np.linalg.norm(n[[0, 2]]) > 1e-6 else n[1]
        L = np.linalg.norm(n)
        n = n / L if L > 1e-9 else np.array([0, 1.0, 0])
        M.F.append((f, colour(P, n), smooth, tuple(n)))
    for a, b in zip(ids, ids[1:]):
        ca = np.mean([M.V[i] for i in a], 0); cb = np.mean([M.V[i] for i in b], 0)
        for k in range(K):
            f = [a[k], a[(k + 1) % K], b[(k + 1) % K], b[k]]
            add(f, (ca + cb) / 2)
    for end, r, sgn in ((nose, ids[0], 1), (tail, ids[-1], -1)):
        if end is None: continue
        cr = np.mean([M.V[i] for i in r], 0)
        if isinstance(end, str):
            P = np.array([M.V[i] for i in r]); n = np.array([0, sgn, 0.0])
            M.F.append((list(r), col if not callable(col) else col(cr, n) if end == 'cap' else end, False, tuple(n)))
            continue
        tip = M.add(end)
        for k in range(K):
            f = [tip, r[(k + 1) % K], r[k]]
            P = np.array([M.V[i] for i in f]); c = P.mean(0)
            n = c - (cr + np.array(end)) / 2; n = n / (np.linalg.norm(n) or 1)
            n = 0.5 * n + 0.5 * np.array([0, sgn, 0.0]); n /= np.linalg.norm(n)
            M.F.append((f, colour(P, n), smooth, tuple(n)))
    return ids


def fuselage(M, st, K=16, col=150, nose=None, tail=None, smooth=True):
    """st: list of dict(y, w, zt, zb, [zc], [n], [nb]) from front to back."""
    rings = [ring_pts(s['y'], s['w'], s['zt'], s['zb'], s.get('zc'), K, s.get('n', 2.4), s.get('nb')) for s in st]
    return loft(M, rings, col, smooth, nose, tail)


AF = [(0.0, 0.0, 0.0), (0.06, 0.62, -0.42), (0.25, 1.0, -0.62), (0.55, 0.78, -0.45), (1.0, 0.06, -0.04)]   # (chord frac, upper, lower) * t


def airfoil(le, chord, t, h, af=AF):
    """closed ring in the (y, h) plane: LE, upper surface aft, TE, lower surface forward.  t = max thickness."""
    up = [(le - f * chord, h + u * t / 2 * 1.6) for f, u, l in af]
    lo = [(le - f * chord, h + l * t / 2 * 1.6) for f, u, l in af[1:-1]][::-1]
    return up + lo


def surface(M, secs, col, mirror=True, vertical=False, smooth=False, tipcap=True, rootcap=False):
    """lifting surface through sections dict(s, le, chord, h, t): s = span coord (x for a wing, z for a fin),
    le = y of the leading edge, h = the surface's offset (z for a wing, x for a fin), t = thickness (units).
    The section ring is lofted spanwise; mirrored to -x for wings (mirror=True)."""
    out = []
    for sx in ((1, -1) if mirror and not vertical else (1,)):
        rings = []
        for s in secs:
            r = airfoil(s['le'], s['chord'], max(s['t'], 1.2), s['h'])
            if vertical: rings.append([(s['h'] + (hh - s['h']), y, s['s']) for y, hh in r])
            else: rings.append([(sx * s['s'], y, hh) for y, hh in r])
        if vertical:   # ring points: (x = offset, y, z = span)
            rings = [[(hh, y, s['s']) for y, hh in airfoil(s['le'], s['chord'], max(s['t'], 1.2), s['h'])] for s in secs]
        ids = [[M.add(p) for p in r] for r in rings]
        K = len(ids[0])
        for a, b in zip(ids, ids[1:]):
            for k in range(K):
                f = [a[k], a[(k + 1) % K], b[(k + 1) % K], b[k]]
                P = np.array([M.V[i] for i in f]); c = P.mean(0)
                # outward: away from the section's chord line
                ra = np.array([M.V[i] for i in a]).mean(0); rb = np.array([M.V[i] for i in b]).mean(0); cl = (ra + rb) / 2
                n = c - cl
                if vertical: n[2] = 0
                else: n[0] = 0
                L = np.linalg.norm(n); n = n / L if L > 1e-9 else np.array([0, 0, 1.0])
                cc = col(c, n) if callable(col) else col
                M.F.append((f, cc, smooth, tuple(n)))
        for r, end in ((ids[-1], tipcap), (ids[0], rootcap)):
            if not end: continue
            P = np.array([M.V[i] for i in r]); c = P.mean(0)
            other = np.array([M.V[i] for i in (ids[-2] if r is ids[-1] else ids[1])]).mean(0)
            n = c - other; n /= np.linalg.norm(n)
            cc = col(c, n) if callable(col) else col
            M.F.append((list(r), cc, False, tuple(n)))
        out.append(ids)
    return out


def prism(M, pts2, axis, a0, a1, col, cap=None, smooth=False):
    """prism with polygon pts2 across `axis` (0 = x: (y, z), 1 = y: (x, z), 2 = z: (x, y)) from a0 to a1."""
    def P3(st, a):
        s_, t_ = st
        return {0: (a, s_, t_), 1: (s_, a, t_), 2: (s_, t_, a)}[axis]
    pts = [np.array(p, float) for p in pts2]; c = np.mean(pts, 0)
    r0 = [M.add(P3(p, a0)) for p in pts]; r1 = [M.add(P3(p, a1)) for p in pts]
    n = len(pts)
    for k in range(n):
        m = (pts[k] + pts[(k + 1) % n]) / 2 - c
        M.F.append(([r0[k], r0[(k + 1) % n], r1[(k + 1) % n], r1[k]], col, smooth, P3(m / (np.linalg.norm(m) or 1), 0.0)))
    ax = np.zeros(3); ax[axis] = 1 if a1 > a0 else -1
    M.F.append((r0, cap if cap is not None else col, False, tuple(-ax)))
    M.F.append((r1, cap if cap is not None else col, False, tuple(ax)))
    return r0, r1


def ngon(r, n, cx=0, cy=0, rot=0.0, ry=None):
    ry = r if ry is None else ry
    return [(cx + r * np.cos(rot + 2 * np.pi * k / n), cy + ry * np.sin(rot + 2 * np.pi * k / n)) for k in range(n)]


def strut(M, a, b, r, col, n=4):
    """n-gon bar from point a to b (any direction)."""
    a = np.array(a, float); b = np.array(b, float); ax = b - a; L = np.linalg.norm(ax); ax /= L
    u = np.array([0, 0, 1.0]) if abs(ax[2]) < 0.9 else np.array([1.0, 0, 0])
    u = u - ax * np.dot(u, ax); u /= np.linalg.norm(u); v = np.cross(ax, u)
    angs = np.pi / 4 + np.arange(n) * 2 * np.pi / n
    r0 = [M.add(a + r * (np.cos(t) * u + np.sin(t) * v)) for t in angs]
    r1 = [M.add(b + r * (np.cos(t) * u + np.sin(t) * v)) for t in angs]
    for k in range(n):
        t = np.pi / 4 + (k + 0.5) * 2 * np.pi / n
        nn = np.cos(t) * u + np.sin(t) * v
        M.F.append(([r0[k], r0[(k + 1) % n], r1[(k + 1) % n], r1[k]], col, False, tuple(nn)))
    M.F.append((r0, col, False, tuple(-ax))); M.F.append((r1, col, False, tuple(ax)))


def wheel(M, centre, r, w, tyre, hub, n=8):
    """tyre: n-gon prism across x, hub colour on the side caps"""
    cx, cy, cz = centre
    prism(M, ngon(r, n, cy, cz, np.pi / n), 0, cx - w / 2, cx + w / 2, tyre, cap=hub)


def plate(M, pts3, nrm, col_a, col_b=None):
    """two-sided flat plate"""
    ids = [M.add(p) for p in pts3]; n = np.array(nrm, float); n /= np.linalg.norm(n)
    M.F.append((ids, col_a, False, tuple(n))); M.F.append((ids[::-1], col_b if col_b is not None else col_a, False, tuple(-n)))
    return ids
