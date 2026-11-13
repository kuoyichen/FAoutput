#!/usr/bin/env python3
"""從 GLB 3D 模型建立新的 F-14 高 LOD 機身，組成 SH（第一版：機身換新，活動零件沿用原本 F14.SH 的）。

做法：
  1. GLB 的機身群組（機身、座艙蓋、雷達罩、外噴嘴）體素化成實心，沿 y 取 16 個剖面，每個剖面取 18 點的環圈（左右對稱），
     接成四邊形；加機鼻尖、兩個 8 邊形噴嘴、垂尾／腹鰭／平尾薄板（geom.py）
  2. 畫面順序：算出「誰可能遮住誰」的圖，沒有環的部分直接照拓撲順序畫，有環才用 06 平面節點切開（bsp.py）
  3. 原本的活動零件（起落架、艙門、可變翼、捕捉勾、後燃器火焰、減速板）當成「物件」放進畫面順序裡，
     控制程式照原檔的 F0 x86 樣式重新組出來（shasm.py）
  4. 取代原檔高 LOD 主體那一段（CODE 0x80～0x3B95），後面整段往前移，修正標頭的相對位移和重定位表
頂點上限：主體 ≤ 371 點（371 以後是零件的頂點）。
用法：python3 f14_glb.py F-14Tomcat_SU_2020.glb SH/F14.SH SHX/F14G.SH
需要：numpy scipy scikit-image
"""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
import numpy as np
from glbload import GLB, voxel_solid
from loft import Sections
from geom import build, GREY
from bsp import Face, Obj, Order, count
from shasm import Asm
from sh_subdivide import pe_sections

R0, R1 = 0x80, 0x3b95            # F14.SH high-LOD main body (82, F6, BSP, part control) up to the first part buffer
HDR_RELS = [0x10, 0x60, 0x68, 0x6c]   # rel16 fields in the header that point past the region
# part buffers in F14.SH (drawn by C4 or called) and the import thunks (CODE offsets)
PARTS = {'speedbrake': 0x3b95, 'wingR': 0x3ca2, 'wingL': 0x403d, 'gearR': 0x43d8, 'gearL': 0x4499,
         'door87': 0x455a, 'nosegear': 0x4605, 'door69': 0x4670, 'hook': 0x4723, 'flames': 0x4766}
VARS = {'AB': 0x7020, 'BRAKE': 0x7026, 'GEARDOWN': 0x702c, 'GEARPOS': 0x7032, 'HOOK': 0x7038, 'SWING': 0x703e, 'RESUME': 0x7044}
MAXV = 371


def main(glb_path, src, dst):
    d = bytearray(open(src, 'rb').read())
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    c = bytes(d[code['ro']:code['ro'] + code['vs']])
    glb = GLB(glb_path)
    sec = Sections(*voxel_solid(glb.body_tris()))
    M = build(glb, sec)
    V = [tuple(int(round(x)) for x in p) for p in M.V]
    # vertex normals for F6 (x, up, fwd), from smooth faces
    VN = [np.zeros(3) for _ in V]
    faces = []
    for ids, col, smooth, nrm in M.F:
        P = [V[i] for i in ids]
        keep = [k for k in range(len(ids)) if P[k] != P[k-1]]
        ids = [ids[k] for k in keep]
        if len(set(V[i] for i in ids)) < 3: continue
        f = Face(ids, [V[i] for i in ids], col, nrm); f.smooth = smooth
        faces.append(f)
        for i in ids:
            if smooth or not VN[i].any(): VN[i] += f.n
    VNl = [list(n) for n in VN]

    def add_vertex(p, i, j, t):       # new vertex from a BSP split: interpolated F6 normal
        V.append(tuple(int(round(x)) for x in p))
        VNl.append(list((1-t)*np.array(VNl[i]) + t*np.array(VNl[j])))
        return len(V) - 1

    objs = make_objs()
    B = Order(V, add_vertex)
    tree = B.build(faces, objs)
    nn, nf = count(tree)
    print(f'畫面順序：{nn} 個 06 節點、{nf} 面、切割 {B.splits} 次；頂點 {len(V)}')
    if len(V) > MAXV: sys.exit(f'頂點 {len(V)} 超過 {MAXV}')

    def assemble(delta):
        a = Asm(R0)
        for k, v in PARTS.items(): a.ext['p_' + k] = v + delta
        for k, v in VARS.items(): a.ext[k] = v + delta
        a.emit(struct.pack('<BBHH', 0x82, 0, len(V), 0))
        for v in V: a.emit(struct.pack('<hhh', *v))
        for i, n in enumerate(VNl):
            n = np.array([n[0], n[2], n[1]]); L = np.linalg.norm(n) or 1
            nb = [int(round(x * 127 / L)) for x in n]
            a.emit(struct.pack('<BHBbbb', 0xF6, i, GREY, *nb))
        emit_tree(a, tree, V)
        a.ret()
        return a.link()

    blob, _ = assemble(0)
    delta = len(blob) - (R1 - R0)
    blob, relocs = assemble(delta)
    nc = bytearray(c[:R0] + blob + c[R1:])
    for p in HDR_RELS:
        struct.pack_into('<h', nc, p, struct.unpack_from('<h', nc, p)[0] + delta)
    room = nxt - code['va']
    print(f'高 LOD 主體 {R1-R0} → {len(blob)} 位元組（{delta:+d}）；CODE {len(nc)} / 上限 {room}')
    if len(nc) > room: sys.exit('CODE 放不下')
    out = rebuild(d, pe, secs, code, nc, delta, relocs)
    open(dst, 'wb').write(out)
    print(f'{dst}: {len(out)} 位元組')


