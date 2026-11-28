---
name: fighters-anthology-mission-generator
description: Generate a complete Jane's Fighters Anthology Mission Creator .M mission file plus a same-basename .MT briefing/debriefing file from a natural-language scenario. Uses the user-supplied FA_items reference (Default only, Default + JKP600, or Default + JKPFA_53b, auto-detected), the companion <MAP>.MM.txt map data, and verified reverse-engineered samples. Covers sides/nationality, objects, flags, reactions, Target/Protect, wings and formation, Assignment/Target/Duration waypoints, carriers (deck start, recovery, split hull+Tower carriers), moving ships, high-altitude and dive bombing, fuel/hardpoints 4-8 (empty and multi-round), ambient units, and 7-character revisioned filenames. Never invents undecoded fields.
---

# Fighters Anthology `.M` Mission Generator Skill

**Version: v28** (2026-11-28). File name: `fighters_anthology_mission_generator_SKILL.md` (never versioned; version and
support status live only in this header). v28 is a full reorganisation of v27 by topic: every v27 rule, tuple and
table is kept; repeated text and version-history prose were removed. No behaviour changed.

## Version and support status

| Area | Status |
|---|---|
| Items profiles | `DEFAULT_ONLY` (factory FA). `DEFAULT_PLUS_JKP`: **JKP600** (`(JKP600 Lib)` markers) and later `JKP<number>` with the same layout, and the older **JKPFA_53b** (`(JKPFA_53b Lib)`). §2 |
| Maps | 14 companion `.MM.txt`: APA, BAL, CUB, EGY, FRA, GRE, IRA, LFA, NSK, PGU, SPA, TVIET, VLA, WTA. Any other map needs its `.MM.txt`. §3 |
| Output | `.M` + same-basename `.MT`, 7-character revisioned basename `^[A-Z0-9]{6}[1-9A-Z]$`. §4.6 |
| Confirmed | header/briefing lines, `sides4`/`nationality3`, coordinates/heading/speed, aliases, flags (success, hide on briefing map, ignore me), all nine reaction classes, search distance, Target/Protect, wings + `npcFlags 2`, `w_wng` formation/spacing/stacking/control, Assignment/Target/Duration (`w_goal 1/4/8/16`), carrier deck start/landing (`w_goal 34`), moving ships, split carriers + Towers, fuel and hardpoints 4–8 (empty and multi-round), bombing corridors, dive bombing. |
| Not decoded | see §17. Never invent. |

Rule origin (kept so old discussions can be matched; the rule text is in the topic sections):
v12 takeoff/landing 0 ft/0 speed and the four formation settings · v13 carrier deck start, A = first airborne point ·
v14 carrier recovery at carrier's initial X/Z · v15 fuel freedom, hardpoints 4–8 only · v16 1–8 char names (historical,
replaced by v25) · v17 spacing far by default · v18 high-altitude bombing corridor, attack lead, no aircraft bomb
targets · v19 `w_react $ffff $0 $0` attack corridor · v20 per-waypoint bomb targets, `.MM` targets · v21 split
carriers + Towers · v22 Assignment/Target/Duration · v23 dive bombing far+loose · v24 `divetest.M` near-vertical dive ·
v25 7-char revisioned names, `1.M` class masks · v26 empty / multi-round hardpoints · v27 JKP600 profile ·
v28 reorganised text.

Evidence files: `coldwar(2).M`, `a.M`–`e.M`, `~B08.M/.MT`, `~E39.M/.MT`, six formation differentials, `assignment.M`
(v22), `CV.M` (v21), `divetest.M` (v24), `1.M` (v25), Mission Creator screenshots, `CUB.MM`.

---

# 1. Purpose, priorities, source hierarchy

Turn the user's mission description into a game-parsable `.M` and a matching `.MT`. Priorities:

1. Files the game/Mission Creator can parse.
2. Preserve the user's units, sides, routes, Target/Protect, reactions and success conditions.
3. Use only asset filenames and encodings supported by the references or verified samples.
4. Never guess an unknown bitfield or code. A syntactically complete but behaviourally fabricated mission is a failure.
5. If a requested feature is undecoded, use a verified equivalent mechanism or ask for one single-variable Mission
   Creator differential sample.

Source hierarchy (highest first):

1. A user-provided working `.M`/`.MT`, differential file, or explicit working syntax example. If it contradicts this
   skill, it wins: report the conflict.
2. The companion `<MAP>.MM.txt` for the selected `.T2` (map-local names, types, nationalities, positions, headings,
   default skill/react). Match by its internal `map <basename>.T2` line, not the filename.
3. The effective catalog from the uploaded `FA_items` file (§2).
4. Rules marked CONFIRMED here; then HIGH CONFIDENCE rules only when needed and uncontradicted.
5. Never invent a `.PT/.NT/.OT/.JT/.LAY/.T2`, flag bit, reaction mask, `w_goal`, target code, nationality or map
   location from general aviation knowledge.

---

# 2. Items reference and asset profile

Categories in the items file: aircraft `*.PT`; ordnance/equipment `*.JT` (and external tanks `*.GAS` in the ordnance
section); vehicles/ships `*.NT`; scenery `*.OT`; layers `*.LAY`; maps `*.T2`; country list/order. A `*.PT` is an
aircraft object that may carry `fuel`/`hardpoint`; a `*.JT` is a token used *inside* hardpoint lines (a `*.JT` mission
object gets no hardpoints).

**Decoding.** Detect encoding first: BOM `FF FE` → UTF-16 LE; UTF-8 BOM → UTF-8 minus BOM; else ASCII/UTF-8.
Never reject a file for being UTF-16.

**Profile from content, not filename** (a renamed file must still work):

- `DEFAULT_ONLY`: only normal sections (`Aircraft:(*.PT)`, `Ordnance:(*.JT)`, `Vehicles: (*.NT)`, `Scenery: (*.OT)`).
  Use only those Default entries; never import or remember JKP assets from another request.
- `DEFAULT_PLUS_JKP`: section headers like `Aircraft:(*.PT) (when JKP600 Lib installed)` and/or row tags
  `(JKP600 Lib)`; also any later `JKP<number>` with the same layout, and the older `(when JKPFA_53b Lib installed)` /
  `(JKPFA_53b Lib)`. Whitespace around headers is not significant. JKP600 is the successor of JKPFA_53b (Zephyr's
  JKPFA 4.55–5.3 beta, continued by hawke as JKP). Everywhere this skill says "JKP", read "the JKP library named by
  the uploaded items file". Use only the one items file supplied; never mix JKPFA_53b and JKP600 lists. Report the
  profile as e.g. `DEFAULT_PLUS_JKP (JKP600)`.

**Overlay (PT, JT, NT, OT separately):** `EFFECTIVE_X = DEFAULT_X overlaid by JKP_X`, key = filename token,
case-insensitive; serialise the spelling from the effective row.

1. Default-only filename → keep. JKP-only filename → add.
2. Same filename in both → the JKP row wins; the Default meaning is inactive and must not remain a natural-language
   search alias (both for exact filenames and natural-language names).
3. JKP listing one filename several times with different labels = one installed file with several JKP aliases; do not
   resurrect the Default meaning and do not invent a variant selector (the `.M` holds only the filename).
4. `*.GAS` follows the ordnance-section profile; in the known combined files tanks are Default-side. Never invent one.
5. `*.LAY`, `*.T2`, country order and any category without a JKP section stay Default-only. A JKP-only filename is
   valid only if listed. Do not fabricate an overlay.
