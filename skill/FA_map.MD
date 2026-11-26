# FA theater maps: .T2 / .MM / .PIC

Notes from reading the original files in `MAP/` and Kuoyi's tools `MAP/my_work/famap2.cpp` and
`FAMAPBMP.cpp` (2026-11-26). **Verified** = checked against all 16 original maps.
**Guess** = not yet confirmed in game.

A theater is three files (Kuoyi):

| file | role | format |
|------|------|--------|
| `XXX.T2` | terrain the game flies over (height + ground type per cell) | binary, `BIT2` |
| `XXX.MM` | map objects (airfields, cities, SAMs, bridges…), terrain tile map, map labels | text (`textFormat`) |
| `XXX.PIC` | the picture shown in the mission editor | normal PIC, format 0 |

In the game they are packed in the map LIB (`JKPFA6_M.LIB`: `*.MM *.T2`; PICs go in a PIC LIB),
see `FA_LIB_build.MD`.

Maps: APA Panama, BAL The Baltics, CUB Cuba, EGY Egypt, FRA France, GRE Greece, IRA Iraq,
KURILE Kuril Islands, LFA Falkland Islands, NSK North/South Korea, PGU Persian Gulf, SPA Pakistan,
TVIET North Vietnam, UKR Ukraine, VLA Vladivostok, WTA Taiwan (names from the T2 header).

## 1. Coordinates (verified)

- World unit = **foot** (same as FA.EXE positions >> 8). MM `pos X ALT Z`.
- One T2 cell = **8192 ft** (about 1.35 nm, 2.5 km). Big maps: 256 × 256 cells = 2,097,152 ft square.
- Cell of an object: `col = X / 8192`, `row = Z / 8192`. Row 0 is the **south** edge
  (row index grows north), column 0 the west edge. Checked: every object of all 16 MM files lands on
  a non-sea cell with this rule (TVIET 494/544, the rest are docks/bridges/ships on water cells).
- In every original MM, object altitude is 0 and the cell under it has height 0 (BAL 171/172,
  TVIET 565/565). The game puts objects on the ground; Kuoyi's famap2 also flattens a 10-cell
  square under each object.

## 2. `.T2` terrain (verified)

```
0x00  4   "BIT2"
0x04  80  map name, zero padded ("The Baltics")
0x54  14  PIC name ("bal.PIC")           (KURILE -> kuril.PIC, TVIET -> viet.PIC)
0x62  i32 extent X in ft (2097152 big, 1638400 small)
0x66  i32 0
0x6A  i32 extent Z in ft
0x6E  i32 0, 0x72 i32 0
0x79  u32 block size = 8 (cells)
0x7D  u32 blocks across  (32 / 26 / 25)
0x81  u32 blocks down    (32 / 25 / 25)
0x85  u32 file offset of block table (= 149 + w*h*3)
0x89  u32 width  in cells (256 / 208 / 200)
0x8D  u32 height in cells (256 / 200 / 200)
0x91  u32 offset of cell grid = 149 (0x95)
0x95  cell grid: w*h records of 3 bytes, row by row from the south-west corner
      [colour][type][height]
then  block table: (w/8 rounded up) * (h/8) records of 3 bytes [colour][type][0]
```

Sizes: big maps 256×256 (199,829 B), EGY/FRA/UKR/VLA **208 × 200** (126,899 B; famap2 assumed
208×208, which is wrong; the extent is 200 cells, so the last 8 columns lie past the edge),
TVIET 200×200 (122,024 B). Kuoyi's tools only build the 256 maps.

