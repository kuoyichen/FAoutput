#!/usr/bin/env python3
"""F-14 起落架重做：原本每個起落架是兩片交叉的貼圖（側面、正面），換成真的 3D 支柱、斜撐和輪胎，輪子會轉。

  * 主起落架（左右各一，C4 在 (∓26, 上 1, 前 5)，收放 = 滾轉 gearPos/2）：方形支柱、斜撐、單個大輪（半徑 5、寬 3），輪子在支柱外側
  * 前起落架（C4 (0, 上 -6, 前 69)，收放 = 俯仰 gearPos/2）：支柱、斜撐、輪軸、兩個小輪（半徑 3、寬 2）
  * 輪胎：胎面平面色（深灰），兩側是貼圖輪框（主輪灰色輪框、前輪白色輪框和黃色輪軸蓋，5 個孔），
    貼圖畫在舊起落架側面貼圖的位置（_F14.PIC u134-170、v155-229，舊的交叉面拿掉後就沒人用了）
  * 每個輪子是起落架零件裡的子零件（C4），轉動 = 改它的俯仰角。起落架零件的開頭換成 F0 跳板（同 sh_ab_flame.py）：
      物件 = [0x553848 + word[0x580BEC]*4]，速度 = dword [物件+0x34]（呎/秒 ×256，falogger 也是讀這裡）
      速度 0 或超過 190 節（320 呎/秒）：不轉；之間：轉速和速度成正比，190 節時每秒 2 圈
      每架飛機一格（32 格，以物件編號 & 31 選，存編號、角度、上次時間），角度 += 轉速 × 經過時間（timeGetTime）
  * 零件裡的畫面順序用 06 平面測試（眼睛在支柱那一側就先畫輪子再畫支柱），每個形狀都是凸的，靠背面剔除
用法：python3 f14_gear.py SH/F14.SH PIC/_F14.PIC 輸出.SH 輸出.PIC
"""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, insert_blocks
from f14_nose import face_bytes

SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])
AB_F0 = 0x395C                     # 後燃器 F0（拿它的 push do_start_interp）
# 舊的起落架零件（C4 指到這裡）：開頭改成跳板
OLD = {'L': 0x4499, 'R': 0x43D8, 'N': 0x4670}
FLAT, TEX = 0x661, 0x75C           # F14 主體的平面色面；舊起落架的貼圖面（色號 0，u8 UV）
STRUT, BRACE, TREAD = 146, 148, 158
# 貼圖：主輪 33×33、前輪 25×25（左上角 u, v）
HUB_MAIN, HUB_NOSE = (135, 156, 33), (135, 192, 25)
REV_PER_S = 2                      # 190 節時每秒幾圈
VMAX = 320                         # 190 節 = 320 呎/秒


class Part:
    """一個零件的頂點和面（頂點座標 x 右、y 前、z 上，整數）"""
    def __init__(s, base): s.base, s.V, s.F = base, [], []
    def v(s, p):
        p = tuple(int(round(c)) for c in p)
        s.V.append(p); return len(s.V) - 1
    def face(s, idx, col, inside, fl=FLAT, uv=None):
        """inside：形狀內部的一點，用來決定面朝外"""
        P = [s.V[i] for i in idx]
        n = [0, 0, 0]
        for k in range(len(P)):
            p, q = P[k], P[(k+1) % len(P)]
            n[0] += p[1]*q[2]-p[2]*q[1]; n[1] += p[2]*q[0]-p[0]*q[2]; n[2] += p[0]*q[1]-p[1]*q[0]
        cen = [sum(p[k] for p in P) / len(P) for k in range(3)]
        out = [cen[k] - inside[k] for k in range(3)]
        if sum(n[k]*out[k] for k in range(3)) > 0:     # FA 的面 ΣP×P 要朝內
            idx = idx[::-1]; uv = uv[::-1] if uv else uv
        s.F.append((fl, col, idx, uv))
    def bytes(s):
        b = bytearray(struct.pack('<BBHH', 0x82, 0, len(s.V), s.base * 8))
        for p in s.V: b += struct.pack('<hhh', *p)
        return b
    def faces_bytes(s, sel=None):
        b = bytearray()
        for k, (fl, col, idx, uv) in enumerate(s.F):
            if sel is None or k in sel:
                b += face_bytes(fl, col, [s.base + i for i in idx], [s.V[i] for i in idx], uv)
        return b


