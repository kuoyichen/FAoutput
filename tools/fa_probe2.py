"""
FA.EXE 記憶體探針 v2（不修改 FA.EXE）— 物件列舉、事件偵測、差異比對

模式:
  python fa_probe2.py objects            每秒列出目前所有物件（含名稱、位置、速度）
  python fa_probe2.py log                以 10Hz 記錄所有物件到 objlog.csv，
                                         並在 events.csv 記錄物件出現 / 消失（如飛彈發射、被擊毀）
  python fa_probe2.py diff               找出玩家飛機的「動作」欄位（起落架、彈藥數…）
      先讓飛機保持穩定，按 Enter 建立基準；接著做一個動作（放起落架 / 開一槍），
      再按 Enter，畫面會列出這段期間變動、但平常不太會變的位元組。重複幾次即可。

腳本與 FA.EXE 誰先啟動都可以。

靜態分析得到的結構（image base 0x400000 固定）:
  0x553838  uint16   物件數量上限 (迴圈從 1 到 count-1)
  0x553848  ptr[]    物件指標表
  0x50CE80           玩家飛機物件（與其他物件同一種結構）
  物件結構:
    +0x00 uint8   類別代碼
    +0x01 uint32  旗標 (bit0 = 啟用中)
    +0x05 ptr     類型定義；其中第 3 個 0 結尾字串是類型名稱
    +0x11/15/19 int32  X / Y(高度) / Z  (>>8 = 英尺)
    +0x1D uint16  航向  +0x1F 俯仰  +0x21 滾轉 (65536 = 360 度)
    +0x34 int32   速度 (>>8 = ft/s)   ※ 已在玩家上驗證；其他物件待驗證
"""
import argparse, csv, ctypes, ctypes.wintypes as wt, struct, sys, time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
PROCESS_VM_READ, PROCESS_QUERY_INFORMATION, TH32CS_SNAPPROCESS = 0x10, 0x400, 0x2

PLAYER = 0x50CE80
OBJ_COUNT = 0x553838
OBJ_TABLE = 0x553848
OBJ_READ = 0x40          # 每個物件讀取的位元組數
MAX_OBJS = 2048          # 安全上限

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD),
                ("th32ProcessID", wt.DWORD), ("th32DefaultHeapID", ctypes.c_void_p),
                ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
                ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wt.DWORD), ("szExeFile", ctypes.c_char * 260)]

def find_pid(name=b"fa.exe"):
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    e = PROCESSENTRY32(); e.dwSize = ctypes.sizeof(e)
    ok = k32.Process32First(snap, ctypes.byref(e))
    while ok:
        if e.szExeFile.lower() == name:
            k32.CloseHandle(snap); return e.th32ProcessID
        ok = k32.Process32Next(snap, ctypes.byref(e))
    k32.CloseHandle(snap); return None

def attach():
    pid = find_pid()
    if not pid:
        print("等待 FA.EXE 啟動中…（Ctrl+C 結束）")
        while not pid:
            time.sleep(1); pid = find_pid()
    h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h: sys.exit(f"OpenProcess 失敗 ({ctypes.get_last_error()})，試試以系統管理員執行")
    print(f"已連上 FA.EXE (PID {pid})")
    return h

def read(h, addr, n):
    buf = ctypes.create_string_buffer(n); got = ctypes.c_size_t()
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)):
        return None
    return buf.raw

_name_cache = {}
def type_name(h, tptr):
    if tptr in _name_cache: return _name_cache[tptr]
    raw = read(h, tptr, 256) if tptr else None
    name = "?"
    if raw:
        parts = raw.split(b"\0")
        if len(parts) > 2:
            name = parts[2].decode("latin1", "replace") or "?"
    _name_cache[tptr] = name
    return name

def decode(h, addr, b):
    cls = b[0]
    flags, tptr = struct.unpack_from("<II", b, 1)
    x, y, z = struct.unpack_from("<iii", b, 0x11)
    hdg, pitch, roll = struct.unpack_from("<Hhh", b, 0x1D)
    spd, = struct.unpack_from("<i", b, 0x34)
    return {
        "addr": f"{addr:08X}", "cls": cls, "flags": f"{flags:08X}",
        "name": type_name(h, tptr),
        "x_ft": x >> 8, "alt_ft": y >> 8, "z_ft": z >> 8,
        "hdg_deg": round(hdg / 65536 * 360, 1),
        "pitch_deg": round(pitch / 65536 * 360, 1),
        "roll_deg": round(roll / 65536 * 360, 1),
        "spd_kts": round((spd >> 8) * 3600 / 6076),
    }

