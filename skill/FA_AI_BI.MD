# FA AI programs: compiling .AI to .BI

Every aircraft PT names an AI profile (`ctName`, e.g. `F.BI`). The `.BI` is a compiled AI program and the `.AI` is its source. The 9 stock pairs are in `BI/`.

**Compiler:** `tools/aic.py` (Python 3, no dependencies).

```
python3 tools/aic.py BI/F.AI              # writes BI/F.BI
python3 tools/aic.py MY.AI -o MY.BI
python3 tools/aic.py --dis BI/F.BI        # disassemble (shows the .AI line if it sits beside it)
```

It is verified byte-for-byte: all 9 stock `.AI` files compile to the shipped `.BI` files. The only bytes that differ are the 4-byte build timestamp in the PE header at 0x88.

## Container

A `.BI` uses the Phar Lap "PL" PE container, the same one `.SH` files use (MZ stub, then `PL\0\0` at 0x80, i386, 4 sections, image base 0):

| Section | Contents |
|---|---|
| CODE (VA 0x1000, file 0x400) | bytecode, then `25` (end), then the signature `01 02 03 02 01 02 03 02 01`, zero-padded to 16 bytes, then one 6-byte thunk `ff 25 <IAT slot>` per import |
| .idata | a single import descriptor for `main.dll`. The names are `_CTDo_<command>` and `_CTEval_<value>`, lowercase and sorted. ILT and IAT each hold (n+2) dwords, with hint 0 |
| .reloc | a HIGHLOW entry (type 3) for every `call` operand and for every thunk's IAT operand, one block per 4 KB page, padded to an even count |
| $$DOSX | a fixed 512-byte block (`DX` …) |

Layout rules (all 9 match): each section starts on the next 0x1000 VA. The CODE and .idata raw sizes are rounded up to 0x200. The .reloc raw size and vsize are padded so that $$DOSX starts on a 0x1000 file offset. SizeOfImage = $$DOSX VA + 0x1000. SizeOfInitializedData = .reloc raw size + 0x1000. BaseOfData = .idata VA. Subsystem = 0x42. Heap 0x100000/0x1000, stack 0/0.

FA's loader (0x41E990) copies CODE only up to the signature. Calls go through the thunks, so a `call` operand is the absolute VA of a thunk and needs a relocation entry. The names are not stored as strings in FA.EXE (it probably matches them some other way), so the list below comes from the stock files only.

## Bytecode (stack machine)

| op | args | meaning |
|---|---|---|
| 01 / 02 / 03 | i32 / i16 / i8 | push a constant (the compiler picks the smallest size that fits) |
| 04 | | pop (discard a command's result) |
| 05 / 06 | u8 var | store / load `%a`..`%z` (index 0..25) |
| 07 | zero-terminated string | push a string (`maneuver "EN;DE;FR"`) |
| 08 09 0a 0b 0c | | `*` `/` `%` `+` `-` |
| 12 13 14 15 16 17 | | `>` `>=` `<=` `<` `==` `!=` (17 is a guess: it is never used) |
| 18 19 | | `&&` `||` |
| 1a 1b 1c | | `abs` `neg` `not` |
| 1d 1e 1f | | `random N` (0..N-1), `percent N` (true N% of the time), `chance N` |
| 20 | u16 | jmp (CODE offset) |
| 23 | u16 | jump if zero |
| 24 | u8 n, n×u16 | switch: jump to target[value] |
| 25 | | end of program |
| 26 | abs32 | call a thunk (an eval pushes its value; a command is followed by 04) |
| 28 | u16 line, u16 offset | line marker (line number and byte offset in the expanded source) |

Operands are evaluated right to left. A binary `L op R` compiles to `R, L, op`, and a command `cmd a b c` pushes `c, b, a` before `call _CTDo_cmd; pop`.

## Language

- Comments start with `;`. A `;` inside a string does not start a comment. Commas are ignored (`if x, goto y`).
- `label:` (may share a line with a statement), `goto L`, `switch EXPR L0 L1 …`, `%a = EXPR`, `exit`, `restart`, or any command `name arg arg …`. Arguments are separated by spaces, and an argument can be an expression (`move h + 170 0 any corner 0`).
- `if COND STATEMENT` compiles to cond, `jz next`, statement. `if COND goto L` compiles to cond, `jz next`, `jmp L`.
- `.if COND` / `.else` / `.endif` blocks are expanded first into ordinary lines, using 9-character labels. `.if C` becomes `if C goto T` / `goto F` / `T:`, `.else` becomes `goto E` / `F:`, and `.endif` becomes `E:`. The line markers count these expanded lines.
- `#DEBUG …` lines compile to a line marker only.
- `any` = 0x7fffffff. `-90` written with no space is a negative constant.
- Precedence, from loosest to tightest: `||`, `&&`, comparisons, `+ -`, `* / %`, then the prefix words `not neg abs random percent chance`. A chain of n terms at one level is grouped as (first k) op (rest), where k is the largest power of two below n: `A||B||C||D||E` gives `((A||B)||(C||D))||E`. The result is the same as left-to-right, except for `-` and `/` chains. Use extra `%` variables if you need a particular order.

## Vocabulary used by the stock files

Commands (`_CTDo_`, with argument counts as used): `move`(5), `movetoalt`(4), `jink`(8), `circle`(6), `homepos`(5), `homeangle`(5), `immelman`(1), `yoyo`(3), `btoh`(0), `invert`(0), `maneuver`(1 string, shown as the AI's current manoeuvre), `wm_break`(2), `wm_approach`(3), `wm_hspacing`(1), `exit`, `restart`.

The meanings of the arguments are not decoded yet. `move` looks like heading, pitch, `any`, speed, rate (`move htotgt + 180 %a any 2000 10`).

Values (`_CTEval_`): `do_nothing do_ir_launch do_radar_launch do_hit do_evade do_attack` (the mode the program is run for; each program starts by testing them), `alt altdiff h hdiff htotgt p pdiff b speed speeddiff maxspeed minspeed corner cornerspeed betterspeed bettertwr turnradius canclimb disttotgt hrzdisttotgt engagep skill tgt tgtahead tgtfacing tgtoffbeam tgthumancontrol tgtisfighter tgtisplane tgtisship wingapproach wingcombat wm_hspacing_is`.

A new name compiles fine, but FA will only run it if `main.dll` (FA.EXE) provides it. Stick to the names above until the resolver in FA.EXE has been decoded.
