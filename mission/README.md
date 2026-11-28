# FA Mission Generator pack / FA 任務產生器套件

Describe a Fighters Anthology mission in words and let an AI write the `.M` mission file and its `.MT` briefing,
following the rules FA.EXE needs. This pack runs with **your own AI** (Claude or another strong model); nothing is
sent to FAshion.

用文字描述一場 Fighters Anthology 任務，讓 AI 寫出符合 FA.EXE 規則的 `.M` 任務檔和 `.MT` 簡報檔。
這個套件用**你自己的 AI**（Claude 或其他夠強的模型）執行，不會傳任何東西到 FAshion。

Made by hawke (kuoyichen). Web page: https://fashion-hawke.vercel.app/tools/mission_gen.html

## What is inside / 內容

| File / 檔案 | What / 說明 |
|---|---|
| `fighters_anthology_mission_generator_SKILL_v26.md` | The generator rules (skill v26): file format, flags, reactions, waypoints, carriers, loadouts. 產生規則（skill v26）。 |
| `items/FA_items(default).txt` | Asset list for a factory FA install. 原版 FA 的物件清單。 |
| `items/FA_items(default+JKP600).txt` | Asset list for FA with the JKP 600 library. 安裝 JKP 600 後的物件清單。 |
| `maps/<MAP>.MM.txt` | The 14 theater maps (`.MM` with a `.txt` suffix so chat apps accept it): airfields, cities, defenses and their coordinates. 14 個戰區地圖。 |

Maps / 地圖: APA Panama, BAL Baltics, CUB Cuba, EGY Egypt, FRA France, GRE Greece, IRA Iraq, LFA Falklands,
NSK Korea, PGU Persian Gulf, SPA Pakistan, TVIET North Vietnam, VLA Vladivostok, WTA Taiwan.

## How to use / 使用方法

1. Give your AI three things: the skill file, **one** items file (the one that matches your FA install) and the
   `.MM.txt` of the map you want. In Claude you can put them in a Project, or attach them to a chat.
   給 AI 三樣東西：skill 檔、**一個**和你的 FA 安裝相符的 items 檔、你要的地圖 `.MM.txt`。
   在 Claude 可以放進 Project，或直接附加在對話裡。
2. Send this first message (once): / 先送這段訊息（一次就好）：

   > Follow the attached Fighters Anthology mission generator skill exactly. Use the attached items file as the
   > asset catalog and the attached .MM.txt as the map reference. If the items file is marked "JKP600" instead of
   > "JKPFA_53b", treat it as the DEFAULT_PLUS_JKPFA_53B profile (JKP 600 is the newer JKP library).
   > Give me the .M and .MT as downloadable files.

3. Describe the mission, in English or Chinese, for example: / 描述任務，中英文都可以，例如：

   > Taiwan map. I fly an F-16 from Chiayi with three wingmen at 20,000 ft. Four MiG-29s come from the west.
   > Destroy them; Chiayi airbase must survive.

4. Put the `.M` and `.MT` files into your FA folder and open the mission in FA. The AI must deliver real files:
   `.M` uses byte 0x01 around names and ends with a 0x00 byte, which a copied text block cannot keep.
   把 `.M` 和 `.MT` 放進 FA 目錄，在 FA 裡開啟任務。一定要讓 AI 產出真正的檔案：`.M` 的名稱前後是 0x01 位元組，
   檔尾是 0x00，從對話框複製文字會遺失這些位元組。

Tips / 小提醒: a strong model gives the best results (the skill is long, about 60k tokens). Ask for changes in the
same chat; the file name keeps its 6-letter stem and the last character counts up (TAIWAN1 → TAIWAN2).
用強一點的模型效果最好（skill 很長，約 6 萬 token）。要修改就在同一個對話裡說，檔名前 6 個字不變，最後一個字遞增（TAIWAN1 → TAIWAN2）。
