#!/usr/bin/env python3
"""KC-130 空中加油（Kuoyi 2026-11-23）：以 AN12A.SH（FA 的 C-130 外形）為原型做 KC130.SH。
兩翼下各加一個加油莢艙，莢艙尾端拉出軟管，管端是羽毛球狀的錐套（drogue）。
玩家接近加油機後下方時兩條軟管同時放出；錐套自動追蹤玩家的受油探管（不用精準對位），
一次只會接上一側（玩家在哪一側就用哪一側），接上後持續加油，加滿時顯示訊息。全部在 SH 裡完成。

原檔結構（SH/AN12A.SH，shift 9，1 單位 = 2 ft）：
  * CODE 0x5C 的 F0：mov byte [0x5CCC],0; push 0x1070; push thunk; ret（每次畫這架飛機最先執行）。
    0x66 的重定位 dword（push 的回到位址）改成指向新區塊的 F0，新 x86 跑完再回到 0x70。
  * 主 LOD 的 BSP 根節點在 0xA42（06），A 分支 0xA57。A 分支改成先經過新的「上下」節點：
    眼睛在機翼下方 → 先畫整架飛機再畫莢艙與軟管；在上方 → 先畫莢艙與軟管再畫飛機（機翼蓋住）。
  * 機翼是單層面 up 6；外側發動機 x ≈ 51，翼尖 x 99。莢艙放在 x ±75。
  * F2 碰撞表在 CODE 0x4C97：半徑 50688（198 ft）；玩家在附近時暫時改成 10 ft（同 KC-135）。
用法：python3 kc130_refuel.py AN12A.SH KC130.SH [預覽.SH]
"""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, insert_blocks
from kc135_refuel import Mesh, node, check_relocs, F_LIT, F_GLOW
from keystone import Ks, KS_ARCH_X86, KS_MODE_32

SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])
F0_PUSH = 0x66              # F0 0x5C 裡 push 0x1070 的重定位 dword
THUNK_DW = 0x6B             # push thunk 的重定位 dword（載入器換成 do_start_interp 的位址）
RESUME = 0x70               # 原本 F0 之後回到的位置
ROOT = 0xA42                # 主 BSP 根節點（06）
F2TBL = 0x4C97
BOUND_R = 340                       # 包圍球：樞紐 (75,−12) 到最長管端 300 單位 ≈ 322，加墜錐
HDR = bytes.fromhex('3c016000f900')   # C4 零件範圍標頭 = CODE+8..13
# 軟管零件的範圍標頭：C4（0x4D3194）用 |眼睛| + 範圍 決定精度位移，軟管長到 400+ 單位，範圍要涵蓋（否則 16 位元溢位）
HOSE_HDR = struct.pack('<3h', 340, 340, 340)

U = 2.0                      # ft / 頂點單位
PODX, POD_UP = 75, 1         # 莢艙中心（x 為右側；左側鏡像）
POD_NOSE, POD_F1, POD_F2, POD_F3, POD_TAIL = 8, 6, 3, -9, -12
PIV = (PODX, POD_UP, POD_TAIL)                  # 軟管出口（樞紐）
WING_UP = 6
BIG = [(3, 0), (2, 2), (0, 3), (-2, 2), (-3, 0), (-2, -2), (0, -3), (2, -2)]
SMALL = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
HOSE = [(0, 0), (1, 0), (1, 1), (0, 1)]          # 1×1 單位方管（Kuoyi 2026-11-23：再細一些）
C_POD, C_NOSE, C_PYLON, C_DARK = 153, 150, 154, 158
C_HOSE, C_CONE_OUT, C_CONE_IN, C_RIM, C_GREEN = 157, 147, 145, 158, 165
F_LITW, F_GLOWW = 0x0461, 0x0441     # 平面點用 i16（錐套離樞紐超過 127 單位）；GLOW 不打光
HUB_D, RIM_D, BAND_D = 1, 6, 7                  # 錐套各環在管尖後的距離（單位）

PROBE_UP, PROBE_FWD = 0.0, 85.0                 # 接觸點 = 玩家機頭：fwd 由玩家 SH 的 F2 碰撞盒前緣（typedef+0xF → CODE）讀，讀不到才用 85 ft
APP_BACK, APP_SIDE, APP_DOWN, APP_UP = 3000, 1000, 1200, 200   # 放出軟管的接近區（ft，相對加油機中心）
NEAR_L = 660                 # 探管離樞紐比這近：該側錐套追蹤探管
L_MIN, L_MAX = 24, 600       # 接上：長度（ft）
P_MIN, P_MAX = -5, 50        # 接上：俯角（度）
YAW_LIM, HDG_LIM, SPD_LIM = 35, 20, 60
TRAIL_P, TRAIL_LEN, STOW_LEN = 8, 180, 1       # 拖曳：下垂 8°、長 180 單位（360 ft，Kuoyi：4 倍會亂晃，改原本的 3 倍）；收起 1 單位
H_MIN, H_MAX = 1, 300        # 軟管長度範圍（單位）
HOSE_RATE = 80               # 軟管每秒 80 單位（160 ft/s）
STEP = 24                    # 每 1/256 s 轉 24 單位 ≈ 34°/s
RATE = 50                    # lb/s
ORIG_R, SMALL_R = 50688, 10 * 256
NEAR_BOX = 3000
DEG = 65536 / 360.0
MSG = b' Plane Re-Fueled\0'
MSG_START = b' Start Refueling\0'
POD_SLOT, HOSE_SLOT, HOSE_N = 300, 400, 64      # 每條軟管 64 點（方管 SEG+1 環 + 錐套 24 點）
SEG = 8                                          # 軟管段數
SAG_A = math.tan(math.radians(TRAIL_P))             # 管尖斜率（相對弦線）= tan(拖曳俯角)：拖曳時錐套前那段水平（Kuoyi 2026-11-23）
SAG_B = 0.38                                     # 靠莢艙那段多垂一些：中點下垂 ≈ L/12


