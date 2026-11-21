#!/usr/bin/env python3
"""F-14 陰影跟著機翼後掠（Kuoyi 2026-11-21）：停機時機翼過度後掠到 75°，但陰影 F14_S.SH 還是全展。

為什麼陰影不會動：FA.EXE 0x4a7d3e 把陰影加進畫面清單時，物件代號（參數 8）固定給 0，
所以畫陰影時 0x4ab450 拿到 0 號，_PLswingWing 一直是 0、word [0x580BEC] 也是 0，
陰影的兩個後掠翼 F0 永遠算出航向 0（全展），而且不知道是哪一架飛機的陰影。

做法：陰影 F0 原本的 `mov ax,[_PLswingWing]` 保留，後面 14 位元組
（mov cx,ax; sar ax,2; sar cx,5; sub ax,cx）換成 call 子程式 + nop。子程式：
  * 用畫面紀錄找回飛機：畫陰影時紀錄被抄到 0x51ce00，+0x12/+0x1a = 攝影機 [0x518316]/[0x51831e]
    減掉陰影位置；陰影的 x、z 就是飛機的 +0x11、+0x19（0x4a7d2f/0x4a7d37），所以
    x = [0x518316]-[0x51ce12]、z = [0x51831e]-[0x51ce1a]，在物件表 0x553848 裡找 class 4 且 x、z 完全相同的。
  * 找到後照 F14 主體同一套：swing = 物件 +0x1A1，正常航向 = s/4 + s/64（和 F14.SH 機翼 C4 一樣），
    停在地上、速度 0、起落架放下 → 4 秒後掠到 55*182；後燃器 3 秒全展；新出現或 1 秒沒畫就直接跳到目標。
  * 找不到就回傳 0（原本的樣子）。
陰影是 1/4 比例（樞軸 ±8、前 4 = 主體 ±32、16 的 1/4），同一個航向角就對得上主體。
用法：python3 f14_shadow_sweep.py F14_S.SH 輸出.SH
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, insert_blocks
from f14_park_sweep import SIG, OVER, AGL_MAX, FOLD_MS, UNF_MS

NORMAL_S = bytes.fromhex('668bc866c1f80266c1f905662bc1')   # mov cx,ax; sar ax,2; sar cx,5; sub ax,cx
NOBJ = 900

def sub_x86(tbl_rel):
    return f"""
        pushfd
        pushad
        call nx
    nx:
        pop ebx
        xor ebp, ebp
        mov edx, dword ptr [0x518316]
        sub edx, dword ptr [0x51ce12]
        mov edi, dword ptr [0x51831e]
        sub edi, dword ptr [0x51ce1a]
        mov ecx, 1
    find:
        mov esi, dword ptr [ecx*4 + 0x553848]
        test esi, esi
        jz nxt
        cmp byte ptr [esi], 4
        jne nxt
        cmp dword ptr [esi + 0x11], edx
        jne nxt
        cmp dword ptr [esi + 0x19], edi
        je found
    nxt:
        inc ecx
        cmp ecx, {NOBJ}
        jb find
        jmp out
    found:
        movsx ebp, word ptr [esi + 0x1a1]
        mov eax, ebp
        sar eax, 2
        sar ebp, 6
        add ebp, eax
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
        test byte ptr [esi + 0x16f], 0x20
        jz noab
        xor edi, edi
    noab:
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
        movzx eax, word ptr [edx + 2]
        cmp eax, edi
        jl up
        imul esi, esi, {round(1024 * 1024 / UNF_MS)}
        shr esi, 10
        sub eax, esi
        cmp eax, edi
        jge done
        mov eax, edi
        jmp done
    up:
        imul esi, esi, {round(1024 * 1024 / FOLD_MS)}
        shr esi, 10
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
        add ebp, ecx
    out:
        mov dword ptr [esp + 28], ebp
        popad
        popfd
        ret
    """

def main():
    src, dst = sys.argv[1:3]
    d = bytearray(open(src, 'rb').read())
    pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE')
    c = bytearray(d[code['ro']:code['ro'] + code['vs']])
    tail = bytes(c).find(SIG)
    sites = [j + 6 for j in range(tail) if c[j:j+2] == b'\x66\xa1' and c[j+6:j+20] == NORMAL_S]
    assert len(sites) == 2, [hex(s) for s in sites]
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    code0 = bytes(ks.asm(sub_x86(0x1000), 0)[0])
    sub_len = (len(code0) + 3) & ~3
    blk_sub = bytes(ks.asm(sub_x86(sub_len - 7), 0)[0])   # ebx = sub+7
    assert len(blk_sub) == len(code0)
    blk = blk_sub + b'\x90' * (sub_len - len(blk_sub)) + bytes(32 * 8)
    nxt = min(s['va'] for s in secs if s['va'] > code['va'])
    assert len(blk) <= nxt - code['va'] - len(c), 'CODE VA room'
    for s in sites:
        c[s:s + 14] = b'\xe8' + struct.pack('<i', tail - (s + 5)) + b'\x90' * 9
    out = insert_blocks(d, pe, secs, code, c, tail, blk)
    open(dst, 'wb').write(out)
    print(f'{dst}: {len(out)} B, 子程式 {len(blk_sub)} B + 表 256 B 在 CODE+{tail:#x}，改了 F0 {[hex(s) for s in sites]}')

if __name__ == '__main__': main()
