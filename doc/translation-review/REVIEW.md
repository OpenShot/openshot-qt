# Main-window translation review

Review date: 2026-09-26. Source revision: `a4b96742f60686f44030a8928b65824a1bbd8a81`.

**Original review: 107 unique English labels; 25 translated languages; 2,675 translated entries reviewed.**
The Play/Pause fix adds one label; the current extraction contains 108 labels across 26 language columns.
All 2,675 have nonempty Qt translations and preserve the checked `%s` placeholders.
There are **237 proposed edits**: 174 meaning/grammar corrections,
51 terminology-consistency edits, and 12 terminology candidates.
The remaining 2,438 translated entries are retained in this review.
Implementation status: **225 reviewed changes applied**, with **12 candidates deferred**.
Nine related Caption effect names and 366 documentation entries were also updated.
See [IMPLEMENTATION.md](IMPLEMENTATION.md) for catalog locations and validation.

This is a contextual linguistic desk review, not certification by 25 native-speaking video editors.
“Retain” means no concrete issue was identified, not proof that no improvement is possible.
Candidates explicitly need local terminology judgment; do not treat them as confirmed mistranslations.
No running-GUI layout, truncation, font, bidirectional rendering, or mnemonic-collision check was performed.

## Reproduce and browse

```sh
python3 src/language/extract_main_window_labels.py
```

Run from any directory using Python with an OpenShot-supported Qt binding. No GUI or libopenshot is required.
The script writes [main-window-labels.csv](main-window-labels.csv) and
[main-window-labels.json](main-window-labels.json). Use `--output-dir /path/to/output` for another location.
CSV is UTF-8 with a BOM for convenient spreadsheet opening. Filter by language, source, or status.
The JSON includes source occurrences, the website-to-Qt locale mapping via the translation rows,
and SHA-256 hashes of all 25 catalog files.

[review-decisions.csv](review-decisions.csv) records a decision for every extracted entry, including unchanged ones.
[recommendations.json](recommendations.json) contains exact source keys, review-time wording, proposed wording,
classification, and rationale. These two files and this report are **dated review snapshots**, not regenerated
by the extractor. The extraction files now reflect the rebuilt catalogs. After future catalog updates, rerun extraction and reconcile proposals against the new wording;
do not carry old “retain” decisions forward automatically.

## Scope and extraction

An XML/AST extraction is safer than a single regex: the same main-window module also contains dialogs,
context menus, and runtime replacements. The extractor:

- Reads the actual menu-bar menus and their immediate entries from `main-window.ui`. Submenu headings
  are included when directly visible there; submenu contents are excluded.
- Finds toolbar actions in the base and Cosmic themes, plus the media/caption toolbars assembled in
  `setup_toolbars`. Includes both action labels and tooltips, with identical strings deduplicated.
- Includes main-window dock headings, filter placeholders, file/property column headings, project title
  fallback, both states of the snapping/razor/timing tools, all four zoom-slider target tooltips,
  track locking/keyframe icons, track labels, and clip/effect/transition hover templates.
- Uses a source-checked allowlist for dynamic strings. A missing allowlisted key fails extraction,
  rather than silently dropping a reviewed control.

Excluded: dialogs and other windows, context-menu contents, deeper menu contents, export settings,
individual effect/property/transition catalogs, emoji names, tutorial body text, and internal controls
of specialist recording/color/scope panels. Their main-window dock headings are included.
User filenames, clip names, and track names are not translation keys; their fixed hover prefixes are included.
The unused “Zoom In”/“Zoom Out” QAction definitions are not selected by the inspected toolbar layouts;
the currently mounted zoom slider's four actual tooltips are included instead.
The brand title “OpenShot Video Editor” is not treated as a translatable editorial label.

Website language source: sibling checkout `openshot-site/openshot_site2/settings/base.py`, `LANGUAGES`,
lines 312–339. It defines **25 non-English languages plus English**.
Mappings: `zh-hans → zh_CN`, `zh-hant → zh_TW`, `nb → nb`, `pt → pt`.
Brazilian Portuguese and Hong Kong Chinese are not substituted for those website languages.
English is a reference column, not a 26th translation to revise.

Translations were looked up with Qt's empty translation context, matching `OpenShotApp._tr` and
`ui_util`. All reviewed values were also compared with `:/locale/OpenShot_*.qm` from this checkout's
`openshot_lang.py`: **zero differences**. “Same as source” is not automatically an error;
loanwords such as Clip, Video, Histogram, or Scopes can be appropriate.

## Editorial principles and behavior checks

Keep OpenShot's short, direct wording. Prefer established editing terms over literal dictionary senses.
Use the same noun for the same object across its heading, toolbar action, and hover text.
Use actions for commands and feature names for dock headings. Keep placeholders, punctuation meaning,
and meaningful Qt mnemonics intact. Do not force English title capitalization or remove familiar loanwords.

Behavior checks in this checkout establish the following:

- **Timing changes playback speed**, not scheduling, measuring time, or audio/video synchronization.
  See [`doc/clips.rst`](../clips.rst), “Timing Tool”, and `TimelineView.RetimeClip` in
  `src/windows/views/timeline.py`. Dragging edges changes duration and rescales keyframes.
- **Captions are timed subtitle cues**: `MainWindow.actionInsertTimestamp_trigger` inserts timestamp pairs
  into a Caption effect. They are not the separate Title feature, comments, or labels attached to icons.
- **Recording supports microphones, screens, and webcams**, and its title is present even when recording
  is inactive. The earlier audio-only inference from the internal name `dockAudioRecording` was incorrect.
  See `AudioRecordingDockContent` in `src/windows/audio_recording.py` and `doc/recording.rst`.
  Chinese Recording View labels are retained; Japanese, Korean, and Vietnamese names cover audio and video.
