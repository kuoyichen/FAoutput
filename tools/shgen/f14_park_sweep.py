#!/usr/bin/env python3
"""F-14 停機過度後掠（Kuoyi 2026-11-20）：停在地上（跑道、航艦甲板、屋頂都算）、速度 0、起落架放下時，
機翼慢慢後掠到 75°（真的 F-14 在甲板上就是這樣收翼），一動就慢慢回到正常後掠。

  * 在地上的判斷照 FA.EXE 0x411910：每個物件 +0x2F 存著腳下表面高度（掃描包含可降落物件的箱頂），
    停著時 y − [+0x2F] = −碰撞盒 ymin（F-14 是 22 ft，用 Kuoyi 的飛行紀錄驗證過）。條件：
      離地 ≤ AGL_MAX、|速度 +0x34| < 1 ft/s、起落架放下（+0x16F 位元 0x40）
  * 原本 6 個後掠翼 F0（3 個 LOD × 左右）：mov ax,[_PLswingWing]; mov cx,ax; sar ax,2; sar cx,6; add ax,cx
    保留第一個 mov（它的重定位不動），後面 14 位元組換成 call 子程式 + nop。子程式回傳 ax = 機翼 C4 航向
    （右翼的 F0 自己會 neg）。
  * 子程式在簽章前的新區塊：每架飛機一格（32 格，物件編號 & 31，存 編號、進度 0..1024、上次時間），
    進度以 FOLD_MS 走完；新出現或超過 1 秒沒畫就直接跳到目標（任務開始就停在甲板上的飛機會直接是收好的）。
    航向 = 正常 + (OVER − 正常) × 進度 / 1024
用法：python3 f14_park_sweep.py 輸入.SH 輸出.SH
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, insert_blocks

SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])
NORMAL = bytes.fromhex('668bc866c1f80266c1f9066603c1')   # mov cx,ax; sar ax,2; sar cx,6; add ax,cx
OVER = 55 * 182          # 正常 20° + 55° = 75°（swing 32767 時是 68°）
AGL_MAX = 25 * 256       # 碰撞盒 ymin -22 ft + 3 ft
FOLD_MS = 4000

def sub_x86(tbl_rel):
    return f"""
        pushfd
        pushad
        call nx
    nx:
        pop ebx
        movsx ebp, word ptr [esp + 28]
        mov eax, ebp
        sar eax, 2
        sar ebp, 6
        add ebp, eax
        movzx ecx, word ptr [0x580bec]
        mov esi, dword ptr [ecx*4 + 0x553848]
        xor edi, edi
        test byte ptr [esi + 0x16f], 0x40
        jz notp
        mov edx, dword ptr [esi + 0x34]
        add edx, 0xff
        cmp edx, 0x1fe
        ja notp
        mov edx, dword ptr [esi + 0x15]
        sub edx, dword ptr [esi + 0x2f]
        cmp edx, {AGL_MAX}
        jg notp
        mov edi, 1024
    notp:
        mov eax, ecx
        and eax, 31
        lea edx, [ebx + eax*8 + {tbl_rel}]
        push edx
        push ecx
        call dword ptr [0x593758]
        pop ecx
        pop edx
        cmp word ptr [edx], cx
        jne snap
        mov esi, eax
        sub esi, dword ptr [edx + 4]
        cmp esi, 1000
        ja snap
        mov dword ptr [edx + 4], eax
        imul esi, esi, {round(1024 * 1024 / FOLD_MS)}
        shr esi, 10
        movzx eax, word ptr [edx + 2]
        cmp eax, edi
        jl up
        sub eax, esi
        cmp eax, edi
        jge done
        mov eax, edi
        jmp done
    up:
        add eax, esi
        cmp eax, edi
        jle done
        mov eax, edi
        jmp done
    snap:
        mov word ptr [edx], cx
        mov dword ptr [edx + 4], eax
        mov eax, edi
    done:
        mov word ptr [edx + 2], ax
        mov ecx, {OVER}
        sub ecx, ebp
        imul ecx, eax
        sar ecx, 10
        add ecx, ebp
        mov dword ptr [esp + 28], ecx
        popad
        popfd
        ret
    """

def find_sites(c, tail, thunk_sw):
    sites = []
    pat = b'\x66\xa1' + struct.pack('<I', thunk_sw) + NORMAL
    i = 0
    while True:
        i = c.find(pat, i)
        if i < 0 or i > tail: break
        sites.append(i + 6); i += 1
    return sites

def main():
    src, dst = sys.argv[1:3]
    d = bytearray(open(src, 'rb').read())
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE'); nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    c = bytearray(d[code['ro']:code['ro'] + code['vs']])
    tail = bytes(c).find(SIG)
    # _PLswingWing 跳板：第一個後掠翼 F0 裡 mov ax,[x] 的 x
    k = bytes(c).find(b'\x66\xa1'); sw = None
    for cand in set(struct.unpack_from('<I', c, j + 2)[0] for j in range(len(c)) if c[j:j+2] == b'\x66\xa1' and c[j+6:j+20] == NORMAL):
        sw = cand
    sites = find_sites(c, tail, sw)
    assert len(sites) == 6, [hex(s) for s in sites]
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    code0 = bytes(ks.asm(sub_x86(0x1000), 0)[0])          # 長度估算
    sub_len = (len(code0) + 3) & ~3
    blk_sub = bytes(ks.asm(sub_x86(sub_len - 7), 0)[0])   # 表在子程式後面；ebx = sub+7（pushfd+pushad+call = 7）
    assert len(blk_sub) == len(code0)
    blk = blk_sub + b'\x90' * (sub_len - len(blk_sub)) + bytes(32 * 8)
    if len(blk) > nxt - code['va'] - len(c):
        from f18g_growler import grow_vas
        d = bytearray(grow_vas(d, 0x1000)); pe, opt, secs = pe_sections(d)
        code = next(s for s in secs if s['name'] == 'CODE')
        c = bytearray(d[code['ro']:code['ro'] + code['vs']])     # grow_vas also rewrites relocated dwords inside CODE: re-read it
    for s in sites:
        rel = tail - (s + 5)
        c[s:s + 14] = b'\xe8' + struct.pack('<i', rel) + b'\x90' * 9
    out = insert_blocks(d, pe, secs, code, c, tail, blk)
    assert len(out) < 65536, len(out)
    open(dst, 'wb').write(out)
    print(f'{dst}: {len(out)} B, 子程式 {len(blk_sub)} B + 表 256 B 在 CODE+{tail:#x}，改了 {len(sites)} 個 F0 {[hex(s) for s in sites]}')

if __name__ == '__main__': main()
