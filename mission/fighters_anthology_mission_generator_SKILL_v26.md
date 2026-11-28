---
name: fighters-anthology-mission-generator
description: Generate syntactically complete Jane's Fighters Anthology Mission Creator .M mission files and a same-basename .MT mission briefing/debriefing file from a user's natural-language scenario, automatically selecting the effective asset catalog from the user-supplied FA_items variant (Default only or Default + JKPFA_53b), using the companion map .MM.txt upload (logical .MM content) and verified reverse-engineered .M/.MT samples as authority. Apply installed-library JKPFA_53b-over-Default precedence for duplicate PT/JT/NT/OT filenames, expert-skill defaults, moving naval/task-group behavior, map-aware placement, ambient dynamic-unit enrichment, v15 mission-aware fuel/loadout policy (eligible *.PT aircraft may receive fuel automatically as mission needs justify; hardpoint overrides are restricted to 4-5 fuselage and 6-8 wing stations, with hardpoint 9 prohibited), while retaining the v14 carrier-recovery initial-position policy, full v13 carrier-deck-start navigation policy, v12 takeoff/landing altitude/speed policy, waypoint formation/spacing/stacking/control mappings with Loose control by default, required briefing-enable header lines, and confirmed briefing-map visibility flags with hostile mission objects hidden from the briefing map by default, while preserving unknown fields conservatively, plus the historical v16 output-filename evidence (1-8 uppercase ASCII alphanumeric characters, extension excluded), superseded for newly generated output by the v25 exactly-seven-character revisioned basename policy, the v17 waypoint-spacing generation policy that defaults every visible navigation point to far spacing and uses near only when the user explicitly requests near, and the v18 bombing policy that forces near spacing + tight control throughout the hostile-territory portion of a high-altitude bombing route (beginning at the enemy-territory entry/turn-in waypoint and continuing through all attacks and hostile-territory egress until the bomber has exited enemy territory with no further attack pending), places bombing attack waypoints before the ground target with altitude-dependent lead distance, and prevents bomb loads from using aircraft objects as direct bombing targets by using an all-object-type attack reaction for airfield/ground-area strikes, plus the v19 bombing attack-reaction corridor that keeps `w_react $ffff $0 $0` continuously from the first bombing Attack waypoint through every Turn, post-attack turn, between-pass turn, realignment/normal-flight waypoint, and subsequent Attack that remains part of the active bombing sequence, relaxing it only after the final planned bombing pass is complete and the bomber has actually left the active target/hostile area with no further attack pending, plus the v20 bombing waypoint target-assignment and .MM map-target override that permits confirmed matching-map .MM ground-object aliases to be used directly by bombing `preferredTargetId2` / `w_preferredTargetId2`, distributes distinct valid ground targets across active bombing-sequence waypoints when available, and preserves the v19 `w_react $ffff $0 $0` corridor independently of preferred-target assignment, plus the v21 JKPFA_53b split-carrier hull/Tower assembly policy that pairs the five confirmed hull-only carrier `*.NT` objects with their required `*.OT` Tower object(s), rotates the verified CV.M local Tower offsets by the carrier heading, and emits the Tower(s) at the correct initial position/orientation so they attach to and follow the moving carrier, plus the v22 waypoint advanced-behavior policy that treats each visible navigation point as three user-facing settings—Assignment, Target, and Duration—using the verified `assignment.M` tuples, decodes `w_goal 1/4/8/16` as until-waypoint-reached / until-target-attacked / until-target-damaged / until-target-destroyed, and applies verified assignment-specific `w_react` / `w_searchDist` plus target alias encoding without discarding any earlier mission-generation behavior, plus the v23 dive-bombing waypoint-behavior override that requires `spacing = far` and `control = loose` on visible waypoints belonging to a true dive-bombing profile (not high-altitude level bombing), so the dive bomber remains free to maneuver and execute the dive; this v23 rule supersedes the v18 `near + tight` altitude-discipline behavior only for dive-bombing profiles and leaves bombing reaction/target-assignment rules otherwise unchanged. v24 preserves all v23 functionality and adds the verified `divetest.M` near-vertical dive geometry: a same-altitude pre-dive staging waypoint may hold `near + tight`, followed by a same-altitude terminal attack waypoint placed very close horizontally to the selected target and using `far + loose`; the exact Green-wing/Iowa sample yields an approximately 83.9-degree geometric descent line, and its target-relative geometry may be scaled conservatively as a planning heuristic when an almost-vertical dive is explicitly requested. v25 preserves all v24 functionality, supersedes the active v16 output-name rule with an exactly seven-character revisioned basename (six-character uppercase ASCII-alphanumeric mission stem plus one revision symbol sequenced 1-9 then A-Z, shared by .M/.MT), and uses the verified `1.M` differential to confirm individual waypoint reaction masks for SAM, AAA, Tank, Vehicle, Structure, and Other plus exact A-F one-class-Defend/all-else-Attack waypoint tuples; v25 also clarifies that `w_react` is the per-class reaction matrix and that v22 named Assignment tuples remain verified presets rather than a prohibition on custom per-class reaction tuning. v26 preserves every v25 and earlier feature, and confirms empty editable hardpoints using the exact trailing-space-sensitive `hardpoint <station> 0 ` syntax (no item filename), as well as positive multi-round quantities on one hardpoint using `hardpoint <station> <quantity> <item_file>`.
---

# Fighters Anthology `.M` Mission Generator Skill

**Version: v26**


## 1. Purpose

Use this skill to turn a user's mission description into a complete Jane's **Fighters Anthology** Mission Creator mission file (`.M`) **and a same-basename mission text/briefing file (`.MT`)**.

The priority order is:

1. Produce a `.M` file the game/Mission Creator can parse, plus a matching `.MT` briefing/debriefing file.
2. Preserve the user's intended units, sides, routes, target/protect relationships, reactions, and mission-success conditions.
3. Use only asset filenames and mission encodings supported by the supplied references or verified mission samples.
4. Never silently guess an unknown bitfield or assignment code.
5. When an exact requested feature is not yet decoded, either use a verified equivalent mechanism or clearly ask for a differential sample before generating that feature.

This skill is based on verified samples including `coldwar(2).M`, `a.M`, `b.M`, `c.M`, `d.M`, `e.M`, the v22 waypoint-behavior differential `assignment.M`, the v24 near-vertical dive sample `divetest.M`, the v25 waypoint-reaction differential `1.M`, their Mission Creator screenshots where available, the user-supplied `FA_items` reference variant, and the observed structure of a companion map file such as `CUB.MM`. The user is expected to provide the companion map as `<MAP>.MM.txt` for the selected map whenever map-aware placement is needed. The added `.txt` suffix is only the upload/storage filename convention; parse the file contents as the original Fighters Anthology `.MM` format.

## Generation-policy overrides

### v26 empty hardpoints and multiple weapons per hardpoint — REQUIRED

v26 **preserves all v25 and earlier functionality**, including the v25 revisioned seven-character `.M`/`.MT` filenames and reaction-mask semantics. It changes only the generation, preservation, and validation of aircraft hardpoint override lines. All prior v15 hardpoint eligibility and station restrictions remain in force: only `*.PT` aircraft objects, with editable stations `4`, `5`, `6`, `7`, `8`; never emit reserved stations `1`–`3` or prohibited station `9`.

**Empty/unequipped hardpoint:** Serialize the station number and the numeric quantity `0`, **followed by exactly one mandatory ASCII space (`U+0020`) before the newline**, and no item filename. The space after `0` is syntactically significant; stripping/trimming it can cause a mission error. This is an explicit empty override, not the same thing as omitting the line. When a user explicitly requests an empty editable station, output the empty override rather than silently dropping it.

**Equipped hardpoint and multiple rounds:** Keep the inherited three-token syntax `hardpoint <station> <quantity> <item_file>` with a **positive integer quantity**. Quantities above `1` represent multiple weapons/items on that same hardpoint; do not require separate hardpoint lines or stations for each round. Use a confirmed eligible catalog token, normally `*.JT` for weapons/equipment or verified `*.GAS` for external tanks. No aircraft-specific pylon capacity or compatibility limit may be invented. This rule does not establish multiple different item types on the same station; absent a verified example, use one type and its quantity per station.

The following working-pattern example requests empty stations 4, 6, 7 and **four** `AIM9D.JT` weapons on station 5:

```text
hardpoint 4 0 
hardpoint 5 4 AIM9D.JT
hardpoint 6 0 
hardpoint 7 0 
```

**Byte-exact output requirements:** The three empty lines above each end in a literal ASCII space immediately before LF or CRLF; do not delete it during output cleanup, file serialization, rendering, Markdown processing, or validation. The string representations (where `\x20` designates the final ASCII space) are `"hardpoint 4 0\x20"`, `"hardpoint 6 0\x20"`, and `"hardpoint 7 0\x20"`. Do not emit an item token, `null`, a hyphen, quotation marks, or a comment after an empty override. Do not turn a user-specified `0` into a positive quantity, or combine it with an equipment line on the same station.

**Validation:** For each emitted hardpoint line, verify the station belongs to `{4,5,6,7,8}` and the parent object's type ends in `*.PT`. If quantity is `0`, verify that there is no item token and that the raw line ends with `0` plus at least the required one literal ASCII space before its line ending (prefer exactly one). If quantity is positive, verify one valid item token exists and the quantity is preserved exactly, including values above `1`. Perform validation on **actual file bytes**, not only on a trimmed or Markdown-rendered version. Treat malformed empty lines such as `hardpoint 4 0` (missing final space) as invalid. When no explicit empty override is requested, ordinary omission of an unspecified station remains permissible under inherited automatic-loadout policy.

This rule supersedes older blanket instructions that hardpoint `quantity` must always be positive; that requirement now applies **only when an item is mounted**. All unrelated naming, fuel, carrier, route, briefing, map, targeting, formation, mission-object, and success-condition behaviors remain unchanged.

### v25 revisioned output filenames + `1.M` waypoint reaction differential override

The v25 policy preserves **all v24 and earlier functionality** except where this section explicitly supersedes an older interpretation. v25 adds two generation rules: an exactly seven-character revisioned mission basename, and a verified per-target-class waypoint reaction model from the supplied working `1.M` sample and Mission Creator screenshot.

#### A. v25 seven-character revisioned `.M` / `.MT` filenames — REQUIRED

For every newly generated mission pair, the `.M` and `.MT` files must use the **same exactly seven-character basename**. Treat the basename as:

```text
<STEM6><REV1>
```

where:

- `<STEM6>` is exactly six uppercase ASCII alphanumeric characters (`A`-`Z`, `0`-`9`) chosen/normalized to identify the mission.
- `<REV1>` is exactly one revision symbol from this ordered sequence:

```text
1 2 3 4 5 6 7 8 9 A B C ... X Y Z
```

- The first generation of a mission uses revision `1`.
- When the user gives a modification/revision instruction for that same mission, keep the same six-character stem and advance the final revision symbol by one step: `1 -> 2 -> ... -> 9 -> A -> B -> ... -> Z`.
- `0` is **not** a v25 revision symbol.
- Example: first generation `TOPGUN1.M` + `TOPGUN1.MT`; after one user-requested modification, generate `TOPGUN2.M` + `TOPGUN2.MT`; after revision `9`, the next revision is `A`.
- When revising an uploaded or previously generated v25 mission whose basename already matches the seven-character scheme, preserve characters 1-6 and increment character 7.
- If the user supplies a mission name that is not already a valid six-character stem, normalize/abbreviate it deterministically to **exactly six uppercase ASCII alphanumeric characters** while preserving recognizability where practical; then append the revision symbol.
- Revision `Z` is the last representable value in the one-character v25 sequence. Do **not** silently roll over to `0`, two characters, or a changed stem. If another revision is requested after `Z`, ask the user to choose/approve a new six-character stem or another explicit naming scheme.
- The active v25 basename validation pattern is therefore:

```text
^[A-Z0-9]{6}[1-9A-Z]$
```

This v25 rule **supersedes the v16 1-8-character filename rule for newly generated output**. The older v16 rule remains useful only as historical evidence for legacy files and older skill versions.

#### B. v25 `1.M` A-F waypoint reaction tuples — CONFIRMED

The supplied `1.M` contains one aircraft waypoint group with START, six visible navigation points A-F, and END. The six visible waypoints hold the same basic no-target / until-waypoint-reached structure (`w_goal 1`, `w_preferredTargetId2 $0`) and use `w_searchDist 10`; their deliberate difference is the target-class reaction matrix in `w_react`.

The exact verified tuples are:

| Navigation point | Defend class | All other raw reaction classes | Exact `w_react` |
|---|---|---|---|
| A | SAM | Attack | `$efff $1000 $0` |
| B | AAA | Attack | `$f7ff $800 $0` |
| C | Tank | Attack | `$fbff $400 $0` |
| D | Vehicle | Attack | `$fdff $200 $0` |
| E | Structure | Attack | `$feff $100 $0` |
| F | Other | Attack | `$ffbf $40 $0` |

Because each row starts from an all-Attack `$ffff` baseline and moves exactly one tested class bit from Attack to Defend, `1.M` confirms these individual class masks:

```text
SAM       = $1000
AAA       = $0800
Tank      = $0400
Vehicle   = $0200
Structure = $0100
Other     = $0040
```

Together with the already-confirmed masks, the currently verified visible Mission Creator target classes are:

```text
Fighter   = $8000
Bomber    = $4000
Ship      = $2000
SAM       = $1000
AAA       = $0800
Tank      = $0400
Vehicle   = $0200
Structure = $0100
Other     = $0040
```

Do **not** assign semantic names to the remaining low raw bits merely because `$ffff` includes them. When constructing a custom reaction from a verified broad baseline such as all-Attack, move only the confirmed class bits requested by the user and leave all still-undecoded raw bits in their verified baseline word.

These reaction-mask semantics apply to `react` and `w_react` wherever those fields are valid: aircraft, ships, vehicles, tanks, AAA, SAM, and other mission objects may use the same target-class Attack / Defend / Evade / Ignore bit semantics. This does **not** by itself decode movement-waypoint syntax for an object type whose movement routing is otherwise still unknown. When planning navigation points, tune the reaction matrix to the unit's mission role instead of blindly copying the A-F test pattern.

#### C. v25 clarification of v22 Assignment / Target / Duration wording

`1.M` confirms that `w_react` is the **per-target-class reaction matrix**. The v22 `assignment.M` rows remain valid, exact working tuples for the named Mission Creator Assignment choices that were tested, and `w_searchDist` remains an independently serialized search-distance field. However, v25 narrows the older wording that could be read as saying a named Assignment is *nothing more than* `w_react + w_searchDist`.

The supplied Mission Creator screenshot for `1.M` shows a Normal Flight / no-assigned-target / until-waypoint-reached waypoint while its class actions are customized (SAM Defend and the other classes Attack). Therefore:

- keep the v22 Duration mapping in `w_goal` and Target mapping in `w_preferredTargetId2`;
- keep every exact `assignment.M` full tuple as authoritative when reproducing that tested named Assignment/Target/Duration combination;
- also allow explicit per-class reaction customization through the now-confirmed `w_react` masks without falsely relabeling the reaction matrix itself as the sole Assignment selector;
- when the user asks for a custom class reaction at a waypoint, change the relevant confirmed reaction bits and preserve the waypoint's independently requested/verified Target, Duration, search distance, formation, and other fields unless a higher-authority working sample requires a coupled change.

This v25 clarification does not invalidate the working v22 tuples; it prevents overgeneralizing those tuples into a one-to-one semantic identity between the visible Assignment label and the raw `w_react` matrix.

### v24 near-vertical dive-bombing waypoint geometry: `divetest.M` Green-wing / Iowa override

The v24 policy preserves **all v23 and earlier functionality** and adds one verified navigation-point arrangement for an explicitly requested **almost-vertical / very-steep dive attack**. `divetest.M` is the authority for this geometry. In that working sample, the Green F8F wing (aliases `-3` through `-7`) attacks the Iowa object `IOWAO.NT` alias `-2`.

The verified terminal geometry is:

```text
Iowa target T       = (597957,     0, 631771)
pre-dive setup S    = (600794, 30000, 621098)
terminal attack A   = (596545, 30000, 628900)

horizontal |S-T|    ~= 11043.6 ft
horizontal |A-T|    ~=  3199.4 ft
vertical   A.y-T.y  = 30000 ft
geometric A->T dive ~= 83.9 degrees below horizontal
                       ~= 6.1 degrees away from vertical
```

The sample therefore demonstrates a **two-stage terminal arrangement** rather than putting the attack waypoint on top of the target or lowering the waypoint toward the ground:

1. **Pre-dive staging / formation point.** Keep the aircraft at the intended dive-entry altitude while it reaches a setup point farther from the target. In `divetest.M`, this point is still at `30000` ft, uses `w_goal 1`, has no preferred target, and uses `w_wng 3 0 512 0` = `tight + Echelon + near + level`. Its purpose is to deliver the wing to a controlled high-altitude setup position before the terminal dive is released.
2. **Terminal attack point.** Keep the attack waypoint at the **same high altitude**, but move it very close to the target in horizontal distance. In the sample this point remains at `30000` ft but is only about `3199` ft horizontally from Iowa. It switches to `w_wng 1 0 2048 0` = `loose + Echelon + far + level`, allowing the aircraft to leave the formation and execute the steep terminal maneuver.
3. **Target assignment occurs at the terminal attack point.** For the exact ship-attack sample, the attack waypoint uses `w_goal 16`, `w_react $2000 $8000 $0`, `w_searchDist 0`, and `w_preferredTargetId2 $fffe`, where `$fffe` is the low-16-bit encoding of Iowa alias `-2`. This exact tuple is verified for this sample. Do not treat `$fffe` as a generic ship token; encode the actual selected alias.
4. **Do not force the setup point and target to be collinear.** `divetest.M` does not use a straight-line setup -> attack -> target geometry. The verified behavior comes from bringing the aircraft to a high setup point, then to a high terminal attack point with very small target-relative horizontal separation, after which the aircraft is free to turn and dive toward the target.

#### A. v24 generation method for an explicitly requested almost-vertical dive

When the user asks for a dive that is nearly vertical, or asks to reproduce the `divetest.M` behavior:

- Let the target be `T = (Tx, Ty, Tz)` and choose the intended terminal dive-entry altitude `Ay`.
- Create a pre-dive staging point `S` at approximately the same altitude `Ay`, far enough from the target to establish the attack. The exact sample uses about `11044` ft horizontal target stand-off at `30000` ft altitude.
- Create the terminal attack point `A` at the **same altitude `Ay`**, but with much smaller horizontal target stand-off. Do **not** put `A` directly at `T`, and do not reduce `A.y` merely to make the route look like a dive.
- If no user-specified or higher-authority terminal stand-off is available, a conservative v24 planning heuristic may scale the verified sample ratio:

```text
vertical separation V = Ay - Ty
terminal horizontal stand-off D ~= 0.10665 * V
```

  This reproduces the `divetest.M` geometry (`V = 30000`, `D ~= 3199`) and corresponds to a geometric descent line of about `83.9` degrees below horizontal. This is a **planning heuristic derived from one working sample**, not a decoded Fighters Anthology ballistic or AI parameter. A user-specified dive angle/stand-off or a later higher-authority working sample always wins.
- When reproducing the full sample-like two-stage geometry and no better setup distance is supplied, the setup-point target stand-off may likewise be scaled from the sample as approximately `0.3681 * V` (`~11044` ft at `30000` ft). Treat this as a secondary planning heuristic, not a required engine constant.
- Choose the azimuths of `S` and `A` to fit the requested ingress, terrain, defenses, and target approach. The v24 requirement is the **large setup stand-off followed by very small high-altitude attack-point stand-off**, not a fixed compass bearing.

#### B. v24 refinement of the v23 `far + loose` dive rule

v23 remains fully active for the **actual dive-maneuver phase**. v24 adds a narrow distinction proven by `divetest.M`:

- A **pre-dive staging/formation waypoint that is still delivering the wing to the dive release geometry** may use `near + tight` even though the next waypoint is a dive attack. In the verified sample this is `w_wng 3 0 512 0`.
- The **terminal attack waypoint where the aircraft is released to perform the steep dive** must use v23 `far + loose`; the sample uses `w_wng 1 0 2048 0`.
- Once the aircraft has entered the active free-maneuver dive sequence, any later visible waypoint that still belongs to that free-maneuver sequence continues to follow v23 `far + loose` unless another higher-authority verified sample explicitly proves otherwise.
- Therefore v24 supersedes only the older v23 wording that could force the **pre-dive staging/formation point** itself to `far + loose`. It does **not** weaken the v23 requirement on the terminal attack point or subsequent active dive maneuvering.

Current dive/level-bombing formation precedence is therefore:

```text
v24 almost-vertical dive, pre-dive staging point -> sample permits near + tight
v24/v23 terminal or active dive maneuver point   -> far + loose
high-altitude / level bombing                    -> v18 near + tight hostile-area corridor
other ordinary navigation                        -> v17 far + loose default unless another verified override applies
```

#### C. Preserve mission-role reaction and target rules

The v24 geometry is independent of weapon/target-class semantics. Use the exact `divetest.M` Anti-ship tuple only when the requested waypoint role and target context justify that verified combination. If the same near-vertical geometry is used for a ground/airfield dive-bombing task, retain the applicable v18-v20 bombing reaction and valid-ground-target rules instead of blindly copying the Iowa Anti-ship reaction. v22 Assignment / Target / Duration encoding remains active, and all v23 and earlier carrier, filename, fuel/loadout, briefing, map, success-condition, ambience, and asset-resolution rules remain unchanged.

### v23 dive-bombing waypoint behavior: mandatory `far + loose` override

The v23 policy preserves **all v22 and earlier functionality** and adds one mission-generation override for **dive bombing**. This rule applies when the intended bombing profile requires the aircraft to maneuver freely and descend/dive toward the ground target. It does **not** apply to the v18 high-altitude/level-bombing profile whose purpose is to hold altitude through the hostile-area attack corridor.

For a true dive-bombing route:

- Every **visible navigation point that belongs to the active free-maneuver dive-bombing phase** must use `spacing = far` and `control = loose`. This includes the terminal attack point, attack-area turns/realignment points, and any waypoint that remains part of the active dive-bombing maneuver sequence. **v24 refinement:** a distinct pre-dive staging/formation point that has not yet released the wing into the free-maneuver dive may use the verified `divetest.M` `near + tight` setup pattern.
- In the verified visible-waypoint field order `w_wng <control> <formation> <spacing> <stacking>`, serialize **`control = loose` as `1`** and **`spacing = far` as `2048`**. Preserve the selected/verified formation and stacking values in their own fields.
- Do **not** apply the v18 high-altitude-bombing `near + tight` corridor to a dive-bombing profile merely because bombs are carried or the aircraft is over hostile territory. The reason for this v23 override is operational freedom: `far + loose` lets the dive bomber leave rigid formation and perform the required dive maneuver.
- Conversely, if the mission is explicitly **high-altitude level bombing**, altitude-hold bombing, or another profile covered by v18, keep the v18 hostile-area `near + tight` rule. Do not reinterpret high-altitude level bombing as dive bombing.
- Classify the bombing profile from the user's requested attack method / mission description or a higher-authority verified sample. A bomb load by itself does not prove that the mission is dive bombing.
- This v23 rule changes **waypoint spacing and control only**. It does not cancel the v19 bombing `w_react` corridor, the v20 bombing preferred-target rules, the v22 Assignment / Target / Duration encoding, or any target-validity rule. Those fields remain independently governed by their existing rules.

Therefore the v23 bombing formation-behavior precedence, as refined by the later v24 pre-dive staging rule above, is:

```text
active free-maneuver dive bombing -> far + loose
v24 pre-dive staging/formation     -> verified sample may use near + tight
high-altitude / level bombing      -> v18 near + tight hostile-area corridor
other ordinary navigation          -> v17 far + loose default unless another verified override applies
```

This v23 rule is a deliberate generation-policy override. It supersedes any older statement that could cause a **dive-bombing** waypoint to inherit `near + tight` solely from the generic/high-altitude bombing rules. **v24 refinement:** this does not prohibit the separately defined `divetest.M` pre-dive staging/formation point from using `near + tight` before the terminal free-maneuver dive begins.

### v22 waypoint advanced behavior: Assignment / Target / Duration override

The v22 policy preserves **all v21 and earlier functionality** and adds a first-class three-selector model for every visible aircraft navigation point. The user-facing Mission Creator settings are:

1. **Assignment** — the tactical behavior at that waypoint.
2. **Target** — either no specified target or a specific object alias.
3. **Duration** — the condition that ends the waypoint assignment.

`assignment.M` is the v22 authority for the exact tested combinations below. v22 correctly established that **`w_goal` carries the tested Duration condition rather than uniquely identifying the named Assignment**, Target is represented by `w_preferredTargetId2`, and the tested named Assignment choices correlate with exact `w_react` / `w_searchDist` tuples. **v25 clarification:** `1.M` proves that `w_react` is also the directly editable per-target-class reaction matrix, so do not treat `w_react + w_searchDist` as a one-to-one universal identity for the visible Assignment label. The v22 rows remain exact verified presets.

#### A. Exact verified `assignment.M` tuples

Use the following complete tuples exactly when the requested three UI choices match a tested row. The aircraft column identifies the differential-test row; the behavior mapping itself is a waypoint setting and is not restricted to that aircraft unless another rule says otherwise.

