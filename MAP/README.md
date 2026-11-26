# MAP — Fighters Anthology theater maps

Uploaded from Kuoyi's `SH\MAP` folder (structure kept).

Top level: the game's 17 theaters, one set per map code (APA, BAL, CUB, EGY, FRA, GRE, IRA, KURILE, LFA, NSK, PGU, SPA, TVIET, UKR, VLA, WTA):

| ext | what |
|-----|------|
| `.MM` | map/mission placement file for the theater |
| `.T2` | terrain grid (199,829 bytes for the large maps, 126,899 for the smaller EGY/FRA/UKR/VLA) |
| `.PIC` | terrain texture (`KURIL.PIC` belongs to KURILE, `VIET.PIC` to TVIET) |

`my_work/` — Kuoyi's earlier map-editing work: `famap2.cpp` / `FAMAPBMP.cpp` map↔BMP tools, per-map 256×256 BMP exports, 256_COLOR/HEIGHT/TYPE palette/reference BMPs, and edited `.MM`/`.T2` copies. The `.MM` files are identical to the top level; every `.T2` differs (edited terrain).

`MAP original/` — empty on the device (kept with `.gitkeep`).
