# Building FA .LIB files (JKPFA set)

Tool: `tools/falib.py` (Python 3.8+, no packages). Set file: `LIB/JKPFA6.txt` (the JKPFA6 release).
It replaces the FA ToolKit for building: no hand-edited ITEM.DAT, a full build of every LIB takes about
2 minutes the first time and a few seconds after that, every build is checked, and it also writes FA
ToolKit project folders so the ToolKit can still open and edit every LIB (section 6).

**Status (2026-11-26):** JKPFA6 (8 LIBs) built by falib runs in Kuoyi's game with both the original
FA.EXE and FA_BIG: mission builder and missions OK. The next release is **JKP600** (`LIB/JKP600.txt`,
LIBs `JKP600_A.LIB` … `JKP600_S.LIB`): built on Kuoyi's PC in `C:\Users\hawke\Documents\SH\Lib pack\JKP600`
from `Lib pack\OK` (newest files: they win), `Lib pack\JKP54A-E` (the ToolKit projects) and the
installed `_MAP.LIB` / `_MUSIC.LIB`; all sources staged one copy per file in `JKP600\src\<EXT>\`.
Rebuild there with `python ..\falib\falib.py build JKP600.txt --src src --out . --toolkit`.

**Version rule (Kuoyi, 2026-11-26): every new build gets the next number** — JKP600, JKP601, JKP602 …
(LIBs `JKP601_A.LIB` …, ToolKit folders `JKP601_A\` …). Never rebuild a released number with
different content. `python falib.py bump JKP600.txt` writes `JKP601.txt` with every LIB renamed;
then build it into a new folder, e.g. `--out ..\JKP601`. Keep the set file of every released build.
Web page for LIB makers: https://fashion-hawke.vercel.app/tools/lib_release.html

## 1. Rules FA.EXE imposes on a LIB (read this first)

Found by testing 33 LIB sets in the game and by disassembling FA.EXE (original, `Libs\FA.EXE_org`).
falib enforces all of them; `verify` checks LIBs made by anything else.

| # | rule | what goes wrong otherwise | where in FA.EXE |
|---|---|---|---|
| 1 | **Pad the end of every LIB.** The game memory-maps the LIB and its PKWare read callback always copies a full 2048-byte chunk, even past the end of the entry. A compressed entry within ~2 KB of the end of the file is read past the end of the mapping. | crash as soon as that file is loaded: mission builder (objects: `ZU23.NT`, `VIS360.SEE`) or mission start (`SMOKE.PIC`). Looks random: it depends only on the size and position of the last entries, so moving a few files between LIBs makes it come and go. | `0x47a010` read callback, `0x401025` chunk 0x800, `0x435dc0` MapViewOfFile |
| 2 | **Compressed matches: distance 2..4095, length at most 516.** The PKWare format can also express distance 1 and 4096 and length 517-518; the real PKWare encoder never uses them, and neither may we. | some files decode wrong in the game → crash when objects load. falib's own decoder accepts them, which is why the first builds "passed". | PKWare explode at `0x401000` |
| 3 | **LIB names DOS 8.3** (`JKPFA6_A.LIB`, at most 8 characters before `.LIB`). | FA.EXE stores LIB names in 14-byte slots. | `0x54a530` name table |
| 4 | **At most 20 LIB files** in the game folder (factory 4 included) for the original FA.EXE; FA_BIG allows 256. **At most 9,950 files** in all LIBs plus loose files (factory: 7,505); FA_BIG 100,000. | the tables overflow (behaviour not tested; falib warns when a set gets close). | see `FA_BIG/fa_patch_limits.py` |
| 5 | **Same file name in two places: the newest container wins.** For each name the game keeps the copy whose LIB file or loose file has the latest modification time (to the minute; ties: arbitrary). | a freshly built LIB overrides older loose files in the game folder and the factory LIBs; an old LIB copied in later loses to nothing newer. Keep every file in only one mod LIB. | `0x4797e0` qsort compare (name, date, time), dedupe at `0x479232` |

Not rules (tested and ruled out): number of files of one type per LIB, order of LIBs by name,
`$FALIB.INF`, stored (uncompressed) entries, entry order inside the LIB (falib still writes the
ToolKit's order: symbols < digits < letters, case-insensitive).

## 2. The short version

```
python tools/falib.py check LIB/JKPFA6.txt --src . --game "C:\Program Files\Fighters Anthology"
python tools/falib.py build LIB/JKPFA6.txt --src . --out JKPFA6 --toolkit
```

Run from the repo root. `check` says what will change and stops on any problem. `build` writes
`JKPFA6/JKPFA6_A.LIB` ... `JKPFA6/JKPFA6_M.LIB` plus one ToolKit project folder per LIB
(`JKPFA6/JKPFA6A/` ...), then checks the LIBs and must end with `RESULT: PASSED` (section 5).

**Install:** keep the 4 factory LIBs and `_HUD.LIB` in the game folder, remove every older JKPFA LIB
(`FA_JKPFA54_*.LIB`, `FA_JKPFA_B.LIB`, `_MAP.LIB`, `_MUSIC.LIB`), copy in the 8 `JKPFA6_*.LIB`.

On Kuoyi's PC the working copy is `C:\Users\hawke\Documents\SH\Lib pack study\JKPFA6`, built with
`--src` the repo **and** `--src "...\Lib pack study\JKPFA54_extra"` (216 files not uploaded to GitHub:
sound effects, `$` pictures, HUD/PTS/GAS, maps, music; same `<EXT>/` layout).
Without a local clone, use the GitHub copy directly: `--src github:kuoyichen/FAoutput`
(downloads the `main` branch zip; `@branch` picks another branch).

## 3. Where the source files live (one place per file)

Every file `NAME.EXT` is read from `<root>/<EXT>/NAME.EXT`, where `<root>` is each `--src`:

| file | folder |
|---|---|
| F14.PT | PT/ |
| F14.SH | SH/ |
| _F14.PIC, $AIM7.PIC | PIC/ |
| &VULCAN.11K, AIR004.11K | 11K/ |
| ^ACF11.5K | 5K/ |
| APA.MM / APA.T2 | MM/ / T2/ |

The rule is always "folder = extension". `SHX/` and other folders not named after an extension are
never read. Several `--src` roots may be given; if the same file is found in two roots **with different
bytes**, the tool stops and names both paths. It never guesses which copy is newest: delete the old one.

## 4. The set file `LIB/JKPFA6.txt`

```
[rules]
JKPFA6_A.LIB  *.PT *.ECM *.SEE *.HUD *.PTS    # aircraft: flight data, ECM, seekers, HUD
JKPFA6_B.LIB  *.NT *.OT                       # ground units, ships and objects
JKPFA6_C.LIB  *.JT *.GAS                      # weapons and fuel tanks
JKPFA6_D.LIB  *.SH                            # 3D shapes
JKPFA6_E.LIB  *.PIC                           # pictures and textures
JKPFA6_S.LIB  AIR*.11K                        # music (was _MUSIC.LIB)
JKPFA6_F.LIB  *.11K *.5K *.8K                 # sound effects
JKPFA6_M.LIB  *.MM *.T2                       # maps (was _MAP.LIB)