6. **Split-carrier exception:** `ESSE.NT`/`ESSET.OT`, `CDEG.NT`/`CDEGT.OT`, `INVN.NT`/`INVNT.OT`, `ELIZ.NT`/`ELIZT.OT`,
   `KUZN.NT`/`KUZNT.OT` are verified by `CV.M`; under `DEFAULT_PLUS_JKP` they are valid even if the items file omits
   them (JKP600 lists them). Unavailable under `DEFAULT_ONLY`. No other absent asset may be assumed.
7. Catalogs are request-local; re-read the uploaded file every request (a future library may redefine a filename).

Examples (illustrative; a JKP row overrides them): `F14.PT` F-14D Tomcat, `E2.PT` E-2C, `E3.PT` E-3 AWACS,
`AC130.PT` AC-130U, `MIG29.PT` MiG-29 Fulcrum-C, `TU26.PT` Tu-26 Backfire-C, `KITT.NT` Kitty Hawk, `CUB.T2` Cuba,
`day2.LAY` normal day/green terrain. Never assume a real-world name maps to an obvious filename: search the effective
catalog.

---

# 3. Companion map `<MAP>.MM.txt`

The upload is the original `.MM` with a transport `.txt` suffix (also `CUB(4).MM.txt`; a legacy plain `.MM` is fine).
Parse the content as `.MM`; verify the internal `map <basename>.T2` line. It is a map-local reference database, not a
template. Read it fresh each request before choosing map-specific coordinates; never apply Cuba data to another map.

Index from `obj` blocks: `type`, `name`, `pos`, `angle`, `nationality3`, `flags`, `speed`, `alias`, and `skill`,
`react`, `searchDist` when present; and `special` markers (`name`, `pos`, e.g. Cuba, Straits of Florida, Caribbean Sea).
Example map object:

```text
obj
	type STRIP1.OT
	pos 1317907 0 1971133
	angle 0 0 0
	nationality3 0
	flags $4003
	speed 0
	alias -10101
	name <SOH>Key West<SOH>
	.
```