def face_bytes(f, V):
    ids = f.ids; P = [V[i] for i in ids]
    fl = 0x273 if f.smooth else 0x271
    if any(i > 255 for i in ids): fl |= 0x400
    n = f.n; nrm = [int(round(n[0]*32767)), int(round(n[2]*32767)), int(round(n[1]*32767))]
    cen = np.mean(np.array(P, float), 0); pt = [int(round(cen[0])), int(round(cen[2])), int(round(cen[1]))]
    if any(abs(x) > 127 for x in pt): fl &= ~0x200
    b = bytearray(struct.pack('<BHH', 0xFC, fl, f.col)) + struct.pack('<hhh', *nrm)
    b += struct.pack('<bbb', *pt) if fl & 0x200 else struct.pack('<hhh', *pt)
    b.append(len(ids))
    b += b''.join(struct.pack('<H', i) for i in ids) if fl & 0x400 else bytes(ids)
    return bytes(b)


def emit_tree(a, t, V):
    """emit t inline (caller adds ret)"""
    if t[0] == 'list':
        for e in t[1]:
            if isinstance(e, Face): a.emit(face_bytes(e, V))
            else: e.emit(a)
        return
    if t[0] == 'leaf': return
    _, n, d, A, Bt, coF, coB = t
    la, lb, lend = a.new('A'), a.new('B'), a.new('E')
    # n.(eye + dd) with dd = -p : choose p = n*d (closest point), integer
    p = np.array(n) * d
    nn = [int(round(n[0]*32767)), int(round(n[2]*32767)), int(round(n[1]*32767))]
    dd = [-int(round(p[0])), -int(round(p[2])), -int(round(p[1]))]
    a.node3(nn, dd, la, lb)
    a.jmp(lend)
    a.label(la)
    for f in coB: a.emit(face_bytes(f, V))
    emit_tree(a, A, V); a.ret()
    a.label(lb)
    for f in coF: a.emit(face_bytes(f, V))
    emit_tree(a, Bt, V); a.ret()
    a.label(lend)


SAR = lambda k: b'\x66\xC1\xF8' + bytes([k])
NEG = b'\x66\xF7\xD8'
SWING = b'\x66\x8B\xC8' + SAR(2) + b'\x66\xC1\xF9\x06' + b'\x66\x03\xC1'


