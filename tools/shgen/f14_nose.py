#!/usr/bin/env python3
"""F-14 機鼻重畫：從原始 SH/F14.SH 產生 SHX/F14N.SH。做法說明見 skill/SH_edit_note.MD。

  * y=95 接合環（機身往前接機鼻的那一圈 13 點）修圓，駕駛艙前緣左邊照右邊鏡像，碰到的面重算法向量
  * 原本 y ≥ 95 的機鼻面（30 個）全部改成 `38 rel16` 跳過；左側機砲口的兩個小貼圖搬到新機鼻區塊最後畫
  * 新機鼻 v2：照實機側面照片的線型（尖端在機身中線附近），超橢圓剖面 10 圈（16→4 點），每條經線在前後 1 呎內挑四捨五入誤差最小的點，
    所以上、下、側面輪廓是順的；F6 用曲面的解析法向量（Gouraud 光影平滑）；機砲口貼圖角點搬到新表面上；CODE 不夠時自動 grow_vas
  * 機鼻下 pod（凸多面體，11 點 9 面，寬 2 呎、高 2 呎、長 9 呎，y 96～105）
  * 畫面順序：主體 BSP 根節點（CODE+0x1007）換成呼叫新區塊，先用 06 測試眼睛在 y=95 前或後決定機身和機鼻/pod 的先後，
    再測試眼睛是否在機鼻底面（上 = -8）以下決定機鼻和 pod 的先後
用法：python3 f14_nose.py SH/F14.SH SHX/F14N.SH
"""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, parse_face, main_lod, FACE_OPS, insert_blocks

SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])
ROOT = 0x1007          # 主體 BSP 根節點（0C 00 …，14 位元組），後面 0x1015 是 38 跳到零件
POD_BASE = 480         # pod 頂點放在頂點表的位置（零件用到 470）

# 左上半照右上半鏡像：頂點 ← 鏡像來源
MIRROR_V = {60: 61, 162: 169, 63: 62, 157: 163, 76: 94, 210: 171, 214: 174}


NOSE_BASE = 500        # 新機鼻頂點放在頂點表的位置
# y=95 接合環（機身往前接機鼻的那一圈），從上中央順時針（從前面看）一圈 13 點：(左右頂點) → 新位置 (x, z)，左邊 x 取負
RING95 = {(72,): (0, 7), (169, 162): (3, 7), (61, 60): (3, 7), (171, 210): (6, 4), (170, 211): (7, 2),
          (202, 229): (6, -5), (263, 332): (4, -7), (290, 333): (2, -8)}
RING_ORDER = [72, 169, 171, 170, 202, 263, 290, 333, 332, 229, 211, 210, 162]
GUN_DECALS = (0x2AFC, 0x2FA2)          # 左側機砲口的小貼圖（色號 0 透明）
GUN_VERTS = (158, 161, 216, 217)       # 這兩個貼圖在 y>95 的角點
# 機鼻線型 v2（2026-11-14，照 Kuoyi 給的實機側面照片重畫）：t = (y-95)/30，y=95 是接合環，y=125 是尖端
#   尖端 z=-2：大約在機身中線（y=95 環上緣 7、下緣 -8，中線 -0.5）；照片量出來尖端在高度的 0.6～0.65
#   上緣 z = 尖端 + 9·(1-t)(1+0.5t)：接近直線的尖拱，起點斜率和後面機身差不多，所以接得順
#   下緣 z = 尖端 - 6·(1-t³)：前段幾乎水平，靠近尖端才往上收（照片量到 t=0.54 時還有 0.84、t=0.76 時 0.59）
#   半寬 = 7·(1-t)(1+0.6t)；剖面是超橢圓 |x/w|^2.4 + |(z-c)/h|^2.4 = 1，n=2.4 時和 y=95 環幾乎一樣
#   頂點座標只能是整數（1 呎），所以每個點都在附近的整數格點裡挑「離曲面最近」的那一個（y 可以前後差 1），
#   光影（F6）用曲面的解析法向量，Gouraud 會把小面之間的差異抹平
TIP = (0, 125, -2)
N_SE = 2.4
BOT_P = 2.0            # 下緣 = 尖端 - 6·(1-t^p)：v2 第一版 p=3 收得太急（Kuoyi），改 2 讓下緣早一點開始往上收
POD_DY = -5            # pod 往後移（原本 y 96～105 → 91～100），讓開下緣的曲線
RINGS = [(98, 16), (101, 16), (104, 16), (107, 16), (110, 16), (113, 12), (116, 12), (119, 8), (121, 8), (123, 4)]
def prof(t):
    top = TIP[2] + (7 - TIP[2]) * (1 - t) * (1 + 0.5 * t)
    bot = TIP[2] - (TIP[2] + 8) * (1 - t ** BOT_P)
    return top, bot, 7 * (1 - t) * (1 + 0.6 * t)
