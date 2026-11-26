#!/usr/bin/env python3
"""F-111F / F-111C Aardvark (F111.SH) and EF-111A Raven (E111.SH) upgrade (mass-upgrade thread, 2026-11-26).
Stock shapes are to scale (73 ft long, 63 ft spread span).  Steps:
 PT -> F111C gets the F111 station layout (both PTs share F111.SH; the rarely used outer fixed x 65 station goes)
 -> stores: only the centreline and the inboard pivot pylon (x 29, next to the wing pivot) are drawn: the outer
    pylons ride on the swinging panel, which FA turns about the pivot, so a store drawn there would hang in the
    air once the wing sweeps.  The EF-111 has no stations.
 -> animated afterburner (TF30, both nozzles; LOD1 too)
 -> 3D gear.  The stock gear is not a C4 part but one static block under _PLgearDown (flat billboards); its start
    is rewritten into three gosubs to three stub parts that up_gear then turns into the new gear: big single main
    wheels on trailing legs outboard, twin nose wheels.
Usage: f111.py OUTDIR"""
import os, sys, struct, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
from pt_edit import set_station
from sh_inspect import load, thunks

HEADER = bytes.fromhex('cb003300e200')


def make_pt(name, dst):
    t = open(os.path.join(ROOT, 'PT', name + '.PT'), encoding='latin1', newline='').read()
    if name == 'F111C':
        rows = [(4, 0x1401, 0, -12, -18, None, 1, 1, 1), (5, 0x17e5, 29, -12, -4, 'AGM84A.JT', 23, 2, 4),
                (6, 0x17e5, 41, -12, -8, 'GBU10.JT', 23, 2, 4), (7, 0x85, 44, -8, -8, 'AIM9M.JT', 4, 2, 4),
                (8, 0x17e5, 54, -12, -13, None, 23, 2, 4)]
        import re
        for r in rows:
            mw = re.search(r';-------- hardpoint %d\r?\n(?:.*\r?\n){8}.*\r?\n\s*byte (\d+)' % r[0], t)
            r = r[:6] + ((int(mw.group(1)) if mw else r[6]),) + r[7:]
            t = set_station(t, *r)
    open(dst, 'w', encoding='latin1', newline='').write(t)


def stores_extra(S):
    for k in (S.AIM54, S.AIM7, S.AAM): S.SHAPES[k] = S.SHAPES[S.AIM9]
    S.SHAPES[S.JDAM] = S.SHAPES[S.LGB]
    for k in list(S.SLOTS):
        if k[1:] not in ('4', '5'): del S.SLOTS[k]          # outer pylons swing with the wing panel
    S.FALL_SLOTS = {k: i for i, k in enumerate([k for k in ('R5', 'L5') if k in S.SLOTS])}


def main_flames(path):
    """LOD0 flame: F0 (cmp _PLafterBurner) -> 12 00 rel -> 16-point 82 (both nozzles)."""
    d, pe, secs, code, c = load(path)
    th = thunks(d, secs, code, c)
    ab = struct.pack('<I', 0x1000 + next(k for k, v in th.items() if v == '_PLafterBurner'))
    out = []; q = -1
    while True:
        q = c.find(ab, q + 1)
        if q < 0: break
        on = struct.unpack_from('<I', c, q + 8)[0] - 0x1000
        if c[on:on + 2] != b'\x12\x00': continue
        t = on + 4 + struct.unpack_from('<h', c, on + 2)[0]
        if c[t] == 0x82 and struct.unpack_from('<H', c, t + 2)[0] == 16: out.append(t)
    return out


def gear_block(path):
    d, pe, secs, code, c = load(path)
    th = thunks(d, secs, code, c)
    gd = struct.pack('<I', 0x1000 + next(k for k, v in th.items() if v == '_PLgearDown'))
    q = c.find(gd); on = struct.unpack_from('<I', c, q + 8)[0] - 0x1000
    assert c[on:on + 2] == b'\x12\x00'
    t = on + 4 + struct.unpack_from('<h', c, on + 2)[0]
    assert c[t] == 0x82 and struct.unpack_from('<H', c, t + 2)[0] == 42, hex(t)
    return t


