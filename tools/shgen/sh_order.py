#!/usr/bin/env python3
"""Pick where new store units go in a model's BSP draw-order tree by measuring, from many eye positions, how
often FA's painter order disagrees with real depth.

FA has no depth buffer: the SH tree decides, per eye position, what is drawn first.  A unit (a store, a pylon)
is inserted at some branch T of the tree behind a new 06 node, so it is drawn just before or just after
everything T draws, depending on which side of the new node's plane the eye is.  For each candidate (T, plane)
this module renders the model at low resolution from ~80 eye positions and counts the pixels where the painter
shows the wrong thing (unit hidden by something behind it, or something behind the unit drawn over it).
Units are placed one at a time; later units see the earlier ones as part of the model.

place(c, ROOT, units) -> plan {T: [(unit, n, d), ...]}, refs {T: (rel field, base)} like f18_stores.place_units.
units: {name: [(cull, [(x, up, fwd), ...]), ...]} in model coordinates, in the unit's own draw order.
"""
import math, struct
import numpy as np
import sh_bsp

W, H = 192, 144


def views():
    out = []
    for el in (-80, -55, -35, -18, -5, 8, 25, 50):
        n = 4 if abs(el) >= 80 else 12
        for k in range(n):
            az = 2 * math.pi * (k + (0.5 if el in (-55, -18, 25) else 0)) / n
            ce = math.cos(math.radians(el))
            out.append((math.sin(az) * ce, math.sin(math.radians(el)), math.cos(az) * ce))
    return out


class Cam:
    def __init__(self, dirn, dist, tgt):
        self.E = np.array([tgt[j] + dirn[j] * dist for j in range(3)], float)
        f = np.array(tgt, float) - self.E; f /= np.linalg.norm(f)
        up = np.array([0, 1.0, 0]) if abs(f[1]) < 0.95 else np.array([0, 0, 1.0])
        r = np.cross(up, f); r /= np.linalg.norm(r); u = np.cross(f, r)
        self.f, self.r, self.u = f, r, u
        self.foc = (W / 2) / 0.62

    def proj(self, P):
        v = np.asarray(P, float) - self.E
        z = v @ self.f
        return W / 2 + (v @ self.r) / z * self.foc, H / 2 - (v @ self.u) / z * self.foc, z


def raster(cam, pts):
    """Pixels (flat index) and depth of a polygon; None if behind the eye or empty."""
    sx, sy, z = cam.proj(pts)
    if (z < 1).any(): return None
    iz = 1 / z
    pix, dep = [], []
    for i in range(1, len(pts) - 1):
        ax, ay, bx, by, cx, cy = sx[0], sy[0], sx[i], sy[i], sx[i+1], sy[i+1]
        area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        if abs(area) < 1e-6: continue
        x0, x1 = max(int(min(ax, bx, cx)), 0), min(int(max(ax, bx, cx)) + 1, W - 1)
        y0, y1 = max(int(min(ay, by, cy)), 0), min(int(max(ay, by, cy)) + 1, H - 1)
        if x0 > x1 or y0 > y1: continue
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
        w0 = ((bx - X) * (cy - Y) - (by - Y) * (cx - X)) / area
        w1 = ((cx - X) * (ay - Y) - (cy - Y) * (ax - X)) / area
        w2 = 1 - w0 - w1
        m = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not m.any(): continue
        zz = 1 / (w0[m] * iz[0] + w1[m] * iz[i] + w2[m] * iz[i+1])
        pix.append((Y[m].astype(int)) * W + X[m].astype(int)); dep.append(zz)
    if not pix: return None
    return np.concatenate(pix), np.concatenate(dep)


