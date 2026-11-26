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