def _s(v, e): return math.copysign(abs(v) ** e, v)
def surf(t, phi):
    """曲面上的點 (x, y, z)；phi 從上中央 0 開始，往 x>0 那邊轉，π 是下中央。"""
    top, bot, w = prof(t); c, h = (top + bot) / 2, (top - bot) / 2
    return (w * _s(math.sin(phi), 2 / N_SE), 95 + 30 * t, c + h * _s(math.cos(phi), 2 / N_SE))
def implicit(x, y, z):
    t = min(max((y - 95) / 30, -0.2), 0.985); top, bot, w = prof(t); c, h = (top + bot) / 2, (top - bot) / 2
    r = ((abs(x) / w) ** N_SE + (abs(z - c) / h) ** N_SE) ** (1 / N_SE)
    return (r - 1) * min(w, h)            # 大約是到曲面的距離（呎），外面為正
def grad(x, y, z, e=0.05):
    g = [(implicit(x+e, y, z) - implicit(x-e, y, z)), (implicit(x, y+e, z) - implicit(x, y-e, z)), (implicit(x, y, z+e) - implicit(x, y, z-e))]
    L = sum(v*v for v in g) ** 0.5 or 1
    return [v / L for v in g]
def f6(g):      # 曲面法向量 (x, y, z) → F6 的 i8 (x, 上, 前)
    return (round(g[0]*127), round(g[2]*127), round(g[1]*127))
def snap(t, phi):
    """沿著這條經線（固定 phi）在名義 y 的前後 1 呎內挑一個 y，讓曲面點四捨五入後的誤差最小。
    每條經線上的點都幾乎正好在曲面上，所以從側面、上面、下面看的輪廓線是順的；環不一定在同一個 y 平面上，
    但 FA 用 F6 做 Gouraud 光影，小面怎麼切看不出來。"""
    y0 = round(95 + 30 * t); best = None
    for Y in (y0 - 1, y0, y0 + 1):
        if not 96 <= Y <= 124: continue
        x, _, z = surf((Y - 95) / 30, phi)
        X = 0 if abs(math.sin(phi)) < 1e-9 else round(x); Z = round(z)
        cost = abs(X - x) + abs(Z - z) + 0.15 * abs(Y - y0)
        if best is None or cost < best[0]: best = (cost, (X, Y, Z))
    return best[1]


