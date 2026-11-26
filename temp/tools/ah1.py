#!/usr/bin/env python3
"""AH-1W (COB.SH, PT AH1) / AH-1S (AH1.SH, PT AH1S) Cobra (mass-upgrade thread, 2026-11-26).  Like the AH-64
(ah64.py): no imports in heli SHs, so the PT default stores are drawn static.  Stub wing x 5..16, underside up -6,
chord fwd 14..23: rocket pods on the inboard pylons (x +-9), four-round launchers outboard (x +-14: AH-1W Hellfire,
AH-1S TOW).  PT launch points moved to the pylons.
Usage: ah1.py OUTDIR"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE)
from pt_edit import set_hp
import ah64

IN, OUT, F0, ATT_U = 9, 14, 18, -7
VAR = {'COB': ('AH1', ((2, IN), (3, OUT))), 'AH1': ('AH1S', ((3, IN), (4, OUT)))}


def build(out):
    import up_stores, shutil, std
    os.makedirs(out, exist_ok=True)
    for sh, (pt, sts) in VAR.items():
        t = open(os.path.join(ROOT, 'PT', pt + '.PT'), encoding='latin1', newline='').read()
        for i, x in sts: t = set_hp(t, i, x=x, u=-11, f=F0)
        open(os.path.join(out, pt + '.PT'), 'w', encoding='latin1', newline='').write(t)
        up_stores.run(os.path.join(ROOT, 'SH', sh + '.SH'), os.path.join(ROOT, 'PT', 'AH64D.PT'),   # layout PT only (slots set below)
                      os.path.join(out, sh + '.SH'),
                      ah64.stores_extra_for(IN, OUT, F0, ATT_U, 2, rack_out=True), static=True)
        shutil.copy(os.path.join(ROOT, 'PIC', '_' + sh + '.PIC'), os.path.join(out, '_' + sh + '.PIC'))
        std.render(os.path.join(out, sh + '.SH'), os.path.join(out, '_' + sh + '.PIC'), os.path.join(out, 'preview_' + sh + '.png'))


if __name__ == '__main__':
    build(sys.argv[1])
