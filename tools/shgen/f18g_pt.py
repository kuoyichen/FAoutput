#!/usr/bin/env python3
"""F18G loadout PT (Kuoyi 2026-11-22): PT/F18G.PT with F18F-style stations: fuselage AIM-120 pair,
outermost wing AGM-88 pair (x 48); wingtip, inner/middle wing and centreline stations removed (F18G-2: tanks and
ALQ-99 pods are fixed structure drawn by f18g_pods.py); shape f18g.SH. Run from the repo root."""
t=open('PT/F18G.PT',encoding='latin1',newline='').read()
assert '\r\n' in t
t=t.replace('\r\n','\n')
H=[('$8',0,0,0,'VIS340.SEE',0,1,1),
   ('$8',0,0,0,'MIG31R.SEE',0,1,1),
   ('$8',0,0,-50,'EA6.ECM',0,1,1),
   ('$8',0,0,0,'AEMP1.JT',0,40,1),
   ('$465',12,-11,-16,'AIM120.JT',7,2,1),
   ('$7e5',48,-11,3,'AGM88.JT',50,2,4),
   ('$8',0,0,0,'EA6R.SEE',0,1,1),
   ('$8',0,0,0,'F14.ECM',0,1,1)]
hs=''.join(f';-------- hardpoint {i}\n    word {f}\n    word {x}\n    word {u}\n    word {w}\n'+'    word 0\n'*4+
  f'\tptr defaultTypeName{i}\n    byte {m}\n    word {q}\n    byte {l}\n' for i,(f,x,u,w,n,m,q,l) in enumerate(H))
a=t.index(':hards\n')+len(':hards\n'); b=t.index(':env')
t=t[:a]+hs+t[b:]
a=t.index(':defaultTypeName0'); b=t.index('\tend',a)
t=t[:a]+''.join(f':defaultTypeName{i}\n\tstring "{h[4]}"\n' for i,h in enumerate(H))+t[b:]
old='    byte 11\n\tptr hards'; assert t.count(old)==1
t=t.replace(old,f'    byte {len(H)}\n\tptr hards')
assert ':shape\n\tstring "f18.SH"' in t
t=t.replace(':shape\n\tstring "f18.SH"',':shape\n\tstring "f18g.SH"')
open('SHX/f18g/F18G-2.PT','w',encoding='latin1',newline='').write(t.replace('\n','\r\n'))