Use it to: resolve named places ("start at Key West" → that object's exact `pos`/`angle`); get airfield heading;
read map-default nationality; see existing SAM/AAA/vehicles/scenery near the mission area; place new units plausibly
and not on top of map objects; use `special` markers as regional anchors.

Rules:

- Do not copy `.MM` objects into the `.M`, and do not duplicate a map object (including to make it targetable). Do not
  rewrite map objects' skill/flags/react; the Expert default applies to generated objects only.
- `.MM` aliases are reserved: generated aliases must not collide with them. Exception: confirmed `.MM` ground-object
  aliases may be used directly as **bombing** targets (§13.5). Non-bombing cross-file Target/Protect stays unverified.
- Ignore `tmap`/`tdic` terrain sections; never copy them into `.M`.

Anchor priority: (1) user raw coordinates, (2) matching `.MM` named object / `special`, (3) supplied working `.M`,
(4) legacy Cuba anchors (§15), (5) otherwise ask for the `.MM.txt` or another anchor.

---

# 4. Physical file format

## 4.1 `.M`

- ASCII bytes only; transliterate non-ASCII names. No smart punctuation.
- CRLF line endings.
- Strings delimited by byte `0x01` (SOH), not `"`: `name \x01Player\x01`; empty string `\x01\x01`. Never write the
  literal text `<SOH>`.
- Hex values use `$` and lowercase: `$0`, `$80`, `$4017`, `$c000`, `$4000ffff`.
- `obj` and `waypoint2` blocks end with a tab + `.` line.
- End the final block with CRLF (optionally one blank CRLF), then one `0x00` byte.

## 4.2 `.MT`

Same basename as `.M`. ASCII plain text, CRLF, **no** SOH delimiters, **no** final NUL; end with a normal CRLF.

## 4.3 Top-level order

1. header/world lines; 2. `sides4` (64 entries); 3. time / global skills / era; 4. all `obj` blocks; 5. all
`waypoint2` blocks; 6. final NUL.

```text
textFormat
brief
briefmap
armplane
map cub.T2
layer day2.LAY 0
clouds 0
wind 65 7
view 4149 1277450 802580
sides4 
	...64 entries...
time 12 0
usGroundSkill 3
usAirSkill 3
themGroundSkill 3
themAirSkill 3
historicalera 4
```

- `brief`, `briefmap`, `armplane` are **required**, immediately after `textFormat` and before `map`. The samples
  `~B08.M`/`~E39.M` also have `selectplane` between `briefmap` and `armplane`; it is optional (keep it if a working
  template has it).
- Cuba defaults when unspecified: `map cub.T2`, `layer day2.LAY 0`, `clouds 0`, `wind 65 7`, `time 12 0`, all four
  global skills `3`, `historicalera 4`.
- `view` is an editor view: if no reference gives one, use `view 4149 <centerX> <centerZ>` (average of major object
  positions). The first number is not decoded.

## 4.4 Output filename (v25)

The `.M` and `.MT` share one basename `<STEM6><REV1>`, exactly 7 characters, matching `^[A-Z0-9]{6}[1-9A-Z]$`:

- `STEM6`: six uppercase ASCII letters/digits identifying the mission. Normalise/abbreviate a user name
  deterministically to exactly six, keeping it recognisable. No `~`, spaces, `_`, `-`, punctuation, lowercase.
- `REV1`: revision `1 2 … 9 A B … Z`; first generation `1`; each user-requested modification of the same mission keeps
  the stem and advances one step (`TOPGUN1` → `TOPGUN2` …, after `9` comes `A`). `0` is never used. After `Z`, do not
  roll over: ask for a new stem.
- When revising an uploaded mission already in this scheme, keep characters 1–6 and increment character 7.
- Legacy names (`~B08.M`, 1–8-char v16 names `^[A-Z0-9]{1,8}$`) are valid evidence only, never new output.

---

# 5. Countries, `sides4`, `nationality3`

Zero-based country index:

```text
 0 America       1 Britain       2 China         3 France        4 Germany
 5 Belgium       6 Jordan        7 Israel        8 Japan         9 North Korea
10 Russia       11 South Korea  12 Syria        13 Arab Egypt   14 Islamic Egypt
15 Estonia      16 Latvia       17 Lithuania    18 Poland       19 Belorussia
20 North Vietnam 21 South Vietnam 22 Ukraine    23 Iraq         24 Iran
25 Kuwait       26 Saudi Arabia 27 Oman         28 U.A.E.       29 Qatar
30 Bahrain      31 Libya        32 Sudan        33 Cuba         34 Panama
35 Columbia     36 Pakistan     37 India        38 Afghanistan  39 Taiwan
40 Greece       41 Turkey       42 Italy        43 Sweden       44 Finland
45 Norway       46 Spain        47 Portugal     48 Austria      49 Denmark
50 Netherlands  51 Canada       52 Bulgaria     53 Hungary      54 Romania
55 Australia    56 Philippines  57 Argentina    58 Bosnia       59 Serbia
```

`sides4`: exactly 64 entries; slots 0–59 = countries, slots 60–63 = `$0` (reserved). Friend of the player `$0`, enemy
`$80`; unused countries `$0` unless a reference mission's table should be preserved.

`nationality3 = country_index | (enemy ? 0x80 : 0)` (verified: America friendly `0`, China enemy `130`, Russia enemy
`138`). Never set the enemy bit on friendly objects.

---

# 6. Coordinates, distance, heading, speed

- `pos X Y Z`: `+X` East, `-X` West, `+Z` North, `-Z` South, `Y` altitude in feet; horizontal units are feet.
  `1 NM ≈ 6076.12` units (E-2C test: ~100 NM north ≈ +635,000 Z).
- Point at bearing `B` (clockwise from north) and `D_nm`: `DX = D_nm·6076.12·sin B`, `DZ = D_nm·6076.12·cos B`,
  `X2 = round(X1+DX)`, `Z2 = round(Z1+DZ)`.
- `angle H 0 0`: `H` = heading in degrees, `0` North, `90` East, `±180` South, `-90` West, clockwise positive. If not
  given, `H = degrees(atan2(DX, DZ))` of the first movement, normalised to `[-180, 180]`.
- `speed` / `w_speed` are ft/s: `fps ≈ knots × 6076.12 / 3600` (UI may differ by 1; keep raw values from references).
  Verified: 50 ≈ 29.6 kt, 676 ≈ 400 kt, 683 ≈ 405 kt, 795 ≈ 471 kt.

---

# 7. Objects

## 7.1 Aliases

Unique negative integers `-1, -2, -3, …` in deterministic object-creation order (after adding ambient units and split
carrier Towers). Waypoint groups use `w_for <alias>`. Never reorder objects after computing target descriptors without
recomputing them.

## 7.2 Object block

```text
obj
	type F14.PT
	pos 1704797 10000 736196
	angle 0 0 0
	nationality3 0
	flags $4017
	speed 676
	alias -1
	controller $80
	name \x01Player\x01
	skill 3
	react $c000 $3fff $0
	searchDist 0
	.
```

Keep the sample field order. Optional lines in their sample positions: `preferredTargetId2` (§10), `wing`, `npcFlags`,
`wng` (§11), then `fuel`, then `hardpoint` lines (§8).

- `type`: from the effective catalog or a verified sample.
- `controller $80` = human player. Use only on the player aircraft (no other controller values are decoded).
- `skill`: `1` average, `3` Expert (0–3 scale; labels for 0/2 unverified). **Every generated unit, friend or foe,
  uses `skill 3`** unless the user asks otherwise for that unit/group; global skills also `3`.
- `name`: optional, ASCII, SOH-delimited.
- Split-carrier Tower objects use their own short template (§12.6).

## 7.3 Flags

Base `$4017` = Mission success Not affected, attackable, shown on briefing map, zero start delay (a tested base, not a
fully decoded constant). Confirmed modifiers, composed with OR:

```text
0x0020 Survive            0x0080 Destroyed      (choose at most one per object)
0x0200 Ignore me          0x0400 Hide in briefing map
```

```text
Not affected $4017   Survive $4037   Destroyed $4097
Hidden $4417   Ignore me $4217   Hidden + Ignore me $4617
Hidden + Survive $4437   Hidden + Destroyed $4497
```

Success conditions behave as jointly required (Cold War test: carrier survives + four F-14s survive + both Tu-26s
destroyed).

Generation policy:

- **Player wing always Not affected:** the player aircraft and every AI wingman in its `wing` have both `0x20` and
  `0x80` cleared, whatever the narrative says. Other modifiers are kept.
- **Enemies hidden on the briefing map:** every hostile object generated into the `.M` (aircraft, ships, vehicles,
  defences, scenery, hostile ambient units) gets `|= 0x0400` (normal base → `$4417`) unless the user asks to show it.
  Friendly/player objects stay shown unless asked. Side/nationality decides, not asset type. The `.MT` has no
  per-object visibility field; do not invent one.
- Unmentioned objects and ambient units are Not affected.
- Only zero start delay is decoded; never invent a nonzero delay.
- Split-carrier Towers use `flags $4011` and skip this composer.

---

# 8. Fuel and hardpoints (`*.PT` aircraft only)

`fuel` and `hardpoint` lines are allowed **only** in an object whose `type` ends in `.PT`; never on `.JT`, `.OT`, `.NT`
or anything else. If the user asks for one on an ineligible object, do not serialise it; explain why.

**Fuel** `fuel <percent>` (percent of internal fuel, practical 0–100), after the wing/formation fields and before
hardpoints. The user's value wins; otherwise the generator may add one whenever role, route length, endurance, loiter,
recovery or reserve justify it, or omit it when default fuel is fine. No fuel-burn model is decoded.

**Stations:** `1–3` reserved (never emit), `4–5` fuselage, `6–8` wing, `9` prohibited (never emit, even if requested
or seen in old samples). Valid stations are exactly `{4,5,6,7,8}`. No real-world pylon, weight, symmetry, launcher,
era or nationality limits.

**Syntax:**

```text
hardpoint <station> <positive_quantity> <item_file>
hardpoint <station> 0 
```

- Equipped: positive integer quantity; values above 1 = several rounds of the same item on one station (e.g.
  `hardpoint 5 4 AIM9D.JT`). Item from the effective ordnance catalog: `*.JT` for weapons/equipment, a listed `*.GAS`
  for tanks. Never invent an item; one item type per station (mixed types undecoded).
- Empty: `hardpoint <station> 0` **followed by exactly one ASCII space before the line ending**, no item token (no
  `null`, `-`, quotes or comment). The space is syntax: without it the mission errors. An explicit empty override is
  not the same as omitting the line. Never auto-fill an explicitly empty station, turn a user's `0` into a
  positive quantity, or add an equipped line for the same station.
- User mappings for stations 4–8 win and are emitted exactly (keep quantities). Requests for 1–3 or 9 are not
  serialised.
- Without user mappings, a role-aware loadout on 4–8 may be built from catalog descriptions: CAP/BARCAP/escort/sweep/
  intercept → air-to-air; strike/bombing/interdiction/CAS → air-to-ground plus self-defence; SEAD/DEAD → suppression
  weapons (never invent an anti-radiation token); anti-ship → anti-ship weapons or heavy strike ordnance; recon/EW →
  pods/equipment when representable; ambiguous multirole → balanced. Fuel and loadout are independent.

Working examples (syntax evidence):

```text
hardpoint 4 0 
hardpoint 5 4 AIM9D.JT
hardpoint 6 0 
hardpoint 7 0 
```

```text
fuel 50                      fuel 80
hardpoint 4 4 AIM54C.JT      hardpoint 4 3 GBU28.JT
hardpoint 5 2 F250.GAS       hardpoint 5 2 F250.GAS
hardpoint 6 2 AIM7.JT        hardpoint 6 2 MK82.JT
hardpoint 7 2 AIM9M.JT       hardpoint 7 1 AIM9M.JT
```

In the first block the lines `hardpoint 4 0`, `6 0`, `7 0` each end with `\x20` (`"hardpoint 4 0\x20"`). Validate on
the real file bytes: any trailing-whitespace cleanup must exempt these lines; `hardpoint 4 0` without the space is
invalid.

---

# 9. Reactions and search distance

## 9.1 Structure

`react <ATTACK> <DEFEND> <EVADE>` (object) and `w_react <ATTACK> <DEFEND> <EVADE>` (waypoint). A class bit in word 1 =
Attack, word 2 = Defend, word 3 = Evade, in none = Ignore. Same semantics for aircraft, ships, vehicles, tanks, AAA,
SAM and other objects wherever the field is valid (this does not decode movement routes for those objects).

## 9.2 Class masks (all nine confirmed)

```text
Fighter $8000   Bomber $4000   Ship $2000   SAM $1000   AAA $0800
Tank $0400      Vehicle $0200  Structure $0100          Other $0040
```

The other low bits inside `$ffff` have no confirmed meaning: never name them; keep them in the same word as the
verified baseline you start from, and move only the confirmed class bits the user asks for.

`1.M` differential (START, A–F, END; all A–F use `w_goal 1`, `w_searchDist 10`, `w_preferredTargetId2 $0` as test
setup, not as mandatory values). Each row is all-Attack with one class moved to Defend:

| Point | Defend class | `w_react` |
|---|---|---|
| A | SAM | `$efff $1000 $0` |
| B | AAA | `$f7ff $800 $0` |
| C | Tank | `$fbff $400 $0` |
| D | Vehicle | `$fdff $200 $0` |
| E | Structure | `$feff $100 $0` |
| F | Other | `$ffbf $40 $0` |

Tailor reactions to each unit's role; the A–F pattern is a reference, not doctrine.

## 9.3 Verified presets

```text
Fighter/Bomber Attack, rest Ignore          react $c000 $0 $0
Fighter/Bomber Evade, rest Ignore           react $0 $0 $c000
Fighter/Bomber Attack, rest Defend          react $c000 $3fff $0
All Defend (passive/defensive)              react $0 $ffff $0
All object types Attack (bombing, §13)      react $ffff $0 $0 / w_react $ffff $0 $0
Preset B: Fighter Ignore, Bomber Evade, Ship Attack, SAM/AAA/Tank/Vehicle/Structure Defend, Other Attack
                                            react $2040 $1fbf $4000
Preset C: as B but AAA Attack               react $2840 $17bf $4000
Cold War ship attack (historical)           w_react $2000 $c000 $0   (Ship Attack, Fighter+Bomber Defend)
```

The Cold War tuple is kept when reproducing that sample; the v22 Anti-ship Assignment preset is `$2000 $8000 $0`
(§12.3). Waypoint Assignment presets are in §12.3. Composite presets (Wild Weasel, CAS) do not authorise guessing the
meaning of their component bits.

## 9.4 Search distance

`searchDist` / `w_searchDist`: `0` = search at any distance; `25` ≈ 25 NM (repeatedly tested); explicit numbers are
written as given; omitted for a combat unit → `25`. A selected v22 Assignment uses its own tuple value (§12.3).

---

# 10. Target and Protect (`preferredTargetId2`)

- Target: `preferredTargetId2 = alias & 0xffff` (alias `-1` → `$ffff`, `-3` → `$fffd`).
- Protect: `preferredTargetId2 = 0x40000000 | (alias & 0xffff)` (alias `-1` → `$4000ffff`, verified; `-3` →
  `$4000fffd`). The `0x40000000` bit marks Protect only.
- No object-level assignment → omit the line. Waypoints always carry `w_preferredTargetId2`, `$0` when none.
- Waypoint targets use the same low-16-bit alias (Cold War: `w_goal 16`, `w_preferredTargetId2 $ffff` = Kitty Hawk
  alias `-1`, i.e. "until that carrier is destroyed"; not a wildcard).
- Object-level Target/Protect needs no waypoint group: the AI follows/chases the object ("F-14 protects E-2C",
  "MiG targets E-3", "attacker targets an aircraft").
- A `*.PT` aircraft is never a valid **bomb** target (§13.4).

---

# 11. Wings and formation

## 11.1 Wings

`wing <wing_id> <member>`: member `0` = leader, then 1, 2, …; one unique wing id per formation (e.g. `wing 0 0` …
`wing 0 3`). AI members of the **player's** wing get `npcFlags 2` (the player does not). Do not add it to unrelated AI
formations.

## 11.2 `w_wng` (visible waypoints)

Field order `w_wng <control> <formation> <spacing> <stacking>`, fully mapped by six differential files:

```text
control:   loose 1, medium 2, tight 3
formation: Echelon 0, Line abreast 1, Line astern 2
spacing:   far 2048, near 512
stacking:  level 0, high 512, low -512
```

| Differential file | waypoint `w_wng` | object `wng` |
|---|---|---|
| Echelon_far_level_loose.M | `1 0 2048 0` | `1 0 2048 0` |
| Echelon_near_high_tight.M | `3 0 512 512` | `1 0 512 512` |
| Line astern_near_level_Tight.M | `3 2 512 0` | `1 2 512 0` |
| Line abreast_near_level_Tight.M | `3 1 512 0` | `1 1 512 0` |
| Echelon_near_low_tight.M | `3 0 512 -512` | `3 0 512 -512` |
| Echelon_near_low_medium.M | `2 0 512 -512` | `3 0 512 -512` |

Individually verified values may be composed in this order. Do not extend to unlisted values or infer from menu order.
START/END records always use `w_wng 0 0 0 0`.

**Object-level `wng`:** fields 2–4 match formation/spacing/stacking, but field 1 is **not** the waypoint control (the
low/medium file keeps `3` while its waypoint has `2`). Use an exact verified tuple, otherwise a tested conservative
pattern; never derive field 1 from a rule.

## 11.3 Defaults (every visible navigation point)

- Honour any user-specified setting whose mapping is verified.
- formation omitted → random among Echelon / Line abreast / Line astern.
- stacking omitted → random among level / high / low.
- **spacing omitted → always `far` (2048).** `near` only when the user explicitly asks; never random, never inherited
  from a historical sample.
- **control omitted → always `loose` (1).** `medium`/`tight` only on request (they make wingmen stick to the route and
  stop them breaking off to attack).
- Exceptions only: high-altitude bombing corridor `near + tight` (§13.1); dive bombing `far + loose` with an optional
  `near + tight` pre-dive staging point (§13.6). Precedence:

```text
v24 near-vertical dive, pre-dive staging point -> near + tight allowed (sample)
dive terminal / active dive-maneuver points     -> far + loose
high-altitude / level bombing, hostile area     -> near + tight
all other navigation                            -> far + loose (+ user choices)
```

---

# 12. Waypoints

## 12.1 Group structure

```text
waypoint2 N
	...records...

  w_for <object_alias>
	.
```

`N = visible points + 2` (hidden START and END): A only → `3`, A/B → `4`, A–D → `6`. `w_index` runs `0 … N-1`. Every
routed object has its own group (Cold War four-ship: identical groups per member).

START:

```text
	w_index 0
	w_flags $1
	w_goal 0
	w_next 0
	w_pos2 0   0   <startX> <startY> <startZ>
	w_speed 0
	w_wng 0 0 0 0
	w_react $0 $0 $0
	w_searchDist 0
	w_preferredTargetId2 $0
	w_name \x01\x01
```

Ordinary airborne point:

```text
	w_index <i>
	w_flags $0
	w_goal 1
	w_next 0
	w_pos2 0   0   <X> <ALT_FT> <Z>
	w_speed <FPS>
	w_wng <control> <formation> <spacing> <stacking>
	w_react <A> <D> <E>
	w_searchDist <range>
	w_preferredTargetId2 $0
	w_name \x01<label>\x01
```

END:

```text
	w_index <last>
	w_flags $2
	w_goal 0
	w_next 0
	w_pos2 0   0   0 0 0
	w_speed 0
	w_wng 0 0 0 0
	w_react $0 $0 $0
	w_searchDist 0
	w_preferredTargetId2 $0
	w_name \x01\x01
```

## 12.2 `w_goal`, `w_flags`, `w_pos2`

```text
w_goal 0  START/END, no assignment
w_goal 1  until waypoint is reached
w_goal 4  until target is attacked
w_goal 8  until target is damaged
w_goal 16 until target is destroyed
w_goal 34 Land (tested as carrier landing)
```

`w_goal` is the **Duration**, not the Assignment (old labels "1 = Normal Flight", "16 = Anti-Ship" are wrong). It
never implies a reaction: a `w_goal 1` point inside a bombing corridor still uses `w_react $ffff $0 $0`.

`w_flags`: `$1` START, `$2` END, `$0` normal, `$4` seen on a moving ship's real waypoint (meaning undecoded; use only
in that pattern).