def prism(part, a, b, r, n, col, rot=0.0, caps=(True, True)):
    """a→b 的 n 角柱（半徑 r），回傳面編號"""
    ax = [b[k] - a[k] for k in range(3)]; L = math.sqrt(sum(x*x for x in ax)); ax = [x / L for x in ax]
    t = [1, 0, 0] if abs(ax[0]) < 0.9 else [0, 1, 0]
    u = [ax[1]*t[2]-ax[2]*t[1], ax[2]*t[0]-ax[0]*t[2], ax[0]*t[1]-ax[1]*t[0]]; ul = math.sqrt(sum(x*x for x in u)); u = [x/ul for x in u]
    w = [ax[1]*u[2]-ax[2]*u[1], ax[2]*u[0]-ax[0]*u[2], ax[0]*u[1]-ax[1]*u[0]]
    ring = lambda c: [part.v([c[k] + r*(math.cos(2*math.pi*i/n + rot)*u[k] + math.sin(2*math.pi*i/n + rot)*w[k]) for k in range(3)]) for i in range(n)]
    A, B = ring(a), ring(b); mid = [(a[k]+b[k])/2 for k in range(3)]
    f0 = len(part.F)
    for i in range(n):
        j = (i+1) % n; part.face([A[i], A[j], B[j], B[i]], col, mid)
    if caps[0]: part.face(A, col, mid)
    if caps[1]: part.face(B, col, mid)
    return list(range(f0, len(part.F)))


def wheel(base, x0, x1, r, n, hub):
    """輪子零件：軸沿 x，中心在原點。胎面平面色、兩側貼圖輪框"""
    p = Part(base); hu, hv, hs = hub; c = (hs - 1) / 2
    rings = []
    for x in (x0, x1):
        rings.append([p.v((x, r*math.cos(2*math.pi*i/n), r*math.sin(2*math.pi*i/n))) for i in range(n)])
    A, B = rings; mid = ((x0+x1)/2, 0, 0)
    for i in range(n):
        j = (i+1) % n; p.face([A[i], A[j], B[j], B[i]], TREAD, mid)
    for R in (A, B):
        uv = [(round(hu + c + c * p.V[i][1] / r), round(hv + c - c * p.V[i][2] / r)) for i in R]
        p.face(list(R), 0, mid, TEX, uv)
    return p


def draw_hub(pb, P, hub, rim, cap):
    """輪框貼圖：黑色輪胎、輪框、5 個孔、中間的輪軸蓋（5 個孔讓轉動看得出來，不會像車輪錯覺一樣倒轉）"""
    hu, hv, hs = hub; c = (hs - 1) / 2
    for y in range(hs):
        for x in range(hs):
            dx, dy = (x - c) / c, (y - c) / c; d = math.hypot(dx, dy); a = math.atan2(dy, dx)
            if d > 1.04: k = 255
            elif d > 0.93: k = 158
            elif d > 0.68: k = 159 if (int((a + math.pi) / (2*math.pi) * 24) % 2 or d < 0.88) else 157
            elif d > 0.62: k = 152
            elif d < 0.16: k = cap
            elif d < 0.21: k = 154
            else:
                k = rim
                for h in range(5):                  # 孔
                    ha = 2*math.pi*h/5
                    if math.hypot(dx - 0.42*math.cos(ha), dy - 0.42*math.sin(ha)) < 0.11: k = 157
            put(pb, P, hu + x, hv + y, k)


def read_pic(b):
    w, h = struct.unpack_from('<II', b, 2); rt = struct.unpack_from('<I', b, 0x22)[0]
    return w, h, [struct.unpack_from('<I', b, rt + 4*r)[0] for r in range(h)]


def put(b, P, u, v, k):
    w, h, rows = P; b[rows[h-1-v] + u] = k


def node(at, n, d, a, b):
    """06 平面測試：Σn·(眼睛+d) ≥ 0 先 a 再 b，否則先 b 再 a；之後 00 00 返回"""
    return struct.pack('<BB6h', 0x06, 0, n[0], d[0], n[1], d[1], n[2], d[2]) + struct.pack('<hh', a - (at+16), b - (at+18)) + b'\x00\x00'


