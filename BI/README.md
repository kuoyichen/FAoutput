# BI/ — Fighters Anthology AI programs

Copied from `SH\AI` on Kuoyi's PC (2026-11-26).

- `*.AI` — AI program source (plain text script, CRLF): `if do_attack goto attack`, labels, `exit`, etc.
- `*.BI` — the compiled form of the same program (32-bit PE / DOSX module with `.idata` and `.reloc`, maneuver names in English/German/French). This is what FA loads.

| Pair | Used for (from header comments) |
|------|----------------------------------|
| F | generic fighter |
| F117 | fighter program for the F-117; ground attack is a straight high pass instead of pop-up/dive-bomb (header still says f.ai) |
| MOTH | giant moth (the monster in the Fighters Anthology bonus missions) |
| B | bomber |
| AC130 | AC-130 gunship |
| H | helicopter |
| HYDRO | hydrofoil boat |
| LARGE | large non-bomber planes: transport, AWACS |
| LINER | airliner |

`.gitattributes` marks `BI/**` as binary so the CRLF text and compiled files are stored byte-for-byte.

## Compiling

`python3 tools/aic.py BI/F.AI` rebuilds `BI/F.BI`. All 9 sources compile to the shipped .BI files byte-for-byte (only the build timestamp differs). The format and the language are described in `skill/FA_AI_BI.MD`.
