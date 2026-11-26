#!/usr/bin/env python3
"""F-35B lift-fan door animation: the door unit's C4 (placed in the BSP by fs_core) becomes an F0 jump to a new
block that sets the C4 pitch from _PLgearPos (door open ~60 deg with the gear down, shut with the gear up) and
draws the door.  run(src, dst, sign=+1)"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools', 'shgen')); sys.path.insert(0, HERE)
from sh_subdivide import pe_sections, insert_blocks
from sh_inspect import load, thunks
from fs_core import find_thunk, SIG
import keystone

DOOR = [(-6, 0, 0), (6, 0, 0), (6, 17, 0), (-6, 17, 0)]

def run(src, dst, sign=1, open_deg=60):
    d, pe, secs, code, c = load(src); d = bytearray(d); c = bytearray(c)
    th = thunks(d, secs, code, c); gp = next(k for k, v in th.items() if v == '_PLgearPos')
    tail = c.find(SIG); thunk = find_thunk(c, tail)
    hits = []
    for i in range(tail):
        if c[i] == 0xC4 and c[i + 1] == 0:
            t = i + 16 + struct.unpack_from('<h', c, i + 14)[0]
            if 0 < t < len(c) - 30 and c[t] == 0x82 and struct.unpack_from('<H', c, t + 2)[0] == 4 and \
               [struct.unpack_from('<3h', c, t + 6 + 6 * k) for k in range(4)] == DOOR: hits.append((i, t))
    assert len(hits) == 1, hits
    at, part = hits[0]
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    va = code['va']
    def asm(Lpos, C4new, L):
        s = f"""
            pushfd
            pushad
            call next
        next:
            pop ebx
            movzx eax, word ptr [{va + gp + L}]
            mov edx, 32767
            sub edx, eax
            jns ok
            xor edx, edx
        ok:
            imul edx, edx, {round(open_deg / 360 * 65536 / 32767 * 1024)}
            sar edx, 10
            {'neg edx' if sign < 0 else ''}
            mov word ptr [ebx + {C4new + 10 - Lpos}], dx
            popad
            popfd
        """
        return bytes(ks.asm(s, 0)[0])
    C4new = tail + 60; L = 0x10000
    for _ in range(5):
        body = asm(tail + 9, C4new, L)
        C4new = tail + 2 + len(body) + 11
        L = len(body) + 2 + 11 + 16 + 2; L += (-L) % 4
    body = asm(tail + 9, C4new, L); assert tail + 2 + len(body) + 11 == C4new
    blk = bytearray(b'\xf0\x00' + body + b'\x68' + struct.pack('<I', va + C4new) + b'\x68' + struct.pack('<I', va + thunk + L) + b'\xc3')
    c4 = bytearray(c[at:at + 16]); struct.pack_into('<h', c4, 14, part - (C4new + 16))
    blk += c4 + b'\x00\x00'
    while len(blk) < L: blk += b'\x00'
    gpos = 2 + body.find(struct.pack('<I', va + gp + L))
    relocs = [gpos, 2 + len(body) + 1, 2 + len(body) + 6]
    c[at:at + 13] = b'\xf0\x00\x68' + struct.pack('<I', va + tail) + b'\x68' + struct.pack('<I', va + thunk + L) + b'\xc3'
    relocs += [at + 3 - tail, at + 8 - tail]
    pe_, opt, secs_ = pe_sections(d)
    nxt = min(s['va'] for s in secs_ if s['va'] > code['va'])
    assert nxt - code['va'] - len(c) >= L, 'no room'
    out = insert_blocks(d, pe_, secs_, next(s for s in secs_ if s['name'] == 'CODE'), c, tail, bytes(blk), extra_relocs=relocs)
    assert len(out) < 65536
    open(dst, 'wb').write(out); print(f'{dst}: door C4 {at:#x} -> block {tail:#x} ({L} B), file {len(out)}')
