#!/usr/bin/env python3
"""KC-135 空中加油（Kuoyi 2026-11-22）：KC135.SH 裡加 x86，玩家飛到加油機後下方時，硬桿放下並指向玩家，
對準後持續加油，加滿時顯示訊息。全部在 SH 裡完成，不改 FA.EXE。

原檔結構（SH/KC135.SH）：
  * 硬桿是一段獨立的面（CODE 0x44F2，29 點、24 面，模型座標，機尾下方 fwd −63..−143、up −2），
    由 CODE 0x3714 的 F0 判斷 `_PLafterBurner == 1` 時才在 0x372B 呼叫畫出。
  * F2 碰撞表在 CODE 0x73E4：半徑 72704（284 ft）。FA 讓移動物件用「自己的 F2 半徑 / 2」掃過去
    （0x463378），目標若是人類玩家就算撞（0x42CA66），玩家的碰撞盒還會再加大這個半徑（0x42D0FB）。
    玩家撞向友軍 AI 不算撞（0x42CA8F），所以會撞的是加油機掃到玩家。

改法：
  1. 硬桿複製一份做成 C4 零件（頂點與平面點減去樞紐 (0, up −2, fwd −63)），法向量不用改：
     C4（0x4D3194）會把眼睛和光源一起轉進零件座標，旋轉後光影和背面剔除照樣正確。
  2. 0x3714 的 F0 改成跳到新的 x86（舊的兩個重定位位置 0x3718、0x3721 留著不執行）。x86 每次畫加油機時：
       - 找出加油機（[0x553848 + word[0x580BEC]*4]）和玩家（word[0x520A1C]）。
       - 玩家同陣營、存活時，把「玩家受油口」= 玩家位置 + (0, +RECEP_UP, +RECEP_FWD) 換到加油機座標
         （只用加油機航向；右 = dx cos h − dz sin h，前 = dx sin h + dz cos h），再算相對硬桿樞紐的
         後方距離、下方距離、左右、長度、俯角、偏角（x87 fpatan / fsqrt）。
       - 接近區（後方 0..APP_BACK、左右 ±APP_SIDE、下方 −60..APP_DOWN）：硬桿放下指向玩家（俯角 10..45°、
         偏角 ±20°，每秒 20° 平滑移動），並把 F2 半徑暫時改成 SMALL_R（離開就改回原值）。
       - 接上：長度 L_MIN..L_MAX、俯角 15..45°、偏角 ±15°、航向差 ±10°、速度差 ±30 ft/s。
         接上時玩家內油（obj+0x1FC，lb×256）每秒加 RATE lb，到 PT 內油上限（typedef+0x165）為止；
         剛好加滿時送出訊息 " Plane Re-Fueled"（FA 0x48D410 / 0x48D420 / 0x48E950，和 0x48E920 一樣的流程）。
       - 硬桿一律畫出（不再看後燃器）；沒有玩家在附近時收回到原本的水平位置。
用法：python3 kc135_refuel.py 輸入KC135.SH 輸出.SH [預覽.SH]
"""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh_subdivide import pe_sections, insert_blocks
from keystone import Ks, KS_ARCH_X86, KS_MODE_32

SIG = bytes([1, 2, 3, 2, 1, 2, 3, 2, 1])
F0_HOOK = 0x3714            # F0 00 + cmp [_PLafterBurner],1 ...
RESUME = 0x373C             # 原本兩條路最後都回到這裡
BOOM = 0x44F2               # 硬桿 82 緩衝區
BOOM_END = 0x485A           # 下一個零件（襟翼）開始
F2TBL = 0x73E4
PIVOT = (0, -2, -63)        # (x, up, fwd) 頂點單位（1 單位 = 2 ft）
HDR = bytes.fromhex('eb0047001a01')   # 零件範圍標頭，照起落架零件抄

