"""F14_D (flying right tail section): container = current F14.SH (main LOD start 0x80, C8/A6 -> 0x80).
Piece = the faces F14_C removes (right aft nacelle skin, right fin, right stab, ventral fin) + the old F14_D's
burnt internal faces (x4, moved to the body frame), centred on the bbox; fin/stab/ventral sorted by 3 plane nodes."""
import sys,struct,os;sys.path.insert(0,'/home/user/fa/tools/shgen');sys.path.insert(0,'.')
import numpy as np
from sh_subdivide import parse_face, pe_sections
from sh_scale import walk
import faces, lods, wreckpic as WP, fixreloc
BASE='/home/user/fa/SH/F14.SH'; BPIC='/home/user/fa/PIC/_F14.PIC'
WRK='/home/user/fa/SH/F14_D.SH'; WPIC='/home/user/fa/PIC/_F14_D.PIC'
OUT=sys.argv[1] if len(sys.argv)>1 else 'wk/F14_D_1.SH'; OPIC=sys.argv[2] if len(sys.argv)>2 else 'wk/_F14_D_1.PIC'
START=0x80; LIM=0x4906
OFFD=np.array([18,-4,-37])     # old D piece frame -> body (fit of the fin: x -4->14, up 8..36 -> 5..31, fwd -28..8 -> -67..-26)
def in_box(cen):
    x,u,f=cen
    if x>=7.5 and -47<=f<=-3 and -13<=u<=8: return 'ventral' if (u<-9.5 and 12<x<16) else 'nacelle'
    if 12<=x<=17 and u>6 and f<-24: return 'fin'
    if x>24 and f<-22 and abs(u)<3: return 'stab'
    return None
d=bytearray(open(BASE,'rb').read()); pe,opt,secs=pe_sections(d); co=next(s for s in secs if s['name']=='CODE')
c=bytearray(d[co['ro']:co['ro']+co['vs']]); c0=bytes(c)
ops0,_,_=walk(c0)
# main LOD vertex buffer + F6 entries
n0=struct.unpack_from('<H',c0,0x82)[0]; MV={i:struct.unpack_from('<hhh',c0,0x86+6*i) for i in range(n0)}   # (x,fwd,up)
F6={}
for a,t in ops0.items():
    if t=='F6' and a<LIM: F6[struct.unpack_from('<H',c0,a+1)[0]]=bytes(c0[a+3:a+7])
groups={'nacelle':[],'fin':[],'stab':[],'ventral':[],'dmg':[]}
for F in lods.all_faces(c0):
    if not (START<=F['o']<LIM) or F['o'] not in ops0 or max(F['idx'])>=n0: continue
    g=in_box(F['cen'])
    if g:
        pf=parse_face(c0,F['o']); P=[(MV[i][0],MV[i][2],MV[i][1]) for i in pf['idx']]
        groups[g].append(dict(raw=pf,P=P,src='f14'))
# old D damage faces
_,_,_,FW=faces.get(WRK); dw=open(WRK,'rb').read(); _,_,sw=pe_sections(dw); cow=next(s for s in sw if s['name']=='CODE'); cw=dw[cow['ro']:cow['ro']+cow['vs']]
hdr,TB=WP.load(BPIC); TW=WP.load(WPIC)[1]
DM=[f for f in FW if f['col']==158]
rects=WP.merge_rects([(max(0,min(u for u,v in f['uv'])-1),max(0,min(v for u,v in f['uv'])-1),min(255,max(u for u,v in f['uv'])+1),min(TW.shape[0]-1,max(v for u,v in f['uv'])+1)) for f in DM if f['uv']])
pk=WP.Packer(TB); sh={}
for r in sorted(rects,key=lambda r:-(r[3]-r[1])): sh[tuple(r)]=pk.add(TW,*r)
def remap(uv):
    for r,(su,sv) in sh.items():
        if all(r[0]<=u<=r[2] and r[1]<=v<=r[3] for u,v in uv): return [(u+su,v+sv) for u,v in uv]
    raise Exception(uv)
for f in DM:
    pf=parse_face(cw,f['o']); P=[tuple(int(v) for v in np.array(p)*4+OFFD) for p in f['P']]
    groups['dmg'].append(dict(raw=pf,P=P,src='old',uv=remap(f['uv']) if f['uv'] else None))
