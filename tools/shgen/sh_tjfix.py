#!/usr/bin/env python3
"""補頂點修改後產生的縫隙（T 接點與重合頂點）。

用法：python3 sh_tjfix.py 原檔.SH 改過.SH 輸出.SH
  * 在原檔中找「頂點落在別的面的邊上」(T 接點) 和「不同緩衝區座標相同的頂點」(例如 flaps 與主翼)
  * 改過的檔案若不再成立：重合頂點跟著主緩衝區的值；T 接點頂點投影到該邊上最近的整數點
  * 只被一個面用到的頂點（貼花/標誌角點）不動
  * 之後請再跑 sh_renormal.py 原檔 輸出 輸出 重算法向量
  * 預設分組為 F18 系列：高 LOD 主體+flaps（緩衝 0,1,5-8）、中 LOD（12）、低 LOD（15）
"""
import sys,struct,itertools,numpy as np
import os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import sh_renormal as R
SIG=bytes([1,2,3,2,1,2,3,2,1])
def scan(path):
    d=open(path,'rb').read(); ro,vs=R.code_of(d); c=d[ro:ro+vs]; stop=c.find(SIG)
    o=c.find(b'\xe2\x00')+16; bufs=[]; tab={}; faces=[]
    while o<stop-6:
        if c[o]==0x82 and c[o+1]==0:
            n,t=struct.unpack_from('<HH',c,o+2)
            if 0<n<900 and t%8==0 and t//8+n<=900:
                b=len(bufs); bufs.append((o,n,t//8,[list(struct.unpack_from('<hhh',c,o+6+6*k)) for k in range(n)]))
                for k in range(n): tab[t//8+k]=(b,k)
                o+=6+6*n; continue
        if c[o]==0xFC:
            f=R.parse_face(c,o)
            if f and f['fl']&0x60 and not f['fl']&0xF000 and (f['fl']&0xFF) in R.FACE_OPS and len(set(f['idx']))==f['n'] and all(i in tab for i in f['idx']) and f['end']<=stop:
                faces.append((o,[tab[i] for i in f['idx']])); o=f['end']; continue
        o+=1
    return d,ro,bufs,faces
def rel(bufs,faces,allowed):
    P=lambda v: np.array(bufs[v[0]][3][v[1]],float)
    edges=set()
    for o,ids in faces:
        if not all(v[0] in allowed for v in ids): continue
        for k in range(len(ids)): a,b=ids[k],ids[(k+1)%len(ids)]; edges.add(tuple(sorted((a,b))))
    verts=[(b,k) for b in allowed for k in range(bufs[b][1])]
    out=[]
    for a,b in edges:
        A,B=P(a),P(b); ab=B-A; L2=ab@ab
        if L2==0: continue
        for v in verts:
            if v in (a,b): continue
            p=P(v); t=(p-A)@ab/L2
            if 0.02<t<0.98 and np.linalg.norm(A+t*ab-p)<0.6: out.append((v,a,b,t))
    return out

def best_int(p,A,B,r=1):
    """integer point near p that lies closest to line AB (prefers small move), not an endpoint"""
    ab=B-A; ab=ab/np.linalg.norm(ab); best=None
    base=np.round(p).astype(int)
    for d in itertools.product(range(-r,r+1),repeat=3):
        q=base+np.array(d)
        if (q==A).all() or (q==B).all(): continue
        w=q-A; dist=np.linalg.norm(w-(w@ab)*ab)
        s=dist+0.15*np.linalg.norm(q-p)
        if best is None or s<best[0]: best=(s,q,dist)
    return best[1],best[2]

def fix(orig,mod,out,groups,tol=0.75,verbose=True):
    _,_,BO,FO=scan(orig); d,ro,BM,FM=scan(mod)
    BM=[list(b) for b in BM]; P=lambda B,v: np.array(B[v[0]][3][v[1]],float)
    log=[]
    for allowed in groups:
        verts=[(b,k) for b in allowed for k in range(BO[b][1])]
        # 1) coincident vertices in orig must stay coincident: follow the main (first) buffer's copy
        byc={}
        for v in verts: byc.setdefault(tuple(BO[v[0]][3][v[1]]),[]).append(v)
        for key,vs in byc.items():
            if len(vs)<2: continue
            vals=[tuple(BM[v[0]][3][v[1]]) for v in vs]
            if len(set(vals))>1:
                # majority among main-buffer copies, else first
                main=[x for v,x in zip(vs,vals) if v[0]==allowed[0]] or vals
                tgt=max(set(main),key=main.count)
                for v,x in zip(vs,vals):
                    if x!=tgt: log.append(('same',v,x,tgt)); BM[v[0]][3][v[1]]=list(tgt)
        # 2) T-junctions
        use={}
        for o_,ids in FO:
            for v in ids: use[v]=use.get(v,0)+1
        R_=[r for r in rel(BO,FO,allowed) if use.get(r[0],0)>=2]   # 1-face vertices are decal corners
        for it in range(3):
            ch=0
            for v,a,b,t in R_:
                A,B=P(BM,a),P(BM,b); p=P(BM,v); ab=B-A
                tt=(p-A)@ab/(ab@ab); dist=np.linalg.norm(A+tt*ab-p)
                if dist>tol:
                    q,dd=best_int(A+tt*ab,A,B)
                    log.append(('T',v,tuple(p.astype(int)),tuple(q),(a,b),round(dist,2),round(dd,2)))
                    newv=list(int(x) for x in q)
                    # keep copies coincident
                    key=tuple(BO[v[0]][3][v[1]])
                    for w in byc.get(key,[v]): BM[w[0]][3][w[1]]=newv
                    ch+=1
            if not ch: break
    o=bytearray(d)
    for off,n,t,Pv in BM:
        for k in range(n): struct.pack_into('<hhh',o,ro+off+6+6*k,*Pv[k])
    open(out,'wb').write(o)
    if verbose:
        for l in log: print(l)
    return log


if __name__=='__main__':
    if len(sys.argv)!=4: sys.exit(__doc__)
    fix(sys.argv[1],sys.argv[2],sys.argv[3],[[0,1,5,6,7,8],[12],[15]])
