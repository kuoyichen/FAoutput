# FA .ECM countermeasure file format

Text in "brent's relocatable format" like .PT / .JT, but with no `START OF` sections: the header line is followed
by 20 values (a 0x1B-byte type record, class 9) and the `:si_names` block. Editor: tools/ecm_editor.html, parser tools/ecm_core.js.

| off | kind | field (original FA editor) |
|---|---|---|
| +00 | byte | structType = 9 |
| +01 | ptr | si_names: [0] Internal Name, [1] Description, [2] Object Name (file name) |
| +05 | word | Weight, lbs |
| +07 | byte | flags: 1 on the pod ECMs (ALQ-119, ALQ-131, ALE-44, BOZ 107, Remora), 0 otherwise; use unknown, not in the dialogs |
| +08 | word | Deception Jamming: $10 Jammer Installed, $20 CW, $40 Pulse, $80 Frequency Hop, $100 IR |
| +0A..+0D | 4 bytes | Chaff: quantity, chance %, launch heading, launch pitch |
| +0E..+11 | 4 bytes | Flares: same |
| +12 | byte | Radar: missile miss % |
| +13 | word | Radar: increase to RCS |
| +15 | byte | Radar: max detect cone (FA.EXE uses it as nm range for the hostile radar-display jam mark) |
| +16 | byte | Radar: min detect cone |
| +17 | byte | IR: missile miss % |
| +18 | word | IR: increase to ICS |
| +1A | byte | IR: lock loss time |

Evidence: the jammer bits match each file's description string (F4 "35R CW" = $30, F18 "55R CW/P" = $70,
A6 "70R CW/P/FH" = $f0, AC130 "70IR" = $100, F15X "... CW/P/FH 70DIRCM" = $1f0); the counts and chances match
"(60) 85C (60) 85F" style descriptions; A102.ECM's own comments name +12..+1A (rdChance, rdSigAdd, rNoiseMaxDist,
rNoiseMinDist, irdChance, irdSigAdd, irdLoseLockTime); the jamming fields match Kuoyi's "ECM Jamming Info" dialog
for A10.ECM (30 / 100 / 0 / 0, 40 / 100 / 0). FA.EXE offsets +08 +12 +13 +15 +17 +18 are in skill/FA_ecm.MD (PR #158).

Angles: one byte = 1/256 turn, pitch signed. Descriptions say "Down" for 127/191 (rear, -91 deg) and "Side" for 63/0
and 191/0. Heading 0 = nose is assumed; left/right not confirmed. Kuoyi's ECM dialog screenshot showed chaff 50/35/135/34,
flares 50/35/225/45 and all jamming boxes ticked for "A10.ECM", which is not the repo file (60/85/127/191, bits $0):
those numbers fit bytes 95/24/159/31 with deg = byte*360/255 (truncated when saving), so the original editor may use
255 rather than 256 per turn; unconfirmed.

Which PT carries which ECM: tools/ecm_index.json (node tools/make_ecm_index.cjs).