[files]
F14.PT        F-14A Tomcat
F14.SH
...
```

* `[files]`: the full list of files in the mod; order does not matter; a name listed twice is an error.
  Text after the name is the **description** the ToolKit shows (ITEM.DAT column 2); default = the name.
* `[rules]`: which LIB each file goes into. **The first matching line wins** (music above sounds).
  A file that matches no rule is an error. LIB names must be 8.3 (rule 3).
* `#` starts a comment.

| I want to ... | do this |
|---|---|
| add a new file | put it in its extension folder, add its name under `[files]` |
| update a file | replace it in its folder. Nothing else. |
| remove a file from the mod | delete its line under `[files]` |
| add a new LIB | add one `[rules]` line, e.g. `JKPFA6_G.LIB *.FNT` (free letters G-L, N-R, T-Z; 20-LIB limit) |
| move some files to another LIB | add a rule above the general one, e.g. `JKPFA6_G.LIB F14*.PT` |
| next build number | `python tools/falib.py bump LIB/JKP600.txt` → `LIB/JKP601.txt` with LIBs `JKP601_?.LIB` |
| build just one LIB | `build ... --only D` |
| quick test build | `build ... --store` (no compression) |

## 5. Is a LIB correct? (`verify`)

`build` always runs the full check and ends with one line:

