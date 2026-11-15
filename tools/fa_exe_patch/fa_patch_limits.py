"""Make a test copy of FA.EXE with bigger limits. Never touches the input file.
usage: python fa_patch_limits.py FA.EXE FA_BIG.EXE
 - object memory pool 300,000 -> 1,500,000 bytes   (push imm at 0x480944)
 - file index 9,950 -> 100,000 entries             (mov ecx imm at 0x478c0a)
 - .LIB files 20 -> 256 (name/handle tables moved into .rmcache)
 - resource cache 1,400 -> 4,096 entries, table moved to a new zeroed section .rmcache
Object count (900) is NOT changed: its tables have 580+ references.
"""
import sys, struct
src, dst = sys.argv[1], sys.argv[2]
assert src.lower() != dst.lower()
d = bytearray(open(src, 'rb').read())
BASE = 0x400000
def off(va): return va - BASE - 0x1000 + 0x400          # .text only
def imm(va, old, new, ilen):
    o = off(va); seg = d[o:o+ilen]
    k = seg.find(struct.pack('<I', old))
    assert k >= 0, (hex(va), seg.hex())
    d[o+k:o+k+4] = struct.pack('<I', new)
# 1. pool
imm(0x480944, 0x493e0, 1_500_000, 5)
# 2. file index buffer (35 bytes per entry)
imm(0x478c0a, 0x5505a, 100000*35, 5)
# 3. resource cache table -> new section
NEW_RVA, NEW_SIZE = 0x1AC000, 0x13000           # 4096 entries * 19 bytes
NEW_VA = BASE + NEW_RVA
SEC_SIZE = 0x15000                               # cache + LIB tables
for va in (0x4a67f3, 0x4a682b, 0x4a6847, 0x4a68f1, 0x4a6a21, 0x4a6d6e, 0x4a6dba):
    imm(va, 0x503e30, NEW_VA, 5)
for va in (0x4a683f, 0x4a6901, 0x4a6a64, 0x4a6d92, 0x4a6dd9):   # loop end compares
    imm(va, 0x50a618, NEW_VA + NEW_SIZE, 6)
for va in (0x4a67f8, 0x4a684e):                                 # rep stosd dword counts
    imm(va, 0x19fa, NEW_SIZE // 4, 5)
# 4. LIB tables: 20 -> 256 (names 14 bytes each, handles 4 bytes each)
NLIB = 256
NAMES = NEW_VA + NEW_SIZE                 # 0x5BF000, 256*14 = 0xE00
PTRS  = NAMES + 0xE00                     # 0x5BFE00, 256*4 = 0x400
imm(0x478d8e, 0x54a530, NAMES, 5)         # mov edi, names (skip LIB already opened)
imm(0x478eef, 0x54a530, NAMES, 7)         # lea edi, [edx*2+names]
imm(0x478eca, 0x54a648, PTRS, 7)          # mov [eax*4+ptrs], ebp
imm(0x4792f3, 0x54a648, PTRS, 5)          # teardown: free each LIB
imm(0x479310, 0x54a648, PTRS, 5)          # teardown: clear table
imm(0x479317, 0x14, NLIB, 5)              # rep stosd count
assert PTRS + 4*NLIB <= NEW_VA + SEC_SIZE
# add section header
pe = struct.unpack_from('<I', d, 0x3c)[0]
nsec = struct.unpack_from('<H', d, pe+6)[0]
optsz = struct.unpack_from('<H', d, pe+20)[0]
sh = pe + 24 + optsz + 40*nsec
assert nsec == 6 and sh + 40 <= 0x400 and d[sh:sh+40] == bytes(40)
d[sh:sh+40] = struct.pack('<8sIIIIIIHHI', b'.rmcache', SEC_SIZE, NEW_RVA, 0, 0, 0, 0, 0, 0, 0xC0000080)
struct.pack_into('<H', d, pe+6, nsec+1)
struct.pack_into('<I', d, pe+24+56, NEW_RVA + SEC_SIZE)       # SizeOfImage
struct.pack_into('<I', d, pe+24+64, 0)                         # CheckSum
open(dst, 'wb').write(d)
print('wrote', dst)
