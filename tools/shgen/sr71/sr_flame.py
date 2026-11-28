"""F-14 style animated afterburner flame for new shapes (from tools/shgen/shuttle/shuttle.py, SHUT-17..23, in game OK):
two crossed textured sheets (both sides), each face a 3-frame op 40 switch over the ab_flame_tex frames in the PIC,
and an F0 x86 prologue that grows the flame from 15% to 100% of its length over GROW_MS after the AB lights.
Sizes here are SH units.  write_pic() writes a 256x256 PIC holding only the 3 flame frames."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, os.path.join(HERE, '..'))
import keystone
from ab_flame_tex import frame as flame_frame

KS = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
FLAME_SLOTS = [(94, 131), (137, 131), (180, 131)]        # (u0, v0) of the 3 frames, 41 x 61 px each
GROW_MS = 3000
PIC_W = PIC_H = 256


def flame_cross(r, l):
    """r = sheet half width, l = full length (SH units); nozzle at y 0, flame towards -y."""
    return [(0, 0, r), (0, 0, -r), (0, -l, -r), (0, -l, r), (r, 0, 0), (-r, 0, 0), (-r, -l, 0), (r, -l, 0)]


def flame_faces(core, PV, base):
    V = {base + i: v for i, v in enumerate(PV)}
    r = PV[0][2]
    def uv(k, i):
        fu, fv = FLAME_SLOTS[k]; x, y, z = PV[i]
        lat = z if i < 4 else x
        return (int(round(fu + 40 * (lat + r) / (2 * r))), int(round(fv + (60 if y == 0 else 0))))
    quads = [([0, 1, 2, 3], (1, 0, 0)), ([3, 2, 1, 0], (-1, 0, 0)), ([4, 5, 6, 7], (0, 0, -1)), ([7, 6, 5, 4], (0, 0, 1))]
    blk = bytearray()
    for ids, n in quads:
        fb = []
        for k in range(3):
            b = bytearray(core.tex_face([base + i for i in ids], V, n, [uv(k, i) for i in ids]))
            struct.pack_into('<H', b, 1, struct.unpack_from('<H', b, 1)[0] | 0x10)
            fb.append(bytes(b))
        at = len(blk)
        L = [len(fb[0]) + 4, len(fb[1]) + 4, len(fb[2])]
        start = [at + 10, at + 10 + L[0], at + 10 + L[0] + L[1]]
        nxt = at + 10 + sum(L)
        blk += b'\x40\x00\x03\x00' + b''.join(struct.pack('<h', start[k] - (at + 4 + 2 * k)) for k in range(3))
        for k in range(3):
            blk += fb[k]
            if k < 2:
                j = len(blk); blk += b'\x48\x00' + struct.pack('<h', nxt - (j + 4))
        assert len(blk) == nxt
    return bytes(blk)


def emit_flame(core, a, r, l, base):
    """F0 grow x86, then the 82 buffer and the animated faces; the per-object timing table follows the ret."""
    PV = flame_cross(r, l); LEN = l
    faces = flame_faces(core, PV, base)
    P0 = a.here(); L_buf = a.new()
    tails = [6 + 6 * i + 2 for i in (2, 3, 6, 7)]                 # y of the tail vertices, from the buffer start
    nb = 0
    for _ in range(6):
        nxt_at = P0 + 2 + 7
        buf_at = P0 + 2 + nb + 11
        tbl_at = buf_at + 6 + 6 * len(PV) + len(faces) + 2
        tbl_at += (-tbl_at) % 4
        st = "\n".join(f"mov word ptr [ebx + {buf_at + t - nxt_at}], ax" for t in tails)
        src = f"""
            pushfd
            pushad
            call nxt
        nxt:
            pop ebx
            movzx ecx, word ptr [0x580bec]
            mov edi, ecx
            and edi, 3
            shl edi, 4
            lea edi, [ebx + edi + {tbl_at - nxt_at}]
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
            cmp eax, {GROW_MS}
            jbe ok
            mov eax, {GROW_MS}
        ok:
            imul eax, eax, 850
            add eax, {150 * GROW_MS}
            imul eax, eax, {LEN}
            xor edx, edx
            mov ecx, {1000 * GROW_MS}
            div ecx
            neg eax
            {st}
            popad
            popfd
        """
        body = bytes(KS.asm(src, 0)[0])
        if len(body) == nb: break
        nb = len(body)
    else: raise SystemExit('flame x86 size did not settle')
    assert body[2] == 0xE8
    a.emit(b'\xF0\x00' + body); a.f0_resume(L_buf, 'RESUME')
    a.label(L_buf); assert a.here() == buf_at
    a.emit(struct.pack('<BBHH', 0x82, 0, len(PV), base * 8))
    for v in PV: a.emit(struct.pack('<hhh', *v))
    a.emit(faces); a.ret()
    while a.here() % 4: a.emit(b'\x00')
    assert a.here() == tbl_at
    a.emit(bytes(4 * 16))      # 4 objects tracked


def write_pic(path, png=None, bg=158):
    """256x256 PIC (layout of _F86.PIC) holding the 3 flame frames; bg = body colour."""
    from PIL import Image
    im = Image.new('P', (PIC_W, PIC_H), bg)
    for k, (u0, v0) in enumerate(FLAME_SLOTS):
        Fr = flame_frame(k)
        for r, row in enumerate(Fr):
            for c_, col in enumerate(row):
                im.putpixel((u0 + c_, v0 + r), col)
    ref = open(os.path.join(REPO, 'PIC', '_F86.PIC'), 'rb').read()
    w, h = PIC_W, PIC_H; px = im.tobytes()
    po = 0x40; ps = w * h; rt = po + ps; pal = rt + 4 * h
    hdr_ = bytearray(ref[:0x40])
    struct.pack_into('<HIIIIII', hdr_, 0, 0, w, h, po, ps, pal, 768)
    struct.pack_into('<II', hdr_, 0x22, rt, 4 * h)
    body = b''.join(px[(h - 1 - r) * w:(h - r) * w] for r in range(h))           # rows bottom-up
    table = b''.join(struct.pack('<I', po + r * w) for r in range(h))
    palb = ref[struct.unpack_from('<I', ref, 18)[0]:][:768]
    open(path, 'wb').write(bytes(hdr_) + body + table + palb)
    if png:
        b = open(os.path.join(REPO, 'PIC', 'PALETTE.PAL'), 'rb').read()[:768]
        if max(b) < 64: b = bytes(min(255, x * 4) for x in b)
        im.putpalette(list(b)); im.convert('RGB').save(png)
