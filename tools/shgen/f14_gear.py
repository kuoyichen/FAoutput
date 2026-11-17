#!/usr/bin/env python3
"""F-14 起落架重做（v2）：原本每個起落架是兩片交叉的貼圖，換成 3D 支柱、斜撐，輪子用貼圖平面，轉動靠改 UV。

  * 主起落架（左右各一，C4 在 (∓26, 上 1, 前 5)，收放 = 滾轉 gearPos/2）：方形支柱、減震套環、斜撐、單個大輪（半徑 5、寬 3）
  * 前起落架（C4 (0, 上 -6, 前 69)，收放 = 俯仰 gearPos/2）：支柱、輪軸、斜撐、兩個小輪（半徑 3、寬 2）
  * 輪子（都在起落架零件裡，不再用子零件 C4）：
      - 兩側：一片平面（主輪八角形、前輪正方形），貼圓形輪框貼圖，圓外是透明色 0xFF。
        轉動 = 每次畫之前改寫這片的 UV，讓貼圖繞輪心轉（5 個孔，所以只要 1/5 圈的 16 格 UV 表）
      - 正面／背面：輪軸平面上一片直立的倒角長方形（胎寬 × 直徑），貼胎紋。轉動 = UV 的 V 往下（背面往上）捲，4 格
      - 一圈 80 步；UV 表事先算好放在新區塊，x86 依角度把對應的那一格複製到面的 UV 位元組
  * 貼圖畫在舊起落架貼圖的位置（_F14.PIC，舊交叉面拿掉後沒人用）：
      輪框：u134-170、v155-229（主輪中心 (152,173) 半徑 16 格，前輪中心 (152,211) 半徑 11 格）
      胎紋：u225-251、v53-127（舊主輪正面貼圖）
  * 舊零件開頭換成 F0 跳板：呼叫新區塊裡的轉動程式，再跳到新零件（同 sh_ab_flame.py）
      物件 = [0x553848 + word[0x580BEC]*4]，速度 = dword [物件+0x34]（呎/秒 ×256）
      速度 0 或超過 190 節（320 呎/秒）：不轉；之間：轉速和速度成正比，190 節時每秒 2 圈
      每架飛機一格（32 格，以物件編號 & 31 選，存編號、角度、上次時間），角度 += 轉速 × 經過時間（timeGetTime）
  * 頂點編號 594 起（三個起落架共用，畫完一個才載入下一個）。v1 用到 700 以上時右輪和前輪不見，
    原版 SH 沒有一個用到 640 以上，所以不再用高編號
  * 畫面順序用 06 平面測試（眼睛在支柱那一側就先畫輪子再畫支柱），輪子兩側的面靠背面剔除
用法：python3 f14_gear.py SH/F14.SH PIC/_F14.PIC 輸出.SH 輸出.PIC
"""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, insert_blocks
from f14_nose import face_bytes

SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])
AB_F0 = 0x395C                     # 後燃器 F0（拿它的 push do_start_interp）
OLD = {'L': 0x4499, 'R': 0x43D8, 'N': 0x4670}
FLAT, TEX = 0x661, 0x75C           # 平面色面；貼圖面（色號 0、u8 UV、0xFF 透明）
STRUT, BRACE = 146, 148
BASE = 594                         # 頂點編號起點
# 輪框貼圖：中心 (u, v)、半徑（格）
HUB_MAIN, HUB_NOSE = (152, 173, 16), (152, 211, 11)
HUB_AREA = (134, 155, 170, 229)
# 胎紋：左上 (u, v)、寬、高（不含捲動的一個週期）
TREAD_MAIN, TREAD_NOSE = (227, 56, 8, 20), (240, 56, 6, 12)
TREAD_AREA = (225, 53, 251, 127)
PERIOD = 4                         # 胎紋週期（格）
STEPS = 80                         # 一圈幾步
DISC_N = 16                        # 輪框：1/5 圈 = 16 步
REV_PER_S = 2
VMAX = 320