def c4(at, pos, target):
    """C4 00 位置(x, 上, 前) 角度(航向, 俯仰, 滾轉) rel16（相對指令結尾）"""
    return struct.pack('<BB6h', 0xC4, 0, *pos, 0, 0, 0) + struct.pack('<h', target - (at + 16))


def build(side):
    """回傳 (零件資訊)：支柱零件、輪子零件和它們在零件座標的位置（預覽也用）"""
    if side in 'LR':
        sx = 1 if side == 'L' else -1                     # L = C4 x -26 那一側（支柱在 +x，輪子在外側 -x）
        base = 600 if side == 'L' else 670
        st = Part(base)
        sf = prism(st, (3*sx, 1, 1), (3*sx, 1, -19), 1.42, 4, STRUT, rot=math.pi/4)       # 方形支柱（2×2）
        sf2 = prism(st, (3*sx, 1, -6), (3*sx, 1, -9), 1.9, 4, BRACE, rot=math.pi/4)       # 減震筒的套環
        bf = prism(st, (3*sx, 1, -11), (6*sx, 8, 0), 0.75, 4, BRACE, rot=math.pi/4)       # 斜撐
        wh = wheel(base + 40, -1 if sx > 0 else -2, 2 if sx > 0 else 1, 5, 12, HUB_MAIN)
        wheels = [((0, -19, 1), wh)]                      # C4 位置 (x, 上, 前)：輪軸在支柱底
        split = ((16384*sx, 0, 0), (-2*sx, 0, 0))         # 眼睛在支柱那一側 → 先畫輪子
        groups = (sf + sf2, bf)
    else:
        st = Part(740)
        sf = prism(st, (0, 7, -1), (0, 5, -13), 1.0, 4, STRUT)
        sf2 = prism(st, (-3, 5, -13), (3, 5, -13), 0.71, 4, BRACE, rot=math.pi/4)          # 輪軸
        bf = prism(st, (0, 6, -7), (0, 15, -2), 0.71, 4, BRACE, rot=math.pi/4)             # 前斜撐
        wh = wheel(780, -1, 1, 3, 8, HUB_NOSE)
        wheels = [((-3, -13, 5), wh), ((3, -13, 5), wh)]
        split = ((16384, 0, 0), (0, 0, 0))
        groups = (sf2 + sf, bf)
    return st, groups, wheels, split


def part_block(side, at):
    """在 CODE 位置 at 組出這個起落架的新零件位元組碼；回傳 (bytes, 輪子 C4 位置列表)"""
    st, (g_strut, g_brace), wheels, (n, d) = build(side)
    wh = wheels[0][1]
    out = bytearray(st.bytes())
    # 先算各段長度
    strut_b = st.faces_bytes(set(g_strut)) + b'\x1e'
    brace_b = st.faces_bytes(set(g_brace)) + b'\x1e'
    wheel_b = wh.bytes() + wh.faces_bytes() + b'\x1e'
    c4s = []
    if side in 'LR':
        # 根 → node(支柱側?: A = 輪子 C4, B = 支柱組)；支柱組 = node(眼睛在前?: A = 支柱, B = 斜撐)
        N1 = at + len(out); WC = N1 + 18 + 2; SG = WC + 16 + 1; S = SG + 18 + 2; B = S + len(strut_b); WP = B + len(brace_b)
        out += node(N1, n, d, WC, SG)
        out += c4(WC, wheels[0][0], WP) + b'\x1e'; c4s.append(WC)
        out += node(SG, (0, 0, 16384), (0, 0, -3), S, B)
        out += strut_b + brace_b + wheel_b
    else:
        # node1(x≥0: A = 左輪, B = REST)；REST = node2(x≥0: A = 支柱組, B = 右輪)；支柱組 = node3(前?: A = 支柱+輪軸, B = 斜撐)
        N1 = at + len(out); WL = N1 + 20; N2 = WL + 17; WR = N2 + 20; SG = WR + 17; S = SG + 20; B = S + len(strut_b); WP = B + len(brace_b)
        out += node(N1, n, d, WL, N2)
        out += c4(WL, wheels[0][0], WP) + b'\x1e'; c4s.append(WL)
        out += node(N2, n, d, SG, WR)
        out += c4(WR, wheels[1][0], WP) + b'\x1e'; c4s.append(WR)
        out += node(SG, (0, 0, 16384), (0, 0, -8), S, B)
        out += strut_b + brace_b + wheel_b
    assert at + len(out) == WP + len(wheel_b)
    return bytes(out), c4s


