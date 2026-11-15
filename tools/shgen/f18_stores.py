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
A slot with rank r is drawn while the station still has at least r rounds: left side rank 1, right side
rank 2, so the right store of a pair goes first (as FA fires them).  Pylons are drawn always, so they stay after firing; tanks
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
NONE, TANK, AIM9, AAM, ARM, LGB, BOMB, AIM7, AIM54, JDAM = range(10)
GENERIC = AAM                       # unknown .JT weapon on a store station
NAMES = [(b'AIM-', b'9', AIM9), (b'AIM-', b'7', AIM7), (b'AIM-', b'5', AIM54), (b'GBU-', b'3', JDAM), (b'AIM-', None, AAM), (b'AGM-', None, ARM), (b'GBU-', None, LGB),
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


def tank480():
    """F/A-18E 480-gal tank: long pointed nose, straight body, tapered tail cone (no fins, Kuoyi 2026-11-15)."""
    r = 3.5; e = r * .7
    sec = [(0, r), (e, e), (r, 0), (e, -e), (0, -r), (-e, -e), (-r, 0), (-e, e)]
    st = [(25, 0, -r), (21, .35, -r), (16, .65, -r), (11, .88, -r), (6, 1, -r), (-11, 1, -r), (-17, .75, -r),
          (-22, .45, -r), (-25, .3, -r)]
    V, F, rings = lathe(sec, st, WHITE)
    return V, F


AFT = -10      # every store ends this far behind its attach point, so it clears the lowered flaps


def aft(VF):
    V, F = VF; d = AFT - min(v[1] for v in V)
    return [(x, f + d, u) for x, f, u in V], F


def pylon(h, bot, top):
    """Slab 1 unit thick from local up 0 (store attach, fwd bot) to up h (inside the wing, fwd top)."""
    V = []
    for (f, r), u in ((bot, 0), (top, h)):
        for x in (-1, 0): V += [(x, f, u), (x, r, u)]
    q = [[0, 1, 5, 4], [2, 3, 7, 6], [0, 2, 6, 4], [1, 3, 7, 5]]
    return V, orient(V, [(FLAT, GREY, f) for f in q])


import fa_weapons
# FA's own weapon models (with their colour bands), scaled to real length in F18 units (~9.5 units per metre)
SHAPES = {TANK: tank480, AIM9: lambda: fa_weapons.load('SIDEM.SH', 29), AAM: lambda: fa_weapons.load('AMRAM.SH', 37),
          ARM: lambda: fa_weapons.load('HARM.SH', 42), LGB: lambda: fa_weapons.load('PAVE.SH', 42, roll=45),
          BOMB: lambda: fa_weapons.load('MK82.SH', 21),
          AIM7: lambda: fa_weapons.load('SPAR.SH', 36), AIM54: lambda: fa_weapons.load('PHENX.SH', 40),
          JDAM: lambda: fa_weapons.load('GB27.SH', 37)}       # GBU-3x JDAM: FA's GBU-29/30 shape (X fins), GBU-31 length

# ---------------------------------------------------------------- slots: (station, rank, default kind, attach x, up, fwd)
# x / fwd from F18.PT; up = pylon bottom (wing pylons) or a point just under the belly / on the wingtip rail
SLOTS = {   # right side rank 2, left side rank 1: FA fires the right store of a pair first (seen in game)
    'R6': (6, 2, LGB, (25, -4, -3)),  'L6': (6, 1, LGB, (-25, -4, -3)),
    'R7': (7, 2, ARM, (41, -4, -4)),  'L7': (7, 1, ARM, (-41, -4, -4)),
    'R8': (8, 2, AIM9, (57, 1, -9)),  'L8': (8, 1, AIM9, (-57, 1, -9)),
    'C4': (4, 1, TANK, (0, -9, -8)),
    'R5': (5, 2, AAM, (10, -7, 0)),   'L5': (5, 1, AAM, (-10, -7, 0)),
}
PYLONS = {'pyW': pylon(6, (5, -5), (6, -6)), 'pyC': pylon(3, (5, -6), (6, -7))}
# wing pylon centre fwd per station: between the leading edge and the flap / aileron hinge
PYFWD = {6: -1, 7: -4}


def f18_pylon_units():
    """Pylons drawn always: (unit name, pylon part, position (x, up, fwd), top of its box for the draw order)."""
    pos = {k: v[3] for k, v in SLOTS.items()}
    out = []
    for s in ('R6', 'L6', 'R7', 'L7'):
        ps = pos[s][:2] + (PYFWD[SLOTS[s][0]],); out.append(('py' + s, 'pyW', ps, ps[1] + 3))
    cpy = pos['C4'][:2] + (pos['C4'][2] + 15,)                    # centre pylon at the middle of the tank
    out.append(('pyC4', 'pyC', cpy, cpy[1] + 2))
    return out


PLACER = None                      # e.g. sh_order-based placement: PLACER(c, ROOT, unit geometry, unit boxes)
PYLON_UNITS = f18_pylon_units      # an aircraft module (f14_stores.py) replaces SLOTS, PYLONS and this


# ---------------------------------------------------------------- x86
def asm(src, addr=0):
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    enc, _ = ks.asm(src, addr)
    return bytes(enc)


def name_table():
    t = b''
    for pre, c5, k in NAMES: t += pre + (c5 or b'\x00') + bytes([k])
    return t + b'\x00' * 4


DEBUG_LEGEND = {'found weapon/tank': TANK, 'no object (default)': AIM9, 'count < rank': AAM, 'type pointer 0': ARM,
                'class not 7/8': LGB, 'name pointer 0': BOMB}


def debug_src(src):
    """Diagnostic routine: every exit returns its own kind (see DEBUG_LEGEND) instead of the store kind."""
    # explicit rewrites, in order of appearance
    src = src.replace('''        mov esi, dword ptr [esi]
        test esi, esi
        je NONE''', '''        mov esi, dword ptr [esi]
        test esi, esi
        je NTD''')
    src = src.replace('''        cmp byte ptr [esi], 7
        jne NONE''', '''        cmp byte ptr [esi], 7
        jne NCLS''')
    src = src.replace('''        mov esi, dword ptr [esi + 5]
        test esi, esi
        je NONE''', '''        mov esi, dword ptr [esi + 5]
        test esi, esi
        je NNAME''')
    src = src.replace('jb NONE', 'jb NCNT')
    src = src.replace('''    DEFAULT:
        mov eax, edi
        shr eax, 16
        movzx eax, al
        jmp OUT''', '''    DEFAULT:
        mov eax, %d
        jmp OUT
    NCNT:
        mov eax, %d
        jmp OUT
    NTD:
        mov eax, %d
        jmp OUT
    NCLS:
        mov eax, %d
        jmp OUT
    NNAME:
        mov eax, %d
        jmp OUT''' % (AIM9, AAM, ARM, LGB, BOMB))
    src = src.replace('''        mov ecx, dword ptr [esi]
        mov dl, byte ptr [esi + 4]
        jmp LOOKUP''', '''        mov eax, %d
        jmp OUT''' % TANK)
    return src


def sub_bytes(sub_at, thunk_at, debug=False):
    """Shared routine (offsets are CODE offsets; VA = 0x1000 + offset).  Entry: [esp] = slot table
    (i16 per kind, relative to the table), [esp+4] = station | rank << 8 | default kind << 16."""
    src = '''
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
    ''' % TANK
    if debug:   # each exit draws a different shape, to see in game where the check stops
        src = debug_src(src)
    head = asm(src)
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


def place_units(c, ROOT, ubox):
    """Insert each store unit into the model's BSP tree: follow the node whose plane has the whole unit on one
    side (positive side = B branch, drawn last when the eye is on that side), and stop at the first node that
    cuts it or at a leaf.  There a new 06 node separates the unit from what that branch draws: the axis plane
    against the unit's box that leaves the fewest of the branch's points (and earlier units) on the unit's side.
    Returns {branch target: [(unit, n, d), ...]} (chained in order) and {branch target: (rel field, base)}."""
    import sh_bsp
    _, tree = sh_bsp.parse(bytes(c), ROOT)
    h = lambda p: struct.unpack_from('<h', c, p)[0]
    plan, refs = {}, {}

    def pts(items):
        out = []
        def walk(it):
            for x in it:
                if x[0] == 'face': out.extend(x[2])
                elif x[0] == 'node': walk(x[5]); walk(x[6])
                elif x[0] == 'call': walk(x[2])
        walk(items); return out
    corners = lambda b: [(x, u, f) for x in (b[0][0], b[1][0]) for u in (b[0][1], b[1][1]) for f in (b[0][2], b[1][2])]
    for u, b in ubox.items():
        T, items, ref = 'ROOT', tree, (None, None)
        while True:
            nds = [x for x in items if x[0] == 'node']
            if len(nds) != 1: break
            nd = nds[0]; p, op, nn, dd = nd[1], nd[2], nd[3], nd[4]
            cen = [(b[0][j] + b[1][j]) / 2 for j in range(3)]
            if op == 0x6C:                            # variable test (gear ...): follow the branch drawing nearer things
                def dist(items):
                    bb = sh_bsp.bbox(items)
                    if not bb: return 1e9
                    return sum(max(bb[0][j] - cen[j], 0, cen[j] - bb[1][j]) ** 2 for j in range(3))
                side = 'A' if dist(nd[5]) <= dist(nd[6]) else 'B'
            else:                                     # plane: the side holding the unit's centre (a straddling
                v = sum(nn[j] * (cen[j] + dd[j]) for j in range(3))   # unit is slightly misordered against it)
                side = 'B' if v >= 0 else 'A'
            if op == 0x6C: fa, base = (p+6, p+8) if side == 'A' else (p+8, p+10)
            elif op == 6: fa, base = (p+14, p+16) if side == 'A' else (p+16, p+18)
            else: fa, base = (p+10, p+12) if side == 'A' else (p+12, p+14)
            if T == 'ROOT': fa = None                 # the root node is copied (BODY); its fields are written there
            T, items, ref = base + h(fa if fa else p+14 if side == 'A' else p+16), nd[5] if side == 'A' else nd[6], (fa, base)
        G = pts(items) + [q for (uu, _, _) in plan.get(T, []) for q in corners(ubox[uu])]
        best = None
        for j in range(3):
            for sgn in (1, -1):
                cc = b[0][j] if sgn > 0 else b[1][j]           # plane at the unit's near face, unit on the + side
                bad = sum(1 for q in G if sgn * (q[j] - cc) > 0)
                if best is None or bad < best[0]: best = (bad, j, sgn, cc)
        bad, j, sgn, cc = best
        nn = [0, 0, 0]; dd = [0, 0, 0]; nn[j] = 16384 * sgn; dd[j] = -cc
        plan.setdefault(T, []).append((u, tuple(nn), tuple(dd))); refs[T] = ref
        print(f'  {u:5s} -> {T if T == "ROOT" else hex(T)}  plane {"x up fwd".split()[j]} {"+" if sgn > 0 else "-"} at {cc}  '
              f'({bad} of {len(G)} points on its side)')
    return plan, refs


def build(d, static=False, debug=False):
    d = bytearray(d)
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    c = bytearray(d[code['ro']:code['ro']+code['vs']])
    o0, n, _, e = main_lod(c)[0]
    ROOT = e
    while c[ROOT] == 0xF6: ROOT += 7
    HOOK = None
    if c[ROOT] == 0x12 and c[ROOT+1] == 0:            # root already hooked by an earlier edit (e.g. the F-14N nose):
        HOOK = ROOT; ROOT = ROOT + 4 + struct.unpack_from('<h', c, ROOT+2)[0]   # the real root node is its target
    assert c[ROOT] == 0x06 and c[ROOT+1] == 0, 'root is not a 06 node'
    tail = bytes(c).find(SIG)
    thunk_old = find_thunk(c, tail)

    def part_bytes(V, F):
        b = bytearray(struct.pack('<BBHH', 0x82, 0, len(V), BASE*8))
        for v in V: b += struct.pack('<hhh', *v)
        b += faces_bytes(V, F) + b'\x00\x00'
        return HDR + b + b'\x00' * (len(b) % 2)
    # C4 (0x4d3194) reads 3 words just BEFORE its target (model extents x, up, fwd) to pick the eye precision shift;
    # garbage there (negative/huge) wrecks the eye and the part is not drawn.  Copy the header of the file's own parts.
    hc = next(t for t in (i + 16 + struct.unpack_from('<h', c, i+14)[0] for i in range(len(c) - 16)
                          if c[i] == 0xC4 and c[i+1] == 0) if 6 <= t < len(c) - 2 and c[t] == 0x82 and c[t+1] == 0)
    HDR = bytes(c[hc-6:hc])
    assert all(v > 0 for v in struct.unpack('<3h', HDR)), HDR
    shapes = {k: aft(f()) for k, f in SHAPES.items()}
    parts = {('K', k): part_bytes(*v) for k, v in shapes.items()}
    parts.update({('P', k): part_bytes(*v) for k, v in PYLONS.items()})
    nv = max(len(v[0]) for v in list(shapes.values()) + list(PYLONS.values()))
    if BASE + nv > 900: sys.exit('vertex table over 900')

    # ---- draw order: every store unit is inserted into the model's own BSP tree (see place_units)
    leaves = {s: [('call', s)] for s in SLOTS}
    pyu = PYLON_UNITS()
    for name, part, ps, top in pyu: leaves[name] = [('c4', ('P', part), ps)]

    def box(V, ps, clip_up=None):
        P = [(ps[0] + x, ps[1] + u, ps[2] + f) for x, f, u in V]
        lo = [min(q[j] for q in P) for j in range(3)]; hi = [max(q[j] for q in P) for j in range(3)]
        if clip_up is not None: hi[1] = min(hi[1], clip_up)
        return lo, hi
    ubox = {k: box(shapes[v[2]][0], v[3]) for k, v in SLOTS.items()}
    for name, part, ps, top in pyu: ubox[name] = box(PYLONS[part][0], ps, top)
    if PLACER is None: plan, rootrefs = place_units(c, ROOT, ubox)
    else:
        ugeo = {}
        def geo(V, F, ps): return [(bool(fl & 0x40), [(ps[0] + V[i][0], ps[1] + V[i][2], ps[2] + V[i][1]) for i in idx]) for fl, col, idx in F]
        for k, v in SLOTS.items(): ugeo[k] = geo(*shapes[v[2]], v[3])
        for name, part, ps, top in pyu: ugeo[name] = geo(*PYLONS[part], ps)
        plan, rootrefs = PLACER(c, ROOT, ugeo, ubox)
    nodes = []                                        # (key, plane n, d, A target, B leaf)
    chain_top = {}
    for T, lst in plan.items():
        prev = ('T', T)
        for i, (u, nn, dd) in enumerate(lst):
            k = ('N', T, i); nodes.append((k, nn, dd, prev, u)); prev = ('K', k)
        chain_top[T] = prev
    isz = lambda it: 16 if it[0] == 'c4' else 4
    NK = len(SHAPES) + 1
    STUB = 2 + 5 + 5 + 2 * NK                       # F0 00, push imm32, call rel32, kind table
    order = ['BODY'] + [k for k, *_ in nodes] + list(leaves)
    size = {k: 20 for k in order}
    if HOOK is not None: size['BODY'] = 22
    size.update({k: sum(isz(it) for it in v) + 2 for k, v in leaves.items()})
    at, p = {}, tail
    for k in order: at[k] = p; p += size[k]
    for s in SLOTS:                                   # slot: stub (or, static, a call to its default list)
        at['S' + s] = p; p += (STUB if not static else 6)
        for kd in range(1, NK):
            at[('L', s, kd)] = p; p += 18             # C4 + 00 00
    at['EMPTY'] = p; p += 2
    at['SUB'] = p
    sub, _ = sub_bytes(0, 0, debug)
    sub_len = len(sub) if not static else 0
    p += sub_len
    pad = p % 2; p += pad
    relocs = []
    for k in parts: at[k] = p + len(HDR); p += len(parts[k])   # target = the 82 after the header
    L = p - tail                                      # inserted length; thunk moves by L
    thunk_new = thunk_old + L

    def addr(r):                                      # ('T', original target) / ('K', node key)
        if r[0] == 'K': return at[r[1]]
        return at['BODY'] if r[1] == 'ROOT' else r[1]
    TA = ROOT + 16 + struct.unpack_from('<h', c, ROOT+14)[0]; TB = ROOT + 18 + struct.unpack_from('<h', c, ROOT+16)[0]
    blk = bytearray()
    o = at['BODY']                                    # copy of the root node; its branches may lead into chains
    ta = addr(chain_top[TA]) if TA in chain_top else TA
    tb = addr(chain_top[TB]) if TB in chain_top else TB
    blk += bytes(c[ROOT:ROOT+14]) + struct.pack('<hh', ta - (o+16), tb - (o+18))
    # hooked root: BODY replaces the node inside the hook's block, so it continues with what followed it there
    blk += (b'\x38' + struct.pack('<h', ROOT + 18 - (o+21)) + b'\x1e') if HOOK is not None else b'\x00\x00'
    for k, nn, dd, a, u in nodes:
        o = at[k]
        blk += struct.pack('<BB6h', 0x06, 0, nn[0], dd[0], nn[1], dd[1], nn[2], dd[2]) + \
            struct.pack('<hh', addr(a) - (o+16), at[u] - (o+18)) + b'\x00\x00'
    for T, (fa, base) in rootrefs.items():            # original branch fields that now lead into a chain
        if T in chain_top and fa is not None: struct.pack_into('<h', c, fa, addr(chain_top[T]) - base)
    top = addr(chain_top['ROOT']) if 'ROOT' in chain_top else at['BODY']
    if HOOK is not None:
        struct.pack_into('<h', c, HOOK+2, top - (HOOK+4))
    else:
        patch = b'\x12\x00' + struct.pack('<h', top - (ROOT+4)) + b'\x38' + struct.pack('<h', ROOT + 18 - (ROOT+7))
        c[ROOT:ROOT+18] = patch + b'\x1e' * (18 - len(patch))
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
        sub, rel = sub_bytes(at['SUB'], thunk_new, debug)
        relocs = [at['SUB'] - tail + rel]
        assert len(sub) == sub_len
        blk += sub
    blk += b'\x00' * pad
    for k in parts: blk += parts[k]
    assert len(blk) == L, (len(blk), L)
    room = nxt - code['va'] - len(c)
    print({str(k): len(v) for k, v in parts.items()}, 'total', len(blk), 'room', room, 'max part verts', nv,
          'sub', sub_len, 'thunk', hex(thunk_old), '->', hex(thunk_new))
    if len(blk) > room: return None, len(blk), room, at
    return insert_blocks(d, pe, secs, code, c, tail, bytes(blk), relocs), len(blk), room, at


def make(d, static=False, debug=False):
    out, need, room, at = build(d, static, debug)
    if out is None:
        delta = (need - room + 0xFFF) // 0x1000 * 0x1000
        print(f'moving .idata/.reloc/$$DOSX up by {delta:#x} to make room')
        out, need, room, at = build(grow_vas(d, delta), static, debug)
    return out, at


def main():
    src, dst = sys.argv[1], sys.argv[2]
    out, _ = make(open(src, 'rb').read(), '--static' in sys.argv, '--debug' in sys.argv)
    open(dst, 'wb').write(out)
    print('wrote', dst)


if __name__ == '__main__':
    main()
