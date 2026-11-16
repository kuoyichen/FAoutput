#!/usr/bin/env python3
"""F-14 後燃器火焰換成 AUR.SH 的做法：3 格動畫、有透明洞的激波環貼圖、拉長。

AUR 的做法（見 skill/SH_edit_note.MD「後燃器火焰動畫」）：
  * SH 指令 `40 00 N rel16×N`：FA 用每畫格加 1 的計數器（0x4EB738）mod N 選一個分支跳過去，
    每個分支畫一個面，然後 `48 00 rel16` 跳到下一個 40 節點
  * 每個火焰面有 3 個版本，各用 _AUR.PIC 裡一張 41×61 的火焰圖；圖裡約一半是 0xFF（色號 0 的面 = 透明），
    所以一段段的亮環中間會透出背景，看起來像半透明、會流動的火焰

這支程式：
  1. 把 _AUR.PIC 的 3 張火焰圖複製到 _F14.PIC 沒用到的地方（第 3 張轉 90° 放，UV 跟著轉）
  2. F14 原本的火焰區塊（後燃器 F0 條件呼叫的 82 + 8 面）不動，改寫呼叫目標到插在簽章前的新區塊：
     同樣 16 點、同樣的十字交叉面（兩具引擎 × 垂直/水平 × 正反面），但從噴嘴 y=-57 拉長到 TAIL，
     每個面包進 `40 00 03 00` 動畫切換
用法：python3 f14_ab_flame.py SH/F14.SH PIC/_F14.PIC PIC/_AUR.PIC 輸出.SH 輸出.PIC
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, insert_blocks

SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])
CALL = 0x3973          # 後燃器 F0 條件後面的 `12 00 rel16`（原本呼叫 0x4766 的火焰區塊）
OLD = 0x4766           # 原火焰區塊：82 00 16 點 + 8 個 FC（每個 39 位元組）+ 1E
NOZZLE, TAIL = -57, -132   # 火焰從噴嘴到尾端的 y（原本到 -94）
# AUR 的 3 張火焰圖（貼圖座標 u0, v0；41×61，v 大的一端是噴嘴）
AUR_FRAMES = [(199, 91), (127, 89), (0, 54)]
# 放到 _F14.PIC 的位置（u0, v0, 轉 90°?）：轉的那張沿火焰方向是 u（u0 = 尾端），橫向是 v
F14_SLOTS = [(184, 0, False), (178, 354, False), (178, 415, True)]


def read_pic(b):
    w, h = struct.unpack_from('<II', b, 2); rt = struct.unpack_from('<I', b, 0x22)[0]
    rows = [struct.unpack_from('<I', b, rt + 4*r)[0] for r in range(h)]
    return w, h, rows      # 檔案第 r 列 = 貼圖 v = h-1-r


def pix(b, P, u, v):
    w, h, rows = P; return b[rows[h-1-v] + u]


def put(b, P, u, v, k):
    w, h, rows = P; b[rows[h-1-v] + u] = k


def main():
    src, psrc, paur, dst, pdst = sys.argv[1:6]
    # ---- 1. 貼圖 ----
    pb = bytearray(open(psrc, 'rb').read()); P = read_pic(pb)
    ab = open(paur, 'rb').read(); A = read_pic(ab)
    for (au, av), (fu, fv, rot) in zip(AUR_FRAMES, F14_SLOTS):
        for r in range(61):            # r：沿火焰方向，0 = 尾端，60 = 噴嘴
            for a in range(41):        # a：橫向
                k = pix(ab, A, au + a, av + r)
                if rot: put(pb, P, fu + r, fv + a, k)
                else:   put(pb, P, fu + a, fv + r, k)

    def uv(slot, t, s):                # t：0 尾端 → 1 噴嘴；s：0/1 橫向兩邊
        fu, fv, rot = F14_SLOTS[slot]
        return (fu + 60*t, fv + 40*s) if rot else (fu + 40*s, fv + 60*t)

    # ---- 2. SH ----
    d = bytearray(open(src, 'rb').read())
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    c = bytearray(d[code['ro']:code['ro']+code['vs']])
    assert c[CALL:CALL+2] == b'\x12\x00' and CALL + 4 + struct.unpack_from('<h', c, CALL+2)[0] == OLD, '不是預期的 F14 火焰呼叫'
    n, t = struct.unpack_from('<HH', c, OLD+2); assert c[OLD] == 0x82 and n == 16
    V = [list(struct.unpack_from('<3h', c, OLD+6+6*i)) for i in range(n)]
    for v in V:
        assert v[1] in (-57, -94)
        v[1] = NOZZLE if v[1] == -57 else TAIL
    vb = struct.pack('<BBHH', 0x82, 0, n, t) + b''.join(struct.pack('<3h', *v) for v in V)
    faces = []
    p = OLD + 6 + 6*n
    for _ in range(8):
        fl = struct.unpack_from('<H', c, p+1)[0]; assert c[p] == 0xFC and fl == 0x065C and c[p+14] == 4
        hdr = bytearray(c[p:p+14]); idx = list(struct.unpack_from('<4H', c, p+15))
        cx = sum(V[i - t//8][0] for i in idx) // 4; cz = sum(V[i - t//8][2] for i in idx) // 4
        struct.pack_into('<3b', hdr, 11, cx, cz, (NOZZLE + TAIL) // 2)     # 平面上的一點（x, up, fwd）
        faces.append((hdr, idx)); p += 39
    assert c[p] == 0x1E
    vert_plane = lambda idx: len({V[i - t//8][0] for i in idx}) == 1     # 垂直面：x 都一樣，橫向是 z；水平面橫向是 x

    def face_bytes(hdr, idx, slot):
        out = bytearray(hdr) + b'\x04' + struct.pack('<4H', *idx)
        ax = 2 if vert_plane(idx) else 0
        lo = min(V[i - t//8][ax] for i in idx); hi = max(V[i - t//8][ax] for i in idx)
        for i in idx:
            v = V[i - t//8]
            out += struct.pack('<HH', *(round(x) for x in uv(slot, 1 if v[1] == NOZZLE else 0, (v[ax] - lo) / (hi - lo))))
        return out

    tail = bytes(c).find(SIG)
    blk = bytearray(vb)
    for hdr, idx in faces:
        at = tail + len(blk)
        fb = [face_bytes(hdr, idx, k) for k in range(3)]
        L = [len(fb[0]) + 4, len(fb[1]) + 4, len(fb[2])]       # 前兩格後面接 48 跳躍
        start = [at + 10, at + 10 + L[0], at + 10 + L[0] + L[1]]
        nxt_node = at + 10 + sum(L)
        node = bytearray(b'\x40\x00\x03\x00')
        for k in range(3): node += struct.pack('<h', start[k] - (at + 4 + 2*k))
        blk += node
        for k in range(3):
            blk += fb[k]
            if k < 2:
                j = tail + len(blk)
                blk += b'\x48\x00' + struct.pack('<h', nxt_node - (j + 4))
        assert tail + len(blk) == nxt_node
    blk += b'\x1e'
    # rel16 只能跳 ±32K，簽章前的新區塊太遠：原火焰區塊開頭（呼叫目標，已經不用了）換成 F0 跳板
    # `push 新區塊 VA; push do_start_interp; ret`，跟原檔 F0 回到位元組碼的寫法一樣；兩個 dword 都要重定位。
    # 新區塊最後的 1E 回到 12 00 呼叫之後。
    thunk = struct.unpack_from('<I', c, 0x395C + 18)[0]      # 後燃器 F0 裡的 push do_start_interp
    assert c[0x395C:0x395E] == b'\xf0\x00' and c[0x395C + 17] == 0x68 and c[0x395C + 22] == 0xC3
    room = nxt - code['va'] - len(c)
    if len(blk) > room: sys.exit(f'空間不夠：需要 {len(blk)}，只有 {room}')
    L = len(blk)
    c[OLD:OLD+13] = b'\xf0\x00\x68' + struct.pack('<I', code['va'] + tail) + b'\x68' + struct.pack('<I', thunk + L) + b'\xc3'
    out = insert_blocks(d, pe, secs, code, c, tail, bytes(blk), extra_relocs=(OLD + 3 - tail, OLD + 8 - tail))
    open(dst, 'wb').write(out); open(pdst, 'wb').write(pb)
    print(f'{dst}: 新火焰區塊 {len(blk)} 位元組（空間 {room}）在 CODE+{tail:#x}，長度 {NOZZLE - TAIL}；{pdst}: 3 張火焰圖')


if __name__ == '__main__': main()
