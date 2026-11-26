# FA sound files (.11K / .8K / .5K)

Worked out from FA.EXE (2026-11-26). Editor: `tools/snd_editor.html` (Sound Editor).

## Format

* **No header.** The whole file is raw PCM: **8-bit unsigned, mono** (0x80 = silence).
* FA.EXE hands the file data straight to Miles (`wail32.dll`):
  `AIL_set_sample_address(s, data, size)` with the data pointer = start of the loaded entry,
  then `AIL_set_sample_type(s, 0, 0)` = `DIG_F_MONO_8`, flags 0 (unsigned) (code at 0x4359CE-0x4359E0).
* The playback rate comes **only from the extension** (0x4336E1-0x433787):

| ext | pitch value | rate = 11025 * value >> 8 |
|---|---|---|
| `.5K`  | 0x80  | 5512 Hz |
| `.8K`  | 0xBA  | 8010 Hz |
| `.11K` | 0x100 | 11025 Hz |

  Any other extension: the load function returns -1 (no sound). The value is stored in the sound
  slot (+0x42) and converted to Hz in 0x435A1D (`AIL_set_sample_playback_rate`), so a per-sound
  pitch offset can be added on top (engine sounds).
* File size in bytes = number of samples. 1 s of `.11K` = 11,025 bytes.

## Exception: RIFF WAV inside a sound entry

A scan of every sound in the factory and JKPFA6 LIBs (249 .11K, 798 .5K, 2 .8K) found headerless
u8 PCM everywhere except **15 factory `.5K` files in FA_2.LIB, which are complete RIFF WAV files**
(PCM, mono, 8-bit): `&EXPL3/7/9/10/11/12/13`, `&GUNLOOP` (has a `smpl` loop chunk), `&HRGUN1`,
`&PRP2OFF`, `&PRP2ON`, `&WATHIT1/2/3`, `^TOWEST` (has a `LIST` chunk). Header rates are 5512,
except `^TOWEST` 5510 and `&WATHIT3` 11025.

FA.EXE does **not** parse WAV: it has no `RIFF`/`fmt `/`smpl` string or 'RIFF'/'WAVE' compare
constant, imports only `AIL_set_sample_address` + `AIL_set_sample_type` (not Miles' file-parsing
`AIL_set_sample_file`), and passes the entry start as the sample address. So for these 15 files
the game plays the header bytes (44+ bytes, a ~8 ms click) as audio, and plays them at the
extension rate: `&WATHIT3` (header 11025) is played at 5512 Hz. The `smpl` loop is ignored too
(looping is FA's own per-sound flag, slot +0x4A -> `AIL_set_sample_loop_count`).

The Sound Editor reads these files (any PCM WAV: 8/16/24/32-bit, mixed to mono), shows `smpl`
loop points, and with "Keep the WAV header" writes the container back with all chunks in order
(`fmt ` kept unless the format changes, `data` replaced, `smpl` loops updated, others verbatim),
so an unedited file is byte-identical. Unticked, it saves plain headerless data.

## Names

* `&NAME.11K/.5K` sound effects (`&AFTBURN.11K`, `&RWRLOCK.5K`), `^NAME.5K` voices / radio
  (`^EJECT.5K`), `AIR###.11K` music (FA.EXE builds the name with `%03d.11K`).
* 8.3, upper case. They live in LIBs; `tools/falib.py` packs them from `11K/`, `5K/`, `8K/` folders.

## Converting (what the Sound Editor does)

MP3/WAV/OGG -> browser decode -> mix to mono -> windowed-sinc resample (Blackman, 10 zero
crossings, cutoff 0.92 x lower Nyquist) -> x*128+128, TPDF dither, clamp 0..255.
Samples already on the 8-bit grid (opened FA file, untouched parts) are not dithered, so an
unedited FA file saves byte-identical.
