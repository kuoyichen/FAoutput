#!/usr/bin/env python3
"""Generic loadout stores for any FA jet: f18_stores driven by the aircraft's own .PT (f18v_upgrade.configure),
with the part vertex base above the aircraft's own part slots.
Usage: up_stores.py in.SH in.PT out.SH"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools', 'shgen')); sys.path.insert(0, HERE)
import fs_core as S
sys.modules['f18_stores'] = S
import f18v_upgrade as U
from sh_inspect import load

def max_slot(c, tail):
    hi = 0; p = 0
    while True:
        p = c.find(b'\x82\x00', p)
        if p < 0 or p > tail: break
        n, slot = struct.unpack_from('<HH', c, p + 2)
        if 0 < n < 900 and slot % 8 == 0 and slot // 8 + n <= 900 and p + 6 + 6*n < tail:
            hi = max(hi, slot // 8 + n); p += 6 + 6*n
        else: p += 1
    return hi

def run(src, pt, dst, extra=None):
    d = open(src, 'rb').read()
    _, _, _, _, c = load(src)
    tail = c.find(S.SIG)
    import f18g_growler
    S.BASE = f18g_growler.BASE = max(480, max_slot(c, tail) + 4)
    print('store vertex base', S.BASE)
    U.configure(d, pt)
    if extra: extra(S)
    out, _ = S.make(d)
    assert len(out) < 65536, len(out)
    open(dst, 'wb').write(out); print(dst, len(out))

if __name__ == '__main__': run(*sys.argv[1:4])
