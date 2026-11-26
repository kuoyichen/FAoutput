#!/usr/bin/env python3
"""Generic 3D landing gear with spinning wheels (f14_gear / f18_gear method, skill SH_edit_note §16) for any SH
whose gear are FA's stock crossed-billboard C4 parts.  Each gear given in the spec becomes:
  square strut (prism), diamond axle, black octagonal tread (not turning), and a round textured hub sub-part (C4,
  6-byte range header before its 82) on each side of the wheel, spun by x86 in an F0 trampoline that replaces
  the start of the old part (FA's own retract F0 / C4 stay untouched).
spec = dict(parts={'R': off, 'L': off, 'N': off}  (82 of each old part), span_end={side: offset of the old part's 1E},
            gear={side: dict(top=(x, fwd, up), bot=(x, fwd, up), wheel=(x, fwd, up), r=, w=(x0, x1))}  part-local,
            hub_main=(u, v, rpx), hub_nose=(u, v, rpx), clear=[(u0, v0, u1, v1)], strip=(u0, u1, v0, v1) or None)
"""
import math, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools', 'shgen')); sys.path.insert(0, HERE)
from sh_subdivide import pe_sections, insert_blocks
import f14_gear as G
from f14_gear import Part, prism, tread, wheel_part, node, c4, put, read_pic, SIG, STRUT, BRACE
from f18_gear import shrink_reloc
from f18g_growler import grow_vas
from fs_core import find_thunk


def build(g, base, wbase, hub):
    st = Part(base)
    tx, ty, tz = g['top']; bx, by, bz = g['bot']; wx, wy, wz = g['wheel']
    sx = 1 if wx > bx else -1                                   # wheel on the +x or -x side of the strut
    faces = prism(st, (tx, ty, tz), (bx, by, bz - 1), 1.42 * g.get('sr', 1), 4, STRUT, rot=math.pi / 4, caps=(False, True))
    if (bx, by) != (wx, wy) or bz != wz:
        faces += prism(st, (bx, by, wz), (wx, wy, wz), 1.0, 4, BRACE, caps=(False, False))   # axle, centred on the hub
    for a, b in g.get('braces', []):
        faces += prism(st, a, b, 0.6, 4, BRACE, rot=math.pi / 4)
    x0, x1 = g['w']
    tr = tread(st, (wx, wy, wz), g['r'], x0, x1)
    mid = wx + (x0 if sx > 0 else x1) - sx                      # plane between strut and tyre
    split = ((-16384 * sx, 0, 0), (-mid, 0, 0))                 # eye on the strut side -> wheel first, then strut
    wp = wheel_part(wbase, g['r'], hub, x0, x1)
    assert base + len(st.V) <= wbase, len(st.V)
    return st, faces, tr, split, wp


def part_block(g, at, header, base, wbase, hub):
    st, sfaces, tr, (n, d), wp = build(g, base, wbase, hub)
    out = bytearray(st.bytes())
    T = st.group(tr)[0][:-1]
    S, _ = st.group(sfaces)
    WB = header + wp.bytes() + wp.group(range(len(wp.F)))[0]
    wx, wy, wz = g['wheel']
    N1 = at + len(out); W = N1 + 20; C = W + len(T); s = C + 17; wpos = s + len(S) + 6
    out += node(N1, n, d, W, s) + T + c4(C, (wx, wz, wy), wpos) + b'\x1e' + S + WB
    assert out[wpos - at] == 0x82 and out[C - at] == 0xC4
    return bytes(out), [C]


def run(src, psrc, dst, pdst, spec):
    pb = bytearray(open(psrc, 'rb').read()); P = read_pic(pb)
    for a in spec.get('clear', []):
        for v in range(a[1], a[3] + 1):
            for u in range(a[0], a[2] + 1): put(pb, P, u, v, 255)
    G.HUB_AREA = (0, 0, -1, -1)                               # nothing more to clear
    G.HUB_MAIN, G.HUB_NOSE = spec['hub_main'], spec['hub_nose']
    G.draw_textures(pb, P)
    G.STRIP = spec.get('strip'); G.TEXCOLS = (STRUT, BRACE) if G.STRIP else ()
    d = bytearray(open(src, 'rb').read())
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    if nxt - code['va'] - code['vs'] < 4096:
        d = bytearray(grow_vas(d, 0x1000)); pe, opt, secs = pe_sections(d)
        code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    c = bytearray(d[code['ro']:code['ro'] + code['vs']])
    OLD, SPAN = spec['parts'], spec['span_end']
    for o in OLD.values(): assert c[o] == 0x82 and c[o + 1] == 0, hex(o)
    header = bytes(c[OLD['R'] - 6:OLD['R']])
    assert all(v > 0 for v in struct.unpack('<3h', header)), header
    tail = bytes(c).find(SIG)
    thunk = find_thunk(c, tail)
    base, wbase = spec.get('base', 594), spec.get('wbase', 668)
    blk = bytearray(); starts = {}; c4s = {}
    for side, g in spec['gear'].items():
        starts[side] = tail + len(blk)
        hub = spec['hub_nose'] if side == 'N' else spec['hub_main']
        b, w = part_block(g, tail + len(blk), header, base, wbase, hub); blk += b; c4s[side] = w
    while len(blk) % 4: blk += b'\x00'
    tbl = tail + len(blk); blk += bytes(32 * 8)
    room = nxt - code['va'] - len(c)
    if len(blk) > room: sys.exit(f'no room: need {len(blk)}, have {room}')
    L = len(blk)
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    relocs = []
    for side, old in OLD.items():
        Lpos = old + 2 + 2 + 5
        body = bytes(ks.asm(G.spin_x86(Lpos, tbl, [a + 10 for a in c4s[side]]), 0)[0])
        assert body[2] == 0xE8
        pp = old + 2 + len(body)
        tr = b'\xf0\x00' + body + b'\x68' + struct.pack('<I', code['va'] + starts[side]) + b'\x68' + struct.pack('<I', 0x1000 + thunk + L) + b'\xc3'
        assert old + len(tr) <= SPAN[side], (side, len(tr), hex(SPAN[side] - old))
        c[old:old + len(tr)] = tr
        relocs += [pp + 1 - tail, pp + 6 - tail]
    out = shrink_reloc(insert_blocks(d, pe, secs, code, c, tail, bytes(blk), extra_relocs=relocs))
    assert len(out) < 65536, f'SH {len(out)} B, FA needs < 65536'
    open(dst, 'wb').write(out); open(pdst, 'wb').write(pb)
    print(f'{dst}: gear {len(blk)} B at CODE+{tail:#x}, file {len(out)}; parts {[hex(v) for v in starts.values()]}')
