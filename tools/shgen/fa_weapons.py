#!/usr/bin/env python3
"""Load FA's own weapon shapes (SH/SIDEM.SH, AMRAM.SH, HARM.SH, PAVE.SH, MK82.SH) as store parts:
all faces of the main LOD (every branch of the BSP), with their palette colours, scaled to a real-size length
in the aircraft's vertex units.  Returns (V (x, fwd, up), faces [(flags, colour, idx)]) like f18g_growler.lathe."""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, main_lod
from f18g_growler import orient, FLAT

SHDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'SH')
TWO_SIDED = 0x241           # flat colour, no back-face culling flag (0x40) -> drawn from both sides


def faces_of(c, start):
    """Walk the bytecode from the main LOD buffer through every branch; returns [(offset, flags, colour, idx)]."""
    h = lambda p: struct.unpack_from('<h', c, p)[0]
    seen, out = set(), []

    def exe(p, depth=0):
        if depth > 40: return
        for _ in range(5000):
            if p in seen and depth: return
            op = c[p]
            if op == 0x00 and c[p+1] == 0 or op == 0x1E: return
            if op == 0x82 and c[p+1] == 0:
                n = struct.unpack_from('<H', c, p+2)[0]; p += 6 + 6*n
            elif op == 0xFC:
                fl, col = struct.unpack_from('<HH', c, p+1); q = p+5
                if fl & 0x60: q += 6 + (3 if fl & 0x200 else 6)
                k = c[q]; q += 1
                idx = [struct.unpack_from('<H', c, q+2*i)[0] for i in range(k)] if fl & 0x400 else list(c[q:q+k])
                q += 2*k if fl & 0x400 else k
                if fl & 4: q += k * (2 if fl & 0x100 else 4)
                if p not in seen: seen.add(p); out.append((p, fl, col, idx))
                p = q
            elif op == 0xF6: p += 7
            elif op == 0x06 and c[p+1] == 0: exe(p+16+h(p+14), depth+1); exe(p+18+h(p+16), depth+1); p += 18
            elif op in (0x0C, 0x0E, 0x10) and c[p+1] == 0: exe(p+12+h(p+10), depth+1); exe(p+14+h(p+12), depth+1); p += 14
            elif op == 0x6C and c[p+1] == 0: exe(p+8+h(p+6), depth+1); exe(p+10+h(p+8), depth+1); p += 10
            elif op == 0x12 and c[p+1] == 0: exe(p+4+h(p+2), depth+1); p += 4
            elif op == 0x38: p = p+3+h(p+1)
            elif op == 0x48 and c[p+1] == 0: p = p+4+h(p+2)
            elif op == 0xE2 and c[p+1] == 0: p += 16
            else: return
    exe(start)
    return out


TOPS = {}
LAST_TOP = None


def load(name, length=None, white=150, roll=0):
    """roll (degrees) turns the store about its axis, e.g. 45 so + fins become X fins clear of the pylon."""
    d = open(os.path.join(SHDIR, name), 'rb').read()
    pe, opt, secs = pe_sections(d); code = next(s for s in secs if s['name'] == 'CODE')
    c = d[code['ro']:code['ro']+code['vs']]
    o, n, t, e = main_lod(c)[0]
    V0 = [struct.unpack_from('<hhh', c, o+6+6*i) for i in range(n)]
    # missiles carry their smoke trail: textured colour-0 faces behind the motor.  Drop them (and their vertices).
    FF = [(p, fl, col, [i for i in idx if i < n]) for p, fl, col, idx in faces_of(c, o)]
    FF = [f for f in FF if not (f[1] & 4 and not f[2] & 0xFF)]
    used0 = {i for f in FF for i in f[3]}
    f0, f1 = min(V0[i][1] for i in used0), max(V0[i][1] for i in used0)
    s = length / (f1 - f0) if length else 1        # length None: FA's own size, so it matches the launched weapon
    import math
    ca, sa = math.cos(math.radians(roll)), math.sin(math.radians(roll))
    V = [(round((x * ca - u * sa) * s), round(f * s), round((x * sa + u * ca) * s)) for x, f, u in V0]
    # attach at the top of the body, not of the fins: fin faces lie in the x = 0 or up = 0 plane, body faces do not
    body = [f[3] for f in FF if any(V0[i][0] for i in f[3]) and any(V0[i][2] for i in f[3])]
    top = max(V[i][2] for q in body for i in q if abs(V[i][0]) <= 1)   # body top on the centreline (X fins are off it)
    global LAST_TOP; LAST_TOP = top
    TOPS[(name, length, roll)] = top                              # body top above the model origin (weapon centre)
    V = [(x, f, u - top) for x, f, u in V]                       # top of the store at local up 0 (pylon attach)
    F = []
    for p, fl, col, idx in FF:
        q = []
        for i in idx:                                            # drop vertices merged by the rounding
            if not q or V[q[-1]] != V[i]: q.append(i)
        while len(q) > 1 and V[q[0]] == V[q[-1]]: q.pop()
        if len(set(V[i] for i in q)) < 3: continue
        col = col & 0xFF or white                                # textured / colour-0 faces -> plain white
        F.append(((FLAT if fl & 0x40 else TWO_SIDED), col, q))
    cen = [sum(v[k] for v in V) / len(V) for k in range(3)]
    G = orient(V, [f for f in F if f[0] == FLAT], cen)
    for fl, col, q in F:
        if fl != FLAT: G += [(FLAT, col, q), (FLAT, col, q[::-1])]   # thin fins: one face per side
    used = sorted({i for _, _, q in G for i in q}); m = {v: k for k, v in enumerate(used)}
    return [V[i] for i in used], [(fl, col, [m[i] for i in q]) for fl, col, q in G]


if __name__ == '__main__':
    for nm, L in (('SIDEM.SH', 29), ('AMRAM.SH', 37), ('HARM.SH', 42), ('PAVE.SH', 42), ('MK82.SH', 21)):
        V, F = load(nm, L)
        from collections import Counter
        print(nm, len(V), 'verts', len(F), 'faces', Counter(c for _, c, _ in F).most_common(8))
