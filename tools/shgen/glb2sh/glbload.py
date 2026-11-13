"""Read the F-14 GLB (SketchUp glTF export), group its triangles by part, convert to SH units,
and voxelise the fuselage into a solid used for the cross-sections.
SH units: x right, y forward, z up, 1 unit = 1 ft (F14.SH scale)."""
import json, struct
import numpy as np
from scipy import ndimage

# part groups (top-level nodes under node 2 / sub-nodes) found by inspecting F-14Tomcat_SU_2020.glb
TOP = [0, 3, 22, 28, 55, 74, 75, 76, 77, 91, 92, 160, 161, 209, 255, 271, 272, 273, 274, 275, 290]
BODY_TOP = {92, 255, 74}               # fuselage + gloves + nacelles, canopy, radome
BODY_SUB = {(161, 165), (209, 214)}    # outer nozzles
SKIP_SUB = {(92, 159)}
# GLB -> SH: nose tip at y=125, overall length 192 (same as the current F-14), ground (GLB y=0.1) at z=-24
S = 192 / 23.87; CX = 19.95


def tosh(W):
    W = np.asarray(W, float)
    return np.c_[(W[:, 0] - CX) * S, 125 - (W[:, 2] + 30.11) * S, (W[:, 1] - 0.1) * S - 24]


class GLB:
    def __init__(s, path):
        d = open(path, 'rb').read(); o = 12; ch = []
        while o < len(d):
            cl, ct = struct.unpack_from('<II', d, o); ch.append(d[o+8:o+8+cl]); o += 8 + cl
        J = json.loads(ch[0]); B = ch[1]; s.J = J
        acc, bv = J['accessors'], J['bufferViews']
        CT = {5126: 'f4', 5125: 'u4', 5123: 'u2', 5121: 'u1'}; NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}
        def read(i):
            a = acc[i]; v = bv[a['bufferView']]; off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
            n = NC[a['type']]; dt = np.dtype(CT[a['componentType']]); st = v.get('byteStride', 0) or dt.itemsize * n
            return np.ndarray((a['count'], n), dt, B, off, (st, dt.itemsize))
        def q2m(q):
            x, y, z, w = q
            return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
        def local(n):
            if 'matrix' in n: return np.array(n['matrix']).reshape(4, 4).T
            T = np.eye(4); R = np.eye(4); Sc = np.eye(4)
            if 'translation' in n: T[:3, 3] = n['translation']
            if 'rotation' in n: R[:3, :3] = q2m(n['rotation'])
            if 'scale' in n: Sc[:3, :3] = np.diag(n['scale'])
            return T @ R @ Sc
        s.tris = []
        def walk(i, M):
            n = J['nodes'][i]; M = M @ local(n)
            if 'mesh' in n:
                for p in J['meshes'][n['mesh']]['primitives']:
                    P = read(p['attributes']['POSITION']).astype(float)
                    I = read(p['indices']).ravel() if 'indices' in p else np.arange(len(P))
                    used = np.unique(I)
                    W = (np.c_[P[used], np.ones(len(used))] @ M.T)[:, :3]
                    rem = np.full(len(P), -1); rem[used] = np.arange(len(used))
                    s.tris.append((W, rem[I].reshape(-1, 3), p.get('material'), i))
            for c in n.get('children', []): walk(c, M)
        walk(0, np.eye(4))
        s.par = {}
        for i, n in enumerate(J['nodes']):
            for c in n.get('children', []): s.par[c] = i

    def top(s, i):
        while i not in TOP and i in s.par: i = s.par[i]
        return i

    def sub(s, i):
        tp = s.top(i)
        if i == tp: return tp, tp
        while s.par.get(i) != tp: i = s.par[i]
        return tp, i

    def points(s, key):
        """SH-unit points of a group: key = (top, sub) or (top, None)"""
        P = [tosh(W) for W, t, m, i in s.tris if (s.sub(i) == key or (key[1] is None and s.top(i) == key[0]))]
        return np.vstack(P)

    def body_tris(s):
        T = []
        for W, t, m, i in s.tris:
            tp, k = s.sub(i)
            if (tp in BODY_TOP and (tp, k) not in SKIP_SUB) or (tp, k) in BODY_SUB: T.append(tosh(W)[t])
        return np.vstack(T)


def voxel_solid(T, vox=0.5, lo=(-36, -70, -20), hi=(36, 128, 16)):
    """triangle soup -> symmetric solid voxel grid. A voxel is inside when the shell blocks it in all 6 axis directions."""
    lo = np.array(lo, float); hi = np.array(hi, float)
    shape = np.ceil((hi - lo) / vox).astype(int) + 1
    G = np.zeros(shape, bool)
    for tri in T:
        e = max(np.linalg.norm(tri[1]-tri[0]), np.linalg.norm(tri[2]-tri[0]), np.linalg.norm(tri[2]-tri[1]))
        n = int(e / (vox * 0.5)) + 2
        a, b = np.meshgrid(np.linspace(0, 1, n), np.linspace(0, 1, n)); m = a + b <= 1
        P = tri[0] + a[m][:, None] * (tri[1] - tri[0]) + b[m][:, None] * (tri[2] - tri[0])
        I = np.round((P - lo) / vox).astype(int); G[I[:, 0], I[:, 1], I[:, 2]] = True
    ix0 = -lo[0] / vox; xs = np.arange(shape[0]); mx = np.round(2*ix0 - xs).astype(int); ok = (mx >= 0) & (mx < shape[0])
    Gm = np.zeros_like(G); Gm[xs[ok]] = G[mx[ok]]; G |= Gm
    G = ndimage.binary_dilation(G, iterations=1)
    cnt = np.zeros(G.shape, np.int8)
    for ax in range(3):
        cnt += np.maximum.accumulate(G, axis=ax).astype(np.int8)
        cnt += np.flip(np.maximum.accumulate(np.flip(G, ax), axis=ax), ax).astype(np.int8)
    solid = (cnt >= 6) | G
    solid = ndimage.binary_erosion(solid, iterations=1)
    solid = ndimage.binary_opening(solid, iterations=1)
    return solid, lo, vox
