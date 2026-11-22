#!/usr/bin/env python3
"""KC-135 空中加油（Kuoyi 2026-11-22）：KC135.SH 裡加 x86，玩家飛到加油機後下方時，硬桿放下並指向玩家，
對準後持續加油，加滿時顯示訊息。全部在 SH 裡完成，不改 FA.EXE。

原檔結構（SH/KC135.SH）：
  * 硬桿是一段獨立的面（CODE 0x44F2，29 點、24 面，模型座標，機尾下方 fwd −63..−143、up −2），
    由 CODE 0x3714 的 F0 判斷 `_PLafterBurner == 1` 時才在 0x372B 呼叫畫出。
  * F2 碰撞表在 CODE 0x73E4：半徑 72704（284 ft）。FA 讓移動物件用「自己的 F2 半徑 / 2」掃過去
    （0x463378），目標若是人類玩家就算撞（0x42CA66），玩家的碰撞盒還會再加大這個半徑（0x42D0FB）。
    玩家撞向友軍 AI 不算撞（0x42CA8F），所以會撞的是加油機掃到玩家。

改法：
  1. 硬桿複製一份做成 C4 零件（頂點與平面點減去樞紐 (0, up −2, fwd −63)），法向量不用改：
     C4（0x4D3194）會把眼睛和光源一起轉進零件座標，旋轉後光影和背面剔除照樣正確。
  2. 0x3714 的 F0 改成跳到新的 x86（舊的兩個重定位位置 0x3718、0x3721 留著不執行）。x86 每次畫加油機時：
       - 找出加油機（[0x553848 + word[0x580BEC]*4]）和玩家（word[0x520A1C]）。
       - 玩家同陣營、存活時，把「玩家受油口」= 玩家位置 + (0, +RECEP_UP, +RECEP_FWD) 換到加油機座標
         （只用加油機航向；右 = dx cos h − dz sin h，前 = dx sin h + dz cos h），再算相對硬桿樞紐的
         後方距離、下方距離、左右、長度、俯角、偏角（x87 fpatan / fsqrt）。
       - 接近區（後方 0..APP_BACK、左右 ±APP_SIDE、下方 −60..APP_DOWN）：硬桿放下指向玩家（俯角 10..45°、
         偏角 ±20°，每秒 20° 平滑移動），並把 F2 半徑暫時改成 SMALL_R（離開就改回原值）。
       - 接上：長度 L_MIN..L_MAX、俯角 15..45°、偏角 ±15°、航向差 ±10°、速度差 ±30 ft/s。
         接上時玩家內油（obj+0x1FC，lb×256）每秒加 RATE lb，到 PT 內油上限（typedef+0x165）為止；
         剛好加滿時送出訊息 " Plane Re-Fueled"（FA 0x48D410 / 0x48D420 / 0x48E950，和 0x48E920 一樣的流程）。
       - 硬桿一律畫出（不再看後燃器）；沒有玩家在附近時收回到原本的水平位置。
用法：python3 kc135_refuel.py 輸入KC135.SH 輸出.SH [預覽.SH]
"""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, insert_blocks
from keystone import Ks, KS_ARCH_X86, KS_MODE_32

SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])
F0_HOOK = 0x3714            # F0 00 + cmp [_PLafterBurner],1 ...
RESUME = 0x373C             # 原本兩條路最後都回到這裡
BOOM = 0x44F2               # 硬桿 82 緩衝區
BOOM_END = 0x485A           # 下一個零件（襟翼）開始
F2TBL = 0x73E4
AB_PTR = 0x3719             # cmp word ptr [_PLafterBurner],1 的位址運算元（重定位）
CALL_AT = 0x372B            # 原本 12 00 c3 0d（呼叫硬桿）的位置


