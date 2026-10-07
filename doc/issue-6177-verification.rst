Issue 6177: disappearing one-frame clips
=======================================

Findings and changes
--------------------

The report at https://github.com/OpenShot/openshot-qt/issues/6177 includes a
broken project with 227 clips, 138 files, and 134 orphaned file references.
The load-time path validator deleted those clips solely because their file IDs
were absent, even if their embedded reader pointed to existing media. Saving
also allowed these references to remain inconsistent. Before path validation
and saving (including backup saves), the fix reuses a file with the same path
or restores its entry from the embedded reader. Missing media still uses the
normal locate/skip dialog. This fixes the destructive load behavior and guards
saving; the operation which originally orphaned the reporter's IDs has not
been established from the supplied projects.

Profile conversion independently rounded clip positions and trims, then
shortened preceding clips to close any small gap/overlap, even across tracks
and between clips and effects. For five adjacent 30-fps one-frame clips,
conversion to 25 fps rounded two positions to the same time, reducing a clip's
duration to zero. It also left the stored duration stale. Conversion now keeps
positive clips at least one frame long, updates duration, and preserves only
originally touching boundaries within a track and object type. Intentional
gaps and overlaps are not treated as rounding errors. Joined clips move to the
preceding clip's new end instead of stretching a clip to fill a rounding gap.
A sequence of one-frame clips becomes longer at a lower frame rate and shorter
at a higher frame rate, keeping every clip one frame long.

Finally, TimelineSync.GetLastFrame subtracted one from libopenshot's already
1-based last playable frame number. Five-frame projects therefore stopped on
frame four. The fix uses GetMaxFrame directly (clamped to at least one).

Typing .04 at 30 fps and getting approximately .033 is expected frame
quantization. Issue 04 (increasing multiple clip durations overlaps their
unchanged positions) is a separate ripple-editing feature request and is not
changed here. Thumbnail alignment has not been independently verified in the
Windows UI; stale duration after profile changes is fixed.

Manual verification
-------------------

Using the Python environment configured for this checkout, generate fixtures::

    python3 benchmarks/generate_issue_6177_projects.py /tmp/openshot-6177

The generator writes five numbered PNGs and four projects, with current version
metadata and a zoom level that makes the one-frame clips visible. Open them in the
modified checkout:

* ``five-frames-25.osp`` and ``five-frames-30.osp``: zoom in, step through all
  five frames, then play from Home. The final preview should be the blue 5.
  Pressing Play again at the end should leave the final frame visible.
* ``five-frames-30.osp``: switch to HD 720p 25 fps. All five clips should remain
  nonempty and adjacent. Save, close, and reopen; all five should remain.
  Repeat the opposite profile change using ``five-frames-25.osp``.
  In particular, converting 25 to 30 fps should give all five clips a duration
  of approximately .033 seconds; clip 3 must not become .067 seconds.
* ``gapped-frames-25.osp``: the last one-frame clip is at 40 seconds. Seek/play
  through the end, then Remove All Gaps on Track 5 and repeat. Clip 5 should
  display in both cases.
* ``orphaned-files-25.osp``: deliberately contains four orphaned references
  (one same-path relink and three missing media entries). Opening should show
  five clips and five Project Files. Save and reopen to verify recovery persists.
  The old code deletes four of these clips on load.

On this workspace the native bindings are available in the sibling build,
while the globally installed Python module cannot find its shared library.
Use these environment settings for the commands above, tests, and launching::

    export LD_LIBRARY_PATH="$PWD/../libopenshot-git/build/src${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export PYTHONPATH="$PWD/../libopenshot-git/build/bindings/python:$PWD/src"
    /usr/bin/python3 src/launch.py

For headless tests add ``QT_QPA_PLATFORM=offscreen``. Do not set that platform
when launching the GUI for manual verification.

Automated validation
--------------------

Run from the repository root with libopenshot and Qt available::

    QT_QPA_PLATFORM=offscreen python3 -m unittest \
        src.tests.test_one_frame_clips src.tests.test_project_data \
        src.tests.test_keyframe_scaler src.tests.test_json_data \
        src.tests.test_query src.tests.test_timeline_helpers \
        src.tests.test_recording_preview src.tests.test_export_clips

New regression tests failed against the original code. They cover one-frame
profile changes, trimmed short clips, intentional gaps/overlaps, separate
tracks/effects, normal and backup save/load, orphan relinking/reconstruction,
and missing-media skip decisions. Native rendering verifies all five frame colors and the final blue frame at
both 25 and 30 fps, including conversion in both directions and native clip
serialization. Repeated conversion checks that every clip stays one frame. Preview
callback coverage checks stopping at frame five and looping to frame one.

The downloaded broken project was also passed through the repaired validator:
227 clips remained, with 222 files and zero orphan references, matching the
reporter's repaired project counts. The ZIP contains only project JSON, so
that attachment check mocked path existence; it does not demonstrate playback
of the reporter's original media. Real PNGs are used by the native rendering
and save/load tests. Validation here is on Linux with libopenshot 1.0.1, not a
manual Windows 11 playback run.

Fixture regression coverage also runs the generator, loads every generated project
through ProjectDataStore.load (including migrations), and verifies five opaque
clips on valid tracks, useful zoom, and red first/blue last rendered frames.