```
RESULT: PASSED, 8 LIBs, 1511 entries: structure OK, every entry unpacks, checksums OK, contents match the sources
```

Anything else is `RESULT: FAILED` with one `FAIL` line per problem (exit code 1). Do not ship a LIB
without `PASSED`. Check LIBs at any time, e.g. after copying or downloading them:

```
python tools/falib.py verify JKPFA6                                  # every .LIB in a folder
python tools/falib.py verify "C:\Program Files\Fighters Anthology"   # what is installed now
python tools/falib.py verify JKPFA6 --set LIB/JKPFA6.txt --src .     # also compare with the sources
```

| # | check | catches |
|---|---|---|
| 1 | header and index: `EALIB`, count, offsets in order, end entry, only zero padding after it, 8.3 upper-case names, no name twice, flag 0 or 4 | truncated or damaged file, broken index |
| 2 | **game read overrun** (rule 1): no compressed entry is read past the end of the file | the "random" crash |
| 3 | every entry unpacks in full, size matches, no stray bytes, **only PKWare-legal matches** (rule 2) | damaged data; streams FA.EXE cannot read |
| 4 | `$FALIB.INF` checksum list: same names, sizes and SHA-1 as at build time | any change to any entry, even one bit, without the sources |
| 5 | with `--set`: exactly the files the `[rules]` give this LIB, byte-identical to the sources | missing, extra or out-of-date files |
| 6 | no file in two mod LIBs (factory LIBs excepted) | rule 5 surprises |

`$FALIB.INF` is a small stored text entry at the start of every falib LIB (`NAME SIZE SHA1` per file,
no date, so builds stay byte-identical). The game ignores it, like the ToolKit's `$TOOLKIT.INF`.
LIBs not built by falib have no list (`NOTE no checksum list`).

Findings on Kuoyi's PC (2026-11-26): the ToolKit-built `FA_JKPFA54_C.LIB` has a rule-1 overrun on
`_TWNBKC.PIC` (1,337 bytes past the end: may crash any mission that uses that town texture);
`_HUD.LIB` holds `~F14S.PIC` twice. The factory FA_1 (`~~QUES.PIC`) and FA_2 (`VALK01.XMI`) have
overruns too; those files seem never to be loaded. Factory LIBs are never changed.

## 6. FA ToolKit compatibility (`build --toolkit`, `import`)

With `--toolkit`, every LIB also gets an FA ToolKit 1.0 project folder in `--out`:
the folder has the LIB's name without `.LIB` (`JKP600_A.LIB` -> `JKP600_A\`). It holds every source file of that LIB
(flat), `ITEM.DAT` (`"NAME","description","D","NAME","","1.0"` per file), `PROJECT.DAT` (project name
twice), `README.TXT`, and `FA_0.LIB` (= the built LIB). These match the ToolKit's own files: generated
from the JKP54 projects' lists, PROJECT.DAT is byte-identical, ITEM.DAT differs only in column 5 that the
ToolKit fills for a few aircraft, README.TXT only in line order.

Note: a LIB built by the **ToolKit** has no rule-1 padding. Run `verify` on it before release; if it
reports an overrun, build the release with falib instead (`import` the ToolKit changes first).

The ToolKit folders are **output**; the repo (plus the extra folder) is the source. If a file was
changed or added inside a ToolKit folder, the next `build --toolkit` stops and lists it. Bring it back:

```
python tools/falib.py import JKPFA6\JKPFA6C --set LIB/JKPFA6.txt --to . --src "...\JKPFA54_extra" --dry-run
python tools/falib.py import JKPFA6\JKPFA6C --set LIB/JKPFA6.txt --to . --src "...\JKPFA54_extra"
```