def reloc_sites(d, pe, code):
    """CODE 內所有 HIGHLOW 重定位位置（CODE 位移）。"""
    rva, rsz = struct.unpack_from('<II', d, pe + 24 + 96 + 8 * 5)
    _, _, secs = pe_sections(d)
    rs = next(s for s in secs if s['va'] <= rva < s['va'] + s['vs'])
    p = rs['ro'] + rva - rs['va']; end = p + rsz; out = []
    while p < end:
        pg, sz = struct.unpack_from('<II', d, p)
        if not pg or sz < 8: break
        for k in range((sz - 8) // 2):
            e = struct.unpack_from('<H', d, p + 8 + 2 * k)[0]
            if e >> 12 == 3: out.append(pg + (e & 0xFFF) - code['va'])
        p += sz
    return out


def check_relocs(d, pe, code, c):
    """改過的位元組不可碰到任何重定位 dword（否則 FA 載入器解析出非法位址而當機）。"""
    orig = d[code['ro']:code['ro'] + code['vs']]
    for site in reloc_sites(d, pe, code):
        assert c[site:site + 4] == orig[site:site + 4] or site >= len(orig), f'patch overwrote reloc at CODE+{site:#x}'
PIVOT = (0, -2, -63)        # (x, up, fwd) 頂點單位（1 單位 = 2 ft）
HDR = bytes.fromhex('eb0047001a01')   # 零件範圍標頭，照起落架零件抄

U = 2.0                      # ft / 頂點單位
HINGE_UP, HINGE_FWD = PIVOT[1] * U, PIVOT[2] * U          # −4, −126 ft
RECEP_UP, RECEP_FWD = 20.0, 50.0                          # 玩家受油口相對玩家原點（ft）
APP_BACK, APP_SIDE, APP_DOWN = 1500, 500, 800             # 接近區（ft）
L_MIN, L_MAX = 104, 148                                   # 上半桿 100 ft + 伸縮管 0..48 ft
NEAR_L = 210                                               # 比這遠：硬桿停在拖曳位置（TRAIL_*）
TRAIL_PITCH, TRAIL_EXT = 30, 8                             # 拖曳位置：放下 30°、伸縮管伸出 8 單位
P_MIN, P_MAX = 20, 40                                      # 對準時俯角範圍（實機約 20..40°）
TELE_RATE = 10                                             # 伸縮管每 1/256 s 動 10/256 單位（≈ 20 ft/s）
RATE = 50                                                  # lb/s（3000 lb/min）
ORIG_R, SMALL_R = 72704, 40 * 256
DEG = 65536 / 360.0
STEP = 14                                                  # 每 1/256 s 轉 14 單位 ≈ 20°/s
MSG = b' Plane Re-Fueled\0'


# ---- 新硬桿幾何（零件座標：樞紐為原點，x 右、up 上、fwd 前；硬桿朝 −fwd）----
UP_LEN = 50                  # 上半桿長（頂點單位，1 = 2 ft）
TELE_LEN = 24                # 下半伸縮管長，全伸出 24（約上半桿的一半）
TELE_STEP = 3                # 橘黑條紋每段 3
BOOM_SLOT = 600              # 硬桿頂點槽 600..（KC135 原本最多用到 590）
LIGHT_SLOT = 515             # 機腹燈頂點槽：用原本硬桿的 515..（原硬桿已不再畫）
C_BOOM, C_FIN, C_ORANGE, C_BLACK, C_GREEN = 156, 158, 162, 158, 165
F_LIT, F_GLOW = 0x0661, 0x0641  # 0x40 背面剔除 + 0x20 打光；0x641 不打光（燈）
BELLY_UP = -7                # 機腹平底 up −7（x ±2，fwd −16..67）
LIGHT_F = [30 + 5 * j for j in range(7)]   # 機腹燈 7 個，各 2×2
EYE_BELOW = BELLY_UP         # 眼睛低於機腹平面才在最後畫（燈、硬桿）
END_JMP = 0x146B             # 主 LOD 最外層 BSP 結束後的 38 → 0x42AD（1E）


class Mesh:
    def __init__(self, slot):
        self.slot, self.v, self.faces = slot, [], []

    def vert(self, x, u, f):
        self.v.append([x, u, f]); return self.slot + len(self.v) - 1

    def face(self, idx, normal, point, col, flags=F_LIT):
        n = [float(k) for k in normal]; L = math.sqrt(sum(k * k for k in n))
        # FA 用螢幕上的繞向剔除背面：(B−A)×(C−A)（x, up, fwd 座標）要和外法線同向，不然整面不畫
        P = [self.v[i - self.slot] for i in idx[:3]]
        e1 = [P[1][t] - P[0][t] for t in range(3)]; e2 = [P[2][t] - P[0][t] for t in range(3)]
        cr = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]]
        if sum(cr[t] * n[t] for t in range(3)) < 0: idx = list(idx)[::-1]
        n = [int(round(k / L * 32767)) for k in n]
        b = bytearray(b'\xFC') + struct.pack('<HH', flags, col) + struct.pack('<3h', *n)
        b += struct.pack('<3b', *[int(round(k)) for k in point]) + bytes([len(idx)])
        b += b''.join(struct.pack('<H', i) for i in idx)
        return b

    def buf(self):
        b = bytearray(b'\x82\x00') + struct.pack('<HH', len(self.v), self.slot * 8)
        for x, u, f in self.v: b += struct.pack('<3h', x, f, u)          # 82 存 (x, fwd, up)
        return b

    def voff(self, i):          # 第 i 個（槽號）頂點在 buf() 裡的位移
        return 6 + 6 * (i - self.slot)