class Part:
    def __init__(s, base): s.base, s.V, s.F = base, [], []
    def v(s, p):
        p = tuple(int(round(c)) for c in p)
        s.V.append(p); return len(s.V) - 1
    def face(s, idx, col, inside, fl=FLAT, uvf=None):
        """inside：形狀內部的一點，用來決定面朝外。uvf(頂點座標, 步) → (u, v)，有的話是貼圖面"""
        P = [s.V[i] for i in idx]
        n = [0, 0, 0]
        for k in range(len(P)):
            p, q = P[k], P[(k+1) % len(P)]
            n[0] += p[1]*q[2]-p[2]*q[1]; n[1] += p[2]*q[0]-p[0]*q[2]; n[2] += p[0]*q[1]-p[1]*q[0]
        cen = [sum(p[k] for p in P) / len(P) for k in range(3)]
        out = [cen[k] - inside[k] for k in range(3)]
        if sum(n[k]*out[k] for k in range(3)) > 0:     # FA 的面 ΣP×P 要朝內
            idx = idx[::-1]
        s.F.append((fl, col, list(idx), uvf))
        return len(s.F) - 1
    def uv(s, k, step):
        fl, col, idx, uvf = s.F[k]
        return [uvf(s.V[i], step) for i in idx]
    def bytes(s):
        b = bytearray(struct.pack('<BBHH', 0x82, 0, len(s.V), s.base * 8))
        for p in s.V: b += struct.pack('<hhh', *p)
        return b
    def group(s, sel):
        """面的位元組 + 1E；回傳 (bytes, {面: UV 在 bytes 裡的位置})"""
        b = bytearray(); pos = {}
        for k in sel:
            fl, col, idx, uvf = s.F[k]
            fb = face_bytes(fl, col, [s.base + i for i in idx], [s.V[i] for i in idx], s.uv(k, 0) if uvf else None)
            if uvf: pos[k] = len(b) + len(fb) - 2 * len(idx)
            b += fb
        return bytes(b + b'\x1e'), pos


def prism(part, a, b, r, n, col, rot=0.0, caps=(True, True)):
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


def wheel(p, ctr, x0, x1, r, hub, tread):
    """在零件 p 裡加一個輪子（軸沿 x，中心 ctr=(·, y, z)）。回傳 (面列表, [(面, 步數)])"""
    _, cy, cz = ctr; hu, hv, hc = hub
    # 兩側：主輪八角形（外切圓），前輪正方形
    if r >= 4: m, R0, a0 = 8, r / math.cos(math.pi / 8), math.pi / 8
    else:      m, R0, a0 = 4, r * math.sqrt(2), math.pi / 4
    def disc_uv(P, step):
        th = 2 * math.pi * step / STEPS
        dy, dz = (P[1] - cy) / r, (P[2] - cz) / r          # 材料座標 = 位置轉 +θ（往前滾，上面往前）
        my, mz = dy*math.cos(th) - dz*math.sin(th), dy*math.sin(th) + dz*math.cos(th)
        return (max(0, min(255, round(hu + hc*my))), max(0, min(255, round(hv - hc*mz))))
    mid = ((x0+x1)/2, cy, cz)
    faces, anim = [], []
    # 胎面：輪軸平面上的倒角長方形，正面（朝前）和背面各一片
    tu, tv, tw, th_ = tread
    if r >= 4: prof = [(0, r-1), (1, r), (-1, r), (0, r-1)]     # (離邊 x, 高)：左下角開始的倒角
    else:      prof = None
    if prof:
        Q = [(x0, cz+r-1), (x0+1, cz+r), (x1-1, cz+r), (x1, cz+r-1), (x1, cz-r+1), (x1-1, cz-r), (x0+1, cz-r), (x0, cz-r+1)]
    else:
        xc = (x0+x1)/2
        Q = [(x0, cz+r-1), (xc, cz+r), (x1, cz+r-1), (x1, cz-r+1), (xc, cz-r), (x0, cz-r+1)]
    for side in (1, -1):
        def tr_uv(P, step, side=side):
            s = (-step * side) % PERIOD                      # 正面：胎面往下走；背面：往上走
            u = tu + (P[0] - x0) / (x1 - x0) * (tw - 1)
            v = tv + s + (cz + r - P[2]) / (2*r) * (th_ - 1)
            return (round(u), round(v))
        idx = [p.v((x, cy, z)) for x, z in Q]
        k = p.face(idx, 0, (mid[0], cy - side, cz), TEX, tr_uv); faces.append(k); anim.append((k, PERIOD))
    for xs in (x0, x1):
        idx = [p.v((xs, cy + R0*math.cos(a0 + 2*math.pi*i/m), cz + R0*math.sin(a0 + 2*math.pi*i/m))) for i in range(m)]
        k = p.face(idx, 0, mid, TEX, disc_uv); faces.append(k); anim.append((k, DISC_N))
    return faces, anim


def read_pic(b):
    w, h = struct.unpack_from('<II', b, 2); rt = struct.unpack_from('<I', b, 0x22)[0]
    return w, h, [struct.unpack_from('<I', b, rt + 4*r)[0] for r in range(h)]


def put(b, P, u, v, k):
    w, h, rows = P; b[rows[h-1-v] + u] = k


