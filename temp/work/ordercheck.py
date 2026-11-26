import sys, os, glob, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if False else '.')
import shview as V
from PIL import Image
res = []
for sh in sorted(glob.glob('../out/*/*.SH')):
    d, n = os.path.split(sh); pic = os.path.join(d, '_' + n[:-3] + '.PIC')
    if not os.path.exists(pic): pic = None
    v = {'_PLgearPos': 0, '_PLgearDown': 1, '_PLafterBurner': 1}
    out = []
    for mode in ('zbuf', 'painter'):
        p = '../work/oc_%s.png' % mode
        try: V.views(sh, pic, p, vars=v, mode=mode, vlist=[(1.5708, 0.0), (0.6, -0.35), (0, 0), (-0.7, 0.45), (2.4, -0.5), (3.6, 0.4)], W=400, H=300)
        except Exception as e: out = None; print(sh, 'ERR', e); break
        out.append(np.asarray(Image.open(p).convert('RGB')).astype(int))
    if out is None: continue
    diff = (np.abs(out[0] - out[1]).sum(2) > 60)
    H, W = 300, 400
    per = [diff[(i // 3) * H:(i // 3 + 1) * H, (i % 3) * W:(i % 3 + 1) * W].sum() for i in range(6)]
    fg = (out[0].sum(2) < 3 * 230).sum()
    res.append((sum(per) / max(fg, 1), sh, per))
    print('%.3f %s %s' % (sum(per) / max(fg, 1), sh, per), flush=True)