def prism_faces(m, rings, prof, cols, flags=None):
    """rings = 各環頂點槽號清單（同 prof 順序）；回傳每段每邊的面（bytes）清單 [seg][side]。"""
    out = []
    for a in range(len(rings) - 1):
        row = []
        for i in range(len(prof)):
            j = (i + 1) % len(prof)
            (x0, u0), (x1, u1) = prof[i], prof[j]
            nx, nu = (x0 + x1) / 2, (u0 + u1) / 2          # 正多邊形：中點方向就是外法線
            q = [rings[a][i], rings[a][j], rings[a + 1][j], rings[a + 1][i]]
            fa = m.v[rings[a][i] - m.slot][2]
            col = cols(a, i); fl = flags(a, i) if flags else F_LIT
            row.append(m.face(q, (nx, nu, 0), (x0, u0, fa), col, fl))
        out.append(row)
    return out


def node(op, n1, d1, n2, d2, A, B):
    """2D 平面節點（14 bytes）；A、B 是相對本節點起點的位移，值 ≥0 先畫 A 再畫 B。"""
    p = 0
    return bytearray(struct.pack('<BBhhhhhh', op, 0, n1, d1, n2, d2, A - (p + 12), B - (p + 14)))


def make_parts():
    """回傳 dict：blk（HDR+硬桿零件、機腹燈、尾端 C4、選擇跳躍、掛勾 C4）與各位移。"""
    m = Mesh(BOOM_SLOT)
    oc = [(1, 1), (1, -1), (-1, -1), (-1, 1)]       # 上半桿：方管 2×2（Kuoyi：原本八角太粗，縮一半）
    sq = [(0, 1), (1, 0), (0, -1), (-1, 0)]         # 伸縮管：菱形，比上半桿稍細
    # 上半桿：環 fwd +2, −36, −40, −50；−36..−40 下面三片是桿上燈
    tube_rings = [[m.vert(x, u, f) for x, u in oc] for f in (2, -36, -40, -UP_LEN)]
    LIGHT_SIDES = (0, 1, 2)          # 右側、底面、左側
    tube = prism_faces(m, tube_rings, oc, lambda a, i: C_BOOM)
    cap = m.face(tube_rings[3], (0, 0, -1), (0, 0, -UP_LEN), C_BOOM)
    # 飛翼（V 形，翼尖朝外上），兩面
    fins = []
    for sx in (-1, 1):
        q = [m.vert(1 * sx, 0, -41), m.vert(1 * sx, 0, -48), m.vert(7 * sx, 4, -48), m.vert(7 * sx, 4, -45)]
        P = [m.v[k - m.slot] for k in q]
        e1 = [P[1][t] - P[0][t] for t in range(3)]; e2 = [P[2][t] - P[0][t] for t in range(3)]
        n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]]
        if n[1] < 0: n = [-k for k in n]                     # 上面
        pt = P[0]
        fins.append(m.face(q, n, pt, C_FIN) + m.face(q[::-1], [-k for k in n], pt, C_FIN))
    # 伸縮管：環 k 在管尖後 3k（fwd 由 x86 每格寫），預設全伸出
    tip = -UP_LEN - TELE_LEN
    nr = TELE_LEN // TELE_STEP + 1
    tele_rings = [[m.vert(x, u, tip + TELE_STEP * k) for x, u in sq] for k in range(nr)]
    tele = prism_faces(m, tele_rings, sq, lambda a, i: C_BLACK if a % 2 == 0 else C_ORANGE)
    tcap = m.face(tele_rings[0], (0, 0, -1), (0, 0, tip), C_BLACK)
    assert BOOM_SLOT + len(m.v) <= 700, len(m.v)

    # ---- 零件位元組 ----
    part = bytearray(HDR); part82 = len(part); part += m.buf()
    # 根：fwd 平面 −UP_LEN（eye_fwd + UP_LEN ≥ 0：眼睛在桿端前方 → 先畫伸縮管再畫上半桿）
    root = len(part); part += bytes(14); part += b'\x1E'
    # 伸縮管
    o_tele = len(part)
    for row in tele[::-1]:                 # 管根先畫、管尖後畫，管尖蓋最後
        for f in row: part += f
    o_tcap = len(part); part += tcap
    part += b'\x1E'
    # 上半桿：x 平面兩層：Lfin / (tube / Rfin)
    o_up = len(part); part += bytes(14); part += b'\x1E'
    o_up2 = len(part); part += bytes(14); part += b'\x1E'
    o_lf = len(part); part += fins[0] + b'\x1E'
    o_rf = len(part); part += fins[1] + b'\x1E'
    o_tube = len(part); part += cap
    light_faces = []
    for a, row in enumerate(tube):
        for i, f in enumerate(row):
            if a == 1 and i in LIGHT_SIDES: light_faces.append(len(part))
            part += f
    part += b'\x1E'
    def put(at, op, n1, d1, n2, d2, A, B):
        part[at:at + 14] = node(op, n1, d1, n2, d2, A - at, B - at)
    put(root, 0x0C, 0, 0, 1, UP_LEN, o_tele, o_up)
    put(o_up, 0x0E, 1, 0, 0, 0, o_lf, o_up2)
    put(o_up2, 0x0E, 1, 0, 0, 0, o_tube, o_rf)
    tele_fwd = [[part82 + m.voff(k) + 2 for k in ring] for ring in tele_rings]   # (x, fwd, up) 的 fwd
    tele_v = [[(part82 + m.voff(k), m.v[k - m.slot][0], m.v[k - m.slot][1]) for k in ring] for ring in tele_rings]
    tcap_pt = o_tcap + 1 + 2 + 2 + 6 + 2                                         # 平面點 fwd（i8）

    # ---- 機腹燈 ----
    lm = Mesh(LIGHT_SLOT); lf = bytearray()
    for f in LIGHT_F:
        q = [lm.vert(-1, BELLY_UP, f), lm.vert(1, BELLY_UP, f), lm.vert(1, BELLY_UP, f + 2), lm.vert(-1, BELLY_UP, f + 2)]
        lf += lm.face(q, (0, -1, 0), (0, BELLY_UP, f), C_GREEN, F_GLOW)
    blk = bytearray(part)
    o_lights = len(blk); blk += lm.buf() + lf
    # 尾端硬桿（眼睛在機腹下方時，在整架飛機最後才畫）
    o_boom2 = len(blk); blk += b'\xC4\x00' + bytes(14) + b'\x1E'
    o_ret = len(blk); blk += b'\x1E'
    o_endsel = len(blk); blk += b'\x38\x00\x00'
    o_snip = len(blk); blk += b'\xC4\x00' + bytes(14) + b'\x38\x00\x00'
    for o in (o_boom2, o_snip):
        struct.pack_into('<3h', blk, o + 2, *PIVOT)
        struct.pack_into('<h', blk, o + 14, part82 - (o + 16))
    rel = lambda o_jmp, tgt: tgt - (o_jmp + 3)
    return dict(blk=blk, part82=part82, snip=o_snip, boom2=o_boom2, endsel=o_endsel,
                rel_ret=rel(o_endsel, o_ret), rel_boom2=rel(o_endsel, o_boom2), rel_lights=rel(o_endsel, o_lights),
                tele_fwd=tele_fwd, tele_v=tele_v, tcap_pt=tcap_pt, light_faces=light_faces, nverts=len(m.v))


