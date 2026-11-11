"""
FA.EXE 飛行狀態記憶體探針（驗證用，不修改 FA.EXE）

用法（Windows，需與 FA.EXE 同一台機器；Python 3，32/64 位元皆可）:
    python fa_mem_probe.py            # 每 0.1 秒印出一行，並寫入 flightlog.csv
                                      # 腳本與 FA.EXE 誰先啟動都可以；若遊戲還沒開，腳本會等待
    python fa_mem_probe.py --hz 20 --out mylog.csv

在任務中對照遊戲內 HUD / 資訊框的高度、航向、速度，確認位址正確。
若數值不對或不動，代表這個全域區塊不是「玩家飛機」，回報給 Claude 繼續找。

位址來源（靜態分析 FA.EXE，image base 0x400000 固定、無 ASLR）:
  函式 0x43D290 會用 "Speed: %d KTS" / "Heading: %d DEG" / "Altitude: %d FT"
  格式化以下全域變數:
    0x50CE91  int32  X 位置 (24.8 定點, >>8 = 英尺)      [候選]
    0x50CE95  int32  高度 Y (>>8 = 英尺)                  [HUD 直接使用]
    0x50CE99  int32  Z 位置 (24.8 定點)                    [候選]
    0x50CE9D  uint16 航向 (65536 = 360 度, /182)           [HUD 直接使用]
    0x50CE9F  int16  俯仰 (推測)
    0x50CEA1  int16  滾轉 (推測)
    0x50CEB4  int32  速度 (>>8 = ft/s, *3600/6076 = 節)   [HUD 直接使用]
"""
import argparse, csv, ctypes, ctypes.wintypes as wt, struct, sys, time

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
TH32CS_SNAPPROCESS = 0x2

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

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

BLOCK_START, BLOCK_LEN = 0x50CE80, 0x40

def read(h, addr, n):
    buf = ctypes.create_string_buffer(n); got = ctypes.c_size_t()
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)):
        raise OSError(ctypes.get_last_error())
    return buf.raw

def decode(b):
    o = lambda a: a - BLOCK_START
    x, y, z = struct.unpack_from("<iii", b, o(0x50CE91))
    hdg, = struct.unpack_from("<H", b, o(0x50CE9D))
    pitch, roll = struct.unpack_from("<hh", b, o(0x50CE9F))
    spd, = struct.unpack_from("<i", b, o(0x50CEB4))
    return {
        "x_ft": x >> 8, "alt_ft": y >> 8, "z_ft": z >> 8,
        "hdg_deg": round(hdg / 65536 * 360, 1),
        "pitch_deg": round(pitch / 65536 * 360, 1),
        "roll_deg": round(roll / 65536 * 360, 1),
        "spd_kts": round((spd >> 8) * 3600 / 6076),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hz", type=float, default=10)
    ap.add_argument("--out", default="flightlog.csv")
    a = ap.parse_args()
    pid = find_pid()
    if not pid:
        print("等待 FA.EXE 啟動中…（先開腳本或先開遊戲都可以，Ctrl+C 結束）")
        while not pid:
            time.sleep(1); pid = find_pid()
        print(f"偵測到 FA.EXE (PID {pid})")
    h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h: sys.exit(f"OpenProcess 失敗 ({ctypes.get_last_error()})，試試以系統管理員執行")
    t0 = time.time()
    with open(a.out, "w", newline="") as f:
        w = None
        while True:
            try: b = read(h, BLOCK_START, BLOCK_LEN)
            except OSError: print("FA.EXE 已結束"); break
            row = {"t": round(time.time() - t0, 2), **decode(b), "raw": b.hex()}
            if w is None:
                w = csv.DictWriter(f, fieldnames=list(row)); w.writeheader()
            w.writerow(row); f.flush()
            print({k: v for k, v in row.items() if k != "raw"})
            time.sleep(1 / a.hz)

if __name__ == "__main__":
    main()