U = 2.0                      # ft / 頂點單位
HINGE_UP, HINGE_FWD = PIVOT[1] * U, PIVOT[2] * U          # −4, −126 ft
RECEP_UP, RECEP_FWD = 20.0, 50.0                          # 玩家受油口相對玩家原點（ft）
APP_BACK, APP_SIDE, APP_DOWN = 1500, 500, 800             # 接近區（ft）
L_MIN, L_MAX = 125, 195                                   # 硬桿全長 160 ft（含伸縮管）
RATE = 50                                                  # lb/s（3000 lb/min）
ORIG_R, SMALL_R = 72704, 40 * 256
DEG = 65536 / 360.0
STEP = 14                                                  # 每 1/256 s 轉 14 單位 ≈ 20°/s
MSG = b' Plane Re-Fueled\0'


def build(src, dst, preview=None):
    d = bytearray(open(src, 'rb').read()); pe, opt, secs = pe_sections(d)
    code = next(s for s in secs if s['name'] == 'CODE')
    c = bytearray(d[code['ro']:code['ro'] + code['vs']])
    tail = c.find(SIG); assert tail > 0
    assert c[F0_HOOK:F0_HOOK + 10] == bytes.fromhex('f000 66833d00840000 01'.replace(' ', ''))
    assert c[0x372B:0x372F] == bytes.fromhex('1200c30d')
    assert c[BOOM:BOOM + 2] == b'\x82\x00' and struct.unpack_from('<i', c, F2TBL)[0] == ORIG_R

    # ---- 1. 硬桿零件：頂點與平面點減去樞紐 ----
    part = bytearray(c[BOOM:BOOM_END])
    n = struct.unpack_from('<H', part, 2)[0]
    for k in range(n):
        x, f, u = struct.unpack_from('<3h', part, 6 + 6*k)
        struct.pack_into('<3h', part, 6 + 6*k, x - PIVOT[0], f - PIVOT[2], u - PIVOT[1])
    p = 6 + 6*n
    while part[p] == 0xF6: p += 7
    nf = 0
    while part[p] == 0xFC:
        fl = struct.unpack_from('<H', part, p + 1)[0]; q = p + 5
        assert fl & 0x60 and fl & 0x200 and fl & 0x400 and not fl & 0x04
        q += 6
        x, u, f = struct.unpack_from('<3b', part, q)
        struct.pack_into('<3b', part, q, x - PIVOT[0], u - PIVOT[1], f - PIVOT[2]); q += 3
        cnt = part[q]; q += 1 + 2*cnt
        p = q; nf += 1
    assert part[p] == 0x1E and p == len(part) - 1 and nf == 24, (hex(p), nf)

    # ---- 2. 區塊配置：PART | SNIP | DATA | CODE ----
    blk = bytearray(HDR) + part
    o_part82 = len(HDR)
    o_snip = len(blk)
    blk += b'\xC4\x00' + struct.pack('<3h', *PIVOT) + struct.pack('<3h', 0, 0, 0) + b'\0\0'   # rel 之後補
    blk += b'\x38\0\0'
    while len(blk) % 4: blk += b'\0'
    D = {}
    def var(name, size, init=b''):
        D[name] = len(blk); blk.extend((init + b'\0' * size)[:size])
    fl = lambda v: struct.pack('<f', v)
    var('SLOTS', 8 * 16)
    for k in ('DT', 'TMP', 'DX', 'DY', 'DZ', 'COS', 'SIN', 'RIGHT', 'BACK', 'DOWN', 'L', 'PITCH', 'YAW',
              'TP', 'TH', 'APPR', 'CONT'): var(k, 4)
    var('K256', 4, fl(1 / 256)); var('KANG', 4, fl(2 * math.pi / 65536)); var('KFA', 4, fl(65536 / (2 * math.pi)))
    var('CFWD', 4, fl(RECEP_FWD - HINGE_FWD)); var('CUP', 4, fl(RECEP_UP - HINGE_UP))
    var('ENTRY', 8); var('MSGTXT', len(MSG), MSG)
    while len(blk) % 16: blk += b'\x90'
    o_code = len(blk)

    def asm(base_off):
        r = lambda name: D[name] - base_off          # [ebx + r] = 變數
        s = lambda off: off - base_off
        src = f"""
            pushfd
            pushad
            call base
        base:
            pop ebx
            mov dword ptr [ebx + {r('TP')}], 0
            mov dword ptr [ebx + {r('TH')}], 0
            mov dword ptr [ebx + {r('APPR')}], 0
            mov dword ptr [ebx + {r('CONT')}], 0
            movzx eax, word ptr [0x580bec]
            test eax, eax
            jz noslot
            mov esi, dword ptr [eax*4 + 0x553848]
            test esi, esi
            jz noslot
            mov ecx, eax
            and ecx, 7
            shl ecx, 4
            lea ebp, [ebx + ecx + {r('SLOTS')}]
            inc eax
            mov edx, dword ptr [0x552928]
            cmp word ptr [ebp], ax
            je haveslot
            mov word ptr [ebp], ax
            mov dword ptr [ebp + 4], edx
            mov dword ptr [ebp + 8], 0
        haveslot:
            mov eax, edx
            sub edx, dword ptr [ebp + 4]
            mov dword ptr [ebp + 4], eax
            cmp edx, 256
            jbe dtok
            xor edx, edx
        dtok:
            mov dword ptr [ebx + {r('DT')}], edx

            movzx eax, word ptr [0x520a1c]
            mov edi, dword ptr [eax*4 + 0x553848]
            test edi, edi
            jz animate
            cmp edi, esi
            je animate
            cmp byte ptr [edi], 4
            jne animate
            test byte ptr [edi + 1], 1
            jz animate
            cmp word ptr [edi + 0xe], 0
            je animate
            mov al, byte ptr [edi + 9]
            xor al, byte ptr [esi + 9]
            test al, 0x80
            jnz animate

            fild dword ptr [edi + 0x11]
            fild dword ptr [esi + 0x11]
            fsubp st(1), st(0)
            fmul dword ptr [ebx + {r('K256')}]
            fstp dword ptr [ebx + {r('DX')}]
            fild dword ptr [edi + 0x15]
            fild dword ptr [esi + 0x15]
            fsubp st(1), st(0)
            fmul dword ptr [ebx + {r('K256')}]
            fstp dword ptr [ebx + {r('DY')}]
            fild dword ptr [edi + 0x19]
            fild dword ptr [esi + 0x19]
            fsubp st(1), st(0)
            fmul dword ptr [ebx + {r('K256')}]
            fstp dword ptr [ebx + {r('DZ')}]
            movzx eax, word ptr [esi + 0x1d]
            mov dword ptr [ebx + {r('TMP')}], eax
            fild dword ptr [ebx + {r('TMP')}]
            fmul dword ptr [ebx + {r('KANG')}]
            fsincos
            fstp dword ptr [ebx + {r('COS')}]
            fstp dword ptr [ebx + {r('SIN')}]
            fld dword ptr [ebx + {r('DX')}]
            fmul dword ptr [ebx + {r('COS')}]
            fld dword ptr [ebx + {r('DZ')}]
            fmul dword ptr [ebx + {r('SIN')}]
            fsubp st(1), st(0)
            fstp dword ptr [ebx + {r('RIGHT')}]
            fld dword ptr [ebx + {r('DX')}]
            fmul dword ptr [ebx + {r('SIN')}]
            fld dword ptr [ebx + {r('DZ')}]
            fmul dword ptr [ebx + {r('COS')}]
            faddp st(1), st(0)
            fadd dword ptr [ebx + {r('CFWD')}]
            fchs
            fstp dword ptr [ebx + {r('BACK')}]
            fld dword ptr [ebx + {r('DY')}]
            fadd dword ptr [ebx + {r('CUP')}]
            fchs
            fstp dword ptr [ebx + {r('DOWN')}]

            fld dword ptr [ebx + {r('DOWN')}]
            fld dword ptr [ebx + {r('BACK')}]
            fpatan
            fmul dword ptr [ebx + {r('KFA')}]
            fistp dword ptr [ebx + {r('PITCH')}]
            fld dword ptr [ebx + {r('RIGHT')}]
            fld dword ptr [ebx + {r('BACK')}]
            fpatan
            fmul dword ptr [ebx + {r('KFA')}]
            fistp dword ptr [ebx + {r('YAW')}]
            fld dword ptr [ebx + {r('RIGHT')}]
            fmul st(0), st(0)
            fld dword ptr [ebx + {r('DOWN')}]
            fmul st(0), st(0)
            faddp st(1), st(0)
            fld dword ptr [ebx + {r('BACK')}]
            fmul st(0), st(0)
            faddp st(1), st(0)
            fsqrt
            fistp dword ptr [ebx + {r('L')}]
            fld dword ptr [ebx + {r('BACK')}]
            fistp dword ptr [ebx + {r('BACK')}]
            fld dword ptr [ebx + {r('DOWN')}]
            fistp dword ptr [ebx + {r('DOWN')}]
            fld dword ptr [ebx + {r('RIGHT')}]
            fistp dword ptr [ebx + {r('RIGHT')}]

            mov eax, dword ptr [ebx + {r('BACK')}]
            cmp eax, 0
            jle animate
            cmp eax, {APP_BACK}
            jg animate
            mov eax, dword ptr [ebx + {r('DOWN')}]
            cmp eax, -60
            jl animate
            cmp eax, {APP_DOWN}
            jg animate
            mov eax, dword ptr [ebx + {r('RIGHT')}]
            cmp eax, {-APP_SIDE}
            jl animate
            cmp eax, {APP_SIDE}
            jg animate
            mov dword ptr [ebx + {r('APPR')}], 1
            mov eax, dword ptr [ebx + {r('PITCH')}]
            cmp eax, {int(10 * DEG)}
            jge p1
            mov eax, {int(10 * DEG)}
        p1:
            cmp eax, {int(45 * DEG)}
            jle p2
            mov eax, {int(45 * DEG)}
        p2:
            mov dword ptr [ebx + {r('TP')}], eax
            mov eax, dword ptr [ebx + {r('YAW')}]
            neg eax
            cmp eax, {int(-20 * DEG)}
            jge y1
            mov eax, {int(-20 * DEG)}
        y1:
            cmp eax, {int(20 * DEG)}
            jle y2
            mov eax, {int(20 * DEG)}
        y2:
            mov dword ptr [ebx + {r('TH')}], eax

            mov eax, dword ptr [ebx + {r('L')}]
            cmp eax, {L_MIN}
            jl animate
            cmp eax, {L_MAX}
            jg animate
            mov eax, dword ptr [ebx + {r('PITCH')}]
            cmp eax, {int(15 * DEG)}
            jl animate
            cmp eax, {int(45 * DEG)}
            jg animate
            mov eax, dword ptr [ebx + {r('YAW')}]
            cmp eax, {int(-15 * DEG)}
            jl animate
            cmp eax, {int(15 * DEG)}
            jg animate
            mov ax, word ptr [edi + 0x1d]
            sub ax, word ptr [esi + 0x1d]
            cwde
            cmp eax, {int(-10 * DEG)}
            jl animate
            cmp eax, {int(10 * DEG)}
            jg animate
            mov eax, dword ptr [edi + 0x34]
            sub eax, dword ptr [esi + 0x34]
            cmp eax, {-30 * 256}
            jl animate
            cmp eax, {30 * 256}
            jg animate
            mov dword ptr [ebx + {r('CONT')}], 1

            mov eax, dword ptr [edi + 5]
            mov ecx, dword ptr [eax + 0x165]
            shl ecx, 8
            mov eax, dword ptr [edi + 0x1fc]
            cmp eax, ecx
            jge animate
            mov edx, dword ptr [ebx + {r('DT')}]
            imul edx, edx, {RATE}
            add eax, edx
            cmp eax, ecx
            jl notfull
            mov dword ptr [edi + 0x1fc], ecx
            mov eax, 0x48d410
            call eax
            lea ecx, [ebx + {r('ENTRY')}]
            lea eax, [ebx + {r('MSGTXT')}]
            mov dword ptr [ecx], eax
            mov dword ptr [ecx + 4], 0
            mov eax, 0x48d420
            call eax
            movzx ecx, word ptr [0x580bec]
            movzx edx, word ptr [0x520a1c]
            mov eax, 0x48e950
            call eax
            jmp animate
        notfull:
            mov dword ptr [edi + 0x1fc], eax

        animate:
            mov edx, dword ptr [ebx + {r('DT')}]
            imul edx, edx, {STEP}
            movsx eax, word ptr [ebp + 8]
            mov ecx, dword ptr [ebx + {r('TP')}]
            call approach
            mov word ptr [ebp + 8], ax
            mov word ptr [ebx + {s(o_snip + 10)}], ax
            movsx eax, word ptr [ebp + 10]
            mov ecx, dword ptr [ebx + {r('TH')}]
            call approach
            mov word ptr [ebp + 10], ax
            mov word ptr [ebx + {s(o_snip + 8)}], ax
            mov eax, {ORIG_R}
            cmp dword ptr [ebx + {r('APPR')}], 0
            je setr
            mov eax, {SMALL_R}
        setr:
            mov dword ptr [ebx + {s(-1)}], eax
            jmp done

        noslot:
            mov word ptr [ebx + {s(o_snip + 8)}], 0
            mov word ptr [ebx + {s(o_snip + 10)}], 0
            mov dword ptr [ebx + {s(-1)}], {ORIG_R}
        done:
            lea eax, [ebx + {s(o_snip)}]
            mov dword ptr [esp + 28], eax
            popad
            popfd
            pop ecx
            push eax
            add ecx, 4
            jmp ecx

        approach:
            mov edi, ecx
            sub edi, eax
            cmp edi, edx
            jle a1
            mov edi, edx
        a1:
            neg edx
            cmp edi, edx
            jge a2
            mov edi, edx
        a2:
            neg edx
            add eax, edi
            ret
        """
        return src

    # 兩次組譯：第一次求 base 位置（code 開頭 + pushfd/pushad/call 之後）
    ks = Ks(KS_ARCH_X86, KS_MODE_32)
    base_off = o_code + 1 + 1 + 5
    F2_REL = None
    for _ in range(3):
        src = asm(base_off)
        # F2 表在原 CODE 0x73E4，區塊插在 tail：相對 base 的位移
        f2disp = F2TBL - (tail + base_off)
        src = src.replace(f'[ebx + {-1 - base_off}]', f'[ebx + {f2disp}]')
        enc, _ = ks.asm(src, 0)
        code_bytes = bytes(enc)
        if code_bytes[:2] == b'\x9c\x60' and code_bytes[2] == 0xE8: break
    blk += code_bytes
    # C4 rel：C4 起點 + 16 之後 + rel = 82
    rel = o_part82 - (o_snip + 16)
    struct.pack_into('<h', blk, o_snip + 14, rel)
    # 38 rel16：38 在 o_snip+16，rel 之後 = o_snip+19；目標 RESUME（原 CODE，在區塊之前）
    struct.pack_into('<h', blk, o_snip + 17, RESUME - (tail + o_snip + 19))

    # ---- 3. 掛勾：0x3714 F0 ----
    #   F0 00 | EB 04 | (0x3718 舊重定位，不執行) | E8 rel32 → x86 | (0x3721 舊重定位) | 68 thunk; C3（保留）
    c[F0_HOOK + 2:F0_HOOK + 4] = b'\xEB\x04'
    call_at = 0x371C
    target = tail + o_code
    c[call_at] = 0xE8; struct.pack_into('<i', c, call_at + 1, target - (call_at + 5))
    assert c[0x3725] == 0x68 and c[0x372A] == 0xC3

    out = insert_blocks(d, pe, secs, code, c, tail, bytes(blk))
    assert len(out) < 65536, len(out)
    open(dst, 'wb').write(out)
    info = dict(tail=tail, o_snip=o_snip, o_code=o_code, o_part82=o_part82, D=D, blk_len=len(blk), size=len(out))
    if preview:
        # 預覽用：F0 改成原本格式「push 回到的位址」讓 sh_paint 跟得到，並把硬桿放下 30°
        d2 = bytearray(out); pe2, o2, s2 = pe_sections(d2); cd = next(s for s in s2 if s['name'] == 'CODE')
        b = cd['ro']; va = lambda off: 0x1000 + off
        d2[b + F0_HOOK + 2] = 0x68; struct.pack_into('<I', d2, b + F0_HOOK + 3, va(tail + o_snip))
        struct.pack_into('<h', d2, b + tail + o_snip + 10, int(30 * DEG))
        open(preview, 'wb').write(d2)
    return info


if __name__ == '__main__':
    a = sys.argv[1:]
    print(build(a[0], a[1], a[2] if len(a) > 2 else None))