def build(src, dst, preview=None, mode='full'):
    d = bytearray(open(src, 'rb').read())
    from f18g_growler import grow_vas
    d = bytearray(grow_vas(d, 0x1000))        # 新硬桿 + 程式約 4.3 KB：CODE 需超過 .idata 原本的 VA 0x9000
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE')
    c = bytearray(d[code['ro']:code['ro'] + code['vs']])
    tail = c.find(SIG); assert tail > 0
    assert c[F0_HOOK:F0_HOOK + 10] == bytes.fromhex('f000 66833d00840000 01'.replace(' ', ''))
    assert c[0x372B:0x372F] == bytes.fromhex('1200c30d')
    assert c[BOOM:BOOM + 2] == b'\x82\x00' and struct.unpack_from('<i', c, F2TBL)[0] == ORIG_R

    # ---- 1. 新硬桿（實機樣式）與機腹燈，見 make_parts() ----
    G = make_parts()
    blk = bytearray(G['blk'])
    o_part82, o_snip, o_boom2, o_endsel = G['part82'], G['snip'], G['boom2'], G['endsel']
    while len(blk) % 4: blk += b'\0'
    D = {}
    def var(name, size, init=b''):
        D[name] = len(blk); blk.extend((init + b'\0' * size)[:size])
    fl = lambda v: struct.pack('<f', v)
    var('SLOTS', 8 * 16)
    for k in ('DT', 'TMP', 'DX', 'DY', 'DZ', 'COS', 'SIN', 'RIGHT', 'BACK', 'DOWN', 'L', 'PITCH', 'YAW',
              'TP', 'TH', 'TE', 'EXT', 'APPR', 'CONT', 'SHOW'): var(k, 4)
    var('K256', 4, fl(1 / 256)); var('KANG', 4, fl(2 * math.pi / 65536)); var('KFA', 4, fl(65536 / (2 * math.pi)))
    var('CFWD', 4, fl(RECEP_FWD - HINGE_FWD)); var('CUP', 4, fl(RECEP_UP - HINGE_UP))
    var('ENTRY', 8); var('MSGTXT', len(MSG), MSG)
    while len(blk) % 16: blk += b'\x90'
    o_code = len(blk)

    def asm(base_off):
        r = lambda name: D[name] - base_off          # [ebx + r] = 變數
        s = lambda off: off - base_off
        # 伸縮管各環 fwd = min(−UP_LEN, 管尖 + 3k)，管尖 = −UP_LEN − EXT/256
        ta = [f"            mov eax, dword ptr [ebx + {r('EXT')}]", "            sar eax, 8", "            neg eax",
              f"            sub eax, {UP_LEN}", f"            mov byte ptr [ebx + {s(G['tcap_pt'])}], al"]
        # 環 k：v = 管尖 + 3k。v ≤ −UP_LEN 露在外面；前一環露在外面時夾在 −UP_LEN（全尺寸）；
        # 其餘藏在上半桿裡的環縮成中心一點（不留退化面的殘線）
        for k, ring in enumerate(G['tele_v']):
            ta += ["            mov ecx, eax", f"            add ecx, {TELE_STEP * k}", f"            cmp ecx, {-UP_LEN}",
                   f"            jle tx{k}", f"            cmp ecx, {-UP_LEN + TELE_STEP}", f"            jl tc{k}"]
            for o, x, u in ring:
                ta += [f"            mov word ptr [ebx + {s(o)}], 0", f"            mov word ptr [ebx + {s(o + 2)}], {-UP_LEN}",
                       f"            mov word ptr [ebx + {s(o + 4)}], 0"]
            ta += [f"            jmp tn{k}", f"        tc{k}:", f"            mov ecx, {-UP_LEN}", f"        tx{k}:"]
            for o, x, u in ring:
                ta += [f"            mov word ptr [ebx + {s(o)}], {x}", f"            mov word ptr [ebx + {s(o + 2)}], cx",
                       f"            mov word ptr [ebx + {s(o + 4)}], {u}"]
            ta += [f"        tn{k}:"]
        TELE_ASM = "\n".join(ta)
        LIGHT_ASM = "\n".join(f"            mov word ptr [ebx + {s(o + 1)}], ax\n            mov byte ptr [ebx + {s(o + 3)}], cl"
                               for o in G['light_faces'])
        src = f"""
            pushfd
            pushad
            call base
        base:
            pop ebx
            mov dword ptr [ebx + {r('TP')}], 0
            mov dword ptr [ebx + {r('TH')}], 0
            mov dword ptr [ebx + {r('APPR')}], 0
            mov dword ptr [ebx + {r('CONT')}], 0
            mov dword ptr [ebx + {r('SHOW')}], 0
            mov dword ptr [ebx + {r('TE')}], 0
            mov dword ptr [ebx + {r('EXT')}], 0
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
            shl ecx, 4
            lea ebp, [ebx + ecx + {r('SLOTS')}]
            inc eax
            mov edx, dword ptr [0x552928]
            cmp word ptr [ebp], ax
            je haveslot
            mov word ptr [ebp], ax
            mov dword ptr [ebp + 4], edx
            mov dword ptr [ebp + 8], 0
            mov dword ptr [ebp + 12], 0
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
            fstp dword ptr [ebx + {r('RIGHT')}]
            fld dword ptr [ebx + {r('DX')}]
            fmul dword ptr [ebx + {r('SIN')}]
            fld dword ptr [ebx + {r('DZ')}]
            fmul dword ptr [ebx + {r('COS')}]
            faddp st(1), st(0)
            fadd dword ptr [ebx + {r('CFWD')}]
            fchs
            fstp dword ptr [ebx + {r('BACK')}]
            fld dword ptr [ebx + {r('DY')}]
            fadd dword ptr [ebx + {r('CUP')}]
            fchs
            fstp dword ptr [ebx + {r('DOWN')}]

            fld dword ptr [ebx + {r('DOWN')}]
            fld dword ptr [ebx + {r('BACK')}]
            fpatan
            fmul dword ptr [ebx + {r('KFA')}]
            fistp dword ptr [ebx + {r('PITCH')}]
            fld dword ptr [ebx + {r('RIGHT')}]
            fld dword ptr [ebx + {r('BACK')}]
            fpatan
            fmul dword ptr [ebx + {r('KFA')}]
            fistp dword ptr [ebx + {r('YAW')}]
            fld dword ptr [ebx + {r('RIGHT')}]
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
            fld dword ptr [ebx + {r('DOWN')}]
            fistp dword ptr [ebx + {r('DOWN')}]
            fld dword ptr [ebx + {r('RIGHT')}]
            fistp dword ptr [ebx + {r('RIGHT')}]

            mov eax, dword ptr [ebx + {r('BACK')}]
            cmp eax, 0
            jle animate
            cmp eax, {APP_BACK}
            jg animate
            mov eax, dword ptr [ebx + {r('DOWN')}]
            cmp eax, -60
            jl animate
            cmp eax, {APP_DOWN}
            jg animate
            mov eax, dword ptr [ebx + {r('RIGHT')}]
            cmp eax, {-APP_SIDE}
            jl animate
            cmp eax, {APP_SIDE}
            jg animate
            mov dword ptr [ebx + {r('APPR')}], 1
            mov dword ptr [ebx + {r('TP')}], {int(TRAIL_PITCH * DEG)}
            mov dword ptr [ebx + {r('TE')}], {TRAIL_EXT * 256}
            mov eax, dword ptr [ebx + {r('L')}]
            cmp eax, {NEAR_L}
            jg animate
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
            cmp eax, {int(-15 * DEG)}
            jge y1
            mov eax, {int(-15 * DEG)}
        y1:
            cmp eax, {int(15 * DEG)}
            jle y2
            mov eax, {int(15 * DEG)}
        y2:
            mov dword ptr [ebx + {r('TH')}], eax
            mov eax, dword ptr [ebx + {r('L')}]
            sub eax, {UP_LEN * 2}
            jge e1
            xor eax, eax
        e1:
            cmp eax, {TELE_LEN * 2}
            jle e2
            mov eax, {TELE_LEN * 2}
        e2:
            shl eax, 7
            mov dword ptr [ebx + {r('TE')}], eax

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
            cmp eax, {int(-15 * DEG)}
            jl animate
            cmp eax, {int(15 * DEG)}
            jg animate
            mov ax, word ptr [edi + 0x1d]
            sub ax, word ptr [esi + 0x1d]
            cwde
            cmp eax, {int(-10 * DEG)}
            jl animate
            cmp eax, {int(10 * DEG)}
            jg animate
            mov eax, dword ptr [edi + 0x34]
            sub eax, dword ptr [esi + 0x34]
            cmp eax, {-30 * 256}
            jl animate
            cmp eax, {30 * 256}
            jg animate
            mov dword ptr [ebx + {r('CONT')}], 1

            mov eax, dword ptr [edi + 5]
            mov ecx, dword ptr [eax + 0x165]
            shl ecx, 8
            mov eax, dword ptr [edi + 0x1fc]
            cmp eax, ecx
            jge animate
            mov edx, dword ptr [ebx + {r('DT')}]
            imul edx, edx, {RATE}
            add eax, edx
            cmp eax, ecx
            jl notfull
            mov dword ptr [edi + 0x1fc], ecx
            mov eax, 0x48d410
            call eax
            lea ecx, [ebx + {r('ENTRY')}]
            lea eax, [ebx + {r('MSGTXT')}]
            mov dword ptr [ecx], eax
            mov dword ptr [ecx + 4], 0
            mov eax, 0x48d420
            call eax
            movzx ecx, word ptr [0x580bec]
            movzx edx, word ptr [0x520a1c]
            mov eax, 0x48e950
            call eax
            jmp animate
        notfull:
            mov dword ptr [edi + 0x1fc], eax

        animate:
            mov edx, dword ptr [ebx + {r('DT')}]
            imul edx, edx, {STEP}
            movsx eax, word ptr [ebp + 8]
            mov ecx, dword ptr [ebx + {r('TP')}]
            call approach
            mov word ptr [ebp + 8], ax
            mov word ptr [ebx + {s(o_snip + 10)}], ax
            mov word ptr [ebx + {s(o_boom2 + 10)}], ax
            movsx eax, word ptr [ebp + 10]
            mov ecx, dword ptr [ebx + {r('TH')}]
            call approach
            mov word ptr [ebp + 10], ax
            mov word ptr [ebx + {s(o_snip + 8)}], ax
            mov word ptr [ebx + {s(o_boom2 + 8)}], ax
            mov edx, dword ptr [ebx + {r('DT')}]
            imul edx, edx, {TELE_RATE}
            movsx eax, word ptr [ebp + 12]
            mov ecx, dword ptr [ebx + {r('TE')}]
            call approach
            mov word ptr [ebp + 12], ax
            mov dword ptr [ebx + {r('EXT')}], eax
            mov eax, dword ptr [ebx + {r('APPR')}]
            or ax, word ptr [ebp + 8]
            or ax, word ptr [ebp + 10]
            or ax, word ptr [ebp + 12]
            mov dword ptr [ebx + {r('SHOW')}], eax
            mov eax, {ORIG_R}
            cmp dword ptr [ebx + {r('APPR')}], 0
            je setr
            mov eax, {SMALL_R}
        setr:
            mov dword ptr [ebx + {s(-1)}], eax
            jmp done

        noslot:
            mov word ptr [ebx + {s(o_snip + 8)}], 0
            mov word ptr [ebx + {s(o_snip + 10)}], 0
            mov word ptr [ebx + {s(o_boom2 + 8)}], 0
            mov word ptr [ebx + {s(o_boom2 + 10)}], 0
            mov dword ptr [ebx + {s(-1)}], {ORIG_R}
        done:
{TELE_ASM}
            mov ax, {F_LIT}
            mov cl, {C_BOOM}
            cmp dword ptr [ebx + {r('CONT')}], 0
            je lt1
            mov ax, {F_GLOW}
            mov cl, {C_GREEN}
        lt1:
{LIGHT_ASM}
            mov ecx, dword ptr [ebx + {s(-2)}]
            cmp word ptr [ecx], 1
            jne ab0
            mov dword ptr [ebx + {r('SHOW')}], 1
        ab0:
            lea edx, [ebx + {s(RESUME - tail)}]
            mov word ptr [ebx + {s(o_endsel + 1)}], {G['rel_ret']}
            cmp dword ptr [ebx + {r('SHOW')}], 0
            je seldone
            movsx eax, word ptr [0x51cdac]
            cmp eax, {EYE_BELOW}
            jl below
            lea edx, [ebx + {s(resume_off)}]
            jmp seldone
        below:
            mov word ptr [ebx + {s(o_endsel + 1)}], {G['rel_boom2']}
            cmp dword ptr [ebx + {r('CONT')}], 0
            je seldone
            mov word ptr [ebx + {s(o_endsel + 1)}], {G['rel_lights']}
        seldone:
            mov eax, edx
        resume:
            mov dword ptr [esp + 28], eax
            popad
            popfd
            pop ecx
            push eax
            add ecx, 6
            jmp ecx

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

    # 兩次組譯：第一次求 base 位置（code 開頭 + pushfd/pushad/call 之後）
    # mode: full = x86 + 可動硬桿；x86only = 跑 x86 但不畫硬桿；static = 不跑 x86、畫收起的 C4 硬桿；
    #       origboom = 不跑 x86、直接用原本的呼叫畫原本的硬桿（只拿掉後燃器判斷）
    resume_off = o_snip if mode == 'full' else RESUME - tail
    ks = Ks(KS_ARCH_X86, KS_MODE_32)
    base_off = o_code + 1 + 1 + 5
    F2_REL = None
    for _ in range(3):
        src = asm(base_off)
        # F2 表在原 CODE 0x73E4，區塊插在 tail：相對 base 的位移
        f2disp = F2TBL - (tail + base_off)
        src = src.replace(f'[ebx + {-1 - base_off}]', f'[ebx + {f2disp}]')
        # [ebx + s(-2)] = 0x3719 的 dword：原本 cmp [_PLafterBurner],1 的運算元，載入器會把它換成變數位址
        src = src.replace(f'[ebx + {-2 - base_off}]', f'[ebx + {AB_PTR - (tail + base_off)}]')
        enc, _ = ks.asm(src, 0)
        code_bytes = bytes(enc)
        if code_bytes[:2] == b'\x9c\x60' and code_bytes[2] == 0xE8: break
    blk += code_bytes
    # 38 rel16：38 在 o_snip+16，rel 之後 = o_snip+19；目標 RESUME（原 CODE，在區塊之前）
    struct.pack_into('<h', blk, o_snip + 17, RESUME - (tail + o_snip + 19))

    # ---- 3. 掛勾：0x3714 F0 ----
    #   F0 00 | EB 04 | (0x3718 舊重定位，不執行) | E8 rel32 → x86 | (0x3721 舊重定位) | 68 thunk; C3（保留）
    #   KC135-1/2/2C 把 call 放在 0x371C，蓋掉了 0x3719 重定位 dword 的最高位元組 → 載入時當機。
    #   現在：F0 00 | EB 13 → 0x372B | (0x3718..0x372A 原樣，重定位 0x3719/0x3721/0x3726 不動)
    #         0x372B: E8 rel32 → x86（蓋掉原本的 12 00 c3 0d 呼叫硬桿與 F0）| 0x3730..0x3735 死碼（含重定位 0x3732）
    #         x86 回到 返回位址+6 = 0x3736：push thunk; ret（原樣）
    call_at = CALL_AT
    target = tail + o_code
    assert c[0x3736] == 0x68 and c[0x373B] == 0xC3
    if mode in ('full', 'x86only'):
        c[F0_HOOK + 2:F0_HOOK + 4] = b'\xEB\x13'
        c[call_at] = 0xE8; struct.pack_into('<i', c, call_at + 1, target - (call_at + 5))
    # 主 LOD 最外層結束的 38（→ 0x42AD 的 1E）改跳到區塊的選擇跳躍（預設 → 1E）
    struct.pack_into('<h', blk, o_endsel + 1, G['rel_ret'])
    assert c[END_JMP] == 0x38 and END_JMP + 3 + struct.unpack_from('<h', c, END_JMP + 1)[0] == 0x42AD and c[0x42AD] == 0x1E
    if mode == 'full':
        struct.pack_into('<h', c, END_JMP + 1, tail + o_endsel - (END_JMP + 3))

    if mode in ('static', 'origboom'):
        c[F0_HOOK + 2:F0_HOOK + 4] = b'\xEB\x08'          # 跳到 0x3720 的 push（原本的重定位）
    check_relocs(d, pe, code, c)
    out = insert_blocks(d, pe, secs, code, c, tail, bytes(blk))
    if mode == 'static':
        out = bytearray(out); pe3, o3, s3 = pe_sections(out); cd3 = next(x for x in s3 if x['name'] == 'CODE')
        assert out[cd3['ro'] + 0x3720] == 0x68
        struct.pack_into('<I', out, cd3['ro'] + 0x3721, 0x1000 + tail + o_snip)
        out = bytes(out)
    assert len(out) < 65536, len(out)
    open(dst, 'wb').write(out)
    info = dict(tail=tail, o_snip=o_snip, o_code=o_code, o_part82=o_part82, D=D, blk_len=len(blk), size=len(out))
    if preview:
        # 預覽用：F0 改成原本格式「push 回到的位址」讓 sh_paint 跟得到，並把硬桿放下 30°
        d2 = bytearray(out); pe2, o2, s2 = pe_sections(d2); cd = next(s for s in s2 if s['name'] == 'CODE')
        b = cd['ro']; va = lambda off: 0x1000 + off
        d2[b + F0_HOOK + 2] = 0x68; struct.pack_into('<I', d2, b + F0_HOOK + 3, va(tail + o_snip))
        struct.pack_into('<h', d2, b + tail + o_snip + 10, int(30 * DEG))
        if len(sys.argv) > 0 and os.environ.get('KC_PREVIEW_BELOW'):
            # 機腹下方視角：最後畫機腹燈 + 硬桿；掛勾處不畫
            struct.pack_into('<I', d2, b + F0_HOOK + 3, va(RESUME))
            struct.pack_into('<h', d2, b + tail + o_endsel + 1, G['rel_lights'])
            struct.pack_into('<h', d2, b + tail + o_boom2 + 10, int(30 * DEG))
            for o in G['light_faces']:
                struct.pack_into('<H', d2, b + tail + o + 1, F_GLOW); d2[b + tail + o + 3] = C_GREEN
        open(preview, 'wb').write(d2)
    return info


if __name__ == '__main__':
    a = sys.argv[1:]
    mode = 'full'
    if a and a[-1] in ('full', 'x86only', 'static', 'origboom', 'insertonly'): mode = a.pop()
    print(build(a[0], a[1], a[2] if len(a) > 2 else None, mode))
