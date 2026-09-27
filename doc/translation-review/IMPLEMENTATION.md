# Translation improvements applied

Initial translation pass applied on 2026-09-26 with **English unchanged**. The subsequent Play/Pause
bug fix adds only the English message key `Pause` and updates playback action text/tooltips; see the
follow-up section below. English `.rst` files and existing gettext message keys remain unchanged.

## Changes

- **225 reviewed UI translations** applied across all 25 website translation languages.
- **9 related Caption effect names** aligned with the Captions dock and documentation. This avoids
  showing two different names for the same feature.
- **366 documentation translations in 125 PO files** updated: headings, explicit UI/menu references,
  and related caption, razor, and retiming prose. Translation word order and grammatical agreement
  were preserved; cross-reference targets, keyboard shortcuts, and substitution tokens are unchanged.
- **12 tentative terminology candidates** remain deferred. Their existing translations are unchanged.

The authoritative UI sources are in the sibling checkout:

- `../translations-2.0/src/language/openshot/{locale}.po` — edited source, with matching `.mo` files built.
- `../translations-2.0/src/language/combined/{locale}.po` and `.mo` — rebuilt merged catalogs.
- `../translations-2.0/src/language/output/OpenShot_{locale}.qm` — rebuilt Qt catalogs.

The application repository contains:

- `src/language/OpenShot_{locale}.qm` — the 25 updated runtime catalogs.
- `src/language/openshot_lang.py` — regenerated embedded resources, with the neutral Qt binding import.
- `doc/locale/{locale}/LC_MESSAGES/*.po` and `.mo` — updated documentation catalogs.

Existing unrelated work in the sibling Bazaar checkout was preserved. The broad `compile.py` entry point
was not run because it operates on every language and reverts its QRC template; its merge/header logic
was reused for only the affected 25 locales. The QRC file list did not need to change.
The large generated Python resource diff is compiled translation data, not application logic.

## Correction to the initial review

The internal name `dockAudioRecording` was misleading: `AudioRecordingDockContent` supports microphones,
screen capture, and webcams. The initial audio-only recommendations were corrected before applying:

- Simplified/Traditional Chinese Recording headings use `录制` / `錄製`; their existing Recording View
  translations are retained.
- Japanese uses `録音・録画` and `録音・録画ビュー`.
- Korean uses `녹음/녹화` and `녹음/녹화 보기`.
- Vietnamese uses `Ghi âm và ghi hình` and `Chế độ xem ghi âm và ghi hình`.

This withdraws two unnecessary Chinese view-name changes and adds one related Vietnamese view-name
correction, bringing the original 226 approved edits to 225. The final recommendations and review
spreadsheet reflect this correction. The Play/Pause tooltip was subsequently fixed as described below.

## Audit files

- [REVIEW.md](REVIEW.md): per-language before/after wording and brief reasons.
- [review-decisions.csv](review-decisions.csv): review-time wording, current wording, and applied/deferred decisions.
- [recommendations.json](recommendations.json): final recommendations; `current` means the review-time value.
- [applied-changes.json](applied-changes.json): every actual UI/documentation edit, source file, before/after
  values, rationale, generated-file list, and exact compiled runtime differences. It also records
  local backups and source-file hashes.
- [main-window-labels.csv](main-window-labels.csv) and [JSON](main-window-labels.json): refreshed extraction
  of the **current rebuilt catalogs**, not the original pre-edit values.

Rerun the inventory from the application checkout with:

```sh
python3 src/language/extract_main_window_labels.py
```

## Validation

- All 150 edited source PO files retain their original message IDs, contexts, plural sources, metadata,
  and all unrelated translations.
- Compiled Qt catalogs were compared message by message before and after: **234 intended changes,
  zero other translation changes**, with no messages added or removed.
- Verified every one of the 600 edits by loading its MO file. Verified all 234 UI edits again through
  the embedded Qt resources.
- All **107 embedded catalogs** byte-match their on-disk counterparts.
- Existing validator: **3,041 strings across 25 UI catalogs**, plus **675 documentation PO files**; passed.
- `msgfmt --check` passed for rebuilt core, combined, and documentation catalogs.
- German Sphinx dummy build completed successfully using the translated catalogs. This validates
  document processing; it is not a visual layout review.
- English `.rst` and POT hashes match the pre-edit snapshot. Documentation reference targets,
  shortcuts, substitution tokens, and backtick counts are preserved.

The application changes and a task-only UI source patch are prepared for the Git commit. The sibling
Bazaar checkout has substantial pre-existing changes and is not being committed or pushed as part of this
Git delivery. Its edited UI sources and rebuilt catalogs remain local.

[ui-source-updates.patch](ui-source-updates.patch) preserves only this task’s edits to the 25 authoritative
UI PO files, including Pause, relative to their pre-task contents. Apply it to the matching translation
source snapshot with `patch -p1 < ui-source-updates.patch`, then use the translation build pipeline.
It is not a patch against the older, unmerged Launchpad export; reconcile newer source messages before
applying to that older branch. The MO files are build outputs created for the affected catalogs.

## Follow-up: Play/Pause tooltip bug fixed

Both Base/Humanity and Cosmic now update the QAction text and tooltip with the icon:
**Pause while playing, Play while paused**. A shared BaseTheme helper handles the translated labels,
including when the toolbar button is not mounted.

This follow-up adds the English message key `Pause` to the POT and supplies translations in all 25
website languages. All other English messages and all English documentation remain unchanged.
UI PO/MO/QM catalogs and embedded resources were rebuilt; comparison against the preceding catalogs
confirms that each language adds only Pause and changes no existing messages.

The regression test in `src/tests/test_playback_tooltip.py` exercises both themes through repeated
play/pause transitions, checking translated action text and the actual toolbar-button tooltip.
The inventory now includes 108 labels. [play-pause-labels.json](play-pause-labels.json) records the new translations.

Follow-up checks passed: the two-theme regression test, all 25 embedded/MO Pause translations,
and the existing validator (3,042 strings across 25 UI catalogs and 675 documentation PO files).

Pre-commit verification: the translation validator passed against **all 107 UI catalogs** (3,042
strings) and all 675 documentation PO files. The existing Cosmic icon test fixture was updated to
provide the app translation method and assert both playback labels.

Final regression run: all **51 main-window and playback-tooltip tests passed**. The task-only
source patch was applied to a copy of the pre-task PO files and reproduced all 25 final files exactly.