def draw_textures(pb, P):
    for area in (HUB_AREA, TREAD_AREA):
        for v in range(area[1], area[3] + 1):
            for u in range(area[0], area[2] + 1): put(pb, P, u, v, 255)
    for (hu, hv, hc), rim, cap in ((HUB_MAIN, 147, 152), (HUB_NOSE, 144, 164)):
        R = int(hc) + 1
        for y in range(-R, R + 1):
            for x in range(-R, R + 1):
                dx, dy = x / hc, y / hc; d = math.hypot(dx, dy); a = math.atan2(dy, dx)
                if d > 1.0: continue
                elif d > 0.90: k = 158
                elif d > 0.68: k = 159 if (int((a + math.pi) / (2*math.pi) * 24) % 2 or d < 0.86) else 157
                elif d > 0.62: k = 152
                elif d < 0.16: k = cap
                elif d < 0.22: k = 154
                else:
                    k = rim
                    for h in range(5):
                        ha = 2*math.pi*h/5
                        if math.hypot(dx - 0.42*math.cos(ha), dy - 0.42*math.sin(ha)) < 0.12: k = 157
                put(pb, P, hu + x, hv + y, k)
    for tu, tv, tw, th_ in (TREAD_MAIN, TREAD_NOSE):
        for y in range(th_ + PERIOD):
            for x in range(tw):
                edge = x == 0 or x == tw - 1
                groove = tw >= 8 and x in (2, tw - 3) or tw < 8 and x == tw // 2
                k = 156 if edge else 159 if groove else 158
                if y % PERIOD == 0 and not edge: k = 155            # 一圈圈的磨痕，捲動時看得出在轉
                put(pb, P, tu + x, tv + y, k)


def node(at, n, d, a, b):
    return struct.pack('<BB6h', 0x06, 0, n[0], d[0], n[1], d[1], n[2], d[2]) + struct.pack('<hh', a - (at+16), b - (at+18)) + b'\x00\x00'


def build(side):
    st = Part(BASE); anim = []
    if side in 'LR':
        sx = 1 if side == 'L' else -1                     # L：支柱在 +x，輪子在外側
        g_s = prism(st, (3*sx, 1, 1), (3*sx, 1, -19), 1.42, 4, STRUT, rot=math.pi/4)
        g_s += prism(st, (3*sx, 1, -6), (3*sx, 1, -9), 1.9, 4, BRACE, rot=math.pi/4)
        g_s += prism(st, (3*sx, 1, -19), (1*sx, 1, -19), 0.71, 4, BRACE, rot=math.pi/4)    # 輪軸
        g_b = prism(st, (3*sx, 1, -11), (6*sx, 8, 0), 0.75, 4, BRACE, rot=math.pi/4)
        x0, x1 = (-2, 1) if sx > 0 else (-1, 2)
        w, a = wheel(st, (0, 1, -19), x0, x1, 5, HUB_MAIN, TREAD_MAIN); anim += a
        wheels = [w]
        split = ((16384*sx, 0, 0), (-1*sx, 0, 0))         # 眼睛在支柱那一側 → 先畫輪子
        fwd = (0, 0, -3)
    else:
        g_s = prism(st, (-3, 5, -13), (3, 5, -13), 0.71, 4, BRACE, rot=math.pi/4)   # 輪軸
        g_s += prism(st, (0, 7, -1), (0, 5, -13), 1.0, 4, STRUT)
        g_b = prism(st, (0, 6, -7), (0, 15, -2), 0.71, 4, BRACE, rot=math.pi/4)
        wheels = []
        for cx in (-3, 3):
            w, a = wheel(st, (cx, 5, -13), cx-1, cx+1, 3, HUB_NOSE, TREAD_NOSE); anim += a; wheels.append(w)
        split = ((16384, 0, 0), (0, 0, 0))
        fwd = (0, 0, -8)
    return st, g_s, g_b, wheels, split, fwd, anim


def part_block(side, at):
    """回傳 (bytes, {面: UV 在 CODE 的位置}, 零件)"""
    st, g_s, g_b, wheels, (n, d), fwd, anim = build(side)
    out = bytearray(st.bytes())
    S, ps = st.group(g_s); B, pb_ = st.group(g_b)
    W = [st.group(w) for w in wheels]
    uvpos = {}
    if side in 'LR':
        N1 = at + len(out); SG = N1 + 20; s = SG + 20; b = s + len(S); w = b + len(B)
        out += node(N1, n, d, w, SG) + node(SG, (0, 0, 16384), fwd, s, b) + S + B + W[0][0]
        uvpos.update({k: w + o for k, o in W[0][1].items()})
    else:
        N1 = at + len(out); N2 = N1 + 20; SG = N2 + 20; s = SG + 20; b = s + len(S); wl = b + len(B); wr = wl + len(W[0][0])
        out += node(N1, n, d, wl, N2) + node(N2, n, d, SG, wr) + node(SG, (0, 0, 16384), fwd, s, b) + S + B + W[0][0] + W[1][0]
        uvpos.update({k: wl + o for k, o in W[0][1].items()}); uvpos.update({k: wr + o for k, o in W[1][1].items()})
    return bytes(out), uvpos, st, anim


