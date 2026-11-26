# Building FA .LIB files (JKPFA set)

Tool: `tools/falib.py` (Python 3.8+, no packages). Current set file: `LIB/JKPFA6.txt` (the JKPFA6
release; `LIB/JKPFA54.txt` was the first draft and is replaced by it).
It replaces the FA ToolKit for building: no hand-edited ITEM.DAT, and a full build of every LIB
takes about 2 minutes the first time and a few seconds after that. It also writes FA ToolKit project
folders, so the ToolKit can still open every LIB's project (section 5).

## 1. The short version

```
python tools/falib.py check LIB/JKPFA6.txt --src . --game "C:\Program Files\Fighters Anthology"
python tools/falib.py build LIB/JKPFA6.txt --src . --out JKPFA6 --toolkit
```

Run from the repo root. `check` says what will change and stops on any problem;
`build` writes `JKPFA6/FA_JKPFA6_A.LIB` ... `JKPFA6/FA_JKPFA6_M.LIB` plus one ToolKit project folder
per LIB (`JKPFA6/JKPFA6A/` ...), then checks the LIBs and must end with `RESULT: PASSED` (section 4).
Copy the LIBs into the game folder (after removing the old JKPFA LIBs, see section 7).

On Kuoyi's PC the working copy is `C:\Users\hawke\Documents\SH\Lib pack study\JKPFA6`, built with
`--src` the repo **and** `--src "...\Lib pack study\JKPFA54_extra"` (216 files not uploaded to GitHub:
sound effects, `$` pictures, HUD/PTS/GAS, maps, music; same `<EXT>/` layout).

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

## 3. The set file `LIB/JKPFA6.txt`

Two sections. `#` starts a comment.

```
[rules]
FA_JKPFA6_A.LIB  *.PT *.ECM *.SEE *.HUD *.PTS    # aircraft
FA_JKPFA6_B.LIB  *.NT *.OT                       # ground units, ships, objects
FA_JKPFA6_C.LIB  *.JT *.GAS                      # weapons, fuel tanks
FA_JKPFA6_D.LIB  *.SH                            # 3D shapes
FA_JKPFA6_E.LIB  *.PIC                           # pictures
FA_JKPFA6_S.LIB  AIR*.11K                        # music (was _MUSIC.LIB)
FA_JKPFA6_F.LIB  *.11K *.5K *.8K                 # sound effects
FA_JKPFA6_M.LIB  *.MM *.T2                       # maps (was _MAP.LIB)

[files]
F14.PT        F-14A Tomcat
F14.SH
AIR004.11K    sound file
...
```

* `[files]` is the full list of files in the mod. Order does not matter; a name listed twice is an error.
* After the name, optional text is the **description** the FA ToolKit shows (ITEM.DAT column 2).
  Without one, the description is the file name, as the ToolKit does by default. No `"` allowed.
* `[rules]` decides which LIB each file goes into. **The first matching line wins**, so the music
  line (`AIR*.11K`) sits above the general sound line (`*.11K`). A file that matches no rule is an error.
