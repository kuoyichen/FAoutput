#!/usr/bin/env python3
"""F/A-18（F18.SH）起落架重做，做法同 f14_gear.py（見 skill/SH_edit_note.MD「起落架與轉動輪子」）：

  * 原本每個起落架是一個 C4 零件，裡面 2～3 片交叉的貼圖（側面、正面）：
      右主輪 C4 0x3108 → 零件 0x3BA6（輪子貼圖在 x=8，支柱 (1,0,0)→(4,0,-11)）
      左主輪 C4 0x351E → 零件 0x3CDF（輪子在 x=-6，支柱 (0,0,0)→(-2,0,-11)）
      前輪   C4 0x3155 → 零件 0x3F2E（側面 x=0、正面 y=1，雙輪）
    收放都是 F0 改 C4 角度（主輪航向 = gearPos/2，前輪航向 = gearPos/2），不用動
  * 新零件：方形支柱（照原貼圖的斜度）、菱形輪軸（中心對準輪心）、八角形黑色胎面（不轉），
    輪子兩側的圓形輪框是子零件 C4（前面放 6 位元組範圍標頭），轉動 = 改它的俯仰角（同 F-14）
  * 主輪半徑 4、厚 2；前輪半徑 2、厚 1、兩個（x -2..-1、1..2）
  * 輪框貼圖畫在舊的輪子側面貼圖（_F18.PIC u86-118 v47-81）和舊的前輪側面貼圖（u164-196 v91-153）
  * 0 或超過 180 節不轉，之間越快轉越快（180 節每秒 2 圈），角度表三個起落架共用
  * SH 檔要小於 65536 位元組
用法：python3 f18_gear.py SH/F18.SH PIC/_F18.PIC 輸出.SH 輸出.PIC
"""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, insert_blocks
import f14_gear as G
from f14_gear import Part, prism, wheel_part, tread, node, c4, put, read_pic, SIG, STRUT, BRACE

OLD = {'R': 0x3BA6, 'L': 0x3CDF, 'N': 0x3F2E}
SPAN_END = {'R': 0x3CD0, 'L': 0x3E09, 'N': 0x3FE0}   # 舊零件的 1E（只從 C4 進來）
THUNK_F0 = 0x30A2                                    # 一個現成的 F0（push 位址; push do_start_interp; ret）
BASE, WBASE = 594, 652
# 輪框貼圖：中心 (u, v)、半徑（格）；要清成透明的區域
HUB_MAIN, HUB_NOSE = (102, 64, 14), (180, 122, 10)
AREAS = [(86, 47, 118, 81), (164, 91, 196, 153)]
# 每個主輪：支柱頂 x、支柱底 x、輪心 x（零件座標）
MAIN = {'R': (1, 4, 8), 'L': (0, -2, -6)}
WZ, NZ, NY = -10, -12, 1                             # 主輪輪心高度；前輪輪心高度、前後位置


def build(side):
    st = Part(BASE)
    if side in 'LR':
        tx, bx, wx = MAIN[side]; sx = 1 if wx > bx else -1
        g_s = prism(st, (tx, 0, 0), (bx, 0, WZ - 1), 1.42, 4, STRUT, rot=math.pi/4, caps=(False, True))
        g_s += prism(st, (bx, 0, WZ), (wx, 0, WZ), 1.0, 4, BRACE, caps=(False, False))     # 輪軸：菱形，置中
        wheels = [((wx, WZ, 0), tread(st, (wx, 0, WZ), 4, -1, 1))]
        mid = wx - 2*sx                                                   # 支柱和輪子之間的平面
        split = ((-16384*sx, 0, 0), (-mid, 0, 0))                        # 眼睛在支柱那一側 → 先畫輪子
        wp = wheel_part(WBASE, 4, HUB_MAIN, -1, 1)
    else:
        g_s = prism(st, (-1, NY, NZ), (1, NY, NZ), 1.0, 4, BRACE, caps=(False, False))    # 輪軸
        g_s += prism(st, (0, NY, 0), (0, NY, NZ - 1), 1.0, 4, STRUT, caps=(False, True))   # 垂直支柱
        g_s += prism(st, (0, NY, -6), (0, 6, 0), 0.71, 4, BRACE, rot=math.pi/4, caps=(False, False))  # 斜撐
        wheels = [((x, NZ, NY), tread(st, (x, NY, NZ), 2, 0, 1)) for x in (-2, 1)]
        split = ((16384, 0, 0), (0, 0, 0))
        wp = wheel_part(WBASE, 2, HUB_NOSE, 0, 1)
    assert BASE + len(st.V) <= WBASE, len(st.V)
    return st, g_s, wheels, split, wp


def part_block(side, at, header):
    st, g_s, wheels, (n, d), wp = build(side)
    out = bytearray(st.bytes())
    S, _ = st.group(g_s)
    T = [st.group(t)[0][:-1] for _, t in wheels]
    WB = header + wp.bytes() + wp.group(range(len(wp.F)))[0]
    c4s = []
    if side in 'LR':
        N1 = at + len(out); W = N1 + 20; C = W + len(T[0]); s = C + 17; wpos = s + len(S) + 6
        out += node(N1, n, d, W, s) + T[0] + c4(C, wheels[0][0], wpos) + b'\x1e' + S + WB
        c4s.append(C)
    else:
        N1 = at + len(out); WL = N1 + 20; N2 = WL + len(T[0]) + 17; WR = N2 + 20; s = WR + len(T[1]) + 17; wpos = s + len(S) + 6
        CL, CR = WL + len(T[0]), WR + len(T[1])
        out += node(N1, n, d, WL, N2) + T[0] + c4(CL, wheels[0][0], wpos) + b'\x1e'
        out += node(N2, n, d, s, WR) + T[1] + c4(CR, wheels[1][0], wpos) + b'\x1e' + S + WB
        c4s += [CL, CR]
    assert out[wpos - at] == 0x82 and all(out[c - at] == 0xC4 for c in c4s)
    return bytes(out), c4s


