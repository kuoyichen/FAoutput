# F-14 wreck builders (F14_A / F14_C, 2026-11-28)

Built from the current `SH/F14.SH` + `PIC/_F14.PIC` and the old wrecks' textures.
`f14wa2.py` (F14_A, torn left wing), `f14wc.py` (F14_C, right aft section blown open),
then `fixreloc.py <base> <out> <region>` (required — see skill/SH_edit_note.MD §20).
`wreckfix.py` (fixed wings, no stores) was tried in v3 and rejected; the shipped files are v2 (no wreckfix).
Helpers: `wreckpic.py` (PIC load/save/append rows), `clip.py`. The scripts import the scratch tools
`faces.py`, `lods.py`, `trender.py` from the session scratchpad (same as the F14W/F14B scripts).
