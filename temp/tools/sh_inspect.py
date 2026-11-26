#!/usr/bin/env python3
"""List an SH's structure: LOD starts, 82 buffers, C4 parts, F0 x86 blocks (vars they test, C4 fields they patch,
bytecode they resume at), AB flame block. Usage: sh_inspect.py X.SH"""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools', 'shgen'))
from sh_subdivide import pe_sections
import capstone, re
SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])

def load(path):
    d = open(path, 'rb').read()
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE')
    c = d[code['ro']:code['ro'] + code['vs']]
    return d, pe, secs, code, c

def thunks(d, secs, code, c):
    """CODE offset of each import thunk (ff 25 [IAT]) -> import name"""
    tail = c.find(SIG); out = {}
    idata = next(s for s in secs if s['name'] == '.idata')
    rva2off = lambda r: idata['ro'] + r - idata['va']
    p = tail + len(SIG)
    while p + 6 <= len(c):
        if c[p:p+2] == b'\xff\x25':
            iat = struct.unpack_from('<I', c, p + 2)[0]
            try:
                hint = struct.unpack_from('<I', d, rva2off(iat))[0]
                nm = d[rva2off(hint) + 2: rva2off(hint) + 40].split(b'\0')[0].decode()
            except Exception: nm = '?'
            out[p] = nm; p += 6
        else: p += 1
    return out

def c4s(c):
    out = []
    for p in range(len(c) - 16):
        if c[p] == 0xC4 and c[p+1] == 0:
            t = p + 16 + struct.unpack_from('<h', c, p + 14)[0]
            if 0 <= t < len(c) - 6 and c[t] == 0x82 and c[t+1] == 0:
                n, slot = struct.unpack_from('<HH', c, t + 2)
                out.append(dict(at=p, pos=struct.unpack_from('<3h', c, p + 2), ang=struct.unpack_from('<3h', c, p + 8), tgt=t, n=n, slot=slot // 8))
    return out

def f0s(c, code, th):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    out = []
    p = 0
    while True:
        p = c.find(b'\xf0\x00', p)
        if p < 0: break
        ins = []; vars_ = set(); fields = set(); resume = []
        for i in md.disasm(c[p+2:p+2+400], code['va'] + p + 2):
            ins.append(f'{i.mnemonic} {i.op_str}')
            if i.mnemonic == 'push' and i.op_str.startswith('0x'):
                v = int(i.op_str, 16) - code['va']
                if 0 <= v < len(c): resume.append(v)
            for tok in i.op_str.replace('[', ' ').replace(']', ' ').replace(',', ' ').split():
                if re.fullmatch(r'0x[0-9a-f]+', tok):
                    v = int(tok, 16) - code['va']
                    if v in th: vars_.add(th[v])
            if 'ebx +' in i.op_str and i.mnemonic == 'mov' and 'word ptr [ebx' in i.op_str:
                fields.add(i.op_str.split('[')[1].split(']')[0])
            if i.mnemonic == 'ret': break
        if ins and ins[-1] == 'ret ':
            out.append(dict(at=p, vars=sorted(vars_), fields=sorted(fields), resume=resume, n=len(ins)))
            p += 2
        else: p += 2
    return out

def main(path):
    d, pe, secs, code, c = load(path)
    th = thunks(d, secs, code, c)
    tail = c.find(SIG)
    nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    print(f'{os.path.basename(path)}: {len(d)} B, CODE vs {code["vs"]:#x}, sig at {tail:#x}, room {nxt - code["va"] - code["vs"]}, shift {struct.unpack_from("<H", c, 6)[0]}')
    print('imports', {hex(k): v for k, v in th.items()})
    for s in secs: print('  sec', s['name'], hex(s['va']), hex(s['vs']), hex(s['rs']))
    p = 0
    while True:
        p = c.find(b'\x82\x00', p)
        if p < 0 or p > tail: break
        n, slot = struct.unpack_from('<HH', c, p + 2)
        if 0 < n < 900 and slot % 8 == 0 and slot // 8 < 900 and p + 6 + 6*n < tail and c[p+6+6*n] in (0xF6, 0xFC, 0x06, 0x1E, 0x00, 0x0C, 0x0E, 0x10, 0x12, 0x38, 0x48, 0xC4, 0xF0, 0x82, 0x6C, 0x40):
            V = [struct.unpack_from('<3h', c, p + 6 + 6*k) for k in range(n)]
            lo = [min(v[k] for v in V) for k in range(3)]; hi = [max(v[k] for v in V) for k in range(3)]
            print(f'  82 @{p:#06x} n={n:3d} slot={slot//8:3d}  x {lo[0]}..{hi[0]} fwd {lo[1]}..{hi[1]} up {lo[2]}..{hi[2]}')
            p += 6 + 6*n
        else: p += 1
    for e in c4s(c): print(f'  C4 @{e["at"]:#06x} pos={e["pos"]} ang={e["ang"]} -> 82 @{e["tgt"]:#06x} n={e["n"]} slot={e["slot"]}')
    for e in f0s(c, code, th): print(f'  F0 @{e["at"]:#06x} vars={e["vars"]} fields={e["fields"]} resume={[hex(r) for r in e["resume"]]} ins={e["n"]}')

if __name__ == '__main__': main(sys.argv[1])