`w_pos2 <modeA> <modeB> X Y Z`: `0 0 X ALT Z` normal airborne; `1 0 X 0 Z` moving ship/carrier point and carrier
landing. Mode meanings are unknown: never use `1 0` elsewhere, never apply special modes to ground objects, and the
0 ft/0 speed rule does not decode land-airfield modes. `w_next` is always `0`.

## 12.3 Assignment / Target / Duration (v22)

Each configured visible point has three Mission Creator choices: **Assignment** (tactics), **Target** (none or one
alias → `w_preferredTargetId2`), **Duration** (→ `w_goal`). Exact `assignment.M` tuples (the aircraft column only names
the test row; the mapping is not aircraft-specific):

| Row | Assignment | Target | Duration | `w_goal` | `w_react` | `w_searchDist` | `w_preferredTargetId2` |
|---|---|---|---|---:|---|---:|---|
| F-4B `F4B.PT` | Normal Flight | none | waypoint reached | 1 | `$0 $8000 $0` | 0 | `$0` |
| F-5E `F5E.PT` | MIGCAP | none | waypoint reached | 1 | `$8000 $0 $0` | 25 | `$0` |
| F-8E `F8J.PT` | BARCAP | none | waypoint reached | 1 | `$c000 $0 $0` | 25 | `$0` |
| F-14 `F14.PT` | Wild Weasel | none | waypoint reached | 1 | `$1800 $8000 $0` | 10 | `$0` |
| F-15 `F15.PT` | CAS | none | waypoint reached | 1 | `$400 $9800 $0` | 5 | `$0` |
| F-16 `F16F.PT` | Anti-ship | none | waypoint reached | 1 | `$2000 $8000 $0` | 0 | `$0` |
| F-22 `F22.PT` | Hi/Lo sweep | none | waypoint reached | 1 | `$ffff $0 $0` | 10 | `$0` |
| F-35A `ASTOVL.PT` | Hi/Lo sweep | airport | target attacked | 4 | `$ffff $0 $0` | 10 | `$fff7` |
| F-35B `ASTOVLF.PT` | Hi/Lo sweep | airport | target damaged | 8 | `$c000 $0 $0` | 25 | `$fff7` |
| F-35C `F22N.PT` | Hi/Lo sweep | airport | target destroyed | 16 | `$c000 $0 $0` | 25 | `$fff7` |

