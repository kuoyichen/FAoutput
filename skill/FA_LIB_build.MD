# Building FA .LIB files (JKPFA set)

Tool: `tools/falib.py` (Python 3.8+, no packages). Set file: `LIB/JKPFA54.txt`.
It replaces the FA ToolKit for building: no ITEM.DAT, no project folders, and a full
build of every JKPFA54 LIB takes about 1 minute the first time and 1-2 seconds after that.

## 1. The short version

```
python tools/falib.py check LIB/JKPFA54.txt --src . --game "C:\Program Files\Fighters Anthology"
python tools/falib.py build LIB/JKPFA54.txt --src . --out build
```

Run from the repo root. `check` says what will change and stops on any problem;
`build` writes `build/FA_JKPFA54_A.LIB` ... `build/FA_JKPFA54_M.LIB`, then checks them and must end
with `RESULT: PASSED` (section 4). Copy them into the game folder (after removing the old JKPFA LIBs,
see section 6).

Without a local clone, use the GitHub copy directly: `--src github:kuoyichen/FAoutput`
(downloads the `main` branch zip; `@branch` picks another branch).

## 2. Where the source files live (one place per file)

Every file `NAME.EXT` is read from `<root>/<EXT>/NAME.EXT`, where `<root>` is each `--src`:

| file | folder |
|---|---|
| F14.PT | PT/ |
| F14.SH | SH/ |
| _F14.PIC, $AIM7.PIC | PIC/ |
| &VULCAN.11K, AIR004.11K | 11K/ |
| ^ACF11.5K | 5K/ |
| APA.MM / APA.T2 | MM/ / T2/ |

The rule is always "folder = extension". There is nothing else to configure.

Several `--src` roots may be given (for example the repo and a local folder for files that are
not in the repo yet). If the same file is found in two roots **with different bytes**, the tool
stops and names both paths. It never guesses which copy is newest: delete the old one.
Identical copies are fine.

`SHX/` and other folders not named after an extension are never read.

## 3. The set file `LIB/JKPFA54.txt`

Two sections. `#` starts a comment.

```
[rules]
FA_JKPFA54_A.LIB  *.PT *.ECM *.SEE *.HUD *.PTS    # aircraft
FA_JKPFA54_B.LIB  *.NT *.OT                       # ground units, ships, objects
FA_JKPFA54_C.LIB  *.JT *.GAS                      # weapons, fuel tanks
FA_JKPFA54_D.LIB  *.SH                            # 3D shapes
FA_JKPFA54_E.LIB  *.PIC                           # pictures
FA_JKPFA54_S.LIB  AIR*.11K                        # music
FA_JKPFA54_F.LIB  *.11K *.5K *.8K                 # sound effects
FA_JKPFA54_M.LIB  *.MM *.T2                       # maps

[files]
F14.PT
F14.SH
...
```

* `[files]` is the full list of files in the mod. Order does not matter; a name listed twice is an error.
* `[rules]` decides which LIB each file goes into. **The first matching line wins**, so the music
  line (`AIR*.11K`) sits above the general sound line (`*.11K`). A file that matches no rule is an error.
