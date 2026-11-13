#!/usr/bin/env python3
"""把 FA 的 SH 模型裡較大的貼圖面細分（1 → 4），新點的 UV 照比例內插，產生點數更多、貼圖不變的 SH。

做法（不移動原本任何指令，所以原檔裡所有相對位移、x86 程式、重定位都不用改）：
  * 新的資料插在 CODE 裡的簽章 01 02 03 02 01 02 03 02 01 之前：FA.EXE 的 SH 載入程式（0x41EB1E）只複製到這個
    簽章為止，簽章後面（匯入跳板 ff 25 …）當成變數區。所以簽章和後面的跳板整段往後移，並用 .reloc 修正所有
    指到這段的絕對位址（第一版把資料放在簽章後面，FA 一畫外部視角就當機）
  * CODE 的虛擬位址可以長到 .idata 之前（F14 約有 4 KB 空間）
  * 每個要細分的面：原位置改成 `12 00 rel16`（呼叫新區塊）+ `38 rel16`（跳過原本面剩下的位元組），其餘填 1E
  * 新區塊：`82 00 n target` 載入新增的點（放在頂點表 480 以後的位置），接著 4 個子面，最後 `00 00` 返回
FA.EXE 的 SH 解譯器（指令表在 0x5183A0）：12 = 呼叫 rel16（相對於 rel16 之後）、38 = 跳躍 rel16、00 = 返回、
82 = 載入頂點 (u16 n, u16 位置×8, n×(x,y,z) i16)、FC = 面（見 sh_texture.html 的說明）。頂點表最多 900 點。
用法：python3 sh_subdivide.py SH/F14.SH out/F14X.SH [面數上限]
"""
import struct, sys

MAX_VERT = 900
FACE_OPS = {0x41,0x44,0x49,0x4C,0x51,0x54,0x59,0x5C,0x61,0x63,0x64,0x69,0x6B,0x6C,0x71,0x73,0x7C,0xCD,0xDD,0xED,0xEE,0xFE,0xFD,0x74}

def pe_sections(d):
    pe = struct.unpack_from('<I', d, 0x3C)[0]; ns = struct.unpack_from('<H', d, pe+6)[0]; opt = struct.unpack_from('<H', d, pe+20)[0]
    secs = []
    for i in range(ns):
        s = pe+24+opt+i*40
        name = d[s:s+8].rstrip(b'\0').decode('latin1'); vs, va, rs, ro = struct.unpack_from('<IIII', d, s+8)
        secs.append(dict(hdr=s, name=name, vs=vs, va=va, rs=rs, ro=ro))
    return pe, opt, secs

def parse_face(c, o):
    """回傳 dict 或 None；格式照 FA.EXE 0x4D43DC 的 FC 處理程式。"""
    if c[o] != 0xFC: return None
    fl, col = struct.unpack_from('<HH', c, o+1)
    p = o + 5
    if fl & 0x60: p += 9 if fl & 0x200 else 12
    hdr_end = p
    n = c[p]; p += 1
    if n < 3 or n > 16: return None
    wide = fl & 0x400
    idx = [struct.unpack_from('<H', c, p+2*k)[0] if wide else c[p+k] for k in range(n)]
    p += n * (2 if wide else 1)
    uv = None
    if fl & 4:
        if fl & 0x100: uv = [(c[p+2*k], c[p+2*k+1]) for k in range(n)]; p += 2*n
        else: uv = [struct.unpack_from('<HH', c, p+4*k) for k in range(n)]; p += 4*n
    return dict(o=o, end=p, fl=fl, col=col, head=bytes(c[o+1:hdr_end]), n=n, idx=idx, uv=uv)

def main_lod(c):
    """第一個 LOD：第一個 target 0 的頂點緩衝，接著同一 LOD 的延續緩衝（同 sh_gallery.html 的做法，簡化版）。"""
    bufs = []
    for o in range(len(c)-6):
        if c[o] != 0x82 or c[o+1] != 0: continue
        n, t = struct.unpack_from('<HH', c, o+2); e = o+6+6*n
        if not n or n > 4000 or t % 8 or e >= len(c): continue
        if not bufs:
            if t == 0 and n >= 3: bufs.append((o, n, 0, e))
            continue
        lo, ln, lt, le = bufs[-1]
        if t == 0 and o >= le and c[o-1] in (0, 0x1E): bufs.append((o, n, -1, e)); break
        if o >= le and t//8 == lt + ln: bufs.append((o, n, t//8, e))
    return bufs