`$fff7` = the sample's `STRIP1.OT` alias `-9`; always encode the real target alias.

Rules:

- A matching combination → use the exact full tuple, unless the user explicitly customises class reactions.
- The first seven rows are the named Assignment presets (reaction + search). For an untested combination, compose
  Target and Duration from the mappings and start the Assignment from its preset, unless a tested tuple contradicts it.
  The targeted Hi/Lo-sweep rows are such a contradiction: use them as full tuples (damaged/destroyed use `$c000`/25).
- `w_react` is also the editable per-class matrix (`1.M` screenshot: Normal Flight / no target / waypoint reached
  with SAM Defend, rest Attack). A user's custom class reactions change only the confirmed class bits and keep the
  requested Target, Duration, search distance and formation. Do not force them back to a named preset.
- When the user explicitly asks for a v22 tuple, do not rewrite its fields to bombing defaults; otherwise bombing
  rules (§13) are the defaults for bombing routes. A future exact differential outranks composition.
- Example: "Tu-26 flies to B with Anti-ship, targets carrier, until destroyed" → B: Anti-ship reaction/search, carrier
  alias16, `w_goal 16`.

---

## 12.4 Takeoff and landing points

- A **visible** takeoff/launch point and every landing/recovery point use `w_pos2 … X 0 Z` and `w_speed 0`. This fixes
  only altitude and speed; `w_goal`, `w_flags`, `w_pos2` modes still come from verified context (no takeoff `w_goal`
  exists; `w_goal 34`/`1 0` only for the tested carrier landing, not land airfields). START/END never become visible
  takeoff/landing points.
- **Carrier deck start:** aircraft starting on a carrier deck at 0 ft / 0 speed (verified pattern) get **no** visible
  launch point; the deck state is the launch. Navigation point A is the first real airborne point (CAP, rendezvous,
  ingress, marshal, escort, transit) with that role's altitude, speed and settings, never forced to 0/0. No extra 0/0
  point near the carrier. The whole carrier-launched wing shares the same route order. Only if the user explicitly
  asks for a visible launch point (or a working sample needs one) emit it at 0 ft / speed 0.
- **Carrier recovery:** the landing waypoint is at the landing carrier's **initial** `pos` X/Z, with `w_flags $0`,
  `w_goal 34`, `w_pos2 1 0 <carrierX> 0 <carrierZ>`, `w_speed 0`, even if the carrier moves. Never project, lead or
  extrapolate for carrier speed, course, ETA or mission time.
- Sequence: deck start (object 0 ft/0 speed) → START → A (first airborne point) → … → carrier landing (0/0) → END.
- Multi-carrier landing choice is undecoded: single carrier is supported; ask for a sample otherwise; once the landing
  carrier is known use its initial X/Z.

## 12.5 Carrier and ship objects

Carrier object (Cold War sample, single Kitty Hawk + F-14 wing):

```text
obj
	type KITT.NT
	pos <carrierX> 0 <carrierZ>
	angle 0 0 0
	nationality3 <country>
	flags <flags>
	speed 0
	alias <alias>
	skill 3
	react <reaction>
	searchDist 25
	.
```

F-14 deck start: near the carrier at 0 ft / speed 0; the four-ship sample is a template for deck offsets and wing
settings (`wng 3 0 512 0`). No carrier-parent field exists; do not claim one.

**Every ship must move:** at least one forward waypoint (no stationary ships unless the user asks for an anchored
vessel). For heading `H` and `D` NM: `x = start_x + D·6076.12·sin H`, `z = start_z + D·6076.12·cos H`. Ship waypoint:

```text
w_flags $4
w_goal 1
w_pos2 1 0 <x> 0 <z>
w_speed <ship_fps>
w_wng 1 0 256 0
```

`w_speed 50` ≈ 30 kt (default carrier-group speed). **Task group:** same heading, speed and displacement vector for
corresponding waypoints, keeping initial offsets (never converge on one point).

## 12.6 Split carriers: hull `*.NT` + Tower `*.OT` (v21, JKP profile)

Five JKP carriers are hull-only; always add their Tower object(s). Offsets `(dX0, dZ0)` = Tower − hull at heading 0
(`CV.M`):

| Hull | Class | Tower(s) | `(dX0, dZ0)` |
|---|---|---|---|
| `ESSE.NT` | Essex CV; **always use for a generic WWII wooden-deck carrier** | `ESSET.OT` | `(+153, +68)` |
| `CDEG.NT` | Charles de Gaulle CVN | `CDEGT.OT` | `(+298, -325)` |
| `INVN.NT` | Invincible CVSA | `INVNT.OT` | `(+46, -77)` |
| `ELIZ.NT` | Queen Elizabeth CVF | `ELIZT.OT` **×2** | `(+330, +571)` and `(+298, -238)` |
| `KUZN.NT` | Admiral Kuznetsov CV | `KUZNT.OT` | `(+202, -160)` |

