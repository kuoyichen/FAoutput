"""F14_B (flying outer-wing piece): container = current F14.SH; both C8 LOD switches and the main LOD start (0x80)
replaced by a small piece: current left outer wing clipped outside the F14_A break line, centred on its bbox,
torn edge (spike band) + burnt cracks at the break. PIC = F14_A's PIC (same packed texture rows)."""
import sys,struct,os;sys.path.insert(0,'/home/user/fa/tools/shgen');sys.path.insert(0,'.')
import numpy as np
from sh_subdivide import parse_face, pe_sections
from sh_scale import walk
import faces, wreckpic as WP, fixreloc
from clip import clip_poly
BASE='/home/user/fa/SH/F14.SH'; BPIC='/home/user/fa/PIC/_F14.PIC'; WPIC='/home/user/fa/PIC/_F14_A.PIC'  # repo _F14_A.PIC = new A (v2)
OUT=sys.argv[1] if len(sys.argv)>1 else 'wk/F14_B_1.SH'; OPIC=sys.argv[2] if len(sys.argv)>2 else 'wk/_F14_B_1.PIC'
XB0,XBK=-60.0,0.3; xb=lambda f: XB0+XBK*f
START=0x80; END=0x4906; SLOT=0
CRACK_W=14; BAND_IN,BAND_OUT=1.0,3.0
OVFL=0x6cd
d=bytearray(open(BASE,'rb').read()); pe,opt,secs=pe_sections(d); co=next(s for s in secs if s['name']=='CODE')
c=bytearray(d[co['ro']:co['ro']+co['vs']])
_,_,_,F=faces.get(BASE)
W=[f for f in F if f.get('part')==0x39fe]
seen=set(); WF=[]
for f in W:
    k=tuple(sorted(tuple(int(v) for v in p) for p in f['P']))+(int(f['n'][1]>0),)
    if k in seen: continue
    seen.add(k); WF.append(f)
fn=lambda p: xb(p[2])-p[0]          # keep x <= break
polys=[]
for f in WF:
    pf=parse_face(c,f['o']); P=[np.array(p,float) for p in f['P']]
    Pc,Uc=clip_poly(P,f['uv'],fn)
    if len(Pc)<3: continue
    nrm=struct.unpack_from('<hhh',pf['head'],4)
    polys.append(dict(fl=pf['fl'],col=pf['col'],nrm=nrm,P=Pc,uv=Uc,top=nrm[1]>0))
print('wing faces',len(polys))
LE=lambda x: np.interp(x,[-96,-90,-32],[-16,-3,16]); TE=lambda x: np.interp(x,[-96,-90,-84,-33],[-16,-16,-15,-11])
def on_line(line,x0,k):
    x=x0
    for _ in range(30): x=x0+k*line(x)
    return x,line(x)
le_b=on_line(LE,XB0,XBK); te_b=on_line(TE,XB0,XBK)
TOPUP,BOTUP=4.0,4.0
# textures: same packing as F14_A
hdr,TB=WP.load(BPIC); TW=WP.load('/home/user/fa/PIC/_F14_A.PIC')[1]
pk=WP.Packer(TB); sh={}
OLDA=WP.load('/tmp/claude-0/oldA.PIC')[1] if os.path.exists('/tmp/claude-0/oldA.PIC') else None
for r in ((85,101,159,168),(202,193,225,296)): sh[r]=pk.add(OLDA,*r)
def remap(uv):
    for r,(su,sv) in sh.items():
        if all(r[0]<=u<=r[2] and r[1]<=v<=r[3] for u,v in uv): return [(u+su,v+sv) for u,v in uv]
    raise Exception(uv)