def snapshot(h):
    """回傳 {索引: 物件資料}；索引 0 = 玩家。None = 遊戲已結束。"""
    pb = read(h, PLAYER, OBJ_READ)
    if pb is None: return None
    objs = {0: decode(h, PLAYER, pb)}
    cnt_raw = read(h, OBJ_COUNT, 2)
    cnt = min(struct.unpack("<H", cnt_raw)[0], MAX_OBJS) if cnt_raw else 0
    tbl = read(h, OBJ_TABLE, 4 * cnt) if cnt else b""
    for i in range(1, cnt):
        p, = struct.unpack_from("<I", tbl, 4 * i)
        if not p or p == PLAYER: continue
        b = read(h, p, OBJ_READ)
        if not b: continue
        flags, = struct.unpack_from("<I", b, 1)
        if not flags & 1: continue          # 未啟用
        objs[i] = decode(h, p, b)
    return objs

def cmd_objects(h):
    while True:
        s = snapshot(h)
        if s is None: print("FA.EXE 已結束"); return
        print(f"\n=== {time.strftime('%H:%M:%S')}  共 {len(s)} 個物件 ===")
        print(f"{'idx':>4} {'cls':>3} {'name':<14} {'x':>9} {'alt':>7} {'z':>9} {'hdg':>6} {'kts':>5}  flags")
        for i, o in sorted(s.items()):
            print(f"{i:>4} {o['cls']:>3} {o['name'][:14]:<14} {o['x_ft']:>9} {o['alt_ft']:>7} "
                  f"{o['z_ft']:>9} {o['hdg_deg']:>6} {o['spd_kts']:>5}  {o['flags']}")
        time.sleep(1)

def cmd_log(h, hz, out, evout):
    t0 = time.time(); prev = {}
    fields = ["t", "idx"] + list(decode(h, PLAYER, bytes(OBJ_READ)).keys())
    with open(out, "w", newline="") as f, open(evout, "w", newline="") as fe:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        we = csv.writer(fe); we.writerow(["t", "event", "idx", "name", "cls", "x_ft", "alt_ft", "z_ft"])
        while True:
            s = snapshot(h)
            if s is None: print("FA.EXE 已結束"); return
            t = round(time.time() - t0, 2)
            for i, o in s.items():
                w.writerow({"t": t, "idx": i, **o})
            # 物件出現 / 消失（同一索引換了位址或名稱也算重新出現）
            for i, o in s.items():
                q = prev.get(i)
                if q is None or q["addr"] != o["addr"] or q["name"] != o["name"]:
                    if prev:  # 第一輪不算
                        we.writerow([t, "spawn", i, o["name"], o["cls"], o["x_ft"], o["alt_ft"], o["z_ft"]])
                        print(f"[{t:8.2f}] 出現 #{i} {o['name']} (cls {o['cls']})")
            for i, q in prev.items():
                if i not in s:
                    we.writerow([t, "despawn", i, q["name"], q["cls"], q["x_ft"], q["alt_ft"], q["z_ft"]])
                    print(f"[{t:8.2f}] 消失 #{i} {q['name']}")
            f.flush(); fe.flush()
            prev = s
            time.sleep(1 / hz)

def cmd_diff(h, size):
    import msvcrt
    print(f"監看玩家物件 0x{PLAYER:X} 起 0x{size:X} 位元組。")
    print("保持穩定飛行，按 Enter 建立基準（會先觀察 3 秒找出一直在變的欄位）…")
    input()
    noisy = set(); first = read(h, PLAYER, size); t_end = time.time() + 3
    while time.time() < t_end:
        b = read(h, PLAYER, size)
        noisy |= {i for i in range(size) if b[i] != first[i]}
        time.sleep(0.05)
    base_ = read(h, PLAYER, size)
    print(f"已排除 {len(noisy)} 個持續變動的位元組。現在做一個動作，完成後按 Enter（輸入 q 再 Enter 結束）。")
    while True:
        changed = {}
        while not msvcrt.kbhit():
            b = read(h, PLAYER, size)
            if b is None: print("FA.EXE 已結束"); return
            for i in range(size):
                if i not in noisy and b[i] != base_[i]:
                    changed.setdefault(i, set()).add(b[i])
            time.sleep(0.02)
        line = input()
        now = read(h, PLAYER, size)
        if not changed: print("  （沒有偵測到變動）")
        for i in sorted(changed):
            print(f"  +0x{i:03X} (0x{PLAYER + i:X}): {base_[i]:3d} -> {now[i]:3d}   (過程中出現過 {sorted(changed[i])[:8]})")
        if line.strip().lower() == "q": return
        base_ = now
        print("已更新基準。做下一個動作後按 Enter。")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["objects", "log", "diff"])
    ap.add_argument("--hz", type=float, default=10)
    ap.add_argument("--out", default="objlog.csv")
    ap.add_argument("--events", default="events.csv")
    ap.add_argument("--size", type=lambda s: int(s, 0), default=0x400,
                    help="diff 模式監看的範圍（預設 0x400）")
    a = ap.parse_args()
    h = attach()
    try:
        if a.mode == "objects": cmd_objects(h)
        elif a.mode == "log": cmd_log(h, a.hz, a.out, a.events)
        else: cmd_diff(h, a.size)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
