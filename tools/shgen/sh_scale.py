#!/usr/bin/env python3
"""把整個 SH 模型等比例放大（KC-10 用 KC-135 放大 4/3，2026-11-27）。全部原地改位元組，檔案大小不變。

從 CODE+0x0E 開始照 FA.EXE 的解譯器走訪（每個分支、C4 零件、F0 的 push 回到位址都走），
把所有座標類的數值乘上 S：
  * 82 頂點（x, fwd, up）
  * FC 平面點（0x200 時是 i8；放大後超出 −128..127 就改用平面上離原點最近的點，還是超出就報錯）
  * 06 節點的 d1..d3、0C/0E/10 節點的 d1/d2（平面位移）
  * 6C 節點：var 6/8/10 是眼睛 x/上/前（cmp [0x51cda4+var], val），val 是座標
  * C4 零件位置、C4 目標前面的 6 byte 範圍標頭
  * 標頭：CODE+4 半徑、CODE+8 範圍、CE 區塊（可變翼樞紐、翼尖白線兩點，int32 ×256）、
    7A 點、78 範圍、C8 LOD 切換的物件大小（第一個 word）
  * F2 碰撞表：半徑（int32，ft×256）和 bbox（6 個 i16 ft）
其他指令（F6 法向量、FC 法向量、6C 變數、x86）不變：等比例放大法向量不變。
用法：python3 sh_scale.py 輸入.SH 輸出.SH [倍率，預設 4/3]
"""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections
import capstone

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)


def walk(c, start=0x0E):
    """回傳 {位址: 指令名}、無法解讀的位址、C4 目標集合。"""
    h = lambda p: struct.unpack_from('<h', c, p)[0]
    ops, unk, c4t, seen, stack = {}, [], set(), set(), [start]

    def go(p):
        for _ in range(100000):
            if p in seen or not (0 <= p < len(c) - 1): return
            seen.add(p); op = c[p]
            if op == 0x1E: ops[p] = '1E'; return
            if op == 0xBC: ops[p] = 'BC'; p += 2; continue        # BC 色號：2 byte
            if op == 0x38: ops[p] = '38'; stack.append(p + 3 + h(p + 1)); return
            if op not in (0xFC, 0xF6) and c[p + 1] != 0: unk.append(p); return
            if op == 0 : ops[p] = '00'; return
            if op == 0x82: ops[p] = '82'; p += 6 + 6 * struct.unpack_from('<H', c, p + 2)[0]
            elif op == 0xFC:
                fl = struct.unpack_from('<H', c, p + 1)[0]; q = p + 5
                if fl & 0x60: q += 6 + (3 if fl & 0x200 else 6)
                k = c[q]; q += 1 + (2 * k if fl & 0x400 else k)
                if fl & 4: q += k * (2 if fl & 0x100 else 4)
                ops[p] = 'FC'; p = q
            elif op == 0xF6: ops[p] = 'F6'; p += 7
            elif op == 0x06: ops[p] = '06'; stack.extend([p + 16 + h(p + 14), p + 18 + h(p + 16)]); p += 18
            elif op in (0x0C, 0x0E, 0x10): ops[p] = '%02X' % op; stack.extend([p + 12 + h(p + 10), p + 14 + h(p + 12)]); p += 14
            elif op == 0x6C: ops[p] = '6C'; stack.extend([p + 8 + h(p + 6), p + 10 + h(p + 8)]); p += 10
            elif op == 0x12: ops[p] = '12'; stack.append(p + 4 + h(p + 2)); p += 4
            elif op == 0x48: ops[p] = '48'; stack.append(p + 4 + h(p + 2)); return
            elif op == 0xC4: ops[p] = 'C4'; t = p + 16 + h(p + 14); c4t.add(t); stack.append(t); p += 16
            elif op == 0xC8: ops[p] = 'C8'; stack.append(p + 8 + h(p + 6)); p += 8
            elif op == 0xA6: ops[p] = 'A6'; stack.append(p + 6 + h(p + 2)); p += 6
            elif op == 0x96: ops[p] = '96'; p += 6                 # 線段（兩個頂點索引）
            elif op in (0xD0, 0xE0): ops[p] = '%02X' % op; p += 4
            elif op == 0x7A: ops[p] = '7A'; p += 10
            elif op == 0x78: ops[p] = '78'; p += 12
            elif op == 0x42:
                q = p + 2
                while c[q]: q += 1
                ops[p] = '42'; p = q + 1
            elif op == 0xE2: ops[p] = 'E2'; p += 16
            elif op == 0xCE: ops[p] = 'CE'; p += 0x28
            elif op == 0xF2: ops[p] = 'F2'; p += 4
            elif op == 0xF0:
                ops[p] = 'F0'
                for ins in MD.disasm(bytes(c[p + 2:p + 400]), p + 2):
                    if ins.mnemonic == 'push' and ins.op_str.startswith('0x'):
                        v = int(ins.op_str, 16) - 0x1000
                        if 0 < v < len(c) and c[v:v + 2] != b'\xff\x25': stack.append(v)
                    if ins.mnemonic == 'ret': break
                return
            else: unk.append(p); return
    while stack: go(stack.pop())
    return ops, unk, c4t


