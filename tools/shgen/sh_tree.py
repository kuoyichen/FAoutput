#!/usr/bin/env python3
"""SH 畫面順序樹（BSP）走訪：找出把指定位址分開的節點。

用法：python3 sh_tree.py 檔案.SH 位址1 位址2 ...（CODE 內的位移，例如 0x30d8）
  * 從主 LOD 的 F6 之後的根節點開始，跟著 06/0C/0E/10/6C 的兩個分支、12 呼叫、38/48 跳躍走
  * F0 x86 區塊跟到第一個 push 的回到位址（減 0x1000）
  * 印出 SPLIT：哪個節點的 A、B 分支各包含哪些位址；無法解讀的指令列在 unknown stops
"""
import struct,sys
import os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, main_lod
d=open(sys.argv[1],'rb').read()
pe,opt,secs=pe_sections(d); code=next(s for s in secs if s['name']=='CODE')
c=d[code['ro']:code['ro']+code['vs']]
L=main_lod(c); o0,n,_,e=L[0]
R=e
while c[R]==0xF6: R+=7
h=lambda p: struct.unpack_from('<h',c,p)[0]
unk=set(); nodes=[]
memo={}
def walk(p,depth=0):
    """returns set of visited op addresses"""
    key=p
    if key in memo: return memo[key]
    memo[key]=set()
    vis=set()
    for g in range(3000):
        if not (0<=p<len(c)-2): break
        vis.add(p); op=c[p]
        if op==0xFC:
            fl=struct.unpack_from('<H',c,p+1)[0]; q=p+5
            if fl&0x60: q+=6+(3 if fl&0x200 else 6)
            k=c[q]; q+=1+(2*k if fl&0x400 else k)
            if fl&4: q+=k*(2 if fl&0x100 else 4)
            p=q
        elif op==0xF6: p+=7
        elif op==6 and c[p+1]==0:
            a=p+16+h(p+14); b=p+18+h(p+16); A=walk(a,depth+1); B=walk(b,depth+1); vis|=A|B; nodes.append((p,'06',a,b,A,B)); p+=18
        elif op in (0x0C,0x0E,0x10) and c[p+1]==0:
            a=p+12+h(p+10); b=p+14+h(p+12); A=walk(a,depth+1); B=walk(b,depth+1); vis|=A|B; nodes.append((p,hex(op),a,b,A,B)); p+=14
        elif op==0x6C and c[p+1]==0:
            a=p+8+h(p+6); b=p+10+h(p+8); A=walk(a,depth+1); B=walk(b,depth+1); vis|=A|B; p+=10
        elif op==0x12 and c[p+1]==0:
            vis|=walk(p+4+h(p+2),depth+1); p+=4
        elif op==0x38: p=p+3+h(p+1)
        elif op==0xC4 and c[p+1]==0: p+=16
        elif op==0xF0 and c[p+1]==0:
            r=None
            for q in range(p+2,p+120):
                if c[q]==0x68:
                    v=struct.unpack_from('<I',c,q+1)[0]-0x1000
                    if 0<v<len(c): r=v; break
            if r is None: unk.add(('F0',hex(p))); break
            p=r
        elif op==0x1E or (op==0 and c[p+1]==0): break
        else: unk.add((hex(op),hex(p))); break
    memo[key]=vis
    return vis
walk(R)
print('unknown stops', sorted(unk)[:20])
G=[int(x,16) for x in sys.argv[2:]]
for p,t,a,b,A,B in nodes:
    inA=[g in A for g in G]; inB=[g in B for g in G]
    if any(inA) and any(inB): print('SPLIT', hex(p), t, struct.unpack_from('<6h',c,p+2) if t=='06' else struct.unpack_from('<4h',c,p+2), 'A',hex(a),inA,'B',hex(b),inB)
