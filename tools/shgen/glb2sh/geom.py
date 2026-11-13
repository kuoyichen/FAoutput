"""New F-14 main-body geometry from the GLB (SH units: x right, y fwd, z up)."""
import numpy as np
from loft import Sections

STA = [120, 112, 103, 93, 82, 70, 58, 46, 34, 22, 8, -6, -20, -34, -46, -54]   # loft stations (y)
TIP = (0, 125, -5)
GREY, GLASS, DARK = 0x98, 0x9B, 0x9D


def hull2(P):
    P = sorted(map(tuple, P))
    def cross(o, a, b): return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lo, hi = [], []
    for p in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0: hi.pop()
        hi.append(p)
    return np.array(lo[:-1] + hi[:-1])


def simplify_poly(H, n):
    """drop the hull point whose removal loses the least area until n remain"""
    H = list(map(np.array, H))
    while len(H) > n:
        best, bi = 1e18, 0
        for i in range(len(H)):
            a, b, c = H[i-1], H[i], H[(i+1) % len(H)]
            ar = abs((b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0]))
            if ar < best: best, bi = ar, i
        H.pop(bi)
    return np.array(H)


class Mesh:
    """V: float points; F: (vertex ids, colour, smooth, normal hint)"""
    def __init__(s): s.V = []; s.F = []
    def add(s, p): s.V.append(tuple(float(x) for x in p)); return len(s.V) - 1


def plate(M, P3, n_out, col, verts=5):
    """thin plate: best-fit plane through P3, 2D hull simplified to `verts`, one face per side"""
    c = P3.mean(0); _, _, Vt = np.linalg.svd(P3 - c); e1, e2, nrm = Vt
    if np.dot(nrm, n_out) < 0: nrm = -nrm
    H = simplify_poly(hull2(np.c_[(P3 - c) @ e1, (P3 - c) @ e2]), verts)
    ids = [M.add(c + h[0]*e1 + h[1]*e2) for h in H]
    M.F.append((ids, col, False, tuple(nrm))); M.F.append((ids[::-1], col, False, tuple(-nrm)))


def build(glb, sec: Sections):
    M = Mesh()
    # 1. fuselage loft: 16 rings of 18 points (half ring: 4+2+3 segments), nose tip, dark end cap
    rings = []
    for y in STA:
        h = sec.half_ring(y, 4, 2, 3)
        full = [(x, y, z) for x, z in h] + [(-x, y, z) for x, z in h[-2:0:-1]]
        rings.append([M.add(p) for p in full])
    K = len(rings[0]); tip = M.add(TIP)
    can = glb.points((255, None)); cy0, cy1 = can[:, 1].min(), can[:, 1].max()
    for a, b in zip(rings, rings[1:]):
        for k in range(K):
            ids = [a[k], a[(k+1) % K], b[(k+1) % K], b[k]]
            cyl = np.mean([M.V[i][1] for i in ids])
            col = GLASS if (cy0 + 2 < cyl < cy1 and (k < 2 or k >= K - 2)) else GREY
            M.F.append((ids, col, True, None))
    for k in range(K): M.F.append(([tip, rings[0][(k+1) % K], rings[0][k]], GREY, True, None))
    M.F.append((rings[-1][::-1], DARK, False, (0, -1, 0)))
    # 2. nozzles: 8-sided, from inside the nacelle (y=-50) to the exhaust (y=-62)
    noz = glb.points((161, 192))
    cx, cz = (noz[:, 0].min() + noz[:, 0].max()) / 2, (noz[:, 2].min() + noz[:, 2].max()) / 2
    r = (noz[:, 0].max() - noz[:, 0].min()) / 2
    for sx in (1, -1):
        r0 = [M.add((sx*cx + r*np.cos(a), -50, cz + r*np.sin(a))) for a in np.arange(8)*np.pi/4]
        r1 = [M.add((sx*cx + 0.85*r*np.cos(a), -62, cz + 0.85*r*np.sin(a))) for a in np.arange(8)*np.pi/4]
        for k in range(8): M.F.append(([r0[k], r0[(k+1) % 8], r1[(k+1) % 8], r1[k]], GREY, True, None))
        M.F.append((r1[::-1], DARK, False, (0, -1, 0)))
    # 3. fins (+rudders), ventral fins, horizontal stabs as plates
    for sx, tk, rk in ((1, (161, 208), (271, None)), (-1, (209, 213), (272, None))):
        P = np.vstack([glb.points(tk), glb.points(rk)])
        plate(M, P[P[:, 2] > 0], (sx, 0, 0), GREY, 5)
        plate(M, P[P[:, 2] < -12], (sx, 0, 0), GREY, 4)
    for key in ((160, None), (273, None)):
        plate(M, glb.points(key), (0, 0, 1), GREY, 6)
    return M