| Differential row | Assignment | Target | Duration | `w_goal` | `w_react` | `w_searchDist` | `w_preferredTargetId2` |
|---|---|---|---|---:|---|---:|---|
| F-4B (`F4B.PT`) | Normal Flight | none | until waypoint is reached | `1` | `$0 $8000 $0` | `0` | `$0` |
| F-5E (`F5E.PT`) | MIGCAP | none | until waypoint is reached | `1` | `$8000 $0 $0` | `25` | `$0` |
| F-8E test row (`F8J.PT`) | BARCAP | none | until waypoint is reached | `1` | `$c000 $0 $0` | `25` | `$0` |
| F-14 (`F14.PT`) | Wild Weasel | none | until waypoint is reached | `1` | `$1800 $8000 $0` | `10` | `$0` |
| F-15 (`F15.PT`) | CAS | none | until waypoint is reached | `1` | `$400 $9800 $0` | `5` | `$0` |
| F-16 (`F16F.PT`) | Anti-ship | none | until waypoint is reached | `1` | `$2000 $8000 $0` | `0` | `$0` |
| F-22 (`F22.PT`) | Hi/Lo sweep | none | until waypoint is reached | `1` | `$ffff $0 $0` | `10` | `$0` |
| F-35A test row (`ASTOVL.PT`) | Hi/Lo sweep | airport target | until target is attacked | `4` | `$ffff $0 $0` | `10` | `$fff7` in this sample |
| F-35B test row (`ASTOVLF.PT`) | Hi/Lo sweep | airport target | until target is damaged | `8` | `$c000 $0 $0` | `25` | `$fff7` in this sample |
| F-35C test row (`F22N.PT`) | Hi/Lo sweep | airport target | until target is destroyed | `16` | `$c000 $0 $0` | `25` | `$fff7` in this sample |

In `assignment.M`, the airport target is `STRIP1.OT` alias `-9`, therefore `-9 & 0xffff = $fff7`. `$fff7` is **not** a universal airport token; for another mission, encode the actual selected target alias through the normal signed-alias low-16-bit rule.

The three Hi/Lo-sweep target-condition rows prove that the raw reaction/search tuple is **not guaranteed to remain identical across every Target/Duration combination**, even when the UI Assignment label is the same. Therefore, exact tested full tuples take precedence over any attempt to normalize all Hi/Lo-sweep rows to one reaction/search preset.

#### B. Duration mapping — CONFIRMED by v22

For ordinary visible aircraft waypoints using the advanced behavior selectors:

```text
w_goal 1  = until waypoint is reached
w_goal 4  = until target is attacked
w_goal 8  = until target is damaged
w_goal 16 = until target is destroyed
```

This v22 decoding supersedes the older provisional labels `w_goal 1 = Normal Flight` and `w_goal 16 = Anti-Ship`. Assignment and Duration are separate UI concepts. For example, the verified F-16 row is **Anti-ship + no target + until waypoint is reached**, so it correctly uses `w_goal 1`; the Anti-ship behavior is carried by `w_react $2000 $8000 $0` plus `w_searchDist 0`.

`w_goal 0` remains the START/END no-assignment sentinel form, and `w_goal 34` remains the separately verified carrier-landing `Land` form. Do not reinterpret those special forms as advanced Duration choices.

#### C. Target mapping — CONFIRMED

For the waypoint Target selector:

```text
no specified target -> w_preferredTargetId2 $0
specific Target alias A -> w_preferredTargetId2 (A & 0xffff)
```

Continue to apply all v20 target-source rules: a valid bombing target may be a suitable generated `.M` ground object or a confirmed matching-map `.MM` ground object, and a `*.PT` aircraft remains invalid as a direct bomb target under v18. Protect encoding remains a separate object-level/verified mechanism and is not implied by the v22 waypoint Target selector.

#### D. Named Assignment / reaction presets and conservative composition

The first seven rows establish these verified no-target / until-waypoint-reached named Assignment / reaction presets:

```text
Normal Flight -> w_react $0    $8000 $0 ; w_searchDist 0
MIGCAP        -> w_react $8000 $0    $0 ; w_searchDist 25
BARCAP        -> w_react $c000 $0    $0 ; w_searchDist 25
Wild Weasel   -> w_react $1800 $8000 $0 ; w_searchDist 10
CAS           -> w_react $400  $9800 $0 ; w_searchDist 5
Anti-ship     -> w_react $2000 $8000 $0 ; w_searchDist 0
Hi/Lo sweep   -> w_react $ffff $0    $0 ; w_searchDist 10
```

For a combination not present verbatim in `assignment.M`, Target and Duration may be composed from the confirmed mappings above, while a named Assignment may start from its verified reaction/search preset **only when no contradictory tested tuple exists**. The Hi/Lo-sweep attacked/damaged/destroyed rows are the explicit contradiction/exception: use their exact complete tuples rather than assuming the baseline Hi/Lo reaction/search survives unchanged. **v25 clarification:** when the user explicitly customizes per-class Attack/Defend/Evade/Ignore behavior, `w_react` may be adjusted with the confirmed class masks from Section 11 while preserving the independently requested/verified Target and Duration; do not claim that such a custom reaction matrix must still equal one of the named preset tuples.

If a future differential supplies another exact Assignment/Target/Duration combination, that exact working tuple outranks this conservative composition rule.

#### E. Precedence with v18-v20 bombing behavior

The v18-v20 bombing policies remain the defaults when waypoint advanced behavior is not explicitly specified. When the user explicitly requests one of the exact v22 advanced tuples **without a custom per-class reaction override**, serialize that exact waypoint tuple; do not silently rewrite its `w_goal`, `w_react`, `w_searchDist`, or `w_preferredTargetId2` back to an older inferred default. If the user explicitly asks to fine-tune target-class reactions, v25 permits changing the confirmed `w_react` class bits while keeping the other independently requested/verified fields unless a higher-authority sample proves a coupled change. All unrelated v18-v20 behavior—bomb-target type restrictions, `.MM` target validation, hostile-area formation/spacing discipline, lead-distance geometry, and multi-waypoint target-source rules—remains in force unless the explicit v22 tuple directly supplies the same waypoint field.

### v21 JKPFA_53b split-carrier hull/Tower assembly override

The v21 policy preserves **all v20 and earlier functionality** and adds a mandatory assembly rule for five JKPFA_53b aircraft carriers whose `*.NT` carrier object contains the **hull only**. When one of these carriers is generated under the `DEFAULT_PLUS_JKPFA_53B` profile, also generate its matching `*.OT` Tower object(s) at the verified carrier-relative position. Once placed correctly, the Tower object becomes part of the carrier and follows the carrier automatically; do **not** give the Tower an independent movement waypoint or attempt to project its later position separately.

`CV.M` is the v21 authority for the exact hull/Tower pairings and the local offsets below. The supplied sample has every carrier and Tower at `angle 0 0 0`, so each listed `(dX0, dZ0)` is the Tower position minus the hull position at carrier heading `H = 0`:

| Carrier hull | Class / use | Required Tower object(s) | Verified local offset(s) `(dX0, dZ0)` |
|---|---|---|---|
| `ESSE.NT` | Essex Class CV; **always use this carrier when simulating a WWII wooden-deck aircraft carrier** | `ESSET.OT` | `(+153, +68)` |
| `CDEG.NT` | Charles De Gaulle Class CVN | `CDEGT.OT` | `(+298, -325)` |
| `INVN.NT` | Invincible Class CVSA | `INVNT.OT` | `(+46, -77)` |
| `ELIZ.NT` | Queen Elizabeth Class CVF | `ELIZT.OT` **twice** | Tower 1 `(+330, +571)`; Tower 2 `(+298, -238)` |
| `KUZN.NT` | Admiral Kuznetsov Class CV | `KUZNT.OT` | `(+202, -160)` |

These exact asset tokens are confirmed by the v21 `CV.M` working sample. Therefore, when the active installation profile is `DEFAULT_PLUS_JKPFA_53B`, treat the five hull/Tower pairings above as verified JKPFA_53b assets even if a separately generated `FA_items` inventory omits one of these exact tokens. They remain unavailable under `DEFAULT_ONLY`.

For a carrier hull at:

```text
pos carrierX carrierY carrierZ
angle H 0 0
```

rotate each heading-zero local offset around the vertical axis before adding it to the carrier position:

```text
dX = dX0 * cos(radians(H)) + dZ0 * sin(radians(H))
dZ = -dX0 * sin(radians(H)) + dZ0 * cos(radians(H))

towerX = carrierX + round(dX)
towerY = carrierY
towerZ = carrierZ + round(dZ)
```

This rotation convention is consistent with the existing naval heading convention in which heading `0` advances toward `+Z` and heading `90` advances toward `+X`. At `H = 0`, the formula reproduces the exact `CV.M` coordinates. Use the carrier's own heading value for `H`; do not leave the Tower at an unrotated heading-zero offset when the carrier heading is nonzero.

Each Tower object must:

- use the exact matching `*.OT` type listed above;
- use the rotated initial position calculated from the carrier hull position;
- use the **same `angle` as the carrier hull** (normally `angle H 0 0` for a level ship);
- use the same nationality as the carrier;
- use a unique alias;
- use the tested Tower object pattern from `CV.M`: `flags $4011` and `speed 0`, unless a later higher-authority differential proves a change is needed;
- have **no independent waypoint group** and no independent ship speed/course logic; after correct placement it follows as part of the carrier;
- remain separate from the carrier's own Section 18.5 movement waypoint. The hull receives the naval movement route; the attached Tower does not.

For `ELIZ.NT`, both `ELIZT.OT` objects are mandatory. They are two separate mission objects with separate aliases, each calculated independently from its own local offset. Never collapse Queen Elizabeth to a single Tower.

This v21 rule changes carrier assembly/placement only. It does not alter v14 carrier-recovery waypoint placement, v13 deck-start behavior, Section 18.5 ship movement, v20 bombing targeting, or any other earlier mission-generation rule.

### v20 bombing waypoint target assignment and `.MM` map-target override

The v20 policy preserves **all v19 and earlier functionality** and adds a bombing-target assignment override for repeated or multi-waypoint bombing missions. This rule supersedes earlier instructions that prohibited or discouraged bombing `preferredTargetId2` / `w_preferredTargetId2` references to map-default `.MM` aliases or implied that a targetable ground object had to be duplicated into the generated `.M`.

For a repeated or multi-waypoint bombing mission, **every visible waypoint that belongs to the active bombing sequence may be assigned its own specific valid ground target**. This includes explicit Attack waypoints and also post-attack turns, between-pass turns, alignment/realignment points, normal-flight repositioning points, and target-area egress points that still belong to the active bombing sequence. When enough valid targets are available, successive bombing-related waypoints should use **different targets** rather than repeating the same alias.

For an airfield strike, suitable direct bombing targets include confirmed non-aircraft ground objects such as control towers, hangars, aircraft shelters, fuel-storage facilities, ammunition/supply storage, bunkers, radar or command facilities, runway-related structures, air-defense units, and other airport-associated ground objects. The inherited v18 restriction still applies: a `*.PT` aircraft object, including a parked aircraft, is not a valid direct bomb target.

Serialize a waypoint-specific bombing target through `w_preferredTargetId2` using the normal signed-alias low-16-bit target encoding. A valid preferred ground target **does not replace, narrow, or terminate** the v19 bombing attack-reaction corridor. Every waypoint still inside that corridor continues to use:

```text
w_react $ffff $0 $0
```

Thus target assignment and reaction are independent: `w_preferredTargetId2 <ground_alias16>` selects a preferred ground object, while `w_react $ffff $0 $0` continues to allow the all-object bombing reaction required by v19.

When multiple bombers share the same planned route, they may use the same ordered target sequence. Allocate separate target sequences only when the user requests separate allocations or a higher-authority working mission requires them.

#### A. Confirmed `.MM` ground objects are valid bombing targets

Objects already present in the **matching companion `.MM`** are valid bombing targets and do not need to be duplicated into the generated `.M` merely to make them targetable. For bombing target assignment, a generator may use the alias of an existing `.MM` ground object directly in object-level `preferredTargetId2` or waypoint-level `w_preferredTargetId2` when that map object is the intended mission target.

Before assigning an `.MM` object as a bombing target, read the supplied matching `.MM` and confirm all of the following from that file:

- the object's exact `alias`;
- its object `type`;
- its `pos X Y Z`;
- that its location/identity is actually related to the requested target area;
- that the `.MM` internally matches the selected mission map through its `map <basename>.T2` header.

Do **not** invent an `.MM` alias, borrow an alias from another map, assume coordinates from a different `.MM`, or use a map object whose relationship to the requested target area has not been established from the supplied matching map.

Mission-generated `.M` ground objects remain valid direct bombing targets as before. A bombing target sequence may freely combine suitable confirmed `.MM` ground objects and suitable mission-specific `.M` ground objects.

#### B. Target distribution across the active bombing sequence

For repeated airfield/installation bombing, first build a pool of valid non-aircraft ground targets in the requested target area from both the matching `.MM` and the generated `.M`. Prefer a sequence that distributes different valid airport-related ground objects across successive bombing-related waypoints. Reuse a target only when the pool does not contain enough valid distinct targets, when route/geometry makes another target inappropriate, or when the user explicitly requests repeated attacks on the same object.

The active target-assignment scope follows the **same mission-phase interpretation used by the v19 attack-reaction corridor**: an intermediate Turn, realignment, repositioning, or target-area egress waypoint can still receive its own preferred ground target when it remains part of the active bombing sequence. Waypoint role/name alone does not force `w_preferredTargetId2 $0`.

This v20 rule is a **target-selection/source override**, not a change to the target alias encoding, v18 aircraft-target prohibition, v18 altitude-discipline corridor, or v19 reaction persistence. In particular, older statements such as “leave `w_preferredTargetId2 $0` unless the target is a generated `.M` object,” “do not reference `.MM` aliases,” or “create/duplicate a `.M` object to make a map target targetable” are superseded **for bombing target assignment** by this v20 policy. Non-bombing Target/Protect behavior remains governed by the earlier verified rules unless a later explicit override changes it.

### v19 bombing attack-reaction corridor override

The v19 policy preserves **all v18 and earlier functionality** and adds one further high-altitude/repeated-bombing behavior rule: once the aircraft has entered the **actual bombing attack phase**, the waypoint-level **Attack all object types** reaction must persist across the whole active bombing sequence instead of being limited to an explicit Attack waypoint.

This creates an **attack-reaction corridor** that is conceptually separate from, but complementary to, the v18 **altitude-discipline corridor**:

- The v18 altitude-discipline corridor still begins at the enemy-territory entry/turn-in waypoint and governs `spacing = near` plus `control = tight` while the high-altitude bomber is in the hostile-area portion of the route.
- The v19 attack-reaction corridor begins at the **first bombing Attack waypoint** of the active bombing sequence. From that waypoint onward, serialize `w_react $ffff $0 $0` on **every visible waypoint that still belongs to that bombing sequence**.
- The corridor explicitly includes the first Attack waypoint, any immediate post-release/post-attack Turn, any Turn between repeated bombing passes, any realignment/stabilization waypoint before the next pass, any ordinary/reposition waypoint (`w_goal 1`, duration = until waypoint reached) used only to reposition for the next bombing pass, every subsequent Attack waypoint, and any post-attack/egress waypoint that still belongs to the active target-area attack cycle.
- **Waypoint name or role must not reset the reaction.** A waypoint named/used as `Turn`, `Realign`, `Ingress`, `Egress`, or a `w_goal 1` reposition point does not by itself permit a return to Defend/normal navigation reaction while another bombing pass is still pending.
- In particular, do **not** replace an intermediate corridor waypoint with `w_react $0 $ffff $0` (All Defend), and do not otherwise remove the `$ffff` Attack mask merely because that waypoint is not itself labeled Attack.
- If another bombing pass remains planned or pending, **Attack all must survive across the intervening Turn(s)** and realignment waypoint(s). The sequence is continuous for reaction purposes even when the route temporarily changes course or uses a normal-flight goal between weapon-release points.
- The attack-reaction corridor may end only after **all three** conditions are true: (1) the final planned bombing pass is complete, (2) the bomber has actually left the active target/hostile area rather than merely passed the last release point, and (3) no further bombing attack remains pending. Only then may later safe-area navigation restore an ordinary verified defense/navigation reaction.
- If a later waypoint still exists to set up another bombing pass, that is proof that the bombing sequence is still active; keep `w_react $ffff $0 $0` through that waypoint and into the next Attack.

For repeated high-altitude bombing passes, `w_react $ffff $0 $0` must therefore **not** be limited to the explicit Attack waypoint. After the first bombing Attack waypoint, every Turn, post-attack turn, between-pass turn, realignment waypoint, and subsequent attack waypoint that remains part of the active bombing sequence must also retain **Attack all object types**. Do not revert these intermediate Turn waypoints to `w_react $0 $ffff $0` (All Defend) while another bombing pass is still pending. The attack-all reaction may be relaxed only after the final planned bombing pass is complete and the bomber has left the active target/hostile area with no further attack requirement.

This v19 rule changes the **persistence/scope** of the verified v18 all-object bombing reaction; it does not change the three-word `w_react <ATTACK_MASK> <DEFEND_MASK> <EVADE_MASK>` encoding, the meaning of `$ffff`, or any earlier targeting, filename, fuel/loadout, carrier, briefing, map, success-condition, ambience, or waypoint-geometry rule. **Current v20 supersession:** v20 now changes bombing target selection/source rules by permitting confirmed matching-map `.MM` ground aliases and per-waypoint bombing preferred targets, while leaving the v19 reaction encoding/persistence itself unchanged.

### v18 high-altitude bombing / bomb-target override

The v18 policy preserves **all v17 and earlier functionality** and adds two bombing-specific mission-generation rules. These are behavior overrides for ground-attack missions; they do not change the verified raw mappings for waypoint `spacing`, waypoint `control`, target aliases, or reaction words.

**v23 supersession for dive bombing, refined by v24:** the v18 `near + tight` altitude-discipline corridor applies to high-altitude/level bombing, not to the active free-maneuver phase of a true dive-bombing profile. Under v23, terminal/active dive-maneuver waypoints use `far + loose` so the aircraft can maneuver freely into the dive. v24 additionally permits the verified `divetest.M` pre-dive staging/formation point to remain `near + tight` before that free-maneuver phase begins. All non-spacing/control parts of v18 remain applicable where relevant.

#### A. High-altitude bombers must hold the assigned bombing altitude

The v17 general default remains `spacing = far` plus `control = loose` for ordinary visible navigation points because that combination gives combat aircraft freedom to leave formation and engage. **v18 adds a specific exception for high-altitude ground bombing.**

Apply the v18 high-altitude bombing exception when either condition is true:

- the aircraft is identified by the active catalog / supplied scenario as a strategic or high-altitude bomber (for example B-52 or B-2 when those assets are actually available in the active catalog), or
- the user explicitly says that the aircraft must perform level/high-altitude bombing, maintain bombing altitude, avoid diving into ground-fire envelopes, or otherwise remain at the specified high altitude during the attack.

For a high-altitude bombing route, treat the hostile-territory portion of the flight as an **altitude-discipline corridor**, not as a rule that applies only to the final attack point.

- From takeoff through friendly/neutral transit, ordinary v17 behavior may remain `spacing = far` plus `control = loose` unless the user specifies otherwise.
- At the **enemy-territory entry/turn-in waypoint** — including a course-change/turn waypoint used to line the formation up for entry into the hostile defended area — switch to `spacing = near` (raw code `512`) and `control = tight` (raw code `3`). If the turn begins immediately before the mapped/known hostile boundary and exists specifically to establish the hostile-area ingress, treat that turn waypoint as the start of the corridor rather than waiting until the following point.
- Keep **every visible waypoint while the bomber remains in enemy territory** at `near + tight`: ingress turns, alignment/stabilization points, bombing attack waypoints, between-target turns for multiple attacks, post-release turns, and hostile-territory egress points.
- If another bombing attack is still pending, do **not** relax to `far + loose` between attacks, even after the first weapon release. Maintain `near + tight` continuously through the hostile-area route.
- After the **final planned attack has been completed and the bomber has exited enemy territory**, the next safe-area egress/transit waypoint may return to the ordinary v17 `far + loose` behavior. If the route will later re-enter enemy territory for another attack, use `far + loose` only in the safe transit portion, then switch back to `near + tight` at the next enemy-entry/turn-in waypoint.
- Therefore every visible waypoint inside this corridor must use the verified `w_wng` field order with `3` in the control field and `512` in the spacing field, while formation/stacking continue to use verified mappings.
- Preserve the explicitly requested high-altitude profile throughout the hostile-territory corridor; do not deliberately lower an attack, turn, or egress waypoint to induce a dive-bombing profile.

This exception exists because a `far + loose` waypoint anywhere inside the hostile bombing corridor can allow the aircraft to break altitude/formation discipline and begin a diving or otherwise uncontrolled ground attack, potentially descending into the ground-defense envelope. Aircraft whose intended attack doctrine actually requires a dive or low-level attack may continue to use the ordinary v17 behavior unless the user specifies otherwise.

The high-altitude **attack waypoint must be placed before the ground target along the inbound flight path**, not directly on top of the target. The aircraft needs horizontal distance/time after entering the attack state for the bombs to fall onto the target while the bomber remains high. Determine this lead distance primarily from the specified attack-waypoint altitude:

- higher bombing altitude -> attack waypoint farther before the target;
- lower bombing altitude -> attack waypoint may be closer to the target;
- never move the attack waypoint behind the target merely to satisfy formation geometry.

When a deterministic lead distance is required and no user/tested value is supplied, a conservative planning heuristic may estimate bomb fall time from altitude and combine it with the waypoint/inbound speed, for example `t ~= sqrt(2 * altitude_ft / 32.174)` and `lead_ft ~= speed_fps * t`, optionally with a modest safety margin. This is a **mission-planning heuristic, not a decoded Fighters Anthology ballistic field**. A higher-authority working mission or user-specified release/attack distance always wins. Regardless of the exact heuristic used, the generated lead distance must increase when the specified bombing altitude increases, all else equal.

#### B. Bomb loads must not use aircraft objects as direct bombing targets

When an aircraft is carrying bombs for a ground-bombing task, treat an aircraft object as an invalid **direct bomb target**, even when that aircraft is parked on the ground. Do not point an object-level or waypoint-level ordinary Target assignment at a `*.PT` aircraft alias merely because the intended victims are parked aircraft.

For an airfield/airbase strike whose desired effect includes destroying parked aircraft:

- treat the attack as an **area / installation ground strike**, not an aircraft-only attack;
- set the attack reaction to **Attack all object types** so the bomber can attack valid airport facilities/ground objects in the target area rather than trying to use bombs against an aircraft-class target;
- under the current confirmed three-word reaction structure and the verified all-category `$ffff` mask, serialize the all-object attack form as `react $ffff $0 $0` at object level when appropriate and `w_react $ffff $0 $0` at the bombing waypoint;
- **historical v18 default, superseded by v20 for bombing:** v18 originally left `w_preferredTargetId2 $0` unless a specific valid non-aircraft generated `.M` object was assigned. Under v20, any valid bombing-sequence waypoint may instead carry a specific valid non-aircraft ground target from either the generated `.M` or the confirmed matching `.MM`;
- **v20 supersession:** confirmed matching-map `.MM` aliases may be used directly for bombing `preferredTargetId2` / `w_preferredTargetId2`. Do not invent an alias or use an alias/position from another map; verify the target's alias, type, position, and target-area relationship from the supplied matching `.MM`.

The intended behavior is that the bomber attacks airport facilities/other valid ground objects in the airfield target area, with parked aircraft exposed to the resulting bombing damage, instead of wasting the bomb attack on an aircraft-class target the bomb cannot validly engage.

If the aircraft carries a mixed load, apply this restriction specifically to the **bombing task/waypoint**. Air-to-air weapons may still be used against aircraft through separate reaction/assignment behavior when the mission supports that role.

This v18 rule supersedes v17's `far + loose` waypoint default **for the entire hostile-territory altitude-discipline corridor of a high-altitude bombing mission**, beginning at the enemy-territory entry/turn-in waypoint and ending only after the final attack is complete and the bomber has exited enemy territory. Friendly/neutral pre-ingress transit and safe post-egress transit may use the ordinary v17 defaults. All inherited v15 fuel/hardpoint, v14 carrier-recovery, v13 carrier-deck-start, v12 takeoff/landing, briefing, map, success-condition, and ambience rules remain in force; historical v16 filename behavior is retained only as legacy evidence because v25 supersedes it for newly generated output.

### v17 waypoint-spacing default override

The v17 policy preserves **all v16 and earlier functionality** and changes only the default generation behavior for navigation-point `spacing`. The purpose is to avoid the `near` spacing behavior that can keep wingmen in formation instead of allowing them to break away and actively attack enemy aircraft.

Under v17:

- Every **visible navigation point** whose spacing is not explicitly specified by the user must use `spacing = far`.
- `far` serializes with the already verified spacing code `2048` in the third field of visible-waypoint `w_wng`.
- Use `spacing = near` / code `512` **only when the user explicitly requests `near`** for that waypoint, route, wing, or group.
- Never randomly select `near` for an unspecified spacing. Historical differential samples containing `near` remain valid mapping/format evidence, but their `near` value must not be inherited into a newly generated waypoint unless the user explicitly requested it.
- This v17 rule changes only the spacing-selection default. Existing verified `formation`, `stacking`, and `control` mappings remain unchanged; `control` still defaults to `loose` unless the user explicitly requests another verified control level.
- START and END sentinel records remain `w_wng 0 0 0 0`; the `far` default applies to visible navigation points, not to sentinel records.

This v17 rule supersedes every older instruction that allowed unspecified waypoint spacing to be randomized between `far` and `near`. Historically all v16 filename behavior and the other inherited rules remained in force; **v25 now supersedes only the active v16 filename-generation rule**. v15 fuel/hardpoint behavior, v14 carrier recovery behavior, v13 carrier-deck-start behavior, and all other inherited rules remain in force.

### v16 `.M` / `.MT` output-filename override — HISTORICAL, SUPERSEDED BY v25 FOR NEW OUTPUT

**v25 supersession:** retain this section as historical v16 behavior and legacy-file evidence only. For newly generated missions, Section v25-A requires an exactly seven-character `<STEM6><REV1>` basename and revision progression `1-9`, then `A-Z`.

The v16 policy adds a strict naming rule for every newly generated mission-file pair while preserving all v15 mission-generation behavior. The `.M` and `.MT` files must use the **same basename**, and that basename must satisfy all of the following:

- Basename length is **1–8 characters inclusive**, matching the classic DOS 8.3 basename limit. The `.M` / `.MT` extension is **not** counted.
- Every basename character must be an ASCII English letter `A`–`Z` or digit `0`–`9`.
- Every English letter in the basename must be serialized in **uppercase**.
- Therefore a newly generated output basename must match the regular expression `^[A-Z0-9]{1,8}$`.
- Spaces, `~`, `_`, `-`, parentheses, punctuation, non-ASCII characters, and all other non-alphanumeric characters are prohibited in newly generated output basenames.
- The paired files must be named exactly `<BASENAME>.M` and `<BASENAME>.MT`.
- If the user supplies a requested filename that does not comply, normalize it to a short compliant uppercase alphanumeric basename while preserving recognizability where practical. If truncation is necessary, truncate/abbreviate deterministically to at most 8 characters and use that same normalized basename for both files.
- Historical verified samples such as `~B08.M` / `~B08.MT` remain valid syntax/format evidence, but their leading `~` is **not** permitted for newly generated v16 output filenames. This v16 output-naming rule supersedes any older instruction to preserve a leading `~` in generated filenames.

This v16 rule changes only output-file naming. All v15 fuel/hardpoint behavior and all inherited v14/v13/v12 mission-generation rules remain in force.

### v15 fuel / hardpoint mission-generation override

The v15 policy supersedes the earlier v12/v13/v14 fuel explicit-only and hardpoint 4–9 generation rules while preserving the existing object-type eligibility gate: appended `fuel` and `hardpoint` fields may still be emitted only on aircraft objects whose own `type` filename ends in `*.PT`.

Under v15:

- `fuel` may be emitted whenever mission requirements justify it; the user does **not** need to explicitly mention fuel. The generator may choose a practical mission-appropriate percentage based on role, route length, expected endurance, loiter/support time, recovery requirements, and reserve needs. An explicit user-specified fuel percentage always takes precedence.
- Fuel remains optional: omit the line when the aircraft's normal/default fuel is suitable and no override is useful. Keep generated values within the practical `0–100` range unless a higher-authority working sample proves otherwise.
- Hardpoints 1–3 remain reserved and must never be emitted as overrides.
- Hardpoints **4 and 5 only** are the editable **fuselage** stations.
- Hardpoints **6, 7, and 8 only** are the editable **wing** stations.
- Hardpoint **9 is prohibited** and must never be emitted or selected by automatic loadout generation, even if an older sample or earlier skill version treated it as editable.
- Therefore the complete v15 editable hardpoint set is exactly `{4, 5, 6, 7, 8}`. User-supplied mappings outside that set must not be serialized.
- Valid payload items still come from the active effective ordnance catalog: weapon/equipment tokens use valid `*.JT`; verified external tanks may use valid `*.GAS`. Aircraft-specific real-world compatibility restrictions are not imposed on the allowed stations unless a higher-authority working sample requires them.

This v15 rule changes only fuel-use freedom and hardpoint station eligibility. The v14 carrier-recovery, v13 carrier deck-start, and inherited v12 takeoff/landing and waypoint-formation policies remain in force.

### v14 carrier-recovery initial-position override

For any aircraft route whose final landing/recovery is on an aircraft carrier, the visible **carrier landing/recovery waypoint must be placed at the landing carrier's initial mission coordinates**, not at an estimated or projected future carrier position. This rule applies even when the carrier itself moves after mission start.

Under this v14 policy:

- Read the landing carrier object's initial `pos <carrierX> <carrierY> <carrierZ>` from the generated mission object.
- Set the carrier recovery waypoint X/Z to that same initial `<carrierX>` / `<carrierZ>`.
- Use the tested carrier-landing form `w_goal 34` and `w_pos2 1 0 <carrierX> 0 <carrierZ>`.
- Set recovery waypoint altitude to `0` and `w_speed 0`.
- **Do not project, lead, extrapolate, or otherwise move the recovery waypoint to account for carrier speed, course, mission duration, ETA, or later carrier position.**
- The carrier and other naval vessels still follow all existing moving-ship/task-group rules; this override changes only the carrier landing/recovery waypoint placement.
- If a mission contains multiple possible landing carriers, the existing multi-carrier-selection limitation remains; do not invent a carrier-selection field. Once the intended landing carrier is known, use that carrier's initial X/Z coordinates.

This v14 rule **supersedes only the v12/v13 moving-carrier projected-recovery-position policy**. All other v13 and v12 behavior remains in force, including the v13 deck-start rule where navigation point A is the first real airborne mission waypoint, and the v12 altitude `0` / speed `0` convention for any explicitly present visible takeoff/launch point and every carrier landing/recovery point.

### v13 carrier deck-start first-visible-waypoint override

For an aircraft or player wing that **starts on an aircraft-carrier deck at altitude `0` and speed `0` using a verified carrier deck-start pattern**, do **not** automatically create a separate visible **takeoff / launch** navigation point merely to represent leaving the deck. The deck-start object state already represents the launch condition.

Under this v13 policy:

- The route still contains the normal START sentinel record, but that sentinel is not a visible navigation point.
- **Navigation point A is the first real airborne mission waypoint** requested by the scenario: for example the first CAP/patrol point, rendezvous, ingress, marshal, escort, or transit point.
- Navigation point A therefore uses the altitude, speed, `w_goal`, reaction, formation, and other settings appropriate to that real airborne mission role. It must **not** be forced to altitude `0` / speed `0` merely because the aircraft launched from a carrier.
- Do not insert a redundant zero-altitude/zero-speed visible waypoint at or near the carrier between the deck start and navigation point A.
- All aircraft in the same carrier-launched player wing/group should use the same visible route ordering, so their first visible waypoint is the same real mission point.
- If the **user explicitly requests a visible launch/takeoff navigation point**, or a higher-authority working mission sample requires one for that specific scenario, then the visible launch point may be emitted and the inherited v12 takeoff rule applies to it: altitude `0`, `w_speed 0`, with all other fields remaining evidence-based.
- This v13 exception is specifically about **carrier deck starts**. It does not remove or weaken the v12 visible takeoff/landing rule for land-airfield missions, explicitly requested launch points, or other verified contexts.
- Carrier recovery uses the tested carrier landing form, altitude `0`, and `w_speed 0`; **v14 overrides the earlier moving-carrier projection rule, so its X/Z is always the landing carrier's initial mission X/Z coordinates.**

In short, the normal carrier sequence is:

```text
carrier deck start (object at 0 ft / 0 speed)
-> START sentinel
-> A = first real airborne mission waypoint
-> ... mission route ...
-> carrier landing/recovery waypoint (0 ft / 0 speed)
-> END sentinel
```

### v12 takeoff / landing navigation-point override

A visible navigation point whose mission role is **takeoff / launch** or **landing / recovery** has a required v12 altitude/speed convention:

- **Takeoff / launch navigation point:** altitude `0`, speed `0`.
- **Landing / recovery navigation point:** altitude `0`, speed `0`.

In raw waypoint terms, the required portion is:

```text
w_pos2 <verified_modeA> <verified_modeB> <X> 0 <Z>
w_speed 0
```

This v12 rule deliberately fixes **only the waypoint altitude (`Y`) and waypoint speed**. It does not invent a new `w_goal`, `w_flags`, or `w_pos2` mode. Those other fields must still come from the verified context/template. In particular, `w_goal 34` and `w_pos2 1 0` remain confirmed for the tested carrier-landing pattern; do not generalize them to an ordinary land-airfield landing without a higher-authority working sample. Likewise, a land-airfield takeoff point may use the altitude/speed convention without claiming that a dedicated takeoff goal code has been decoded.

**v14 carrier-position supersession:** the v12 altitude/speed rule above remains valid, but its former moving-carrier future-position projection policy is no longer used. For every carrier landing/recovery waypoint, set X/Z to the landing carrier object's **initial mission X/Z coordinates**, with altitude `0` and `w_speed 0`, regardless of how far the carrier moves after mission start. Do not compute recovery ETA or project the carrier position for landing-waypoint placement.

### v12 waypoint formation / spacing / stacking / control override

Every visible navigation point may carry four formation-behavior settings in addition to speed and altitude:

- `formation`: `Echelon`, `Line abreast`, or `Line astern`. When the user does not specify one, the generator may choose randomly among values whose raw encoding is verified by the current differential sample set.
- `spacing`: `far` or `near`. **v17 override: when unspecified, always use `far`; use `near` only when the user explicitly requests `near`. Never randomize spacing by default.**
- `stacking`: `level`, `high`, or `low`. When unspecified, the generator may choose randomly among verified encodings.
- `control`: `loose`, `medium`, or `tight`. **Mission-generation default is always `loose` unless the user explicitly asks for another control level.** Do not randomize `control` by default. `medium` and especially `tight` make the formation follow the navigation point more rigidly and can reduce the unit's freedom to break formation and attack.

The four values are serialized through `wng` / `w_wng`; Section 14.2 contains the verified/derived mapping policy. For navigation-point generation, apply the four settings to the visible waypoint's `w_wng` value. Do not copy START/END `w_wng 0 0 0 0` records into a visible waypoint.

**v18 high-altitude bombing exception:** the v17 `far` / `loose` defaults remain the general rule outside the hostile bombing area, but a high-altitude bomber must use `spacing = near` and `control = tight` from the enemy-territory entry/turn-in waypoint through every waypoint inside enemy territory, including ingress turns, attack/alignment points, between-target turns, post-release turns, and hostile-territory egress. Keep `near + tight` until the final attack is complete **and** the bomber has exited enemy territory; only then may safe-area transit return to `far + loose`. If another attack is pending, never relax between attacks. Place each attack waypoint before its target along the inbound track, with more lead distance at higher bombing altitude.

### v15 fuel / hardpoint eligibility summary

`fuel` and `hardpoint` are **optional appended object fields**, not generic fields for every object type. The inherited type gate remains: only an aircraft object whose `type` filename ends in `*.PT` may receive appended `fuel` or `hardpoint` lines. Do not append either field to `*.JT`, `*.OT`, `*.NT`, or other object extensions unless a later explicit working differential revises the only-`*.PT` rule.

On an eligible `*.PT` aircraft object, `fuel` may be added automatically when useful for the mission; no explicit user request is required. User-specified fuel still overrides automatic selection.

Hardpoint syntax remains evidence-based. Hardpoints 1–3 remain reserved. The only editable stations are **4–5 (fuselage)** and **6–8 (wing)**. **Hardpoint 9 must never be used.** Valid payload items must come from the active catalog; weapon/equipment tokens use `*.JT`, and verified external tanks may use `*.GAS`.


The following are **mission-generation policies**, even when an older reverse-engineering sample used different values:

- **v22 waypoint advanced behavior:** treat each explicitly configured visible aircraft waypoint as Assignment / Target / Duration. Use exact `assignment.M` tuples when available; decode Duration as `w_goal 1/4/8/16 = waypoint reached / target attacked / target damaged / target destroyed`, encode Target through `w_preferredTargetId2`, and use the verified Assignment reaction/search preset unless an exact tested full tuple overrides it.
- Every newly generated `.M` / `.MT` pair uses the shared v25 revisioned basename: exactly seven characters matching `^[A-Z0-9]{6}[1-9A-Z]$`, with a six-character uppercase ASCII-alphanumeric stem and revision symbol `1-9` then `A-Z`; the first generation uses `1`, and each user-requested modification advances one symbol.
- Every visible navigation point defaults to **`spacing = far` (`2048`)** under v17. Use **`near` (`512`) only when the user explicitly requests `near`**; never select `near` randomly for unspecified spacing.
- **v18 high-altitude bombing exception:** for B-52/B-2-style strategic/high-altitude bombers or any aircraft explicitly tasked to maintain high-altitude level bombing, the bombing attack waypoint and any terminal stabilization ingress waypoint use **`spacing = near` (`512`) + `control = tight` (`3`)** even when the user did not explicitly request those two settings. The attack waypoint is placed before the target, and its lead distance increases with the specified bombing altitude.
- **v18 bomb-target rule + v20 target override:** when a bomb-carrying aircraft is performing a ground/airfield bombing task, do not directly Target a `*.PT` aircraft object with the bomb attack, even if the aircraft is parked. Keep the **all-object-type attack reaction** (`w_react $ffff $0 $0`) as required by v19, but under v20 each active bombing-sequence waypoint may also receive a specific valid non-aircraft ground target through `w_preferredTargetId2`; valid targets may come from the generated `.M` or from confirmed ground objects in the matching supplied `.MM`.
- **v19 bombing attack-reaction corridor:** once the first bombing Attack waypoint is reached, keep `w_react $ffff $0 $0` on every subsequent waypoint that is still part of the active bombing sequence, including `Turn`, post-attack turns, between-pass turns, realignment/stabilization points, `w_goal 1` repositioning points, later Attack waypoints, and target-area egress points. Never reset such an intermediate waypoint to `w_react $0 $ffff $0` merely because its role is Turn/Normal Flight. If another bombing pass is pending, Attack all persists across the Turn. Restore an ordinary defense/navigation reaction only after the final planned bombing pass is complete, the bomber has actually left the active target/hostile area, and no further attack remains pending.
- **v20 bombing waypoint target assignment / `.MM` override:** build a pool of valid non-aircraft ground targets for the requested bombing area from both generated `.M` objects and confirmed objects in the matching `.MM`. Assign `w_preferredTargetId2` per active bombing-sequence waypoint when appropriate, preferring different successive targets when enough valid targets exist. Confirm an `.MM` target alias/type/position/target-area relationship from the matching supplied map before use; no `.M` duplicate is required solely for targetability. Multiple bombers sharing one route may share the same ordered target sequence unless the user requests separate allocations.
- Every member of the **player's own wing/group**, including the player aircraft and all of its wingmen, must always use **Mission Success: Not affected**. Player-wing survival or destruction must never decide mission success.
- Every unit, friendly or hostile, defaults to **Expert** (`skill 3`) unless the user explicitly requests another skill for that unit/group.
- Every **hostile/enemy mission object** generated into the `.M` defaults to **Hide in briefing map** by OR-ing `0x0400` into that object's `flags`, unless the user explicitly requests that specific enemy object/group be shown. With the normal Not-affected base this is `flags $4417` instead of `$4017`. Friendly/player objects remain shown by default unless explicitly hidden. The paired `.MT` is still generated normally; `.MT` has no verified per-object briefing-map visibility field, so do not invent one.
- Every naval vessel must have at least one forward movement waypoint. Ships in the same task group must use the same course and speed.
- Every **explicitly present visible** takeoff/launch navigation point must use altitude `0` and `w_speed 0`; every landing/recovery navigation point must also use altitude `0` and `w_speed 0`. **v13 carrier-deck-start exception:** for a normal verified carrier deck start, do not auto-create a redundant visible launch point; navigation point A is the first real airborne mission waypoint. **v14 carrier-recovery rule:** place every carrier landing/recovery waypoint at the landing carrier's initial mission X/Z coordinates; do not project it to a future carrier position.
- Unless the user requests a minimal/exact-order-of-battle mission or explicitly disables ambience, automatically add approximately **5–10 auxiliary dynamic units** appropriate to the setting, while keeping them unrelated to mission success.
- `fuel` / `hardpoint` retain the only-`*.PT` object-type gate in Sections 9.5–9.6. Under v15, eligible aircraft may receive a mission-aware automatic `fuel` override without an explicit user request. Hardpoint overrides are restricted to exactly 4–5 (fuselage) and 6–8 (wing); 1–3 remain reserved and hardpoint 9 is prohibited.
- When a companion map `.MM.txt` file (logical `.MM` content) is supplied, it must be read before choosing map-specific locations. Use its default objects and named map markers as placement/reference data; do **not** blindly copy the complete `.MM` contents into the generated `.M`.


---

# 2. Source hierarchy

When generating a mission, use sources in this order:

1. **A user-provided working `.M`/`.MT` file pair, `.M` differential test file, or explicit working syntax example** — highest authority for mission syntax, briefing structure, and behavior.
2. **The companion map `<MAP>.MM.txt` file for the selected `.T2` map** — authoritative map-local reference for default object names, types, nationalities, positions, headings, and any stored default reaction/skill fields. Treat `.MM.txt` as the original logical `.MM` data with a transport `.txt` suffix. Match by the internal `map <basename>.T2` line, not filename alone.
3. **The active/effective catalog built from the user-supplied `FA_items` file** — authoritative lookup for available assets, maps, layers, ordnance, and country ordering. Section 3 defines automatic Default-vs-JKPFA_53b profile selection and PT/JT/NT/OT installed-library override precedence.
4. **Rules marked CONFIRMED in this skill.**
5. **Rules marked HIGH CONFIDENCE** only when necessary and when no contradictory sample exists.
6. Never invent a `.PT`, `.NT`, `.OT`, `.JT`, `.LAY`, `.T2`, flag bit, reaction mask, waypoint goal, target code, nationality value, or map-object location from general aviation knowledge.

If a user-provided working mission contradicts this skill, the working mission wins. Report the conflict and update the model rather than forcing the older rule.

---

# 3. Required items reference and automatic asset-profile selection

Read the **user-supplied items reference** before resolving any asset. Do not assume that every mission request uses the same installation profile.

The items reference provides at least these categories:

- Aircraft: `*.PT`
- Ordnance / hardpoint weapons and equipment: `*.JT`
- External tanks: `*.GAS` when listed in the ordnance section

**v12 object-vs-payload distinction:** `*.PT` identifies the aircraft object that may carry appended `fuel` / `hardpoint` lines. `*.JT` identifies ordnance/equipment tokens placed *inside* hardpoint lines; a `*.JT` mission object is not thereby eligible to carry its own hardpoints.
- Vehicles: `*.NT`
- Scenery: `*.OT`
- Layers: `*.LAY`
- Maps: `*.T2`
- Country list / country index order

## 3.1 Decode the uploaded items file before parsing

Known items-reference variants are not required to use the same text encoding. Detect a BOM/content encoding before line parsing.

- UTF-16 LE BOM (`FF FE`) -> decode as UTF-16 LE / `utf-16`.
- UTF-8 BOM -> decode as UTF-8 with BOM removal.
- Otherwise use an ASCII-compatible/UTF-8 decode conservatively.

Do not reject a valid combined reference merely because it is UTF-16 rather than the encoding used by the Default-only reference.

## 3.2 Automatically determine the active installation profile from file contents

Determine the profile from **section markers/content first**, not from the uploaded filename. A renamed file must still work.

### Profile A — `DEFAULT_ONLY`

Use this profile when the items file contains only the normal built-in asset sections and no JKPFA_53b overlay marker/section.

Typical section headers include:

```text
Aircraft:(*.PT)
Ordnance:(*.JT)
Vehicles: (*.NT)
Scenery: (*.OT)
```

For this profile, resolve `*.PT`, `*.JT`, `*.NT`, and `*.OT` only from the built-in/default entries in that uploaded reference. Do **not** import, remember, or guess JKPFA_53b assets from another request.

### Profile B — `DEFAULT_PLUS_JKPFA_53B`

Use this profile when the uploaded items reference clearly contains JKPFA_53b overlay markers such as any of:

```text
Aircraft:(*.PT) (when JKPFA_53b Lib installed)
Ordnance:(*.JT) (when JKPFA_53b Lib installed)
Vehicles: (*.NT)(when JKPFA_53b Lib installed)
Scenery: (*.OT)(when JKPFA_53b Lib installed)
```

or entry annotations such as:

```text
(JKPFA_53b Lib)
```

Whitespace around the heading is not semantically significant. Match the category/extension plus the `JKPFA_53b` installed marker, not an exact filename or exact spacing pattern.

For this profile, use the Default catalog **plus** all JKPFA_53b catalog sections present in the uploaded file. Never consult the Default-only items file as a second external source unless the user explicitly supplied it for comparison; the combined upload itself is the authority for the active installation.

The known complete combined reference contains separate Default and JKPFA_53b sections for **PT, JT, NT, and OT**, so it must activate this profile and build overlays for all four categories.

## 3.3 Effective PT/JT/NT/OT overlay rule — JKPFA_53b wins on duplicate filenames

This is a **mission-generation policy modeling what is actually installed after the JKPFA_53b library is loaded**.

Build logical catalogs separately for each overridable resource category:

```text
DEFAULT_PT      JKPFA_PT
DEFAULT_JT      JKPFA_JT
DEFAULT_NT      JKPFA_NT
DEFAULT_OT      JKPFA_OT
```

Then construct:

```text
EFFECTIVE_PT = DEFAULT_PT overlaid by JKPFA_PT
EFFECTIVE_JT = DEFAULT_JT overlaid by JKPFA_JT
EFFECTIVE_NT = DEFAULT_NT overlaid by JKPFA_NT
EFFECTIVE_OT = DEFAULT_OT overlaid by JKPFA_OT
```

Overlay key = the asset filename token, compared case-insensitively (for example `F14.PT`, `AA10.JT`, `KITT.NT`, or `BNK1.OT`). Preserve the filename spelling from the authoritative effective row when serializing.

Rules:

1. If a filename exists only in Default, keep the Default entry.
2. If a filename exists only in JKPFA_53b, add the JKPFA_53b entry.
3. If the **same PT, JT, NT, or OT filename** exists in both Default and JKPFA_53b, the JKPFA_53b entry is authoritative. The Default semantic/name mapping for that filename is inactive and must not be used for mission generation.
4. This precedence applies both when the user gives an exact filename and when the user names an asset in natural language. The final natural-language index must be built from the effective catalogs, not from Default and JKPFA independently.
5. Do not let an overwritten Default description remain as an active search alias. Otherwise a request such as an aircraft, ship, vehicle, scenery object, or weapon name could resolve to a filename whose installed JKPFA meaning is different.
6. Mission serialization still writes only the actual effective filename token, for example `type F14.PT`, `hardpoint ... AA10.JT`, `type KITT.NT`, or `type BNK1.OT`.
7. If a JKPFA overlay itself lists the same filename multiple times with different descriptive labels, treat it as **one installed filename with multiple JKPFA-side lookup aliases/descriptions**. Do not resurrect the Default meaning. Serialization cannot distinguish those labels because the mission contains only the filename token.
8. If the user's natural-language request is ambiguous among multiple labels that serialize to the same filename, emit that filename only when the requested behavior is otherwise supported; do not invent a hidden variant selector that is not represented in `.M` syntax.
9. `*.GAS` entries follow the active ordnance-section profile for availability. In the known complete combined reference the listed external tanks are Default-side entries; keep them unless a JKPFA same-name tank override is explicitly present in the uploaded file. Never invent a tank filename.

### Installed-library interpretation examples

These examples describe the **precedence mechanism**, not hard-coded asset knowledge:

```text
Default:  F14.PT   <default description>
JKPFA:    F14.PT   <JKPFA description>
Effective -> F14.PT uses the JKPFA description/meaning

Default:  KITT.NT  <default description>
JKPFA:    KITT.NT  <JKPFA description>
Effective -> KITT.NT uses the JKPFA description/meaning

Default:  BNK1.OT  <default description>
JKPFA:    BNK1.OT  <JKPFA description>
Effective -> BNK1.OT uses the JKPFA description/meaning
```

Do not hard-code the descriptions shown by a previous items file. Re-read the uploaded reference each request because a future library/version may redefine the same filename differently.

## 3.4 Non-overlaid categories and catalog scope

For `*.LAY`, `*.T2`, country ordering, and any category for which the uploaded reference does **not** provide a JKPFA overlay section, preserve the prior rule: resolve only from entries actually present in the uploaded items reference or from a higher-authority verified sample. Do not fabricate a JKPFA overlay for a category merely because the active profile is `DEFAULT_PLUS_JKPFA_53B`.

In particular:

- PT/JT/NT/OT use explicit overlay behavior whenever both Default and JKPFA sections are present.
- A category absent from JKPFA remains Default-only for that category.
- A JKPFA-only filename is valid only if it is actually listed in the uploaded combined reference.
- **v21 split-carrier exception:** the exact carrier/Tower tokens `ESSE.NT`/`ESSET.OT`, `CDEG.NT`/`CDEGT.OT`, `INVN.NT`/`INVNT.OT`, `ELIZ.NT`/two `ELIZT.OT`, and `KUZN.NT`/`KUZNT.OT` are independently verified by the supplied `CV.M` working sample. Under `DEFAULT_PLUS_JKPFA_53B`, that higher-authority v21 sample is sufficient to validate these exact tokens even if an auxiliary combined `FA_items` inventory omits them. This is a narrow exception only for the listed split-carrier assets and does not authorize guessing any other absent JKPFA filename.
- Asset availability is request-local. Do not carry an effective catalog from one user's earlier upload into a later mission that supplies a different items reference.

Examples verified from the reference/sample set include:

```text
F14.PT       F-14D Tomcat
E2.PT        E-2C Hawkeye
E3.PT        E-3 AWACS Sentry
AC130.PT     AC-130U Spectre
MIG29.PT     MiG-29 Fulcrum-C
TU26.PT      Tu-26 Backfire-C
KITT.NT      Kitty Hawk
CUB.T2       Cuba
day2.LAY     normal day, green terrain
```

These examples are illustrative only; when the JKPFA profile is active, a same-filename JKPFA row overrides the corresponding Default description above.

Do not assume that a real-world aircraft/vehicle/scenery/weapon name maps to an obvious filename. Search the **active effective catalog** first.

**Fuel and hardpoint line syntax is supported by user-provided working examples, with an inherited only-`*.PT` object-type generation gate and a v15 station/fuel policy.** Only an aircraft object whose `type` filename ends in `*.PT` may receive appended `fuel` / `hardpoint` lines. Do not emit those lines for `*.JT`, `*.OT`, `*.NT`, or other object extensions unless a later explicit working differential revises this policy. On an eligible object, the editable hardpoints are exactly 4–5 (fuselage) and 6–8 (wing); hardpoints 1–3 are reserved and hardpoint 9 is prohibited. Resolve all hardpoint items from the **active effective ordnance catalog**. Weapons/equipment placed on hardpoints must use valid `*.JT` tokens; verified external tanks may use valid `*.GAS` tokens. Under v15, `fuel` may be emitted automatically when mission requirements justify an override; explicit user fuel values take precedence. See Sections 9.5–9.6.

