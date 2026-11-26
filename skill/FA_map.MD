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

- World unit = **foot** (FA.EXE positions are 24.8 fixed ft). MM `pos X ALT Z`.
- The original maps are not true scale: WTA's Taiwan is ~195 cells (~490 km) long, real ~394 km.
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
0x54  13  PIC name ("bal.PIC", 8.3 + NUL)  (KURILE -> kuril.PIC, TVIET -> viet.PIC)
0x61  3×i32 max corner X, Y, Z in 24.8 fixed ft (536870912 = 2,097,152 ft; small maps 1,638,400 ft)
0x6D  3×i32 min corner X, Y, Z (all 0)
0x75  i32 0
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
- **height**: **256 ft per step** (from FA.EXE, section 6). 0…31 in every original map, so the
  highest original ground is 7,936 ft. 0 = sea level. Kuoyi's my_work T2s use up to 55–64 and only
  changed this byte.
- **type** (ground cover; Kuoyi's list from the editor): 00 nothing, 01 sea, 02 forest,
  03 forest #1, 04 forest #2, 05 farm, 06 moose, 07 paddy #1, 08/09 paddy #2, 0A–0C palms #1–3,
  0D–0F trees #1–3, 10 water buffalo. Type 1 covers the sea plus a coastal band. Each map uses its
  own subset (BAL 0–4, WTA 0,1,6–9,12–14, TVIET up to 16).
- **colour**: 255 = sea, otherwise a land value: 210 on all big maps; 208–218 on the small maps
  (194–199 on TVIET). Not the PIC colour. The renderer reads it together with the type byte;
  probably the flat ground colour where no texture tile covers the cell.

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
  (BAL 66). These are textured ground tiles (section 6); `tdic` = two 4×4 masks per tile, meaning
  not decoded yet.
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

## 6. How FA.EXE uses the T2 (read only, no patch; 2026-11-26)

- Load: `0x4c5e7b` loads `<map>.T2` whole into memory, pointer in global `0x57cd28`; the offsets at
  +0x85 (block table) and +0x91 (grid) are turned into pointers.
- Cell lookup `0x4c6040(ecx=col, edx=row, push step)`: if step < block size (+0x79) it checks
  0 ≤ col < width (+0x89), 0 ≤ row < height (+0x8D) and returns `grid + (row*width+col)*3`;
  otherwise it uses the block table (+0x7D/+0x81/+0x85). Outside the map it returns a fixed default
  record at `0x50ce4c`. **So width/height come from the header, not hard-coded.**
- Cell size is hard-coded: `pos >> 21` on 24.8 positions (= 8192 ft). The flyable area check
  (`0x42bdc0`) is `0 ≤ pos < width << 21`; the editor centres on `(width << 21) / 2` (`0x4283d6`).
- Height: the ground-collision code (`0x42bfc0`) builds a cell quad with corners `col*32`, `row*32`
  and the raw height byte in the same 16-bit space, and compares with `y >> 16`. One cell = 32 units
  = 8192 ft, so **1 height step = 256 ft**. The byte is read as 0…255 (max 65,280 ft); the originals
  stop at 31 (7,936 ft).
- Render (`0x4a9d00`): terrain patches from the same lookup (colour+type word and height),
  up to 499 patches per frame; far patches use the block table.
- `0x4a8355` reads the type byte under an object position (ground cover check).
- MM parser (`0x482f27…`): `tmap` → table at `0x5733e0` (8 bytes: x, y, tile, rot as u16), **max 3500
  (0xDAC)**; BAL already uses 3356. `tdic` → up to **300**, each = one dword (256) + two 16-byte
  4×4 masks. `tmap_named NAME x y` loads `NAME.PIC` as a ground texture tile (KURILE's k000004.PIC …).
  Editor help strings: "Rotate tmap / Dec/inc tmap index / Pick tmap under cursor / Add tmap".
  So **tmap = textured ground tiles**, one per 4×4 cells (32,768 ft square).

### Limits that matter for bigger maps

- Positions are signed 24.8 ft. `width << 21` must stay below 2^31, so **width/height ≤ 1023 cells**
  (8,380,416 ft). 512×512 (2× each side, 4× area) and 724×724 (8× area) fit; 1024×1024 (4× each
  side) overflows by one cell. Ground quad corners `col*32` are int16: also fine up to 1023.
- 3500 tmap tiles per map cover 3500 of the 4096 tile slots of a 256 map; a 512 map has 16,384
  slots, so most of a bigger map would have no ground texture (plain colour) unless textures are
  spent only where it matters.
- Untested: object count limits in MM, mission editor PIC size / scroll, AI and radar code that may
  assume 256 cells, and whether heights above 31 render correctly (Kuoyi's my_work used up to 64).


## 7. Open questions

1. Do heights above 31 show correctly in game? (Kuoyi's my_work T2s with up to 64.)
2. Does a 512×512 T2 load and fly? Mission editor and AI behaviour on it.
3. Where the numbered tmap tile textures come from (layer / PIC naming) and what `tdic` masks do.
4. Meaning of the colour byte (renderer reads it with the type byte; probably flat ground colour).

## 8. Research: Kuoyi's three goals (2026-11-26, nothing built yet)

**A. Bigger maps (4×, 8×).** The T2 loader and cell lookup read width/height from the header, so a
bigger grid is possible without patching FA.EXE. Hard ceiling: 1023 cells per side (24.8 position
overflow). Feasible: 512×512 (4× area, 4,194,304 ft ≈ 1,280 km square) and up to ~724×724 (8× area).
Not feasible: 1024×1024 (4× per side). Costs/risks: only 3500 texture tiles, so ground textures cover
at most ~21% of a 512 map; T2 grows to ~790 KB (512²×3); MM object limits, editor PIC and AI/radar
behaviour must be tested. First step: a 512×512 test T2 (original map in one quarter, flat sea
around) and fly to the far corner.

**B. Real heights.** 1 step = 256 ft, byte up to 255, so real terrain (Taiwan 13,000 ft = 51 steps,
Himalaya edge on SPA ~ 100+) fits if values > 31 render well. Data: AWS Terrain Tiles
(`s3.amazonaws.com/elevation-tiles-prod/terrarium/z/x/y.png`, SRTM/GEBCO based) is reachable from the
cloud session; at zoom 7–8 it is finer than a 2.5 km cell. Steps: (1) georeference each map by
fitting its sea mask (type 1 / colour 255) to a real coastline (Natural Earth 10m from GitHub raw is
reachable); the originals are not true scale, so either keep their stretch or remake the map at true
scale; (2) sample the DEM per cell (max or mean over the 8192 ft square), round to 256 ft; (3) keep
height 0 and flatten a few cells around every MM object (airfields, cities), as famap2 did;
(4) rebuild the block table.

**C. Real cities, roads, rivers, bridges.** In 3D these exist only as (a) MM objects (CITY1–4,
CTYBK*, TWNBK*, ROAD/ROAD2/ROAD4/ROADC, BR1–3 END/MID, BRDEND/BRDMID… placed by `pos` and `angle`)
and (b) tmap ground texture tiles (rivers/roads painted in the texture). Sources: Natural Earth 10m
populated places, roads, rivers (GitHub raw, reachable), OpenStreetMap for detail (Overpass is blocked
from the cloud session; would need Kuoyi's PC). Plan: chain road/bridge segment objects along real
lines (bridge where a road crosses a river), city blocks on real city footprints, keep within object
limits; optionally paint new tmap_named texture PICs from real land cover. The editor PIC can be
redrawn from the same data.

## 9. Relief that reads as 3D: what was built (2026-11-26)

Real heights alone look flat in FA: one cell is 8192 ft (~2.5 km), so real mountain slopes come out at
about 8° and FA's terrain renderer shows no depth. Kuoyi wants the feeling of flying in a valley and
looking up at the mountains; the land / plain / sea layout only needs to be roughly right.

**Method (WTA-2, chosen by Kuoyi; later used for every map).**
1. Georeference: fit the T2 sea mask (colour 255) to Natural Earth 10m land with a grid search, then
   Nelder-Mead over lon0, lat0, sx, sy, rot. Score = balanced accuracy (land hit rate + sea hit rate) / 2,
   so mostly-sea maps (KURILE, LFA) are not won by "all sea". Many theaters are stylised: UKR is
   ~5.8 km/cell and needed a start point by hand (Crimea ↔ Crimea); KURILE likewise (chain end points).
   GRE islands are drawn freely, so the fit is only rough (86%).
2. DEM: AWS terrarium tiles (zoom 7–9 chosen so a cell has ≥ 4 DEM pixels); per vertex
   0.5 × mean + 0.5 × max of a 7 × 7 sample in the cell. Game land that is sea in the real data borrows
   the nearest real land within 5 cells, otherwise a low dome.
3. Heights in steps (256 ft):
   `env = clip((gauss(e,1.5) − 150) / (ref − 150), 0, 1)`, `ref = clip(0.75 × max gauss(e,1.5), 1200 m, 2900 m)`,
   `H = clip(e/1000,0,1)×3 + env^1.3 × P × 0.66 + k × (e − gauss(e,2.5))/78 × env + hills`,
   mountain maps P = 70, k = 7, hills = 2 steps of smooth noise × (1 − env);
   flat maps (EGY, UKR, BAL) P = 14, k = 2.5, hills 4 steps. Soft cap above 110 steps (× 0.5),
   so peaks stay near WTA-2 (max ≈ 140 = 36k ft). Sea = 0.
4. Lakes: build the ground-texture mosaic (see below), water = tile index 240–254, binary opening 5×5
   (drops thin rivers), lake cell = > 4% water and ≥ 3 cells from the sea; each lake gets its
   median height, the ring around it is averaged halfway.
5. Objects: every MM object has ALT 0, so cells cx−1..cx+2, cy−1..cy+2 around each `pos` are 0 ft;
   after WTA-5 a ramp (≤ 6 steps per cell) keeps them valleys, not pits.
Only the height byte changes. Result: SH\MAP\NEW_T2\ on Kuoyi's PC (16 T2 + contour PNGs); scripts and
fits in the project files (`maps/ALL_T2/scripts`).

**Ground texture tiles.** A numbered `tmap X Y N ROT` loads `<first 3 letters of the map>N.PIC`
(TVIET → TVI0.PIC …), from C:\work\FA_1 on Kuoyi's PC (not in the repo). APA, GRE, LFA, NSK and WTA
use the same 68 tiles. KURILE uses `tmap_named` K*.PIC, 128×128 or 256×256. Tile pixels: 192–207 land
shades, 217–224 shore, 240–254 rivers/lakes, 255 transparent (sea). A tile covers cells x..x+3,
y..y+3 as `rot90(flipud(tile), ROT)` with row 0 = south (fits the coasts best).

**Map Editor** (`tools/map_editor.html`): opens a T2 from MAP/ or your disk, with the MM, editor PIC and
texture tiles (pick the tiles folder) as overlays; raise / lower / smooth / flatten / set / restore /
pick brushes, protect sea and objects, contours, a 3D preview of the area under the cursor, height
PNG export / import; Save writes the original file back with only the height bytes changed.
