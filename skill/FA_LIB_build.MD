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
`build` writes `build/FA_JKPFA54_A.LIB` ... `build/FA_JKPFA54_M.LIB`. Copy them into the game folder
(after removing the old JKPFA LIBs, see section 5).

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

## 4. Other commands

```
python tools/falib.py list   FA_JKPFA54_D.LIB                  # entries, flags, sizes
python tools/falib.py unpack FA_JKPFA54_D.LIB out --by-ext     # extract into PT/ SH/ ... folders
python tools/falib.py verify FA_JKPFA54_D.LIB --against folder # unpack all, compare with sources
python tools/falib.py build  ... --verify                      # slow extra check after building
```

`unpack --by-ext` is how to bring files from any LIB (an old release, a downloaded mod) into the
repo layout. The factory LIBs (FA_1, FA_2, FA_4B, FA_4D) unpack fine too; never write to them.

## 5. Installing and load order

* The game picks up every `*.LIB` in its folder (the JKPFA, `_MAP` and `_HUD` LIBs all load with no
  config entry; FA.EXE only names `.LIB`). Loose files in the game folder override every LIB.
  `check --game` lists loose files that differ from the source, because the game will use them.
* Mod files override the factory LIBs with the same name. Keep each file in only one mod LIB:
  `check --game` reports files that are installed in two mod LIBs today.
* Remove the old JKPFA LIBs (for example `FA_JKPFA_B.LIB`, `_MAP.LIB`, `_MUSIC.LIB`) when installing
  a new set, or their old copies stay loaded alongside the new ones.
* Keep mod LIB names sorting after `FA_4D.LIB` (the `FA_JKPFA...` names do). Inferred from the working
  setup, not tested with other names.

## 6. File format (for reference)

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
* ToolKit LIBs also hold `$TOOLKIT.INF` (project name, serial). The game does not need it and the
  tool does not write it.
* Compression ratio matches the ToolKit (JKP54D: 1,627,337 bytes by ToolKit, 1,634,908 by falib).

## 7. How it was checked

* Every entry of all 21 LIBs in `Lib pack study` (factory, JKPFA_53b, JKPFA54, MAP, MUSIC) unpacks,
  and the JKPFA54 ToolKit LIBs unpack byte-identical to their ToolKit project folders.
* Every compressed entry is unpacked again before it is stored in the cache, so a bad entry can't be written.
* Same input gives the same LIB bytes on every build (folder or zip source).
* In-game test: see the LIB 製作 thread (FA_JKPFA54_D.LIB rebuilt by falib in place of the ToolKit one).

## 8. Speed

Compressed entries are cached by content in `%LOCALAPPDATA%\falib\pk`, so only new or changed files
are compressed, on all CPU cores. Measured on Kuoyi's PC (8 threads): all 8 LIBs from cold 63 s,
again 1.4 s. The ToolKit took about 10 minutes for JKP54D alone. Deleting the cache folder is always safe.