def sc(v, S):
    """左右對稱的四捨五入。"""
    r = int(math.floor(abs(v) * S + 0.5))
    return -r if v < 0 else r


def scale_code(c, S, verbose=True):
    c = bytearray(c)
    sig = c.find(bytes([1, 2, 3, 2, 1, 2, 3, 2, 1]))
    ops, unk, c4t = walk(c)
    assert not unk, [hex(u) for u in unk]
    W = lambda p, n=1: [struct.pack_into('<h', c, p + 2 * i, sc(struct.unpack_from('<h', c, p + 2 * i)[0], S)) for i in range(n)]
    # 標頭
    W(4); W(8, 3)
    for p, t in ops.items():
        if t == 'CE':
            for o in (2, 2 + 0xE, 2 + 0x1A):
                for i in range(3):
                    v = struct.unpack_from('<i', c, p + o + 4 * i)[0]; struct.pack_into('<i', c, p + o + 4 * i, sc(v, S))
        elif t == 'F2':
            f2 = p + 4 + struct.unpack_from('<h', c, p + 2)[0]
            r = struct.unpack_from('<i', c, f2)[0]; struct.pack_into('<i', c, f2, sc(r, S)); W(f2 + 4, 6)
    stat = dict(v=0, pt=0, pt_fix=0, node=0, eye=0, c4=0)
    for p, t in sorted(ops.items()):
        if t == '82':
            n = struct.unpack_from('<H', c, p + 2)[0]; W(p + 6, 3 * n); stat['v'] += n
        elif t == 'FC':
            fl = struct.unpack_from('<H', c, p + 1)[0]
            if not fl & 0x60: continue
            nrm = struct.unpack_from('<3h', c, p + 5); q = p + 11
            if fl & 0x200:
                pt = struct.unpack_from('<3b', c, q); new = [sc(v, S) for v in pt]
                if max(abs(v) for v in new) > 127:
                    # 平面上離原點最近的點：n (n·q) / |n|²
                    nn = sum(k * k for k in nrm); dq = sum(nrm[i] * pt[i] * S for i in range(3))
                    new = [int(round(nrm[i] * dq / nn)) for i in range(3)]
                    assert max(abs(v) for v in new) <= 127, (hex(p), pt, new)
                    stat['pt_fix'] += 1
                struct.pack_into('<3b', c, q, *new)
            else: W(q, 3)
            stat['pt'] += 1
        elif t == '06': W(p + 4); W(p + 8); W(p + 12); stat['node'] += 1
        elif t in ('0C', '0E', '10'): W(p + 4); W(p + 8); stat['node'] += 1
        elif t == '6C':
            if struct.unpack_from('<h', c, p + 2)[0] in (6, 8, 10): W(p + 4); stat['eye'] += 1
        elif t == 'C4': W(p + 2, 3); stat['c4'] += 1
        elif t == '7A': W(p + 2, 3)
        elif t == '78': W(p + 4, 3)
        elif t == 'C8': W(p + 2)
    for t in c4t:
        assert bytes(c[t:t + 2]) == b'\x82\x00'
        W(t - 6, 3)
    if verbose: print('scaled', stat, 'parts', len(c4t))
    return bytes(c)


def scale_file(d, S):
    from kc135_refuel import check_relocs
    d = bytearray(d)
    pe, opt, secs = pe_sections(d); code = next(s for s in secs if s['name'] == 'CODE')
    c = bytearray(d[code['ro']:code['ro'] + code['vs']])
    c2 = scale_code(c, S)
    check_relocs(bytes(d), pe, code, c2)
    d[code['ro']:code['ro'] + code['vs']] = c2
    return bytes(d)


if __name__ == '__main__':
    a = sys.argv[1:]
    S = eval(a[2]) if len(a) > 2 else 4 / 3
    open(a[1], 'wb').write(scale_file(open(a[0], 'rb').read(), S))