---

# 3.5 Companion map reference: `<MAP>.MM.txt` (logical `.MM`) — REQUIRED WHEN PROVIDED

For each map, the user may provide a companion Mission Map file corresponding to the selected `.T2`. The current upload/storage naming convention appends `.txt` to the original `.MM` filename, for example:

```text
CUB.T2  ->  CUB.MM.txt
NSK.T2  ->  NSK.MM.txt
APA.T2  ->  APA.MM.txt
```

The final `.txt` suffix does **not** change the internal file format or semantics. Strip/ignore only that final transport suffix for logical identification and parse the contents exactly as the original Fighters Anthology `.MM` data. In this skill, later references to “`.MM` data”, “the `.MM`”, or an “`.MM` anchor” mean the logical Mission Map content even when the uploaded physical filename ends in `.MM.txt`.

The actual uploaded filename may also contain a copy/version suffix before `.MM.txt`, such as `CUB(4).MM.txt`. For backward compatibility, a legacy direct `.MM` upload may still be read if supplied. **Do not rely on the filename alone.** Open the file and verify its internal header, for example:

```text
map cub.T2
```

The internal `map <basename>.T2` line is authoritative for map matching. A matching `.MM.txt` / logical `.MM` is a **map-local reference database**, not a template that should be pasted wholesale into the mission. Read it before choosing coordinates for airfields, cities, defenses, landmarks, or other map-related placement.

## 3.5.1 What to extract from `.MM`

The observed logical `CUB.MM` sample (now uploaded as a filename such as `CUB.MM.txt`) contains ordinary `obj` blocks with useful map-default fields such as:

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

It also contains map-default combat units for which fields such as these may be present:

```text
skill ...
react ...
searchDist ...
```

And it may contain `special` named map labels, for example named regions or seas, with a position and display metadata. In the observed Cuba sample, examples include map labels for Cuba, the Straits of Florida, and the Caribbean Sea.

For mission-generation purposes, build an in-memory index of at least:

- object `type`
- `name` when present
- `pos X Y Z`
- `angle`
- `nationality3`
- `flags`
- `speed`
- `alias`
- `skill`, `react`, and `searchDist` when present
- `special` marker `name` and `pos`

Do not require every object to have every field. Static scenery commonly has fewer behavior fields than combat-capable `.NT` objects.

## 3.5.2 What `.MM` is used for

Use the companion `.MM` to:

1. Resolve user references to named places on the map, such as an airfield, city, sea, or region.
2. Obtain exact map coordinates and heading/orientation for known runways/airfields and other default objects.
3. Determine the map-default nationality of a named installation/object rather than guessing from real-world knowledge.
4. See which SAM/AAA/vehicle/scenery objects already exist in the map near the mission area.
5. Place newly generated dynamic units plausibly around an existing airfield, city, defense site, or other known anchor.
6. Avoid placing generated objects directly on top of default map objects or in obviously invalid terrain/geometry when the `.MM` provides enough context.
7. Use named `special` markers as rough geographic anchors when the user gives a regional description rather than raw coordinates.

When a user says, for example, “start at Key West” or “place fighters at San Antonio,” first search the matching `.MM` by object name and use its exact `pos`/`angle` as the location anchor. Do not substitute a hard-coded Cuba anchor when the named place exists in the supplied `.MM`.

## 3.5.3 Do not duplicate the entire map into `.M`

The `.MM` contains the map's **default** objects. The generated mission `.M` should normally contain only mission-specific/dynamic objects and explicit mission additions.

Therefore:

- Do **not** emit all `.MM` `obj` blocks into the generated `.M`.
- Do **not** duplicate an airport, city, tower, bunker, SAM, AAA, or scenery object merely because it appears in `.MM`. **Under v20, do not duplicate a confirmed `.MM` ground object solely to make it targetable for bombing; use its confirmed `.MM` alias directly when it is the intended bombing target.**
- Do not rewrite map-default object skills/flags/reactions merely to satisfy the generation defaults in this skill. The “all units Expert” policy applies to **objects generated into the mission `.M`**, unless the user explicitly asks to modify/duplicate a map-default object through a verified mechanism.
- If the scenario needs an additional unit at an existing site, use the `.MM` object as the **anchor/reference**, then create only the new dynamic unit(s).

## 3.5.4 Alias safety

Aliases found in the `.MM` belong to map-default objects. Treat them as reserved while planning the mission. Generated mission aliases should remain unique and should not intentionally collide with any alias read from the `.MM`.

**v20 bombing exception:** for bombing target assignment, confirmed ground-object aliases from the supplied matching `.MM` are valid direct `preferredTargetId2` / `w_preferredTargetId2` references. Read the exact alias, type, position, and target-area relationship from that `.MM`; never invent or transplant an alias from another map. The older cross-file prohibition remains only for **non-bombing** Target/Protect behavior that has not otherwise been verified or overridden.

## 3.5.5 Terrain-only sections are not mission syntax

The observed `.MM` also contains non-object sections such as:

```text
tmap ...
tdic ...
```

Their detailed encoding is not decoded and is **not required** to generate a normal `.M` mission. Ignore these sections for mission serialization. Do not copy `tmap`/`tdic` data into `.M`.

## 3.5.6 Map reference priority

When choosing a map-specific anchor, use this order:

1. exact raw coordinate explicitly supplied by the user
2. exact named-object / `special` position from the matching supplied `.MM`
3. position from a supplied working `.M` reference
4. a legacy verified anchor documented in this skill
5. if none exists, ask for the companion `.MM.txt` (logical `.MM`) or another map anchor

The companion map is expected to be supplied as an extra `<MAP>.MM.txt` file for future mission-generation requests. Read its logical `.MM` content fresh for each request; do not assume that Cuba's objects or coordinates apply to another map.

---

# 4. Physical file format — REQUIRED

A usable `.M` file is not merely ordinary UTF-8 text. The paired `.MT` file is a separate plain-text format with different termination rules.

## 4.1 Encoding

Use ASCII-compatible bytes.

All syntax and tested names are ASCII. If the user supplies non-ASCII unit/waypoint names, transliterate them to ASCII unless a verified Fighters Anthology encoding sample is available.

## 4.2 Line endings

Use Windows CRLF:

```text
\r\n
```

Do not normalize to LF-only when writing the actual game file.

## 4.3 String delimiter

Fighters Anthology mission strings use byte `0x01` (SOH) as the delimiter, not ASCII quotation mark `0x22`.

Conceptual display:

```text
name <SOH>Player<SOH>
w_name <SOH>CAP-A<SOH>
```

Actual bytes:

```text
name \x01Player\x01
w_name \x01CAP-A\x01
```

An empty string is:

```text
\x01\x01
```

Do not write literal `<SOH>` text into the mission.

## 4.4 `.M` file terminator

Append one NUL byte at end of the `.M` file:

```text
\x00
```

Prefer ending the final block with CRLF, optionally one blank CRLF, then NUL.

## 4.5 Hex syntax

Mission hex values use a dollar prefix:

```text
$0
$80
$4017
$c000
$4000ffff
```

Use lowercase hexadecimal for consistency with verified samples.

## 4.6 Block terminator

Objects and waypoint groups terminate with a tab-indented dot:

```text
	.
```


## 4.6.1 v25 output filename format — REQUIRED

Before writing either physical file, choose one shared v25 output basename in the form:

```text
<STEM6><REV1>
```

The basename must be exactly seven characters and match:

```text
^[A-Z0-9]{6}[1-9A-Z]$
```

Use exactly six uppercase ASCII alphanumeric characters for the mission stem and one final revision symbol. The revision order is `1` through `9`, then `A` through `Z`. First generation uses `1`; each user-requested modification of the same mission advances the final symbol by one step while retaining the six-character stem.

Write the pair with the identical basename:

```text
TOPGUN1.M
TOPGUN1.MT
```

After one modification:

```text
TOPGUN2.M
TOPGUN2.MT
```

After revision `9`, use revision `A`. Do not use revision `0`. Do not silently roll over after `Z`; request a new stem or explicit naming instruction if another revision is required.

This v25 physical-output rule supersedes the former active v16 `^[A-Z0-9]{1,8}$` generation rule. Legacy files with older names remain valid evidence and may be read/preserved as source material, but newly generated v25 mission output must use the seven-character revisioned form above.

## 4.7 `.MT` physical format — CONFIRMED FROM `~B08.MT` AND `~E39.MT`

The paired mission briefing file uses the **same basename** as the mission file:

```text
MISSION.M   -> MISSION.MT
~B08.M      -> ~B08.MT
~E39.M      -> ~E39.MT
```

Write `.MT` as ASCII-compatible plain text using Windows CRLF line endings.

Unlike `.M`:

- `.MT` uses ordinary printable text; it does **not** use SOH (`0x01`) string delimiters.
- `.MT` does **not** append a final NUL byte in the two verified samples.
- End the file with a normal CRLF after the final debrief sentence.
- Keep generated briefing text ASCII unless a later verified sample proves another encoding is supported.

---

# 5. Top-level mission layout

Generate blocks in this order:

1. Header/world settings, including briefing-enable lines immediately after `textFormat`
2. `sides4` table
3. Time/global skill/era settings
4. All `obj` blocks
5. All `waypoint2` blocks
6. Final NUL byte

Verified header pattern:

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
usGroundSkill 1
usAirSkill 1
themGroundSkill 1
themAirSkill 1
historicalera 4
```


## 5.1 Briefing-enable header lines — REQUIRED WHEN GENERATING THE PAIRED `.MT`

To make the mission briefing available, emit these **three lines immediately after `textFormat` and before `map`**:

```text
textFormat
brief
briefmap
armplane
map <MAP>.T2
```

This is a required generation rule for missions produced by this skill.

The two supplied working `.M` examples (`~B08.M` and `~E39.M`) also contain:

```text
selectplane
```

between `briefmap` and `armplane`. That extra line is sample-observed but is **not made mandatory by this skill**, because the requested confirmed change is specifically the three-line set `brief`, `briefmap`, `armplane`. If a higher-authority working mission/template supplied for a future request requires `selectplane`, preserve it.

## Conservative defaults

When the user does not specify these values and the mission is on Cuba, the following tested defaults are acceptable:

```text
map cub.T2
layer day2.LAY 0
clouds 0
wind 65 7
time 12 0
usGroundSkill 3
usAirSkill 3
themGroundSkill 3
themAirSkill 3
historicalera 4
```

`view` is believed to be an editor-view setting rather than combat logic. If no reference mission supplies it, use:

```text
view 4149 <mission_center_x> <mission_center_z>
```

where mission center is the approximate average of major object positions.

Do not claim that the first `view` number has been decoded.

---


# 5.5 Paired `.MT` briefing/debriefing file — REQUIRED

Whenever this skill generates a mission `.M`, it must also generate a **same-basename `.MT` file** that briefly explains the mission. The two supplied examples, `~B08.MT` and `~E39.MT`, establish the following four-section structure.

## 5.5.1 Section 1 — mission identification

Use:

```text
.section 1
<mission-id>  (<mission-basename>)
<MISSION TITLE>  (<map/region label>)
<Mission type/source label>
```

Generation rules:

- `<mission-basename>` must correspond to the `.M` / `.MT` basename; preserve a leading `~` when one exists.
- **v25 supersession for generated output:** the historical `~` preservation rule above applies only when interpreting/preserving legacy sample text. A newly generated v25 `.M` / `.MT` pair must instead use the exactly seven-character revisioned basename matching `^[A-Z0-9]{6}[1-9A-Z]$`, so a leading `~` is removed and a six-character stem plus the current revision symbol is generated.
- If the user does not supply a campaign-style mission ID, source label, or parenthetical region label, generate conservative descriptive ASCII text rather than inventing a historical campaign code.
- Do not claim that the exact semantics of sample IDs such as `AB08` / `AE39` or `ATFGOLD` are decoded; they are presentation text in these samples.

## 5.5.2 Section 2 — briefing

Verified formatting directives include:

```text
.section 2
.center .underline .header
<MISSION TITLE>
..underline .left .body

<BASE / OPERATING AREA>
DATE :  <date>
LOCAL  TIME :  <HHMM>
WEATHER :  <brief weather description>

.underline .header
SITUATION
..underline .body
<situation paragraph>

.underline .header
MISSION OBJECTIVE
..underline .body
<objective paragraph>

.underline .header
THREAT SUPPRESSION DATA
..underline .body
GROUND  OPPOSITION :  <known threats or Unknown>

AIR  OPPOSITION :  <known threats or Unknown>
```

An optional support/intelligence block is verified by `~B08.MT`:

```text
.underline .header
ELECTRONIC INTELLIGENCE
..underline .body
SUPPORT  AIRCRAFT  :  <support assets>
```

Include optional briefing subsections only when they are useful and supported by the actual generated mission. Do not mention threats, support aircraft, locations, or objectives that are not present in the scenario/mission.

## 5.5.3 Section 3 — success debrief

Use:

```text
.section 3
.center .underline .header
DEBRIEF
..underline .left .body

<BASE / OPERATING AREA>
DATE :  <date>
MISSION :  <mission title>
RESOLUTION :  Success

<short success debrief>
```

The success text should summarize successful completion of the mission-success conditions actually encoded in the `.M`. Do not imply completion of conditions that are set to `Not affected`.

## 5.5.4 Section 4 — failure debrief

Use:

```text
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

A conservative generic failure sentence such as `You failed to complete your objectives.` is supported by both verified samples.

## 5.5.5 Briefing content synchronization — REQUIRED

The `.MT` must describe the generated `.M`, not an independent story. Keep these synchronized:

- mission title / basename identity
- map/operating area
- date/time/weather wording when supplied or derivable from the mission settings
- player role and principal objective
- friendly support explicitly present in the `.M`
- enemy air/ground threats explicitly present in the `.M`
- success/failure debrief wording versus actual `.M` mission-success conditions

If the user supplies narrative details that cannot be represented in `.M` syntax, they may still appear as non-mechanical briefing context **only if clearly framed as narrative background and not as a false encoded objective/behavior**.

---

# 6. Country indexing, `sides4`, and `nationality3`

## 6.1 Country indices — CONFIRMED ORDER

Use zero-based indices:

```text
 0 America
 1 Britain
 2 China
 3 France
 4 Germany
 5 Belgium
 6 Jordan
 7 Israel
 8 Japan
 9 North Korea
10 Russia
11 South Korea
12 Syria
13 Arab Egypt
14 Islamic Egypt
15 Estonia
16 Latvia
17 Lithuania
18 Poland
19 Belorussia
20 North Vietnam
21 South Vietnam
22 Ukraine
23 Iraq
24 Iran
25 Kuwait
26 Saudi Arabia
27 Oman
28 U.A.E.
29 Qatar
30 Bahrain
31 Libya
32 Sudan
33 Cuba
34 Panama
35 Columbia
36 Pakistan
37 India
38 Afghanistan
39 Taiwan
40 Greece
41 Turkey
42 Italy
43 Sweden
44 Finland
45 Norway
46 Spain
47 Portugal
48 Austria
49 Denmark
50 Netherlands
51 Canada
52 Bulgaria
53 Hungary
54 Romania
55 Australia
56 Philippines
57 Argentina
58 Bosnia
59 Serbia
```

The active uploaded items reference states:

- `$0` = friend
- `$80` = enemy
- four final `$0` entries are unrelated/reserved

## 6.2 `sides4`

Write exactly 64 entries:

- slots 0–59 correspond to the country table above
- slots 60–63 should be `$0`

For each country used by mission objects:

- friendly to the player: `$0`
- enemy to the player: `$80`

For unused countries, `$0` is a conservative default unless the user supplied a reference mission whose alliance table should be preserved.

## 6.3 `nationality3` — CONFIRMED FORMULA

Verified examples:

```text
America friendly -> 0
China enemy      -> 130 = 0x82 = 0x80 | 2
Russia enemy     -> 138 = 0x8a = 0x80 | 10
```

Generate:

```text
nationality3 = country_index | (enemy ? 0x80 : 0x00)
```

Do not use an enemy bit on friendly objects.

---

# 7. Coordinates, distances, altitude, speed, and heading

## 7.1 Coordinate axes — HIGH CONFIDENCE / TESTED

Mission positions are:

```text
pos X Y Z
```

Use:

- `+X` = East
- `-X` = West
- `+Z` = North
- `-Z` = South
- `Y` = altitude in feet

Horizontal internal units are effectively feet.

Use:

```text
1 nautical mile ~= 6076.12 internal units
```

This is supported by an E-2C test where an approximately 100 NM north waypoint changed primarily `Z` by about 635,000 units.

## 7.2 Relative position formula

For a point at bearing `B` degrees clockwise from north and distance `D_nm`:

```text
D_ft = D_nm * 6076.12
DX   = D_ft * sin(B)
DZ   = D_ft * cos(B)
X2   = round(X1 + DX)
Z2   = round(Z1 + DZ)
```

Examples:

- north: bearing `0`
- east: bearing `90`
- south: bearing `180` or `-180`
- west: bearing `270` or `-90`

## 7.3 Heading — HIGH CONFIDENCE

The first field of:

```text
angle H 0 0
```

is heading/yaw in degrees.

Verified:

- `0` = North
- `-180`/`180` = South
- positive rotation is clockwise; approximately `+90` = East
- `-90` = West

If the user does not supply heading, calculate it from the first intended movement vector:

```text
H = degrees(atan2(DX, DZ))
```

Normalize to a convenient range such as `[-180, 180]`.

## 7.4 Speed — HIGH CONFIDENCE

`speed` and `w_speed` are effectively feet per second.

Approximate conversion from knots:

```text
raw_fps ~= knots * 6076.12 / 3600
```

UI quantization can cause a small one-unit difference. Preserve raw values from a reference mission when possible.

Verified examples:

```text
50  fps ~= 29.6 kt
676 fps ~= 400 kt
683 fps ~= 405 kt
795 fps ~= 471 kt
```

---

# 8. Alias allocation

## CONFIRMED BEHAVIOR

Objects in verified missions use unique negative integer aliases:

```text
-1, -2, -3, ...
```

Use deterministic sequential aliases starting at `-1` in object creation order.

Rules:

- aliases must be unique
- use negative integers for all generated mission objects
- target references use the target object's alias encoded as signed 16-bit in `preferredTargetId2`
- waypoint groups use `w_for <alias>`

Do not reorder objects after computing target descriptors without recomputing all references.

---

# 9. Object block

Base tested pattern:

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

Fields should be emitted in the same general order as verified samples.

**v21 split-carrier Tower exception:** the verified `CV.M` Tower objects are intentionally shorter than the generic aircraft/combat-object pattern. For `ESSET.OT`, `CDEGT.OT`, `INVNT.OT`, `ELIZT.OT`, and `KUZNT.OT`, use the dedicated Section 18.6 Tower template (`type`, rotated `pos`, copied `angle`, `nationality3`, `flags $4011`, `speed 0`, unique `alias`, terminator) and do not invent `skill`, `react`, `searchDist`, controller, or waypoint fields that are absent from the working sample.

## 9.1 `type`

Resolve from the active uploaded items reference/effective catalog defined in Section 3, or a verified sample.

Examples:

```text
type F14.PT
type E2.PT
type E3.PT
type AC130.PT
type TU26.PT
type MIG29.PT
type KITT.NT
```

## 9.2 `controller`

Verified:

```text
controller $80
```

means human/player control.

Use it for the player aircraft only unless a later multiplayer sample provides additional controller values.

## 9.3 `skill`

Verified sample meanings include:

```text
skill 1 = average
skill 3 = Expert (verified by Mission Creator sample UI)
```

Prior documentation indicates a 0–3 scale, but if exact labels for 0 and 2 matter, prefer a verified reference rather than inventing wording.

The mission-generation default is **Expert** for every unit, friendly or hostile:

```text
skill 3
```

Only use another value when the user explicitly requests a different skill for that specific unit/group. Keep the top-level global skill defaults at `3` as well unless the user explicitly overrides them.

## 9.4 `name`

Optional for objects.

Use byte `0x01` delimiters. Keep names ASCII.

## 9.5 `fuel` — VERIFIED SYNTAX + v15 MISSION-AWARE POLICY

The verified appended syntax is:

```text
fuel <percent>
```

Interpret the value as a percentage of the object's default/internal fuel quantity when the object type is eligible for this field.

Examples of the line syntax include:

```text
fuel 50
fuel 80
```

### v15 generation rules

- **Eligibility gate:** emit `fuel` only inside an aircraft object whose `type` filename ends in `*.PT`.
- Never emit `fuel` for `*.JT`, `*.OT`, `*.NT`, or other object extensions unless a later user-provided working differential explicitly revises the only-`*.PT` rule.
- **Mission-aware use is allowed:** the generator may emit `fuel` even when the user did not mention fuel, whenever an override is useful for mission role, route length, endurance, loiter/support time, recovery, or reserve planning.
- If the user explicitly gives a fuel percentage for an eligible `*.PT` aircraft object, that value wins over automatic selection.
- Fuel remains optional; omit it when the object's default/internal fuel is suitable and no mission-specific override is needed.
- When automatically choosing fuel, use a conservative practical value in the `0–100` range; do not claim an exact fuel-burn model unless a verified sample establishes one.
- Emit the value after wing/formation fields and before any `hardpoint` lines.
- If the user requests fuel on an ineligible object type, do not silently serialize it; explain that the only-`*.PT` eligibility gate still applies.

## 9.6 `hardpoint` — VERIFIED SYNTAX + v15 STATION RESTRICTION

A loaded hardpoint override uses the verified syntax below; **v26 adds the separate empty-hardpoint form** (see the v26 override and Section 9.6.3):

```text
hardpoint <station_index> <positive_quantity> <item_file>
hardpoint <station_index> 0 
```

Legacy working examples establish the serialization form, for example:

```text
hardpoint 4 4 AIM54C.JT
hardpoint 5 2 F250.GAS
hardpoint 6 2 AIM7.JT
hardpoint 7 2 AIM9M.JT
```

These lines remain syntax evidence. Append `hardpoint` lines only to an aircraft object whose own `type` filename ends in `*.PT`. Do not apply them to `*.JT`, `*.OT`, `*.NT`, or other object extensions unless a later explicit working differential revises the only-`*.PT` rule.

### 9.6.1 v15 hardpoint topology — ELIGIBLE `*.PT` AIRCRAFT OBJECTS ONLY

For an eligible `*.PT` aircraft object:

```text
hardpoint 1-3 = reserved / never modify
hardpoint 4-5 = fuselage hardpoints
hardpoint 6-8 = wing hardpoints
hardpoint 9   = prohibited / never use
```

Rules:

- Hardpoints 1, 2, and 3 are reserved and must never be emitted as overrides.
- Hardpoints 4 and 5 are editable fuselage stations.
- Hardpoints 6, 7, and 8 are editable wing stations.
- **Hardpoint 9 must never be emitted**, whether requested by the user, selected by an automatic loadout, or shown as editable in an older skill version.
- Therefore the only valid v15 override station indices are `4`, `5`, `6`, `7`, and `8`.
- Do not enforce real-world pylon compatibility, weight, symmetry, launcher, electrical-bus, clearance, nationality, or historical-era restrictions on the allowed stations 4–8.
- The `quantity` field must be a positive integer **for an equipped station**; under v26, an explicitly empty station uses `0` with no item token and a mandatory trailing ASCII space after `0`.
- Every emitted item token must exist in the active effective ordnance catalog or in a higher-authority working sample. Weapon/equipment hardpoint items use `*.JT`; verified external tanks may use `*.GAS`. Never invent an item filename.
- Do not emit any hardpoint override on `*.JT`, `*.OT`, `*.NT`, or any other ineligible object extension.

### 9.6.3 v26 explicit empty stations and multiple weapons on one station

- **Empty:** `hardpoint <station> 0 `, where the line finishes with a mandatory ASCII trailing space after `0` and no equipment filename. Do not trim this line. The explicit zero overrides the station to be empty; it is not equivalent to leaving the hardpoint line out.
- **Equipped:** `hardpoint <station> <positive_quantity> <item_file>`. A positive quantity may be greater than one, e.g. `hardpoint 5 4 AIM9D.JT` mounts four of that item on station 5. A single station may thus carry multiple rounds of the same item, without duplicating the station line.
- **Scope:** Only existing editable aircraft stations `4`–`8` on `*.PT` objects. All inherited catalog/type rules remain unchanged.
- **Priority:** Explicit user-supplied zeros and positive counts override automatic loadout choices. Never auto-fill an explicitly empty station. Preserve the exact quantity.
- **Serialization check:** After writing the `.M` file, inspect the raw bytes of each empty override, checking that a `0` is directly followed by an ASCII space and a line break. General-purpose trailing-whitespace normalization must exempt these lines.

### 9.6.2 Automatic mission-role loadout generation — TYPE-GATED

If the user gives exact hardpoint mappings for allowed stations 4–8 on an eligible `*.PT` aircraft object, those mappings win and must be emitted exactly. Hardpoints 1–3 remain untouched and hardpoint 9 remains forbidden. If the user asks for station 9, do not serialize it; use only valid stations 4–8.

If no exact hardpoint mapping is supplied, the generator may build a mission-role-aware hardpoint 4–8 loadout **only when the aircraft object is eligible under the only-`*.PT` type gate**. Candidate items must come from the active effective ordnance catalog. Weapon/equipment candidates use valid `*.JT` tokens; verified external tanks may use valid `*.GAS` tokens.

Role guidance remains:

- CAP / BARCAP / escort / fighter sweep / air superiority / interception: prioritize catalog-identified air-to-air weapons.
- Strike / bombing / interdiction / attack / CAS: prioritize catalog-identified air-to-ground weapons while retaining self-defense weapons when useful.
- SEAD / DEAD: prioritize catalog-identified suppression weapons; do not invent an anti-radiation token.
- Anti-ship / maritime strike: prioritize catalog-identified anti-ship weapons, otherwise supported heavy strike ordnance.
- Recon / electronic-support / special equipment: use catalog-identified pods/equipment only when representable with the verified hardpoint syntax.
- Multirole or ambiguous combat task: choose a balanced supported loadout.