def draw_textures(pb, P):
    for a in AREAS:
        for v in range(a[1], a[3] + 1):
            for u in range(a[0], a[2] + 1): put(pb, P, u, v, 255)
    G.HUB_AREA = AREAS[0]
    G.HUB_MAIN, G.HUB_NOSE = HUB_MAIN, HUB_NOSE
    G.draw_textures(pb, P)


def shrink_reloc(d):
    """.reloc 縮到放得下重定位資料的最小 0x200 倍數（原版 SH 的 .reloc 從 0x200 到 0x1000 都有，和資料量無關；
    F18 是 0x1000 但只有約 280 位元組資料）。只改大小和後面區段的檔案位置，VA 不動。"""
    pe, opt, secs = pe_sections(d)
    rel = next(x for x in secs if x['name'] == '.reloc')
    used = struct.unpack_from('<I', d, pe + 24 + 96 + 5*8 + 4)[0]
    new = max(0x200, (used + 0x1FF) & ~0x1FF)
    delta = rel['rs'] - new
    if delta <= 0: return d
    assert not any(d[rel['ro'] + used:rel['ro'] + rel['rs']].strip(b'\0'))
    out = bytearray(d[:rel['ro'] + new] + d[rel['ro'] + rel['rs']:])
    struct.pack_into('<II', out, rel['hdr'] + 8, new, rel['va'])
    struct.pack_into('<I', out, rel['hdr'] + 16, new)
    for x in secs:
        if x['ro'] > rel['ro']: struct.pack_into('<I', out, x['hdr'] + 20, x['ro'] - delta)
    return bytes(out)


def main():
    src, psrc, dst, pdst = sys.argv[1:5]
    pb = bytearray(open(psrc, 'rb').read()); P = read_pic(pb)
    draw_textures(pb, P)
    d = bytearray(open(src, 'rb').read())
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    if nxt - code['va'] - code['vs'] < 4096:
        from f18g_growler import grow_vas
        d = bytearray(grow_vas(d, 0x1000)); pe, opt, secs = pe_sections(d)
        code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    c = bytearray(d[code['ro']:code['ro']+code['vs']])
    for o in OLD.values(): assert c[o] == 0x82, hex(o)
    header = bytes(c[OLD['R'] - 6:OLD['R']])
    assert all(bytes(c[o - 6:o]) == header for o in OLD.values()), '零件範圍標頭不一樣'
    assert c[THUNK_F0:THUNK_F0+2] == b'\xf0\x00' and c[THUNK_F0 + 2] == 0x68 and c[THUNK_F0 + 7] == 0x68 and c[THUNK_F0 + 12] == 0xC3
    thunk = struct.unpack_from('<I', c, THUNK_F0 + 8)[0]
    tail = bytes(c).find(SIG)
    blk = bytearray(); starts = {}; c4s = {}
    for side in 'RLN':
        starts[side] = tail + len(blk)
        b, w = part_block(side, tail + len(blk), header); blk += b; c4s[side] = w
    while len(blk) % 4: blk += b'\x00'
    tbl = tail + len(blk); blk += bytes(32 * 8)
    room = nxt - code['va'] - len(c)
    if len(blk) > room: sys.exit(f'空間不夠：需要 {len(blk)}，只有 {room}')
    L = len(blk)
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    relocs = []
    for side, old in OLD.items():
        Lpos = old + 2 + 2 + 5
        body = bytes(ks.asm(G.spin_x86(Lpos, tbl, [a + 10 for a in c4s[side]]), 0)[0])
        assert body[2] == 0xE8
        pp = old + 2 + len(body)
        tr = b'\xf0\x00' + body + b'\x68' + struct.pack('<I', code['va'] + starts[side]) + b'\x68' + struct.pack('<I', thunk + L) + b'\xc3'
        assert old + len(tr) <= SPAN_END[side], (side, len(tr))
        c[old:old + len(tr)] = tr
        relocs += [pp + 1 - tail, pp + 6 - tail]
    out = shrink_reloc(insert_blocks(d, pe, secs, code, c, tail, bytes(blk), extra_relocs=relocs))
    print(f'{dst}: 起落架 {len(blk)} 位元組（空間 {room}）在 CODE+{tail:#x}，CODE 長 {len(c) + L:#x}，檔案 {len(out)}；零件 {[hex(v) for v in starts.values()]}；輪子 C4 {c4s}')
    assert len(out) < 65536, f'SH 檔 {len(out)} 位元組，FA 只接受 < 65536'
    open(dst, 'wb').write(out); open(pdst, 'wb').write(pb)
    return dict(tail=tail, starts=starts, c4s=c4s, tbl=tbl)


if __name__ == '__main__': main()
