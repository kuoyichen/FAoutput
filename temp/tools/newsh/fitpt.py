#!/usr/bin/env python3
"""Fit a PT's wing hardpoints (loc 4) to a generated SH: the store centre goes under the wing chord at that span
(pylon fully under the wing, store centre ~45% chord from the trailing edge) and the store top hangs 3 below
the wing underside. The old PTs were laid out for the stand-in shapes, so stations often sat behind the new wing.
Usage: fitpt.py X.SH A.PT [B.PT ...]   (edits the PTs in place; every PT gets the same station geometry)"""
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import stores  # noqa  (patches intake_lip)
import up_stores
from pt_edit import set_hp
U = up_stores.U; S = up_stores.S


def chord(P, x, f0, near):
    """Contiguous fwd run (LE, TE) around f0 where the lowest surface at span x is within 3 of `near` (the wing
    underside; gaps of 2 allowed), so a tailplane at the same height is not counted."""
    ok = lambda f: (lambda v: v is not None and abs(v - near) < 3)(U.under(P, x, f, -40))
    if not ok(f0): return None
    le = te = f0
    while any(ok(le + k) for k in (1, 2, 3)): le += 1
    while any(ok(te - k) for k in (1, 2, 3)): te -= 1
    return le, te


def fit(sh, pts):
    d = open(sh, 'rb').read()
    P = U.main_polys(d)
    done = {}
    for pt in pts:
        t = open(pt, encoding='latin1', newline='').read()
        crlf = '\r\n' in t; t = t.replace('\r', '')
        ch_any = False
        for h in U.pt_hards(pt):
            if h['i'] < 4 or h['loc'] != 4 or h['x'] == 0: continue
            key = (abs(h['x']), h['u'], h['f'])
            if key not in done:
                x, u, f = abs(h['x']), h['u'], h['f']
                kd = U.jt_kind(h['default']) or S.GENERIC
                top = lambda uu: uu + U.PT_DROP + S.top_of(kd)
                ch = und = None
                while x > 4:
                    hit = next(((f + df, v) for df in sorted(range(-80, 81), key=abs) for v in [U.under(P, x, f + df, -40)] if v is not None), None)
                    und = hit and hit[1]
                    ch = hit and chord(P, x, hit[0], und)
                    if ch and ch[0] - ch[1] >= 8: break
                    x -= 1
                if not ch: print(pt, 'hp', h['i'], 'no wing found, left'); done[key] = key; continue
                le, te = ch
                nf = round(te + 0.45 * (le - te))
                nf = max(min(nf, le - 9), te + 10) if le - te >= 19 else round((le + te) / 2)
                nu = u
                if abs(top(u) - (und - 3)) > 3: nu = round(und - 3 - U.PT_DROP - S.top_of(kd))
                done[key] = (x, nu, nf)
                print(f'{os.path.basename(pt)} hp{h["i"]} ({h["x"]},{u},{f}) wing und {und:.1f} chord {ch} -> (±{x},{nu},{nf})')
            x, nu, nf = done[key]
            if (x, nu, nf) != key:
                t = set_hp(t, h['i'], x=x if h['x'] > 0 else -x, u=nu, f=nf); ch_any = True
        if ch_any:
            if crlf: t = t.replace('\n', '\r\n')
            open(pt, 'w', encoding='latin1', newline='').write(t)


if __name__ == '__main__': fit(sys.argv[1], sys.argv[2:])