For hull `pos cX cY cZ`, `angle H 0 0` (H in degrees, use radians in code):

```text
dX = dX0*cos(H) + dZ0*sin(H)
dZ = -dX0*sin(H) + dZ0*cos(H)
towerX = cX + round(dX);  towerY = cY;  towerZ = cZ + round(dZ)
```

(consistent with heading 0 → +Z, 90 → +X; at H = 0 it reproduces `CV.M`). Tower template:

```text
obj
	type <Tower.OT>
	pos <towerX> <cY> <towerZ>
	angle <H> 0 0
	nationality3 <same as carrier>
	flags $4011
	speed 0
	alias <unique>
	.
```

No `skill`, `react`, `searchDist`, controller or waypoint group: correct initial placement attaches it and it follows
the carrier. The hull keeps its normal ship fields and route (§12.5). Queen Elizabeth always has two separate Towers.
Do not substitute another class for the generic WWII carrier role unless the user names one and it exists. Tower
assembly does not change deck start, recovery or ship movement.

---

# 13. Bombing

Classify the profile from the user's described attack method (or a working sample): **high-altitude/level** (§13.1–
13.2) or **dive** (§13.6). Carrying bombs alone proves neither.

## 13.1 High-altitude bombing: altitude-discipline corridor (v18)

Applies to strategic/high-altitude bombers (e.g. B-52/B-2 when in the catalog) or any aircraft told to level-bomb,
hold bombing altitude or stay out of ground-fire envelopes.

- Takeoff and friendly/neutral transit: normal `far + loose`.
- From the **enemy-territory entry/turn-in waypoint** (including a turn just before the hostile boundary whose purpose
  is to line up for entry) through **every** waypoint inside enemy territory (ingress turns, alignment, attacks, turns
  between attacks, post-release turns, hostile egress): `control tight (3)` + `spacing near (512)`, e.g. Echelon/level
  `w_wng 3 0 512 0`. Formation/stacking stay selectable.
- Never relax between attacks while another is pending. Return to `far + loose` only after the final attack **and**
  exit from enemy territory; a later re-entry switches back at its entry point.
- Keep the high altitude; never lower a point to make a dive. (A `far + loose` point inside the corridor lets the
  bomber dive into the defences.) A user's explicitly different attack profile wins.

## 13.2 Attack point lead

The attack waypoint is placed **before** the target on the inbound track, never on top of or behind it. Lead grows
with bombing altitude. Without a user/tested value, plan with `t ≈ sqrt(2·alt_ft / 32.174)`, `lead_ft ≈ speed_fps · t`
(plus a modest margin). This is a planning heuristic, not a game field.

## 13.3 Attack-reaction corridor (v19)

From the **first bombing Attack waypoint**, every visible waypoint still in the active bombing sequence uses
`w_react $ffff $0 $0`: the Attack, post-release turns, turns between passes, realignment/stabilisation, `w_goal 1`
repositioning points, later Attacks, and target-area egress still in the attack cycle. Names like Turn, Realign,
Ingress, Egress or `w_goal 1` never reset it; never write `w_react $0 $ffff $0` (All Defend) there while a pass is
pending. A later point that sets up another pass proves the sequence is still active. End only when **all three**
hold: final planned pass done, bomber actually left the target/hostile area, no attack pending. This corridor is
separate from §13.1 (which starts at the entry point). Object-level `react` follows the task-level policy.

## 13.4 No aircraft as bomb targets (v18)

A `*.PT` aircraft, even parked at 0 ft, is never the object- or waypoint-level target of a bombing task. For an
airfield strike meant to destroy parked aircraft: treat it as an area/installation strike, use `w_react $ffff $0 $0`
(and object `react $ffff $0 $0` when the whole task should attack all classes), and target facilities so parked
aircraft are hit by the bombing. With mixed loads this applies to the bombing waypoints only; air-to-air weapons may
still engage aircraft through separate reactions/assignments.

## 13.5 Per-waypoint ground targets and `.MM` targets (v20)

- Each waypoint of the active bombing sequence (same scope as §13.3, including turns, realignment, repositioning and
  egress) may carry its own valid **non-aircraft ground** target in `w_preferredTargetId2` (alias low 16 bits).
- Airfield targets: control towers, hangars, shelters, fuel/ammo/supply storage, bunkers, radar/command sites,
  runway structures, air defences and other airport ground objects.
- Build a pool from generated `.M` objects **and** confirmed objects of the matching `.MM`; prefer a different target
  at each successive waypoint; reuse only if the pool is exhausted, geometry demands it, or the user asks.
- `.MM` targets are used by alias directly (no duplicate in `.M`). Before use, confirm from that `.MM`: exact alias,
  type, `pos`, its relation to the requested target area, and the file's `map <name>.T2`. Never invent an alias or
  take one from another map.
- A preferred target never replaces the `$ffff` reaction corridor.
- Bombers sharing one route may share one ordered target sequence unless separate allocations are requested.

## 13.6 Dive bombing (v23, v24)

- Every visible waypoint of the **active free-maneuver dive** (terminal attack point, attack-area turns, realignment,
  any point still in the dive sequence) uses `far + loose` (`w_wng 1 <formation> 2048 <stacking>`), so the aircraft can
  break formation and dive. The §13.1 `near + tight` corridor does not apply to dive bombing.
- Exception (v24): a distinct **pre-dive staging/formation point** that has not yet released the wing may use
  `near + tight`.
- Reactions (§13.3), targets (§13.5) and Assignment/Target/Duration (§12.3) are unchanged by these spacing rules.

**Near-vertical dive geometry (`divetest.M`, Green F8F wing aliases `-3…-7` vs Iowa `IOWAO.NT` alias `-2`):**

```text
target T  = (597957,     0, 631771)
setup S   = (600794, 30000, 621098)   |S-T| horiz ~11043.6 ft   w_goal 1, no target, w_wng 3 0 512 0
attack A  = (596545, 30000, 628900)   |A-T| horiz  ~3199.4 ft   w_wng 1 0 2048 0
A->T descent ~83.9 deg below horizontal (~6.1 deg off vertical)
A: w_goal 16, w_react $2000 $8000 $0, w_searchDist 0, w_preferredTargetId2 $fffe (= alias -2)
```

When an almost-vertical dive is requested:

- Keep S and A at the **same** dive-entry altitude `Ay`; S far from the target, A very close horizontally. Never put A
  on the target and never lower A to fake a dive. S, A and T need not be collinear; choose azimuths for ingress,
  terrain and defences.
- Without better data: terminal stand-off `D ≈ 0.10665 · (Ay − Ty)`; setup stand-off `≈ 0.3681 · (Ay − Ty)`
  (planning heuristics from one sample; user values or a newer sample win).
- Copy the Anti-ship tuple only for a matching ship attack; ground/airfield dives use §13.3–13.5. Encode the real
  target alias (`$fffe` only when the alias is `-2`).

---

# 14. Ambient units (default 5–10)

Unless the user asks for a minimal/exact order of battle or no ambience, add about 5–10 auxiliary units **before**
alias allocation. Each: `skill 3`, Not affected, never a hidden objective, valid catalog asset, plausible side and
nationality, genuinely mobile with at least one visible movement waypoint (if no verified movement pattern exists,
pick another unit; no static decoration). Keep them off the player's takeoff/landing path and main target track and out of the main fight unless their role
is ambience support (e.g. defensive helicopter patrols);
same-group units keep offsets and common speed.

