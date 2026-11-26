"""Standard single-SH upgrade chain used by the later aircraft (mass-upgrade thread):
[morph] -> stores (configured from one PT) -> pre-clear old gear art -> animated afterburner on every textured
stock plume (f16.flame_parts) -> 3D gear.  Writes OUT/<name>.SH and OUT/_<pic>.PIC."""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)


def chain(src, pic, out, name, picname, pt=None, extra=None, parts=None, gear=None, flame=None, rm=12, rn=9,
          keep_old=False, morph=None, flame_at=None, stub=None):
    import up_stores, up_gear, up_ab2, f16
    from f14_gear import read_pic, put
    from sh_inspect import load
    os.makedirs(out, exist_ok=True)
    cur = src
    if morph:
        import morph as M
        warp, abs_, lods = morph
        m0 = os.path.join(out, name + '_m0.SH'); M.apply(src, m0, warp, abs_); M.remap(src, m0, warp, lods); cur = m0
    if pt:
        s1 = os.path.join(out, name + '_s1.SH'); up_stores.run(cur, pt, s1, extra); cur = s1
    pre = up_gear.auto_hubs(cur, pic, parts, rm=rm, rn=rn, keep_old=keep_old)['clear'] if parts else []
    pb = bytearray(open(pic, 'rb').read()); P = read_pic(pb)
    for a in pre:
        for y in range(a[1], a[3] + 1):
            for x in range(a[0], a[2] + 1): put(pb, P, x, y, 255)
    cpic = os.path.join(out, name + '_p0.PIC'); open(cpic, 'wb').write(pb)
    if flame:
        from up_ab import free_slots
        if len(free_slots(cur, cpic, ignore=pre)) < 3 and len(free_slots(cur, cpic, need_ff=False, ignore=pre)) < 3:
            pic_grow(cpic, cpic, 62); print('PIC grown by 62 rows for the flame frames')
        _, _, _, _, c = load(cur)
        def tex(t):
            p = t + 6 + 6 * struct.unpack_from('<H', c, t + 2)[0]
            while c[p] in (0x6C, 0x38): p += 10 if c[p] == 0x6C else 3
            return c[p] == 0xFC and struct.unpack_from('<H', c, p + 1)[0] & 4
        slots = None
        fl = flame_at or flames(cur); fl = [t for t in fl if tex(t)] or fl
        for k, old in enumerate(fl):
            ns, np_ = os.path.join(out, name + '_f%d.SH' % k), os.path.join(out, name + '_f%d.PIC' % k)
            slots = up_ab2.run(cur, cpic, ns, np_, old=old, length=flame, ignore=pre, slots=slots); cur, cpic = ns, np_
    dst, pdst = os.path.join(out, name + '.SH'), os.path.join(out, '_' + picname + '.PIC')
    if stub:                                         # static gear block -> stub parts in the body frame
        g0 = os.path.join(out, name + '_g0.SH'); parts = stub_parts(cur, g0, list(gear)); cur = g0
    if parts:
        spec = dict(parts=parts, gear=gear, strip=None)
        if stub: spec['span_end'] = {k: v + 14 for k, v in parts.items()}
        h = up_gear.auto_hubs(cur, cpic, parts, rm=rm, rn=rn, keep_old=True); h['clear'] = []
        if stub: h.pop('span_end')
        spec.update(h)
        up_gear.run(cur, cpic, dst, pdst, spec)
    else:
        import shutil; shutil.copy(cur, dst); shutil.copy(cpic, pdst)
    return dst, pdst


def render(sh, pic, png, extra_vars=None):
    import shview as V
    v = {'_PLgearPos': 0, '_PLgearDown': 1, '_PLafterBurner': 1}; v.update(extra_vars or {})
    V.views(sh, pic, png, vars=v, vlist=[(1.5708, 0.0), (0.6, -0.35), (0, 0), (-0.7, 0.45)], W=560, H=340)


