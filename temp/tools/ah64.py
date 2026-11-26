#!/usr/bin/env python3
"""AH-64A (APL.SH) / AH-64D (APA.SH) Apache (mass-upgrade thread, 2026-11-26).  Helicopter SHs have no .idata (no
imports, no variables), so the stores cannot follow the loadout (no F0 code): they are drawn STATIC, the PT default
fit always shown, inserted into the model's own draw-order tree.  Stub wing pylons at the real inboard / outboard
positions (+-14 / +-22 u, 3 u per ft): M299 four-round Hellfire launchers inboard, M261 19-tube rocket pods outboard
(the PT's AGM-114 / LAU-61 stations).  PT launch points moved to them.
Usage: ah64.py OUTDIR"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
from pt_edit import set_hp

OLIVE, DARK = 106, 160          # palette green ramp 96..111 (olive drab), black tube ends
IN, OUT, F0, ATT_U = 14, 22, 4, -2      # pylon x, store fwd centre, attach (store top) up


def hellfire_rack():
    from fs_core import lathe, FLAT, orient
    V, F = [], []
    # launcher beam: box x -1..1, up 0..-2, fwd -8..8
    b = [(x, f, u) for x in (-1, 1) for f in (-8, 8) for u in (0, -2)]
    q = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]
    V += b; F += orient(b, [(FLAT, OLIVE, x) for x in q])
    sec = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    for x0 in (-2, 2):
        for u0 in (-3, -5.5):
            Vm, Fm, _ = lathe(sec, [(9, 0, 0), (7, .9, 0), (-8, .9, 0)], OLIVE)
            n = len(V); V += [(round(x + x0), f, round(u + u0)) for x, f, u in Vm]
            F += [(fl, col, [i + n for i in idx]) for fl, col, idx in Fm]
    return V, F


def rocket_pod():
    from fs_core import lathe
    r = 2.3; e = r * .7
    sec = [(0, r), (e, e), (r, 0), (e, -e), (0, -r), (-e, -e), (-r, 0), (-e, e)]
    V, F, rings = lathe(sec, [(9, .75, -r), (8, 1, -r), (-8, 1, -r), (-9, .8, -r)], OLIVE)
    F = [(fl, DARK if idx == list(rings[0]) or idx == list(rings[0])[::-1] or idx == list(rings[-1]) or idx == list(rings[-1])[::-1] else col, idx)
         for fl, col, idx in F]                                     # tube ends black
    return V, F


def pylon(h):
    from fs_core import orient, FLAT
    V = [(x, f, u) for x in (-1, 0) for f in (-4, 6) for u in (0, h)]
    q = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6]]
    return V, orient(V, [(FLAT, OLIVE, x) for x in q])


def stores_extra_for(IN=IN, OUT=OUT, F0=F0, ATT_U=ATT_U, ph=2, rack_out=False):
    """rack_out: missile launcher on the outboard pylon, rocket pod inboard (AH-1); else Hellfires inboard (AH-64)."""
    def ex(S): stores_extra(S, IN, OUT, F0, ATT_U, ph, rack_out)
    return ex


def stores_extra(S, IN=IN, OUT=OUT, F0=F0, ATT_U=ATT_U, ph=2, rack_out=False):
    hf, rp = hellfire_rack(), rocket_pod()
    for k in list(S.SHAPES): S.SHAPES[k] = (lambda v: (lambda: v))(hf)
    S.SHAPES[S.AAM] = (lambda: rp)
    ki, ko = (S.AAM, S.ARM) if rack_out else (S.ARM, S.AAM)
    S.SLOTS = {'R4': (4, 2, ki, (IN, ATT_U, F0)), 'L4': (4, 1, ki, (-IN, ATT_U, F0)),
               'R5': (5, 2, ko, (OUT, ATT_U, F0)), 'L5': (5, 1, ko, (-OUT, ATT_U, F0))}
    S.FALL_SLOTS = {}
    S.PYLONS = {'py': pylon(ph)}
    S.PYLON_UNITS = lambda: [('py' + s, 'py', S.SLOTS[s][3], ATT_U + ph) for s in S.SLOTS]


VAR = {'APA': 'AH64D', 'APL': 'AH64'}


def make_pt(name, dst):
    t = open(os.path.join(ROOT, 'PT', name + '.PT'), encoding='latin1', newline='').read()
    if name == 'AH64':      # single stations: hp2 / hp3 Hellfire left / right, hp4 / hp5 rockets left / right
        for i, x, u in ((2, -IN, -6), (3, IN, -6), (4, -OUT, -5), (5, OUT, -5)): t = set_hp(t, i, x=x, u=u, f=F0)
    else:                   # AH-64D: paired stations hp4 Hellfire, hp5 rockets
        t = set_hp(t, 4, x=IN, u=-6, f=F0); t = set_hp(t, 5, x=OUT, u=-5, f=F0)
    open(dst, 'w', encoding='latin1', newline='').write(t)


def build(out):
    import up_stores, shutil, std
    os.makedirs(out, exist_ok=True)
    for sh, pt in VAR.items():
        make_pt(pt, os.path.join(out, pt + '.PT'))
        up_stores.run(os.path.join(ROOT, "SH", sh + ".SH"), os.path.join(out, pt + ".PT"), os.path.join(out, sh + ".SH"), stores_extra_for(), static=True)
        shutil.copy(os.path.join(ROOT, 'PIC', '_' + sh + '.PIC'), os.path.join(out, '_' + sh + '.PIC'))
        std.render(os.path.join(out, sh + '.SH'), os.path.join(out, '_' + sh + '.PIC'), os.path.join(out, 'preview_' + sh + '.png'))


if __name__ == '__main__':
    build(sys.argv[1])
