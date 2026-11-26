"""Vertex warp of selected absolute-coordinate 82 buffers + renormal (tools/shgen/sh_renormal).
apply(src, dst, fn, offs): fn((x, fwd, up)) -> (x, fwd, up); offs = CODE offsets of the 82s to warp."""
import os, struct, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools', 'shgen'))
import sh_renormal
from sh_inspect import load

def apply(src, dst, fn, offs):
    d, pe, secs, code, c = load(src)
    d = bytearray(d); ro = code['ro']; moved = 0
    for o in offs:
        assert c[o] == 0x82 and c[o + 1] == 0, hex(o)
        n = struct.unpack_from('<H', c, o + 2)[0]
        for i in range(n):
            p = o + 6 + 6 * i; v = struct.unpack_from('<3h', c, p)
            w = tuple(int(round(a)) for a in fn(v))
            if w != v: moved += 1
            struct.pack_into('<3h', d, ro + p, *w)
    tmp = dst + '.raw'; open(tmp, 'wb').write(d)
    sh_renormal.main(src, tmp, dst); os.remove(tmp)
    print(f'{dst}: {moved} vertices moved')


def remap(path_in, path_out, warp, starts, var_sets=None):
    """After apply(): move the BSP plane points (06 / 0C / 0E / 10) and the C4 part positions of path_out with the
    same warp((x, fwd, up)), so the draw order still splits where the geometry now is (f35.remap_nodes, generic)."""
    import nodes as NODES
    vs = var_sets or [{}, {'_PLafterBurner': 1, '_PLgearDown': 0, '_PLleftFlap': 30, '_PLrightFlap': 30, '_PLbrake': 1}]
    N, C4 = NODES.collect_all(path_in, starts, vs)
    d, pe, secs, code, c = load(path_out); d = bytearray(d); ro = code['ro']
    h = lambda p: struct.unpack_from('<h', c, p)[0]
    cl = lambda v: max(-32768, min(32767, int(round(v))))
    for p, op in N.items():
        if op == 6:
            x, f, u = warp((-h(p + 4), -h(p + 12), -h(p + 8)))
            for off, val in ((4, -x), (8, -u), (12, -f)): struct.pack_into('<h', d, ro + p + off, cl(val))
        elif op == 0x0C:
            x, f, u = warp((0, -h(p + 8), -h(p + 4)))
            struct.pack_into('<h', d, ro + p + 4, cl(-u)); struct.pack_into('<h', d, ro + p + 8, cl(-f))
        elif op == 0x0E:
            x, f, u = warp((-h(p + 4), -h(p + 8), 0))
            struct.pack_into('<h', d, ro + p + 4, cl(-x)); struct.pack_into('<h', d, ro + p + 8, cl(-f))
        elif op == 0x10:
            x, f, u = warp((-h(p + 4), 0, -h(p + 8)))
            struct.pack_into('<h', d, ro + p + 4, cl(-x)); struct.pack_into('<h', d, ro + p + 8, cl(-u))
    for p in C4:
        X, U, F = struct.unpack_from('<3h', c, p + 2)
        x, f, u = warp((X, F, U))
        struct.pack_into('<3h', d, ro + p + 2, cl(x), cl(u), cl(f))
    if c[0x0E:0x10] == b'\xf2\x00':                  # F2 bbox (resting height = ground - ymin, gun box): same warp
        t = 0x12 + struct.unpack_from('<H', c, 0x10)[0]
        r = struct.unpack_from('<i', c, t)[0]; b = struct.unpack_from('<6h', c, t + 4)
        nb = (warp((b[0], 0, 0))[0], warp((b[1], 0, 0))[0], warp((0, 0, b[2]))[2], warp((0, 0, b[3]))[2],
              warp((0, b[4], 0))[1], warp((0, b[5], 0))[1])
        k = max(abs(nb[i]) / max(1, abs(b[i])) for i in range(6))
        struct.pack_into('<i6h', d, ro + t, int(r * k) if k > 1 else r, *(cl(v) for v in nb))
        print(f'F2 bbox {b} -> {tuple(cl(v) for v in nb)}')
    open(path_out, 'wb').write(d)
    print(f'{path_out}: {len(N)} planes, {len(C4)} C4 positions remapped')
