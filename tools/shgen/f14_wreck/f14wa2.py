"""F14_A wreck v1: current F14.SH; left outer wing part replaced by a stub = current wing clipped at a break line,
plus burnt crack overlay and torn-edge spike band (textures from the old _F14_A.PIC, appended to _F14.PIC)."""
import sys,struct,os;sys.path.insert(0,'/home/user/fa/tools/shgen');sys.path.insert(0,'.')
import numpy as np
from sh_subdivide import parse_face, pe_sections
from sh_scale import walk
import faces, wreckpic as WP
from clip import clip_poly
BASE='/home/user/fa/SH/F14.SH'; BPIC='/home/user/fa/PIC/_F14.PIC'; WPIC='/home/user/fa/PIC/_F14_A.PIC'
OUT=sys.argv[1] if len(sys.argv)>1 else 'wk/F14_A_1.SH'; OPIC=sys.argv[2] if len(sys.argv)>2 else 'wk/_F14_A_1.PIC'
OFF=np.array([-32,4,16])                  # left wing C4 pos (x,up,fwd)
C4S=(0x39fe,0x60ad,0x6a3e); PART=0x403d; HDR=0x4037; END=0x43d2
SLOT=399
XB0,XBK=float(os.environ.get('XB0',-60)),float(os.environ.get('XBK',0.3))   # break line x = XB0 + XBK*fwd
xb=lambda f: XB0+XBK*f
CRACK_W=float(os.environ.get('CRW',18)); BAND_IN,BAND_OUT=1.0,3.0
CRACK_TOP=(86,135,158,167); CRACK_BOT=(86,102,158,134); SPIKE=(203,194,224,295)
OVFL=0x6cd                                # torn-face flags without 0x20 lighting (black stays black); col 0 = 255 texels transparent

d=bytearray(open(BASE,'rb').read()); pe,opt,secs=pe_sections(d); co=next(s for s in secs if s['name']=='CODE')
c=bytearray(d[co['ro']:co['ro']+co['vs']])
_,_,_,F=faces.get(BASE)
W=[f for f in F if f.get('part')==0x39fe]
# dedupe identical polygons (variants)
seen=set(); WF=[]
for f in W:
    k=tuple(sorted(tuple(int(v) for v in p) for p in f['P']))+(int(f['n'][1]>0),)
    if k in seen: continue
    seen.add(k); WF.append(f)
keep=lambda p: xb(p[2])-p[0]<=0 and 0 or (p[0]-xb(p[2]))   # >=0 inside (x >= xb)
fn=lambda p: p[0]-xb(p[2])
polys=[]   # (fl,col,head_normal,P(list x,up,fwd),uv)
for f in WF:
    pf=parse_face(c,f['o'])
    P=[np.array(p,float) for p in f['P']]
    Pc,Uc=clip_poly(P,f['uv'],fn)
    if len(Pc)<3: continue
    nrm=struct.unpack_from('<hhh',pf['head'],4)
    polys.append(dict(fl=pf['fl'],col=pf['col'],nrm=nrm,P=Pc,uv=Uc,top=nrm[1]>0))
print('wing faces kept',len(polys),'of',len(WF))
# surface height of top / bottom at (x,fwd)
def surf(x,fw,top):
    best=None
    for q in polys:
        if q['top']!=top: continue
        P=np.array(q['P']); n=np.array(q['nrm'],float)
        if abs(n[1])<1e3: continue
        up=P[0][1]-(n[0]*(x-P[0][0])+n[2]*(fw-P[0][2]))/n[1]
        # inside test 2D
        xs=P[:,[0,2]]; inside=True; s0=None
        for i in range(len(xs)):
            a,b=xs[i],xs[(i+1)%len(xs)]; cr=(b[0]-a[0])*(fw-a[1])-(b[1]-a[1])*(x-a[0])
            if abs(cr)<1e-9: continue
            s=cr>0
            if s0 is None: s0=s
            elif s!=s0: inside=False;break
        dist=0 if inside else np.min(np.hypot(xs[:,0]-x,xs[:,1]-fw))
        if best is None or dist<best[0]: best=(dist,up)
    return best[1]
# LE / TE lines of the stub (from wing outline)
LE=lambda x: np.interp(x,[-90,-32],[-3,16]); TE=lambda x: np.interp(x,[-84,-33],[-15,-11])
def on_line(line,x0,k):   # intersect x = x0 + k*fwd with fwd=line(x)
    x=x0
    for _ in range(30): x=x0+k*line(x)
    return x,line(x)
le_b=on_line(LE,XB0,XBK); te_b=on_line(TE,XB0,XBK)
overlay=[]
for top,cr in ((True,CRACK_TOP),(False,CRACK_BOT)):
    # crack quad: outer edge on break line, inner edge CRACK_W further in
    pts2=[te_b,le_b,(le_b[0]+CRACK_W,LE(le_b[0]+CRACK_W)),(te_b[0]+CRACK_W,TE(te_b[0]+CRACK_W))]
    uvs=[(cr[0],cr[1]),(cr[0],cr[3]),(cr[2],cr[3]),(cr[2],cr[1])]
    overlay.append((top,pts2,uvs))
    # spike band along the break line: u 224 (solid) inside, 203 outside; v along chord
    pts2=[(te_b[0]-BAND_OUT,te_b[1]),(le_b[0]-BAND_OUT,le_b[1]),(le_b[0]+BAND_IN,le_b[1]),(te_b[0]+BAND_IN,te_b[1])]
    uvs=[(SPIKE[0],SPIKE[1]),(SPIKE[0],SPIKE[3]),(SPIKE[2],SPIKE[3]),(SPIKE[2],SPIKE[1])]
    overlay.append((top,pts2,uvs))
