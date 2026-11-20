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


def load(name, length=None, white=150, roll=0, balance=False):
    """roll (degrees) turns the store about its axis, e.g. 45 so + fins become X fins clear of the pylon.
    balance: make the body as deep as it is wide at every station before turning.  FA's bodies are a 4-point
    diamond (PAVE 6 wide x 8 deep); turned 45 deg an unequal diamond becomes a tilted, lopsided rhombus.
    With equal corners it turns into an even square whose corners line up with the X fins."""
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
    finq = lambda q: (all(V0[i][0] == 0 for i in q) or all(V0[i][2] == 0 for i in q)) and \
        max(abs(V0[i][0]) + abs(V0[i][2]) for i in q) >= 3        # fin / canard: in the x = 0 or up = 0 plane
    finv = {i for f in FF if finq(f[3]) for i in f[3]}
    bodyv = {i for f in FF if not finq(f[3]) for i in f[3]}
    if balance:
        V0 = list(V0)
        for i in bodyv - finv:              # PAVE has (-3,-1,1) next to the corner (-3,-1,0): snap such points
            x, f, u = V0[i]                 # onto the corner, or turned they stick out of the square (a crack)
            if x and u:
                near = [V0[j] for j in bodyv if V0[j][1] == f and (V0[j][0] == 0) != (V0[j][2] == 0)
                        and abs(V0[j][0] - x) + abs(V0[j][2] - u) <= 1 and max(abs(V0[j][0]), abs(V0[j][2])) >= 3]
                if near: V0[i] = near[0]
        W0 = list(V0)                       # station extents from the unscaled points
        for i in bodyv - finv:
            x, f, u = V0[i]
            xr = max([abs(W0[j][0]) for j in bodyv if W0[j][1] == f and W0[j][2] == 0] or [0])
            ur = max([abs(W0[j][2]) for j in bodyv if W0[j][1] == f and W0[j][0] == 0] or [0])
            if xr and ur: R = max(xr, ur); V0[i] = (x * R / xr, f, u * R / ur)
    V = [(round((x * ca - u * sa) * s), round(f * s), round((x * sa + u * ca) * s)) for x, f, u in V0]
    # attach at the top of the body, not of the fins: fin faces lie in the x = 0 or up = 0 plane, body faces do not
    body = [f[3] for f in FF if any(V0[i][0] for i in f[3]) and any(V0[i][2] for i in f[3])]
    top = max(V[i][2] for q in body for i in q if abs(V[i][0]) <= 1)   # body top on the centreline (X fins are off it)
    if balance: top = max(V[i][2] for i in bodyv - finv)          # the square's flat top hangs on the pylon
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
        F.append(((FLAT if fl & 0x40 else TWO_SIDED), col, q, finq(idx)))
    global LAST_GROUPS; LAST_GROUPS = None
    cen = [sum(v[k] for v in V) / len(V) for k in range(3)]
    if balance:
        # FA's fin faces come as one-sided FLAT pairs; orient() by the centre turns both the same way, so each fin
        # showed from one side only (in game only 2 of the 4 X fins were seen from off-axis).  Give every fin
        # face both sides, and group the fins by quadrant for xfin_code's draw order.
        G = orient(V, [f[:3] for f in F if f[0] == FLAT and not f[3]], cen)
        seen = set()                                             # FA's own exact duplicate faces draw nothing new
        G = [g for g in G if not ((g[1], tuple(g[2])) in seen or seen.add((g[1], tuple(g[2]))))]
        nb = len(G); seen = set(); quad = {}
        for fl, col, q, fin in F:
            if fl != FLAT or fin:
                k = frozenset(q)
                if k in seen: continue
                seen.add(k)
                cx = sum(V[i][0] for i in q) / len(q); cu = sum(V[i][2] for i in q) / len(q) + top   # axis at up -top
                quad.setdefault((cx > 0, cu > 0), []).extend([len(G), len(G) + 1])
                G += [(FLAT, col, q), (FLAT, col, q[::-1])]
    else:
        G = orient(V, [f[:3] for f in F if f[0] == FLAT], cen)
        for fl, col, q, fin in F:
            if fl != FLAT: G += [(FLAT, col, q), (FLAT, col, q[::-1])]   # thin fins: one face per side
    used = sorted({i for _, _, q in G for i in q}); m = {v: k for k, v in enumerate(used)}
    if balance: LAST_GROUPS = {'body': list(range(nb)), **quad}
    return [V[i] for i in used], [(fl, col, [m[i] for i in q]) for fl, col, q in G]


def xfin_code(V, F, groups, top, faces_bytes):
    """Faces of an X-finned store with its own draw order (after the 82 buffer, up to and incl. the final 00 00).
    Eye in part coords; node `06`: n.(eye + d) >= 0 -> A then B, else B then A.  Two nodes on each 45 deg plane
    through the axis (axis at x 0, up -top): far fin, then the rest, then the near fin."""
    import struct as S
    sub = lambda key: faces_bytes(V, [F[i] for i in groups.get(key, [])]) + b'\0\0'
    body = sub('body')
    def wrap(n, far, inner, near):            # n = plane normal (x, up); far is drawn first when n.eye >= 0
        # N_a: A = far, B = N_b;  N_b: A = inner, B = near
        nb = S.pack('<BB6h', 0x06, 0, n[0], 0, n[1], top, 0, 0)
        # layout: [Na 18][00 00][Nb 18][00 00][far][inner][near]
        la = 18 + 2; lb = 18 + 2
        o_far = la + lb; o_in = o_far + len(far); o_near = o_in + len(inner)
        Na = nb + S.pack('<hh', o_far - 16, la - 18) + b'\0\0'
        Nb = nb + S.pack('<hh', o_in - (la + 16), o_near - (la + 18)) + b'\0\0'
        return Na + Nb + far + inner + near
    c = 11585
    core = wrap((c, -c), sub((False, True)), body, sub((True, False)))     # fins (-,+) / (+,-)
    return wrap((c, c), sub((False, False)), core, sub((True, True)))      # fins (-,-) / (+,+)


if __name__ == '__main__':
    for nm, L in (('SIDEM.SH', 29), ('AMRAM.SH', 37), ('HARM.SH', 42), ('PAVE.SH', 42), ('MK82.SH', 21)):
        V, F = load(nm, L)
        from collections import Counter
        print(nm, len(V), 'verts', len(F), 'faces', Counter(c for _, c, _ in F).most_common(8))
