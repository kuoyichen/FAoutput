"""F-14 後燃器火焰貼圖（照實機照片）：噴嘴紅橘→黃，往後轉白、再轉淡藍白，平順的錐形，
淡淡的激波環；尾段用有規則的點陣（Bayer 4×4）慢慢變透明，不留散落的點。
frame(k) 回傳 61 列 × 41 行的色號（0xFF = 透明），第 0 列是尾端，第 60 列是噴嘴。3 格的激波環位置錯開，看起來會往後流。"""
import math

BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
# 沿火焰方向的顏色（t = 0 尾端 … 1 噴嘴）：(t 起點, 中心色, 邊緣色)
RAMP = [(0.95, 186, 183), (0.90, 188, 186), (0.84, 189, 187), (0.77, 190, 189),
        (0.68, 191, 190), (0.42, 47, 191), (0.25, 47, 128), (0.0, 128, 129)]
HOT = {187: 189, 188: 190, 189: 190, 190: 191, 191: 47, 47: 47, 128: 47, 129: 128}   # 激波環：亮一階


def frame(k, W=41, H=61):
    out = [[0xFF] * W for _ in range(H)]
    for r in range(H):
        t = r / (H - 1)
        hw = 18 * (0.28 + 0.72 * t ** 0.7)                      # 錐形半寬（像素）
        hw *= 1 + 0.04 * math.sin(2 * math.pi * (r / 9.0 + k / 3))   # 微微抖動
        alpha = 1.0 if t > 0.5 else 0.1 + 0.9 * (t / 0.5) ** 1.2  # 尾段淡出
        ring = math.cos(2 * math.pi * (r / 9.0 + k / 3)) > 0.55 and 0.15 < t < 0.9   # 激波環（亮帶）
        core, edge = next((c, e) for t0, c, e in RAMP if t >= t0)
        for a in range(W):
            x = abs(a - (W - 1) / 2) / hw
            if x > 1: continue
            a_px = alpha * (1 if x < 0.75 else (1 - x) / 0.25 * 0.9 + 0.1)   # 邊緣也用點陣淡出
            if a_px * 16 <= BAYER[(r + k) & 3][a & 3]: continue
            col = core if x < 0.55 else edge
            if ring and x < 0.7: col = HOT.get(col, col)
            out[r][a] = col
    return out