**Fuel is independent of hardpoint generation but may be mission-aware.** An automatic hardpoint loadout may be accompanied by an automatically selected `fuel` override when mission needs justify it; neither one requires the other.

Recommended field order on an eligible object:

```text
wing ...
.. formation fields ...
fuel ...        # optional; explicit or mission-aware automatic override
hardpoint ...  # stations 4-8 only
hardpoint ...
.
```

---

# 10. Object `flags`

## 10.1 Known base pattern

A normal object with:

- Mission success: Not affected
- Other objects can attack it
- Shown in briefing map
- zero-minute start delay

has been observed as:

```text
flags $4017
```

Treat `$4017` as the **tested standard base flags** for this state, not as a universal semantic constant whose internal low bits are all decoded.

**v21 split-carrier Tower exception:** the dedicated Tower objects in `CV.M` use `flags $4011`, not the ordinary `$4017` base. Preserve `$4011` for `ESSET.OT`, `CDEGT.OT`, `INVNT.OT`, both `ELIZT.OT` objects, and `KUZNT.OT` unless a later higher-authority differential changes the Tower pattern. Do not run these attached Tower objects through the ordinary mission-success/briefing-visibility flag composer.

## 10.2 Mission-success bits — CONFIRMED

Differential tests established:

```text
0x0020 = Survive
0x0080 = Destroyed
```

Therefore, with the standard tested base:

```text
Not affected -> $4017
Survive      -> $4037
Destroyed    -> $4097
```

Use bit composition:

```text
flags = 0x4017 | success_bit
```

Only one mission-success state should normally be chosen for an object.

Mission conditions in the tested Cold War scenario behaved as jointly required conditions: carrier survives + all four F-14s survive + both Tu-26s destroyed.

## 10.3 Briefing-map visibility and Ignore-me bits — CONFIRMED

A single-variable differential F-14 test established the briefing-map visibility bit:

```text
Shown on briefing map     -> flags $4017
Hidden on briefing map    -> flags $4417
```

The only flag difference is:

```text
$4017 XOR $4417 = $0400
```

Therefore:

```text
0x0400 = Hide in briefing map
```

A previously verified test changed the same standard-base F-14 to both:

- Other objects ignore me
- Hide in briefing map

and produced:

```text
flags $4617
```

Since `0x0400` is now isolated as Hide in briefing map, the remaining bit in the verified combined difference is:

```text
0x0200 = Ignore me
0x0400 = Hide in briefing map
0x0600 = Ignore me + Hide in briefing map
```

Safe composition rules:

- normal visible/attackable object: preserve the tested base/state flags without `0x0200` or `0x0400`
- Ignore me only: OR `0x0200`
- Hide in briefing map only: OR `0x0400`
- both Ignore me and Hide in briefing map: OR `0x0600`
- mission-success bits (`0x0020` Survive / `0x0080` Destroyed) compose independently with these visibility/ignore modifiers

Examples using the normal tested Not-affected base:

```text
Visible, attackable, Not affected -> $4017
Hidden,  attackable, Not affected -> $4417
Visible, Ignore me, Not affected  -> $4217
Hidden,  Ignore me, Not affected  -> $4617
```

Mission-success examples with hidden briefing-map status:

```text
Hidden + Survive   -> $4437   # $4017 | $0400 | $0020
Hidden + Destroyed -> $4497   # $4017 | $0400 | $0080
```

### Required enemy briefing-map generation policy

Unless the user explicitly requests otherwise, every **hostile/enemy object generated into the mission `.M`** must have `0x0400` set so that it does **not show on the briefing map**.

Apply this as a modifier, not as a replacement constant:

```text
if object_is_enemy and user_did_not_request_brief_map_visibility:
    flags |= 0x0400
```

This rule applies to enemy aircraft, ships, vehicles, defenses, scenery/mission objects, and automatically added hostile ambient units that are serialized as mission `obj` blocks. Preserve any valid mission-success, Ignore-me, or other confirmed flag modifiers while adding the hide bit.

Friendly and player-side mission objects remain shown on the briefing map by default unless the user explicitly asks to hide them.

The paired `.MT` file has no verified object-level visibility bit. Continue generating its normal briefing/threat text from the actual scenario; do **not** invent an `.MT` directive to hide an object. The no-show behavior is encoded in the `.M` object's `flags`.

## 10.4 Player-wing mission-success policy — REQUIRED GENERATION RULE

Every object that belongs to the **player's own wing/group** must always have Mission Success set to **Not affected**.

This includes:

- the human-controlled player aircraft (`controller $80`)
- every AI wingman sharing the player's `wing <wing_id> ...`

Do **not** set `Survive` or `Destroyed` mission-success bits on any player-wing member, even when an older sample mission did so. This is a generation-policy override.

With the normal tested visible/attackable base state, use:

```text
flags $4017
```

Equivalently, ensure both mission-success bits are clear:

```text
flags &= ~0x0020
flags &= ~0x0080
```

If other known flag modifiers are present (for example `0x0200` Ignore me or `0x0400` Hide in briefing map), preserve those modifiers while keeping both success bits clear. Player-wing objects remain briefing-map visible by default unless the user explicitly requests them hidden.

## 10.5 Start delay

Only zero-minute delay is decoded in the current samples. Do not invent nonzero-delay encoding.

---

# 11. Reaction encoding: `react` and `w_react`

## 11.1 Structure — CONFIRMED

Both object-level and waypoint-level reactions use:

```text
react   <ATTACK_MASK> <DEFEND_MASK> <EVADE_MASK>
w_react <ATTACK_MASK> <DEFEND_MASK> <EVADE_MASK>
```

For a target class:

- Attack: its bit/group appears in word 1
- Defend: its bit/group appears in word 2
- Evade: its bit/group appears in word 3
- Ignore: its bit/group appears in none of the three words

## 11.2 Confirmed individual class masks

The earlier differentials plus the v25 `1.M` A-F differential establish all nine visible Mission Creator target-class masks:

```text
Fighter   = $8000
Bomber    = $4000
Ship      = $2000
SAM       = $1000
AAA       = $0800
Tank      = $0400
Vehicle   = $0200
Structure = $0100
Other     = $0040
```

`1.M` confirms SAM/Tank/Vehicle/Structure by starting from all-Attack and moving exactly one class bit to Defend at A/C/D/E; it independently reconfirms AAA and Other at B/F. The remaining low raw bits included by `$ffff` still have no individual Mission Creator semantic names confirmed here. Do not invent meanings for those bits.

### 11.2.1 v25 `1.M` exact one-class-Defend / all-else-Attack presets

```text
A: SAM Defend       -> w_react $efff $1000 $0
B: AAA Defend       -> w_react $f7ff $800  $0
C: Tank Defend      -> w_react $fbff $400  $0
D: Vehicle Defend   -> w_react $fdff $200  $0
E: Structure Defend -> w_react $feff $100  $0
F: Other Defend     -> w_react $ffbf $40   $0
```

In the supplied file, all six visible points also use `w_goal 1`, `w_searchDist 10`, and `w_preferredTargetId2 $0`. Treat those as part of the exact `1.M` test setup, not as mandatory values for every future reaction configuration.

## 11.3 Verified complete reaction presets

Use these patterns when they match the user's intent.

### Fighter/Bomber Attack; everything else Ignore

```text
react $c000 $0 $0
```

### Fighter/Bomber Evade; everything else Ignore

```text
react $0 $0 $c000
```

### Fighter/Bomber Attack; remaining tested UI categories Defend

```text
react $c000 $3fff $0
```

### All categories Defend

```text
react $0 $ffff $0
```

### Test preset B

UI:

```text
Fighter    Ignore
Bomber     Evade
Ship       Attack
SAM        Defend
AAA        Defend
Tank       Defend
Vehicle    Defend
Structure  Defend
Other      Attack
```

Raw:

```text
react $2040 $1fbf $4000
```

### Test preset C

Same as preset B, except AAA = Attack:

```text
react $2840 $17bf $4000
```

### Historical Cold War ship-attack reaction (not the v22 generic Anti-ship Assignment preset)

```text
w_react $2000 $c000 $0
```

Meaning at minimum:

- Ship = Attack
- Fighter = Defend
- Bomber = Defend

This remains a valid verified reaction from the older Cold War mission, but v22 `assignment.M` separately confirms the Mission Creator **Anti-ship Assignment** baseline as `w_react $2000 $8000 $0` with `w_searchDist 0` for **no target / until waypoint is reached**. Do not overwrite either working sample; choose the v22 preset when the user explicitly selects the v22 Anti-ship Assignment UI behavior, and preserve the historical Cold War tuple when reproducing that older sample/context.

## 11.4 v22 verified waypoint Assignment presets

For the v22 advanced waypoint Assignment selector, the baseline no-target / until-waypoint-reached presets are:

| Assignment | `w_react` | `w_searchDist` |
|---|---|---:|
| Normal Flight | `$0 $8000 $0` | `0` |
| MIGCAP | `$8000 $0 $0` | `25` |
| BARCAP | `$c000 $0 $0` | `25` |
| Wild Weasel | `$1800 $8000 $0` | `10` |
| CAS | `$400 $9800 $0` | `5` |
| Anti-ship | `$2000 $8000 $0` | `0` |
| Hi/Lo sweep | `$ffff $0 $0` | `10` |

These are full verified presets; unresolved component masks inside presets such as Wild Weasel or CAS still do not authorize independently guessing the meaning of every individual bit.

The exact targeted Hi/Lo-sweep tuples in the v22 override remain authoritative when Duration is `until target is attacked/damaged/destroyed`; in particular, the damaged/destroyed rows use `$c000 $0 $0` with search distance `25` rather than the baseline `$ffff $0 $0` / `10` tuple.

## 11.5 v18 all-object attack preset for bombing / airfield strikes

The verified reaction structure places attacked target classes in word 1, and the verified "All categories Defend" preset demonstrates that `$ffff` represents the complete category set when placed in word 2. Under the v18 bomb-target policy, use the corresponding all-object attack form when a bomb-carrying aircraft must attack an airfield/ground installation rather than a parked aircraft-class target:

```text
react   $ffff $0 $0
w_react $ffff $0 $0
```

Use `w_react $ffff $0 $0` on the bombing attack waypoint. Object-level `react $ffff $0 $0` may also be used when the entire aircraft task should treat all object classes as attack candidates. This v18 policy is specifically intended to provide valid ground/facility targets for bomb loads; it must not be used as a reason to assign a bomb directly to an aircraft alias.

**v19 persistence override:** for repeated/high-altitude bombing, the waypoint-level form is not confined to the explicit Attack point. Beginning with the first bombing Attack waypoint, every waypoint still inside the active bombing sequence must retain `w_react $ffff $0 $0`, including Turn/post-attack/between-pass/realignment waypoints and ordinary `w_goal 1` repositioning points before a later Attack. Do not restore `w_react $0 $ffff $0` (All Defend) on those intermediate points while another bombing pass is pending. Only after the final planned pass is complete, the bomber has left the active target/hostile area, and no further bombing attack remains pending may subsequent safe-navigation waypoints return to an ordinary verified reaction. This is a waypoint-reaction persistence rule; object-level `react` remains governed by the existing task-level policy.

## 11.6 Custom reaction policy

If the user requests a custom reaction combination:

1. All nine visible Mission Creator classes listed in Section 11.2 now have confirmed individual masks, including `SAM=$1000`, `Tank=$0400`, `Vehicle=$0200`, and `Structure=$0100` from v25 `1.M`.
2. Prefer editing those confirmed class bits against a verified complete baseline. For example, `1.M` proves that an all-Attack baseline may move exactly one known class bit into Defend while the rest of the raw mask remains in Attack.
3. Do not assign semantic names to the remaining low raw bits inside `$ffff`. Preserve those still-undecoded bits in the same action word as the chosen verified baseline unless a later differential isolates them.
4. Reaction semantics apply to object-level `react` and waypoint-level `w_react` wherever those fields are valid. For navigation-point planning, tailor reactions to mission role; the A-F `1.M` pattern is a reference differential, not a mandatory doctrine.

---

# 12. Search distance

Verified:

```text
searchDist 0
```

corresponds to Mission Creator text:

```text
Search for targets at any distance.
```

`searchDist 25` is strongly consistent with a 25-NM search setting and is used repeatedly in tested combat missions.

Rules:

- explicit “any distance” -> `0`
- explicit tested numeric value -> write that number
- if omitted for a combat unit -> `25` is a conservative tested default
- **v22 waypoint Assignment override:** when the user selects a verified v22 Assignment, use that Assignment tuple's exact `w_searchDist` instead of the generic `25` fallback; exact targeted Hi/Lo-sweep tuples also keep their tested search values

Waypoint search range uses:

```text
w_searchDist <value>
```

---

# 13. Assigned targets and protection: `preferredTargetId2`

This mechanism is one of the most strongly decoded features.

## 13.1 Direct Target — CONFIRMED

If an object directly targets another object, encode the target alias as a signed 16-bit value in the low 16 bits.

Examples:

```text
Target alias -1 -> preferredTargetId2 $ffff
Target alias -3 -> preferredTargetId2 $fffd
```

Use:

```text
target16 = alias & 0xffff
preferredTargetId2 = target16
```

## 13.2 Protect — CONFIRMED FOR TESTED FORM

Protecting alias `-1` produced:

```text
preferredTargetId2 $4000ffff
```

Use:

```text
preferredTargetId2 = 0x40000000 | (alias & 0xffff)
```

Examples:

```text
Protect alias -1 -> $4000ffff
Protect alias -3 -> $4000fffd   # inferred by the confirmed encoding rule
```

The `0x40000000` bit distinguishes Protect from ordinary Target in the tested samples.

## 13.3 No assigned target

Omit object-level `preferredTargetId2` when there is no direct Target/Protect assignment, matching tested object blocks.

Waypoint records always include:

```text
w_preferredTargetId2 $0
```

when no waypoint target is assigned.

## 13.4 Waypoint target

Waypoint target descriptors use the same signed-alias low-16-bit scheme.

Cold War sample:

```text
w_goal 16
w_preferredTargetId2 $ffff
```

The target alias `-1` is the Kitty Hawk carrier.

Under v22, this is a waypoint directed at that specific carrier with `w_goal 16 = until target is destroyed`; the tactical Anti-ship Assignment is encoded separately by the waypoint reaction/search behavior. It is not a wildcard.

## 13.5 Object Target/Protect requires no waypoint

Verified target/protect aircraft can have no waypoint block at all. The AI can dynamically follow/chase the assigned object.

Use this for simple:

- “Fighter protects AWACS”
- “Interceptor targets AWACS”
- “Attacker targets a specific aircraft”

when no explicit route is requested.

## 13.6 v18 bomb-load aircraft-target restriction

For a bombing task, a `*.PT` aircraft object is not a valid direct bomb target even if its altitude is `0` or it is visually parked on an airfield. Therefore:

- do not set object-level `preferredTargetId2` to a parked-aircraft alias for the bombing task;
- do not set the bombing waypoint's `w_preferredTargetId2` to a parked-aircraft alias;
- for an airfield strike intended to destroy parked aircraft, use the v18 all-object attack reaction at the target-area Attack waypoint so the bomber attacks airport facilities/ground objects instead; under v19, once that first bombing Attack waypoint begins the active bombing sequence, retain the same `w_react $ffff $0 $0` reaction on every intervening Turn/realignment/subsequent Attack waypoint until the attack-reaction corridor is allowed to end;
- under v20, do **not** force `w_preferredTargetId2 $0` merely because the intended valid ground target is map-default rather than mission-generated. Active bombing-sequence waypoints may use specific non-aircraft ground targets from the generated `.M` **or the confirmed matching `.MM`**, and successive bombing-related waypoints should use different valid targets when enough are available;
- a confirmed matching-map `.MM` ground-object alias is valid for bombing `preferredTargetId2` / `w_preferredTargetId2`; verify alias, type, position, and relationship to the requested target area from the supplied `.MM`. Never invent an `.MM` alias or assume another map's coordinates.

This restriction is task-specific. The same aircraft may still have separate air-to-air reactions/assignments for missiles or guns when appropriate; v18 only prevents the **bombing attack** from being bound to an aircraft-class target.

---

# 14. Wing grouping

Verified structure:

```text
wing <wing_id> <member_index>
```

Example four-ship:

```text
wing 0 0
wing 0 1
wing 0 2
wing 0 3
```

Use:

- member `0` = leader
- members increase from 0
- assign a unique wing ID per generated formation

## 14.1 Player wingmen

In the tested four-F-14 player wing, AI wingmen had:

```text
npcFlags 2
```

The player aircraft did not.

Use `npcFlags 2` for AI members of a player-controlled wing when reproducing this tested pattern.

Do not add it to unrelated enemy AI formations without evidence.

## 14.2 `wng` / `w_wng` — v12 four-setting model with v17 spacing default

The formation tuple is no longer treated as an opaque preset. For navigation points, the user-facing controls are:

1. `formation`: `Echelon`, `Line abreast`, `Line astern`
2. `spacing`: `far`, `near`
3. `stacking`: `level`, `high`, `low`
4. `control`: `loose`, `medium`, `tight`

Six named differential missions are currently available and differ only in these formation-behavior settings (plus the resulting dependent formation geometry):

```text
Echelon_far_level_loose.M        -> visible waypoint w_wng 1 0 2048 0
Echelon_near_high_tight.M        -> visible waypoint w_wng 3 0 512 512
Line astern_near_level_Tight.M   -> visible waypoint w_wng 3 2 512 0
Line abreast_near_level_Tight.M  -> visible waypoint w_wng 3 1 512 0
Echelon_near_low_tight.M         -> visible waypoint w_wng 3 0 512 -512
Echelon_near_low_medium.M        -> visible waypoint w_wng 2 0 512 -512
```

Their corresponding object-level `wng` lines are:

```text
Echelon_far_level_loose.M        -> wng 1 0 2048 0
Echelon_near_high_tight.M        -> wng 1 0 512 512
Line astern_near_level_Tight.M   -> wng 1 2 512 0
Line abreast_near_level_Tight.M  -> wng 1 1 512 0
Echelon_near_low_tight.M         -> wng 3 0 512 -512
Echelon_near_low_medium.M        -> wng 3 0 512 -512
```

Cross-comparison isolates the visible-waypoint raw field order as:

```text
w_wng <control_code> <formation_code> <spacing_code> <stacking_code>
```

This ordering is HIGH CONFIDENCE from the six-file differential set. The visible-waypoint `w_wng` first field tracks control (`1` loose, `2` medium, `3` tight), the second tracks formation, the third spacing, and the fourth stacking. The `Line abreast_near_level_Tight.M` versus `Line astern_near_level_Tight.M` pair isolates formation because control, spacing, and stacking are identical while only the second field changes (`1` versus `2`). The `Echelon_near_high_tight.M` versus `Echelon_near_low_tight.M` pair isolates stacking because control, formation, and spacing are identical while only the fourth field changes (`512` versus `-512`). The `Echelon_near_low_medium.M` versus `Echelon_near_low_tight.M` pair isolates control because formation, spacing, and stacking are identical while only the first `w_wng` field changes (`2` versus `3`).

### Confirmed semantic mappings from the current differential set

```text
control:
  loose  = 1
  medium = 2
  tight  = 3

formation:
  Echelon      = 0
  Line abreast = 1
  Line astern  = 2

spacing:
  far  = 2048
  near = 512

stacking:
  level = 0
  high  = 512
  low   = -512
```

The complete confirmed tuples are therefore:

```text
Echelon + far + level + loose        -> w_wng 1 0 2048 0
Echelon + near + high + tight        -> w_wng 3 0 512 512
Line abreast + near + level + tight  -> w_wng 3 1 512 0
Line astern + near + level + tight   -> w_wng 3 2 512 0
Echelon + near + low + tight         -> w_wng 3 0 512 -512
Echelon + near + low + medium        -> w_wng 2 0 512 -512
```

All four navigation-point controls are now fully mapped by the six-file differential set. Continue to require direct evidence before extending these mappings to any new control/formation/spacing/stacking values not listed here.

### Object-level `wng` versus waypoint `w_wng`

The current samples show that object-level `wng` and waypoint `w_wng` must be treated separately. Positions 2–4 consistently track the same formation/spacing/stacking codes, but the object-level first field is **not stable enough to equate directly with waypoint control**. In four earlier samples it remained `1`; `Echelon_near_low_tight.M` stores object-level `wng 3 0 512 -512` with waypoint `w_wng 3 0 512 -512`; and crucially `Echelon_near_low_medium.M` still stores object-level `wng 3 0 512 -512` while its waypoint changes to `w_wng 2 0 512 -512`. This directly proves that object-level `wng` field 1 is not the same semantic control field as waypoint `w_wng` field 1.

```text
waypoint w_wng confirmed form: <control_code> <formation_code> <spacing_code> <stacking_code>
object wng observed forms:     1 <formation_code> <spacing_code> <stacking_code>
                               3 <formation_code> <spacing_code> <stacking_code>   # observed in both low/tight and low/medium samples
```

Therefore, **do not derive object-level `wng` field 1 from a universal rule yet**. For navigation-point behavior, `w_wng` is authoritative and all currently defined semantic values are fully mapped. When emitting object-level `wng`, prefer an exact verified tuple from a matching differential sample. If no matching object-level tuple exists, preserve a tested conservative object-level pattern rather than assuming field 1 always equals either `1`, `2`, `3`, or the waypoint control code.

### v17 generation policy for the four settings (preserving v12 mappings)

- If the user explicitly specifies any of the four settings, honor that value when its raw mapping is verified.
- If `formation` is omitted, randomly choose among all three verified mappings: `Echelon`, `Line abreast`, and `Line astern`.
- If `spacing` is omitted, **always use `far`**, which serializes as spacing code `2048`. Use `near` / `512` only when the user explicitly requests `near`; never randomize spacing by default.
- If `stacking` is omitted, all three values are verified and may be selected randomly: `level`, `high`, or `low`.
- If `control` is omitted, **always use `loose`**, which serializes as first-field code `1` in visible waypoint `w_wng`. Never randomize the control level by default.
- Use `medium` only when the user explicitly requests it; it serializes as first-field code `2`. Use `tight` only when the user explicitly requests it; it serializes as first-field code `3`.
- The loose-by-default rule is a behavior policy: medium/tight control can make units adhere too rigidly to waypoint/formation geometry and reduce their freedom to break formation and attack.
- START and END records keep `w_wng 0 0 0 0`. Apply the chosen four-setting tuple only to visible navigation points.
- When all four requested semantic values are verified individually, compose them in the confirmed field order rather than requiring an exact previously seen full tuple.

### v18 high-altitude bombing exception to the v17 defaults

For ordinary waypoints outside the hostile bombing area, keep the v17 defaults above. For a high-altitude ground-bombing mission, v18 overrides the omitted-value defaults for the entire hostile-territory altitude-discipline corridor, beginning at the enemy-territory entry/turn-in waypoint and continuing through every hostile-area waypoint until the final attack is complete and the bomber has exited enemy territory:

```text
control = tight  -> 3
spacing = near   -> 512
```

Thus a high-altitude Echelon/level waypoint anywhere inside that corridor — entry turn, ingress, attack, between-target turn, post-release turn, or hostile-territory egress — would use:

```text
w_wng 3 0 512 0
```

Formation and stacking remain independently selectable from verified values. If the user explicitly provides another verified formation/stacking setting, preserve it while still forcing `tight + near` throughout the hostile-territory corridor. Do not revert to `far + loose` after a weapon release while the bomber is still in enemy territory, and never relax between multiple pending attacks. Safe-area transit may return to the ordinary v17 defaults only after the final attack is complete and the bomber has exited enemy territory. The user's explicit request for a genuinely different attack profile (for example a dive/low-level attack) takes precedence over this high-altitude exception.

When future differential files are supplied, prefer single-variable comparisons and extend only the missing lookup values. Do not infer an unmapped semantic value from menu order alone.

---

# 15. Waypoint group structure

A waypoint group has this structure:

```text
waypoint2 N
	...waypoint records...

  w_for <object_alias>
	.
```

## 15.1 Record count — CONFIRMED

`N` includes two hidden records:

- START
- END

Therefore:

```text
N = number_of_visible_waypoints + 2
```

Examples:

- one visible A point -> `waypoint2 3`
- visible A/B -> `waypoint2 4`
- visible A/B/C/D -> `waypoint2 6`

## 15.2 START record

Use:

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

## 15.3 Ordinary airborne waypoint

Use the tested pattern:

```text
	w_index <i>
	w_flags $0
	w_goal 1
	w_next 0
	w_pos2 0   0   <X> <ALT_FT> <Z>
	w_speed <FPS>
	w_wng <control_code> <formation_code> <spacing_code> <stacking_code>
	w_react <reaction triple>
	w_searchDist <range>
	w_preferredTargetId2 $0
	w_name \x01<label>\x01
```

**v22/v19 precedence note:** `w_goal 1` now means **until waypoint is reached**, not Normal Flight Assignment. It does **not** imply a reaction reset. If this normal-flight waypoint is a Turn, post-attack point, between-pass point, or realignment point inside an active v19 bombing attack-reaction corridor, set its reaction to `w_react $ffff $0 $0` just like the surrounding Attack waypoints.

### v12 takeoff / landing specialization

**v14/v13 precedence note:** a normal verified **carrier deck start** does not automatically create a visible takeoff/launch waypoint. In that case, the first visible waypoint is the first real airborne mission waypoint and uses its normal mission altitude/speed. The rule below applies only when a visible takeoff/launch waypoint is actually present by explicit request or verified scenario requirement, and it continues to apply to visible landing/recovery points. For a carrier landing/recovery point, v14 additionally requires X/Z to equal the landing carrier's initial mission X/Z coordinates.

When a **visible** waypoint is intentionally used as the takeoff/launch point or landing/recovery point, override the normal airborne altitude/speed values as follows:

```text
Takeoff / launch: <X> 0 <Z>, w_speed 0
Landing / recovery: <X> 0 <Z>, w_speed 0
```