def sag_g(k):
    """第 k 環往弦線下方的偏移 / L，×256：a·t(1−t) + b·t(1−t)²（t=1 時斜率 −a，即管尖水平）。"""
    t = k / SEG
    return int(round((SAG_A * t * (1 - t) + SAG_B * t * (1 - t) ** 2) * 256))
F_NONRM = 0x0401                                 # 無法向量的面


def newell(P):
    n = [0.0, 0.0, 0.0]
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2]); n[1] += (a[2] - b[2]) * (a[0] + b[0]); n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


def face_out(m, idx, centre, col, flags=F_LIT, inward=False, point=None):
    """面法向量取幾何法向，朝外（離 centre）；inward 時朝內。Mesh.face 會照法向量排頂點順序。"""
    P = [m.v[i - m.slot] for i in idx]
    n = newell(P)
    if not any(n):
        return b''
    g = [sum(p[t] for p in P) / len(P) for t in range(3)]
    s = sum((g[t] - centre[t]) * n[t] for t in range(3))
    if (s < 0) != inward: n = [-k for k in n]
    return m.face(idx, n, point or P[0], col, flags)


def ring(m, prof, x0, u0, f, sx=1):
    return [m.vert(x0 + sx * x, u0 + u, f) for x, u in prof]


def band(m, r0, r1, centre_fn, col, inward=False):
    out = []
    for i in range(len(r0)):
        j = (i + 1) % len(r0)
        q = [r0[i], r0[j], r1[j], r1[i]]
        P = [m.v[k - m.slot] for k in q]
        f = sum(p[2] for p in P) / 4
        out.append(face_out(m, q, centre_fn(f), col, inward=inward))
    return out


def pod_faces(m, sx):
    """一側莢艙（凸的旋轉體）＋派龍架。回傳 (pod bytes, pylon bytes)。"""
    X = sx * PODX
    ax = lambda f: (X, POD_UP, f)
    nose = m.vert(X, POD_UP, POD_NOSE)
    r1 = ring(m, SMALL, X, POD_UP, POD_F1, sx); r2 = ring(m, BIG, X, POD_UP, POD_F2, sx)
    r3 = ring(m, BIG, X, POD_UP, POD_F3, sx); r4 = ring(m, SMALL, X, POD_UP, POD_TAIL, sx)
    pod = bytearray(); fl = []                       # fl = (面位移, 原色)：加油時整個莢艙變綠
    def add(f, col):
        if f: fl.append((len(pod), col))
        pod.extend(f)
    for i in range(8):
        add(face_out(m, [nose, r1[i], r1[(i + 1) % 8]], ax(POD_F1), C_NOSE), C_NOSE)
    for f in band(m, r1, r2, ax, C_NOSE): add(f, C_NOSE)
    for f in band(m, r2, r3, ax, C_POD) + band(m, r3, r4, ax, C_POD): add(f, C_POD)
    pod += m.face(r4, (0, 0, -1), m.v[r4[0] - m.slot], C_DARK)
    # 派龍架：x 從 75 到 76（左側 −76..−75），底 up 4 fwd −6..2，頂 up 6 fwd −8..1
    x0, x1 = (PODX, PODX + 1) if sx > 0 else (-PODX - 1, -PODX)
    bot, top = POD_UP + 3, WING_UP
    q = {}
    for xx in (x0, x1):
        q[xx] = [m.vert(xx, bot, -6), m.vert(xx, bot, 2), m.vert(xx, top, 1), m.vert(xx, top, -8)]
    c = ((x0 + x1) / 2, (bot + top) / 2, -3)
    py = bytearray()
    py += face_out(m, q[x0], c, C_PYLON) + face_out(m, q[x1], c, C_PYLON)
    py += face_out(m, [q[x0][1], q[x1][1], q[x1][2], q[x0][2]], c, C_PYLON)
    py += face_out(m, [q[x0][3], q[x1][3], q[x1][0], q[x0][0]], c, C_PYLON)
    return pod, py, fl


def widen(f, flags):
    """FC 面（0x200：i8 平面點）改成 i16 平面點的格式（旗標去掉 0x200）。"""
    pt = struct.unpack('<3b', f[11:14])
    return bytes(f[:1]) + struct.pack('<H', flags) + bytes(f[3:11]) + struct.pack('<3h', *pt) + bytes(f[14:])


