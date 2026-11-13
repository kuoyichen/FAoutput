"""Tiny SH bytecode assembler: labels, rel16/rel32 fixups, abs32 fixups (each gets a HIGHLOW reloc).
F0 blocks follow the pattern of the original F14.SH part control: x86 code that ends with
`push <bytecode VA>; push <do_start_interp thunk>; ret` to resume the bytecode."""
import struct


class Asm:
    def __init__(s, base_off, code_va=0x1000):
        s.b = bytearray(); s.base = base_off; s.va = code_va
        s.labels = {}; s.rel = []; s.abs = []; s.ext = {}   # ext: name -> CODE offset (outside this block)
        s.n = 0

    def new(s, p='L'):
        s.n += 1; return f'{p}{s.n}'

    def here(s): return s.base + len(s.b)
    def label(s, name): s.labels[name] = s.here()
    def emit(s, data): s.b += data

    def rel16(s, target, frm_end_extra=0):
        """rel16 measured from the end of this rel16 field (+frm_end_extra bytes)."""
        s.rel.append((len(s.b), target, 2 + frm_end_extra)); s.b += b'\0\0'

    def abs32(s, target, addend=0):
        """absolute VA of a label/CODE offset (needs a HIGHLOW reloc)"""
        s.abs.append((len(s.b), target, addend)); s.b += b'\0\0\0\0'

    def addr(s, t):
        if isinstance(t, int): return t
        if t in s.labels: return s.labels[t]
        return s.ext[t]

    def link(s):
        for pos, t, end in s.rel:
            if end == 'r32':
                struct.pack_into('<i', s.b, pos, s.addr(t) - (s.base + pos + 4)); continue
            v = s.addr(t) - (s.base + pos + end)
            assert -32768 <= v < 32768, (t, v)
            struct.pack_into('<h', s.b, pos, v)
        relocs = []
        for pos, t, add in s.abs:
            struct.pack_into('<I', s.b, pos, s.va + s.addr(t) + add)
            relocs.append(s.base + pos)
        return bytes(s.b), relocs

    # ---- ops ----
    def ret(s): s.emit(b'\x00\x00')
    def call(s, t): s.emit(b'\x12\x00'); s.rel16(t)
    def jmp(s, t): s.emit(b'\x38'); s.rel16(t)

    def node3(s, n, d, a, b):
        s.emit(struct.pack('<BB6h', 0x06, 0, n[0], d[0], n[1], d[1], n[2], d[2]))
        s.rel16(a); s.rel16(b)

    def c4(s, pos, rot, target):
        at = s.here()
        s.emit(struct.pack('<BB6h', 0xC4, 0, *pos, *rot)); s.rel16(target)
        return at

    # x86 helpers (F0 00 + code); vars are CODE offsets of import thunks
    def f0_resume(s, ret_label, resume_thunk):
        s.emit(b'\x68'); s.abs32(ret_label)            # push retVA
        s.emit(b'\x68'); s.abs32(resume_thunk)         # push do_start_interp thunk
        s.emit(b'\xC3')

    def cond(s, var, resume, then_fn):
        """if word [var] == 1: run then_fn bytecode. Falls through afterwards."""
        L_then, L_else, L_end = s.new(), s.new(), s.new()
        s.emit(b'\xF0\x00\x66\x83\x3D'); s.abs32(var); s.emit(b'\x01')
        s.emit(b'\x0F\x85'); s.rel32_to(L_else)        # jne L_else (near)
        s.f0_resume(L_then, resume)
        s.label(L_then); then_fn()
        s.emit(b'\xF0\x00'); s.label(L_else); s.f0_resume(L_end, resume)
        s.label(L_end)

    def rel32_to(s, t):
        s.rel.append((len(s.b), t, 'r32')); s.b += b'\0\0\0\0'

    def patch_c4(s, var, field, ops, resume, c4_fn):
        """F0: ax = [var] transformed by ops; store into C4 field (byte offset in C4) then run the C4."""
        L_c4 = s.new()
        s.emit(b'\xF0\x00\xE8\x00\x00\x00\x00'); pop_at = s.here()      # call $+5
        s.emit(b'\x5B\x81\xC3')                          # pop ebx; add ebx, imm32
        imm_pos = len(s.b); s.b += b'\0\0\0\0'
        s.emit(b'\x66\xA1'); s.abs32(var)                 # mov ax,[var]
        s.emit(ops)
        s.emit(b'\x66\x89\x43' + bytes([field]))          # mov [ebx+field],ax
        s.f0_resume(L_c4, resume)
        s.label(L_c4); c4_at = s.here(); c4_fn()
        struct.pack_into('<I', s.b, imm_pos, c4_at - pop_at)