Keep all other waypoint fields context-specific and evidence-based. This rule does not convert START or END sentinel records into visible takeoff/landing points, and it does not create a new takeoff `w_goal`. For the tested carrier landing, continue to use the Section 18 carrier-specific `w_goal 34` / `w_pos2 1 0` form.

## 15.4 END record

Use:

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

## 15.5 `w_for`

The final ownership line references the object's alias:

```text
w_for -1
```

Every object that requires an explicit route gets its own waypoint group.

In the tested Cold War four-ship, each wing member had an individual but identical waypoint group.

---

# 16. Known waypoint goals (`w_goal`) — v22 Duration decoding

Only use decoded values unless a verified reference adds more. v22 `assignment.M` establishes that `w_goal` primarily carries the waypoint **Duration/end-condition** for the advanced behavior selectors, not the tactical Assignment label.

```text
w_goal 0  = no assignment / START-END sentinel
w_goal 1  = until waypoint is reached
w_goal 4  = until target is attacked
w_goal 8  = until target is damaged
w_goal 16 = until target is destroyed
w_goal 34 = Land (tested as carrier landing; separate special form)
```

The older provisional meanings `w_goal 1 = Normal Flight` and `w_goal 16 = Anti-Ship` are superseded. For the exact v22 named presets, the tested Assignment choice correlates with its verified reaction/search tuple, **Target** is carried through `w_preferredTargetId2`, and **Duration** through `w_goal`. **v25 clarification:** `w_react` is also the editable per-target-class reaction matrix, so a user-requested custom class-action mix may deliberately differ from a named preset without changing the independently selected Target/Duration semantics.

Examples from `assignment.M`:

- Normal Flight / no target / until waypoint reached -> `w_goal 1`, `w_react $0 $8000 $0`, `w_searchDist 0`, `w_preferredTargetId2 $0`
- Anti-ship / no target / until waypoint reached -> `w_goal 1`, `w_react $2000 $8000 $0`, `w_searchDist 0`, `w_preferredTargetId2 $0`
- Hi/Lo sweep / airport target / until target attacked -> `w_goal 4`
- Hi/Lo sweep / airport target / until target damaged -> `w_goal 8`
- Hi/Lo sweep / airport target / until target destroyed -> `w_goal 16`

**v19 precedence note:** waypoint Duration and waypoint reaction are independent fields. A `w_goal 1` transit/turn/reposition waypoint that remains inside an active bombing attack-reaction corridor must still use `w_react $ffff $0 $0`; do not infer a Normal Flight reaction or All Defend reaction merely from `w_goal 1`.

When the user's intent can be expressed with object-level Target/Protect instead of a routed waypoint assignment, the confirmed Target/Protect mechanism remains available and requires no route.

Example:

- “F-14 protect E-2C” -> object-level Protect descriptor, no route required
- “MiG targets E-3” -> object-level Target descriptor, no route required
- “Tu-26 flies to B with Anti-ship assignment, targets carrier, until carrier is destroyed” -> waypoint B uses the verified Anti-ship reaction/search tuple, carrier target alias, and `w_goal 16`

---

# 17. `w_flags` and `w_pos2` special cases

## Known waypoint flags

```text
$1 = START record
$2 = END record
$0 = normal airborne waypoint
$4 = observed on a moving carrier's real waypoint
```

`$4` is not semantically fully decoded. Use it only when reproducing the tested moving-ship/carrier route pattern.

## `w_pos2`

Format:

```text
w_pos2 <modeA> <modeB> <X> <Y> <Z>
```

Known tested patterns:

```text
normal airborne point: 0 0 X ALT Z
moving carrier point:  1 0 X 0   Z
carrier landing point: 1 0 X 0   Z
```

The exact meanings of the first two fields remain unknown.

Therefore:

- use `0 0` for ordinary airborne points
- use tested `1 0` only for the carrier/landing patterns described below
- the v12 altitude/speed rule for takeoff/landing points does **not** by itself establish `modeA` / `modeB` for an ordinary land-airfield takeoff or landing
- do not generalize special modes to ground objects without a verified sample

---

# 18. Carrier mission pattern — tested but limited

The Cold War sample provides a working **single Kitty Hawk + F-14** carrier pattern.

## 18.1 Carrier object

Example:

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

## 18.2 Carrier movement waypoint

Use the tested form:

```text
w_flags $4
w_goal 1
w_pos2 1 0 <X> 0 <Z>
w_speed <ship_fps>
w_wng 1 0 256 0
```

A raw `w_speed 50` corresponds to roughly 30 knots.

## 18.3 F-14 deck start

The tested F-14 carrier wing starts near the carrier at altitude 0 and speed 0. **Under v13, that verified deck-start state is sufficient to represent the launch condition, so the generator must not automatically add a redundant visible takeoff/launch waypoint. Navigation point A is the first real airborne mission waypoint** (for example the first CAP/patrol, rendezvous, ingress, escort, or transit point) and uses the altitude/speed appropriate to that role.

The inherited v12 rule remains available when a visible launch point is **explicitly requested by the user** or required by a higher-authority verified sample: in that exceptional case, the visible launch point uses altitude `0` and `w_speed 0`. This does not alter the carrier-landing altitude/speed rule; v14 separately fixes carrier recovery X/Z at the landing carrier's initial mission coordinates.

For a four-ship F-14/Kitty Hawk mission, the verified sample can be used as a geometric template for deck offsets and wing settings.

Do not claim a generic carrier-parent field exists; no explicit parent/host alias has been observed.

## 18.4 Carrier landing

Tested landing waypoint:

```text
w_flags $0
w_goal 34
w_pos2 1 0 <near_carrier_X> 0 <near_carrier_Z>
w_speed 0
```

The verified carrier pattern uses a landing point at/near the carrier's starting location. **v14 makes this placement explicit and mandatory:** set the carrier landing/recovery waypoint X/Z to the landing carrier object's exact initial mission X/Z coordinates. Keep `w_goal 34`, `w_pos2 1 0`, waypoint altitude `0`, and `w_speed 0`.

Do not adjust the landing waypoint for carrier speed, course, elapsed mission time, estimated recovery ETA, or the carrier's later simulated position. The carrier may continue moving normally under Section 18.5; the recovery waypoint nevertheless remains fixed at the carrier's initial mission coordinates.

### Limitation

The exact mechanism that chooses among **multiple carriers** is not decoded.

Safe rule:

- single-carrier mission: supported with the tested pattern plus the v14 initial-carrier-position landing-point policy, even when the carrier moves after mission start
- multiple-carrier or cross-carrier landing: require a verified differential sample before claiming exact carrier-selection behavior

## 18.5 Mandatory ship movement — REQUIRED GENERATION RULE

Every naval vessel in a generated mission must have at least one forward movement waypoint so that it moves in the simulation. Do not intentionally create stationary ships unless the user explicitly requests a disabled/anchored vessel and accepts the deviation from this skill policy.

For a ship whose initial heading is `H` degrees and whose route length is `D` nautical miles, a parallel forward waypoint can be calculated as:

```text
dx = D * 6076.12 * sin(radians(H))
dz = D * 6076.12 * cos(radians(H))
waypoint_x = start_x + dx
waypoint_z = start_z + dz
```

Use the tested naval movement form conservatively:

```text
w_flags $4
w_goal 1
w_pos2 1 0 <waypoint_x> 0 <waypoint_z>
w_speed <ship_fps>
w_wng 1 0 256 0
```

Convert knots to raw speed with:

```text
ship_fps = knots * 6076.12 / 3600
```

### Task-group rule

Ships that are intended to belong to the same carrier/task group must:

- use the same heading/course
- use the same speed
- use the same displacement vector for corresponding movement waypoints
- retain their initial lateral/longitudinal offsets rather than converging on one identical waypoint

In other words, if ship A and ship B begin separated by an offset, their next points should preserve that offset. This keeps the formation moving together and reduces collision risk.

Unless the user supplies a speed, use a plausible common group speed based on the tested carrier pattern (approximately 30 knots for a carrier group) and keep every ship in that group synchronized.


## 18.6 JKPFA_53b split-carrier Tower assembly — v21 REQUIRED RULE

When the active profile is `DEFAULT_PLUS_JKPFA_53B` and the selected carrier hull is one of the five v21 split-carrier types, create its Tower object(s) immediately after resolving the hull position and heading, before serializing final object placement.

Verified pairs and heading-zero offsets from `CV.M`:

```text
ESSE.NT -> ESSET.OT   dX0=+153  dZ0= +68
CDEG.NT -> CDEGT.OT  dX0=+298  dZ0=-325
INVN.NT -> INVNT.OT  dX0= +46  dZ0= -77
ELIZ.NT -> ELIZT.OT  dX0=+330  dZ0=+571   (Tower 1)
ELIZ.NT -> ELIZT.OT  dX0=+298  dZ0=-238   (Tower 2)
KUZN.NT -> KUZNT.OT  dX0=+202  dZ0=-160
```

For carrier heading `H` degrees:

```text
rotated_dX = dX0*cos(H) + dZ0*sin(H)
rotated_dZ = -dX0*sin(H) + dZ0*cos(H)

towerX = carrierX + round(rotated_dX)
towerZ = carrierZ + round(rotated_dZ)
```

Use radians internally for ordinary math-library `sin`/`cos` calls. Set Tower Y equal to carrier Y and copy the carrier `angle` to the Tower.

Tested Tower serialization pattern:

```text
obj
	type <matching_Tower.OT>
	pos <towerX> <carrierY> <towerZ>
	angle <carrierH> 0 0
	nationality3 <same_as_carrier>
	flags $4011
	speed 0
	alias <unique_alias>
	.
```

The carrier hull keeps its ordinary `*.NT` ship object fields and Section 18.5 route. Do **not** create a Tower waypoint group. Correct initial placement is the attachment mechanism used by these split carrier models, after which the Tower follows the carrier.

WWII wooden-deck carrier selection policy under JKPFA_53b:

```text
generic WWII wooden-deck aircraft carrier -> ESSE.NT + ESSET.OT
```

Do not substitute another carrier class for that generic role unless the user explicitly names a different carrier and a verified asset exists.


---

# 19. Known Cuba anchors for missions without raw coordinates

These are **legacy fallback anchors**. If a matching `CUB.MM.txt` (logical `CUB.MM`) is supplied, prefer the exact named/default-object or `special` coordinates from that `.MM` over the hard-coded anchors below. If the user asks for a Cuba mission but gives only relative geometry and no usable `.MM` location is available, these verified anchors may be used.

## Airborne Caribbean anchor

From E-2C test:

```text
X = 1277450
Y = 10000
Z = 802580
```

This is a useful airborne staging anchor south of Cuba.

## Kitty Hawk anchor from Cold War mission

```text
X = 1538837
Y = 0
Z = 748643
```

Use for a tested Cuba carrier scenario.

For maps other than Cuba, do not assume the same coordinate origin. First look for the supplied companion `.MM.txt` (logical `.MM`); if it contains a usable named/default-object anchor, use it. If neither a matching `.MM.txt`/logical `.MM`, a working reference mission, nor a raw anchor is supplied, ask the user for one before promising exact placement.

## 19.5 Automatic dynamic-unit enrichment — REQUIRED DEFAULT POLICY

Unless the user explicitly asks for a minimal mission, an exact order of battle, or no ambient traffic, automatically add approximately **5–10 auxiliary units** to make the scenario feel alive.

These auxiliary units must:

- use `skill 3` (Expert) unless explicitly overridden
- use Mission Success: **Not affected**
- not become hidden mandatory objectives
- use valid assets from the active uploaded items reference/effective catalog
- have plausible nationality and side settings
- be selected as genuinely dynamic/mobile units and receive at least one visible movement waypoint; if a candidate unit cannot be given a verified movement pattern, choose a different auxiliary unit rather than adding it as static decoration
- avoid interfering with the primary mission unless their role intentionally supports ambience (for example defensive helicopter patrols)

### Carrier/naval setting

Prefer a mix such as:

- 2–4 additional carrier-capable aircraft placed on/near the carrier using a verified deck-start template when available
- 1–2 helicopters in the air near the task group (for example `SH3A.PT` or `SH60.PT` when appropriate and present in the active uploaded items reference/effective catalog)
- additional escort ships when the user has described a larger task group

Every ship must follow Section 18.5. Every airborne auxiliary aircraft/helicopter must have at least one visible movement waypoint. If a deck aircraft is intended to move, give it a verified takeoff/air route; do not invent an unsupported deck-taxi mechanism.

### Airfield setting

When a matching `.MM.txt` (logical `.MM`) is supplied, locate the requested/nearest airfield by its `STRIP*.OT` / `DTSTRP.OT` object, use the exact `.MM` `pos` and `angle` as the placement/orientation anchor, and inspect nearby default objects before adding traffic. Prefer a mix such as:

- several additional aircraft associated with the airfield: some may start parked/on the ground **only when a verified airport-ground-start/takeoff pattern is available**, and some should already be airborne on short local routes
- ground-support vehicles such as `TRUCK.NT`, `TANKER.NT`, or `HUMVEE.NT` when available in the active uploaded items reference/effective catalog
- helicopters on local routes when appropriate

The user specifically wants both ground/field activity and airborne activity. However, do not invent an unverified airport-takeoff or ground-vehicle waypoint encoding. If no working ground-route/takeoff template is available, satisfy the 5–10-unit enrichment using verified mobile aircraft/helicopter/naval patterns and clearly keep unsupported ground movement out rather than fabricating fields.

### Route policy for ambient units

Every auto-added auxiliary unit must be intended to move and should receive a short, safe, scenario-appropriate route. If a unit cannot be assigned a verified route, do not use it as one of the 5–10 automatic dynamic units. Do not place ambient units directly across the player's takeoff/landing path or primary target track. For same-group units, preserve formation offsets and common speeds where appropriate.

---

# 20. Mission-construction algorithm

Follow these steps every time.

## Step 1 — Parse the user's scenario

Extract:

- map
- time/environment
- player country and aircraft
- friendly countries/objects
- enemy countries/objects
- unit counts
- wing/group membership
- initial positions or relative positions
- altitude
- heading
- speed
- routes / waypoint labels
- Target / Protect relations
- reactions
- search ranges
- mission-success conditions
- carrier start/landing requirements, including the intended landing carrier whose **initial mission X/Z** must be used for the v14 recovery waypoint
- v21 split-carrier assembly requirements when using `ESSE.NT`, `CDEG.NT`, `INVN.NT`, `ELIZ.NT`, or `KUZN.NT`: record the carrier hull position/heading, required Tower type(s), and rotated Tower position(s); Queen Elizabeth requires two `ELIZT.OT` objects
- carrier deck-start status and whether the user explicitly requested a visible launch/takeoff navigation point; under v13 a normal verified carrier deck start does not auto-create one, so navigation point A becomes the first real airborne mission waypoint; any explicitly present visible takeoff/launch or landing/recovery point still follows the inherited v12 altitude 0 / speed 0 rule, and v14 fixes carrier recovery X/Z at the landing carrier's initial mission coordinates
- waypoint `formation` / `spacing` / `stacking` / `control` preferences; if omitted, apply Section 14.2 with the v17 defaults (`spacing = far`, `control = loose`) while formation/stacking may still use their verified selection policy
- bombing profile: whether the task is dive/low-level attack versus level/high-altitude bombing; for high-altitude bombing, record the attack waypoint altitude and inbound speed/course needed to place the attack waypoint ahead of the target under v18
- bomb-target intent: whether the bomb load is being asked to destroy parked aircraft/airfield targets; if so, treat it as an all-object-type area/installation strike rather than directly assigning the bomb attack to an aircraft alias
- bombing-sequence state for v19: identify the first bombing Attack waypoint, every Turn/post-attack/between-pass/realignment waypoint that still leads to another bombing pass, the final planned bombing pass, and the point where the aircraft has actually exited the active target/hostile area; use these markers to keep the attack-reaction corridor continuous
- fuel preference/percentage when supplied, plus any hardpoint overrides; under v15 fuel may otherwise be chosen automatically from mission needs, while hardpoint requests are limited to stations 4–8 and the inherited only-`*.PT` object-type gate still applies
- whether the user opted out of automatic 5–10 unit ambient enrichment
- the companion `<MAP>.MM.txt` file (logical `.MM` content) corresponding to the selected map, when provided
- the uploaded items reference and the automatically detected installation profile (`DEFAULT_ONLY` or `DEFAULT_PLUS_JKPFA_53B`)
- mission briefing title / operating-area label / date text when supplied
- concise situation, objective, threat, support, success-debrief, and failure-debrief content for the paired `.MT`

## Step 2 — Select the items profile, load the map reference, and resolve assets

Detect/decode the uploaded items reference first, select `DEFAULT_ONLY` or `DEFAULT_PLUS_JKPFA_53B` from its content, and build the effective PT/JT/NT/OT catalogs exactly as defined in Section 3. This selection must occur before natural-language asset matching, object-type selection, or hardpoint resolution.

If a companion `.MM.txt` (or legacy `.MM`) is supplied, treat it as logical `.MM` content, verify that its internal `map ...` line matches the requested `.T2`, then parse its `obj` and `special` records into a searchable map-local index as described in Section 3.5. Ignore `tmap`/`tdic` for normal mission generation.

Then look up every aircraft/vehicle/scenery/map/layer and every requested ordnance/tank (`.JT` / `.GAS`) in the active uploaded items reference/effective catalog or a verified higher-authority sample. For PT/JT/NT/OT under the JKPFA_53b profile, never fall back to an overwritten Default semantic mapping.

Do not fabricate filenames or map locations.

### Step 2A — Add ambient dynamic units

Unless disabled by the user, add approximately 5–10 auxiliary units according to Section 19.5 **before alias allocation** so every generated object receives a deterministic alias. Prefer units for which movement behavior is already verified.

### Step 2B — Expand v21 split carriers into hull + Tower object(s)

Before alias allocation, inspect every selected carrier. Under `DEFAULT_PLUS_JKPFA_53B`, if its hull type is one of the five v21 split-carrier `*.NT` types, add the required matching Tower object(s) from Section 18.6. Compute each Tower's initial X/Z by rotating its `CV.M` heading-zero local offset by the carrier's heading, copy the carrier Y/angle/nationality, and reserve a separate unique alias for every Tower. `ELIZ.NT` always expands to **two** `ELIZT.OT` objects. Do not add a Tower route.

## Step 3 — Choose coordinate anchors

Priority:

1. user-provided raw `X/Y/Z`
2. exact named-object or `special` position from the matching supplied `.MM`
3. positions from a supplied reference `.M`
4. a verified legacy Cuba anchor if map is Cuba and no better logical `.MM` anchor applies
5. otherwise ask for the companion `.MM.txt` (logical `.MM`) or another reference mission/anchor for that map

When using an `.MM` airfield/installation anchor, preserve its `angle` when orientation matters and inspect nearby default objects before placing new units. Then calculate relative positions in feet from nautical-mile bearings.

## Step 4 — Allocate aliases

Assign:

```text
-1, -2, -3, ...
```

in deterministic object order.

Resolve all Target/Protect relations only after aliases are known. Treat aliases found in the supplied `.MM` as reserved and do not deliberately collide with them. **v20 bombing exception:** a confirmed matching-map `.MM` ground-object alias may be used directly for a bombing `preferredTargetId2` / `w_preferredTargetId2` assignment after its alias/type/position/target-area relationship is verified from that `.MM`. For non-bombing Target/Protect cross-file references, retain the earlier evidence requirement.

## Step 5 — Build `sides4` and nationality values

Generate all 64 side entries and `nationality3` values consistently.

### Step 5A — Apply skill policy

Set all top-level skill defaults and all generated object skill fields to Expert unless explicitly overridden:

```text
usGroundSkill 3
usAirSkill 3
themGroundSkill 3
themAirSkill 3
...
skill 3
```

## Step 6 — Choose object flags

Start from tested standard base:

```text
0x4017
```

Then apply only known bits:

```text
Survive   -> | 0x0020
Destroyed -> | 0x0080
Ignore+Hide pair -> | 0x0600
```

**Player-wing override:** for the player object and every member of its wing, clear both `0x0020` and `0x0080` so mission success is always Not affected.

Auxiliary ambient units also default to Not affected.

**v21 Tower exception:** attached split-carrier Tower `*.OT` objects use the verified `flags $4011` pattern from `CV.M`; do not derive their flags from `0x4017` or apply independent mission-success/briefing-map modifiers to them.

Do not invent individual Ignore/Hide bits or nonzero delay values.

## Step 7 — Set direct assignments

For object-level Target:

```text
preferredTargetId2 = target_alias & 0xffff
```

For Protect:

```text
preferredTargetId2 = 0x40000000 | (target_alias & 0xffff)
```

**v18 bombing restriction:** if the task is a bomb attack and the proposed direct target is an aircraft object (`*.PT`), do not create that Target assignment even when the aircraft is parked on the ground. Convert the bombing portion of the task to the all-object airfield/ground-area attack behavior in Steps 8/9 instead.

## Step 8 — Select reactions

Use an exact verified preset or a combination based only on confirmed class masks.

For custom reactions, use the v25-confirmed SAM/AAA/Tank/Vehicle/Structure/Other class masks from Section 11. Do not invent semantic meanings for the still-undecoded low raw bits inside `$ffff`; preserve them from a verified baseline.

**v18 bomb/airfield strike:** when bombs are being used against an airfield/ground area, especially to destroy parked aircraft indirectly through the installation, set the bombing attack waypoint to `w_react $ffff $0 $0` (Attack all object types) rather than an aircraft-only reaction.

**v19 attack-reaction corridor:** after assigning the first bombing Attack waypoint `w_react $ffff $0 $0`, carry that exact reaction forward over every waypoint that remains part of the active bombing sequence. This includes Turn, post-attack turn, between-pass turn, realignment/stabilization, ordinary `w_goal 1` repositioning, later Attack, and target-area egress waypoints. The waypoint label/goal does not cancel the corridor. If another bombing pass is still pending, do not emit `w_react $0 $ffff $0` (All Defend) or another ordinary navigation reaction on the intermediate Turn. End the corridor only after the final planned bombing pass is complete **and** the aircraft has actually departed the active target/hostile area **and** no further bombing attack remains pending.

### Step 8A — Apply the waypoint formation tuple with v18 altitude-corridor exception

For every visible navigation point, choose/resolve `formation`, `spacing`, `stacking`, and `control` using Section 14.2. Unless the user explicitly requests otherwise, force `spacing = far` and `control = loose`. Use `near` only when the user explicitly requests `near`. Serialize only verified semantic-to-raw mappings.

**v18 exception:** for a high-altitude bombing mission, identify the hostile-territory altitude-discipline corridor. The switch point is the enemy-territory entry/turn-in waypoint (or an immediately preceding turn whose purpose is to establish entry into the hostile defended area). From that point through every waypoint still inside enemy territory, force `spacing = near` plus `control = tight`. This includes ingress turns, stabilization/alignment points, every bombing attack point, turns between multiple attacks, post-release turns, and hostile-territory egress points. Do not return to `far + loose` merely because one attack has finished; another pending attack keeps the corridor active. After the final attack is complete and the route has actually exited enemy territory, safe-area egress/transit may resume ordinary v17 `far + loose`. This exception applies even though the user did not explicitly request `near`/`tight`, because the high-altitude bombing role itself triggers the v18 behavior. The v19 attack-reaction corridor is tracked separately: its `w_react $ffff $0 $0` persistence starts at the first bombing Attack waypoint and is not reset by Turn/`w_goal 1` waypoints that remain in the active bombing sequence.

### Step 8B — Apply fuel/hardpoint overrides or build a type-gated loadout

For each object:

- first inspect the object's own `type` extension
- only if the object type ends in `*.PT` may appended `fuel` / `hardpoint` fields be considered
- never append `fuel` or `hardpoint` to `*.JT`, `*.OT`, `*.NT`, or other object extensions unless a later working differential revises the only-`*.PT` rule
- apply an explicit user fuel percentage when supplied; otherwise, v15 permits a mission-aware automatic `fuel` value when route/endurance/role/recovery needs justify it
- fuel may also be omitted when the aircraft's default/internal fuel is suitable
- if the user supplied hardpoint station/quantity/item mappings for allowed stations 4–8 on an eligible object, emit those mappings; user mappings override automatic choices; **v26:** `quantity=0` means an explicit empty station serialized with a mandatory trailing ASCII space and no item token, while positive quantities (including >1) represent multiple same-type items on a single station
- never emit hardpoint overrides for stations 1, 2, 3, or 9
- on an eligible object, stations 4–5 are fuselage stations and 6–8 are wing stations; these are the complete editable set
- when the user did not specify an exact hardpoint loadout, role-aware automatic hardpoint selection may use only stations 4–8 and only active-catalog items
- hardpoint 9 must never be selected by automatic generation
- never invent an ordnance/equipment filename; catalog validity and installed-library precedence still apply

## Step 9 — Build explicit routes

For each routed object:

- START record
- visible waypoints in index order
- END record
- `w_for alias`

Use only known `w_goal` codes.

Additionally:

- for a normal verified carrier deck start, do **not** auto-create a redundant visible takeoff/launch waypoint; the first visible waypoint (navigation point A) is the first real airborne mission waypoint and uses that role's altitude/speed/settings
- if the user explicitly requested a visible takeoff/launch waypoint, or a higher-authority verified sample requires one, that visible point must use altitude `0` and `w_speed 0` under the inherited v12 rule
- every visible landing/recovery navigation point must use altitude `0` and `w_speed 0`
- for any carrier landing/recovery, set landing X/Z to the intended landing carrier object's **initial mission X/Z coordinates**; do not project or lead the point for carrier movement, ETA, or mission duration
- every ship must receive at least one forward naval movement waypoint
- ships in the same task group must share course and speed while preserving formation offsets
- every auto-added airborne auxiliary unit must receive at least one visible movement waypoint
- for a v18 high-altitude bombing run, place the bombing attack waypoint **before** the target along the inbound track; choose an altitude-dependent lead distance so higher specified bombing altitude produces an earlier/farther attack point, using the Section 1 v18 heuristic only when no higher-authority distance is supplied
- for a bomb-carrying airfield strike, do not bind the bombing waypoint to a parked-aircraft alias; keep the all-object attack reaction, and under v20 assign specific valid non-aircraft ground targets through `w_preferredTargetId2` across active bombing-sequence waypoints when appropriate, using confirmed matching-map `.MM` objects and/or generated `.M` objects
- under v19, after the first bombing Attack waypoint, copy `w_react $ffff $0 $0` onto every subsequent Turn/post-attack/between-pass/realignment/next-Attack waypoint that still belongs to the bombing sequence; do not let a normal `w_goal 1` route point silently restore All Defend while another pass is pending
- under v20, build an ordered target sequence for the active bombing waypoints; prefer a different valid ground target at each successive bombing-related waypoint when enough targets are available, and allow multiple bombers on the same route to share that ordered sequence unless the user requests separate allocations
- only use ground/airport movement patterns when a working route/takeoff encoding is available; the v12 altitude/speed convention alone does not decode the remaining land-airfield takeoff/landing fields

