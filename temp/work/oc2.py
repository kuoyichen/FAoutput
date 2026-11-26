import sys, os, numpy as np
sys.path.insert(0, '../tools')
import shview as V
from PIL import Image
for n in sys.argv[1:]:
    sh = '../../SH/%s.SH' % n; pic = '../../PIC/_%s.PIC' % n
    v = {'_PLgearPos': 0, '_PLgearDown': 1, '_PLafterBurner': 1}
    out = []
    for mode in ('zbuf', 'painter'):
        p = 'oc_%s.png' % mode
        V.views(sh, pic, p, vars=v, mode=mode, vlist=[(1.5708, 0.0), (0.6, -0.35), (0, 0), (-0.7, 0.45), (2.4, -0.5), (3.6, 0.4)], W=400, H=300)
        out.append(np.asarray(Image.open(p).convert('RGB')).astype(int))
    diff = (np.abs(out[0] - out[1]).sum(2) > 60); fg = (out[0].sum(2) < 3 * 230).sum()
    print('stock %.3f %s' % (diff.sum() / fg, n))
