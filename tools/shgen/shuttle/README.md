# Space Shuttle generator (Release #12)

`python3 shuttle.py OUTDIR` writes `SHUTTLE.SH`, `_SHUTTLE.PIC` and a preview PNG into OUTDIR.
The result is byte-identical to `SH/SHUTTLE.SH` and `PIC/_SHUTTLE.PIC` (build SHUT-23, md5 68264790 / e4d27801).

- Donor container: `SH/F86.SH` (PE wrapper, header ops, import thunks).
- Needs numpy, keystone-engine, capstone, Pillow, and the modules in `tools/shgen` and `tools/shgen/glb2sh` (bsp, shasm, sh_subdivide, f18g_growler, ab_flame_tex).
- `core.py`, `geo.py`, `mesh.py`, `hdr.py`, `sh_inspect.py` are the procedural-shape helpers this script was developed with.
- `ALL_ALWAYS=1` builds a debug shape that draws the tank and boosters whatever the loadout.
- PT: `PT/SHUTTLE.PT` (hardpoint 4 = external tank F500.GAS, hardpoint 5 = 2 SRB stores; PLANE[65] parked pitch -3; F-14 low-speed envelope).

Lessons: skill/SH_edit_note.MD section 19 (op 78 visibility box), skill/FA_flight_model.MD section 5.10 (parked pitch).
