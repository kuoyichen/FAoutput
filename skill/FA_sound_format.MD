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

## Names

* `&NAME.11K/.5K` sound effects (`&AFTBURN.11K`, `&RWRLOCK.5K`), `^NAME.5K` voices / radio
  (`^EJECT.5K`), `AIR###.11K` music (FA.EXE builds the name with `%03d.11K`).
* 8.3, upper case. They live in LIBs; `tools/falib.py` packs them from `11K/`, `5K/`, `8K/` folders.

## Converting (what the Sound Editor does)

MP3/WAV/OGG -> browser decode -> mix to mono -> windowed-sinc resample (Blackman, 10 zero
crossings, cutoff 0.92 x lower Nyquist) -> x*128+128, TPDF dither, clamp 0..255.
Samples already on the 8-bit grid (opened FA file, untouched parts) are not dithered, so an
unedited FA file saves byte-identical.