`import` compares three copies of every file (ToolKit, source, and the released copy recorded in the
LIB's `$FALIB.INF`), so it never guesses:

| line | meaning | what happens |
|---|---|---|
| `IMPORT` | changed in the ToolKit only | ToolKit file copied into the source |
| `KEEP` | changed in the source only | nothing (source is newer) |
| `CONFLICT` | changed on both sides | **nothing is written**; rerun with `--take-toolkit NAME` / `--take-source NAME` |
| `NEW` | in ITEM.DAT, not in the set file | file copied to `<EXT>/`, line + description added; says which LIB the rules pick |
| `DESC` | description changed | set file line updated |
| `GONE?` | no longer in ITEM.DAT | kept; `--remove-missing` deletes the set-file line |

`--overwrite-toolkit` (on build) throws ToolKit changes away instead.

## 7. Other commands

```
python tools/falib.py list   JKPFA6_D.LIB                  # entries, flags, sizes
python tools/falib.py unpack JKPFA6_D.LIB out --by-ext     # extract into PT/ SH/ ... folders
python tools/falib.py verify JKPFA6_D.LIB --against folder # compare with a folder of sources
```

`unpack --by-ext` brings files from any LIB (old release, downloaded mod, factory) into the repo layout.
Never write to the factory LIBs (FA_1, FA_2, FA_4B, FA_4D).

## 8. File format

```
"EALIB"  uint16 count
count+1 entries of 18 bytes: name[13] (zero padded), flag[1], offset[4]
          last entry: empty name, offset = end of data
entry data, then (falib) 4096 zero bytes
```

* flag 0 = stored. flag 4 = `uint32 unpacked size` + PKWare DCL implode stream (`00 06`: binary
  literals, 4 KB window). (FA.EXE also accepts flag 1, another compression method; no LIB here uses it.)
* The PKWare window starts zero-filled; EA's and the ToolKit's encoders sometimes copy from it
  (SCDN_B.SH, AIR109.11K). The decoder handles this.
* FA.EXE builds one sorted index of every LIB entry and every loose file in the game folder
  (35 bytes each: flag, folder, name, DOS time, DOS date, LIB, offset, size), keeps the newest copy of
  each name (rule 5) and finds files by binary search. Entries are read straight from the mapped LIB.
* Factory and ToolKit LIBs use the same compressor (identical bytes for the same file). EA stored some
  files uncompressed; falib does too when compression leaves 90% or more (`STORE_RATIO`: all music,
  a few sounds).
* **Encoder:** greedy LZ77 + one-step lazy matching, 48-step hash chains, distance 2..4095, length
  2..516 (rule 2; `ENCODER_VERSION` v4). All JKP54 contents together compress to about the ToolKit's
  size (100-102% per LIB). Changing `implode()` must bump `ENCODER_VERSION` so old cache entries are not reused.

## 9. How it was found and checked (2026-11-26)

* All 21 LIBs in `Lib pack study` unpack; the JKPFA54 ToolKit LIBs unpack byte-identical to their
  ToolKit project folders. Same input always gives the same LIB bytes.
* In-game bisect with Kuoyi (FA_BIG): the ToolKit originals recompressed by falib crashed until the
  encoder stopped using distance 1 / 4096 (rule 2); JKPFA6 still crashed; the crashing sets were narrowed
  file by file, then FA.EXE was disassembled (capstone) and rule 1 explained all 33 results: every
  crashing set had an overrun entry of a kind loaded at that moment.
* Final JKPFA6 (padded, 8 LIBs) passed in the game on the original FA.EXE and on FA_BIG.

## 10. Speed

Compressed entries are cached by content in `%LOCALAPPDATA%\falib\pk-v4`, so only new or changed files
are compressed, on all CPU cores. On Kuoyi's PC (8 threads): all 8 JKPFA6 LIBs from cold about 2 minutes,
again a few seconds, plus ~10-15 s for the verify after every build. Deleting the cache is always safe.
The ToolKit took about 10 minutes for JKP54D alone.