* Names must be 8.3 and upper case (the game's limit).

### Everyday changes

| I want to ... | do this |
|---|---|
| add a new file | put it in its extension folder, add its name under `[files]` |
| update a file | replace it in its folder. Nothing else. |
| remove a file from the mod | delete its line under `[files]` (the source file can stay) |
| add a new LIB | add one `[rules]` line, e.g. `FA_JKPFA54_G.LIB *.FNT` (free letters: G-L, N-R, T-Z) |
| move one file to another LIB | add a rule above the general one, e.g. `FA_JKPFA54_G.LIB F14*.PT` |
| start version 55 | copy the set file to `LIB/JKPFA55.txt` and rename the LIBs in `[rules]` |
| build just one LIB | `build ... --only D` |
| quick test build | `build ... --store` (no compression; the game reads stored entries too) |

## 4. Is a LIB correct? (`verify`)

`build` always runs the full check on what it just built and ends with one line:

```
RESULT: PASSED, 8 LIBs, 1511 entries: structure OK, every entry unpacks, checksums OK, contents match the sources
```

Anything else is `RESULT: FAILED` with one `FAIL` line per problem, and the exit code is 1.
Do not ship a LIB without `PASSED`. (`--no-verify` skips the check; don't use it for a release.)

Check LIBs at any time, for example after copying, uploading or downloading them:

```
python tools/falib.py verify build                                   # every .LIB in a folder
python tools/falib.py verify "C:\Program Files\Fighters Anthology"   # what is installed now
python tools/falib.py verify build --set LIB/JKPFA54.txt --src .     # also compare with the sources
```

What is checked, in order:

| # | check | catches |
|---|---|---|
| 1 | header and index: `EALIB`, count, offsets in order, first entry right after the index, end entry = file size, 8.3 upper-case names, no name twice, flag 0 or 4 | truncated or padded file, broken index, duplicate entries |
| 2 | every entry is unpacked in full; unpacked size = the size in its header; no stray bytes after the stream | damaged compressed data, wrong offsets |
| 3 | `$FALIB.INF` checksum list (see below): same file names, sizes and SHA-1 as at build time | **any** change to any entry, even one bit, without needing the sources |
| 4 | with `--set`: the LIB holds exactly the files its `[rules]` give it, each byte-identical to the source file | missing, extra or out-of-date files |
| 5 | across all LIBs checked (factory LIBs excepted): no file in two mod LIBs | the "which copy does the game use" problem |

Why check 3 is needed: PKWare data has no checksum of its own, so a flipped bit often still unpacks,
just to the wrong bytes. Checks 1-2 can't see that; the checksum list can.

**`$FALIB.INF`** is a small stored (uncompressed) text entry that every falib-built LIB starts with:
`lib`, `files`, then one `NAME SIZE SHA1` line per file. It has no date, so builds stay byte-identical.
The game ignores it, the same way it ignores the ToolKit's `$TOOLKIT.INF`. LIBs not built by
falib (factory, ToolKit) have no list: `verify` then says `NOTE no checksum list` and can only
prove checks 1, 2 and 5 (add `--set`/`--against` for 4).

Tested (2026-11-26) by damaging a good LIB seven ways: one bit flipped in compressed data, file
truncated, index offset moved, duplicate name, wrong unpacked size, entry renamed, and the bit flip
again without sources. `verify` failed every one and passed the undamaged LIB. Run on the game folder it
found real problems: `_HUD.LIB` holds `~F14S.PIC` twice, and DRNR1.PT, HAWK.NT, UH1.PT are each in two
JKPFA54 LIBs.

## 5. Other commands

```
python tools/falib.py list   FA_JKPFA54_D.LIB                  # entries, flags, sizes
python tools/falib.py unpack FA_JKPFA54_D.LIB out --by-ext     # extract into PT/ SH/ ... folders
python tools/falib.py verify FA_JKPFA54_D.LIB --against folder # compare with a folder of sources
```

`unpack --by-ext` is how to bring files from any LIB (an old release, a downloaded mod) into the
repo layout. The factory LIBs (FA_1, FA_2, FA_4B, FA_4D) unpack fine too; never write to them.

## 6. Installing and load order

* The game picks up every `*.LIB` in its folder (the JKPFA, `_MAP` and `_HUD` LIBs all load with no
  config entry; FA.EXE only names `.LIB`). Loose files in the game folder override every LIB.
  `check --game` lists loose files that differ from the source, because the game will use them.
* Mod files override the factory LIBs with the same name. Keep each file in only one mod LIB:
  `check --game` reports files that are installed in two mod LIBs today.
* Remove the old JKPFA LIBs (for example `FA_JKPFA_B.LIB`, `_MAP.LIB`, `_MUSIC.LIB`) when installing
  a new set, or their old copies stay loaded alongside the new ones.
* Keep mod LIB names sorting after `FA_4D.LIB` (the `FA_JKPFA...` names do). Inferred from the working
  setup, not tested with other names.

## 7. File format (for reference)

```
"EALIB"  uint16 count
count+1 entries of 18 bytes: name[13] (zero padded), flag[1], offset[4]
          last entry: empty name, offset = file size
entry data
```

* flag 0 = stored as is. flag 4 = `uint32 unpacked size` + PKWare DCL "implode" stream
  (header bytes `00 06`: binary literals, 4 KB window). FA.EXE links the PKWARE Data Compression
  Library, and every factory and ToolKit LIB uses flag 4 except FA_4D (music, flag 0).
* The PKWare window starts zero filled; EA's and the ToolKit's encoders sometimes copy from it
  (seen in SCDN_B.SH and AIR109.11K). The decoder handles this.
* ToolKit LIBs also hold `$TOOLKIT.INF` (project name, serial). The game does not need it and
  falib does not write it; falib writes `$FALIB.INF` instead (section 4).
* Compression ratio matches the ToolKit (JKP54D: 1,627,337 bytes by ToolKit, 1,634,908 by falib).

## 8. How the tool itself was checked

* Every entry of all 21 LIBs in `Lib pack study` (factory, JKPFA_53b, JKPFA54, MAP, MUSIC) unpacks,
  and the JKPFA54 ToolKit LIBs unpack byte-identical to their ToolKit project folders.
* Every compressed entry is unpacked again before it is stored in the cache, so a bad entry can't be written.
* Same input gives the same LIB bytes on every build (folder or zip source).
* In-game test: see the LIB 製作 thread (FA_JKPFA54_D.LIB rebuilt by falib in place of the ToolKit one).

## 9. Speed

Compressed entries are cached by content in `%LOCALAPPDATA%\falib\pk`, so only new or changed files
are compressed, on all CPU cores. Measured on Kuoyi's PC (8 threads): all 8 LIBs from cold 63 s,
again 1.4 s, plus about 15 s for the verify that follows every build. Verifying the whole game folder
(about 9,000 entries, 280 MB unpacked) takes about 2 minutes. The ToolKit took about 10 minutes for JKP54D alone. Deleting the cache folder is always safe.