def nose(V):
    """回傳 (新頂點, F6 法向量, 面 [(旗標, 色號, 索引)], y=95 環的 F6 [(頂點, 法向量)])。
    y=95 環（13 點）→ 10 圈新環（16 → 4 點，照大小遞減）→ 尖端；相鄰兩圈依角度縫起來，對得上的是四邊形，其餘是三角形。"""
    NV, NN = [], []
    def phi_of(x, z, c=-0.5):
        a = math.atan2(x / 7, (z - c) / 7.5); return a % (2 * math.pi)
    rings = [[(i, phi_of(V[i][0], V[i][2])) for i in RING_ORDER]]
    for y, m in RINGS:
        t = (y - 95) / 30; half = []
        for k in range(m // 2 + 1):
            phi = 2 * math.pi * k / m; half.append((snap(t, phi), phi))
        pts = half + [((-p[0], p[1], p[2]), 2 * math.pi - phi) for p, phi in half[-2:0:-1]]
        r = []
        for p, phi in pts:
            if r and NV[r[-1][0][1]] == p: continue
            NV.append(p); NN.append(f6(grad(*p))); r.append((('n', len(NV) - 1), phi))
        while len(r) > 1 and NV[r[-1][0][1]] == NV[r[0][0][1]]: r.pop()
        rings.append(r)
    NV.append(TIP); NN.append((0, 8, 127)); tip = ('n', len(NV) - 1)
    ring0 = [(i, f6(grad(V[i][0], 95, V[i][2]))) for i in RING_ORDER]
    ids = lambda r: r if isinstance(r, int) else NOSE_BASE + r[1]
    allv = dict(V); allv.update({NOSE_BASE + k: v for k, v in enumerate(NV)})
    faces = []
    def add(idx):
        idx = [ids(i) for i in idx]; P = [allv[i] for i in idx]
        q = [k for k in range(len(P)) if P[k] != P[k-1]]
        idx = [idx[k] for k in q]; P = [P[k] for k in q]
        if len(set(P)) < 3: return
        if len(P) == 4:          # 不平的四邊形切成兩個三角形（沿較短的對角線）
            n = [0, 0, 0]
            for k in range(3):
                p, q_ = P[k], P[(k+1) % 3]
                n[0] += p[1]*q_[2]-p[2]*q_[1]; n[1] += p[2]*q_[0]-p[0]*q_[2]; n[2] += p[0]*q_[1]-p[1]*q_[0]
            L = sum(v*v for v in n) ** 0.5
            off = abs(sum(n[k]*(P[3][k]-P[0][k]) for k in range(3))) / L if L else 9
            if off > 0.2:
                d02 = sum((P[0][k]-P[2][k])**2 for k in range(3)); d13 = sum((P[1][k]-P[3][k])**2 for k in range(3))
                if d02 <= d13: add2([idx[0], idx[1], idx[2]]); add2([idx[0], idx[2], idx[3]])
                else: add2([idx[0], idx[1], idx[3]]); add2([idx[1], idx[2], idx[3]])
                return
        add2(idx)
    def add2(idx):
        P = [allv[i] for i in idx]
        n = [0, 0, 0]
        for k in range(len(P)):
            p, q_ = P[k], P[(k+1) % len(P)]
            n[0] += p[1]*q_[2]-p[2]*q_[1]; n[1] += p[2]*q_[0]-p[0]*q_[2]; n[2] += p[0]*q_[1]-p[1]*q_[0]
        if sum(v*v for v in n) < 1e-6: return
        cen = [sum(p[k] for p in P) / len(P) for k in range(3)]
        g = grad(*cen)
        if sum(n[k]*g[k] for k in range(3)) > 0: idx = idx[::-1]      # FA：ΣP×P 朝內
        faces.append((0x273, 0x98, idx))
    TWO = 2 * math.pi
    for A, B in zip(rings, rings[1:]):
        i = j = 0; na, nb = len(A), len(B)
        while i < na or j < nb:
            pa = A[(i+1) % na][1] if i + 1 < na else TWO
            pb = B[(j+1) % nb][1] if j + 1 < nb else TWO
            a0, a1, b0, b1 = A[i % na][0], A[(i+1) % na][0], B[j % nb][0], B[(j+1) % nb][0]
            if i >= na: add([a0, b1, b0]); j += 1
            elif j >= nb: add([a0, a1, b0]); i += 1
            elif abs(pa - pb) < 1e-6: add([a0, a1, b1, b0]); i += 1; j += 1
            elif pa < pb: add([a0, a1, b0]); i += 1
            else: add([a0, b1, b0]); j += 1
    last = rings[-1]
    for k in range(len(last)):
        add([last[k][0], last[(k+1) % len(last)][0], tip])
    return NV, NN, faces, ring0


def normal_point(P, fl):
    """FC 面的法向量（x、上、前，長度 32767，朝外）和平面上的點。FA 的面在 (x,y,z) 下 ΣP×P 朝內。"""
    n = [0, 0, 0]
    for k in range(len(P)):
        p, q = P[k], P[(k+1) % len(P)]
        n[0] += p[1]*q[2]-p[2]*q[1]; n[1] += p[2]*q[0]-p[0]*q[2]; n[2] += p[0]*q[1]-p[1]*q[0]
    L = sum(x*x for x in n) ** 0.5 or 1
    nrm = [round(-n[0]/L*32767), round(-n[2]/L*32767), round(-n[1]/L*32767)]
    cen = [sum(p[k] for p in P) / len(P) for k in range(3)]
    pt = [round(cen[0]), round(cen[2]), round(cen[1])]
    if fl & 0x200: pt = [max(-128, min(127, v)) for v in pt]
    return nrm, pt


def face_bytes(fl, col, idx, P, uv=None):
    if any(i > 255 for i in idx): fl |= 0x400
    b = bytearray(struct.pack('<BHH', 0xFC, fl, col))
    if fl & 0x60:
        nrm, pt = normal_point(P, fl)
        b += struct.pack('<hhh', *nrm) + (struct.pack('<bbb', *pt) if fl & 0x200 else struct.pack('<hhh', *pt))
    b.append(len(idx))
    b += b''.join(struct.pack('<H', i) for i in idx) if fl & 0x400 else bytes(idx)
    if fl & 4:
        b += b''.join(bytes(u) if fl & 0x100 else struct.pack('<HH', *u) for u in uv)
    return b


def pod():
    """回傳 (頂點, F6 法向量（x、上、前）, 面 [(旗標, 色號, 索引)])，索引從 0 起算。"""
    # 頂點座標以 1 呎為單位，尺寸減半後剖面只能用五邊形：寬 2、高 2，底下一條龍骨
    ring = [(-1, -8), (1, -8), (1, -9), (0, -10), (-1, -9)]
    V, N = [], []
    def add(p, n): V.append(p); L = sum(x*x for x in n) ** 0.5; N.append(tuple(round(x*127/L) for x in n)); return len(V) - 1
    R = add((0, 96 + POD_DY, -8), (0, -60, -110))
    M = [add((x, 98 + POD_DY, z), (x, z+9, -0.4)) for x, z in ring]
    F = [add((x, 105 + POD_DY, z), (x, z+9, 0.4)) for x, z in ring]
    body, win, fl = 0x98, 0x9B, 0x273
    faces = []
    for k in range(1, 5):  # 環的邊 k → k+1；0→1 是貼在機鼻底面的上緣，不畫
        a, b = k, (k+1) % 5
        faces.append((fl, body, [R, M[a], M[b]]))
        faces.append((fl, body, [M[a], F[a], F[b], M[b]]))
    faces.append((0x271, win, list(F)))    # 前面的窗：單色、不用 Gouraud
    # 繞向：FA 的面在 (x,y,z) 下 ΣP×P 朝內；不對就反轉
    cen = [sum(p[k] for p in V) / len(V) for k in range(3)]
    out = []
    for fl_, col, idx in faces:
        P = [V[i] for i in idx]; n = [0, 0, 0]
        for k in range(len(P)):
            p, q = P[k], P[(k+1) % len(P)]
            n[0] += p[1]*q[2]-p[2]*q[1]; n[1] += p[2]*q[0]-p[0]*q[2]; n[2] += p[0]*q[1]-p[1]*q[0]
        fc = [sum(p[k] for p in P) / len(P) - cen[k] for k in range(3)]
        if sum(n[k]*fc[k] for k in range(3)) > 0: idx = idx[::-1]
        out.append((fl_, col, idx))
    return V, N, out


def build(d, log=print):
    """回傳 (新檔案或 None（CODE 放不下）, 需要的位元組, 空間)。"""
    d = bytearray(d)
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    c = bytearray(d[code['ro']:code['ro']+code['vs']])
    bufs = main_lod(c); o0, main_n, _, main_e = bufs[0]
    stop = next((b[0] for b in bufs if b[2] < 0), None) or (bufs[1][0] if len(bufs) > 1 else len(c))
    V = {i: struct.unpack_from('<hhh', c, o0+6+6*i) for i in range(main_n)}
    F6 = {}; p = main_e
    while c[p] == 0xF6: F6[struct.unpack_from('<H', c, p+1)[0]] = p; p += 7
    faces, o = {}, main_e
    while o < stop - 6:
        f = parse_face(c, o) if c[o] == 0xFC else None
        ok = f and ((f['fl'] & 0x200 and not f['fl'] & 0xF000 and (f['fl'] & 0xFF) in FACE_OPS) or (not f['fl'] & 0x200 and (f['fl'] & 0xFF) in FACE_OPS and f['fl'] < 0x1000))
        if ok and all(i < main_n for i in f['idx']) and len(set(f['idx'])) == f['n'] and f['end'] <= stop:
            faces[o] = f; o = f['end']; continue
        o += 1
    # 檢查法向量公式：和原檔每個面存的法向量同方向
    agree = sum(1 for f in faces.values() if f['fl'] & 0x60 and
                sum(a*b for a, b in zip(normal_point([V[i] for i in f['idx']], f['fl'])[0], struct.unpack_from('<hhh', f['head'], 4))) > 0)
    log(f'法向量公式和原檔同方向：{agree}/{sum(1 for f in faces.values() if f["fl"] & 0x60)} 個面')

    # 1. 搬頂點：駕駛艙前緣左邊照右邊鏡像，y=95 接合環修圓
    for i, s_ in MIRROR_V.items():
        x, y, z = V[s_]; V[i] = (-x, y, z)
    for ids, (x, z) in RING95.items():
        for k, i in enumerate(ids): V[i] = ((x, -x)[k], 95, z) if k < 2 else None
    for i in range(main_n): struct.pack_into('<hhh', c, o0+6+6*i, *V[i])
    moved = set(MIRROR_V) | {i for ids in RING95 for i in ids}
    # 2. 機鼻（y ≥ 95 的面）全部拿掉，機砲口的小貼圖搬到新機鼻區塊裡（在機鼻之後畫）
    front = [f for f in faces.values() if all(V[i][1] >= 95 for i in f['idx'])]
    # 機砲口貼圖的角點搬到新機鼻表面上（原本在 x=-7，新機鼻在 y=99 只剩 6 呎寬），再重算它們的法向量
    for i in GUN_VERTS:
        x, y, z = V[i]; t = (y - 95) / 30; top, bot, w = prof(t); cc, h = (top + bot) / 2, (top - bot) / 2
        V[i] = (-round(w * max(0, 1 - abs((z - cc) / h) ** N_SE) ** (1 / N_SE)), y, z)
        struct.pack_into('<hhh', c, o0+6+6*i, *V[i])
    decals = []
    for f in front:
        if f['o'] not in GUN_DECALS: continue
        b = bytearray(c[f['o']:f['end']]); nrm, pt = normal_point([V[i] for i in f['idx']], f['fl'])
        struct.pack_into('<hhh', b, 5, *nrm); struct.pack_into('<bbb' if f['fl'] & 0x200 else '<hhh', b, 11, *pt)
        decals.append(bytes(b))
    for f in front:
        o, e = f['o'], f['end']; c[o:e] = b'\x38' + struct.pack('<h', e - (o + 3)) + b'\x1e' * (e - o - 3)
    # 3. 碰到搬動頂點的面重算法向量
    for f in faces.values():
        if f in front or not f['fl'] & 0x60 or not set(f['idx']) & moved: continue
        nrm, pt = normal_point([V[i] for i in f['idx']], f['fl'])
        struct.pack_into('<hhh', c, f['o']+5, *nrm)
        struct.pack_into('<bbb' if f['fl'] & 0x200 else '<hhh', c, f['o']+11, *pt)
    # 4. 新機鼻
    NV, NN, NF, ring0 = nose(V)
    allv = dict(V); allv.update({NOSE_BASE+k: v for k, v in enumerate(NV)})
    def vid(r): return r if isinstance(r, int) and r < 1000 else NOSE_BASE + r[1]
    noseb = bytearray(struct.pack('<BBHH', 0x82, 0, len(NV), NOSE_BASE*8))
    for v in NV: noseb += struct.pack('<hhh', *v)
    for k, n in enumerate(NN): noseb += struct.pack('<BHBbbb', 0xF6, NOSE_BASE+k, 0x98, *n)
    for i, n in ring0: noseb += struct.pack('<BHBbbb', 0xF6, i, 0x98, *n)
    nf = 0
    for fl, col, idx in NF:
        P = [allv[i] for i in idx]
        q = [k for k in range(len(P)) if P[k] != P[k-1]]        # 四捨五入後重疊的點拿掉
        idx = [idx[k] for k in q]; P = [P[k] for k in q]
        if len(set(P)) < 3: continue
        noseb += face_bytes(fl, col, idx, P); nf += 1
    for b in decals: noseb += b
    noseb += b'\x00\x00'
    # 5. pod
    PV, PN, PF = pod()
    podb = bytearray(struct.pack('<BBHH', 0x82, 0, len(PV), POD_BASE*8))
    for v in PV: podb += struct.pack('<hhh', *v)
    for k, n in enumerate(PN): podb += struct.pack('<BHBbbb', 0xF6, POD_BASE+k, 0x98, *n)
    allv.update({POD_BASE+k: v for k, v in enumerate(PV)})
    for fl, col, idx in PF:
        ids = [POD_BASE+i for i in idx]; podb += face_bytes(fl, col, ids, [allv[i] for i in ids])
    podb += b'\x00\x00'
    # 6. 根節點換成呼叫新區塊：
    #    S:  06 眼睛在 y=95 前面？ 是 → 先機身 BODY 再 NP；否 → 先 NP 再機身
    #    NP: 06 眼睛在機鼻底面（上 = -8）以下？ 是 → 先機鼻再 pod；否 → 先 pod 再機鼻
    assert c[ROOT] == 0x0C and c[ROOT+1] == 0 and c[ROOT+14] == 0x38, '根節點不是預期的 0C … 38'
    tail = bytes(c).find(SIG)
    TA = ROOT + 12 + struct.unpack_from('<h', c, ROOT+10)[0]; TB = ROOT + 14 + struct.unpack_from('<h', c, ROOT+12)[0]
    # pod 跨過 y=95，所以順序改成：先用機鼻底面（上 = -8）分 pod 和其他；其他再用 y=95 分機身和機鼻
    PN = tail; S = PN + 20; BODY = S + 20; NOSE = BODY + 16; POD = NOSE + len(noseb)
    def node(at, n, d, a, b):   # 06 00 n1 d1 n2 d2 n3 d3 relA relB 00 00
        return struct.pack('<BB6h', 0x06, 0, n[0], d[0], n[1], d[1], n[2], d[2]) + struct.pack('<hh', a - (at+16), b - (at+18)) + b'\x00\x00'
    body = bytearray(c[ROOT:ROOT+10]) + struct.pack('<hh', TA - (BODY+12), TB - (BODY+14)) + b'\x00\x00'
    blocks = node(PN, (0, -16384, 0), (0, 8, 0), S, POD) + node(S, (0, 0, 16384), (0, 0, -95), BODY, NOSE) + body + noseb + podb
    patch = bytearray(b'\x12\x00') + struct.pack('<h', PN - (ROOT + 4)) + b'\x38' + struct.pack('<h', ROOT + 14 - (ROOT + 7))
    c[ROOT:ROOT+14] = patch + b'\x1e' * (14 - len(patch))
    room = nxt - code['va'] - len(c)
    if NOSE_BASE + len(NV) > 900: sys.exit('頂點表超過 900')
    if len(blocks) > room: return None, len(blocks), room
    out = insert_blocks(d, pe, secs, code, c, tail, blocks)
    log(f'拿掉機鼻 {len(front)} 面；新機鼻 {len(NV)} 點 {nf} 面（+機砲口貼圖 {len(decals)}）；pod {len(PV)} 點 {len(PF)} 面；新增 {len(blocks)} 位元組（空間 {room}）')
    return out, len(blocks), room


def main():
    src, dst = sys.argv[1], sys.argv[2]
    d = open(src, 'rb').read()
    out, need, room = build(d, log=lambda *a: None)
    if out is None:     # CODE 放不下：把 .idata/.reloc/$$DOSX 的 VA 往後移（第 8 節），再重做一次
        delta = (need - room + 0xFFF) // 0x1000 * 0x1000
        print(f'CODE 空間不夠（需要 {need}，只有 {room}），後面的區段往後移 {delta:#x}')
        from f18g_growler import grow_vas
        out, need, room = build(grow_vas(d, delta))
    else:
        out, need, room = build(d)
    open(dst, 'wb').write(out)
    print('寫出', dst)

if __name__ == '__main__': main()
