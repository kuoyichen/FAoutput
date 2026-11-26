#!/usr/bin/env python3
"""Parse an SH main LOD into its draw-order tree (BSP) with the bounding box of what each subtree draws.

Node kinds: ('node', addr, op, n(x,up,fwd), d(x,up,fwd), A, B, ctx)  ctx '' / 'c4' (inside a C4 part) / 'f0' (after an F0 block)  -- 06 and the 2D 0C/0E/10 nodes as 3D planes
            ('seq', [items])  items: ('face', addr, pts)  ('part', addr, pts)  (C4 parts / F0 chains flattened)
Coordinates are (x, up, fwd) like the eye.  F0 blocks follow the first `push imm32` (gear / flaps down).
Usage: python3 sh_bsp.py F18.SH [depth]
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, main_lod


F0_VARS = None          # None: F0 blocks follow their first push (gear down); see parse()


def load(path):
    d = open(path, 'rb').read()
    pe, opt, secs = pe_sections(d); code = next(s for s in secs if s['name'] == 'CODE')
    return d[code['ro']:code['ro']+code['vs']]


def parse(c, start=None):
    h = lambda p: struct.unpack_from('<h', c, p)[0]
    o0, n0, _, e = main_lod(c)[0]
    vt = {}

    def load82(p):
        n, t = struct.unpack_from('<HH', c, p+2)
        for i in range(n):
            x, f, u = struct.unpack_from('<hhh', c, p+6+6*i); vt[t//8 + i] = (x, u, f)
        return p + 6 + 6*n
    load82(o0)

    def seq(p, tf, depth=0, ctx=''):
        items = []
        for _ in range(20000):
            if not 0 <= p < len(c) - 1: break
            op = c[p]
            if op == 0x00 and c[p+1] == 0 or op == 0x1E: break
            if op == 0x82 and c[p+1] == 0: p = load82(p)
            elif op == 0xFC:
                fl = struct.unpack_from('<H', c, p+1)[0]; q = p+5
                if fl & 0x60: q += 6 + (3 if fl & 0x200 else 6)
                k = c[q]; q += 1
                idx = [struct.unpack_from('<H', c, q+2*i)[0] for i in range(k)] if fl & 0x400 else list(c[q:q+k])
                q += 2*k if fl & 0x400 else k
                if fl & 4: q += k * (2 if fl & 0x100 else 4)
                pts = [tf(vt[i]) for i in idx if i in vt]
                if pts: items.append(('face', p, pts))
                p = q
            elif op == 0xF6: p += 7
            elif op in (0xD0, 0xE0) and c[p+1] == 0: p += 4
            elif op == 0xE2 and c[p+1] == 0: p += 16
            elif op == 0x06 and c[p+1] == 0:
                nn = (h(p+2), h(p+6), h(p+10)); dd = (h(p+4), h(p+8), h(p+12))
                items.append(('node', p, 6, nn, dd, seq(p+16+h(p+14), tf, depth+1, ctx), seq(p+18+h(p+16), tf, depth+1, ctx), ctx)); p += 18
            elif op in (0x0C, 0x0E, 0x10) and c[p+1] == 0:
                ax = {0x0C: (1, 2), 0x0E: (0, 2), 0x10: (0, 1)}[op]
                nn = [0, 0, 0]; dd = [0, 0, 0]
                nn[ax[0]], dd[ax[0]], nn[ax[1]], dd[ax[1]] = h(p+2), h(p+4), h(p+6), h(p+8)
                items.append(('node', p, op, tuple(nn), tuple(dd), seq(p+12+h(p+10), tf, depth+1, ctx), seq(p+14+h(p+12), tf, depth+1, ctx), ctx)); p += 14
            elif op == 0x6C and c[p+1] == 0:
                items.append(('node', p, 0x6C, None, struct.unpack_from('<Hh', c, p+2), seq(p+8+h(p+6), tf, depth+1, ctx), seq(p+10+h(p+8), tf, depth+1, ctx), ctx)); p += 10
            elif op == 0x12 and c[p+1] == 0: items.append(('call', p, seq(p+4+h(p+2), tf, depth+1, ctx))); p += 4
            elif op == 0x38: p = p+3+h(p+1)
            elif op == 0x48 and c[p+1] == 0: p = p+4+h(p+2)
            elif op == 0xC4 and c[p+1] == 0:
                pos = struct.unpack_from('<3h', c, p+2)
                ptf = (lambda pos, tf: lambda v: tf(tuple(pos[j] + v[j] for j in range(3))))(pos, tf)
                items.append(('call', p, seq(p+16+h(p+14), ptf, depth+1, 'c4'))); p += 16
            elif op == 0xF0 and c[p+1] == 0 and F0_VARS is not None and c[p+2:p+5] == b'\x66\x83\x3d' and c[p+10] in (0x74, 0x75):
                # `cmp word [var], imm8; jne/je; push target; push thunk; ret` (gear / brake / hook / flap switches):
                # take the branch for the variable values in F0_VARS ({CODE offset of the variable: value}, default 0)
                a = struct.unpack_from('<I', c, p+5)[0] - 0x1000; imm = struct.unpack_from('<b', c, p+9)[0]
                eq = F0_VARS.get(a, 0) == imm
                q = p+12 if eq == (c[p+10] == 0x75) else p+12+struct.unpack_from('<b', c, p+11)[0]
                r = next((struct.unpack_from('<I', c, k+1)[0] - 0x1000 for k in range(q, q+80)
                          if c[k] == 0x68 and c[k+5] == 0x68 and c[k+10] == 0xC3), None)
                if r is None or not 0 < r < len(c): break
                p = r; ctx = ctx or 'f0'
            elif op == 0xF0 and c[p+1] == 0:
                r = None
                for q in range(p+2, p+200):
                    if c[q] == 0x68:
                        v = struct.unpack_from('<I', c, q+1)[0] - 0x1000
                        if 0 < v < len(c): r = v; break
                if r is None: break
                p = r; ctx = ctx or 'f0'
            else:
                items.append(('stop', p, op)); break
        return items
    root = start if start is not None else e
    while c[root] == 0xF6: root += 7
    return root, seq(root, lambda v: v)


def bbox(items):
    pts = []
    def walk(it):
        for x in it:
            if x[0] == 'face': pts.extend(x[2])
            elif x[0] == 'node': walk(x[5]); walk(x[6])
            elif x[0] == 'call': walk(x[2])
    walk(items)
    if not pts: return None
    return tuple(min(p[j] for p in pts) for j in range(3)), tuple(max(p[j] for p in pts) for j in range(3))


def nfaces(items):
    k = 0
    for x in items:
        if x[0] == 'face': k += 1
        elif x[0] == 'node': k += nfaces(x[5]) + nfaces(x[6])
        elif x[0] == 'call': k += nfaces(x[2])
    return k


def dump(items, depth, ind=0):
    run = []
    def flush():
        if run: print(' ' * ind + f'faces x{len(run)} {hex(run[0])}..  bbox {bbox([("face", 0, p) for p in run_pts])}'); run.clear(); run_pts.clear()
    run_pts = []
    for x in items:
        if x[0] == 'face': run.append(x[1]); run_pts.append(x[2]); continue
        flush()
        if x[0] == 'node':
            print(' ' * ind + f'{hex(x[1])} op{x[2]:02x} n={x[3]} d={x[4]}  faces A {nfaces(x[5])} B {nfaces(x[6])}')
            if depth > 0:
                print(' ' * ind + ' A:', bbox(x[5])); dump(x[5], depth-1, ind+3)
                print(' ' * ind + ' B:', bbox(x[6])); dump(x[6], depth-1, ind+3)
        elif x[0] == 'call':
            print(' ' * ind + f'{hex(x[1])} call/part faces {nfaces(x[2])} bbox {bbox(x[2])}')
        else: print(' ' * ind + str(x))
    flush()


if __name__ == '__main__':
    c = load(sys.argv[1]); root, t = parse(c)
    print('root', hex(root)); dump(t, int(sys.argv[2]) if len(sys.argv) > 2 else 4)
