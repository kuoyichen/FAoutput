"""FA.EXE patch: the rear view (view mode 1) of the KC-135 looks from the boom operator's window.
Never touches the input file.   usage: python fa_kc135_rearview.py FA.EXE OUT.EXE [x up fwd tilt]

How FA places the rear view (found 2026-11-25):
  camera switch 0x40D94E on word [cam] = view mode, table 0x40E1F4; mode 1 = rear view at 0x40D962
  eye = aircraft position + its rotation applied to the PT cockpit eye (typedef +0x9C x, +0x9E up + 5, +0xA0 fwd, ft)
        via 0x411D10(obj, x, up, fwd, out);  heading = +0x7FF8 (turned round), pitch/roll negated
  the forward views use the same PT eye, so the PT cannot move the rear view alone.
Patch: the first 10 bytes at 0x40D97A jump to a cave after .text. When the aircraft's PT is KC135.PT (third ot_names string,
case-insensitive), the eye is the boom operator's (x, up, fwd ft from the aircraft centre) and the view is
tilted down by `tilt` degrees (camera pitch < 0 looks down, as the top-down view 0x40DE56 uses -90).
Every other aircraft runs the original instructions. The CRC32 is forged back to the input's, as fa_gun_hitbox.py.
"""
import sys, struct, zlib
from keystone import Ks, KS_ARCH_X86, KS_MODE_32
src, dst = sys.argv[1], sys.argv[2]
X, UP, FWD, TILT = (float(v) for v in sys.argv[3:7]) if len(sys.argv) > 6 else (0, -10, -108, 25)
assert src.lower() != dst.lower()
d = bytearray(open(src, 'rb').read()); crc0 = zlib.crc32(d)
off = lambda va: va - 0x401000 + 0x400
pe = struct.unpack_from('<I', d, 0x3C)[0]; sec0 = pe + 24 + struct.unpack_from('<H', d, pe + 20)[0]
assert d[sec0:sec0 + 5] == b'.text'
TVS, TRS = struct.unpack_from('<I', d, sec0 + 8)[0], struct.unpack_from('<I', d, sec0 + 16)[0]
assert TVS == 0xE7B6C and TRS == 0xE7C00, (hex(TVS), hex(TRS))
CRCPOS = off(0x401000 + TVS + 0x10)               # the 4 bytes fa_gun_hitbox.py / crc_match.py use for the CRC
CAVE = 0x401000 + TVS + 0x14
HOOK, RESUME, DONE = 0x40D97A, 0x40D99E, 0x40E18B
ORIG = bytes.fromhex('8b4e050fbf81a0000000500fbf819e0000000fbf899c00000083c005505156e872430000')
assert d[off(HOOK):off(HOOK) + len(ORIG)] == ORIG, 'mode-1 code differs (already patched?)'
assert d[off(CAVE) - 4:off(0x401000 + TRS)].strip(b'\0') == b'' or True
assert d[off(CAVE):off(0x401000 + TRS)] == bytes(TRS - TVS - 0x14), 'cave not empty'
# relocations inside the replaced bytes would break the patch
rva_reloc = None
n = struct.unpack_from('<H', d, pe + 6)[0]
for i in range(n):
    nm, vs, va, rs, ro = struct.unpack_from('<8sIIII', d, sec0 + 40 * i)
    if nm.startswith(b'.reloc'):
        p, end = ro, ro + vs
        while p < end:
            page, size = struct.unpack_from('<II', d, p)
            if size < 8: break
            for k in range((size - 8) // 2):
                e = struct.unpack_from('<H', d, p + 8 + 2 * k)[0]
                if e >> 12 and HOOK - 3 <= 0x400000 + page + (e & 0xFFF) < HOOK + 10: raise SystemExit('reloc in hook range')
            p += size
tilt = int(round(TILT * 65536 / 360))
asm = f"""
    mov ecx, dword ptr [esi + 5]
    mov edx, dword ptr [ecx + 5]
    test edx, edx
    jz orig
    mov ah, 2
skip:
    mov al, byte ptr [edx]
    inc edx
    test al, al
    jnz skip
    dec ah
    jnz skip
    mov eax, dword ptr [edx]
    or eax, 0x20202020
    cmp eax, 0x3331636b
    jne orig
    mov eax, dword ptr [edx + 4]
    or eax, 0x20202020
    cmp eax, 0x74702e35
    jne orig
    cmp byte ptr [edx + 8], 0
    jne orig
    push {int(FWD)}
    push {int(UP)}
    push {int(X)}
    push esi
    call {0x411D10}
    mov ax, word ptr [esp + 0x18]
    add ax, 0x7ff8
    mov word ptr [ebp + 0x2c], ax
    mov ax, word ptr [esp + 0x1a]
    neg ax
    sub ax, {tilt}
    mov word ptr [ebp + 0x2e], ax
    mov ax, word ptr [esp + 0x1c]
    neg ax
    mov word ptr [ebp + 0x30], ax
    jmp {DONE}
orig:
    movsx eax, word ptr [ecx + 0xa0]
    jmp {HOOK + 10}
"""
code = bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(asm, CAVE)[0])
assert len(code) <= TRS - TVS - 0x14, len(code)
d[off(CAVE):off(CAVE) + len(code)] = code
jmp = b'\xE9' + struct.pack('<i', CAVE - (HOOK + 5))
d[off(HOOK):off(HOOK) + 10] = jmp + b'\x90' * 5     # mov ecx,[esi+5]; movsx eax,[ecx+0xa0] -> jmp cave (rest of the original runs as before)
struct.pack_into('<I', d, sec0 + 8, TRS)            # .text virtual size covers the cave
# forge CRC back to the original
pos = CRCPOS
d[pos:pos + 4] = b'\0\0\0\0'
base = zlib.crc32(d); cols = []
for i in range(32):
    e = bytearray(d); e[pos + i // 8] ^= 1 << (i % 8); cols.append(zlib.crc32(e) ^ base)
basis = {}
for i in range(32):
    v, m = cols[i], 1 << i
    for b in range(31, -1, -1):
        if not (v >> b) & 1: continue
        if b in basis: v ^= basis[b][0]; m ^= basis[b][1]
        else: basis[b] = (v, m); break
v, m = base ^ crc0, 0
for b in range(31, -1, -1):
    if (v >> b) & 1: v ^= basis[b][0]; m ^= basis[b][1]
assert v == 0
for i in range(32):
    if (m >> i) & 1: d[pos + i // 8] ^= 1 << (i % 8)
assert zlib.crc32(d) == crc0
open(dst, 'wb').write(d)
print(f'{dst}: KC135.PT rear view at ({X:g}, {UP:g}, {FWD:g}) ft, tilt {TILT:g} deg, cave {len(code)} bytes at {CAVE:#x}, crc {crc0:#010x} kept')
