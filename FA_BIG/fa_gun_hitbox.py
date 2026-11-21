"""FA.EXE gun hit-box patch. Never touches the input file.
usage: python fa_gun_hitbox.py FA.EXE OUT.EXE [pad] [minr]
  pad  = extra margin FA adds around every object for projectiles (stock 50, default 0)
  minr = minimum projectile hit radius (stock 20, default 2); only guns use it (missiles/bombs have >= 50 in their JT)
Both values are in FA world units (the same units as SH F2 boxes; F-14 bbox is 191 wide, 58 tall).

How FA tests a projectile against an object (found 2026-11-20):
  mover sweep 0x46345C -> 0x42B800 -> per object 0x42C9B0 -> segment-vs-box clip 0x42D050
  bullet radius R = JT PROJ81 (typedef+0x12A) << 8, raised to 20 at 0x463364 (guns have 0)
  target typedef+9 flag 0x800      -> box grown by R            (0x42D0FB)
  target typedef+9 & 0x1E00, proj  -> box and sphere grown +50  (0x42D10B, 0x42CB84)
  box = SH F2 table bbox, or each F2 box record when the SH has them (nearest hit wins)
  every aircraft PT has 0x800|0x200 -> stock bullet box = bbox + 70 on every side
The CRC32 of the output is forged back to the input's CRC (4 spare bytes after .text), like FA_BIG/crc_match.py.
"""
import sys, struct, zlib
src, dst = sys.argv[1], sys.argv[2]
pad = int(sys.argv[3]) if len(sys.argv) > 3 else 0
minr = int(sys.argv[4]) if len(sys.argv) > 4 else 2
assert src.lower() != dst.lower()
d = bytearray(open(src, 'rb').read()); crc0 = zlib.crc32(d)
def off(va): return va - 0x401000 + 0x400
def put(va, old, new):
    o = off(va); assert d[o:o+len(old)] == old, (hex(va), d[o:o+len(old)].hex()); d[o:o+len(new)] = new
put(0x42CB84, bytes.fromhex('81c200320000'), b'\x81\xc2' + struct.pack('<I', pad << 8))   # sphere: add edx, pad
put(0x42D10B, bytes.fromhex('0500320000'),   b'\x05'     + struct.pack('<I', pad << 8))   # box:    add eax, pad
put(0x463364, bytes.fromhex('81fb00140000'), b'\x81\xfb' + struct.pack('<I', minr << 8))  # cmp ebx, minr
put(0x46336C, bytes.fromhex('bb00140000'),   b'\xbb'     + struct.pack('<I', minr << 8))  # mov ebx, minr
# forge CRC back to the original (so a patched copy still matches the other side in network play)
pos = 0x400 + 0xe7b6c + 0x10
d[pos:pos+4] = b'\0\0\0\0'
base = zlib.crc32(d); cols = []
for i in range(32):
    e = bytearray(d); e[pos+i//8] ^= 1 << (i % 8); cols.append(zlib.crc32(e) ^ base)
basis = {}
for i in range(32):
    v, m = cols[i], 1 << i
    for b in range(31, -1, -1):
        if not (v >> b) & 1: continue
        if b in basis: v ^= basis[b][0]; m ^= basis[b][1]
        else: basis[b] = (v, m); break
v, m = base ^ crc0, 0
for b in range(31, -1, -1):
    if (v >> b) & 1: v ^= basis[b][0]; m ^= basis[b][1]
assert v == 0
for i in range(32):
    if (m >> i) & 1: d[pos+i//8] ^= 1 << (i % 8)
assert zlib.crc32(d) == crc0
open(dst, 'wb').write(d)
print(f'{dst}: pad {pad}, min radius {minr}, crc {crc0:#010x} kept')