* Names must be 8.3 and upper case (the game's limit).

### Everyday changes

| I want to ... | do this |
|---|---|
| add a new file | put it in its extension folder, add its name under `[files]` |
| update a file | replace it in its folder. Nothing else. |
| remove a file from the mod | delete its line under `[files]` (the source file can stay) |
| add a new LIB | add one `[rules]` line, e.g. `FA_JKPFA6_G.LIB *.FNT` (free letters: G-L, N-R, T-Z) |
| move one file to another LIB | add a rule above the general one, e.g. `FA_JKPFA6_G.LIB F14*.PT` |
| start version 7 | copy the set file to `LIB/JKPFA7.txt` and rename the LIBs in `[rules]` |
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
python tools/falib.py verify JKPFA6 --set LIB/JKPFA6.txt --src .     # also compare with the sources
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

## 5. FA ToolKit compatibility (`build --toolkit`)

With `--toolkit`, every LIB also gets an FA ToolKit 1.0 project folder in `--out`, named after the LIB:
`FA_JKPFA6_A.LIB` -> `JKPFA6A\` (drop `FA_` and `_`; at most 8 characters). Each folder holds what the
ToolKit itself keeps in a project folder:

| file | content |
|---|---|
| every source file of that LIB | flat, as the ToolKit stores them |
| `ITEM.DAT` | one line per file: `"NAME","description","D","NAME","","1.0"` (`D` = data file) |
| `PROJECT.DAT` | project name twice, then an empty line |
| `README.TXT` | ToolKit header, then `NAME` padded to 14 columns + description |
| `FA_0.LIB` | the built LIB (same bytes as `FA_JKPFA6_A.LIB`) |

These match the ToolKit's own files: generated from the JKP54A-E and MAP projects' own lists and
descriptions, PROJECT.DAT is byte-identical and ITEM.DAT differs only where the ToolKit filled column 5
(a few aircraft, e.g. F18E.PT) and in README.TXT line order (informational only). Opening a JKPFA6 project
in the ToolKit itself has not been tried yet.

The ToolKit folders are **output**: the repo (plus the extra folder) is the source. If you change or
add a file inside a ToolKit folder, the next `build --toolkit` **stops** and lists it
(`changed in the ToolKit folder` / `in the ToolKit folder but not in this LIB of the set file`),
so ToolKit work is never lost silently. Bring it back with `import` (below), then build again.
`--overwrite-toolkit` throws such changes away instead. A ToolKit file that only *looks* different
because the source got newer (it still equals what falib wrote last time, per FA_0.LIB's checksum list)
is simply replaced. Files removed from the set file are removed from the ToolKit folder.
`SHORTCUT.DAT` (the ToolKit's recent-files list) is left alone.

### Bringing ToolKit work back (`import`)

For Kuoyi's own ToolKit edits, or a project folder another player edited and sent back:

```
python tools/falib.py import JKPFA6\JKPFA6C --set LIB/JKPFA6.txt --to . --src "...\JKPFA54_extra" --dry-run
python tools/falib.py import JKPFA6\JKPFA6C --set LIB/JKPFA6.txt --to . --src "...\JKPFA54_extra"
```

`--to` is the writable copy of the repo (new files go to `<EXT>/` there); `--src` as in `build`
(changed files that live there are updated in place). Always run `--dry-run` first.

It compares three copies of every file, so it never guesses which is newest:
the ToolKit copy, the source copy, and the **released** copy (the `$FALIB.INF` checksum list in
`JKPFA6\FA_JKPFA6_C.LIB` next to the folder, else the folder's `FA_0.LIB`, or `--base LIB`).

| line | meaning | what happens |
|---|---|---|
| `IMPORT` | changed in the ToolKit, source unchanged since release | ToolKit file copied into the source |
| `KEEP` | source changed since release, ToolKit copy unchanged | nothing (source is newer) |
| `CONFLICT` | both changed, differently (or no release record) | **nothing at all is written**; rerun with `--take-toolkit NAME` or `--take-source NAME` |
| `NEW` | in ITEM.DAT but not in the set file | file copied to `<EXT>/`, name + description added to the set file; says which LIB the `[rules]` put it in |
| `DESC` | description changed in the ToolKit | set file line updated |
| `GONE?` | in the set file for this LIB, no longer in ITEM.DAT | kept; `--remove-missing` deletes the set-file line |
| `MISSING` / `IGNORED` | ITEM.DAT names a file that is not there / a file not in ITEM.DAT | reported only |

Tested (2026-11-26) on copies with all of these at once: a ToolKit edit, a repo edit, the same file
edited on both sides, a new JT with a description, a new PT dropped into the weapons project (correctly
sent to LIB A), a file removed from ITEM.DAT and a changed description. Build refused before the import,
import refused while the conflict was open, `--take-toolkit` resolved it, and the following build passed
with the repo edit kept.

On Kuoyi's PC (no git), `--to` must be a local copy of the repo; the changed files then go to GitHub
the usual way (for now: through a cloud thread).

## 6. Other commands

```
python tools/falib.py list   FA_JKPFA6_D.LIB                  # entries, flags, sizes
python tools/falib.py unpack FA_JKPFA6_D.LIB out --by-ext     # extract into PT/ SH/ ... folders
python tools/falib.py verify FA_JKPFA6_D.LIB --against folder # compare with a folder of sources
```

`unpack --by-ext` is how to bring files from any LIB (an old release, a downloaded mod) into the
repo layout. The factory LIBs (FA_1, FA_2, FA_4B, FA_4D) unpack fine too; never write to them.

## 7. Installing and load order

* The game picks up every `*.LIB` in its folder (the JKPFA, `_MAP` and `_HUD` LIBs all load with no
  config entry; FA.EXE only names `.LIB`). Loose files in the game folder override every LIB.
  `check --game` lists loose files that differ from the source, because the game will use them.
* Mod files override the factory LIBs with the same name. Keep each file in only one mod LIB:
  `check --game` reports files that are installed in two mod LIBs today.
* Remove the old JKPFA LIBs (for example `FA_JKPFA_B.LIB`, `_MAP.LIB`, `_MUSIC.LIB`) when installing
  a new set, or their old copies stay loaded alongside the new ones.
* Keep mod LIB names sorting after `FA_4D.LIB` (the `FA_JKPFA...` names do). Inferred from the working
  setup, not tested with other names.

## 8. File format (for reference)

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
* Factory LIBs and ToolKit LIBs use the same compressor: 7 unchanged files that are in both
  compress to the same bytes (76,761 total). The only difference is that EA stored some files
  uncompressed (all of FA_4D's music, 126 files in FA_2); the ToolKit compresses everything.
  Sound barely compresses (FA_4B music: 99.3% of original size).
* **Stored vs compressed (falib does what EA did):** a file whose compressed form is still 90% or more
  of its size is stored (flag 0) instead (`STORE_RATIO` in falib.py). That is all the music
  (AIR*.11K compresses to ~94-99%) and a few sound effects. The LIB grows by under 1% and the game
  does not have to unpack them.
* **Encoder:** greedy LZ77 + one-step lazy matching (if the match starting one byte later costs fewer
  bits per byte, send a literal first), 48-step hash chains, 4 KB window. Same entries as in the JKP54
  ToolKit LIBs (A-E, MAP, MUSIC; 45.4 MB unpacked), compression only, no store rule:

  | LIB | ToolKit | falib | |
  |---|---|---|---|
  | JKPFA54_A | 1,092,758 | 1,099,268 | 100.6% |
  | JKPFA_B | 212,443 | 209,468 | 98.6% |
  | JKPFA54_C (big PICs) | 3,039,452 | 3,099,497 | 102.0% |
  | JKPFA54_D | 1,620,140 | 1,610,820 | 99.4% |
  | JKPFA54_E | 1,136,609 | 1,133,916 | 99.8% |
  | _MAP | 528,557 | 528,605 | 100.0% |
  | _MUSIC | 7,570,990 | 7,550,343 | 99.7% |
  | **total** | **15,200,949** | **15,231,917** | **100.2%** |

  The first, greedy-only version was about 1-4% bigger. A full optimal parse was tried: about 2% smaller
  than the ToolKit but 20x slower, so it is not used.
* Changing `implode()` must come with a new `ENCODER_VERSION`, so cached entries made by the old
  encoder are not reused.

## 9. How the tool itself was checked

* Every entry of all 21 LIBs in `Lib pack study` (factory, JKPFA_53b, JKPFA54, MAP, MUSIC) unpacks,
  and the JKPFA54 ToolKit LIBs unpack byte-identical to their ToolKit project folders.
* Every compressed entry is unpacked again before it is stored in the cache, so a bad entry can't be written.
* Same input gives the same LIB bytes on every build (folder or zip source).
* In-game test: see the LIB 製作 thread (FA_JKPFA54_D.LIB rebuilt by falib in place of the ToolKit one).

## 10. Speed

Compressed entries are cached by content in `%LOCALAPPDATA%\falib\pk-v2`, so only new or changed files
are compressed, on all CPU cores. Measured on Kuoyi's PC (8 threads): all 8 JKPFA6 LIBs from cold about
2 minutes, again a few seconds, plus about 15 s for the verify that follows every build. Verifying the whole game folder
(about 9,000 entries, 280 MB unpacked) takes about 2 minutes. The ToolKit took about 10 minutes for JKP54D alone. Deleting the cache folder is always safe.