- **Scopes are signal-analysis instruments**: the submenu contains waveform, histogram, and vectorscope docks.
  Some languages conventionally use a loanword; a dictionary reading alone is insufficient to reject it.
- **Zoom edges are handles on the visible timeline range**. Dragging either way can change the zoom;
  translations should not suggest scaling the media image or always zooming in.

## Source-level observations (English; separate from translation edits)

1. `Thumb` is an abbreviation for **Thumbnail**. This has produced literal body-part or unrelated translations.
   Consider spelling it out in the source in a later UI change; the proposals below correct its meaning
   without changing the current message key.
2. `Enable Timing` / `Disable Timing` could become **Enable Retiming** / **Disable Retiming**.
   The current English is ambiguous. The proposed translations only clarify unmistakably wrong senses;
   valid short timing/retiming loanwords are retained.
3. `Zoom left edge` / `Zoom right edge` are terse and ambiguous even in English. Consider
   **Drag left edge to zoom** / **Drag right edge to zoom**, with a translator comment explaining
   the visible-range handles. Review directional “zoom in” translations together with that source clarification.
   Those unlisted edge translations are retained provisionally, not certified against a redesigned label.
4. **Fixed in the follow-up:** both themes now update the action text and tooltip to translated
   Pause while playing, and Play while paused. A shared helper keeps their behavior consistent.
   The new Pause message is translated in all 25 website languages.

## External terminology checks and deliberate keeps

These are spot checks supporting specific decisions, not claimed native review of every language:

- German: Adobe uses the cutting-tool term **Rasierklinge**, supporting replacement of the eraser wording.
  [Adobe: Schneiden von Clips](https://helpx.adobe.com/de/premiere/desktop/edit-projects/trim-clips/cut-clips.html).
- Dutch: Kdenlive calls magnetic alignment **Vastklikken**, supporting replacement of sliding terminology.
  [Kdenlive: Bewerken](https://docs.kdenlive.org/nl/cutting_and_assembling/editing.html).
- French: Adobe's manual uses **sous-titres** for timed caption editing, supporting the proposed caption family.
  [Adobe: French Premiere manual](https://helpx.adobe.com/archive/fr/premiere-pro/cc/2015/premiere_pro_reference.pdf).
- **Retain Spanish `Scopes → Ámbitos`**: Adobe explicitly uses that terminology for the same type of video
  instruments. Its general dictionary sense is not enough to reject it.
  [Adobe: Mostrar Lumetri Scopes](https://helpx.adobe.com/es/premiere/desktop/correct-color/add-color-effects/display-lumetri-scopes.html).
- Do not “fix” a razor loanword just because it resembles laser: Japanese Adobe documentation uses
  **レーザーツール**. The existing Japanese razor loanword is left unchanged in this pass.
  [Adobe: Japanese Premiere manual](https://helpx.adobe.com/archive/jp/premiere-pro/cc/2015/premiere_pro_reference.pdf).
- Retain established local Timeline choices such as French `Ligne de temps`, Dutch `Tijdbalk`, and Ukrainian
  `Монтажний стіл`; fix inconsistent references around them instead of imposing another editor's vocabulary.
- Retain valid borrowing and regional choices rather than rewriting everything: Bengali/Hindi technical
  loanwords, French `magnétisme`, Spanish `ajuste`, Norwegian `magnetfunksjon`, and Portuguese `ficheiro`.
  The Portuguese review uses the `pt` catalog's European Portuguese baseline.

## Per-language coverage

Each language below was reviewed against all 107 unique source strings. Counts refer to unique
language/source pairs, not repeated appearances of the same label.

| Language | Qt locale | Proposed edits | Retained |
| --- | --- | ---: | ---: |
| Arabic (`ar`) | `ar` | 10 | 97 |
| Bengali (`bn`) | `bn` | 6 | 101 |
| Chinese (Simplified) (`zh-hans`) | `zh_CN` | 16 | 91 |
| Chinese (Traditional) (`zh-hant`) | `zh_TW` | 9 | 98 |
| Croatian (`hr`) | `hr` | 8 | 99 |
| Dutch (`nl`) | `nl` | 9 | 98 |
| French (`fr`) | `fr` | 7 | 100 |
| Finnish (`fi`) | `fi` | 8 | 99 |
| German (`de`) | `de` | 9 | 98 |
| Hindi (`hi`) | `hi` | 17 | 90 |
| Icelandic (`is`) | `is` | 7 | 100 |
| Indonesian (`id`) | `id` | 13 | 94 |
| Italian (`it`) | `it` | 7 | 100 |
| Japanese (`ja`) | `ja` | 6 | 101 |
| Korean (`ko`) | `ko` | 7 | 100 |
| Norwegian Bokmål (`nb`) | `nb` | 8 | 99 |
| Persian (`fa`) | `fa` | 15 | 92 |
| Polish (`pl`) | `pl` | 9 | 98 |
| Portuguese (`pt`) | `pt` | 8 | 99 |
| Romanian (`ro`) | `ro` | 13 | 94 |
| Russian (`ru`) | `ru` | 7 | 100 |
| Spanish (`es`) | `es` | 3 | 104 |
| Turkish (`tr`) | `tr` | 9 | 98 |
| Vietnamese (`vi`) | `vi` | 15 | 92 |
| Ukrainian (`uk`) | `uk` | 11 | 96 |

## Proposed changes and brief reasons

“Correction” addresses meaning, grammar, or the described behavior. “Consistency” aligns labels referring
to the same concept. “Candidate” identifies a likely problem but proposes terminology that needs local
editor confirmation. Several consistency decisions are editorial choices, not claims that the old word
is inherently ungrammatical. Unlisted entries are retained; see the complete decision CSV.

Approved wording has been applied to the authoritative translation sources, and catalogs/resources rebuilt together.
This repository's runtime `.qm` files are compiled assets; do not byte-edit them. Source keys shared with
other windows use the same empty translation context, so a catalog change also affects those occurrences;
check that shared use before implementation even though their UI is outside this review's scope.

### Arabic (`ar`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| &File | & ملف | &ملف | correction | Remove the space after the Qt mnemonic marker so it targets a letter. |
| Add Marker | إضافة إشارة مرجعية | إضافة علامة | consistency | Use the same marker noun as Previous/Next Marker; this adds a timeline marker, not a bookmark. |
| Center on Playhead | الضَّبط على المُشير | توسيط على مؤشر التشغيل | correction | Express a centering action and identify the playback indicator. |
| Center the timeline on the Playhead | تعيين خط الزمان على المُشير | توسيط شريط الوقت على مؤشر التشغيل | correction | Describe centering, not assigning; retain the existing Timeline noun. |
| Pan timeline | تحريك الجدول الزمني | تحريك شريط الوقت | consistency | Use the same timeline term as the dock heading. |
| Captions | التعليقات | التسميات التوضيحية | correction | Comments is the wrong sense here; match the caption toolbar's terminology. |
| Insert Caption | إدراج عنوان | إدراج تسمية توضيحية | correction | Inserts a timed caption cue, not a title. |
| Enter caption text... | أدخل نص التسمية... | أدخل نص التسمية التوضيحية... | consistency | Use the same full caption term as the dock and insertion command. |
| Recording | جارٍ التسجيل | التسجيل | correction | A dock title must not claim that recording is already in progress. |
| Transition | شكل انتقالي | انتقال | correction | Match the plural dock heading and hover prefix without adding shape. |

### Bengali (`bn`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Center on Playhead | প্লেহেডের কেন্দ্রে | প্লেহেডে কেন্দ্র করুন | correction | Use an action rather than a location phrase. |
| Click: center · Drag: zoom | ক্লিক: কেন্দ্র · ড্র্যাগ: জুম | ক্লিক: কেন্দ্রে আনুন · ড্র্যাগ: জুম করুন | correction | Both halves describe actions; center is currently only a noun. |
| Effect: %s | এফেক্ট: %s | ইফেক্ট: %s | consistency | Match the spelling already used in Effect and Effects. |
| Property | সম্পত্তি | বৈশিষ্ট্য | correction | This is an editable attribute, not a possession; match Properties. |
| Thumb | নমুনা | থাম্বনেইল | correction | The column contains thumbnails, not generic samples. |
| Save Project As... | প্রকল্প হিসাবে সংরক্ষণ করুন... | প্রকল্প অন্য নামে সংরক্ষণ করুন... | correction | Make saving under another name explicit; current wording reads save as a project. |

### Chinese (Simplified) (`zh-hans`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Center the timeline on the Playhead | 时间线放在播放区顶 | 将时间线居中到播放指针位置 | correction | The current text says to put the timeline at the top of the playback area. |
| Enable Timing | 启用计时 | 启用变速工具 | correction | Dragging clip edges changes playback speed; it does not enable a timer. |
| Disable Timing | 禁用定时 | 禁用变速工具 | correction | Use the same retiming term as the enabled state, not scheduled operation. |
| Clip | 剪辑(_C) | 剪辑 | correction | Remove a literal GTK-style underscore mnemonic from the clip fallback label. |
| Property | 属性(_P) | 属性 | correction | Remove a literal underscore mnemonic from the property column heading. |
| Effects | 特效(_E) | 特效 | correction | Qt does not interpret the imported (_E) mnemonic syntax. |
| Donate | 捐赠(_D) | 捐赠 | correction | Remove the literal GTK-style mnemonic suffix. |
| Effect | 效果 | 特效 | consistency | Match the Effects dock heading. |
| Effect: %s | 效果：%s | 特效：%s | consistency | Match the Effects dock heading. |
| Open Project | 打开工程 | 打开项目 | consistency | Match New Project and Open Project...; the same action should use the same noun. |
| Save Project | 保存工程 | 保存项目 | consistency | Use the same project term as New Project and Save Project As.... |
| Project Files | 工程文件 | 项目文件 | correction | Keep the project noun consistent across the primary workspace. |
| Rewind | 倒序 | 快退 | correction | This is backward playback, not reversing the ordering of items. |
| Recording | 录制中 | 录制 | correction | The dock supports microphone, screen, and webcam capture. Use a feature name covering audio and video, not an active-recording status or audio-only term. |
| Transition | 转场特效 | 转场 | correction | Use one established editing term across the dock and hover text. |
| Transitions | 过渡 | 转场 | correction | Match Transition: %s, which already uses the video-editing term. |

### Chinese (Traditional) (`zh-hant`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Clip: %s | 剪輯：%s | 片段：%s | correction | Match the Clip fallback noun rather than switching terminology on hover. |
| Effect: %s | 效果：%s | 特效：%s | consistency | Match Effect and the Effects dock heading. |
| Lock track | 鎖定軌道 | 鎖定影音軌 | consistency | Match Add Track and Track %s. |
| Unlock track | 解鎖軌道 | 解鎖影音軌 | consistency | Match Add Track and Track %s. |
| Enable Timing | 啟用計時 | 啟用變速工具 | correction | This changes clip speed instead of running a timer. |
| Disable Timing | 停用計時 | 停用變速工具 | correction | Use the same retiming term as the enabled state. |
| Recording | 錄製中 | 錄製 | correction | The dock supports microphone, screen, and webcam capture. Use a feature name covering audio and video, not an active-recording status or audio-only term. |
| Title | 標題或字幕 | 標題 | correction | The Title menu creates titles; adding or subtitles blurs the separate Captions feature. |
| Caption Toolbar | 字幕工具欄 | 字幕工具列 | consistency | Match the existing Toolbar term 工具列. |

### Croatian (`hr`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Center on Playhead | Centriraj na crtu trenutačne pozicije ili kadra | Centriraj na pokazivač reprodukcije | correction | Replace the long explanatory phrase with a concise playback-position term. |
| Center the timeline on the Playhead | Centriraj vremensku crtu na crtu trenutačne pozicije ili kadra | Centriraj vremensku crtu na pokazivač reprodukcije | correction | Use the same concise playhead term as the action. |
| Enable Timing | Aktiviraj mjerenje vremena | Aktiviraj promjenu brzine | correction | The tool retimes clips; it does not measure elapsed time. |
| Disable Timing | Deaktiviraj mjerenje vremena | Deaktiviraj promjenu brzine | correction | Keep the enabled and disabled retiming states paired. |
| Lock track | Zaključaj stazu | Zaključaj traku | consistency | Match Add Track and Track %s. |
| Unlock track | Otključaj stazu | Otključaj traku | consistency | Match Add Track and Track %s. |
| Insert Caption | Umetni titl | Umetni podnaslov | consistency | Use the same subtitle noun as Captions and its text prompt. |
| Scopes | Opsezi | Mjerni instrumenti | candidate | Name the measurement instruments rather than ranges; native editor review should settle the preferred short label. |

### Dutch (`nl`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Enable Snapping | Schuiven inschakelen | Vastklikken inschakelen | correction | Snapping aligns clip edges; schuiven means sliding. Kdenlive also calls this vastklikken. |
| Disable Snapping | Schuiven uitschakelen | Vastklikken uitschakelen | correction | Use the same snapping term in both states. |
| Click: center · Drag: zoom | Klik: centrum · Sleep: zoom | Klik: centreren · Sleep: zoomen | correction | Use actions rather than the noun centrum. |
| Pan timeline | Schuif tijdlijn | Tijdbalk verschuiven | consistency | Match the existing Timeline heading and use an infinitive like other commands. |
| Audio Levels | Audiovolumes | Audioniveaus | correction | Meters show signal levels, not volume-control settings. |
| Captions | Bijschriften | Ondertitels | correction | The editor handles timed subtitle cues rather than image captions. |
| Caption Toolbar | Bijschrift-werkbalk | Ondertitelwerkbalk | correction | Use the same timed-subtitle term as the dock. |
| Insert Caption | Bijschrift invoegen | Ondertitel invoegen | correction | Use the same subtitle term as the dock. |
| Enter caption text... | Tekst voor bijschrift invoeren... | Ondertiteltekst invoeren... | correction | Use the same subtitle term as the dock. |

### French (`fr`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Captions | Légendes | Sous-titres | correction | This dock edits timed subtitles; légendes suggests image captions. |
| Caption Toolbar | Barre d'outils de légende | Barre d’outils des sous-titres | correction | Match the timed-subtitle term used for the dock. |
| Insert Caption | Insérer une légende | Insérer un sous-titre | correction | Inserts a timed subtitle cue, not a picture legend. |
| Enter caption text... | Saisir le texte de légende... | Saisir le texte du sous-titre... | correction | Match the dock and insertion action. |
| Contents | Contenus | Sommaire | correction | This opens the help table of contents, not generic content items. |
| Center the timeline on the Playhead | Centrer la ligne du temps sur la tête de lecture | Centrer la ligne de temps sur la tête de lecture | consistency | Match the existing Timeline heading exactly. |
| Pan timeline | Déplacer la timeline | Déplacer la ligne de temps | correction | Avoid changing from the localized dock name to English in its tooltip. |

### Finnish (`fi`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Caption Toolbar | Tekstitys työkalupalkki | Tekstitystyökalupalkki | correction | Use a correctly formed Finnish compound for the subtitle toolbar. |
| Enter caption text... | Kirjoita otsikkoteksti... | Kirjoita tekstitysteksti... | correction | This is subtitle text, not title text. |
| Center on Playhead | Keskellä toistopaikkaa | Keskitä toistopaikkaan | correction | Use an action instead of in the middle of the playback position. |
| Effect: %s | Efekti: %s | Tehoste: %s | consistency | Match Effect and Effects. |
| Color View | Väri-näkymä | Värinäkymä | correction | Use the normal compound without an unnecessary hyphen. |
| Vectorscope | Vektoriaaltomuoto | Vektoriskooppi | correction | A vectorscope is an instrument, not a vector waveform. |
| Enable Snapping | Ota napsauttaminen käyttöön | Ota kohdistus käyttöön | candidate | Napsauttaminen means clicking; the tool enables magnetic alignment. Confirm the preferred local snapping term. |
| Disable Snapping | Poista napsauttaminen käytöstä | Poista kohdistus käytöstä | candidate | Pair with the proposed magnetic-alignment term. |

### German (`de`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Enable Razor | Radierer aktivieren | Rasierklinge aktivieren | correction | Radierer is an eraser; this tool splits clips. Adobe uses Rasierklinge for this tool. |
| Disable Razor | Radierer deaktivieren | Rasierklinge deaktivieren | correction | Use the same cutting-tool term in both states. |
| Captions | Beschriftungen | Untertitel | correction | The dock edits timed subtitle cues, not generic labels. |
| Caption Toolbar | Beschriftungs-Symbolleiste | Untertitel-Werkzeugleiste | consistency | Use the subtitle term and match the existing Toolbar noun. |
| Insert Caption | Beschriftung einfügen | Untertitel einfügen | correction | The action inserts a timed subtitle cue. |
| Enter caption text... | Beschriftungstext eingeben … | Untertiteltext eingeben … | correction | Match the subtitle dock and insertion action. |
| Center the timeline on the Playhead | Zeitleiste auf Abspiel-Cursor zentrieren | Zeitleiste auf Abspielkopf zentrieren | correction | Match Center on Playhead rather than switching to Abspiel-Cursor. |
| Pan timeline | Timeline verschieben | Zeitleiste verschieben | consistency | Match the localized Timeline dock name. |
| Property | Merkmal | Eigenschaft | correction | Use the singular of the existing Properties term. |

### Hindi (`hi`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Clear | स्पष्ट | साफ़ करें | correction | The current word means clear as an adjective, not the clearing command. |
| Thumb | अंगूठा | थंबनेल | correction | The column contains thumbnail images, not a thumb on a hand. |
| Property | संपत्ति | विशेषता | correction | Use the singular of Properties; this is an attribute, not owned property. |
| Value | मूल्य | मान | correction | This column shows an attribute value, not a price. |
| Open Project | खुले परियोजना | प्रोजेक्ट खोलें | correction | Fix the grammar and use the project term already used by import/export. |
| Open Project... | परियोजना खोलें... | प्रोजेक्ट खोलें... | consistency | Match the same action's tooltip and the chosen project noun. |
| New Project | नई परियोजना | नया प्रोजेक्ट | consistency | Use one project noun across the main toolbar. |
| Save Project | परियोजना को सुरक्षित करो | प्रोजेक्ट सहेजें | correction | Use a concise polite command matching the other toolbar actions. |
| Save Project As... | परियोजना को यथाकतिथ सहेजें... | प्रोजेक्ट इस नाम से सहेजें... | correction | The current wording does not express Save As correctly. |
| Recent Projects | हाल ही के परियोजनाएं | हाल के प्रोजेक्ट | correction | Fix agreement and match the project noun used in adjacent commands. |
| Untitled Project | अनामांकित परियोजना | बिना शीर्षक वाला प्रोजेक्ट | correction | Use a clear untitled-project label consistent with the project commands. |
| Import Files | फ़ाइलें आयात करे | फ़ाइलें आयात करें | correction | Fix the verb spelling to match Import Files.... |
| Jump To Start | शुरू से करे | शुरुआत में जाएँ | correction | This seeks to the start; it does not start doing the operation again. |
| Jump To End | सीधा अंत में जाये | अंत में जाएँ | correction | Use the same concise navigation construction as Jump To Start. |
| Center on Playhead | प्लेहेड पर केंद्रित कीजिए | प्लेहेड पर केंद्रित करें | correction | Match the verb form used by its longer tooltip. |
| Quit | छोड़े | बाहर निकलें | correction | Match the Quit menu action. |
| Preferences | वरीयता | पसंदें | consistency | Match the Preferences menu action rather than using a different singular noun. |

### Icelandic (`is`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Clip: %s | Klippa: %s | Myndbútur: %s | consistency | Match the existing Clip noun rather than using a cut/clip verb. |
| Lock track | Læsa lagi | Læsa spori | consistency | Match Add Track and Track %s. |
| Unlock track | Lykja upp lag | Aflæsa spori | correction | Use an actual unlock command and the existing track noun; the current wording is malformed. |
| Transition: %s | Yfirfærsla: %s | Millifærsla: %s | consistency | Match the existing Transition and Transitions terms. |
| Luma Waveform | Luma bylgjulaga | Luma-bylgjuform | correction | Name the waveform rather than using the adjective wavy. |
| My Views | Sýn mín | Mínar sýnir | correction | Use a plural possessive matching multiple saved views. |
| Effects | Sjónhverfingar | Áhrif | candidate | Unify the plural dock heading with Effect and its hover prefix; the current term evokes visual illusions although this dock also contains audio effects. |

### Indonesian (`id`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Add Track | Tambah Alur | Tambah Trek | correction | Match Track %s and the track-lock controls. |
| Enable Razor | Aktifkan Razor | Aktifkan Pisau | consistency | Use the same cutting-tool noun as Disable Razor. |
| Enable Timing | Aktifkan Penjadwalan | Aktifkan Pengaturan Kecepatan | correction | This retimes playback; penjadwalan means scheduling. |
| Disable Timing | Nonaktifkan Penjadwalan | Nonaktifkan Pengaturan Kecepatan | correction | Use the same playback-speed term as the enabled state. |
| Center the timeline on the Playhead | Pusatkan linimasa pada Playhead | Pusatkan Garis Waktu pada Playhead | consistency | Match the existing Timeline dock noun. |
| Pan timeline | Geser timeline | Geser Garis Waktu | consistency | Match the existing Timeline heading rather than introducing a third name. |
| Click: center · Drag: zoom | Klik: pusat · Seret: zoom | Klik: pusatkan · Seret: zoom | correction | Use the centering verb rather than the noun center. |
| Rewind | Putar Ulang | Mundur | correction | The control plays backward; putar ulang suggests replaying. |
| Recording | Merekam | Perekaman | correction | A dock title should name recording rather than assert the app is recording. |
| Thumb | Preview (Thumb) | Gambar Mini | correction | Name the thumbnail instead of leaving a mixed English abbreviation. |
| Video Preview | Video Preview | Pratinjau Video | correction | Localize the high-visibility dock heading. |
| Insert Caption | Sisipkan Keterangan | Sisipkan Kapsi | correction | Match the Captions dock and text prompt. |
| Scopes | Cakupan | Skop | candidate | Cakupan means coverage/scope in a general sense; a technical instrument label is clearer, subject to local editor terminology review. |

### Italian (`it`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Caption Toolbar | Didascalia barra degli strumenti | Barra degli strumenti dei sottotitoli | correction | The current phrase reverses the noun relationship; this toolbar edits timed subtitles. |
| Captions | Didascalie | Sottotitoli | correction | The editor manages timed subtitle cues, not picture captions. |
| Insert Caption | Inserisci Didascalia | Inserisci sottotitolo | correction | Match the subtitle dock. |
| Enter caption text... | Inserire il testo della didascalia... | Inserisci il testo del sottotitolo... | correction | Match the dock and the concise imperative used by the insertion command. |
| Center the timeline on the Playhead | Centra la timeline sulla testina di riproduzione | Centra la timeline sul cursore di riproduzione | consistency | Use the same playhead term as the short action. |
| Clip | Filmato | Clip | correction | Includes audio and still-image clips as well as films; matches the hover prefix. |
| Recording View | Visualizzazione Registrazione | Vista registrazione | correction | Match the View noun used in Simple View and Color View. |

### Japanese (`ja`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Animated Title | 動画タイトル | アニメーションタイトル | correction | An animated title is more specific than a video title. |
| Caption Toolbar | ツールバーのキャプション | キャプションツールバー | correction | Current wording means caption of the toolbar; correct the noun relationship. |
| Center on Playhead | 再生ヘッドの中央 | 再生ヘッドを中心に表示 | correction | Describe centering the view rather than the center of the playhead. |
| Center the timeline on the Playhead | 再生ヘッドのタイムラインを中央にする | 再生ヘッドを中心にタイムラインを表示 | correction | Correct which object is centered on which position. |
| Recording | 録画中 | 録音・録画 | correction | The dock supports microphone, screen, and webcam capture. Use a feature name covering audio and video, not an active-recording status or audio-only term. |
| Recording View | 録画ビュー | 録音・録画ビュー | correction | The dock supports microphone, screen, and webcam capture. Use a feature name covering audio and video, not an active-recording status or audio-only term. |

### Korean (`ko`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Center on Playhead | 재생 헤드 중앙 | 재생 헤드를 중심으로 보기 | correction | Describe centering the view on the playhead rather than naming the center of the playhead. |
| Recording | 녹화 중 | 녹음/녹화 | correction | The dock supports microphone, screen, and webcam capture. Use a feature name covering audio and video, not an active-recording status or audio-only term. |
| Recording View | 녹화 뷰 | 녹음/녹화 보기 | consistency | The dock supports microphone, screen, and webcam capture. Use a feature name covering audio and video, not an active-recording status or audio-only term. |
| Common | 공통 사항 | 자주 사용 | correction | The filter shows commonly used transitions, not shared/common matters. |
| Simple View | 요약 보기 | 간단 보기 | correction | This is a simple workspace layout, not a summary view. |
| Transition: %s | 전환: %s | 전환효과: %s | consistency | Match the Transition and Transitions labels. |
| Preferences | 기본 설정 | 환경설정 | consistency | Match the Preferences menu action. |

### Norwegian Bokmål (`nb`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Add Marker | Legg til markør | Legg til merke | consistency | Match Previous/Next Marker so markers are not confused with a moving cursor. |
| Captions | Tekster | Undertekster | correction | Use a specific timed-subtitle term instead of generic texts. |
| Caption Toolbar | Bildetekstverktøylinje | Verktøylinje for undertekster | correction | This edits timed subtitles, not picture captions. |
| Insert Caption | Sett inn bildetekst | Sett inn undertekst | correction | Match the subtitle dock. |
| Enter caption text... | Skriv inn bildetekst... | Skriv inn undertekst... | correction | Match the subtitle dock. |
| Recording | Tar opp | Opptak | correction | A dock heading names the feature; tar opp asserts that recording is active. |
| Video Preview | Forhåndsvis Video | Videoforhåndsvisning | correction | Use a noun for the preview dock rather than an imperative. |
| Scopes | Områder | Måleinstrumenter | candidate | Områder means areas; these panels are signal-measurement instruments. Confirm preferred local short label. |

### Persian (`fa`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Center on Playhead | مرکز روی سر پخش | مرکز کردن روی نشانگر پخش | correction | Use the action form and the playback-indicator term already used in its tooltip. |
| Center the timeline on the Playhead | مرکز کردن جدول زمانی روی نشانگر پخش | مرکز کردن خط زمان روی نشانگر پخش | correction | Match the Timeline dock noun. |
| Pan timeline | حرکت دادن جدول زمانی | حرکت دادن خط زمان | correction | Match the Timeline dock noun. |
| Clip | ویدیو | کلیپ | correction | The item can be video, audio, or a still image; match the hover prefix. |
| Export Project | صادرات پروژه | برون‌ریزی پروژه | correction | The existing phrase uses commercial exports; match Export Video's software-export verb. |
| Thumb | بینیه | تصویر بندانگشتی | correction | Replace the incorrect word with thumbnail image. |
| Track %s | شیار %s | ترک %s | consistency | Match Add Track and track locking. |
| Effect | افکت | جلوه | consistency | Match the existing plural Effects heading. |
| Effect: %s | افکت: %s | جلوه: %s | consistency | Match the Effects heading. |
| Transition | ترنزیشن | گذار | consistency | Match the existing plural Transitions heading. |
| Transition: %s | ترنزیشن: %s | گذار: %s | consistency | Match the Transitions heading. |
| Recording | در حال ضبط | ضبط | correction | A feature heading should not claim recording is in progress. |
| Luma Waveform | موج‌نمای لومای | شکل موج لوما | correction | Remove the dangling possessive form and name the luma waveform clearly. |
| My Views | نمای من | نماهای من | correction | Use plural views, matching the saved-layout menu. |
| Scopes | محدوده‌ها | ابزارهای سنجش | candidate | The current label means ranges; name the measurement instruments, with native editor confirmation for the final short label. |

### Polish (`pl`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Captions | Podpisy | Napisy | correction | Use the timed-subtitle term already present in Caption Toolbar. |
| Insert Caption | Wstaw podpis | Wstaw napis | correction | Match the subtitle toolbar. |
| Enter caption text... | Wpisz treść podpisu... | Wpisz tekst napisu... | correction | Match the subtitle toolbar. |
| Export Video | Eksport nagrań wideo | Eksportuj wideo | correction | Use the concise command form used by Export Project. |
| Import Files | Import plików | Importuj pliki | consistency | Match the same action's menu text without its ellipsis. |
| Property | Właściwości | Właściwość | correction | Use singular property for the table column, matching the English and paired value column. |
| Scopes | Zakresy | Przyrządy pomiarowe | candidate | Zakresy means ranges; a measurement-instrument label explains this submenu. Confirm the preferred local editor term. |
| Enable Timing | Włącz synchronizację | Włącz zmianę prędkości | correction | The tool changes clip speed by dragging its edges; the current wording suggests synchronization or merely turning on time. |
| Disable Timing | Wyłącz synchronizację | Wyłącz zmianę prędkości | correction | Use the same playback-speed term as the enabled state. |

### Portuguese (`pt`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Center on Playhead | Centralizar no Indicador de Reprodução | Centrar no cursor de reprodução | correction | Use European Portuguese centrar and match the playhead noun in the tooltip. |
| Center the timeline on the Playhead | Centralizar a linha do tempo no cursor de reprodução | Centrar a linha cronológica no cursor de reprodução | consistency | Match the existing Timeline heading and European Portuguese usage. |
| Pan timeline | Mover linha do tempo | Deslocar a linha cronológica | consistency | Match the existing Timeline dock heading. |
| Click: center · Drag: zoom | Clique: centralizar · Arraste: zoom | Clique: centrar · Arraste: zoom | correction | Use centrar consistently with the centering action. |
| Clip: %s | Clipe: %s | Clip: %s | consistency | Match the existing Clip noun rather than switching regional spelling in the tooltip. |
| Recording | Gravando | Gravação | correction | A dock title names the feature instead of asserting that recording is in progress. |
| Open Help Contents | Abrir Ajuda de Conteúdos | Abrir o índice da ajuda | correction | The command opens the help contents; the current word order is unnatural. |
| Video Preview | Pré-visualizar vídeo | Pré-visualização de vídeo | correction | Use a noun for the dock heading rather than a verb. |

### Romanian (`ro`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Center on Playhead | Centrat pe Playhead | Centrează pe cursorul de redare | correction | Use a command and a localized playback-cursor noun. |
| Center the timeline on the Playhead | Centrează cronologia pe Playhead | Centrează cronologia pe cursorul de redare | correction | Match the short action's playhead term. |
| Click: center · Drag: zoom | Click: centru · Trage: zoom | Clic: centrează · Trage: zoom | correction | Use the centering verb rather than the noun center. |
| Clip | Decupează | Clip | correction | The current text is the cropping/cutting command, not a clip noun. |
| Export Video | Exportă clip | Exportă video | correction | The command exports the project video, not only an individual clip. |
| Export Project | Export Proiect | Exportă proiectul | correction | Use a command, matching Import Project. |
| Import Project | Import Proiect | Importă proiectul | correction | Use a command, matching Export Project. |
| Open Help Contents | Deschideți conținutul ajutor | Deschide cuprinsul ajutorului | correction | Correct the grammar and express help table of contents. |
| Save Project As... | Salveaza proiectul ca... | Salvează proiectul ca... | correction | Restore the missing Romanian diacritic. |
| Thumb | Miniatura | Miniatură | correction | Use the correctly accented noun for a thumbnail. |
| Scopes | Scopuri | Instrumente de măsură | candidate | Scopuri means purposes/goals; this menu contains signal-measurement instruments. Confirm the preferred short editor label. |
| Enable Timing | Activează sincronizarea | Activează modificarea vitezei | correction | The tool changes clip speed by dragging its edges; the current wording suggests synchronization or merely turning on time. |
| Disable Timing | Dezactivează sincronizarea | Dezactivează modificarea vitezei | correction | Use the same playback-speed term as the enabled state. |

### Russian (`ru`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Captions | Подписи | Субтитры | correction | Match the timed-subtitle term already used in Caption Toolbar. |
| Insert Caption | Вставить подпись | Вставить субтитр | correction | Insert a timed subtitle cue rather than a generic label. |
| Enter caption text... | Введите текст заголовка ... | Введите текст субтитра... | correction | This is subtitle text, not title text. |
| Center on Playhead | Центр ползунка | Центрировать по позиции воспроизведения | correction | The current noun phrase names the slider center instead of issuing an action. |
| Center the timeline on the Playhead | Центр таймлайна на ползунке | Центрировать шкалу времени по позиции воспроизведения | correction | Use an action and the same Timeline noun as the dock. |
| Pan timeline | Переместить таймлайн | Переместить шкалу времени | consistency | Match the localized Timeline dock name. |
| Click: center · Drag: zoom | Клик: центр · Перетаскивание: масштаб | Щелчок: центрировать · Перетаскивание: масштабировать | correction | Describe both gestures as actions instead of isolated nouns. |

### Spanish (`es`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Center on Playhead | Centro en la cabeza de reproducción | Centrar en el cabezal de reproducción | consistency | Use the command infinitive and the same playhead noun as the longer tooltip. |
| Recording | Grabando | Grabación | correction | The dock title names the feature; grabando incorrectly asserts an active recording. |
| Emojis | Emoticonos | Emojis | correction | Emoji images and emoticons are not the same category; preserve the intended category name. |

### Turkish (`tr`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Captions | Başlıklar | Altyazılar | correction | This is the timed-caption editor, not the separate titles feature. |
| Caption Toolbar | Başlık araç çubuğu | Altyazı araç çubuğu | correction | Match Insert Caption, which already uses the subtitle term. |
| Enter caption text... | Başlık metnini yazın... | Altyazı metnini yazın... | correction | Use subtitle text rather than title text. |
| Center on Playhead | Oynatma Başlığına Ortala | Oynatma kafasına ortala | correction | Match the playhead noun in the longer tooltip; başlık suggests a title/header. |
| Clip | Parça | Klip | correction | Match the hover prefix and distinguish clips from tracks. |
| Lock track | Parçayı kilitle | İzi kilitle | consistency | Match Add Track and Track %s. |
| Unlock track | Parça kilidini aç | İzin kilidini aç | consistency | Match Add Track and Track %s. |
| Effects | Etkiler | Efektler | consistency | Match Effect and the effect hover prefix with the established editing noun. |
| Docks | Yanaşmalar | Paneller | correction | Name the dockable panels rather than the act of approaching/docking. |

### Vietnamese (`vi`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Captions | Chủ Đề | Phụ đề | correction | The current label means topics; this dock edits timed subtitles. |
| Insert Caption | Chèn chú thích | Chèn phụ đề | correction | Match Caption Toolbar and the caption text prompt. |
| Lock track | Khóa đường dẫn | Khóa rãnh | consistency | Match Add Track and Track %s; đường dẫn means path. |
| Unlock track | Mở khóa đường dẫn | Mở khóa rãnh | correction | Match the track noun rather than file-path terminology. |
| Launch Tutorial | Khỏi chạy hướng dẫn | Khởi chạy hướng dẫn | correction | Fix the typo Khỏi to Khởi. |
| Thumb | Thumb | Ảnh thu nhỏ | correction | Translate the English abbreviation as thumbnail image. |
| Jump To Start | Bắt đầu | Đến đầu | correction | This seeks to the start rather than starting playback. |
| Jump To End | Kết thúc | Đến cuối | correction | This seeks to the end rather than ending an operation. |
| Recording | Đang ghi âm | Ghi âm và ghi hình | correction | The dock supports microphone, screen, and webcam capture. Use a feature name covering audio and video, not an active-recording status or audio-only term. |
| Clip: %s | Đoạn phim: %s | Clip: %s | correction | Match the Clip noun and avoid implying all clips are films. |
| Scopes | Phạm vi | Công cụ đo | candidate | The current term means range/scope in general; name the measurement tools. Confirm preferred local editor wording. |
| Vectorscope | Phạm vi vector | Máy đo véc-tơ | candidate | The current term means vector range rather than the signal instrument; confirm the local instrument name. |
| Enable Timing | Bật thời gian | Bật công cụ đổi tốc độ | correction | The tool changes clip speed by dragging its edges; the current wording suggests synchronization or merely turning on time. |
| Disable Timing | Tắt thời gian | Tắt công cụ đổi tốc độ | correction | Use the same playback-speed term as the enabled state. |
| Recording View | Chế độ xem ghi âm | Chế độ xem ghi âm và ghi hình | correction | The workspace supports microphone, screen, and webcam recording, so its name must cover both audio and video. |

### Ukrainian (`uk`)

| English key | Before | Proposed / applied | Type | Why |
| --- | --- | --- | --- | --- |
| Captions | Підписи | Субтитри | correction | Match the timed-subtitle term already used in Caption Toolbar. |
| Insert Caption | Вставити підпис | Вставити субтитр | correction | This inserts a timed subtitle cue rather than a generic label. |
| Enter caption text... | Введіть текст заголовку... | Введіть текст субтитру... | correction | This is subtitle text, not heading/title text. |
| Transition: %s | Переход: %s | Перехід: %s | correction | Use the Ukrainian noun already present in Transition, not the Russian form. |
| Pan timeline | Переміщення часової шкали | Перемістити монтажний стіл | consistency | Match the existing Timeline heading and use a command form. |
| Export Video | Експортування відео | Експортувати відео | correction | Use an action infinitive matching Export Project. |
| Save Current Frame | Збереження поточного кадру | Зберегти поточний кадр | correction | Use an action infinitive matching Save Project. |
| Preferences | Налаштування | Параметри | consistency | Match the Preferences menu action. |
| Scopes | Діапазони | Вимірювальні прилади | candidate | The current term means ranges; this submenu contains measurement instruments. Confirm the preferred editor label. |
| Enable Timing | Увімкнути синхронізацію | Увімкнути зміну швидкості | correction | The tool changes clip speed by dragging its edges; the current wording suggests synchronization or merely turning on time. |
| Disable Timing | Вимкнути синхронізацію | Вимкнути зміну швидкості | correction | Use the same playback-speed term as the enabled state. |

## Validation performed

- Extracted all 26 language columns successfully with zero missing translations.
- Verified the inspected embedded-resource translations match all 25 loose catalogs.
- Checked `%s` placeholders in both the inventory and every proposed replacement.
- Checked every proposal's old value against the extracted catalog and rejected duplicate proposal keys.
- Verified first-level menu/toolbar selection excludes known deeper actions and placeholder menu entries.
- Regenerated the inventory into a separate directory to check deterministic output.

The initial translation implementation left runtime behavior and English unchanged. The subsequent
Play/Pause bug fix updates the playback action state and adds only the English message key Pause;
English documentation and existing message keys remain unchanged.