Cell bytes:
- **height**: 0…31 in every original map (5-bit range). 0 = sea level. Unit in ft is **not known
  yet** (guess: a few hundred ft per step; Taiwan's 31 ≈ 13,000 ft would be ~420 ft/step). Kuoyi's
  my_work T2s use up to 55–64 and only changed this byte.
- **type** (ground cover; Kuoyi's list from the editor): 00 nothing, 01 sea, 02 forest,
  03 forest #1, 04 forest #2, 05 farm, 06 moose, 07 paddy #1, 08/09 paddy #2, 0A–0C palms #1–3,
  0D–0F trees #1–3, 10 water buffalo. Type 1 covers the sea plus a coastal band. Each map uses its
  own subset (BAL 0–4, WTA 0,1,6–9,12–14, TVIET up to 16).
- **colour**: 255 = sea, otherwise a land value: 210 on all big maps; 208–218 on the small maps
  (194–199 on TVIET). Not the PIC colour. Guess: ground shade / palette band used when drawing.

Block table (one record per 8×8 cells): colour = colour of the block's first (south-west) cell
(100% of blocks), type = most common type in the block (≥99%), third byte always 0. Probably a
coarse LOD for far terrain. **When writing a new T2, rebuild this table from the grid.**

## 3. `.MM` map file (text)

```
textFormat
map bal.T2
layer day2b.LAY 0        sky/lighting layer
clouds 0
wind 65 7
view 4149 1258291 1229887   mission editor start view
sides3 / sides4 …        list of $xx side flags per nation
historicalera …          (some maps)
time 12 0
obj  … .                  map objects: type XXX.OT/.NT, pos X ALT Z, angle, nationality2/3,
                          flags $4003, speed, name, alias, (skill/react/searchDist for units)
special … .               map labels in the editor: pos, name, color, icon, flags
tmap X Y TILE ROT         terrain tile placement (see below)
tmap_named NAME X Y       (KURILE only: k000004 0 4 …, 208 entries)
tdic 256 + 8 lines of 4   tile dictionary, one per tile id
```

- `tmap`: X and Y are cell coordinates in steps of 4 (0…252), so one tile = 4×4 cells, 64×64
  tiles per big map. TILE = 1…65 (BAL), ROT = 0…3 (90° steps). Number of `tdic` blocks = tile count
  (BAL 66). FA.EXE has editor debug strings "Tmap: %d (rot: %d)" and "Leaf coords". **Guess:** the
  ground texture/detail pattern per 4×4 cells, and `tdic` 8×4 = two 4×4 masks per tile.
  Not decoded yet.
- Map objects in the MM are the fixed scenery for every mission on that map; mission `.M` files
  add their own objects on top.

## 4. `.PIC` editor map (verified)

PIC format 0, 800×800 (big maps) or 600×600 (EGY/FRA/UKR/VLA), pixels at 0x40, row table, then a
**384-byte embedded palette** (128 colours, 6-bit) that replaces the low half of the game palette.
Displayed as stored, north up. The PIC spans the T2 extent (2,097,152 ft → 800 px ≈ 2621 ft/px).
Kuoyi's `my_work/XXX.bmp` are these maps cut to 256×256 8-bit BMPs, one pixel per T2 cell, used by
famap2 to find rivers / roads / cities by palette index (index lists differ per map, see famap2.cpp
`make()`).

## 5. Kuoyi's tools (my_work, 2010–2016)

- `FAMAPBMP.cpp` → `famap2.cpp` (newer, superset). Commands:
  - `famap2 e BAL.T2`: extract into `tmp_BAL.T2\TER_BAL.T2_COLOR_.BMP`, `_TYPE_.BMP`,
    `_HEIGHT_.BMP` (256×256 8-bit, header copied from `256_*.bmp` templates) and a `x,y,h` TXT.
  - `famap2 b BAL.T2`: write the three BMPs back into the T2 (bytes 149/150/151 + 3i).
  - `famap2 m BAL.T2 [maxh]`: random terrain: every height = rand(1…maxh) (default 60),
    100 random 4×4 flat spots, then height 0 on rivers / roads / cities read from `BAL.bmp`
    (plus a 3–4 cell flat border), on sea (colour 255, 8-cell border) and under every MM object
    (10×10 cells).
- Limits found: only 256×256 maps; the block table is not updated; heights are pure noise
  (no smoothing, the 2016 smoothing try is commented out); heights above 31 are written.
  BMP rows are bottom-up so BMP row 0 = T2 row 0 = south, which is why it lines up.

## 6. Open questions

1. Height unit (ft per step) and whether values > 31 are valid. Test: make one cell area a known
   height, fly/crash over it with FAlogger and read the altitude (no EXE patch needed).
2. Meaning of the colour byte (shade band?) and of `tmap` / `tdic` (ground texture tiles?).
3. Whether FA.EXE reads the block table or recomputes it.