## Step 10 — Validate target references

For every `preferredTargetId2` / `w_preferredTargetId2`:

- referenced alias exists in the generated `.M`, **or for a v20 bombing target**, exists as a confirmed ground-object alias in the supplied matching `.MM`
- low 16-bit signed value decodes to the intended alias
- Protect bit is present only for Protect assignments
- no bombing task with bomb ordnance directly references a `*.PT` aircraft alias as its object-level or waypoint-level bomb target
- every v20 `.MM` bombing target has its alias, type, position, and relationship to the requested target area confirmed from the matching supplied `.MM`
- repeated/multi-waypoint bombing distributes different valid ground targets across successive active bombing-sequence waypoints when enough targets are available; reuse is allowed when the valid pool is exhausted or the user requests repetition
- every targeted bombing-sequence waypoint still retains the v19-required `w_react $ffff $0 $0`; setting `w_preferredTargetId2` does not replace the all-object reaction

## Step 11 — Build the paired `.MT`

First choose/normalize the v25 shared output basename so it is exactly seven characters and matches `^[A-Z0-9]{6}[1-9A-Z]$`. Use a six-character stem plus the current revision symbol (`1-9`, then `A-Z`) and use exactly that basename for both `.M` and `.MT`.

Using Section 5.5, generate a same-basename `.MT` with:

- `.section 1` mission identification
- `.section 2` briefing
- `.section 3` success debrief
- `.section 4` failure debrief

Synchronize its objective, threats, support assets, time/environment, and debrief text with the actual generated `.M`.

## Step 12 — Serialize exact files

For `.M`:

- filename is `<BASENAME>.M` where `<BASENAME>` is the v25 exactly seven-character revisioned name matching `^[A-Z0-9]{6}[1-9A-Z]$`
- ASCII-compatible content
- CRLF line endings
- `textFormat` followed immediately by required `brief`, `briefmap`, `armplane` lines before `map`
- actual `0x01` string delimiters
- final `0x00`

For `.MT`:

- filename is `<BASENAME>.MT` using the exact same v25 seven-character revisioned basename as `.M`
- same basename as `.M`
- ASCII-compatible plain text
- CRLF line endings
- no SOH delimiters
- no final NUL in the verified format
- final normal CRLF

## Step 13 — Self-check before delivery

Run all checks in Section 23.

---

# 21. Decision rules for common user requests

## “Fighter intercepts/targets aircraft X”

If user explicitly identifies the target object:

- create target object first or allocate its alias
- create fighter
- set ordinary Target `preferredTargetId2`
- use a verified fighter reaction preset
- waypoint route is optional

## “Fighter protects/escorts AWACS X”

Use object-level Protect:

```text
0x40000000 | target_alias16
```

No waypoint is required unless the user also requests a route.

Do not imitate the old Cold War MiG route-only pseudo-escort when formal Protect is intended.

## “Bombers fly to point B then attack a carrier”

Use the v22 three-selector model explicitly:

- ordinary prior waypoint(s): Duration = until waypoint reached -> `w_goal 1`
- carrier-attack waypoint: Assignment = Anti-ship -> use the verified Anti-ship reaction/search tuple when that UI behavior is intended
- Target = carrier -> `w_preferredTargetId2` = carrier alias16
- if Duration = until target destroyed -> `w_goal 16`; use `w_goal 4` or `8` instead when the user explicitly selects until target attacked or damaged
- when reproducing the older Cold War working sample exactly, preserve its historical ship-attack reaction tuple rather than rewriting it to the v22 baseline preset

## “High-altitude bomber attacks a ground target”

For a strategic/high-altitude bomber such as an available B-52/B-2 asset, or any aircraft explicitly instructed to maintain high altitude during level bombing:

- keep the specified high-altitude profile; do not create a deliberate dive profile
- allow ordinary v17 `far + loose` from takeoff through friendly/neutral pre-ingress transit
- switch to `spacing = near` and `control = tight` at the enemy-territory entry/turn-in waypoint, including the turn used to line up for hostile-area entry
- keep **all** hostile-territory waypoints `near + tight`: ingress, alignment, attack, between-target turns, post-release turns, and hostile-territory egress
- if another attack is pending, remain `near + tight` continuously between attacks
- after the first bombing Attack waypoint, begin the v19 attack-reaction corridor and use `w_react $ffff $0 $0` on that Attack and every Turn, post-attack turn, between-pass turn, realignment/`w_goal 1` reposition waypoint, and later Attack that remains in the active bombing sequence
- if another bombing pass is pending, keep Attack all across the intervening Turn/realignment points; never revert those points to `w_react $0 $ffff $0` merely because they are Turn/Normal Flight
- end the v19 reaction corridor only after the final planned bombing pass is complete, the bomber has actually left the active target/hostile area, and no further bombing attack remains pending
- after the final attack is complete and the bomber has exited enemy territory, allow safe-area egress/transit to return to ordinary v17 `far + loose` for formation behavior; reaction behavior may likewise relax only when the v19 end conditions above are satisfied
- place each attack waypoint before its target on the inbound course
- make the lead distance increase with bombing altitude; use the v18 fall-time/speed planning heuristic only when no tested/user distance is available

## “Bomb aircraft must destroy parked aircraft at an airfield”

Do **not** assign the bomb attack directly to the parked aircraft `*.PT` alias. Instead:

- treat the airfield as an area/installation strike
- use `w_react $ffff $0 $0` (Attack all object types) at the first bombing Attack waypoint and, under v19, retain it on all subsequent Turn/post-attack/between-pass/realignment/subsequent-Attack waypoints that remain inside the active bombing sequence
- under v20, assign specific valid non-aircraft ground targets through `w_preferredTargetId2` across those active bombing-sequence waypoints when suitable targets are available; use confirmed matching-map `.MM` aliases directly and/or generated `.M` aliases, preferring different successive targets when possible
- do not duplicate a confirmed `.MM` facility into `.M` merely to target it; confirm the map object's alias/type/position/airfield relationship from the supplied matching `.MM`
- position each attack/reposition point consistently with the bombing geometry while keeping the v19 all-object reaction active, so the preferred target guides target choice without narrowing the attack reaction

## “Four F-14s launch from one Kitty Hawk and return”

Use the tested Cold War carrier pattern:

- carrier `KITT.NT`
- four F-14 objects at deck altitude/speed zero
- one player `controller $80`
- wing IDs/member indices
- `npcFlags 2` for AI player wingmen
- matching `wng 3 0 512 0`
- identical per-aircraft route blocks
- **v13 normal deck-start behavior:** do not auto-create a visible takeoff/launch point; navigation point A is the first real airborne mission waypoint
- if a visible takeoff/launch point is explicitly requested or required by a higher-authority verified sample, use altitude `0`, speed `0` for that point under v12
- final `w_goal 34` carrier landing at altitude `0`, speed `0`
- place that final landing point at the landing carrier's **initial mission X/Z coordinates**, even when the carrier is moving after mission start

## “Mission success requires X survive and Y destroyed”

Set object flag bits:

```text
X: base | 0x20
Y: base | 0x80
```

All unmentioned objects should normally be Not affected (`base`) unless user says otherwise. **Exception:** every member of the player's own wing is always Not affected regardless of narrative mission-success wording. For enemy objects, independently apply the default briefing-map hide modifier `0x0400` unless the user explicitly requests them visible.

---

# 22. Features that are NOT fully decoded

The companion `.MM` is useful as a reference. Its terrain-grid sections (`tmap`, `tdic`) remain undecoded and must not be treated as mission syntax. **v20 explicitly overrides the former bombing cross-file-target limitation:** confirmed matching-map ground-object aliases may be used directly for bombing `preferredTargetId2` / `w_preferredTargetId2`. Other unverified cross-file semantics outside this bombing override remain not fully decoded.

Do not hide these limitations.

## Must not be invented

- any additional briefing-map/object-visibility flag semantics beyond the confirmed `0x0400 = Hide in briefing map` and `0x0200 = Ignore me` mappings
- nonzero mission start delay
- arbitrary `w_goal` codes beyond `0`, `1`, `4`, `8`, `16`, `34`
- semantic identities of the remaining low raw reaction bits inside `$ffff` beyond the nine confirmed visible Mission Creator classes; preserve those bits from verified full baselines instead of naming them
- object-level `wng` field 1 remains behaviorally underdetermined and must not be generalized from waypoint `w_wng` control codes; all currently defined waypoint `w_wng` formation/spacing/stacking/control values are mapped
- exact meaning of `w_flags $4`
- exact meaning of the first two `w_pos2` fields beyond tested patterns
- nonzero `w_next` behavior
- multiplayer controller values other than player `$80`
- exact multi-carrier landing selection
- coordinate origins for non-Cuba maps without a reference mission
- exact `view` zoom encoding
- `layer` trailing value meaning
- complete `clouds` enumeration
- exact wind units/direction convention beyond the observed syntax
- `fuel` / `hardpoint` generation eligibility outside the inherited only-`*.PT` aircraft-object rule; do not extend eligibility to JT/OT/NT or other types without a new explicit working differential
- generic ground-vehicle movement and the undecoded portions of generic land-airfield takeoff/landing routing unless a verified sample is supplied; v12 only standardizes the takeoff/landing waypoint altitude and speed as `0` / `0`

## Response policy for unsupported requests

If a requested feature depends on an unknown encoding:

1. Try to express the intent using a confirmed mechanism.
2. If no confirmed mechanism exists, ask for a single-variable Mission Creator differential test.
3. Do not fill the unknown with a plausible-looking number.
4. A syntactically complete but behaviorally fabricated mission is considered a failure.

---

# 23. Validation checklist — REQUIRED

Before presenting a generated `.M` + `.MT` pair, verify all of the following.

## File integrity

- [ ] `.M` and `.MT` share one v25 basename matching `^[A-Z0-9]{6}[1-9A-Z]$`
- [ ] basename length is exactly 7 characters, excluding the `.M` / `.MT` extension
- [ ] basename characters 1-6 are an uppercase ASCII-alphanumeric mission stem; character 7 is the revision symbol and follows the ordered sequence `1-9`, then `A-Z`
- [ ] first generation uses revision `1`; a user-requested modification retains the same stem and advances exactly one revision step
- [ ] revision `0`, `~`, spaces, punctuation, underscore, hyphen, lowercase, and non-ASCII characters are absent; no silent rollover occurs after `Z`
- [ ] CRLF line endings
- [ ] all string delimiters are byte `0x01`
- [ ] final byte is `0x00`
- [ ] no accidental UTF-8 smart punctuation or non-ASCII names
- [ ] `.MT` has the exact same basename as `.M`
- [ ] `.MT` uses CRLF and ends with normal CRLF, not NUL

## Items reference/profile

- [ ] the uploaded items file was decoded correctly (including UTF-16 when applicable)
- [ ] the active profile was selected from file contents, not filename alone
- [ ] `DEFAULT_ONLY` uses only built-in/default PT, JT, NT, and OT entries
- [ ] `DEFAULT_PLUS_JKPFA_53B` uses Default + JKPFA_53b PT/JT/NT/OT entries
- [ ] v21 split-carrier exception accepts only the five exact `CV.M`-verified hull/Tower pairings when JKPFA_53b is active; it does not open a general absent-asset loophole
- [ ] every duplicate PT/JT/NT/OT filename resolves to the JKPFA_53b entry/meaning when the JKPFA profile is active
- [ ] an overwritten Default PT/JT/NT/OT description was not used for natural-language asset matching
- [ ] no JKPFA asset was carried over from memory or another request when the Default-only profile is active

## Map reference

- [ ] if a companion `.MM.txt` (or legacy `.MM`) was supplied, it was treated as logical `.MM` content and its internal `map` line matches the requested `.T2`
- [ ] named airfields/places referenced by the scenario were resolved against the `.MM` when available
- [ ] `.MM` default objects were used as anchors/reference and were not blindly duplicated into `.M`
- [ ] no generated alias intentionally collides with a reserved `.MM` alias
- [ ] no `tmap`/`tdic` lines were copied into the mission `.M`

## Header

- [ ] `textFormat` exists
- [ ] immediately after `textFormat`, the generated `.M` contains `brief`, `briefmap`, `armplane` in that order before `map`
- [ ] map exists in reference
- [ ] layer exists in reference
- [ ] `sides4` has exactly 64 entries
- [ ] final four side entries are `$0`

## Paired `.MT`

- [ ] `.section 1`, `.section 2`, `.section 3`, and `.section 4` all exist in order
- [ ] section 2 contains a mission title, situation, mission objective, and threat data
- [ ] section 3 is the Success debrief and section 4 is the Failure debrief
- [ ] `.MT` objective matches the actual `.M` mission logic
- [ ] `.MT` named friendly support and enemy threats actually exist in the scenario/generated `.M`
- [ ] `.MT` does not invent any per-object briefing-map visibility directive; enemy no-show behavior is encoded only in `.M` object `flags`
- [ ] success/failure text does not contradict `.M` mission-success flags
- [ ] no undecoded campaign identifiers are presented as mechanically meaningful fields

## Objects

- [ ] every `type` exists in reference or verified sample
- [ ] every alias is unique
- [ ] nationality3 matches country index and side
- [ ] one intended player object has `controller $80`
- [ ] flags use only known compositions
- [ ] every hostile/enemy generated mission object has `0x0400` set (Hide in briefing map) unless the user explicitly requested it visible
- [ ] no friendly/player object is hidden by the enemy-default rule merely because of asset type; side/nationality determines the default
- [ ] mission-success bits match user's requirements
- [ ] every member of the player wing has both Survive/Destroyed bits cleared (Not affected)
- [ ] every generated unit uses `skill 3` unless the user explicitly requested another skill
- [ ] every emitted `fuel` value is either explicitly requested or a deliberate v15 mission-aware override justified by role/route/endurance/recovery needs; values remain within the practical supported range
- [ ] every object containing `fuel` or `hardpoint` is an aircraft object whose `type` filename ends in `*.PT`
- [ ] no `*.JT`, `*.OT`, `*.NT`, or other ineligible object contains appended `fuel` / `hardpoint` lines
- [ ] every emitted hardpoint item exists in the active effective ordnance catalog / a verified higher-authority sample
- [ ] every equipped hardpoint weapon/equipment item uses a valid `*.JT` token; an external tank uses `*.GAS` only when verified/listed; v26 empty `quantity=0` hardpoint lines contain no item token
- [ ] automatic/custom loadout editing, when allowed by the `*.PT` aircraft-object type gate, uses only hardpoints 4–8; hardpoints 1–3 remain untouched and hardpoint 9 is never emitted
- [ ] **v26:** every explicitly empty station is serialized as `hardpoint <station> 0 ` with a literal ASCII space immediately after `0` before the line ending (checked in raw `.M` bytes); it must not be silently omitted or automatically filled
- [ ] **v26:** equipped stations preserve the user-requested positive quantity, including multiple items on one station (`hardpoint 5 4 AIM9D.JT`), without inventing a second item type on that station
- [ ] no aircraft-specific compatibility, weight, symmetry, launcher, or realism rule blocked an otherwise valid hardpoint 4–8 request
- [ ] when an automatic loadout was generated, its items match the object's mission role using catalog descriptions/labels rather than invented filenames

## Waypoint formation behavior

- [ ] every visible navigation point has a deliberate `w_wng` tuple
- [ ] visible waypoint tuples use the confirmed order `<control> <formation> <spacing> <stacking>`
- [ ] `loose` serializes as control code `1`; `medium` as `2`; `tight` as `3`
- [ ] `Echelon=0`, `Line abreast=1`, `Line astern=2`, `far=2048`, `near=512`, `level=0`, `high=512`, `low=-512` when those settings are selected
- [ ] default `control` is `loose` unless the user explicitly requested `medium` or `tight`
- [ ] default `spacing` is `far` (`2048`) on every visible navigation point unless the user explicitly requested `near` (`512`) **or a verified exception applies; v18 high-altitude bombing uses `near + tight`, v23 active dive-maneuver points use `far + loose`, and v24 permits the verified pre-dive staging point to use `near + tight`**
- [ ] `near` spacing is never selected randomly or inherited merely from a historical sample
- [ ] every v18 high-altitude bombing waypoint inside the hostile-territory altitude-discipline corridor uses `spacing = near` (`512`) and `control = tight` (`3`), beginning at the enemy-entry/turn-in waypoint
- [ ] every visible waypoint that belongs to the active free-maneuver portion of a true v23 dive-bombing attack profile uses `spacing = far` (`2048`) and `control = loose` (`1`); under v24, a separate pre-dive staging/formation point may use the verified `near + tight` sample pattern before the terminal dive is released
- [ ] high-altitude/level bombing and dive bombing are classified by the requested attack profile, not merely by the presence of bombs
- [ ] no hostile-territory turn, alignment, between-target, post-release, or egress waypoint reverts to `far + loose` before the bomber has exited enemy territory
- [ ] if another high-altitude bombing attack is pending, `near + tight` remains continuous between attacks; safe-area `far + loose` resumes only after the final attack and hostile-territory exit
- [ ] friendly/neutral pre-ingress transit may remain `far + loose`, and a later re-entry into enemy territory switches back to `near + tight` at its entry/turn-in waypoint
- [ ] every v18 high-altitude bombing attack waypoint is before the target along the inbound track, and a higher specified bombing altitude produces an equal-or-greater planned lead distance than a lower altitude under otherwise comparable conditions
- [ ] random/default formation and stacking selection uses only semantic values whose raw encodings are verified in the available differential set
- [ ] START and END records remain `w_wng 0 0 0 0`
- [ ] no unknown `w_wng` code outside the confirmed mapping table was invented

## v24 near-vertical dive-bombing geometry

- [ ] when an almost-vertical dive is explicitly requested, the route uses a two-stage terminal geometry: a high-altitude pre-dive staging point followed by a same-altitude terminal attack point much closer horizontally to the target
- [ ] the terminal attack point is not placed directly on top of the target and is not artificially lowered toward target altitude merely to create the appearance of a dive
- [ ] when no better value is supplied, the terminal target stand-off may use the sample-derived heuristic `D ~= 0.10665 * vertical_separation`, clearly treated as a planning heuristic rather than a decoded game constant
- [ ] if the sample-like staging geometry is scaled, its target stand-off may use approximately `0.3681 * vertical_separation`, again only as a heuristic
- [ ] the v24 pre-dive staging point may use `near + tight`; the terminal attack point uses v23 `far + loose`
- [ ] target alias encoding always uses the actual selected alias; the sample `$fffe` is used only when the target alias is actually `-2`
- [ ] the exact `divetest.M` Anti-ship reaction tuple is copied only for a matching ship-attack role/context; ground/airfield dive bombing keeps the applicable v18-v20 reaction/target rules

## v23 dive-bombing behavior

- [ ] a true dive-bombing route uses `far + loose` on every visible waypoint in the active free-maneuver dive-bombing sequence, with the v24 pre-dive staging/formation point as the verified narrow exception
- [ ] visible dive-bombing `w_wng` uses control code `1` and spacing code `2048`, while preserving the chosen formation/stacking fields
- [ ] v18 `near + tight` remains reserved for high-altitude/level bombing and is not applied to dive bombing merely because the aircraft carries bombs or crosses hostile territory
- [ ] v19 reaction persistence, v20 target assignment, and v22 Assignment / Target / Duration remain independent and are not reset by the v23 spacing/control override

## v22 advanced waypoint behavior

- [ ] every explicitly configured advanced waypoint is interpreted as **Assignment / Target / Duration**, not as one overloaded `w_goal`
- [ ] exact `assignment.M` tuples are preserved when a requested combination matches a tested row
- [ ] `w_goal 1/4/8/16` means respectively until waypoint reached / target attacked / target damaged / target destroyed
- [ ] Normal Flight, MIGCAP, BARCAP, Wild Weasel, CAS, Anti-ship, and baseline Hi/Lo sweep use the verified v22 `w_react` + `w_searchDist` presets when selected
- [ ] no-target waypoints use `w_preferredTargetId2 $0`; specified targets use the actual alias low 16 bits rather than a hard-coded `$fff7`
- [ ] `$fff7` is used only when the selected target alias is actually `-9` (as for the `assignment.M` airport sample)
- [ ] Hi/Lo sweep + airport + attacked/damaged/destroyed uses the exact corresponding v22 full tuple; damaged/destroyed are not silently normalized to the baseline Hi/Lo reaction/search tuple
- [ ] old provisional semantics `w_goal 1 = Normal Flight` and `w_goal 16 = Anti-Ship` are not used

## Target references

- [ ] ordinary target low 16 bits decode to correct alias
- [ ] Protect has `0x40000000`
- [ ] no target descriptor references a nonexistent alias
- [ ] no bomb-carrying ground-bombing task directly targets a `*.PT` aircraft alias, even when the aircraft is parked
- [ ] for v20 bombing, each nonzero `preferredTargetId2` / `w_preferredTargetId2` resolves to a valid non-aircraft ground target in either the generated `.M` or the confirmed matching `.MM`; `.MM` alias/type/position/target-area relationship were read from that map, not invented
- [ ] repeated/multi-waypoint bombing prefers different successive ground targets when enough valid targets are available; multiple bombers sharing the same route may share the same ordered target sequence unless separate allocations were requested
- [ ] assigning a bombing preferred target does not remove the v19 `w_react $ffff $0 $0` attack-reaction corridor

## Reactions

- [ ] exact preset or confirmed-mask encoding only
- [ ] v18 bomb/airfield strike uses `w_react $ffff $0 $0` when the goal is to attack all object types in the target area
- [ ] v19 attack-reaction corridor starts at the first bombing Attack waypoint and every Turn/post-attack/between-pass/realignment/`w_goal 1` reposition/subsequent-Attack waypoint that remains part of the active bombing sequence also uses `w_react $ffff $0 $0`
- [ ] no intermediate bombing-sequence Turn or `w_goal 1` reposition waypoint reverts to `w_react $0 $ffff $0` (All Defend) while another bombing pass remains pending
- [ ] Attack all persists across Turn(s) whenever another bombing pass is pending
- [ ] ordinary defense/navigation reaction is restored only after the final planned bombing pass is complete, the bomber has actually left the active target/hostile area, and no further bombing attack remains pending
- [ ] v25-confirmed visible reaction masks are used for Fighter/Bomber/Ship/SAM/AAA/Tank/Vehicle/Structure/Other, and no semantic meaning was invented for the remaining low raw bits inside `$ffff`
- [ ] when reproducing the v25 `1.M` differential, A-F use exactly `$efff $1000 $0`, `$f7ff $800 $0`, `$fbff $400 $0`, `$fdff $200 $0`, `$feff $100 $0`, `$ffbf $40 $0` respectively
- [ ] custom waypoint reactions are treated as per-class `w_react` tuning and are not incorrectly forced back to a named v22 Assignment preset

## Waypoints

- [ ] `waypoint2 N = visible_count + 2`
- [ ] indices run from 0 through `N-1`
- [ ] first record uses `w_flags $1`
- [ ] final record uses `w_flags $2`
- [ ] normal air points use `w_pos2 0 0 ...`
- [ ] for a normal verified carrier deck start, no redundant visible takeoff/launch point was auto-created
- [ ] for a normal carrier deck start, navigation point A is the first real airborne mission waypoint and is not incorrectly forced to altitude `0` / `w_speed 0`
- [ ] every visible takeoff/launch point that is explicitly present has waypoint altitude `0` and `w_speed 0`
- [ ] every visible landing/recovery point has waypoint altitude `0` and `w_speed 0`
- [ ] every carrier landing/recovery point uses the intended landing carrier object's **initial mission X/Z coordinates**
- [ ] no carrier landing/recovery point was projected, led, or extrapolated to a future carrier position
- [ ] the v12 altitude/speed rule was not used to invent an otherwise unknown land-airfield `w_goal`, `w_flags`, or `w_pos2` mode
- [ ] `w_for` matches object alias
- [ ] only decoded `w_goal` values are used (`0`, `1`, `4`, `8`, `16`, `34` under v22/current evidence)
- [ ] waypoint target aliases are valid
- [ ] every ship has at least one forward movement waypoint
- [ ] every v21 split carrier has its required Tower object(s) at heading-rotated offsets; `ELIZ.NT` has two `ELIZT.OT` objects; Towers use copied angle/nationality, `flags $4011`, `speed 0`, and no waypoint group
- [ ] ships in each task group share course and speed and preserve relative offsets
- [ ] auto-added mobile ambient units have movement waypoints

## Geometry

- [ ] altitude is in feet
- [ ] relative NM offsets use ~6076.12 ft/NM
- [ ] heading is consistent with intended direction
- [ ] raw speed is plausible in ft/s
- [ ] when `.MM.txt` / logical `.MM` anchors are available, generated units near named map objects use those coordinates/orientations rather than unrelated hard-coded anchors

---

# 24. Recommended serializer behavior

When actual file creation is available, build the `.M` as bytes rather than relying on a text editor to preserve control characters, and build the paired `.MT` separately as CRLF plain text.

Conceptual pseudocode:

```python
SOH = b"\x01"
CRLF = b"\r\n"
NUL = b"\x00"

# Construct mission lines as ASCII bytes.
# For names:
name_field = b"\tname " + SOH + b"Player" + SOH + CRLF

# End the complete .M file with NUL.
mission_bytes += NUL

# The paired .MT is ordinary ASCII/CRLF text and has no NUL terminator.
mt_text = mt_text.replace("\n", "\r\n")
mt_bytes = mt_text.encode("ascii")
```

If a user asks for a downloadable mission file, provide the actual `.M` **and same-basename `.MT`** files, not only a visually quoted code block.

Under v25, the downloadable filenames must use the exactly seven-character revisioned basename rule `^[A-Z0-9]{6}[1-9A-Z]$`, with the first generation at revision `1` and each user-requested modification advancing `1-9` then `A-Z`.

A human-readable preview may replace SOH with quotation marks for explanation, but the downloadable file must contain real `0x01` bytes.

---

# 25. Minimal object templates

## 25.1 Player F-14, no direct target

```text
obj
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

## 25.2 AI fighter directly targeting object alias -3

```text
obj
	type <FIGHTER.PT>
	pos <X> <ALT> <Z>
	angle <HDG> 0 0
	nationality3 <NAT>
	flags $4017
	speed <FPS>
	alias <ALIAS>
	skill 3
	react $c000 $3fff $0
	preferredTargetId2 $fffd
	searchDist 0
	.
```

## 25.3 Fighter protecting object alias -1

```text
preferredTargetId2 $4000ffff
```

## 25.4 Passive/defensive aircraft

```text
react $0 $ffff $0
```

## 25.5 Legacy fuel/hardpoint line-syntax examples

Earlier working files established line serialization such as:

```text
fuel 50
hardpoint 4 4 AIM54C.JT
hardpoint 5 2 F250.GAS
hardpoint 6 2 AIM7.JT
hardpoint 7 2 AIM9M.JT
```

and:

```text
fuel 80
hardpoint 4 3 GBU28.JT
hardpoint 5 2 F250.GAS
hardpoint 6 2 MK82.JT
hardpoint 7 1 AIM9M.JT
```

Treat these only as **line-syntax evidence**. The inherited generation policy allows these lines only on aircraft objects whose own `type` ends in `*.PT`. `*.JT`, `*.OT`, `*.NT`, and other object extensions are not eligible unless a later explicit working differential revises the rule. Under v15, a `fuel` line may be used without an explicit user request when mission needs justify it. Hardpoint 9 remains prohibited regardless of legacy examples or older skill versions.

---

# 26. Mission-design defaults when user omits details

Use defaults only when they do not contradict explicit user intent. When a matching companion `.MM.txt` (logical `.MM`) is supplied, its map-local object positions/names/orientations take precedence over generic hard-coded placement defaults.

For a simple Cuba airborne mission:

- map: `CUB.T2`
- layer: `day2.LAY 0`
- time: 12:00
- global skills: `3` (Expert)
- era: 4
- airborne anchor: `(1277450, 10000, 802580)`
- unit skill: `3` (Expert) for friendly and hostile units
- enemy briefing-map visibility: **hidden by default** with `flags |= 0x0400`; normal Not-affected enemy base therefore becomes `$4417` unless another confirmed flag modifier/success bit also applies
- friendly/player briefing-map visibility: shown by default unless explicitly hidden
- mission success: Not affected unless user specifies otherwise; **player-wing members are always Not affected even if narrative wording suggests survival is important**
- search range: 25 for generic combat, or 0 when “any distance” is desired
- direct fighter reaction: choose a verified preset rather than constructing unknown category masks
- ambient enrichment: add approximately 5–10 appropriate dynamic units unless explicitly disabled
- all ships: assign at least one forward waypoint; same task-group ships use common course and speed
- v21 JKPFA_53b split carriers: add the required Tower object(s) using the verified local offsets rotated by carrier heading; copy carrier angle/nationality, use Tower `flags $4011` / `speed 0`, and do not give the Tower an independent route; Queen Elizabeth always gets both Towers
- takeoff/landing navigation-point behavior: under v13 a normal verified carrier deck start does not auto-create a visible launch point, so navigation point A is the first real airborne mission waypoint; any explicitly present visible takeoff/launch point and any landing/recovery point retain the v12 altitude `0` / speed `0` rule; under v14 every carrier landing/recovery X/Z equals the landing carrier's initial mission X/Z, with no future-position projection
- waypoint formation behavior: under v17, `spacing` defaults to `far` on every visible navigation point and changes to `near` only on explicit user request; formation/stacking may still be selected from verified mappings when omitted, while `control` defaults to `loose` and changes to `medium`/`tight` only on explicit user request
- fuel/loadout: appended `fuel` / `hardpoint` fields are allowed only on an aircraft object whose `type` ends in `*.PT`; v15 permits mission-aware automatic fuel overrides when useful; eligible hardpoint editing uses exactly stations 4–5 (fuselage) and 6–8 (wing), while 1–3 remain reserved and 9 is prohibited
- briefing output: always generate the paired same-basename `.MT` and enable it in `.M` with `brief`, `briefmap`, `armplane` after `textFormat`
- output filename: under v25 the shared `.M` / `.MT` basename is exactly seven characters matching `^[A-Z0-9]{6}[1-9A-Z]$`; characters 1-6 are the uppercase ASCII-alphanumeric mission stem and character 7 is the revision symbol `1-9` then `A-Z`

For a Cuba Kitty Hawk carrier mission:

- use the verified carrier anchor/pattern from `coldwar(2).M`
- normal deck start: do not auto-create a visible takeoff/launch navigation point; **A = first real airborne mission waypoint**
- only when a visible takeoff/launch point is explicitly requested or verified-required, its altitude/speed = `0` / `0` under v12
- carrier landing point altitude/speed = `0` / `0`
- set the carrier landing point X/Z to the carrier's initial mission X/Z even if the carrier is moving after mission start
- do not create multiple carrier landing choices without a new sample

---

# 27. Output behavior

When the user asks you to create a mission:

1. Briefly restate the interpreted mission only if needed to resolve ambiguity.
2. If all requested behavior is representable with confirmed encodings, generate the `.M` and same-basename `.MT` immediately.
   - v25 filename rule: before serialization/delivery, normalize/select a six-character uppercase ASCII-alphanumeric stem, append revision `1` for the first generation or increment the prior revision for a user-requested modification, ensure the result matches `^[A-Z0-9]{6}[1-9A-Z]$`, and use it unchanged for both files.
3. If one critical requested feature needs an undecoded field, ask one focused question or request a differential sample; do not ask broad unnecessary questions.
4. Validate both files and their cross-file consistency.
5. Return the downloadable `.M` **and same-basename `.MT`** plus a concise summary of:
   - `.MT` briefing title/objective and success/failure debrief coverage
   - v25 filename stem/revision used, and whether this was first generation (`1`) or an increment from the prior revision
   - objects/aliases
   - mission-success conditions
   - briefing-map visibility overrides, including any enemy intentionally shown or friendly object intentionally hidden
   - direct Target/Protect assignments
   - waypoint assignments
   - v25 per-class reaction handling, including any custom Fighter/Bomber/Ship/SAM/AAA/Tank/Vehicle/Structure/Other Attack/Defend/Evade/Ignore choices and the verified baseline used for still-undecoded low raw bits
   - takeoff/landing navigation-point handling, including whether v13 carrier deck-start behavior made A the first real airborne mission waypoint and confirmation that v14 carrier recovery uses the landing carrier's initial mission X/Z at altitude `0` / speed `0`
   - v21 split-carrier assembly when applicable: hull type, Tower type(s), heading, local offset(s), rotated initial Tower position(s), and confirmation that Tower objects have no independent route; explicitly report both Queen Elizabeth Towers
   - waypoint formation/spacing/stacking/control choices, including the v18 hostile-territory `near + tight` corridor (entry/turn-in switch point, continuous hostile-area coverage, and safe post-egress return to `far + loose`) and the altitude-dependent pre-target attack-waypoint lead used
   - bomb-target handling, including whether a parked-aircraft/airfield objective was converted from an aircraft direct target to the v18 all-object attack reaction and whether the v19 attack-reaction corridor was preserved across Turn/realignment waypoints until its final-pass/hostile-area-exit end condition
   - fuel/hardpoint handling, including whether fuel was explicit or mission-aware automatic, confirmation that the object type was eligible, and confirmation that only hardpoints 4–8 were used
   - automatically added ambient units
   - important `.MM.txt` / logical `.MM` map anchors used (for example the selected airfield/region)
   - active items profile (`DEFAULT_ONLY` or `DEFAULT_PLUS_JKPFA_53B`) and any PT/JT/NT/OT override that materially affected the requested mission
   - any conservative defaults used
6. Clearly disclose any field that was extrapolated rather than directly confirmed.

Do not overwhelm the user with reverse-engineering commentary unless they ask for it.

---

# 28. Confidence legend for maintaining this skill

When new differential samples are provided, classify each rule:

- **CONFIRMED** — isolated single-variable differential or multiple independent direct examples
- **HIGH CONFIDENCE** — strong geometric/structural cross-validation but no clean one-variable differential
- **UNKNOWN** — not enough evidence; must not be invented

**v26 preserves the complete v25 and all earlier mission-generation functionality.** The v26 hardpoint extension allows explicit empty stations with a syntax-critical trailing ASCII space (`hardpoint 4 0 `) and multiple rounds of one weapon/equipment type on the same station (`hardpoint 5 4 AIM9D.JT`). The existing v15 aircraft `*.PT` eligibility, only-stations-4–8 topology, weapon catalog validation, and the v25 filename and reaction-matrix policies stay intact. Empty hardpoint lines require byte-level validation because stripping trailing whitespace makes them invalid.

**v25 preserves the complete v24 mission-generation policy and adds two confirmed overrides/refinements.** First, newly generated mission filenames now use an exactly seven-character shared `.M` / `.MT` basename: a six-character uppercase ASCII-alphanumeric stem plus one revision symbol. The first generation uses `1`; each user-requested modification keeps the stem and advances `1` through `9`, then `A` through `Z`. This supersedes v16's active 1-8-character output naming rule for new output while leaving legacy names usable as evidence. Second, the supplied `1.M` differential confirms the individual reaction masks `SAM=$1000`, `AAA=$0800`, `Tank=$0400`, `Vehicle=$0200`, `Structure=$0100`, and `Other=$0040`, with exact visible waypoint tuples A `$efff $1000 $0`, B `$f7ff $800 $0`, C `$fbff $400 $0`, D `$fdff $200 $0`, E `$feff $100 $0`, and F `$ffbf $40 $0`. Together with the existing Fighter/Bomber/Ship masks, all nine visible Mission Creator target classes are now individually mapped. v25 also clarifies v22: exact `assignment.M` named Assignment tuples remain verified presets, but `w_react` is the editable per-class reaction matrix and may be mission-tuned without pretending the raw reaction matrix is the sole universal Assignment identity. Remaining low raw bits inside `$ffff` stay semantically undecoded and must be preserved from verified baselines.

**v24 preserves the complete v23 mission-generation policy and adds the `divetest.M` near-vertical dive-bombing navigation geometry.** The verified Green-wing/Iowa sample uses a high-altitude pre-dive staging point at `30000` ft about `11044` ft horizontally from the target, followed by a terminal attack point at the same `30000` ft altitude but only about `3199` ft horizontally from the target. That terminal geometry corresponds to an approximately `83.9`-degree descent line below horizontal. The staging point uses `near + tight` (`w_wng 3 0 512 0`) while the terminal attack point switches to v23 `far + loose` (`w_wng 1 0 2048 0`). v24 therefore refines only the scope of v23 by allowing a distinct pre-dive formation/staging point to remain rigid before the aircraft is released into the free-maneuver dive; the actual terminal/active dive phase remains `far + loose`. When an almost-vertical dive is requested and no better geometry is available, `D ~= 0.10665 * vertical_separation` may be used as a sample-derived terminal stand-off planning heuristic, not as a decoded engine constant. The sample's Anti-ship target/reaction tuple remains role-specific; other bombing roles continue to use the applicable v18-v22 rules. All v23 and earlier functionality remains active.

**v23 preserves the complete v22 mission-generation policy and adds a dive-bombing waypoint formation-behavior override.** For a true dive-bombing profile—not v18 high-altitude/level bombing—every visible waypoint that belongs to the active free-maneuver dive sequence uses `spacing = far` (`2048`) plus `control = loose` (`1`) so the aircraft can freely leave rigid formation and execute the dive. Bomb carriage or hostile-territory location alone does not activate the rule; classify the profile from the requested attack method or a higher-authority verified sample. v23 supersedes the v18 `near + tight` corridor only for dive-bombing spacing/control. **v24 later refines only the pre-dive boundary:** a separate formation/staging point before the free-maneuver dive may use the verified `divetest.M` `near + tight` pattern. v23 does not alter v19 reaction persistence, v20 preferred-target assignment, v22 Assignment / Target / Duration encoding, bombing target validity, or any earlier feature.

**v22 preserves the complete v21 mission-generation policy and adds advanced waypoint behavior as three explicit Mission Creator choices: Assignment, Target, and Duration.** The `assignment.M` differential confirms baseline Assignment presets for Normal Flight, MIGCAP, BARCAP, Wild Weasel, CAS, Anti-ship, and Hi/Lo sweep through exact `w_react` / `w_searchDist` tuples; confirms `w_preferredTargetId2 $0` for no target and signed-alias low-16-bit encoding for a selected target; and decodes `w_goal 1`, `4`, `8`, and `16` as until waypoint reached, until target attacked, until target damaged, and until target destroyed. This supersedes the older provisional labels `w_goal 1 = Normal Flight` and `w_goal 16 = Anti-Ship`. The exact Hi/Lo-sweep + airport target rows for attacked/damaged/destroyed are preserved as full tuples because the damaged/destroyed samples use a different reaction/search tuple from the baseline/attacked sample. All v21 carrier assembly and every earlier feature remain active except where v22 explicitly corrects the semantic interpretation or supplies an exact waypoint field tuple. **v25 later clarifies** that these remain exact named-preset tuples, while `w_react` itself is the directly editable per-class reaction matrix; explicit class-action tuning may therefore depart from a named preset without treating the reaction matrix as the sole universal Assignment identity.

**v21 preserves the complete v20 mission-generation policy and adds the JKPFA_53b split-carrier hull/Tower assembly rule.** The confirmed hull-only carriers are `ESSE.NT`, `CDEG.NT`, `INVN.NT`, `ELIZ.NT`, and `KUZN.NT`, paired respectively with `ESSET.OT`, `CDEGT.OT`, `INVNT.OT`, two `ELIZT.OT` objects, and `KUZNT.OT`. The heading-zero local `(dX0,dZ0)` offsets from `CV.M` are Essex `(+153,+68)`, Charles de Gaulle `(+298,-325)`, Invincible `(+46,-77)`, Queen Elizabeth `(+330,+571)` and `(+298,-238)`, and Kuznetsov `(+202,-160)`. For a carrier heading `H`, rotate each offset with `dX=dX0*cos(H)+dZ0*sin(H)` and `dZ=-dX0*sin(H)+dZ0*cos(H)`, round to integer mission coordinates, add the result to the carrier X/Z, copy the carrier angle/nationality, and emit the Tower with the tested `flags $4011`, `speed 0`, and a unique alias. The Tower receives no independent waypoint group because correct initial placement attaches it to the carrier so it follows the carrier's movement. Queen Elizabeth always receives both Towers. Under JKPFA_53b, a generic WWII wooden-deck carrier request uses `ESSE.NT` plus `ESSET.OT`. These exact pairings are accepted as verified v21 assets from `CV.M` under `DEFAULT_PLUS_JKPFA_53B` even if an auxiliary `FA_items` inventory omits them; they are not available under `DEFAULT_ONLY`.

**v20 preserves the complete v19 mission-generation policy and adds bombing waypoint target assignment plus the `.MM` map-target override.** Every waypoint that still belongs to an active repeated/multi-waypoint bombing sequence may carry its own specific non-aircraft ground target through `w_preferredTargetId2`, including Attack, post-attack Turn, between-pass Turn, realignment, repositioning, and target-area egress points. Prefer different successive targets when enough valid targets exist. Confirmed ground-object aliases read from the matching companion `.MM` are valid bombing `preferredTargetId2` / `w_preferredTargetId2` references and need not be duplicated into `.M`; verify the alias, type, position, and target-area relationship from that exact supplied map. Generated `.M` ground targets remain valid and may be mixed with `.MM` targets. The preferred target does not replace the v19 all-object reaction: every waypoint in the v19 corridor still uses `w_react $ffff $0 $0`. Multiple bombers sharing the same route may share one ordered target sequence unless separate allocation is requested. This v20 rule supersedes older bombing instructions that forced `w_preferredTargetId2 $0`, prohibited `.MM` target aliases, or required a mission-generated duplicate solely for targetability; the v18 prohibition on directly bombing `*.PT` aircraft remains in force.

**v19 preserves the complete v18 mission-generation policy and adds the bombing attack-reaction corridor.** The v18 all-object bombing reaction `w_react $ffff $0 $0` is no longer treated as an Attack-waypoint-only setting during an active repeated/high-altitude bombing sequence. Starting with the first bombing Attack waypoint, carry Attack all across every Turn, post-attack turn, between-pass turn, realignment/stabilization point, normal `w_goal 1` repositioning point, subsequent Attack, and target-area egress waypoint that still belongs to that bombing sequence. The name/goal `Turn`/`w_goal 1` never authorizes an automatic reset to `w_react $0 $ffff $0` (All Defend) while another bombing pass is pending. Relax the reaction only after the final planned bombing pass is complete, the bomber has actually exited the active target/hostile area, and no further bombing attack remains pending. This reaction corridor is independent of the v18 `near + tight` altitude-discipline corridor and changes no reaction mask encoding or earlier mission-generation feature.

**v18 preserves the complete v17 mission-generation policy and adds two bombing-specific behavior overrides.** First, high-altitude bombing uses a hostile-territory altitude-discipline corridor: ordinary `far + loose` may be used from takeoff through friendly/neutral pre-ingress transit, but the enemy-territory entry/turn-in waypoint switches to `spacing = near` (`512`) plus `control = tight` (`3`) and every hostile-territory waypoint remains `near + tight` through ingress, attacks, turns between attacks, post-release turns, and hostile-territory egress. The route may return to `far + loose` only after the final attack is complete and the bomber has exited enemy territory; if another attack is pending, never relax between attacks. Each attack waypoint is placed before its target with lead distance increasing with bombing altitude; any fall-time/speed calculation is a planning heuristic rather than a decoded game ballistic field. Second, a bomb-carrying ground-bombing task must not directly Target an aircraft (`*.PT`) object even when it is parked. Airfield/parked-aircraft bombing uses an all-object attack reaction (`w_react $ffff $0 $0`, and object-level `react $ffff $0 $0` when appropriate) so valid facilities/ground objects can be attacked. **The former v18 “normally without a waypoint preferred-target alias” behavior is superseded by v20**, which permits and prefers specific valid non-aircraft ground targets from `.M` and confirmed matching-map `.MM` objects across active bombing-sequence waypoints. All earlier fuel/loadout, carrier, briefing, map, success, ambience, and general v17 waypoint defaults remain unchanged outside these v18 exceptions; filename generation follows the later v25 revisioned-name override.

**v17 historically preserved the complete v16 mission-generation policy and changed only the default waypoint-spacing selection policy; v25 later supersedes only the active filename portion:** every visible navigation point uses `spacing = far` (`2048`) unless the user explicitly requests `near` (`512`). `near` must never be selected randomly for an unspecified spacing or inherited merely because a historical differential sample used it. This v17 rule does not change the verified spacing encodings or any formation, stacking, control, filename, fuel/loadout, carrier, briefing, map, targeting, success-condition, or ambience behavior.

**v16 historical policy (superseded by v25 for newly generated filenames):** v16 preserved the complete v15 mission-generation policy and added a strict 1–8-character uppercase ASCII-alphanumeric basename rule matching `^[A-Z0-9]{1,8}$`. Legacy sample names containing `~` remained evidence only. v25 now replaces that active generation rule with the exactly seven-character revisioned `<STEM6><REV1>` scheme while retaining v16 as historical evidence.

Update this skill incrementally. Prefer small controlled Mission Creator tests where exactly one setting changes. **v15 preserves v14 carrier behavior and the inherited v13/v12 navigation/formation behavior, while changing fuel and hardpoint generation policy:** fuel may be used automatically on eligible `*.PT` aircraft when mission needs justify it; the user does not need to mention fuel. Hardpoint overrides are restricted to exactly 4–5 (fuselage) and 6–8 (wing); 1–3 remain reserved and hardpoint 9 must never be used.

**v14 preserves all v13 and v12 functionality except that it supersedes the earlier moving-carrier recovery-position projection policy:** every carrier landing/recovery waypoint must use the intended landing carrier object's **initial mission X/Z coordinates**, with `w_goal 34`, carrier-landing `w_pos2 1 0`, altitude `0`, and `w_speed 0`. Ignore the carrier's later simulated position for recovery-waypoint placement; do not project by speed, course, ETA, or mission duration. The carrier itself still moves normally under the existing naval/task-group rules.

**v13 preserves the rest of v12 functionality and adds the carrier deck-start first-visible-waypoint rule:** when an aircraft/player wing already starts on a carrier deck at altitude `0` and speed `0` using a verified carrier deck-start pattern, do not auto-create a redundant visible launch waypoint. The START sentinel remains, and navigation point A is the first real airborne mission waypoint requested by the scenario, using that waypoint's actual mission altitude/speed/settings. The inherited v12 visible takeoff rule is not removed: if the user explicitly requests a visible launch/takeoff point, or a higher-authority verified sample requires one, that visible point remains altitude `0` / `w_speed 0`. Carrier landing/recovery retains the tested altitude `0` / speed `0` form, with its X/Z placement now governed by v14.

**v12 preserved all prior v11 functionality and added a first-class takeoff/landing navigation-point generation rule:** every explicitly present visible takeoff/launch point and every visible landing/recovery point uses waypoint altitude `0` and `w_speed 0`. v12 originally used a projected future X/Z for moving-carrier recovery; **that position sub-rule is historical and is superseded by v14**, which uses the landing carrier's initial mission X/Z instead. The v12 altitude/speed rule remains active, and it still does not claim new decoding of land-airfield takeoff/landing `w_goal`, `w_flags`, or `w_pos2` mode fields.

The waypoint `formation` / `spacing` / `stacking` / `control` model remains a first-class generation rule. The current six named differentials establish the visible-waypoint field order `w_wng <control> <formation> <spacing> <stacking>` and verify `loose=1`, `medium=2`, `tight=3`, `Echelon=0`, `Line abreast=1`, `Line astern=2`, `far=2048`, `near=512`, `level=0`, `high=512`, and `low=-512`. All currently defined navigation-point formation/spacing/stacking/control values are therefore fully mapped. Object-level `wng` field 1 is not yet governed by a universal mapping and must be preserved from verified tuples conservatively; the low/medium sample directly proves that it does not simply mirror waypoint control. **Under v17, waypoint `spacing` defaults to `far` (`2048`) and `near` (`512`) is used only when the user explicitly requests `near`; spacing is no longer randomized.** `control` still defaults to `loose` unless the user explicitly requests another verified control level. **v18 exception:** high-altitude bombing forces a hostile-territory `near + tight` corridor based on the bombing role itself, even without an explicit near/tight request: switch at the enemy-entry/turn-in waypoint, keep every hostile-area waypoint `near + tight` through all attacks and egress, and return to `far + loose` only after the final attack and actual exit from enemy territory; each attack waypoint is led ahead of the ground target according to bombing altitude. **v23 dive-bombing supersession, refined by v24:** when the actual attack profile is dive bombing rather than high-altitude/level bombing, terminal and active free-maneuver dive waypoints use `far` (`2048`) + `loose` (`1`); v24 permits a distinct pre-dive staging/formation point to use the verified `near` (`512`) + `tight` (`3`) pattern before the terminal dive begins. The v24 near-vertical geometry keeps staging and attack waypoints at the same high altitude and places the terminal attack point very close horizontally to the target; when no higher-authority geometry exists, a sample-derived terminal stand-off of about `0.10665 * vertical_separation` may be used as a planning heuristic. These spacing/geometry rules do not alter reaction, target, or duration fields. **v19 reaction exception:** from the first bombing Attack waypoint onward, every waypoint that remains inside the active bombing sequence—including Turn, post-attack, between-pass, realignment, normal `w_goal 1`, subsequent Attack, and relevant egress points—must retain `w_react $ffff $0 $0`; do not restore `w_react $0 $ffff $0` merely because an intermediate waypoint is a Turn/Normal Flight point, and relax Attack all only after the final planned bombing pass, actual departure from the active target/hostile area, and absence of any further pending bombing attack. **v20 target-assignment exception:** those same active bombing-sequence waypoints may each carry their own valid non-aircraft ground `w_preferredTargetId2`; prefer distinct successive targets when available, and permit confirmed matching-map `.MM` aliases directly without duplicating them into `.M`. Verify each `.MM` target alias/type/position/target-area relationship from the supplied map, and keep `w_react $ffff $0 $0` regardless of the preferred target. **v15 supersedes the older fuel explicit-only and hardpoint 4–9 policy:** appended `fuel` / `hardpoint` fields remain limited to aircraft objects whose own type ends in `*.PT`; `fuel` may now be selected automatically when mission needs justify it, while explicit user fuel values take precedence. Editable hardpoints are exactly 4–5 (fuselage) and 6–8 (wing); 1–3 remain reserved and hardpoint 9 is prohibited. Hardpoint weapon/equipment payload tokens are resolved as `*.JT` ordnance items; verified external tanks may use `*.GAS`. Legacy fuel/hardpoint examples remain serialization evidence, not permission to append those fields to JT/OT/NT or other object types or to use station 9. The supplied `~B08.MT` / `~E39.MT` samples establish the four-section `.MT` structure; hostile mission objects remain hidden on the briefing map by default unless explicitly shown.