T=pk.build(); print('PIC',TB.shape,'->',T.shape,'rects',rects)
print({k:len(v) for k,v in groups.items()})
allP=np.concatenate([np.array(q['P']) for g in groups.values() for q in g]); CEN=np.round((allP.min(0)+allP.max(0))/2).astype(int)
print('bbox',allP.min(0),allP.max(0),'centre',CEN)
V=[]; vid={}; f6=bytearray()
def vtx(p,src_idx=None):
    k=tuple(int(v) for v in np.array(p)-CEN)
    if k not in vid:
        vid[k]=len(V); V.append(k)
    return vid[k]
def face_bytes(q):
    pf=q['raw']; fl=pf['fl']
    idx=[]
    for j,p in enumerate(q['P']):
        i=vtx(p); idx.append(i)
        if q['src']=='f14' and fl&0x02 and pf['idx'][j] in F6 and i not in done6:
            done6.add(i); f6.extend(b'\xF6'+struct.pack('<H',i)+F6[pf['idx'][j]])
    if q['src']=='old': fl&=~0x02
    if q['src']=='f14' and fl&0x02 and not all(pf['idx'][j] in F6 for j in range(len(idx))): fl&=~0x02
    wide=max(idx)>255; fl=(fl|0x400) if wide else (fl&~0x400)
    uv=q.get('uv') if q['src']=='old' else pf['uv']
    if q['src']=='old' and uv is not None: fl&=~0x100
    b=struct.pack('<BHH',0xFC,fl,pf['col'])
    if fl&0x60:
        nrm=struct.unpack_from('<hhh',pf['head'],4)
        pt=np.mean([np.array(p)-CEN for p in q['P']],0).round().astype(int)
        b+=struct.pack('<hhh',*nrm)+(struct.pack('<bbb',*pt) if fl&0x200 else struct.pack('<hhh',*pt))
    b+=bytes([len(idx)])+b''.join((struct.pack('<H',i) if wide else bytes([i])) for i in idx)
    if fl&4: b+=b''.join((bytes(w) if fl&0x100 else struct.pack('<HH',*w)) for w in uv)
    return b
done6=set()
leaf={k:b''.join(face_bytes(q) for q in v) for k,v in groups.items()}
def node(n,plane,A,B):
    """06 node: value = sum n_i*(eye_i + d_i) (x,up,fwd); >=0 draws A then B. plane = body coord on that axis."""
    dd=[0,0,0]; ax=[i for i in range(3) if n[i]][0]; dd[ax]=int(-(plane-CEN[ax]))
    A=bytes(A)+b'\x1e'; B=bytes(B)+b'\x1e'
    hdr_=struct.pack('<BB6h',0x06,0,n[0],dd[0],n[1],dd[1],n[2],dd[2])
    # layout: node(18) 38(3) A B ; relA at +14 -> p+16+relA = p+21 ; relB at +16 -> p+18+relB = p+21+len(A)
    relA=21-16; relB=21+len(A)-18
    return hdr_+struct.pack('<hh',relA,relB)+struct.pack('<Bh',0x38,len(A)+len(B))+A+B
K=32767
body=leaf['dmg']+leaf['nacelle']
tree=node((0,K,0),6,node((0,K,0),-10,leaf['ventral'],node((K,0,0),22,body,leaf['stab'])),leaf['fin'])
code=bytearray(struct.pack('<BBHH',0x82,0,len(V),0))
for x,u,f in V: code+=struct.pack('<hhh',x,f,u)
code+=f6+tree+b'\x1e'
print('verts',len(V),'F6',len(f6)//7,'bytes',len(code))
assert len(code)<LIM-START
c[START:START+len(code)]=code
for p in (0x5a,0x62): assert c[p]==0xC8; struct.pack_into('<h',c,p+6,START-(p+8))
assert c[0x6a]==0xA6; struct.pack_into('<h',c,0x6a+2,START-(0x6a+6))
ops,unk,_=walk(bytes(c)); print('reachable',len(ops),'unk',[hex(u) for u in unk if u<0x5000])
d[co['ro']:co['ro']+co['vs']]=c
old=b'\xE2\x00'+b'_f14.PIC'.ljust(14,b'\0'); new=b'\xE2\x00'+b'_f14_d.PIC'.ljust(14,b'\0')
d=d.replace(old,new); open(OUT,'wb').write(d)
print('reloc neutralised',fixreloc.fix(BASE,OUT,[(START,START+len(code))]))
WP.save(hdr,T,OPIC); print('wrote',OUT,OPIC)
