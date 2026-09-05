# Sentry triage: 2026-09-05

Scope: the first ten results sorted by affected users for
`release:openshot@4.0.0 firstSeen:>=2026-08-30`, inspected on September 5.
Both repositories started clean on `develop`; changes are on
`sentry-fix-2026-09-05` in openshot-qt and libopenshot.

## Decisions

| Issue | Disposition | Evidence and change |
| --- | --- | --- |
| [FY5H](https://openshot.sentry.io/issues/OPENSHOT-FY5H) | No code change | `KeyboardInterrupt` at entry to a Qt event filter. This indicates interruption but does not establish a defect in the filter or explain a possible preceding hang. Do not suppress the report or claim to fix a hang without more evidence. |
| [FYCZ](https://openshot.sentry.io/issues/OPENSHOT-FYCZ) | Fixed in libopenshot | JUCE creates audio device types lazily; selecting a backend before enumeration is a no-op. Enumerate before selecting the requested type so DirectSound input names are not passed to the default WASAPI backend. |
| [FY6Z](https://openshot.sentry.io/issues/OPENSHOT-FY6Z) | Fixed in openshot-qt packaging | The Linux shared-library filename filter skipped the unversioned `libopenshot-wayland-capture.so`. Include it explicitly and scan its dependencies. Existing host-provided PipeWire/SPA exclusions remain in effect. |
| [FYT6](https://openshot.sentry.io/issues/OPENSHOT-FYT6) | Fixed in openshot-qt | All six inspected events attempt to open MP4, MKV, or JPG files as projects. Reject non-OSP local paths before clearing project state, with guidance to Import Files. Preserve uppercase OSP extensions and Android document URIs. Legacy project parsing is unchanged. |
| [FYN7](https://openshot.sentry.io/issues/OPENSHOT-FYN7) | Fixed in openshot-qt | Removing an open runtime recording fails with Windows sharing violation 32 when the destination already exists. Retain that source and finish updating file/clip paths to the project asset. |
| [FYA3](https://openshot.sentry.io/issues/OPENSHOT-FYA3) | Fixed in openshot-qt | Moving an open recording fails after copying it. Copy through a temporary file in the destination directory and publish the complete copy before attempting source cleanup. Sharing violation 32 during cleanup is tolerated; other errors still propagate to the existing handler. |
| [FYP5](https://openshot.sentry.io/issues/OPENSHOT-FYP5) | Deferred | Five events contain truncated timeline-load JSON. `Timeline::ApplyJsonDiff` replaces underlying exceptions with a generic InvalidJSON error. The failing field/reader cannot be identified from the available payload. Investigate with the full failing project and original exception in a separate branch; avoid relaxing JSON validation speculatively. |
| [FYMJ](https://openshot.sentry.io/issues/OPENSHOT-FYMJ) | Deferred | The two events are different environmental failures: connection reset and disk full. Existing download handling displays a warning and revalidates files. Reliable retry/resume, mirrors, and storage handling deserve separate work; no speculative retry or telemetry suppression here. |
| [FYCC](https://openshot.sentry.io/issues/OPENSHOT-FYCC) | Fixed in libopenshot | `FFmpegReader::Close` decoded pending packets before releasing resources, potentially allocating images and throwing during shutdown. Discard buffered output on close and retain codec/resource cleanup. This addresses shutdown decoding, not general memory exhaustion during playback. |
| [FYAA](https://openshot.sentry.io/issues/OPENSHOT-FYAA) | Fixed in openshot-qt | A context-menu event wrapper reached the mouse-release branch. Check for `QMouseEvent` before accessing `button()`; middle-click dock closing remains supported. |

## Validation

- 126 Python tests passed across `tests.test_main_window`,
  `tests.test_project_data`, and `tests.test_recording_preview` using
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 -m unittest`.
- Regression coverage includes first and repeated saves of locked recordings,
  interrupted copies followed by successful retry, file/clip reader paths,
  media rejected before modifying project state, valid project paths, and
  mismatched Qt event wrappers plus left/right/middle mouse releases.
- Built `openshot-FFmpegReader-test` and `openshot-AudioRecorder-test` locally.
  All seven AudioRecorder cases passed (47 assertions). The FFmpegReader suite
  passed 23 of 25 cases; the two VAAPI cases fail to create a hardware device
  on this host and also fail against the pre-fix installed library.
- The new close/reopen regression passes eight assertions with the rebuilt
  library and fails against the installed pre-fix library: close decodes 17
  additional packets in the old implementation.
- Executed the packaging selection loop against library paths without
  underscores, confirming inclusion of the Wayland module and existing
  versioned libraries. A complete AppImage was not built.
- Python regression checks also fail against the original methods loaded
  from `HEAD`, confirming the event, project-open, and recording regressions.
- `git diff --check` passed in both repositories.

## Remaining platform checks

Test a packaged Windows build with a DirectSound input, recording then saving
while its reader remains open, and closing a project under memory pressure.
Build an AppImage and test Wayland capture with host PipeWire and the desktop
portal. The Windows backend correction is based on the JUCE implementation;
Windows microphone hardware is not available in this Linux environment.

When a runtime recording remains locked, its complete project copy is used and
the original runtime file is retained. This deliberately favors preserving
media over forced cleanup. No new background cleanup mechanism is introduced.

## Follow-up: VAAPI test prerequisites

The host's NVIDIA render node is accessible, but both `vainfo` and standalone
FFmpeg fail to initialize VAAPI. The tests previously treated any render node
and FFmpeg's compiled VAAPI support as sufficient. They now probe
`/dev/dri/renderD128` with the linked FFmpeg library, matching the adapter used
by the tests. CTest reports unavailable prerequisites as skipped; decode
assertions remain unchanged when initialization succeeds.

After this test-only correction, the full libopenshot suite completed in
99.01 seconds: 517 passed, two VAAPI tests skipped, zero failures (519 total).

## Final review follow-ups

- Restore same-filesystem rename for runtime recordings, avoiding a full copy
  and its extra disk-space requirement. Fall back to atomic copying only for
  cross-device moves or Windows sharing violation 32. Save As continues copying
  the previous project's assets. Tests cover the no-copy fast path and EXDEV
  fallback alongside the existing locked-reader and interrupted-copy cases.
- Accept OpenShot repair backup filenames ending in `.osp.bak` or
  `.osp.bak.<number>`, case-insensitively, as well as `.osp`. Reject misleading
  suffixes and media inside directories containing `.osp`. Project contents
  still pass through the existing loader; Android document URIs are unchanged.
- Seven of the top ten reports are addressed across the two repositories;
  FY5H, FYP5, and FYMJ remain outside this fix batch as documented above.
