#!/usr/bin/env python3
"""Loadout stores for F18.SH: weapons and tanks that follow what the aircraft actually carries.

FA.EXE draws no stores itself, and none of the SH variables (_PLgearDown ...) tell the shape what is loaded.
But F0 blocks are native x86, so each store slot here runs a small routine that reads the aircraft being
drawn straight from FA's memory (all addresses checked in FA.EXE, base 0x400000, not relocatable):
  * 0x4ab450 is called before every object is drawn: [0x51ce26] = object handle, word [0x580bec] = its index
    (handle 0 or bit 31 = not an object, e.g. a shape drawn on a menu screen).
  * object = [0x553848 + index*4]; byte +0 = class (4 = aircraft); (byte +0x49D = number of stations is only
    filled in FA's working copy at 0x50CE80, it is 0 in the real objects, so it is not used);
    station i record = object + [object+0x114] + i*0x11 (0x452770): dword +0 = weapon type, u16 +4 = count
    (& 0x7fff; 0x7fff = unlimited).  Station i is hardpoint i of the .PT file.
  * weapon type: byte +0 = class (7 = .JT weapon, 8 = .GAS tank); for .JT, dword +5 = short name ("AIM-9M").
The routine picks a store kind from the name (AIM-9 / other AIM / AGM / GBU / Mk-8x or CBU bomb / tank),
then hands control back to the bytecode at that kind's C4 list (or an empty one), via do_start_interp.
A slot with rank r is drawn while the station still has at least r rounds: right side rank 1, left side
rank 2, so the left store of a pair goes first.  Pylons are drawn always, so they stay after firing; tanks
disappear when used up or jettisoned (their count drops to 0).  When no aircraft object is being drawn,
each slot shows the .PT default loadout.

Draw order (FA has no z-buffer) reuses the EA-18G plane tree from f18g_growler.py; the store slots sit where
the Growler had its tanks (station 6, x = ±25), ALQ-99s (station 7, ±41), wingtip pods (station 8, ±57) and
belly pod (stations 4 and 5).
Usage: python3 f18_stores.py SH/F18.SH out/F18.SH [--static]   (--static: no F0, defaults always drawn, for viewers)
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, main_lod, insert_blocks
from f18g_growler import lathe, orient, faces_bytes, grow_vas, FLAT, GREY, DARK, BASE, SIG
import keystone

WHITE, OLIVE = 150, 156
# store kinds; 0 = nothing
NONE, TANK, AIM9, AAM, ARM, LGB, BOMB = range(7)
GENERIC = AAM                       # unknown .JT weapon on a store station
NAMES = [(b'AIM-', b'9', AIM9), (b'AIM-', None, AAM), (b'AGM-', None, ARM), (b'GBU-', None, LGB),
         (b'MK-8', None, BOMB), (b'CBU-', None, BOMB)]


# ---------------------------------------------------------------- store shapes (local x, fwd, up; top at up 0)
def missile(length, rad, nose, fin_sets, sq=False):
    """Thin missile: diamond (or square) section of radius rad, nose cone of `nose` units, flat tail.
    fin_sets = [(front fwd, rear fwd, fin span beyond the body)]."""
    sec = [(0, rad), (rad, 0), (0, -rad), (-rad, 0)] if not sq else [(rad, rad), (rad, -rad), (-rad, -rad), (-rad, rad)]
    h = length / 2
    st = [(h, 0, -rad), (h - nose, 1, -rad)]
    for f, r, s in fin_sets: st += [(f, 1, -rad), (r, 1, -rad)]
    st.append((-h, 1, -rad))
    st = sorted(set(st), key=lambda s: -s[0])
    V, F, rings = lathe(sec, st, WHITE)
    fwds = [s[0] for s in st]
    for f, r, s in fin_sets:
        a, b = fwds.index(f), fwds.index(r)
        for k, (x, z) in enumerate(sec):
            L = (x * x + z * z) ** .5
            tip = (round(x + x / L * s), round(r), round(z - rad + z / L * s)); V.append(tip)
            tri = [rings[a][k], rings[b][k], len(V) - 1]
            F += [(FLAT, DARK, tri), (FLAT, DARK, tri[::-1])]
    return V, F


def aim9():   return missile(29, 1, 4, [(9, 7, 1), (-11, -14, 2)])
def aim120(): return missile(37, 1, 5, [(2, -2, 1), (-15, -18, 2)], sq=True)
def harm():   return missile(42, 1, 6, [(4, -2, 3), (-17, -21, 2)], sq=True)


def gbu10():
    """GBU-10: thin seeker and canards up front, body radius 2, big tail wings."""
    sec = [(0, 2), (1.4, 1.4), (2, 0), (1.4, -1.4), (0, -2), (-1.4, -1.4), (-2, 0), (-1.4, 1.4)]
    st = [(21, 0, -2), (19, .5, -2), (14, .5, -2), (12, 1, -2), (-14, 1, -2), (-21, .8, -2)]
    V, F, rings = lathe(sec, st, OLIVE)
    for k in (0, 2, 4, 6):          # canards on the seeker, tail wings
        for a, b, s in ((1, 2, 2), (4, 5, 3)):
            x, z = sec[k]; L = (x * x + z * z) ** .5
            tip = (round(x / L * (2 + s)), round(st[b][0]), round(-2 + z / L * (2 + s))); V.append(tip)
            tri = [rings[a][k], rings[b][k], len(V) - 1]
            F += [(FLAT, DARK, tri), (FLAT, DARK, tri[::-1])]
    return V, F


def mk82():
    sec = [(0, 2), (1.4, 1.4), (2, 0), (1.4, -1.4), (0, -2), (-1.4, -1.4), (-2, 0), (-1.4, 1.4)]
    st = [(11, 0, -2), (9, .6, -2), (6, 1, -2), (-5, 1, -2), (-11, .4, -2)]
    V, F, rings = lathe(sec, st, OLIVE)
    for k in (1, 3, 5, 7):
        x, z = sec[k]; L = (x * x + z * z) ** .5
        tip = (round(x / L * 3), -11, round(-2 + z / L * 3)); V.append(tip)
        tri = [rings[3][k], rings[4][k], len(V) - 1]
        F += [(FLAT, DARK, tri), (FLAT, DARK, tri[::-1])]
    return V, F


def tank330():
    sec = [(0, 3), (2, 2), (3, 0), (2, -2), (0, -3), (-2, -2), (-3, 0), (-2, 2)]
    V, F, _ = lathe(sec, [(20, 0, -3), (17, .45, -3), (13, .8, -3), (8, 1, -3), (-9, 1, -3), (-15, .6, -3), (-19, 0, -3)])
    return V, F


def pylon(h, bot, top):
    """Slab 1 unit thick from local up 0 (store attach, fwd bot) to up h (inside the wing, fwd top)."""
    V = []
    for (f, r), u in ((bot, 0), (top, h)):
        for x in (-1, 0): V += [(x, f, u), (x, r, u)]
    q = [[0, 1, 5, 4], [2, 3, 7, 6], [0, 2, 6, 4], [1, 3, 7, 5]]
    return V, orient(V, [(FLAT, GREY, f) for f in q])


SHAPES = {TANK: tank330, AIM9: aim9, AAM: aim120, ARM: harm, LGB: gbu10, BOMB: mk82}

# ---------------------------------------------------------------- slots: (station, rank, default kind, attach x, up, fwd)
# x / fwd from F18.PT; up = pylon bottom (wing pylons) or a point just under the belly / on the wingtip rail
SLOTS = {
    'R6': (6, 1, LGB, (25, -4, -3)),  'L6': (6, 2, LGB, (-25, -4, -3)),
    'R7': (7, 1, ARM, (41, -4, -6)),  'L7': (7, 2, ARM, (-41, -4, -6)),
    'R8': (8, 1, AIM9, (57, 1, -9)),  'L8': (8, 2, AIM9, (-57, 1, -9)),
    'C4': (4, 1, TANK, (0, -9, 0)),
    'R5': (5, 1, AAM, (10, -7, 0)),   'L5': (5, 2, NONE, (-10, -7, 0)),
}
PYLONS = {'pyW': pylon(6, (6, -7), (9, -10)), 'pyC': pylon(3, (5, -6), (6, -7))}


# ---------------------------------------------------------------- x86
def asm(src, addr=0):
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    enc, _ = ks.asm(src, addr)
    return bytes(enc)


def name_table():
    t = b''
    for pre, c5, k in NAMES: t += pre + (c5 or b'\x00') + bytes([k])
    return t + b'\x00' * 4


def sub_bytes(sub_at, thunk_at):
    """Shared routine (offsets are CODE offsets; VA = 0x1000 + offset).  Entry: [esp] = slot table
    (i16 per kind, relative to the table), [esp+4] = station | rank << 8 | default kind << 16."""
    head = asm('''
        pop ebx
        pop eax
        push ecx
        push edx
        push esi
        push edi
        mov edi, eax
        movzx esi, al
        mov ecx, dword ptr [0x51ce26]
        test ecx, ecx
        jle DEFAULT
        movzx edx, word ptr [0x580bec]
        cmp cx, dx
        jne DEFAULT
        mov ecx, dword ptr [edx*4 + 0x553848]
        test ecx, ecx
        je DEFAULT
        cmp byte ptr [ecx], 4
        jne DEFAULT
        cmp esi, 16
        jae NONE
        imul esi, esi, 0x11
        add esi, dword ptr [ecx + 0x114]
        add esi, ecx
        movzx edx, word ptr [esi + 4]
        and edx, 0x7fff
        mov eax, edi
        shr eax, 8
        movzx eax, al
        cmp edx, eax
        jb NONE
        mov esi, dword ptr [esi]
        test esi, esi
        je NONE
        cmp byte ptr [esi], 8
        je TANK
        cmp byte ptr [esi], 7
        jne NONE
        mov esi, dword ptr [esi + 5]
        test esi, esi
        je NONE
        mov ecx, dword ptr [esi]
        mov dl, byte ptr [esi + 4]
        jmp LOOKUP
    DEFAULT:
        mov eax, edi
        shr eax, 16
        movzx eax, al
        jmp OUT
    NONE:
        xor eax, eax
        jmp OUT
    TANK:
        mov eax, %d
        jmp OUT
    LOOKUP:
        nop
        nop
        nop
        nop
        nop
    OUT:
        movsx eax, word ptr [ebx + eax*2]
        add eax, ebx
        pop edi
        pop esi
        pop edx
        pop ecx
        push eax
    ''' % TANK)
    # LOOKUP (5 nops) becomes a jmp to the name lookup placed after the head (it needs the table address)
    tbl = name_table()
    look = asm('''
        pop esi
    LOOP:
        mov eax, dword ptr [esi]
        test eax, eax
        je GEN
        cmp eax, ecx
        jne NEXT
        mov al, byte ptr [esi + 4]
        test al, al
        je HIT
        cmp al, dl
        je HIT
    NEXT:
        add esi, 6
        jmp LOOP
    HIT:
        movzx eax, byte ptr [esi + 5]
        jmp BACK
    GEN:
        mov eax, %d
    BACK:
    ''' % GENERIC)
    # layout: head | jmp thunk | call over table | table | lookup | jmp OUT
    nop_at = head.index(b'\x90' * 5); out_at = nop_at + 5
    b = bytearray(head)
    # return to the bytecode the way FA's own F0 blocks do: push do_start_interp; ret.  The pushed value is the
    # thunk's VA and needs a relocation: FA's loader copies CODE only up to the signature and points relocations
    # that hit a thunk at the real target, so a relative jump to the thunk would land on nothing.
    reloc_at = len(b) + 1
    b += b'\x68' + struct.pack('<I', 0x1000 + thunk_at) + b'\xc3'
    look_start = len(b)
    b[nop_at:nop_at+5] = b'\xe9' + struct.pack('<i', look_start - (nop_at + 5))
    b += b'\xe8' + struct.pack('<i', len(tbl)) + tbl + look
    b += b'\xe9' + struct.pack('<i', out_at - (len(b) + 5))
    return bytes(b), reloc_at


# ---------------------------------------------------------------- SH build
def find_thunk(c, tail):
    """do_start_interp thunk: the target of `push imm32; ret` / `push retVA; push thunk; ret` in existing F0s."""
    import re, collections
    hits = collections.Counter()
    for m in re.finditer(rb'\x68(....)\xc3', bytes(c[:tail]), re.S):
        v = struct.unpack('<I', m.group(1))[0] - 0x1000
        if tail < v < len(c) and c[v:v+2] == b'\xff\x25': hits[v] += 1
    return hits.most_common(1)[0][0]


def build(d, static=False):
    d = bytearray(d)
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    c = bytearray(d[code['ro']:code['ro']+code['vs']])
    o0, n, _, e = main_lod(c)[0]
    ROOT = e
    while c[ROOT] == 0xF6: ROOT += 7
    assert c[ROOT] == 0x06 and c[ROOT+1] == 0 and c[ROOT+18] == 0x38, 'root is not the expected 06 node + 38'
    TA = ROOT + 16 + struct.unpack_from('<h', c, ROOT+14)[0]; TB = ROOT + 18 + struct.unpack_from('<h', c, ROOT+16)[0]
    GF, GE = 0x3068, 0x3087
    assert c[GF] == 0xFC and c[GE] == 0xF0, 'unexpected bytes at the gear hook'
    assert c[TA] == 0x06 and c[TA+1] == 0, 'TA is not a plane node'
    tail = bytes(c).find(SIG)
    thunk_old = find_thunk(c, tail)

    def part_bytes(V, F):
        b = bytearray(struct.pack('<BBHH', 0x82, 0, len(V), BASE*8))
        for v in V: b += struct.pack('<hhh', *v)
        return b + faces_bytes(V, F) + b'\x00\x00'
    shapes = {k: f() for k, f in SHAPES.items()}
    parts = {('K', k): part_bytes(*v) for k, v in shapes.items()}
    parts.update({('P', k): part_bytes(*v) for k, v in PYLONS.items()})
    nv = max(len(v[0]) for v in list(shapes.values()) + list(PYLONS.values()))
    if BASE + nv > 900: sys.exit('vertex table over 900')

    # tree leaves (same groups as the Growler): items are ('c4', part key, pos) or ('call', slot name)
    pos = {k: v[3] for k, v in SLOTS.items()}
    leaves = {
        'Ltip': [('call', 'L8')], 'Lalq': [('call', 'L7')], 'Ltank': [('call', 'L6')],
        'C': [('c4', ('P', 'pyC'), pos['C4']), ('call', 'C4'), ('call', 'R5'), ('call', 'L5')],
        'Rtank': [('call', 'R6')], 'Ralq': [('call', 'R7')], 'Rtip': [('call', 'R8')],
        'LPY': [('c4', ('P', 'pyW'), pos['L6']), ('c4', ('P', 'pyW'), pos['L7'])],
        'RPY': [('c4', ('P', 'pyW'), pos['R6']), ('c4', ('P', 'pyW'), pos['R7'])],
    }
    isz = lambda it: 16 if it[0] == 'c4' else 4
    NK = 7
    STUB = 2 + 5 + 5 + 2 * NK                       # F0 00, push imm32, call rel32, kind table
    order = ['PR', 'PRT', 'PL', 'PLT', 'PYR', 'PYL', 'BODY', 'MID', 'GH', 'LG', 'RG'] + list(leaves)
    size = {k: 20 for k in order}
    size['GH'] = GE - GF + 4 + 2
    size.update({k: sum(isz(it) for it in v) + 2 for k, v in leaves.items()})
    at, p = {}, tail
    for k in order: at[k] = p; p += size[k]
    for s in SLOTS:                                   # slot: stub (or, static, a call to its default list)
        at['S' + s] = p; p += (STUB if not static else 6)
        for kd in range(1, NK):
            at[('L', s, kd)] = p; p += 18             # C4 + 00 00
    at['EMPTY'] = p; p += 2
    at['SUB'] = p
    sub, _ = sub_bytes(0, 0)
    sub_len = len(sub) if not static else 0
    p += sub_len
    relocs = []
    for k in parts: at[k] = p; p += len(parts[k])
    L = p - tail                                      # inserted length; thunk moves by L
    thunk_new = thunk_old + L

    def node(k, nrm, dd, a, b):
        o = at[k]
        return struct.pack('<BB6h', 0x06, 0, nrm[0], dd[0], nrm[1], dd[1], nrm[2], dd[2]) + \
            struct.pack('<hh', at[a] - (o+16), at[b] - (o+18)) + b'\x00\x00'
    X = (16384, 0, 0)
    blk = bytearray()
    blk += node('PR', (3604, -16384, 819), (-18, -2, 0), 'PRT', 'RG')
    blk += node('PRT', (10923, 13107, 0), (-20, 0, 0), 'PL', 'Rtip')
    blk += node('PL', (-3604, -16384, 819), (18, -2, 0), 'PLT', 'LG')
    blk += node('PLT', (-10923, 13107, 0), (20, 0, 0), 'PYR', 'Ltip')
    blk += node('PYR', (0, -16384, 0), (0, -2, 0), 'PYL', 'RPY')
    blk += node('PYL', (0, -16384, 0), (0, -2, 0), 'BODY', 'LPY')
    TAB = TA + 18 + struct.unpack_from('<h', c, TA+16)[0]; at['TAB'] = TAB
    o = at['BODY']; blk += bytes(c[ROOT:ROOT+14]) + struct.pack('<hh', TA - (o+16), TB - (o+18)) + b'\x00\x00'
    o = at['MID']; blk += bytes(c[TA:TA+14]) + struct.pack('<hh', at['C'] - (o+16), TAB - (o+18)) + b'\x00\x00'
    struct.pack_into('<h', c, TA+16, at['MID'] - (TA+18))
    o = at['GH']; blk += bytes(c[GF:GE]) + b'\x12\x00' + struct.pack('<h', at['C'] - (o + GE - GF + 4)) + b'\x00\x00'
    hook = b'\x12\x00' + struct.pack('<h', at['GH'] - (GF+4)) + b'\x38' + struct.pack('<h', GE - (GF+7))
    c[GF:GE] = hook + b'\x1e' * (GE - GF - len(hook))
    blk += node('LG', X, (33, 0, 0), 'Lalq', 'Ltank')
    blk += node('RG', X, (-33, 0, 0), 'Rtank', 'Ralq')
    for k, items in leaves.items():
        o = at[k]
        for it in items:
            if it[0] == 'c4':
                blk += struct.pack('<BB6h', 0xC4, 0, *it[2], 0, 0, 0) + struct.pack('<h', at[it[1]] - (o+16)); o += 16
            else:
                blk += b'\x12\x00' + struct.pack('<h', at['S' + it[1]] - (o+4)); o += 4
        blk += b'\x00\x00'
    for s, (st, rank, dflt, ps) in SLOTS.items():
        o = at['S' + s]; assert len(blk) == o - tail
        if static:
            tgt = at[('L', s, dflt)] if dflt else at['EMPTY']
            blk += b'\x12\x00' + struct.pack('<h', tgt - (o+4)) + b'\x00\x00'
        else:
            blk += b'\xf0\x00' + b'\x68' + struct.pack('<I', st | rank << 8 | dflt << 16)
            blk += b'\xe8' + struct.pack('<i', at['SUB'] - (o + 12))
            tb = o + 12
            for kd in range(NK):
                tgt = at[('L', s, kd)] if kd else at['EMPTY']
                blk += struct.pack('<h', tgt - tb)
        for kd in range(1, NK):
            q = at[('L', s, kd)]
            blk += struct.pack('<BB6h', 0xC4, 0, *ps, 0, 0, 0) + struct.pack('<h', at[('K', kd)] - (q+16)) + b'\x00\x00'
    blk += b'\x00\x00'
    if not static:
        assert len(blk) == at['SUB'] - tail
        sub, rel = sub_bytes(at['SUB'], thunk_new)
        relocs = [at['SUB'] - tail + rel]
        assert len(sub) == sub_len
        blk += sub
    for k in parts: blk += parts[k]
    assert len(blk) == L, (len(blk), L)
    patch = b'\x12\x00' + struct.pack('<h', at['PR'] - (ROOT+4)) + b'\x38' + struct.pack('<h', ROOT + 18 - (ROOT+7))
    c[ROOT:ROOT+18] = patch + b'\x1e' * (18 - len(patch))
    room = nxt - code['va'] - len(c)
    print({str(k): len(v) for k, v in parts.items()}, 'total', len(blk), 'room', room, 'max part verts', nv,
          'sub', sub_len, 'thunk', hex(thunk_old), '->', hex(thunk_new))
    if len(blk) > room: return None, len(blk), room, at
    return insert_blocks(d, pe, secs, code, c, tail, bytes(blk), relocs), len(blk), room, at


def make(d, static=False):
    out, need, room, at = build(d, static)
    if out is None:
        delta = (need - room + 0xFFF) // 0x1000 * 0x1000
        print(f'moving .idata/.reloc/$$DOSX up by {delta:#x} to make room')
        out, need, room, at = build(grow_vas(d, delta), static)
    return out, at


def main():
    src, dst = sys.argv[1], sys.argv[2]
    out, _ = make(open(src, 'rb').read(), '--static' in sys.argv)
    open(dst, 'wb').write(out)
    print('wrote', dst)


if __name__ == '__main__':
    main()