def make_objs():
    def gear(pos, field, ops, part):
        def e(a):
            a.cond('GEARDOWN', 'RESUME', lambda: a.patch_c4('GEARPOS', field, ops, 'RESUME', lambda: a.c4(pos, (0, 0, 0), part)))
        return e
    def wing(pos, ops, part):
        def e(a): a.patch_c4('SWING', 0x08, ops, 'RESUME', lambda: a.c4(pos, (0, 0, 0), part))
        return e
    def callc(var, part):
        def e(a): a.cond(var, 'RESUME', lambda: a.call(part))
        return e
    O = []
    O.append(Obj('nosegear', (-3, 25, -30), (3, 75, -3), gear((0, -5, 50), 0x0a, SAR(3), 'p_nosegear')))
    O.append(Obj('door87', (-4, 72, -24), (2, 92, -6), gear((-2, -7, 87), 0x0c, SAR(1), 'p_door87')))
    O.append(Obj('door69', (-4, 52, -24), (4, 72, -6), gear((0, -6, 69), 0x0a, SAR(1), 'p_door69')))
    O.append(Obj('gearL', (-36, -10, -26), (-16, 20, -8), gear((-26, 1, 5), 0x0c, SAR(1), 'p_gearL')))
    O.append(Obj('gearR', (16, -10, -26), (36, 20, -8), gear((27, 1, 5), 0x0c, SAR(1) + NEG, 'p_gearR')))
    O.append(Obj('wingR', (21, -48, 3), (96, 28, 5), wing((32, 4, 16), SWING, 'p_wingR')))
    O.append(Obj('wingL', (-96, -48, 3), (-21, 28, 5), wing((-32, 4, 16), SWING + NEG, 'p_wingL')))
    O.append(Obj('hook', (-1, -46, -22), (1, -19, -7), callc('HOOK', 'p_hook')))
    O.append(Obj('flames', (-19, -94, -6), (19, -63, 5), callc('AB', 'p_flames')))
    O.append(Obj('speedbrake', (-8, -54, 5), (8, -43, 18), callc('BRAKE', 'p_speedbrake')))
    return O


def rebuild(d, pe, secs, code, nc, delta, new_relocs):
    rel = next(s for s in secs if s['name'] == '.reloc')
    rdir = pe + 24 + 96 + 8*5; rva, rsz = struct.unpack_from('<II', d, rdir)
    ents, p = [], rel['ro'] + (rva - rel['va'])
    while p < rel['ro'] + (rva - rel['va']) + rsz:
        page, sz = struct.unpack_from('<II', d, p)
        if sz < 8: break
        for k in range((sz-8)//2):
            e = struct.unpack_from('<H', d, p+8+2*k)[0]
            if e >> 12: ents.append(page + (e & 0xFFF))
        p += sz
    cva = code['va']; out_r = []
    for r in ents:
        off = r - cva
        if not 0 <= off < code['vs']: out_r.append(r); continue
        if R0 <= off < R1: continue                 # old region: dropped
        if off >= R1: off += delta
        val = struct.unpack_from('<I', nc, off)[0] - cva
        if R0 <= val < R1: sys.exit(f'reloc at {off:#x} points into the replaced region')
        if R1 <= val < code['vs']: struct.pack_into('<I', nc, off, val + delta + cva)   # CODE targets only (IAT stays)
        out_r.append(off + cva)
    out_r += [o + cva for o in new_relocs]
    tbl = bytearray(); pages = {}
    for r in sorted(out_r): pages.setdefault(r & ~0xFFF, []).append((3 << 12) | (r & 0xFFF))
    for pg, es in sorted(pages.items()):
        if len(es) % 2: es.append(0)
        tbl += struct.pack('<II', pg, 8 + 2*len(es)) + b''.join(struct.pack('<H', e) for e in es)
    if len(tbl) > rel['rs']: sys.exit('reloc table too big')
    falign = struct.unpack_from('<I', d, pe+24+36)[0]
    new_rs = (len(nc) + falign - 1) // falign * falign
    shift = new_rs - code['rs']
    out = bytearray(d[:code['ro']]) + nc + b'\x00' * (new_rs - len(nc))
    for s in sorted(secs, key=lambda s: s['ro']):
        if s['ro'] > code['ro']: out += d[s['ro']:s['ro']+s['rs']]
    out += d[max(s['ro']+s['rs'] for s in secs):]
    struct.pack_into('<I', out, code['hdr']+8, len(nc)); struct.pack_into('<I', out, code['hdr']+16, new_rs)
    for s in secs:
        if s['ro'] > code['ro']: struct.pack_into('<I', out, s['hdr']+20, s['ro'] + shift)
    soc = struct.unpack_from('<I', out, pe+24+4)[0]; struct.pack_into('<I', out, pe+24+4, soc + shift)
    rel_ro = rel['ro'] + shift + (rva - rel['va'])
    out[rel_ro:rel_ro + rel['rs']] = b'\x00' * rel['rs']
    out[rel_ro:rel_ro + len(tbl)] = tbl
    struct.pack_into('<I', out, rdir + 4, len(tbl))
    return bytes(out)


if __name__ == '__main__':
    if len(sys.argv) != 4: sys.exit(__doc__)
    main(*sys.argv[1:4])
