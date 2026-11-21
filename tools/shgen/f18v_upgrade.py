#!/usr/bin/env python3
"""Carry the F18.SH upgrades (F18-23) over to the other F/A-18 shapes (F18C, F18E, F18F, F18T, F18U), Kuoyi 2026-11-21.

Same four steps, in the same order as F18.SH was built:
  1. stores     f18_stores.py, but the slots, pylons and falling-tank slots come from the variant's own .PT
                (every hardpoint with a position: centreline -> one slot, symmetrical -> right/left pair; pylons
                on wing and centreline stations, fitted from the store top up into the wing / belly surface)
  2. afterburner sh_ab_flame.py <variant profile> --grow 3000
  3. gear       f18_gear.py (address set picked per layout: F18/F/U or C/E/T)
  4. wing fold  f18_wing_fold.py; hinge |x| = max(44, outermost wing station + 2, flap end + 1), so wing stores stay on the
                fixed wing; the wingtip station folds with the panel
Usage: python3 f18v_upgrade.py VARIANT in.SH in.PIC in.PT out.SH out.PIC [folded_preview.SH]
Every step keeps the file < 65536 bytes and the vertex table <= 900 (asserted by the steps themselves).
"""
import os, re, struct, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sh_subdivide import pe_sections, parse_face, main_lod
import f18_stores as S
import f18_wing_fold as W


# ---------------------------------------------------------------- .PT hardpoints
def pt_hards(path):
    t = open(path, encoding='latin1').read().replace('\r', '')
    names = dict(re.findall(r'\n:(defaultTypeName\d+)\n\s*string "([^"]*)"', t))
    body = t[t.index('\n:hards'):].split('\n')[2:]
    hps, cur = [], None
    for l in body:
        l = l.strip()
        if l.startswith(';-------- hardpoint'): cur = []; hps.append(cur); continue
        if l.startswith(':'): break
        if cur is None or not l or l.startswith(';'): continue
        cur.append(l.split(None, 1)[1])
    num = lambda s: int(s.replace('$', '0x'), 0)
    out = []
    for i, h in enumerate(hps):
        fl, x, u, f = (num(h[k]) for k in range(4))
        dn = names.get(h[8]) if not h[8][0].isdigit() else None
        out.append(dict(i=i, fl=fl, x=x, u=u, f=f, default=dn, count=num(h[10]), loc=num(h[11])))
    return out


def jt_kind(fname):
    """Store kind of a default .JT / .GAS name, by the short name FA reads at run time (same table as the x86)."""
    if fname is None: return S.NONE
    if fname.upper().endswith('.GAS'): return S.TANK
    p = os.path.join(HERE, '..', '..', 'JT', fname)
    alt = [n for n in os.listdir(os.path.dirname(p)) if n.upper() == fname.upper()]
    if not alt: return S.GENERIC
    t = open(os.path.join(os.path.dirname(p), alt[0]), encoding='latin1').read()
    short = re.search(r':ot_names\s*\n\s*string "([^"]*)"', t).group(1).encode()
    for pre, nxt, k in S.NAMES:
        if short.startswith(pre) and (nxt is None or short[len(pre):len(pre)+1] == nxt): return k
    return S.GENERIC


# ---------------------------------------------------------------- geometry: surfaces above a point
def main_polys(d):
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE')
    c = d[code['ro']:code['ro'] + code['vs']]
    L = main_lod(c); at, n = L[0][0], L[0][1]; end = L[1][0]
    V = [struct.unpack_from('<3h', c, at + 6 + 6 * k) for k in range(n)]   # x, fwd, up
    P, p = [], at + 6 + 6 * n
    while p < end:
        if c[p] == 0xFC:
            f = parse_face(c, p)
            if f and all(i < n for i in f['idx']) and f['end'] <= end:
                P.append([V[i] for i in f['idx']]); p = f['end']; continue
        p += 1
    return P


def ups_at(P, x, f):
    """Heights of every surface crossing the vertical line (x, fwd)."""
    out = []
    for poly in P:
        k = len(poly)
        for j in range(1, k - 1):                      # fan triangles
            a, b, c = poly[0], poly[j], poly[j + 1]
            den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if den == 0: continue
            l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (f - c[1])) / den
            l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (f - c[1])) / den
            l3 = 1 - l1 - l2
            if min(l1, l2, l3) >= -1e-6:
                out.append(l1 * a[2] + l2 * b[2] + l3 * c[2]); break
    return out


