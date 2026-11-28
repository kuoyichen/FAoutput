# Convert FA .PIC (format 0 raw rows, format 1 span list) to RGBA PNG; index 0xFF = transparent.
# Used to make tools/mb_assets from the factory MCICONS/MSNCREA3/PANEL/SLIDERH/SLIDERV/MAPFONT files.
import struct,sys,os
from PIL import Image
def pal(b,o):
    p=b[o:o+768]; m=max(p)
    return bytes(min(255,c*4) if m<64 else c for c in p)
def load(path,fallback):
    b=open(path,'rb').read()
    fmt,w,h,po,ps,pao,pas=struct.unpack('<HIIIIII',b[:26])
    ro,rs=struct.unpack('<II',b[0x22:0x2a])
    if fmt!=0 or ps!=w*h: return None,(fmt,w,h,ps)
    p=pal(b,pao) if pas else fallback
    offs=struct.unpack('<%dI'%h,b[ro:ro+rs]) if rs==4*h else [po+i*w for i in range(h)]
    idx=b''.join(b[o:o+w] for o in offs)
    im=Image.frombytes('P',(w,h),idx); im.putpalette(p)
    rgba=im.convert('RGBA'); a=Image.frombytes('L',(w,h),bytes(0 if v==255 else 255 for v in idx)); rgba.putalpha(a)
    return rgba,idx
def load1(path,fallback):
    b=open(path,'rb').read()
    fmt,w,h,po,ps,pao,pas,to,ts=struct.unpack('<HIIIIIIII',b[:34])
    if fmt==0: return load(path,fallback)
    p=pal(b,pao) if pas else fallback
    idx=bytearray([255]*(w*h))
    for i in range(ts//10):
        y,x0,x1,o=struct.unpack('<HHHI',b[to+i*10:to+i*10+10])
        if y==0xffff: break
        for x in range(x0,x1+1): idx[y*w+x]=b[po+o+x-x0]
    idx=bytes(idx)
    im=Image.frombytes('P',(w,h),idx); im.putpalette(p)
    rgba=im.convert('RGBA'); rgba.putalpha(Image.frombytes('L',(w,h),bytes(0 if v==255 else 255 for v in idx)))
    return rgba,idx