hdr,TB=WP.load(BPIC); TW=WP.load(WPIC)[1]; pk=WP.Packer(TB); sh={}
for r in ((85,101,159,168),(202,193,225,296)): sh[r]=pk.add(TW,*r)
def remap(uv):
    for r,(su,sv) in sh.items():
        if all(r[0]<=u<=r[2] and r[1]<=v<=r[3] for u,v in uv): return [(u+su,v+sv) for u,v in uv]
    raise Exception(uv)
for top,pts2,uvs in overlay:
    P=[np.array([x,surf(x,fw,top)+(0.0),fw]) for x,fw in pts2]
    # winding: match a wing face of same side (normal sign)
    nrm=(0,32767 if top else -32767,0)
    A=sum(P[i][0]*P[(i+1)%4][2]-P[(i+1)%4][0]*P[i][2] for i in range(4))
    ref=next(q for q in polys if q['top']==top and abs(q['nrm'][1])>30000)
    Ar=sum(q[0]*r[2]-r[0]*q[2] for q,r in zip(ref['P'],ref['P'][1:]+ref['P'][:1]))
    if np.sign(A)!=np.sign(Ar): P=P[::-1]; uvs=uvs[::-1]
    polys.append(dict(fl=OVFL,col=0,nrm=nrm,P=P,uv=remap(uvs),top=top,ov=True))
T=pk.build(); print('PIC',TB.shape,'->',T.shape)
# vertices: round to ints (1 ft); merge
def key(p): return tuple(int(round(v)) for v in p)
V=[]; vid={}
for q in polys:
    q['K']=[]
    for p in q['P']:
        k=key(p)
        if k not in vid: vid[k]=SLOT+len(V); V.append(k)
        if not q['K'] or q['K'][-1]!=k: q['K'].append(k)
    if len(q['K'])>1 and q['K'][0]==q['K'][-1]: q['K'].pop()
code=bytearray(c[HDR:PART]); code+=struct.pack('<BBHH',0x82,0,len(V),SLOT*8)
for x,u,f in V: code+=struct.pack('<hhh',x-OFF[0],f-OFF[2],u-OFF[1])
nf=0
for q in sorted(polys,key=lambda q:q.get('ov',False)):
    if len(q['K'])<3: print('degenerate drop'); continue
    fl=q['fl']|0x400; uv=[tuple(int(round(t)) for t in w) for w in q['uv']]
    if len(uv)!=len(q['K']):   # dedupe dropped verts: rebuild uv list by first occurrence
        m={}; [m.setdefault(key(p),tuple(int(round(t)) for t in w)) for p,w in zip(q['P'],q['uv'])]; uv=[m[k] for k in q['K']]
    cen=np.mean([np.array(k)-OFF for k in q['K']],0).round().astype(int)
    b=struct.pack('<BHH',0xFC,fl,q['col'])
    if fl&0x60: b+=struct.pack('<hhh',*q['nrm'])+(struct.pack('<bbb',*cen) if fl&0x200 else struct.pack('<hhh',*cen))
    b+=bytes([len(q['K'])])+b''.join(struct.pack('<H',vid[k]) for k in q['K'])
    if fl&4: b+=b''.join((bytes(w) if fl&0x100 else struct.pack('<HH',*w)) for w in uv)
    code+=b; nf+=1
code+=b'\x1e'
print('stub verts',len(V),'faces',nf,'bytes',len(code),'room',END-HDR)
assert len(code)<=END-HDR
c[HDR:HDR+len(code)]=code; c[HDR+len(code):END]=b'\x00'*(END-HDR-len(code))
for q in C4S: struct.pack_into('<h',c,q+14,PART-(q+16))
# CE wingtip line: left tip -> outer edge of the stub (relative to pivot)
assert c[0x12]==0xCE and struct.unpack_from('<i',c,0x12+0x10)[0]==-64*256
tipx=(le_b[0]+te_b[0])/2-OFF[0]; tipf=(le_b[1]+te_b[1])/2-OFF[2]
struct.pack_into('<3i',c,0x12+0x10,int(tipx*256),0,int(tipf*256)); print('CE left tip',tipx,tipf)
ops,unk,_=walk(bytes(c)); assert PART in ops
d[co['ro']:co['ro']+co['vs']]=c
old=b'\xE2\x00'+b'_f14.PIC'.ljust(14,b'\0'); new=b'\xE2\x00'+b'_f14_a.PIC'.ljust(14,b'\0')
print('E2 renamed',d.count(old)); d=d.replace(old,new)
assert len(d)<65536
open(OUT,'wb').write(d); WP.save(hdr,T,OPIC); print('wrote',OUT,len(d),OPIC)
