"""Draw-order compiler for FA (painter's algorithm, no z-buffer).
Faces that can obscure each other form an "obscures" graph; acyclic parts are emitted in
topological order, and only cycles are cut with 06 plane nodes (BSP).
Elements: faces (int vertex coords) and objects (axis boxes drawn by callbacks).
Node 06: value = n.(eye - p) >= 0 (eye in front) -> A (back side) then B (front side)."""
import numpy as np
EPS = 0.35


class Face:
    def __init__(s, ids, P, col, nrm=None):
        s.ids = list(ids); s.P = np.array(P, float); s.col = col
        n = np.zeros(3)
        for k in range(len(P)):
            p, q = s.P[k], s.P[(k+1) % len(P)]
            n += np.cross(p, q)
        # FA faces: sum PxP points inward -> outward normal = -n
        n = -n; L = np.linalg.norm(n)
        if L < 1e-9 and nrm is not None: n = np.array(nrm, float); L = np.linalg.norm(n)
        s.n = n / L; s.d = float(np.dot(s.n, s.P.mean(0)))

    def side(s, n, d):
        v = s.P @ n - d
        f, b = (v > EPS).any(), (v < -EPS).any()
        return 'S' if f and b else 'F' if f else 'B' if b else 'C'


class Obj:
    def __init__(s, name, lo, hi, emit):
        s.name = name; s.lo = np.array(lo, float); s.hi = np.array(hi, float); s.emit = emit
        s.P = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])], float)

    def side(s, n, d):
        v = s.P @ n - d
        f, b = (v > EPS).any(), (v < -EPS).any()
        return 'S' if f and b else 'F' if f else 'B' if b else 'C'



class Builder:
    def __init__(s, V, add_vertex):
        s.V = V; s.add_vertex = add_vertex; s.splits = 0

    def split(s, f, n, d):
        """split face f by plane; returns (front, back) Faces"""
        ids, P = f.ids, f.P; v = P @ n - d
        fr, bk = [], []
        for k in range(len(ids)):
            i, j = k, (k+1) % len(ids)
            if v[i] >= -EPS: fr.append(ids[i])
            if v[i] <= EPS: bk.append(ids[i])
            if (v[i] > EPS and v[j] < -EPS) or (v[i] < -EPS and v[j] > EPS):
                t = v[i] / (v[i] - v[j]); p = P[i] + t*(P[j] - P[i])
                ni = s.add_vertex(p, ids[i], ids[j], t); fr.append(ni); bk.append(ni)
        s.splits += 1
        def mk(l):
            if len(set(map(tuple, (s.V[i] for i in l)))) < 3: return None
            g = Face(l, [s.V[i] for i in l], f.col, f.n); g.smooth = getattr(f, 'smooth', True)
            if np.dot(g.n, f.n) < 0.5: g.n = f.n; g.d = float(np.dot(f.n, g.P.mean(0)))
            return g
        return mk(fr), mk(bk)


def occl_graph(els):
    """edges[i] = set of j such that i may obscure j (i must be drawn after j)."""
    n = len(els); E = [set() for _ in range(n)]
    for i, a in enumerate(els):
        for j, b in enumerate(els):
            if i == j: continue
            if isinstance(b, Face):
                va = a.P @ b.n - b.d            # a in front of b's plane?
                if not (va > EPS).any(): continue
                if isinstance(a, Face):
                    vb = b.P @ a.n - a.d
                    if not (vb < -EPS).any(): continue
                E[i].add(j)
            else:   # b is an object: a obscures b if b has corner behind a's plane (a face) / always (a obj)
                if isinstance(a, Face):
                    if (b.P @ a.n - a.d < -EPS).any(): E[i].add(j)
                else: E[i].add(j)
    return E


def sccs(E):
    n = len(E); idx = [None]*n; low = [0]*n; on = [False]*n; st = []; out = []; c = [0]
    import sys; sys.setrecursionlimit(100000)
    def strong(v):
        idx[v] = low[v] = c[0]; c[0] += 1; st.append(v); on[v] = True
        for w in E[v]:
            if idx[w] is None: strong(w); low[v] = min(low[v], low[w])
            elif on[w]: low[v] = min(low[v], idx[w])
        if low[v] == idx[v]:
            comp = []
            while True:
                w = st.pop(); on[w] = False; comp.append(w)
                if w == v: break
            out.append(comp)
    for v in range(n):
        if idx[v] is None: strong(v)
    return out      # reverse topological order of the condensation (sinks first)


class Order(Builder):
    def build(s, faces, objs, depth=0):
        faces = [f for f in faces if f is not None]
        els = faces + objs
        if not els: return ('leaf', [], [])
        E = occl_graph(els)
        comps = sccs(E)
        big = [c for c in comps if len(c) > 1]
        if not big or depth > 40:
            # i -> j means i may obscure j, so j is drawn first. Tarjan pops a component only after
            # every component it reaches, so its output order is already the draw order.
            order = [els[v] for c in comps for v in c]
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
        if best is None: return ('list', [els[v] for c in comps for v in c])
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


def count(t):
    if t[0] == 'list': return 0, sum(isinstance(e, Face) for e in t[1])
    if t[0] == 'leaf': return 0, 0
    a = count(t[3]); b = count(t[4])
    return 1 + a[0] + b[0], a[1] + b[1] + len(t[5]) + len(t[6])
