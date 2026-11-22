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

## ECM typedef fields used (offsets inside the .ECM typedef; map to file once we have one)
| off | size | use |
|---|---|---|
| +0x08 | word | flags: 0x10 radar jammer, 0x100 IR jammer, 0x20/0x40/0x80 seeker match bits |
| +0x12 | byte | radar jam % reduction of missile track |
| +0x13 | word | added to radar/ARM signature |
| +0x15 | byte | jam range (nm) for radar display |
| +0x16 | byte | second range value (display ramp) |
| +0x17 | byte | IR jam % reduction |
| +0x18 | word | added to IR signature |

TODO: get Kuoyi's EA6.ECM / F14.ECM files and fill in the real values and signs.
Idea if area jamming is wanted: patch 0x4C3380/0x478200 to also take the best ECM of any
friendly jamming aircraft within ECM +0x15 nm of the target.