T=pk.build(); assert (T==TW).all(), 'packing differs from F14_A PIC'
CRACK_TOP=(86,135,158,167); CRACK_BOT=(86,102,158,134); SPIKE=(203,194,224,295)
for top,cr in ((True,CRACK_TOP),(False,CRACK_BOT)):
    up=TOPUP if top else BOTUP
    # crack: inner edge (u158 side) at the break, outer edge CRACK_W further out (u86)
    pts=[te_b,le_b,(le_b[0]-CRACK_W,LE(le_b[0]-CRACK_W)),(te_b[0]-CRACK_W,TE(te_b[0]-CRACK_W))]
    uvs=[(cr[2],cr[1]),(cr[2],cr[3]),(cr[0],cr[3]),(cr[0],cr[1])]
    yield_=[(pts,uvs)]
    # spike band: solid (u224) just outside the break, spikes (u203) reaching inward
    pts=[(te_b[0]+BAND_OUT,te_b[1]),(le_b[0]+BAND_OUT,le_b[1]),(le_b[0]-BAND_IN,le_b[1]),(te_b[0]-BAND_IN,te_b[1])]
    uvs=[(SPIKE[0],SPIKE[1]),(SPIKE[0],SPIKE[3]),(SPIKE[2],SPIKE[3]),(SPIKE[2],SPIKE[1])]
    yield_.append((pts,uvs))
    ref=next(q for q in polys if q['top']==top and abs(q['nrm'][1])>30000)
    Ar=sum(a[0]*b[2]-b[0]*a[2] for a,b in zip(ref['P'],ref['P'][1:]+ref['P'][:1]))
    for pts,uvs in yield_:
        P=[np.array([x,up,f]) for x,f in pts]
        A=sum(P[i][0]*P[(i+1)%4][2]-P[(i+1)%4][0]*P[i][2] for i in range(4))
        if np.sign(A)!=np.sign(Ar): P=P[::-1]; uvs=uvs[::-1]
        polys.append(dict(fl=OVFL,col=0,nrm=(0,32767 if top else -32767,0),P=P,uv=remap(uvs),top=top,ov=True))
# centre on bbox
allP=np.concatenate([np.array(q['P']) for q in polys]); CEN=np.round((allP.min(0)+allP.max(0))/2)
print('piece bbox',allP.min(0),allP.max(0),'centre',CEN)
key=lambda p: tuple(int(round(v)) for v in (np.array(p)-CEN))
V=[]; vid={}
for q in polys:
    q['K']=[]; q['U']=[]
    for p,w in zip(q['P'],q['uv']):
        k=key(p)
        if k not in vid: vid[k]=SLOT+len(V); V.append(k)
        if q['K'] and q['K'][-1]==k: continue
        q['K'].append(k); q['U'].append(tuple(int(round(t)) for t in w))
    if len(q['K'])>1 and q['K'][0]==q['K'][-1]: q['K'].pop(); q['U'].pop()
code=bytearray(struct.pack('<BBHH',0x82,0,len(V),SLOT*8))
for x,u,f in V: code+=struct.pack('<hhh',x,f,u)
for q in sorted(polys,key=lambda q:q.get('ov',False)):
    if len(q['K'])<3: continue
    fl=q['fl']&~0x02; wide=any(vid[k]>255 for k in q['K'])
    fl=(fl|0x400) if wide else (fl&~0x400)
    cen=np.mean(q['K'],0).round().astype(int)
    b=struct.pack('<BHH',0xFC,fl,q['col'])
    if fl&0x60: b+=struct.pack('<hhh',*q['nrm'])+(struct.pack('<bbb',*cen) if fl&0x200 else struct.pack('<hhh',*cen))
    b+=bytes([len(q['K'])])+b''.join((struct.pack('<H',vid[k]) if wide else bytes([vid[k]])) for k in q['K'])
    if fl&4: b+=b''.join((bytes(w) if fl&0x100 else struct.pack('<HH',*w)) for w in q['U'])
    code+=b
code+=b'\x1e'
print('verts',len(V),'bytes',len(code))
c[START:START+len(code)]=code
for p in (0x5a,0x62): assert c[p]==0xC8; struct.pack_into('<h',c,p+6,START-(p+8))
assert c[0x6a]==0xA6; struct.pack_into('<h',c,0x6a+2,START-(0x6a+6))
ops,unk,_=walk(bytes(c)); print('reachable ops',len(ops))
d[co['ro']:co['ro']+co['vs']]=c
old=b'\xE2\x00'+b'_f14.PIC'.ljust(14,b'\0'); new=b'\xE2\x00'+b'_f14_b.PIC'.ljust(14,b'\0')
d=d.replace(old,new); open(OUT,'wb').write(d)
print('reloc neutralised',fixreloc.fix(BASE,OUT,[(START,START+len(code))]))
WP.save(hdr,T,OPIC); print('wrote',OUT,OPIC)
