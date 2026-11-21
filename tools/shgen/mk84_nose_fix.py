#!/usr/bin/env python3
"""One-off fix of the nose of Kuoyi's SH/MK84.SH (2026-11-21): sunken / missing fuze quadrants, dented band, notched
body corner.  Moves 7 vertices of the main LOD and recomputes the normals of the faces that use them (keeping each
face's facing).  Usage (repo root): python3 tools/shgen/mk84_nose_fix.py SH/MK84.SH out.SH"""
import os, sys, struct; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, main_lod
import fa_weapons as FW
from f14_nose import normal_point
src,dst=sys.argv[1:3]
d=bytearray(open(src,'rb').read()); pe,opt,secs=pe_sections(d); code=next(s for s in secs if s['name']=='CODE'); ro=code['ro']
c=bytearray(d[ro:ro+code['vs']])
o,n,t,e=main_lod(c)[0]
V=[list(struct.unpack_from('<hhh',c,o+6+6*i)) for i in range(n)]
NEW={4:(-2,13,0),5:(0,13,-2),   # fuze lower-left quadrant started from a radius-1 ring at fwd 12 (sunken)
     35:(0,3,-4),36:(0,3,-4),   # body lower-left front corner notched to (-1,3,-3)
     66:(0,10,3),69:(0,12,2),   # band upper-right had a dent ((1,10,2), (1,11,1))
     14:(2,13,0)}               # fuze lower-right quadrant face was a triangle missing its (2,13,0) corner   # band upper-right had a dent ((1,10,2), (1,11,1))
for i,v in NEW.items(): print(i,V[i],'->',v); V[i]=list(v); struct.pack_into('<hhh',c,o+6+6*i,*v)
for p,fl,col,idx in FW.faces_of(bytes(c),o):
    P=[tuple(V[i]) for i in idx]; U=[]
    for q in P:
        if q not in U: U.append(q)
    if len(U)<3: print('  face %x degenerate now'%p); continue
    nrm,pt=normal_point(U,fl)
    old=struct.unpack_from('<hhh',c,p+5)
    if sum(a*b for a,b in zip(nrm,old))<0: nrm=[-x for x in nrm]   # keep the file's own facing
    struct.pack_into('<hhh',c,p+5,*nrm); struct.pack_into('<bbb',c,p+11,*pt)
    dot=sum(a*b for a,b in zip(nrm,old))/32767/32767
    if dot<0.98: print('  face %x'%p, old,'->',nrm, U, round(dot,2))
d[ro:ro+code['vs']]=c; open(dst,'wb').write(d)
