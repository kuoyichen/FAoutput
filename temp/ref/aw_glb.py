"""Airwolf GLB (Kuoyi's SketchUp export) -> SH units and part groups.
SH units: x right, y forward, z up, 1 unit = 1 ft (shift 8). Scale: rotor diameter 13.4 m -> 114 units (same as Ka-52 HOKUT).
GLB axes: X aft, Y up, Z lateral (right = +Z, rotor hub at X 9.0, Z -12.8)."""
import numpy as np
from glbload import GLB as _GLB

K = 114 / 13.4


def tosh(W):
    W = np.asarray(W, float)
    return np.c_[(W[:, 2] + 12.8) * K, -(W[:, 0] - 9.0) * K, (W[:, 1] - 12.63) * K - 8]


# groups (node ids found by inspecting Airwolf.glb; see fa-airwolf memory)
BODY = [187, 192, 205, 98, 3, 197, 198, 199, 202, 216, 217, 232, 213, 17]
BODY_SKIP = [210, 20, 18]          # tail skid, boom stripe, belly light
SPONSON_R, SPONSON_L = 21, 110
GEAR = 233
ROTOR = 219
TAIL = 249          # 250 = fin + stab, 252 = tail rotor (right side)


class AW(_GLB):
    def desc(s, n):
        out = [n]
        for c in s.J['nodes'][n].get('children', []): out += s.desc(c)
        return out

    def grp(s, groups, skip=()):
        keep = set(); drop = set()
        for g in groups: keep |= set(s.desc(g))
        for g in skip: drop |= set(s.desc(g))
        T = []; M = []
        for W, t, m, i in s.tris:
            if i in keep and i not in drop:
                T.append(tosh(W)[t]); M += [m] * len(t)
        return np.vstack(T), np.array(M)

    def points(s, groups):
        return np.vstack([t.reshape(-1, 3) for t in [s.grp(groups)[0]]])

    def mat_lum(s, m):
        mt = s.J['materials'][m] if m is not None else {}
        c = mt.get('pbrMetallicRoughness', {}).get('baseColorFactor', [0.5, 0.5, 0.5, 1])
        return c
