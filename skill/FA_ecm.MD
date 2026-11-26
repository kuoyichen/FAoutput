# FA.EXE ECM / jammer logic (static RE, 2026-11-22)

Question: does a jamming aircraft such as the EA-6B (EA6.PT carries `EA6.ECM` + `F14.ECM`)
protect other friendly aircraft (area jamming), or only itself?

**Answer from code: only itself.** Every missile / sensor calculation reads the jammer bits
and the ECM data of the *target object itself*. No code looks up a nearby friendly jammer.
Not yet verified in game.

## Switching the jammer (player key handler 0x415424)
- Object flag dword `obj+0xDE` (scratch copy 0x50CF5E):
  - bit 0x10 = radar jammer on (ECM kind 3)
  - bit 0x20 = IR jammer on (ECM kind 2)
- `0x452EA0(kind)` scans the object's hardpoints for a class-9 (ECM) typedef:
  kind 3 needs ECM typedef `+8` word bit 0x10, kind 2 needs bit 0x100. First match wins.
- Messages: "Jammers are on" / "No working jammers found" / "Jammers are off".
- `0x452F10(kind, objIndex)` = return that object's ECM typedef, but only if its own bit is on.

## Seeker kinds (JT PROJ6 "guidance" = seeker typedef +8)
2 = IR (AIM-9M, AA-11), 3 = radar (AIM-54C, AIM-120, AA-10), 4 = anti-radiation (AGM-88).

## Signature 0x478200(sensorObj, targetObj, targetIdx, seekerTypedef, flag)
Called from sensor/lock check 0x4C2B50 (from 0x4C2860 radar search and 0x4C3380 missile track).
- Base = target typedef table `+0x3F[kind]`.
- Kind 4 (ARM): base = 100 if the target radiates (+0x11A) **or its radar jammer is on** —
  jamming makes you visible to anti-radiation missiles.
- Target radar jammer on, seeker kind 3 (flag 0) or 4: `+= ECM word +0x13`
  (only if the seeker typedef +9 bits 1/2 match ECM +8 bits 0x40/0x20/0x80).
- Target IR jammer on, seeker kind 2 (flag 0): `+= ECM word +0x18`.
- Kind 2: doubled when target afterburner (+0x16F bit 0x20).
- Then range factor (0x4B4720, 200..1500 ft ramp) etc.

## Missile track roll 0x4C3380 (missile = scratch 0x50CE80, target = +0xE2)
- strength from 0x4C2B50; then if target is aircraft/ground and seeker is 2/3 and the
  target's own jammer of that kind is on: `strength *= (100 - ECM byte)/100`,
  byte +0x12 for radar, +0x17 for IR.
- target airborne (speed +0x34 > 0x3A00): `*= (100 - missile typedef +0x122)/100`.
- 0x4C32B7: `0x4561A0(strength)` = random 0..99 < strength → keep lock (missile +0xDE |= 0x10),
  else lock lost / re-target (0x4854E0).

So jamming lowers the missile's per-tick chance of keeping its lock on **the jammer carrier**.

## The only "area" use: radar display (0x440588)
Loops the objects on the player's radar list; for each hostile aircraft/ground unit with
radar jammer on, reads ITS ECM byte +0x15 as a range in nautical miles (dist / 0x17BC00)
and, if the player is inside it, draws a jamming indication (0x43BB50, id 0x113).
This affects the radar picture only, not missile hit chance for other aircraft.

## Who can switch a jammer on (2026-11-22 follow-up)
Only two writers set +0xDE bits 0x10/0x20 on aircraft: the human player's key handler
(0x4146AF, loads player 0x520A1C, jump table 0x415CEC) and the multiplayer receive code
(0x46D9B7, copies a remote human's bits). No AI code sets them, and 0x452EA0 (find a jammer)
is called only from the key handler and the radar display. So by this reading **AI aircraft,
including an AI EA-6B, never turn a jammer on**. (Scan of direct +0xDE / 0x50CF5E writes; an
indirect write could still exist. Not verified in game.)

## ECM typedef fields used (file field names from skill/FA_ecm_file.MD)
| off | size | use |
|---|---|---|
| +0x08 | word | flags: 0x10 radar jammer, 0x100 IR jammer, 0x20/0x40/0x80 seeker match bits |
| +0x12 | byte | radar jam % reduction of missile track |
| +0x13 | word | added to radar/ARM signature |
| +0x15 | byte | jam range (nm) for radar display |
| +0x16 | byte | second range value (display ramp) |
| +0x17 | byte | IR jam % reduction |
| +0x18 | word | added to IR signature |

## Repo ECM files vs this code (ECM/, 38 files)
- A jammer only works if +08 has $10 (Jammer Installed). 18 files have miss %/RCS values but
  +08 = $0 (A10, AV8*, B1B, B52, B52H, F14, SU24, SU27, SU37, TU160, TU26, TU95, MIG27 ...):
  their radar/IR jam values are never read by this code; only chaff/flares count.
  F14.ECM = $0, so an F-14 gets "No working jammers found".
- Radar miss % (+12) applies to any radar missile once the jammer is on. The RCS add (+13)
  needs a type match: seeker +9 bit 1 → Pulse ($40) else CW ($20); bit 2 → also FH ($80).
- IR jam needs $100: AC130, F15X, F22, KA50 only.
- EA6.ECM ($f0, ALQ-99): radar miss 90 % (best of all files; F22 80, A6/ALQ-131/MIG31/SEAHAR 70),
  RCS add 150 (others 100), display range +15 = 150 nm (others 0-50), IR miss 40 but no $100,
  so its IR values are unused. The EA-6B also carries F14.ECM (chaff/flares, $0).
- +1A IR lock loss time (AC130, KA50 = 3) is not traced in FA.EXE yet.
Idea if area jamming is wanted: patch 0x4C3380/0x478200 to also take the best ECM of any
friendly jamming aircraft within ECM +0x15 nm of the target.