def main():
    src, dst = sys.argv[1], sys.argv[2]; limit = int(sys.argv[3]) if len(sys.argv) > 3 else 999
    d = bytearray(open(src, 'rb').read())
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    c = bytearray(d[code['ro']:code['ro']+code['vs']])
    room = nxt - code['va'] - len(c)
    bufs = main_lod(c)
    main_o, main_n, _, main_e = bufs[0]
    stop = next((b[0] for b in bufs if b[2] < 0), None) or (bufs[1][0] if len(bufs) > 1 else len(c))
    used = max(b[2] + b[1] for b in bufs if b[2] >= 0)
    V = {}
    for (o, n, t, e) in bufs:
        if t < 0: continue
        for k in range(n): V[t+k] = struct.unpack_from('<hhh', c, o+6+6*k)
    # 主體 LOD 裡有貼圖、只用主體點的面
    faces, o = [], main_e
    while o < stop - 6:
        f = parse_face(c, o) if c[o] == 0xFC else None
        ok = f and ((f['fl'] & 0x200 and not f['fl'] & 0xF000 and (f['fl'] & 0xFF) in FACE_OPS) or (not f['fl'] & 0x200 and (f['fl'] & 0xFF) in FACE_OPS and f['fl'] < 0x1000))
        if ok and all(i < main_n for i in f['idx']) and len(set(f['idx'])) == f['n'] and f['end'] <= stop:
            faces.append(f); o = f['end']; continue
        o += 1
    def area(f):
        P = [V[i] for i in f['idx']]; a = [0, 0, 0]
        for k in range(len(P)):
            p, q = P[k], P[(k+1) % len(P)]
            a[0] += p[1]*q[2]-p[2]*q[1]; a[1] += p[2]*q[0]-p[0]*q[2]; a[2] += p[0]*q[1]-p[1]*q[0]
        return (a[0]**2+a[1]**2+a[2]**2) ** 0.5
    cand = sorted([f for f in faces if f['uv'] and f['n'] in (3, 4) and f['end'] - f['o'] >= 7], key=area, reverse=True)
    base = max(used, 480)
    nextv = base; blocks = bytearray(); patches = []; done = 0
    SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])
    tail = bytes(c).find(SIG)
    if tail < 0: sys.exit('找不到 CODE 結尾簽章')
    for f in cand[:limit]:
        P = [V[i] for i in f['idx']]; U = f['uv']; n = f['n']
        mid = lambda a, b: tuple(round((a[k]+b[k])/2) for k in range(len(a)))
        nv = [mid(P[k], P[(k+1) % n]) for k in range(n)]; nu = [mid(U[k], U[(k+1) % n]) for k in range(n)]
        if n == 4:
            nv.append(tuple(round(sum(p[k] for p in P)/4) for k in range(3))); nu.append(tuple(round(sum(u[k] for u in U)/4) for k in range(2)))
        if nextv + len(nv) > MAX_VERT: break
        ids = [nextv + k for k in range(len(nv))]
        a, b, cc = f['idx'][0], f['idx'][1], f['idx'][2]
        if n == 3:
            m0, m1, m2 = ids
            subs = [([a, m0, m2], [U[0], nu[0], nu[2]]), ([m0, b, m1], [nu[0], U[1], nu[1]]), ([m2, m1, cc], [nu[2], nu[1], U[2]]), ([m0, m1, m2], [nu[0], nu[1], nu[2]])]
        else:
            dd = f['idx'][3]; m0, m1, m2, m3, e = ids
            subs = [([a, m0, e, m3], [U[0], nu[0], nu[4], nu[3]]), ([m0, b, m1, e], [nu[0], U[1], nu[1], nu[4]]),
                    ([e, m1, cc, m2], [nu[4], nu[1], U[2], nu[2]]), ([m3, e, m2, dd], [nu[3], nu[4], nu[2], U[3]])]
        blk = bytearray(struct.pack('<BBHH', 0x82, 0, len(nv), ids[0]*8))
        for p in nv: blk += struct.pack('<hhh', *p)
        fl = f['fl'] | 0x400
        for idx, uv in subs:
            head = bytearray(f['head']); struct.pack_into('<H', head, 0, fl)
            blk += bytes([0xFC]) + head + bytes([len(idx)]) + b''.join(struct.pack('<H', i) for i in idx)
            blk += b''.join(bytes(u) if fl & 0x100 else struct.pack('<HH', *u) for u in uv)
        blk += b'\x00\x00'
        if room - len(blocks) - len(blk) < 0: break
        start = tail + len(blocks); blocks += blk; nextv += len(nv); done += 1
        patches.append((f, start))
    for f, start in patches:
        o = f['o']
        patch = bytearray(b'\x12\x00') + struct.pack('<h', start - (o + 4))
        patch += b'\x38' + struct.pack('<h', f['end'] - (o + 7))
        patch += b'\x1e' * (f['end'] - o - len(patch))
        c[o:f['end']] = patch
    L = len(blocks)
    c = c[:tail] + blocks + c[tail:]
    # 重定位：位置或目標在簽章之後的都往後移 L
    rel = next(s for s in secs if s['name'] == '.reloc')
    rdir = pe + 24 + 96 + 8*5; rva, rsz = struct.unpack_from('<II', d, rdir)
    ents, p = [], rel['ro'] + (rva - rel['va'])
    while p < rel['ro'] + (rva - rel['va']) + rsz:
        page, sz = struct.unpack_from('<II', d, p)
        if sz < 8: break
        for k in range((sz-8)//2):
            e = struct.unpack_from('<H', d, p+8+2*k)[0]
            if e >> 12: ents.append((e >> 12, page + (e & 0xFFF)))
        p += sz
    cut = code['va'] + tail; cend = code['va'] + code['vs']
    new_ents = []
    for t, r in ents:
        if code['va'] <= r < cend:
            if r >= cut: r += L
            off = r - code['va']; val = struct.unpack_from('<I', c, off)[0]
            if cut <= val < cend: struct.pack_into('<I', c, off, val + L)
        new_ents.append((t, r))
    # 其他區段裡指到簽章後面的絕對位址（理論上沒有，檢查一下）
    for t, r in ents:
        if not code['va'] <= r < cend:
            sec = next(x for x in secs if x['va'] <= r < x['va'] + max(x['vs'], x['rs']))
            val = struct.unpack_from('<I', d, sec['ro'] + r - sec['va'])[0]
            if cut <= val < cend: sys.exit('有區段外的重定位指到簽章後面，未處理')
    tbl = bytearray(); pages = {}
    for t, r in sorted(new_ents, key=lambda x: x[1]): pages.setdefault(r & ~0xFFF, []).append((t << 12) | (r & 0xFFF))
    for pg, es in sorted(pages.items()):
        if len(es) % 2: es.append(0)
        tbl += struct.pack('<II', pg, 8 + 2*len(es)) + b''.join(struct.pack('<H', e) for e in es)
    if len(tbl) > rel['rs'] - (rva - rel['va']): sys.exit('重定位表放不下')
    # 重新組檔：CODE 變長，後面區段的檔案位置往後移（虛擬位址不變）
    falign = struct.unpack_from('<I', d, pe+24+36)[0]
    new_rs = (len(c) + falign - 1) // falign * falign
    shift = new_rs - code['rs']
    out = bytearray(d[:code['ro']]) + c + b'\x00' * (new_rs - len(c))
    for s in sorted(secs, key=lambda s: s['ro']):
        if s['ro'] > code['ro']: out += d[s['ro']:s['ro']+s['rs']]
    out += d[max(s['ro']+s['rs'] for s in secs):]
    struct.pack_into('<I', out, code['hdr']+8, len(c)); struct.pack_into('<I', out, code['hdr']+16, new_rs)
    for s in secs:
        if s['ro'] > code['ro']: struct.pack_into('<I', out, s['hdr']+20, s['ro'] + shift)
    soc = struct.unpack_from('<I', out, pe+24+4)[0]; struct.pack_into('<I', out, pe+24+4, soc + shift)
    # 寫回新的重定位表（區段位置已經移過）
    rel_ro = rel['ro'] + shift + (rva - rel['va'])
    out[rel_ro:rel_ro + rsz] = b'\x00' * rsz
    out[rel_ro:rel_ro + len(tbl)] = tbl
    struct.pack_into('<I', out, rdir + 4, len(tbl))
    open(dst, 'wb').write(out)
    print(f'{src}: 主體 {main_n} 點，細分 {done} 個貼圖面，新增 {nextv-base} 點（頂點表用到 {nextv}/{MAX_VERT}），CODE {code["vs"]:#x} → {len(c):#x}（上限 {nxt-code["va"]:#x}）')

if __name__ == '__main__': main()