def hose_part(slot):
    """軟管零件（零件座標：樞紐為原點，軟管朝 −fwd）。回傳 bytes 與 x86 要改的位移。
    管尖、錐套的頂點 fwd = −L + off；錐套面的平面點 fwd（i16）同樣；節點 d = L。
    檔案裡先放 TB 長度的樣子（x86 每格都會重寫）。"""
    TB = 20
    m = Mesh(slot)
    root = [m.vert(x, u, 0) for x, u in HOSE]
    mids = [[m.vert(x, u, -TB * k // SEG) for x, u in HOSE] for k in range(1, SEG)]
    tip = [m.vert(x, u, -TB) for x, u in HOSE]
    hub = [m.vert(x, u, -TB - HUB_D) for x, u in SMALL]
    rim = [m.vert(x, u, -TB - RIM_D) for x, u in BIG]
    rim2 = [m.vert(x, u, -TB - BAND_D) for x, u in BIG]
    ax = lambda f: (0, 0, f)
    # 軟管分 SEG 段，x86 每格把中間各環往下壓成垂掛曲線（Kuoyi 2026-11-23）。
    # 左右兩面（x 固定）法向量一直有效，打光；上下兩面會傾斜，不放法向量（0x401：單色、不剔除、不打光）。
    tube = bytearray(); rings = [root] + mids + [tip]
    for a, b in zip(rings, rings[1:]):
        for i, f in enumerate(band(m, a, b, lambda f: (0.5, 0.5, f), C_HOSE)):
            if i in (0, 2):                          # 下、上
                f = bytearray(f); f = f[:1] + struct.pack('<HH', F_NONRM, C_HOSE) + f[14:]
            else:                                    # 平面點用根部頂點（x 不變，fwd 0 也在平面上）
                f = bytearray(f); f[12:14] = struct.pack('<2b', 0, 0)
            tube += f
    # 錐套：輪轂蓋（朝後）、內錐面、外緣帶、外錐面、輪轂前面（軟管接頭）
    dro = [('hub', m.face(hub[::-1], (0, 0, -1), m.v[hub[0] - slot], C_RIM))]
    dro += [('in', f) for f in band(m, hub, rim, ax, C_CONE_IN, inward=True)]
    dro += [('rim', f) for f in band(m, rim, rim2, ax, C_RIM)]
    dro += [('out', f) for f in band(m, hub, rim, ax, C_CONE_OUT)]
    dro.append(('hubf', m.face(hub, (0, 0, 1), m.v[hub[0] - slot], C_RIM)))
    part = bytearray(HOSE_HDR); p82 = len(part); part += m.buf()
    nd = len(part); part += bytes(14); part += b'\x1E'
    o_dro = len(part); pts = []; inner = []
    for kind, f in dro:
        w = widen(f, F_LITW)
        pts.append((len(part) + 15, struct.unpack_from('<h', w, 15)[0] + TB))   # 平面點 fwd word 位移、相對管尖
        if kind == 'in': inner.append(len(part))
        part += w
    part += b'\x1E'
    o_tube = len(part); part += tube + b'\x1E'
    # 根節點：fwd 平面在管尖（−L）：eye_fwd + L ≥ 0（眼睛在管尖前方）→ 先畫錐套再畫軟管
    part[nd:nd + 14] = node(0x0C, 0, 0, 1, TB, o_dro - nd, o_tube - nd)
    mid = []                                         # (fwd word 位移, up word 位移, 第 k 環, 原 up)
    for k, rr in enumerate(mids, 1):
        for v in rr: mid.append((p82 + m.voff(v) + 2, p82 + m.voff(v) + 4, k, m.v[v - slot][1]))
    verts = []
    for k in tip + hub + rim + rim2:
        verts.append((p82 + m.voff(k) + 2, m.v[k - slot][2] + TB))     # (fwd word 位移, 相對管尖)
    return dict(b=part, p82=p82, verts=verts, mid=mid, pts=pts, inner=inner, nd_d=nd + 8, n=len(m.v))


def make_block():
    """區塊：兩個軟管零件、包裝節點（上下）、莢艙群組。回傳 bytes 與各位移（相對區塊起點）。"""
    blk = bytearray()
    H = {}
    for side, slot in (('R', HOSE_SLOT), ('L', HOSE_SLOT + HOSE_N)):
        hp = hose_part(slot); o = len(blk); blk += hp['b']
        H[side] = dict(hp, o=o)
    m = Mesh(POD_SLOT)
    pods = {s: pod_faces(m, sx) for s, sx in (('L', -1), ('R', 1))}
    podf = {}
    W = len(blk); blk += bytes(14) + b'\x1E'
    o_main = len(blk); blk += b'\x38\x00\x00'                  # → 0xA57（插入後再填）
    o_grp = len(blk); blk += m.buf(); g0 = len(blk); blk += bytes(14) + b'\x1E'
    side_at, c4_at = {}, {}
    for s in ('L', 'R'):
        sn = len(blk); blk += bytes(14) + b'\x1E'
        c4 = len(blk); blk += b'\xC4\x00' + bytes(14) + b'\x1E'
        sx = 1 if s == 'R' else -1
        struct.pack_into('<3h', blk, c4 + 2, sx * PIV[0], PIV[1], PIV[2])
        struct.pack_into('<h', blk, c4 + 14, H[s]['o'] + H[s]['p82'] - (c4 + 16))
        pn = len(blk); blk += bytes(14) + b'\x1E'
        o_pod = len(blk); blk += pods[s][0] + b'\x1E'
        podf[s] = [(o_pod + fo, col) for fo, col in pods[s][2]]
        o_py = len(blk); blk += pods[s][1] + b'\x1E'
        # 莢艙頂 up 4：眼睛在上面 → 先莢艙後派龍架
        blk[pn:pn + 14] = node(0x0C, 1, -(POD_UP + 3), 0, 0, o_pod - pn, o_py - pn)
        # 莢艙尾 fwd −12：眼睛在前面 → 先軟管再莢艙
        blk[sn:sn + 14] = node(0x0C, 0, 0, 1, -POD_TAIL, c4 - sn, pn - sn)
        side_at[s], c4_at[s] = sn, c4
    # x 平面：眼睛在右（x ≥ 0）→ 先左再右
    blk[g0:g0 + 14] = node(0x0E, 1, 0, 0, 0, side_at['L'] - g0, side_at['R'] - g0)
    # 上下：n_up = −1, d = −5：眼睛 up ≤ 5 → 先畫飛機再畫莢艙
    blk[W:W + 14] = node(0x0C, -1, -5, 0, 0, o_main - W, o_grp - W)
    assert POD_SLOT + len(m.v) <= HOSE_SLOT and H['R']['n'] <= HOSE_N and HOSE_SLOT + HOSE_N + H['L']['n'] <= 900
    return dict(blk=blk, W=W, o_main=o_main, H=H, c4=c4_at, podf=podf)


def build(src, dst, preview=None, show=None):
    d = bytearray(open(src, 'rb').read())
    from f18g_growler import grow_vas
    d = bytearray(grow_vas(d, 0x3000))      # 莢艙綠色切換的程式變大：0x2000 不夠（VA 會蓋到 .idata）
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE')
    c = bytearray(d[code['ro']:code['ro'] + code['vs']])
    tail = c.find(SIG); assert tail > 0
    assert c[0x5C:0x60] == bytes.fromhex('f000c605') and c[0x65] == 0x68 and c[0x6A] == 0x68 and c[0x6F] == 0xC3
    assert struct.unpack_from('<I', c, F0_PUSH)[0] == 0x1000 + RESUME
    assert c[ROOT] == 0x06 and ROOT + 16 + struct.unpack_from('<h', c, ROOT + 14)[0] == 0xA57
    assert struct.unpack_from('<i', c, F2TBL)[0] == ORIG_R and tail == F2TBL + 18
    # 貼圖名稱 _an12a.PIC → _kc130.PIC（同長度）
    k = 0
    while True:
        k = c.find(b'_an12a.PIC', k)
        if k < 0: break
        c[k:k + 10] = b'_kc130.PIC'; k += 10

    G = make_block(); blk = bytearray(G['blk'])
    struct.pack_into('<h', blk, G['o_main'] + 1, 0xA57 - (tail + G['o_main'] + 3))
    while len(blk) % 4: blk += b'\0'
    D = {}
    def var(name, size, init=b''):
        D[name] = len(blk); blk.extend((init + b'\0' * size)[:size])
    fl = lambda v: struct.pack('<f', v)
    var('SLOTS', 8 * 64)
    for k in ('DT', 'TMP', 'DX', 'DY', 'DZ', 'COS', 'SIN', 'RIGHT', 'FWD', 'RS', 'BACK', 'DOWN', 'L', 'PITCH', 'YAW',
              'RI', 'FI', 'UI', 'SIDE', 'APPR', 'CONT', 'NEARR', 'TP', 'TH', 'TE', 'TPR', 'THR', 'TER', 'TPL', 'THL', 'TEL'):
        var(k, 4)
    var('K256', 4, fl(1 / 256)); var('KANG', 4, fl(2 * math.pi / 65536)); var('KFA', 4, fl(65536 / (2 * math.pi)))
    var('PF', 4, fl(PROBE_FWD - PIV[2] * U)); var('PIVF', 4, fl(PIV[2] * U)); var('NOSE', 4); var('PU', 4, fl(PROBE_UP - PIV[1] * U)); var('PX', 4, fl(PIV[0] * U))
    var('ENTRY', 8); var('MSGTXT', len(MSG), MSG); var('MSGSTART', len(MSG_START), MSG_START)
    while len(blk) % 16: blk += b'\x90'
    o_f0 = len(blk); blk += b'\xF0\x00'
    # 網頁檢視器跟著 F0 的第一個 push 走：放一個不會執行的 push 0x1070（回到 0x70）
    blk += b'\xEB\x05\x68' + struct.pack('<I', 0x1000 + RESUME)
    o_code = len(blk)

    def asm(base_off):
        r = lambda name: D[name] - base_off
        s = lambda off: off - base_off
        def geo(side, sl):
            h = G['H'][side]; o = h['o']
            a = [f"            mov eax, dword ptr [ebp + {sl}]", "            sar eax, 8",
                 f"            mov word ptr [ebx + {s(o + h['nd_d'])}], ax", "            neg eax"]
            for vo, off in h['verts']:
                a += [f"            lea ecx, [eax + {off}]", f"            mov word ptr [ebx + {s(o + vo)}], cx"]
            for po, off in h['pts']:
                a += [f"            lea ecx, [eax + {off}]", f"            mov word ptr [ebx + {s(o + po)}], cx"]
            a += ["            neg eax"]           # eax = L（正）
            for fo, uo, k, u0 in h['mid']:
                g = sag_g(k)
                a += [f"            imul ecx, eax, {k}", f"            sar ecx, {SEG.bit_length() - 1}", "            neg ecx",
                      f"            mov word ptr [ebx + {s(o + fo)}], cx",
                      f"            imul ecx, eax, {g}", "            sar ecx, 8", "            neg ecx", f"            add ecx, {u0}",
                      f"            mov word ptr [ebx + {s(o + uo)}], cx"]
            return "\n".join(a)
        def cone(side, sgn):
            # 接上加油時，該側莢艙整個變綠（不打光），從受油機看得到（Kuoyi 2026-11-23）
            lab = 'cn' + side; F = G['podf'][side]
            a = [f"            cmp dword ptr [ebx + {r('CONT')}], 0", f"            je {lab}n",
                 f"            cmp dword ptr [ebx + {r('SIDE')}], {sgn}", f"            jne {lab}n"]
            for fo, col in F:
                a += [f"            mov word ptr [ebx + {s(fo + 1)}], {F_GLOW}", f"            mov byte ptr [ebx + {s(fo + 3)}], {C_GREEN}"]
            a += [f"            jmp {lab}d", f"        {lab}n:"]
            for fo, col in F:
                a += [f"            mov word ptr [ebx + {s(fo + 1)}], {F_LIT}", f"            mov byte ptr [ebx + {s(fo + 3)}], {col}"]
            a += [f"        {lab}d:"]
            return "\n".join(a)
        def anim(side, base):
            c4 = G['c4'][side]; t = 'R' if side == 'R' else 'L'
            return f"""
            mov edx, dword ptr [ebx + {r('DT')}]
            imul edx, edx, {STEP}
            movsx eax, word ptr [ebp + {base}]
            mov ecx, dword ptr [ebx + {r('TP' + t)}]
            call approach
            mov word ptr [ebp + {base}], ax
            mov word ptr [ebx + {s(c4 + 10)}], ax
            movsx eax, word ptr [ebp + {base + 2}]
            mov ecx, dword ptr [ebx + {r('TH' + t)}]
            call approach
            mov word ptr [ebp + {base + 2}], ax
            mov word ptr [ebx + {s(c4 + 8)}], ax
            mov edx, dword ptr [ebx + {r('DT')}]
            imul edx, edx, {HOSE_RATE}
            mov eax, dword ptr [ebp + {base + 4}]
            mov ecx, dword ptr [ebx + {r('TE' + t)}]
            call approach
            mov dword ptr [ebp + {base + 4}], eax
{geo(side, base + 4)}
"""
        src = f"""
            sub esp, 8
            pushfd
            pushad
            call base
        base:
            pop ebx
            xor eax, eax
            mov dword ptr [ebx + {r('SIDE')}], eax
            mov dword ptr [ebx + {r('APPR')}], eax
            mov dword ptr [ebx + {r('CONT')}], eax
            mov dword ptr [ebx + {r('NEARR')}], eax
            mov dword ptr [ebx + {r('TPR')}], eax
            mov dword ptr [ebx + {r('THR')}], eax
            mov dword ptr [ebx + {r('TPL')}], eax
            mov dword ptr [ebx + {r('THL')}], eax
            mov dword ptr [ebx + {r('TER')}], {STOW_LEN * 256}
            mov dword ptr [ebx + {r('TEL')}], {STOW_LEN * 256}
            movzx eax, word ptr [0x580bec]
            test eax, eax
            jz noslot
            cmp ax, word ptr [0x553838]
            jae noslot
            mov esi, dword ptr [eax*4 + 0x553848]
            test esi, esi
            jz noslot
            cmp byte ptr [esi], 4
            jne noslot
            mov ecx, eax
            and ecx, 7
            shl ecx, 6
            lea ebp, [ebx + ecx + {r('SLOTS')}]
            inc eax
            mov edx, dword ptr [0x552928]
            cmp word ptr [ebp], ax
            je haveslot
            mov word ptr [ebp], ax
            mov dword ptr [ebp + 4], edx
            mov dword ptr [ebp + 8], 0
            mov dword ptr [ebp + 12], 0x70000000
            mov dword ptr [ebp + 16], 0
            mov dword ptr [ebp + 20], 0
            mov dword ptr [ebp + 24], 0
            mov dword ptr [ebp + 28], 0
        haveslot:
            mov eax, edx
            sub edx, dword ptr [ebp + 4]
            mov dword ptr [ebp + 4], eax
            cmp edx, 256
            jbe dtok
            xor edx, edx
        dtok:
            mov dword ptr [ebx + {r('DT')}], edx

            movzx eax, word ptr [0x520a1c]
            test eax, eax
            jz animate
            cmp ax, word ptr [0x553838]
            jae animate
            mov edi, dword ptr [eax*4 + 0x553848]
            test edi, edi
            jz animate
            cmp edi, esi
            je animate
            cmp byte ptr [edi], 4
            jne animate
            test byte ptr [edi + 1], 1
            jz animate
            cmp word ptr [edi + 0xe], 0
            je animate
            mov al, byte ptr [edi + 9]
            xor al, byte ptr [esi + 9]
            test al, 0x80
            jnz animate

            fild dword ptr [edi + 0x11]
            fild dword ptr [esi + 0x11]
            fsubp st(1), st(0)
            fmul dword ptr [ebx + {r('K256')}]
            fstp dword ptr [ebx + {r('DX')}]
            fild dword ptr [edi + 0x15]
            fild dword ptr [esi + 0x15]
            fsubp st(1), st(0)
            fmul dword ptr [ebx + {r('K256')}]
            fstp dword ptr [ebx + {r('DY')}]
            fild dword ptr [edi + 0x19]
            fild dword ptr [esi + 0x19]
            fsubp st(1), st(0)
            fmul dword ptr [ebx + {r('K256')}]
            fstp dword ptr [ebx + {r('DZ')}]
            movzx eax, word ptr [esi + 0x1d]
            mov dword ptr [ebx + {r('TMP')}], eax
            fild dword ptr [ebx + {r('TMP')}]
            fmul dword ptr [ebx + {r('KANG')}]
            fsincos
            fstp dword ptr [ebx + {r('COS')}]
            fstp dword ptr [ebx + {r('SIN')}]
            fld dword ptr [ebx + {r('DX')}]
            fmul dword ptr [ebx + {r('COS')}]
            fld dword ptr [ebx + {r('DZ')}]
            fmul dword ptr [ebx + {r('SIN')}]
            fsubp st(1), st(0)
            fst dword ptr [ebx + {r('RIGHT')}]
            fistp dword ptr [ebx + {r('RI')}]
            fld dword ptr [ebx + {r('DX')}]
            fmul dword ptr [ebx + {r('SIN')}]
            fld dword ptr [ebx + {r('DZ')}]
            fmul dword ptr [ebx + {r('COS')}]
            faddp st(1), st(0)
            fst dword ptr [ebx + {r('FWD')}]
            fistp dword ptr [ebx + {r('FI')}]
            fld dword ptr [ebx + {r('DY')}]
            fistp dword ptr [ebx + {r('UI')}]

            mov eax, dword ptr [ebx + {r('FI')}]
            add eax, {NEAR_BOX}
            cmp eax, {2 * NEAR_BOX}
            ja nb
            mov eax, dword ptr [ebx + {r('RI')}]
            add eax, {NEAR_BOX}
            cmp eax, {2 * NEAR_BOX}
            ja nb
            mov eax, dword ptr [ebx + {r('UI')}]
            add eax, {NEAR_BOX}
            cmp eax, {2 * NEAR_BOX}
            ja nb
            mov dword ptr [ebx + {r('NEARR')}], 1
        nb:
            mov eax, dword ptr [ebx + {r('FI')}]
            cmp eax, 0
            jg animate
            cmp eax, {-APP_BACK}
            jl animate
            mov eax, dword ptr [ebx + {r('RI')}]
            cmp eax, {-APP_SIDE}
            jl animate
            cmp eax, {APP_SIDE}
            jg animate
            mov eax, dword ptr [ebx + {r('UI')}]
            cmp eax, {-APP_DOWN}
            jl animate
            cmp eax, {APP_UP}
            jg animate
            mov dword ptr [ebx + {r('APPR')}], 1
            mov eax, {int(TRAIL_P * DEG)}
            mov dword ptr [ebx + {r('TPR')}], eax
            mov dword ptr [ebx + {r('TPL')}], eax
            mov eax, {TRAIL_LEN * 256}
            mov dword ptr [ebx + {r('TER')}], eax
            mov dword ptr [ebx + {r('TEL')}], eax

            mov ecx, {int(PROBE_FWD)}
            mov eax, dword ptr [edi + 5]
            test eax, eax
            jz nosedef
            mov eax, dword ptr [eax + 0xf]
            test eax, eax
            jz nosedef
            cmp word ptr [eax + 0xe], 0xf2
            jne nosedef
            movzx edx, word ptr [eax + 0x10]
            movsx edx, word ptr [eax + edx + 0x12 + 14]
            cmp edx, 10
            jl nosedef
            cmp edx, 400
            jg nosedef
            mov ecx, edx
        nosedef:
            mov dword ptr [ebx + {r('NOSE')}], ecx
            fild dword ptr [ebx + {r('NOSE')}]
            fsub dword ptr [ebx + {r('PIVF')}]
            fstp dword ptr [ebx + {r('PF')}]
            mov dword ptr [ebx + {r('SIDE')}], 1
            fld dword ptr [ebx + {r('RIGHT')}]
            cmp dword ptr [ebx + {r('RI')}], 0
            jl leftside
            fsub dword ptr [ebx + {r('PX')}]
            jmp sidedone
        leftside:
            mov dword ptr [ebx + {r('SIDE')}], -1
            fadd dword ptr [ebx + {r('PX')}]
        sidedone:
            fstp dword ptr [ebx + {r('RS')}]
            fld dword ptr [ebx + {r('FWD')}]
            fadd dword ptr [ebx + {r('PF')}]
            fchs
            fstp dword ptr [ebx + {r('BACK')}]
            fld dword ptr [ebx + {r('DY')}]
            fadd dword ptr [ebx + {r('PU')}]
            fchs
            fstp dword ptr [ebx + {r('DOWN')}]
            fld dword ptr [ebx + {r('DOWN')}]
            fld dword ptr [ebx + {r('BACK')}]
            fpatan
            fmul dword ptr [ebx + {r('KFA')}]
            fistp dword ptr [ebx + {r('PITCH')}]
            fld dword ptr [ebx + {r('RS')}]
            fld dword ptr [ebx + {r('BACK')}]
            fpatan
            fmul dword ptr [ebx + {r('KFA')}]
            fistp dword ptr [ebx + {r('YAW')}]
            fld dword ptr [ebx + {r('RS')}]
            fmul st(0), st(0)
            fld dword ptr [ebx + {r('DOWN')}]
            fmul st(0), st(0)
            faddp st(1), st(0)
            fld dword ptr [ebx + {r('BACK')}]
            fmul st(0), st(0)
            faddp st(1), st(0)
            fsqrt
            fistp dword ptr [ebx + {r('L')}]
            fld dword ptr [ebx + {r('BACK')}]
            fistp dword ptr [ebx + {r('BACK')}]

            mov eax, dword ptr [ebx + {r('L')}]
            cmp eax, {NEAR_L}
            jg animate
            cmp dword ptr [ebx + {r('BACK')}], 0
            jle animate
            mov eax, dword ptr [ebx + {r('PITCH')}]
            cmp eax, {int(P_MIN * DEG)}
            jge p1
            mov eax, {int(P_MIN * DEG)}
        p1:
            cmp eax, {int(P_MAX * DEG)}
            jle p2
            mov eax, {int(P_MAX * DEG)}
        p2:
            mov dword ptr [ebx + {r('TP')}], eax
            mov eax, dword ptr [ebx + {r('YAW')}]
            neg eax
            cmp eax, {int(-YAW_LIM * DEG)}
            jge y1
            mov eax, {int(-YAW_LIM * DEG)}
        y1:
            cmp eax, {int(YAW_LIM * DEG)}
            jle y2
            mov eax, {int(YAW_LIM * DEG)}
        y2:
            mov dword ptr [ebx + {r('TH')}], eax
            mov eax, dword ptr [ebx + {r('L')}]
            sub eax, {2 * HUB_D}
            shl eax, 7
            cmp eax, {H_MIN * 256}
            jge e1
            mov eax, {H_MIN * 256}
        e1:
            cmp eax, {H_MAX * 256}
            jle e2
            mov eax, {H_MAX * 256}
        e2:
            mov dword ptr [ebx + {r('TE')}], eax
            mov ecx, dword ptr [ebx + {r('TP')}]
            mov edx, dword ptr [ebx + {r('TH')}]
            cmp dword ptr [ebx + {r('SIDE')}], 0
            jl trkl
            mov dword ptr [ebx + {r('TPR')}], ecx
            mov dword ptr [ebx + {r('THR')}], edx
            mov dword ptr [ebx + {r('TER')}], eax
            jmp trkd
        trkl:
            mov dword ptr [ebx + {r('TPL')}], ecx
            mov dword ptr [ebx + {r('THL')}], edx
            mov dword ptr [ebx + {r('TEL')}], eax
        trkd:

            mov eax, dword ptr [ebx + {r('L')}]
            cmp eax, {L_MIN}
            jl animate
            cmp eax, {L_MAX}
            jg animate
            mov eax, dword ptr [ebx + {r('PITCH')}]
            cmp eax, {int(P_MIN * DEG)}
            jl animate
            cmp eax, {int(P_MAX * DEG)}
            jg animate
            mov eax, dword ptr [ebx + {r('YAW')}]
            cmp eax, {int(-YAW_LIM * DEG)}
            jl animate
            cmp eax, {int(YAW_LIM * DEG)}
            jg animate
            mov ax, word ptr [edi + 0x1d]
            sub ax, word ptr [esi + 0x1d]
            cwde
            cmp eax, {int(-HDG_LIM * DEG)}
            jl animate
            cmp eax, {int(HDG_LIM * DEG)}
            jg animate
            mov eax, dword ptr [edi + 0x34]
            sub eax, dword ptr [esi + 0x34]
            cmp eax, {-SPD_LIM * 256}
            jl animate
            cmp eax, {SPD_LIM * 256}
            jg animate
            mov dword ptr [ebx + {r('CONT')}], 1

            mov eax, dword ptr [edi + 5]
            mov ecx, dword ptr [eax + 0x165]
            shl ecx, 8
            mov eax, dword ptr [edi + 0x1fc]
            cmp eax, ecx
            jge animate
            cmp word ptr [ebp + 14], 256
            jb nostart
            push eax
            push ecx
            lea eax, [ebx + {r('MSGSTART')}]
            call sendmsg
            pop ecx
            pop eax
        nostart:
            mov word ptr [ebp + 14], 0
            mov edx, dword ptr [ebx + {r('DT')}]
            imul edx, edx, {RATE}
            add eax, edx
            cmp eax, ecx
            jl notfull
            mov dword ptr [edi + 0x1fc], ecx
            lea eax, [ebx + {r('MSGTXT')}]
            call sendmsg
            jmp animate
        notfull:
            mov dword ptr [edi + 0x1fc], eax

        animate:
            cmp dword ptr [ebx + {r('CONT')}], 0
            jne inbox
            movzx eax, word ptr [ebp + 14]
            add eax, dword ptr [ebx + {r('DT')}]
            cmp eax, 30000
            jbe ob1
            mov eax, 30000
        ob1:
            mov word ptr [ebp + 14], ax
        inbox:
{anim('R', 16)}
{anim('L', 24)}
{cone('R', 1)}
{cone('L', -1)}
            mov eax, {ORIG_R}
            cmp dword ptr [ebx + {r('NEARR')}], 0
            je setr
            mov eax, {SMALL_R}
        setr:
            mov dword ptr [ebx + {s(-1)}], eax
            jmp done

        noslot:
            mov dword ptr [ebx + {s(-1)}], {ORIG_R}
        done:
            mov eax, dword ptr [ebx + {s(-2)}]
            mov dword ptr [esp + 36], eax
            lea eax, [ebx + {s(-3)}]
            mov dword ptr [esp + 40], eax
            popad
            popfd
            ret

        sendmsg:
            push eax
            mov eax, 0x48d410
            call eax
            pop eax
            lea ecx, [ebx + {r('ENTRY')}]
            mov dword ptr [ecx], eax
            mov dword ptr [ecx + 4], 0
            mov eax, 0x48d420
            call eax
            movzx ecx, word ptr [0x580bec]
            movzx edx, word ptr [0x520a1c]
            mov eax, 0x48e950
            call eax
            ret

        approach:
            mov edi, ecx
            sub edi, eax
            cmp edi, edx
            jle a1
            mov edi, edx
        a1:
            neg edx
            cmp edi, edx
            jge a2
            mov edi, edx
        a2:
            neg edx
            add eax, edi
            ret
        """
        return src

    ks = Ks(KS_ARCH_X86, KS_MODE_32)
    base_off = o_code + 3 + 1 + 1 + 5          # sub esp,8 / pushfd / pushad / call
    for _ in range(3):
        src = asm(base_off)
        for fake, real in ((-1, F2TBL), (-2, THUNK_DW), (-3, RESUME)):
            src = src.replace(f'[ebx + {fake - base_off}]', f'[ebx + {real - (tail + base_off)}]')
        enc, _ = ks.asm(src, 0)
        code_bytes = bytes(enc)
        if code_bytes[:5] == b'\x83\xec\x08\x9c\x60' and code_bytes[5] == 0xE8: break
    blk += code_bytes

    # 物件包圍球半徑 CODE+4（頂點單位）：FA 0x4d028c 用它判斷要不要做近平面裁切（整球在視錐內 → 不裁切的快速路徑）。
    # 原本 158 只包住機身；軟管伸到 300 單位，球太小時管端跑到鏡頭後面也不裁切 → 一筆劃過畫面。
    assert struct.unpack_from('<h', c, 4)[0] == 158
    struct.pack_into('<h', c, 4, BOUND_R)
    # 根節點 A → 包裝節點
    struct.pack_into('<h', c, ROOT + 14, tail + G['W'] - (ROOT + 16))
    check_relocs(d, pe, code, c)
    out = bytearray(insert_blocks(d, pe, secs, code, c, tail, bytes(blk)))
    pe3, o3, s3 = pe_sections(out); cd3 = next(x for x in s3 if x['name'] == 'CODE')
    assert struct.unpack_from('<I', out, cd3['ro'] + F0_PUSH)[0] == 0x1000 + RESUME
    struct.pack_into('<I', out, cd3['ro'] + F0_PUSH, 0x1000 + tail + o_f0)
    assert len(out) < 65536, len(out)
    so = sorted(s3, key=lambda x: x['va'])
    for a, b in zip(so, so[1:]): assert a['va'] + a['vs'] <= b['va'], f"{a['name']} VA 重疊 {b['name']}"
    open(dst, 'wb').write(out)
    info = dict(tail=tail, o_f0=o_f0, o_code=o_code, blk_len=len(blk), size=len(out), D=D, G=G)
    if preview:
        # 預覽：軟管放出（show = (長度單位, 俯角, 偏角) 給兩側），x86 不跑（F0 直接 push 0x1070 的網頁路徑相同）
        d2 = bytearray(out); b = cd3['ro'] + tail
        Ln, pt, yw = show or (TRAIL_LEN, TRAIL_P, 0)
        for sd in ('R', 'L'):
            h = G['H'][sd]; o = h['o']
            struct.pack_into('<h', d2, b + o + h['nd_d'], Ln)
            for vo, off in h['verts']: struct.pack_into('<h', d2, b + o + vo, -Ln + off)
            for po, off in h['pts']: struct.pack_into('<h', d2, b + o + po, -Ln + off)
            for fo, uo, k, u0 in h['mid']:
                t = k / SEG; struct.pack_into('<h', d2, b + o + fo, -(Ln * k >> 3))
                struct.pack_into('<h', d2, b + o + uo, u0 - (Ln * sag_g(k) >> 8))
            struct.pack_into('<h', d2, b + G['c4'][sd] + 10, int(pt * DEG))
            struct.pack_into('<h', d2, b + G['c4'][sd] + 8, int(yw * DEG))
        open(preview, 'wb').write(d2)
    return info


if __name__ == '__main__':
    a = sys.argv[1:]
    i = build(a[0], a[1], a[2] if len(a) > 2 else None)
    print({k: v for k, v in i.items() if k not in ('D', 'G')})