def under(P, x, f, above):
    """Lowest surface above height `above` at (x, fwd), or None."""
    u = [v for v in ups_at(P, x, f) if v > above]
    return min(u) if u else None


def chord(P, x, above, near):
    """Fwd range (LE, TE) of the surface just above `above` at span x, near height `near` (the wing)."""
    fs = [f for f in range(90, -60, -1) if (lambda v: v is not None and abs(v - near) < 3)(under(P, x, f, above))]
    return (max(fs), min(fs)) if fs else None


NOSE_GAP = 2                                           # fuselage AIM-120 nose this far behind the intake lip


def intake_lip(d):
    """Front of the intake mouth: lowest fwd of the forward-facing main-LOD faces at x 3..20 below up 4."""
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE')
    c = d[code['ro']:code['ro'] + code['vs']]
    L = main_lod(c); at, n = L[0][0], L[0][1]; end = L[1][0]
    V = [struct.unpack_from('<3h', c, at + 6 + 6 * k) for k in range(n)]
    out, p = [], at + 6 + 6 * n
    while p < end:
        if c[p] == 0xFC:
            f = parse_face(c, p)
            if f and all(i < n for i in f['idx']) and f['end'] <= end:
                fl = struct.unpack_from('<H', c, p + 1)[0]
                P = [V[i] for i in f['idx']]
                if fl & 0x60 and struct.unpack_from('<h', c, p + 9)[0] > 20000 and min(q[0] for q in P) >= 3 \
                        and max(q[0] for q in P) <= 20 and max(q[2] for q in P) <= 4 and min(q[1] for q in P) > -30:
                    out.append(min(q[1] for q in P))
                p = f['end']; continue
        p += 1
    assert out, 'intake mouth not found'
    return min(out)


def flap_span(d):
    """Outer |x| of the flap vertex buffers: main-LOD part buffers behind the wing hinge line (fwd < -5) that
    reach |x| >= 30."""
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE')
    c = d[code['ro']:code['ro'] + code['vs']]
    out = 0
    for o, n, t, e in main_lod(c)[1:]:
        if t < 0: continue
        V = [struct.unpack_from('<3h', c, o + 6 + 6 * k) for k in range(n)]
        if max(v[1] for v in V) < -5 and max(abs(v[0]) for v in V) >= 30: out = max(out, max(abs(v[0]) for v in V))
    return out


def placer(c, ROOT, ugeo, ubox, fus):
    import sh_order, sh_bsp
    plan, refs = S.place_units(c, ROOT, {u: b for u, b in ubox.items() if u not in fus})
    big = sorted(fus)
    sh_bsp.F0_VARS = {}                                # judged in flight: gear up, doors / hook / flaps closed
    try: p2, r2, M, *_ = sh_order.place(c, ROOT, ugeo, ubox, big, pre=plan)   # the other stores already in place
    finally: sh_bsp.F0_VARS = None
    return M.ins, {**refs, **r2}