- Carrier/naval: 2–4 extra carrier aircraft on/near the deck via a verified deck-start template, 1–2 helicopters
  near the task group (e.g. `SH3A.PT`, `SH60.PT` if in the catalog), extra escorts for a larger task group. Ships
  follow §12.5. Moving deck aircraft need a verified takeoff/air route; no invented deck taxi.
- Airfield: find the airfield `STRIP*.OT` / `DTSTRP.OT` in the `.MM`, use its `pos`/`angle`, inspect nearby objects;
  some aircraft airborne on short local routes (parked starts only with a verified ground-start pattern), ground
  vehicles such as `TRUCK.NT`, `TANKER.NT`, `HUMVEE.NT` if available, helicopters. The user wants both ground and air
  activity, but ground-vehicle routes and airport takeoff are undecoded: without a working template, fill the count
  with verified aircraft/helicopter/naval patterns instead.

---

# 15. Legacy Cuba anchors and defaults

Use only when no matching `CUB.MM.txt` location applies:

```text
airborne Caribbean anchor (E-2C test, south of Cuba)  X 1277450  Y 10000  Z 802580
Kitty Hawk anchor (Cold War mission)                  X 1538837  Y 0      Z 748643
```

Other maps: never assume the Cuba origin; use their `.MM`, a working mission or a raw anchor, else ask.

Defaults when the user omits details (never against explicit intent; `.MM` data beats generic defaults): Cuba header
of §4.3; unit skill 3; enemies hidden (`$4417`), friends shown; success Not affected (player wing always); search 25
(or 0 for "any distance"); fighter reactions from verified presets; ambient units; moving ships with common task-group
course/speed; split carriers with Towers; carrier deck start without a launch point and recovery at the carrier's
initial X/Z; spacing far, control loose; fuel/hardpoints per §8; paired `.MT` with the three briefing lines; v25
filename. Cuba Kitty Hawk mission: use the `coldwar(2).M` anchor/pattern; do not create multiple landing carriers.

---

# 16. `.MT` briefing file

Four sections, structure from `~B08.MT` / `~E39.MT`:

```text
.section 1
<mission-id>  (<mission-basename>)
<MISSION TITLE>  (<map/region label>)
<Mission type/source label>
.section 2
.center .underline .header
<MISSION TITLE>
..underline .left .body

<BASE / OPERATING AREA>
DATE :  <date>
LOCAL  TIME :  <HHMM>
WEATHER :  <weather>

.underline .header
SITUATION
..underline .body
<situation>

.underline .header
MISSION OBJECTIVE
..underline .body
<objective>

.underline .header
THREAT SUPPRESSION DATA
..underline .body
GROUND  OPPOSITION :  <threats or Unknown>

AIR  OPPOSITION :  <threats or Unknown>
.section 3
.center .underline .header
DEBRIEF
..underline .left .body

<BASE / OPERATING AREA>
DATE :  <date>
MISSION :  <mission title>
RESOLUTION :  Success

<short success debrief>
.section 4
.center .underline .header
DEBRIEF
..underline .left .body

<BASE / OPERATING AREA>
DATE :  <date>
MISSION :  <mission title>
RESOLUTION :  Failure

<short failure debrief>
```

Optional block in section 2 (from `~B08.MT`), only when such support exists:

```text
.underline .header
ELECTRONIC INTELLIGENCE
..underline .body
SUPPORT  AIRCRAFT  :  <support assets>
```

- `<mission-basename>` = the v25 basename (legacy `~` names only when preserving old samples).
- Without a user campaign ID/source/region label, write plain descriptive ASCII; sample IDs like `AB08`, `AE39`,
  `ATFGOLD` are presentation text, not decoded fields.
- Keep the `.MT` in sync with the `.M`: title/basename, area, date/time/weather, player role and objective, friendly
  support and enemy threats actually present, and success/failure text matching the actual success flags (never claim
  a Not-affected condition). Narrative extras only as clearly framed background. `You failed to complete your
  objectives.` is a verified generic failure line.

---

# 17. Not decoded (never invent)

- flag bits beyond `0x20`, `0x80`, `0x200`, `0x400` on the `$4017` base (and Tower `$4011`); nonzero start delay
- `w_goal` codes other than `0, 1, 4, 8, 16, 34`
- names of the low raw reaction bits inside `$ffff`
- object-level `wng` field 1
- `w_flags $4` meaning; `w_pos2` mode fields beyond tested patterns; nonzero `w_next`
- controller values other than `$80`
- multi-carrier landing selection
- coordinate origins of non-Cuba maps without `.MM` or reference mission
- `view` zoom; `layer` trailing value; full `clouds` list; wind units/direction
- `fuel`/`hardpoint` on anything other than `*.PT`
- ground-vehicle movement; land-airfield takeoff/landing routing (only its 0 ft / 0 speed is fixed)
- `.MM` `tmap`/`tdic`; non-bombing cross-file Target/Protect to `.MM` aliases

If a request depends on these: express it with a confirmed mechanism, else ask for one single-variable Mission Creator
differential; never fill in a plausible number.

---

# 18. Construction procedure

1. **Parse the scenario:** map, time/weather, player country/aircraft, friends/enemies, counts, wings, positions,
   altitude, heading, speed, routes/labels, Target/Protect, reactions, search ranges, success conditions, carrier deck
   start / visible launch request / landing carrier, split carriers, formation preferences, bombing profile (dive vs
   level; altitude and inbound speed), bomb-target intent (parked aircraft → area strike), bombing sequence markers
   (first Attack, intermediate turns, final pass, hostile-area exit), fuel/hardpoint requests, ambience opt-out,
   briefing title/area/date and `.MT` content.
2. **Items and map:** decode the items file, select the profile, build effective catalogs (§2) before any asset
   lookup. Verify and index the `.MM` (§3). Resolve every asset in the effective catalog; never fall back to an
   overwritten Default meaning; never fabricate files or locations.
3. **Add** ambient units (§14) and split-carrier Towers (§12.6), then **choose anchors** (§3 priority) and compute
   relative positions (§6), keeping `.MM` airfield angles where orientation matters.
4. **Aliases** `-1, -2, …`; then resolve Target/Protect (`.MM` aliases only for bombing targets).
5. **sides4** and `nationality3`; skills 3 everywhere.
6. **Flags** per §7.3 (player wing Not affected, enemies hidden, Towers `$4011`).
7. **Direct assignments** per §10; drop any bomb Target on a `*.PT` and use the area-strike behaviour instead.
8. **Reactions** from presets or confirmed class bits (§9); bombing corridor (§13.3).
9. **Formation** per §11.3 and §13; **fuel/hardpoints** per §8.
10. **Routes:** START, visible points, END, `w_for`; deck start / takeoff / recovery per §12.4; every ship moves with
    task-group sync; ambient airborne units get routes; bombing lead, targets and reaction corridor per §13; no
    ground/airport movement without a working encoding.
11. **Basename** (§4.4) and the `.MT` (§16).
12. **Serialise** (§19) and run the checklist (§20).

Common requests:

- *Fighter intercepts aircraft X:* create/alias the target, fighter with Target `preferredTargetId2`, verified
  fighter preset; route optional.
- *Fighter escorts/protects X:* object-level Protect; no route needed. Do not imitate the old Cold War route-only
  pseudo-escort.
- *Bombers fly to B then attack a carrier:* earlier points `w_goal 1`; B = Anti-ship preset, carrier alias16,
  `w_goal 16` (or 4/8 if attacked/damaged chosen). Keep the historical Cold War tuple only when reproducing it.
