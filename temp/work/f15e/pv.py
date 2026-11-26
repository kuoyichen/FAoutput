import sys, numpy as np
sys.path.insert(0,'.')
import shview as V
sh, pic, out = sys.argv[1:4]
vl=[(1.5708,0.0),(0.6,-0.35),(2.4,-0.3),(-0.7,0.45)]
V.views(sh,pic,out,vars={'_PLafterBurner':1},vlist=vl,mode='zbuf',W=800,H=480,fit=(np.zeros(3),95))