# ---------------------------------------------------------------- configure f18_stores from the PT
def configure(d, pt):
    P = main_polys(d)
    hps = [h for h in pt_hards(pt) if h['i'] >= 4 and (h['x'], h['u'], h['f']) != (0, 0, 0)]
    slots, pylons, units, fall, under_ = {}, {}, [], {}, {}
    wing = sorted({h['x'] for h in hps if h['loc'] == 4})
    tip = max(hps, key=lambda h: h['x'])
    print('hardpoints:')
    for h in hps:
        st, x, u, f = h['i'], h['x'], h['u'], h['f']
        kd = jt_kind(h['default'])
        att_k = kd or S.GENERIC                        # no default store: attach height of a generic missile
        if h['loc'] == 1 and x != 0:                   # fuselage pair: AIM-120 nose just behind the intake lip
            lip = intake_lip(d)                        # (Kuoyi 2026-11-21, photo of the real jet); drawn position
            nose = max(v[1] for v in S.SHAPES[S.AAM]()[0])   # only, the PT launch point is left as it is
            f = min(f, lip - NOSE_GAP - nose)
        a = (x, round(u + S.top_of(att_k)), f)
        print(f"  hp{st} {h['default']} kind {kd} loc {h['loc']} PT ({x},{u},{h['f']}) attach {a}")
        if x == 0: slots['C%d' % st] = (st, 1, kd, a)
        else:
            slots['R%d' % st] = (st, 2, kd, a); slots['L%d' % st] = (st, 1, kd, S.mx(a))
        if h['loc'] in (0, 4):                         # pylon from the store top into the wing / belly
            und = next((v for df in sorted(range(-30, 31), key=abs) for v in [under(P, x, f + df, a[1])] if v is not None), None)
            assert und is not None, ('no surface above', st)   # (store ahead of the wing LE: nearest chord point)
            under_[st] = und
            hgt = round(und + 1 - a[1])
            if x == 0:
                pylons['py%d' % st] = S.pylon(hgt, (f + 6, f - 6), (f + 7, f - 7))
                units.append(('pyC%d' % st, 'py%d' % st, (0, a[1], 0), a[1] + 2))
            else:
                ch = chord(P, x, a[1], und)
                le, te = ch if ch else (f + 8, f - 12)
                top = (min(f + 7, le - 2), max(f - 12, te + 7))
                if top[0] - top[1] < 6: top = (top[1] + 6, top[1])
                pylons['py%d' % st] = S.pylon(hgt, (f + 7, f - 12), top)
                for s, xs in (('R', x), ('L', -x)):
                    units.append(('py%s%d' % (s, st), 'py%d' % st, (xs, a[1], 0), a[1] + 3))
                print(f'     wing underside {und:.1f}, chord {ch}, pylon h {hgt} top fwd {top}')
    # falling jettisoned tanks: centreline + the two innermost wing stations (as F18: C4, R6/L6, R7/L7)
    k = 0
    for name in [n for n in slots if n[0] == 'C'] + [p + str(h['i']) for h in sorted((h for h in hps if h['loc'] == 4), key=lambda h: h['x'])[:2] for p in 'RL']:
        fall[name] = k; k += 1
    S.SLOTS, S.PYLONS, S.FALL_SLOTS = slots, pylons, fall
    # file size: these jets never carry the AIM-54, so an AIM-54 is drawn with the AIM-120 shape (stored once)
    S.SHAPES[S.AIM54] = S.SHAPES[S.AAM]
    S.PYLON_UNITS = lambda: units
    # fuselage pairs (loc 1, x != 0) sit against the curved intake / belly: one plane down the BSP descent misorders
    # them (Kuoyi 2026-11-21, F18C: the far AIM-120 shows through the body, the near one is lost), so they are
    # placed by sh_order (best branch + plane over ~80 rendered views); every other unit as before
    fus = {p + str(h['i']) for h in hps if h['loc'] == 1 and h['x'] != 0 for p in 'RL'}
    S.PLACER = (lambda c, ROOT, ugeo, ubox: placer(c, ROOT, ugeo, ubox, fus)) if fus else None
    W.TIP_ST = tip['i']
    # hinge outboard of the flaps too: the flap faces use their own vertex buffers (flaps up / down), which the
    # fold does not clip, so a flap reaching past the hinge sticks out of the folded wing (F18E/F/T/U flaps reach
    # x 51; F18 / F18C 39)
    W.H = max(44, max(wing) + 2 if wing else 44, flap_span(d) + 1)
    print('slots', list(slots), 'fall', fall, 'tip station', W.TIP_ST, 'hinge |x|', W.H)


def main():
    var, src, psrc, pt, dst, pdst = sys.argv[1:7]
    tmp = dst + '.tmp'
    d = open(src, 'rb').read()
    configure(d, pt)
    out, _ = S.make(d)
    open(tmp + '1.SH', 'wb').write(out); print('1 stores', len(out))
    py = sys.executable
    subprocess.run([py, os.path.join(HERE, 'sh_ab_flame.py'), var, tmp + '1.SH', psrc, tmp + '2.SH', tmp + '2.PIC', '--grow', '3000'], check=True)
    subprocess.run([py, os.path.join(HERE, 'f18_gear.py'), tmp + '2.SH', tmp + '2.PIC', tmp + '3.SH', pdst], check=True)
    d = open(tmp + '3.SH', 'rb').read()
    o, lay = W.build(d)
    if o is None: o, lay = W.build(W.grow_vas(d, 0x1000), grown=True)
    assert len(o) < 65536, len(o)
    open(dst, 'wb').write(o)
    if len(sys.argv) > 7:                          # optional: a preview copy with the panels folded (static roll)
        f, _ = W.build(d, folded=True)
        if f is None: f, _ = W.build(W.grow_vas(d, 0x1000), folded=True, grown=True)
        open(sys.argv[7], 'wb').write(f)
    for k in '123': os.remove(tmp + k + '.SH')
    os.remove(tmp + '2.PIC')
    print(f'{dst}: {len(o)} B')


if __name__ == '__main__':
    main()
