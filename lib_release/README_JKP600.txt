JKP 600  -  library for Jane's Fighters Anthology            (2026-11-26)
=========================================================================

JKP continues JKPFA, the library created by Zephyr (jkpete106@yahoo.com),
versions 4.55 to 5.3 beta. JKP keeps his name and grows from there.
Thank you, Zephyr.

Page with the full file list, search and history:
  https://fashion-hawke.vercel.app/tools/jkp_lib.html


INSTALL
-------
1. Keep the factory LIBs in your FA folder: FA_1.LIB, FA_2.LIB, FA_4B.LIB,
   FA_4D.LIB (and _HUD.LIB if you have it).
2. Remove every older JKPFA / JKP LIB, for example FA_JKPFA_A..E.LIB,
   FA_JKPFA54_*.LIB, FA_JKPFA_B.LIB, _MAP.LIB, _MUSIC.LIB, JKP5xx_*.LIB.
   Old and new copies must not be loaded together.
3. Copy the 8 JKP600_*.LIB files into the FA folder.

Tested with the original FA.EXE 1.02f and with FA_BIG: mission builder
and missions work.


WHAT IS IN EACH LIB
-------------------
JKP600_A.LIB  aircraft: flight data (PT), ECM, seekers (SEE), HUD   426 files
JKP600_B.LIB  ground units and ships (NT), objects (OT)              295 files
JKP600_C.LIB  weapons (JT) and fuel tanks (GAS)                      180 files
JKP600_D.LIB  3D shapes (SH)                                         188 files
JKP600_E.LIB  pictures and textures (PIC)                            358 files
JKP600_F.LIB  sound effects                                           30 files
JKP600_M.LIB  maps (MM, T2)                                           20 files
JKP600_S.LIB  music                                                   24 files
                                                               1,521 files

New in JKP 600 (compared with JKPFA54, hawke's update of 5.3b): F-14B Super Tomcat, F-14J, F-14S,
F-14W, reworked F-14 and F/A-18 family, KC-130 and KC-135 tankers with air
refueling, Ticonderoga with a helicopter deck.


VERSION NUMBERS
---------------
Every build gets the next number: JKP600, JKP601, JKP602 ... JKP699, JKP700.
A higher number is always newer. Install only one JKP version at a time.


IF A FILE OF YOURS DOES NOT SHOW UP
-----------------------------------
For a file that exists in several places, FA uses the copy whose file
(LIB or loose file in the FA folder) has the newest date. A loose file
you edited after installing JKP wins over the copy in JKP.


FOR LIB MAKERS
--------------
Rules every LIB must follow, and a LIB checker:
  https://fashion-hawke.vercel.app/tools/lib_release.html
Built with falib: https://github.com/kuoyichen/FAoutput (tools/falib.py)


Fighters Anthology is a trademark of Electronic Arts. Fan project by hawke.