def outward(pts):
    """Outward normal in (x, up, fwd): in file order (x, fwd, up) the sum of Pk x Pk+1 points inside."""
    P = [(p[0], p[2], p[1]) for p in pts]
    n = [0.0, 0.0, 0.0]
    for i in range(len(P)):
        a, b = P[i], P[(i+1) % len(P)]
        n[0] += a[1]*b[2] - a[2]*b[1]; n[1] += a[2]*b[0] - a[0]*b[2]; n[2] += a[0]*b[1] - a[1]*b[0]
    return np.array([-n[0], -n[2], -n[1]])


class Model:
    def __init__(self, c, ROOT, units):
        self.c = c = bytes(c)
        _, self.tree = sh_bsp.parse(bytes(c), ROOT)
        self.ROOT = ROOT
        self.units = units
        self.faces = {}                     # id -> (cull, pts, normal)
        self.refs = {}                      # branch target -> (rel field, base)
        self.ins = {}                       # branch target -> [(unit, n, d)]
        seen, dup = set(), set()
        h = lambda p: struct.unpack_from('<h', c, p)[0]

        def walk(items, root_level):
            for x in items:
                if x[0] == 'face':
                    fl = struct.unpack_from('<H', c, x[1] + 1)[0]
                    self.faces[id(x)] = (bool(fl & 0x40), np.array(x[2], float), outward(x[2]))
                elif x[0] == 'call': walk(x[2], False)
                elif x[0] == 'node':
                    p, op = x[1], x[2]
                    for side, br in (('A', x[5]), ('B', x[6])):
                        if op == 0x6C: fa, base = (p+6, p+8) if side == 'A' else (p+8, p+10)
                        elif op == 6: fa, base = (p+14, p+16) if side == 'A' else (p+16, p+18)
                        else: fa, base = (p+10, p+12) if side == 'A' else (p+12, p+14)
                        T = base + h(fa)
                        if T in seen: dup.add(T)
                        seen.add(T)
                        if x[7] == '': self.refs[T] = (None, None) if root_level else (fa, base)
                        walk(br, False)
        walk(self.tree, True)
        for T in dup: self.refs.pop(T, None)
        self.refs['ROOT'] = (None, None)
        for u, fl in units.items():
            for i, (cull, pts) in enumerate(fl):
                self.faces[(u, i)] = (cull, np.array(pts, float), outward(pts))

    def order(self, eye):
        """Face ids in draw order, and {T: (start, end)} index ranges of each branch's content."""
        out, rng = [], {}

        def plane(n, d):
            return sum(n[j] * (eye[j] + d[j]) for j in range(3)) >= 0

        def content(T, items, k):
            if k == 0: seq(items); return
            u, n, d = self.ins[T][k-1]
            if plane(n, d): content(T, items, k-1); out.extend((u, i) for i in range(len(self.units[u])))
            else: out.extend((u, i) for i in range(len(self.units[u]))); content(T, items, k-1)

        def branch(T, items):
            s = len(out); content(T, items, len(self.ins.get(T, ()))); rng[T] = (s, len(out))

        def seq(items):
            for x in items:
                if x[0] == 'face': out.append(id(x))
                elif x[0] == 'call': seq(x[2])
                elif x[0] == 'node':
                    p, op = x[1], x[2]
                    h = lambda q: struct.unpack_from('<h', self.c, q)[0]
                    if op == 0x6C:
                        first = eye[(x[4][0] - 6) // 2] >= x[4][1]
                        TA, TB = p + 8 + h(p+6), p + 10 + h(p+8)
                    else:
                        first = plane(x[3], x[4])
                        TA, TB = (p + 16 + h(p+14), p + 18 + h(p+16)) if op == 6 else (p + 12 + h(p+10), p + 14 + h(p+12))
                    if first: branch(TA, x[5]); branch(TB, x[6])
                    else: branch(TB, x[6]); branch(TA, x[5])
        branch('ROOT', self.tree)
        return out, rng


def visible(face, E):
    cull, P, n = face
    return (not cull) or float(n @ (E - P[0])) > 0


def place(c, ROOT, units, boxes, order_units=None, dist=260, tgt=(0, -4, 20), log=print, pre=None):
    """pre: {T: [(unit, n, d), ...]} units already placed (by another placer); their faces must be in units, and
    only order_units are placed here, against the model with those already in it."""
    M = Model(c, ROOT, units)
    if pre: M.ins = {T: list(v) for T, v in pre.items()}
    cams = [Cam(v, dist, tgt) for v in views()]
    # per camera: raster of every face (cached), visibility
    R = []
    for cam in cams:
        rr = {}
        for fid, f in M.faces.items():
            if not visible(f, cam.E): continue
            r = raster(cam, f[1])
            if r is not None: rr[fid] = r
        R.append(rr)
    plan, refs = {}, {}
    names = order_units or list(units)
    for u in names:
        b = boxes[u]
        cands = []
        for T in M.refs:
            for j in range(3):
                for sgn in (1, -1):
                    cc = b[0][j] if sgn > 0 else b[1][j]
                    n = [0, 0, 0]; d = [0, 0, 0]; n[j] = 16384 * sgn; d[j] = -cc
                    cands.append((T, tuple(n), tuple(d)))
        err = np.zeros(len(cands))
        for cam, rr in zip(cams, R):
            eye = cam.E
            seq, rng = M.order(eye)
            idx = {fid: i for i, fid in enumerate(seq)}
            Bz = np.full(W * H, np.inf); L = np.full(W * H, -1)
            for fid, (pix, z) in rr.items():
                if fid in idx and not (isinstance(fid, tuple) and fid[0] == u):
                    np.minimum.at(Bz, pix, z); np.maximum.at(L, pix, idx[fid])
            Uz = np.full(W * H, np.inf)
            for i in range(len(units[u])):
                r = rr.get((u, i))
                if r is not None: np.minimum.at(Uz, r[0], r[1])
            m = np.isfinite(Uz) & (L >= 0)
            if not m.any(): continue
            front = np.sort(L[m & (Uz < Bz)]); back = np.sort(L[m & (Uz >= Bz)])
            for ci, (T, n, d) in enumerate(cands):
                if T not in rng: continue
                s, e = rng[T]
                k = e if sum(n[j] * (eye[j] + d[j]) for j in range(3)) >= 0 else s
                # unit drawn after faces with index < k
                err[ci] += (len(front) - np.searchsorted(front, k)) + np.searchsorted(back, k)
        bi = int(np.argmin(err)); T, n, d = cands[bi]
        M.ins.setdefault(T, []).append((u, n, d))
        plan.setdefault(T, []).append((u, n, d)); refs[T] = M.refs[T]
        j = next(j for j in range(3) if n[j])
        log(f'  {u:5s} -> {T if T == "ROOT" else hex(T)}  plane {"x up fwd".split()[j]} {"+" if n[j] > 0 else "-"} at {-d[j]}'
            f'  wrong pixels {int(err[bi])} (root-after {int(min(e for (TT, nn, dd), e in zip(cands, err) if TT == "ROOT"))})')
    return plan, refs, M, cams, R


def render(M, cam, rr, path, painter=True):
    """Debug image: painter order (as FA draws) or depth buffer."""
    from PIL import Image
    seq, _ = M.order(cam.E)
    img = np.full(W * H, 40, np.uint8); Z = np.full(W * H, np.inf)
    for fid in seq:
        r = rr.get(fid)
        if r is None: continue
        f = M.faces[fid]
        n = f[2] / (np.linalg.norm(f[2]) + 1e-9)
        shade = int(90 + 140 * abs(n @ np.array([.3, .8, .5]) / 1.0))
        if isinstance(fid, tuple): shade = 255 if shade > 160 else 200
        if painter: img[r[0]] = shade
        else:
            m = r[1] < Z[r[0]]; Z[r[0][m]] = r[1][m]; img[r[0][m]] = shade
    Image.fromarray(img.reshape(H, W)).resize((W * 3, H * 3), Image.NEAREST).save(path)