def spin_x86(Lpos, tbl, pitch_fields):
    st = "\n".join(f"mov word ptr [ebx + {f - Lpos}], ax" for f in pitch_fields)
    return f"""
        pushfd
        pushad
        call next
    next:
        pop ebx
        movzx ecx, word ptr [0x580bec]
        mov esi, dword ptr [ecx*4 + 0x553848]
        mov ebp, dword ptr [esi + 0x34]
        sar ebp, 8
        jns pos
        neg ebp
    pos:
        cmp ebp, {VMAX}
        jbe slow
        xor ebp, ebp
    slow:
        mov edi, ecx
        and edi, 31
        lea edi, [ebx + edi*8 + {tbl - Lpos}]
        call dword ptr [0x593758]
        cmp word ptr [edi], cx
        je same
        mov word ptr [edi], cx
        mov dword ptr [edi + 4], eax
    same:
        mov edx, eax
        sub edx, dword ptr [edi + 4]
        mov dword ptr [edi + 4], eax
        cmp edx, 200
        jbe dtok
        xor edx, edx
    dtok:
        imul edx, ebp
        imul edx, edx, {round(65536 * REV_PER_S / VMAX / 1000 * 1024)}
        shr edx, 10
        mov ax, word ptr [edi + 2]
        sub ax, dx
        mov word ptr [edi + 2], ax
        {st}
        popad
        popfd
    """


def main():
    src, psrc, dst, pdst = sys.argv[1:5]
    pb = bytearray(open(psrc, 'rb').read()); P = read_pic(pb)
    draw_hub(pb, P, HUB_MAIN, 147, 152)
    draw_hub(pb, P, HUB_NOSE, 144, 164)
    d = bytearray(open(src, 'rb').read())
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    if nxt - code['va'] - code['vs'] < 4096:
        from f18g_growler import grow_vas
        d = bytearray(grow_vas(d, 0x1000)); pe, opt, secs = pe_sections(d)
        code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    c = bytearray(d[code['ro']:code['ro']+code['vs']])
    for o in OLD.values(): assert c[o] == 0x82, hex(o)
    assert c[AB_F0:AB_F0+2] == b'\xf0\x00' and c[AB_F0 + 17] == 0x68 and c[AB_F0 + 22] == 0xC3
    thunk = struct.unpack_from('<I', c, AB_F0 + 18)[0]
    tail = bytes(c).find(SIG)
    blk = bytearray(); starts = {}; c4s = {}
    for side in 'LRN':
        starts[side] = tail + len(blk)
        b, w = part_block(side, tail + len(blk)); blk += b; c4s[side] = w
    while len(blk) % 4: blk += b'\x00'
    tbls = {}
    for side in 'LRN':
        tbls[side] = tail + len(blk); blk += bytes(32 * 8)
    room = nxt - code['va'] - len(c)
    if len(blk) > room: sys.exit(f'空間不夠：需要 {len(blk)}，只有 {room}')
    L = len(blk)
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    relocs = []
    for side, old in OLD.items():
        Lpos = old + 2 + 2 + 5
        body = bytes(ks.asm(spin_x86(Lpos, tbls[side], [a + 10 for a in c4s[side]]), 0)[0])
        assert body[2] == 0xE8
        pp = old + 2 + len(body)
        tr = b'\xf0\x00' + body + b'\x68' + struct.pack('<I', code['va'] + starts[side]) + b'\x68' + struct.pack('<I', thunk + L) + b'\xc3'
        n = struct.unpack_from('<H', c, old + 2)[0]
        assert len(tr) <= 6 + 6*n + 4*31, (side, len(tr))
        c[old:old + len(tr)] = tr
        relocs += [pp + 1 - tail, pp + 6 - tail]
    out = insert_blocks(d, pe, secs, code, c, tail, bytes(blk), extra_relocs=relocs)
    open(dst, 'wb').write(out); open(pdst, 'wb').write(pb)
    print(f'{dst}: 起落架 {len(blk)} 位元組（空間 {room}）在 CODE+{tail:#x}；零件 {[hex(v) for v in starts.values()]}；輪子 C4 {c4s}')


if __name__ == '__main__': main()
