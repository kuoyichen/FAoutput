#!/usr/bin/env python3
"""Animated, growing afterburner for SHs whose stock flame is a C4 PART (F-22 ATF.SH: flat 2D-nozzle plumes,
12 points at fwd 0 / mid / tail, 8 textured two-sided faces, C4 pitch = thrust vectoring).
Same look as sh_ab_flame (3 frames from ab_flame_tex, op 40 switch per face, 0xFF transparent) and the same
grow-in x86 (15 % -> 100 % in GROW ms, per object, timeGetTime); every non-nozzle point is scaled (mid ring too).
run(src, psrc, dst, pdst, old=82 offset of the flame part, length=new tail distance, grow=ms)"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools', 'shgen')); sys.path.insert(0, HERE)
from sh_subdivide import pe_sections, insert_blocks
from ab_flame_tex import frame
from sh_ab_flame import read_pic, put, SIG
from up_ab import free_slots
from fs_core import find_thunk


def run(src, psrc, dst, pdst, old, length, grow=3000, ignore=(), slots=None):
    """slots: flame frames already drawn by an earlier call (second engine of a twin): reuse them, PIC unchanged."""
    ignore = [tuple(r) for r in ignore]             # PIC areas of faces that a later step removes (old gear billboards)
    pb = bytearray(open(psrc, 'rb').read()); P = read_pic(pb)
    drawn = slots is not None
    if not drawn:
        slots = free_slots(src, psrc, ignore=ignore)
        if len(slots) < 3: slots = free_slots(src, psrc, need_ff=False, ignore=ignore)
    assert len(slots) == 3, slots
    for k, (fu, fv, rot) in enumerate([] if drawn else slots):
        F = frame(k)
        for r in range(61):
            for a in range(41):
                if rot: put(pb, P, fu + r, fv + a, F[r][a])
                else: put(pb, P, fu + a, fv + r, F[r][a])
    uvf = lambda sl, t, s: ((slots[sl][0] + 60 * t, slots[sl][1] + 40 * s) if slots[sl][2] else (slots[sl][0] + 40 * s, slots[sl][1] + 60 * t))
    d = bytearray(open(src, 'rb').read())
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    if nxt - code['va'] - code['vs'] < 2000:
        from f18g_growler import grow_vas
        d = bytearray(grow_vas(d, 0x1000)); pe, opt, secs = pe_sections(d)
        code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    c = bytearray(d[code['ro']:code['ro'] + code['vs']])
    n, t = struct.unpack_from('<HH', c, old + 2); assert c[old] == 0x82
    V = [list(struct.unpack_from('<3h', c, old + 6 + 6 * i)) for i in range(n)]
    NOZ = max(v[1] for v in V); TL = min(v[1] for v in V); k = length / (NOZ - TL)
    for v in V: v[1] = round(NOZ - (NOZ - v[1]) * k)
    TAIL = NOZ - length
    vb = struct.pack('<BBHH', 0x82, 0, n, t) + b''.join(struct.pack('<3h', *v) for v in V)
    faces = []; p = old + 6 + 6 * n
    while True:
        if c[p] == 0x6C: p += 10; continue                  # F-104 style: view test (6C) + jump (38) between faces
        if c[p] == 0x38: p += 3; continue
        if c[p] == 0x1E and c[p + 1] in (0xFC, 0x6C): p += 1; continue
        if c[p] != 0xFC: break
        fl = struct.unpack_from('<H', c, p + 1)[0]; nv = c[p + 14]
        assert fl & 0x200 and fl & 0x60 and nv >= 3, hex(fl)
        hdr = bytearray(c[p:p + 14]); struct.pack_into('<H', hdr, 1, (fl & ~0x100) | 0x404)  # u8 UVs / byte indices -> u16
        if not fl & 4: hdr[3] = 0                     # flat-colour plume (F-5): textured now, colour 0 = 0xFF see-through
        wi = 2 if fl & 0x400 else 1
        idx = list(struct.unpack_from('<%d%s' % (nv, 'H' if wi == 2 else 'B'), c, p + 15))
        P3 = [V[i - t // 8] for i in idx]
        struct.pack_into('<3b', hdr, 11, sum(q[0] for q in P3) // nv, sum(q[2] for q in P3) // nv, (NOZ + TAIL) // 2)
        faces.append((hdr, idx)); p += 15 + wi * nv + ((2 if fl & 0x100 else 4) * nv if fl & 4 else 0)
    assert c[p] == 0x1E and len(faces) >= 2, (hex(p), len(faces))

    def fbytes(hdr, idx, sl):
        P3 = [V[i - t // 8] for i in idx]; ax = 2 if len({q[0] for q in P3}) == 1 else 0
        lo, hi = min(q[ax] for q in P3), max(q[ax] for q in P3)
        out = bytearray(hdr) + bytes([len(idx)]) + struct.pack('<%dH' % len(idx), *idx)
        for q in P3:
            out += struct.pack('<HH', *(round(z) for z in uvf(sl, (q[1] - TAIL) / (NOZ - TAIL), (q[ax] - lo) / (hi - lo))))
        return out
    tail = bytes(c).find(SIG)
    blk = bytearray(vb)
    for hdr, idx in faces:
        at = tail + len(blk); fb = [fbytes(hdr, idx, s) for s in range(3)]
        L = [len(fb[0]) + 4, len(fb[1]) + 4, len(fb[2])]
        st = [at + 10, at + 10 + L[0], at + 10 + L[0] + L[1]]; nn = at + 10 + sum(L)
        blk += b'\x40\x00\x03\x00' + b''.join(struct.pack('<h', st[s] - (at + 4 + 2 * s)) for s in range(3))
        for s in range(3):
            blk += fb[s]
            if s < 2: j = tail + len(blk); blk += b'\x48\x00' + struct.pack('<h', nn - (j + 4))
        assert tail + len(blk) == nn
    blk += b'\x1e'
    while len(blk) % 4: blk += b'\x00'
    TBL = tail + len(blk); blk += bytes(32 * 16)
    movers = [(tail + 6 + 6 * i + 2, v[1]) for i, v in enumerate(V) if v[1] != NOZ]
    G = grow

    def asm(Lpos):
        st = "\n".join(f"mov edx, eax\nimul edx, edx, {f}\nsar edx, 10\nmov word ptr [ebx + {a - Lpos}], dx" for a, f in movers)
        return f"""
            pushfd
            pushad
            call next
        next:
            pop ebx
            movzx ecx, word ptr [0x580bec]
            mov edi, ecx
            and edi, 31
            shl edi, 4
            lea edi, [ebx + edi + {TBL - Lpos}]
            call dword ptr [0x593758]
            cmp word ptr [edi], cx
            jne restart
            mov edx, eax
            sub edx, dword ptr [edi + 8]
            cmp edx, 1000
            jbe keep
        restart:
            mov word ptr [edi], cx
            mov dword ptr [edi + 4], eax
        keep:
            mov dword ptr [edi + 8], eax
            sub eax, dword ptr [edi + 4]
            cmp eax, {G}
            jbe ok
            mov eax, {G}
        ok:
            imul eax, eax, {870}
            xor edx, edx
            mov ecx, {G}
            div ecx
            add eax, 154
            {st}
            popad
            popfd
        """
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    Lpos = old + 2 + 2 + 5
    body = bytes(ks.asm(asm(Lpos), 0)[0]); assert body[2] == 0xE8
    thunk = find_thunk(c, tail)
    room = nxt - code['va'] - len(c)
    if len(blk) > room: sys.exit(f'no room {len(blk)} > {room}')
    L = len(blk); pp = old + 2 + len(body)
    tr = b'\xf0\x00' + body + b'\x68' + struct.pack('<I', code['va'] + tail) + b'\x68' + struct.pack('<I', code['va'] + thunk + L) + b'\xc3'
    assert old + len(tr) <= p, (len(tr), p - old)
    c[old:old + len(tr)] = tr
    out = insert_blocks(d, pe, secs, code, c, tail, bytes(blk), extra_relocs=(pp + 1 - tail, pp + 6 - tail))
    assert len(out) < 65536
    open(dst, 'wb').write(out); open(pdst, 'wb').write(pb)
    print(f'{dst}: flame part {len(blk)} B at CODE+{tail:#x}, length {length}, slots {slots}, file {len(out)}')
    return slots