def spin_routine(R, state, patches):
    """新區塊裡的程式（位置 R）：更新角度，把 UV 表複製到面。patches = [(uv 位置, 表位置, 步數, 位元組)]"""
    cp = ""
    for uv, tbl, n, nb in patches:
        cp += f"""
        mov edx, eax
        and edx, {n - 1}
        imul edx, edx, {nb}
        lea esi, [ebx + edx + {tbl - (R + 6)}]
        lea edi, [ebx + {uv - (R + 6)}]
        mov ecx, {nb}
        rep movsb"""
    return f"""
        cld
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
        lea edi, [ebx + edi*8 + {state - (R + 6)}]
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
        add ax, dx
        mov word ptr [edi + 2], ax
        movzx eax, ax
        imul eax, eax, {STEPS}
        shr eax, 16
        {cp}
        ret
    """


def main():
    src, psrc, dst, pdst = sys.argv[1:5]
    pb = bytearray(open(psrc, 'rb').read()); P = read_pic(pb)
    draw_textures(pb, P)
    d = bytearray(open(src, 'rb').read())
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    if nxt - code['va'] - code['vs'] < 8192:
        from f18g_growler import grow_vas
        d = bytearray(grow_vas(d, 0x2000)); pe, opt, secs = pe_sections(d)
        code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    c = bytearray(d[code['ro']:code['ro']+code['vs']])
    for o in OLD.values(): assert c[o] == 0x82, hex(o)
    assert c[AB_F0:AB_F0+2] == b'\xf0\x00' and c[AB_F0 + 17] == 0x68 and c[AB_F0 + 22] == 0xC3
    thunk = struct.unpack_from('<I', c, AB_F0 + 18)[0]
    tail = bytes(c).find(SIG)
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    blk = bytearray(); starts = {}; info = {}
    for side in 'LRN':
        starts[side] = tail + len(blk)
        b, uvpos, st, anim = part_block(side, tail + len(blk)); blk += b; info[side] = (uvpos, st, anim)
    while len(blk) % 4: blk += b'\x00'
    patches = {}
    for side in 'LRN':
        uvpos, st, anim = info[side]; patches[side] = []
        for k, n in anim:
            t = tail + len(blk)
            for step in range(n): blk += b''.join(bytes(x) for x in st.uv(k, step))
            patches[side].append((uvpos[k], t, n, 2 * len(st.F[k][2])))
        while len(blk) % 4: blk += b'\x00'
    states = {}
    for side in 'LRN':
        states[side] = tail + len(blk); blk += bytes(32 * 8)
    routs = {}
    for side in 'LRN':
        R = tail + len(blk)
        code_b = bytes(ks.asm(spin_routine(R, states[side], patches[side]), 0)[0])
        assert code_b[1] == 0xE8 and len(code_b) > 6
        routs[side] = R; blk += code_b
    room = nxt - code['va'] - len(c)
    if len(blk) > room: sys.exit(f'空間不夠：需要 {len(blk)}，只有 {room}')
    L = len(blk)
    relocs = []
    for side, old in OLD.items():
        nx = old + 2 + 2 + 5                                 # F0 00 pushfd pushad call → next
        body = bytes(ks.asm(f"""
            pushfd
            pushad
            call next
        next:
            pop ebx
            add ebx, {routs[side] - nx}
            call ebx
            popad
            popfd
        """, 0)[0])
        pp = old + 2 + len(body)
        tr = b'\xf0\x00' + body + b'\x68' + struct.pack('<I', code['va'] + starts[side]) + b'\x68' + struct.pack('<I', thunk + L) + b'\xc3'
        n = struct.unpack_from('<H', c, old + 2)[0]
        assert len(tr) <= 6 + 6*n, (side, len(tr))
        c[old:old + len(tr)] = tr
        relocs += [pp + 1 - tail, pp + 6 - tail]
    out = insert_blocks(d, pe, secs, code, c, tail, bytes(blk), extra_relocs=relocs)
    open(dst, 'wb').write(out); open(pdst, 'wb').write(pb)
    print(f'{dst}: 起落架 {len(blk)} 位元組（空間 {room}）在 CODE+{tail:#x}；零件 {[hex(v) for v in starts.values()]}；轉動程式 {[hex(v) for v in routs.values()]}')
    return dict(tail=tail, starts=starts, routs=routs, states=states, patches=patches, info=info, va=code['va'])


if __name__ == '__main__': main()
