"""F14_C wreck v1: current F14.SH; right aft nacelle / fin / stab / ventral fin removed (38 jumps over the faces) in the
high and medium LODs, far LOD -> medium LOD (frees 0x653b..0x701d), damage cavity faces of the old F14_C (x4, shift 10->8)
drawn as a C4 part at the start of each LOD (trampoline over the first F6). Textures from old _F14_C.PIC appended to _F14.PIC."""
import sys,struct,os;sys.path.insert(0,'/home/user/fa/tools/shgen');sys.path.insert(0,'.')
import numpy as np
from sh_subdivide import parse_face, pe_sections
from sh_scale import walk
import faces, lods, wreckpic as WP
BASE='/home/user/fa/SH/F14.SH'; BPIC='/home/user/fa/PIC/_F14.PIC'
WRK='/home/user/fa/SH/F14_C.SH'; WPIC='/home/user/fa/PIC/_F14_C.PIC'
OUT=sys.argv[1] if len(sys.argv)>1 else 'wk/F14_C_1.SH'; OPIC=sys.argv[2] if len(sys.argv)>2 else 'wk/_F14_C_1.PIC'
FREE=(0x653b,0x701d); SLOT=399; HDR6=bytes.fromhex('e6004700fb00')
LODS=[(0x80,0x4906,383),(0x4906,0x653b,188)]     # (start,end,max main slot)
TRAMP=[0x938,0x4d74]                              # first F6 after each LOD's 82
def in_box(cen,P):
    x,u,f=cen
    if x>=7.5 and -47<=f<=-3 and -13<=u<=8: return 'nacelle'
    if 12<=x<=17 and u>6 and f<-24: return 'fin'
    if x>24 and f<-22 and abs(u)<3: return 'stab'
    return None
d=bytearray(open(BASE,'rb').read()); pe,opt,secs=pe_sections(d); co=next(s for s in secs if s['name']=='CODE')
c=bytearray(d[co['ro']:co['ro']+co['vs']])
ops0,_,_=walk(bytes(c))
# far LOD -> medium LOD
assert c[0x5a]==0xC8; struct.pack_into('<h',c,0x5a+6,0x4906-(0x5a+8))
# 1) remove faces
AF=lods.all_faces(bytes(c)); removed=[]
for F in AF:
    lo=[L for L in LODS if L[0]<=F['o']<L[1]]
    if not lo or max(F['idx'])>=lo[0][2] or F['o'] not in ops0: continue
    why=in_box(F['cen'],F['P'])
    if why:
        n=F['end']-F['o']; assert n>=3
        c[F['o']:F['o']+3]=struct.pack('<Bh',0x38,n-3); removed.append((hex(F['o']),why,F['lod']))
from collections import Counter
print('removed',len(removed),Counter((w,l) for _,w,l in removed))
# 2) cavity faces from the old wreck
_,_,_,FW=faces.get(WRK); dw=open(WRK,'rb').read(); _,_,sw=pe_sections(dw); cow=next(s for s in sw if s['name']=='CODE'); cw=dw[cow['ro']:cow['ro']+cow['vs']]
S=[f for f in FW if f['col']==158 and f['cen'][0]>0]; S.sort(key=lambda f:f['o'])
seen=set(); Q=[]
for f in S:
    k=tuple(sorted(tuple(int(v) for v in p) for p in f['P']))+(tuple(np.sign(f['n']).astype(int)),)
    if k in seen: continue
    seen.add(k); Q.append(f)
print('cavity faces',len(Q),'of',len(S))
hdr,TB=WP.load(BPIC); TW=WP.load(WPIC)[1]
rects=WP.merge_rects([(max(0,min(u for u,v in f['uv'])-1),max(0,min(v for u,v in f['uv'])-1),min(255,max(u for u,v in f['uv'])+1),min(TW.shape[0]-1,max(v for u,v in f['uv'])+1)) for f in Q if f['uv']])
pk=WP.Packer(TB); sh={}
for r in sorted(rects,key=lambda r:-(r[3]-r[1])): sh[tuple(r)]=pk.add(TW,*r)
def remap(uv):
    for r,(su,sv) in sh.items():
        if all(r[0]<=u<=r[2] and r[1]<=v<=r[3] for u,v in uv): return [(u+su,v+sv) for u,v in uv]
    raise Exception(uv)
T=pk.build(); print('PIC',TB.shape,'->',T.shape,'rects',rects)
V=[]; vid={}
for f in Q:
    for p in f['P']:
        k=tuple(int(v)*4 for v in p)
        if k not in vid: vid[k]=SLOT+len(V); V.append(k)
part=bytearray(HDR6)+struct.pack('<BBHH',0x82,0,len(V),SLOT*8)
for x,u,fw in V: part+=struct.pack('<hhh',x,fw,u)
for f in Q:
    F=parse_face(cw,f['o']); fl=(F['fl']|0x400)&~0x100&~0x02
    b=struct.pack('<BHH',0xFC,fl,F['col'])
    if F['fl']&0x60:
        nrm=struct.unpack_from('<hhh',F['head'],4)
        pt=np.mean([np.array(p)*4 for p in f['P']],0).round().astype(int)
        if fl&0x200: assert all(-128<=v<=127 for v in pt)
        b+=struct.pack('<hhh',*nrm)+(struct.pack('<bbb',*pt) if fl&0x200 else struct.pack('<hhh',*pt))
    K=[tuple(int(v)*4 for v in p) for p in f['P']]
    b+=bytes([len(K)])+b''.join(struct.pack('<H',vid[k]) for k in K)
    if fl&4: b+=b''.join(struct.pack('<HH',*w) for w in remap(f['uv']))
    part+=b
part+=b'\x1e'
PART=FREE[0]+6
code=bytearray(part)
# trampolines: C4 part + relocated F6 + jump back
for t in TRAMP:
    assert c[t]==0xF6
    p=FREE[0]+len(code)
    blk=bytearray(struct.pack('<BB3h3hh',0xC4,0,0,0,0,0,0,0,PART-(p+16)))
    blk+=c[t:t+7]; blk+=struct.pack('<Bh',0x38,(t+7)-(p+len(blk)+3))
    code+=blk
    c[t:t+3]=struct.pack('<Bh',0x38,p-(t+3))
assert FREE[0]+len(code)<=FREE[1], (len(code),FREE[1]-FREE[0])
c[FREE[0]:FREE[0]+len(code)]=code; c[FREE[0]+len(code):FREE[1]]=b'\x00'*(FREE[1]-FREE[0]-len(code))
print('cavity verts',len(V),'part bytes',len(part),'total',len(code),'room',FREE[1]-FREE[0])
ops,unk,_=walk(bytes(c)); assert PART in ops, 'part not reached'
d[co['ro']:co['ro']+co['vs']]=c
old=b'\xE2\x00'+b'_f14.PIC'.ljust(14,b'\0'); new=b'\xE2\x00'+b'_f14_c.PIC'.ljust(14,b'\0')
print('E2 renamed',d.count(old)); d=d.replace(old,new); assert len(d)<65536
open(OUT,'wb').write(d); WP.save(hdr,T,OPIC); print('wrote',OUT,len(d),OPIC)