def stub_parts(src, dst):
    """Old gear block start -> gosub R, L, N stubs (each a 6-byte range header + empty 82, 20 bytes apiece)."""
    d, pe, secs, code, c = load(src); d = bytearray(d); ro = code['ro']
    t = gear_block(src)
    parts = {'R': t + 20, 'L': t + 40, 'N': t + 60}
    blk = bytearray()
    for i, s in enumerate('RLN'):
        at = t + 4 * i
        blk += b'\x12\x00' + struct.pack('<h', parts[s] - (at + 4))
    blk += b'\x1e'
    blk += bytes(14 - len(blk) + 0)
    for s in 'RLN':
        blk += HEADER + b'\x82\x00\x00\x00\x00\x00' + bytes(8)
    assert len(blk) == 74 - 0 and t + 6 * 42 > t + len(blk)
    d[ro + t:ro + t + len(blk)] = blk
    open(dst, 'wb').write(d)
    return parts


def gear_spec(sh, pic, parts):
    import up_gear as U
    m = lambda s: dict(top=(9 * s, 2, -9), bot=(11 * s, -3, -15), wheel=(14 * s, -3, -15), r=6, w=(-2, 2), sr=1.1,
                       braces=[((10 * s, 0, -12), (6 * s, 12, -9))])
    g = {'R': m(1), 'L': m(-1),
         'N': dict(top=(0, 84, -9), bot=(0, 84, -18), wheel=(0, 84, -18), r=3, w=(-1, 1), twin=3, sr=0.9,
                   braces=[((0, 84, -13), (0, 92, -9))])}
    spec = dict(parts=parts, gear=g, strip=None, span_end={k: v + 14 for k, v in parts.items()})
    h = U.auto_hubs(sh, pic, parts, rm=10, rn=8)
    spec.update(hub_main=h['hub_main'], hub_nose=h['hub_nose'], clear=[])
    return spec


def build(out):
    os.makedirs(out, exist_ok=True)
    import up_stores, up_gear, up_ab, up_ab2, f16
    for p in ('F111', 'F111C', 'EF111'): make_pt(p, os.path.join(out, p + '.PT'))
    for sh in ('F111', 'E111'):
        src = os.path.join(ROOT, 'SH', sh + '.SH'); pic = os.path.join(ROOT, 'PIC', '_' + sh + '.PIC')
        cur = src
        if sh == 'F111':
            tpl = os.path.join(out, 'layout.PT'); t = open(os.path.join(out, 'F111.PT'), encoding='latin1', newline='').read()
            for i in (6, 7, 8): t = set_station(t, i, 8, 0, 0, 0, None, 0, 1, 1)      # swinging-panel stations: not drawn
            open(tpl, 'w', encoding='latin1', newline='').write(t)
            cur = os.path.join(out, sh + '_s1.SH'); up_stores.run(src, tpl, cur, stores_extra)
        cpic = pic; slots = None
        for k, old in enumerate(main_flames(cur)):
            ns, np_ = os.path.join(out, sh + '_a%d.SH' % k), os.path.join(out, sh + '_a%d.PIC' % k)
            slots = up_ab2.run(cur, cpic, ns, np_, old=old, length=70, slots=slots); cur, cpic = ns, np_
        _, _, _, _, c = load(cur)
        tex = lambda t: struct.unpack_from('<H', c, t + 6 + 6 * struct.unpack_from('<H', c, t + 2)[0] + 1)[0] & 4
        try: fl = [t for t in f16.flame_parts(cur) if tex(t)]
        except AssertionError: fl = []
        print(sh, 'LOD1 textured flames', [hex(x) for x in fl])
        for k, old in enumerate(fl):
            ns, np_ = os.path.join(out, sh + '_f%d.SH' % k), os.path.join(out, sh + '_f%d.PIC' % k)
            slots = up_ab2.run(cur, cpic, ns, np_, old=old, length=70, slots=slots); cur, cpic = ns, np_
        g0 = os.path.join(out, sh + '_g0.SH'); parts = stub_parts(cur, g0)
        up_gear.run(g0, cpic, os.path.join(out, sh + '.SH'), os.path.join(out, '_' + sh + '.PIC'), gear_spec(g0, cpic, parts))


if __name__ == '__main__':
    build(sys.argv[1])
