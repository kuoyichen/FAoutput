"""Collect the plane nodes (06 / 0C / 0E / 10) reachable from the top-level frame of an SH (not inside C4 parts),
following F0 blocks with the unicorn emulator of shview.  nodes(path, starts) -> {offset: opcode}; also C4 offsets."""
import struct
import shview as V

def collect(path, starts, vars=None):
    sh = V.SH(path, vars or {}); c = sh.c; h = lambda p: struct.unpack_from('<h', c, p)[0]
    seen = set(); nodes = {}; c4 = set()
    stack = list(starts)
    while stack:
        p = stack.pop()
        for _ in range(100000):
            if p in seen or not 0 <= p < len(c) - 1: break
            seen.add(p); op = c[p]
            if (op == 0 and c[p + 1] == 0) or op == 0x1E: break
            if op == 0x82 and c[p + 1] == 0: p += 6 + 6 * struct.unpack_from('<H', c, p + 2)[0]
            elif op == 0xFC:
                fl = struct.unpack_from('<H', c, p + 1)[0]; q = p + 5
                if fl & 0x60: q += 6 + (3 if fl & 0x200 else 6)
                k = c[q]; q += 1 + (2 * k if fl & 0x400 else k)
                if fl & 4: q += 2 * k if fl & 0x100 else 4 * k
                p = q
            elif op == 0xF6: p += 7
            elif op in (0xD0, 0xE0) and c[p + 1] == 0: p += 4
            elif op == 0xE2 and c[p + 1] == 0: p += 16
            elif op == 0x06 and c[p + 1] == 0:
                nodes[p] = 6; stack += [p + 16 + h(p + 14), p + 18 + h(p + 16)]; break
            elif op in (0x0C, 0x0E, 0x10) and c[p + 1] == 0:
                nodes[p] = op; stack += [p + 12 + h(p + 10), p + 14 + h(p + 12)]; break
            elif op == 0x6C and c[p + 1] == 0:
                stack += [p + 8 + h(p + 6), p + 10 + h(p + 8)]; break
            elif op == 0x12 and c[p + 1] == 0: stack.append(p + 4 + h(p + 2)); p += 4
            elif op == 0x40 and c[p + 1] == 0:
                n = struct.unpack_from('<H', c, p + 2)[0]
                stack += [p + 4 + 2 * i + h(p + 4 + 2 * i) for i in range(n)]; break
            elif op == 0x38: p = p + 3 + h(p + 1)
            elif op == 0x48 and c[p + 1] == 0: p = p + 4 + h(p + 2)
            elif op == 0xC4 and c[p + 1] == 0: c4.add(p); p += 16
            elif op == 0xF0 and c[p + 1] == 0:
                r = sh.run_f0(p)
                if r is None or not 0 < r < len(c): break
                p = r
            else: break
    return nodes, sorted(c4)

def collect_all(path, starts, var_sets):
    N = {}; C = set()
    for vs in var_sets:
        n, c = collect(path, starts, vs); N.update(n); C |= set(c)
    return N, sorted(C)
