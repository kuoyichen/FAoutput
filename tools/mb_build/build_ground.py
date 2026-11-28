"""Ground-texture tiles for the Mission Builder 3D view.
usage: python tools/mb_build/build_ground.py TILE_DIR LAY_DIR
TILE_DIR: the map tile PICs from FA_1.LIB (WTA30.PIC, K000004.PIC, OCEAN0.PIC ...); LAY_DIR: DAY2*.LAY from FA_2.LIB.
Writes tools/mb_assets/ground/<TILE>.png (8-bit palette PNG, index 255 = transparent: the sea shows through), north-up
for tmap rotation 0; rotation 1 = turned 90 degrees clockwise, 2 = 180, 3 = 90 counter-clockwise (tile N covers cells
x..x+3, y..y+3, row 0 = south).
Colours: PALETTE.PAL for 0..191; 192..255 from the map's day layer (.MM 'layer day2X.LAY'), the bright-day record
at LAY offset 0x760: indices 224..255 at +0x13, 192..223 at +0x73 (6-bit RGB). 192..197 vegetation, 198..207 rock/soil,
208..223 the land colour of untextured T2 cells (T2 colour byte), 240..254 water, 249..252 open sea (OCEAN*.PIC).
Also writes ground/pal_<LAY>.json (the 256 RGB colours) for the T2 cell colours and the sea."""
import os, re, sys, glob, json
from PIL import Image
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
tdir, ldir = sys.argv[1], sys.argv[2]
OUT = os.path.join(R, 'tools', 'mb_assets', 'ground'); os.makedirs(OUT, exist_ok=True)
base = open(os.path.join(R, 'PIC', 'PALETTE.PAL'), 'rb').read()[:768]
def lay_pal(name):
    b = open(os.path.join(ldir, name.upper()), 'rb').read(); r = 0x760
    p = bytearray(base)
    p[224*3:256*3] = b[r + 0x13:r + 0x13 + 96]; p[192*3:224*3] = b[r + 0x73:r + 0x73 + 96]
    return bytes(min(255, v * 4 + (v >> 4)) for v in p)
def tile(path):
    b = open(path, 'rb').read(); n = 256 if len(b) > 60000 else 128
    return n, b[64:64 + n * n]   # rows as stored: with tmap rotation 0 this is the tile north-up
pals = {}; count = 0
for mm in sorted(glob.glob(os.path.join(R, 'MAP', '*.MM'))):
    s = open(mm, 'rb').read().decode('latin1'); key = os.path.basename(mm)[:-3].upper()
    lay = (re.search(r'^layer\s+(\S+)', s, re.M) or [None, 'day2.LAY'])[1].upper()
    if lay not in pals:
        pals[lay] = lay_pal(lay)
        json.dump([list(pals[lay][3*i:3*i+3]) for i in range(256)], open(os.path.join(OUT, 'pal_' + lay[:-4] + '.json'), 'w'), separators=(',', ':'))
    pre = 'TVI' if key == 'TVIET' else key
    names = {pre + m.group(1) for m in re.finditer(r'^tmap\s+\d+\s+\d+\s+(\d+)', s, re.M)}
    names |= {m.group(1).upper() for m in re.finditer(r'^tmap_named\s+(\S+)', s, re.M)}
    for nm in sorted(names):
        src = os.path.join(tdir, nm + '.PIC')
        if not os.path.exists(src): print('missing', nm); continue
        n, px = tile(src); im = Image.frombytes('P', (n, n), px); im.putpalette(pals[lay])
        im.info['transparency'] = 255; im.save(os.path.join(OUT, nm + '.png'), optimize=True, transparency=255); count += 1
# open sea texture, with the default day palette
n, px = tile(os.path.join(tdir, 'OCEAN0.PIC')); im = Image.frombytes('P', (n, n), px); im.putpalette(pals['DAY2.LAY']); im.save(os.path.join(OUT, 'OCEAN0.png'), optimize=True)
print(count, 'tiles,', len(pals), 'layers')