- *High-altitude bomber hits a ground target:* §13.1–13.3 (+§13.5).
- *Bombers must destroy parked aircraft:* §13.4–13.5.
- *Four F-14s launch from one Kitty Hawk and return:* `KITT.NT`; four F-14s at deck 0 ft/0 speed; one `controller $80`;
  wing ids/members; `npcFlags 2` on AI wingmen; `wng 3 0 512 0`; identical routes; A = first airborne point; final
  `w_goal 34` landing at 0/0 at the carrier's initial X/Z.
- *X must survive and Y be destroyed:* X `base|0x20`, Y `base|0x80`, others Not affected; player wing always Not
  affected; enemies still get `0x400` unless shown.

---

# 19. Serializer

Build the `.M` as bytes (an editor may destroy control characters), the `.MT` separately:

```python
SOH, CRLF, NUL = b"\x01", b"\r\n", b"\x00"
name_field = b"\tname " + SOH + b"Player" + SOH + CRLF
mission_bytes += NUL                       # .M only
mt_bytes = mt_text.replace("\n", "\r\n").encode("ascii")   # .MT: no NUL
```

Deliver real downloadable `.M` and `.MT` files (not only a code block). A preview may show SOH as quotes; the file must
contain `0x01`. Do not strip the trailing space of empty hardpoint lines.

Minimal templates:

```text
obj                              (player F-14, no target)
	type F14.PT
	pos <X> <ALT> <Z>
	angle <HDG> 0 0
	nationality3 <NAT>
	flags $4017
	speed <FPS>
	alias <ALIAS>
	controller $80
	name <SOH>Player<SOH>
	skill 3
	react $c000 $3fff $0
	searchDist 0
	.
```

AI fighter targeting alias `-3`: same without `controller`/`name`, plus `preferredTargetId2 $fffd` after `react`.
Protect alias `-1`: `preferredTargetId2 $4000ffff`. Passive aircraft: `react $0 $ffff $0`.

---

# 20. Validation checklist

**Files:** shared 7-char basename `^[A-Z0-9]{6}[1-9A-Z]$`, revision `1` first then +1 per modification, no `0`, no
rollover after `Z`; `.M` CRLF, SOH delimiters, final `0x00`, ASCII only; `.MT` same basename, CRLF, no SOH, ends with
CRLF not NUL.

**Items/map:** encoding decoded (UTF-16 ok); profile from content; Default-only uses Default rows only and nothing
remembered; JKP profile uses JKP rows on duplicates and no overwritten Default meaning; split-carrier exception limited
to the five pairs; `.MM` internal map matches; names resolved from `.MM`; no map objects copied; no alias collisions;
no `tmap`/`tdic`.

**Header:** `textFormat` then `brief`, `briefmap`, `armplane` before `map`; map and layer exist; `sides4` 64 entries,
last four `$0`.

**`.MT`:** sections 1–4 in order; section 2 has title, situation, objective, threats; 3 Success, 4 Failure; content
matches the `.M` (objective, support, threats, success flags); no visibility directive; no fake mechanical IDs.

**Objects:** types exist; aliases unique; `nationality3` correct; exactly one `controller $80`; only known flag
compositions; enemies `0x400` unless shown, friends not hidden by type; success bits as requested; player wing both
bits clear; all `skill 3` unless requested; fuel/hardpoints only on `*.PT`, fuel explicit or justified; stations only
4–8; items in catalog (`*.JT`, listed `*.GAS`); empty stations are `hardpoint N 0 ` with the space in the raw bytes and
no item; multi-round quantities preserved, one item type per station; no realism rule blocked a valid request; auto
loadouts match the role.

**Formation:** every visible point has a deliberate `w_wng` in `<control> <formation> <spacing> <stacking>` with
verified codes; spacing far and control loose unless requested or a bombing/dive exception applies; `near` never
random; high-altitude corridor `near + tight` from entry/turn-in through hostile egress, continuous between pending
attacks, `far + loose` only after final attack and exit, re-entry switches back; attack points before targets with
lead growing with altitude; dive points `far + loose` except a pre-dive staging point; profile classified by attack
method; START/END `0 0 0 0`; no unmapped codes.

**Dive geometry (if requested):** staging + terminal point at the same altitude, terminal close to but not on the
target, not lowered; heuristics only as heuristics; Anti-ship tuple only for ship attacks; real alias encoded.

**Assignment:** Assignment/Target/Duration model; exact tuples for tested combinations; `w_goal 1/4/8/16` meanings;
presets for named Assignments; `$0` for no target, real alias otherwise (`$fff7` only for alias `-9`); targeted
Hi/Lo-sweep rows not normalised; old `w_goal` labels unused; custom class reactions allowed.

**Targets:** low 16 bits decode to the intended alias; Protect bit only for Protect; no nonexistent alias; no bomb task
targets a `*.PT`; `.MM` bomb targets confirmed from the matching map; distinct successive targets when possible; targets
never remove the `$ffff` corridor.

**Reactions:** presets or confirmed masks only; bombing corridor from first Attack through every pending-pass turn and
reposition point, never All Defend while a pass is pending, ends only after final pass + area exit + nothing pending;
`1.M` tuples exact when reproduced; low bits unnamed.

**Waypoints:** `waypoint2 N = visible + 2`; indices `0…N-1`; START `$1`, END `$2`; air points `0 0`; no auto launch
point on carrier deck start and A not forced to 0/0; visible takeoff and all landings at 0 ft / speed 0; carrier
landing at the carrier's initial X/Z, not projected; no invented land-airfield fields; `w_for` matches; only decoded
`w_goal`; every ship moves; task groups share course/speed and keep offsets; split carriers have Towers (Queen
Elizabeth two) with copied angle/nationality, `$4011`, speed 0, no route; ambient units move.

**Geometry:** feet altitude; 6076.12 ft/NM; headings match direction; plausible ft/s; `.MM` anchors used when available.

---

# 21. Output behaviour

1. Restate the interpreted mission only if needed to resolve ambiguity.
2. If everything is representable, generate the `.M` and `.MT` immediately (choose the basename first).
3. If one critical feature is undecoded, ask one focused question or request a differential; no broad questions.
4. Validate both files and their consistency.
5. Return both files plus a concise summary: `.MT` title/objective and debrief coverage; basename stem and revision
   (first or incremented); objects/aliases; success conditions; briefing-map visibility overrides; Target/Protect;
   waypoint assignments; custom class reactions and the baseline kept for undecoded bits; takeoff/landing handling
   (deck start → A, recovery at initial carrier X/Z, 0/0); split carriers (hull, Tower types, heading, offsets, rotated
   positions, no Tower route, both Queen Elizabeth Towers); formation choices including the bombing corridor
   (switch point, coverage, return) and attack lead; bomb-target handling and reaction corridor; fuel/hardpoint
   handling (explicit or automatic, eligible type, stations 4–8); ambient units; `.MM` anchors used; items profile and
   any JKP override that mattered; defaults used.
6. Disclose any extrapolated (not directly confirmed) field. Skip reverse-engineering commentary unless asked.

---

# 22. Maintaining this skill

Classify new findings as **CONFIRMED** (isolated single-variable differential or several independent direct
examples), **HIGH CONFIDENCE** (strong structural cross-validation without a clean differential) or **UNKNOWN** (must
not be invented). Update with small Mission Creator tests where exactly one setting changes; extend only the missing
lookup values. Keep the file name unchanged and record the new version in the header and the rule-origin line.