def pic_grow(src, dst, add):
    """Add `add` blank (0xFF) texture rows below the last one (v = h .. h+add-1); every existing v stays."""
    d = open(src, 'rb').read(); w, h = struct.unpack_from('<II', d, 2); rt = struct.unpack_from('<I', d, 0x22)[0]
    rows = [d[struct.unpack_from('<I', d, rt + 4 * r)[0]:][:w] for r in range(h)]       # file order, r = h-1-v
    H = h + add; rows = [b'\xff' * w] * add + rows
    hdr = bytearray(d[:0x40])
    struct.pack_into('<I', hdr, 6, H); struct.pack_into('<I', hdr, 14, H * w); struct.pack_into('<I', hdr, 0x1e, 10 * (H + 1))
    struct.pack_into('<I', hdr, 0x22, 0x40 + H * w); struct.pack_into('<I', hdr, 0x26, 4 * H)
    tbl = b''.join(struct.pack('<I', 0x40 + r * w) for r in range(H))
    open(dst, 'wb').write(bytes(hdr) + b''.join(rows) + tbl)


def flames(path):
    """Every stock plume: F0 (cmp _PLafterBurner) -> 12 00 rel -> 82 of 8 / 12 / 16 points (16 = sh_ab_flame type)."""
    from sh_inspect import load, thunks
    d, pe, secs, code, c = load(path)
    th = thunks(d, secs, code, c)
    ab = struct.pack('<I', 0x1000 + next(k for k, v in th.items() if v == '_PLafterBurner'))
    out = []; q = -1
    while True:
        q = c.find(ab, q + 1)
        if q < 0: break
        if c[q - 5:q - 3] != b'\xf0\x00' or c[q + 7] != 0x68: continue
        on = struct.unpack_from('<I', c, q + 8)[0] - 0x1000
        if c[on:on + 2] != b'\x12\x00': continue
        t = on + 4 + struct.unpack_from('<h', c, on + 2)[0]
        if c[t] == 0x82 and struct.unpack_from('<H', c, t + 2)[0] in (8, 12, 16, 24, 32) and t not in out: out.append(t)
    return out


def static_gear_block(path, nverts=None):
    """82 of the stock gear when it is not a C4 part but one block under F0 (cmp _PLgearDown) -> 12 00 rel (F-111, B-1)."""
    from sh_inspect import load, thunks
    d, pe, secs, code, c = load(path)
    th = thunks(d, secs, code, c)
    gd = struct.pack('<I', 0x1000 + next(k for k, v in th.items() if v == '_PLgearDown'))
    q = c.find(gd); on = struct.unpack_from('<I', c, q + 8)[0] - 0x1000
    assert c[on:on + 2] == b'\x12\x00'
    t = on + 4 + struct.unpack_from('<h', c, on + 2)[0]
    assert c[t] == 0x82 and (nverts is None or struct.unpack_from('<H', c, t + 2)[0] == nverts), hex(t)
    return t


HEADER = bytes.fromhex('cb003300e200')


def stub_parts(src, dst, keys, t=None):
    """Rewrite the start of a static gear block into gosubs to one empty stub part per gear (6-byte range header +
    empty 82, 20 bytes each) that up_gear then turns into 3D gear drawn in the body frame."""
    from sh_inspect import load
    d, pe, secs, code, c = load(src); d = bytearray(d); ro = code['ro']
    t = t if t is not None else static_gear_block(src)
    head = (4 * len(keys) + 1 + 3) // 4 * 4 + 2           # stub 82 lands 6 bytes into its 20-byte slot
    parts = {k: t + head + 6 + 20 * i for i, k in enumerate(keys)}
    blk = bytearray()
    for i, k in enumerate(keys):
        blk += b'\x12\x00' + struct.pack('<h', parts[k] - (t + 4 * i + 4))
    blk += b'\x1e'; blk += bytes(head - len(blk))
    for k in keys: blk += HEADER + b'\x82\x00\x00\x00\x00\x00' + bytes(8)
    n = struct.unpack_from('<H', c, t + 2)[0]
    assert len(blk) <= 6 + 6 * n, (len(blk), n)
    d[ro + t:ro + t + len(blk)] = blk
    open(dst, 'wb').write(d)
    return parts
