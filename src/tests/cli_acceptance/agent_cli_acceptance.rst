Agent CLI acceptance measurements
================================

Measured on Linux, 2026-10-05, using five fresh agents: a baseline on the
previous CLI followed by four rounds of improvements. Each agent discovered
commands through help, edited through the CLI, and exported the same 20-second
1280x720, 24 fps reel from title/credits images, Sintel excerpts, and music.
Every export had 480 H.264 video frames, AAC audio, and passed a full FFmpeg
decode. MP4 container duration included about 22 ms of AAC padding; video and
audio streams were each 20 seconds.

Measured outcomes
-----------------

.. list-table:: First CLI invocation through session stop
   :header-rows: 1

   * - Run
     - CLI calls
     - Wall seconds
     - Summed CLI seconds
     - Unexpected errors
     - Response bytes
   * - Baseline
     - 48
     - 72.582
     - 9.728
     - 0
     - 34,007
   * - Round 1
     - 30
     - 88.811
     - 15.076
     - 2
     - 39,820
   * - Round 2
     - 35
     - 99.504
     - 15.461
     - 2
     - 51,081
   * - Round 3
     - 35
     - 75.655
     - 14.560
     - 0
     - 52,541
   * - Round 4
     - 33
     - 72.447
     - 14.595
     - 0
     - 63,175

Round 4 additionally made one deliberate failing call to verify atomic rejection
of an invalid batch reference. Its 422 stderr bytes are included in the response
total. Round 1 and 2 each included one missing JSON-file error caused by an agent
using an unavailable ``python`` executable to prepare the file; these are counted
but are not CLI implementation defects.

These are real agent-workflow observations, not a controlled speed benchmark.
Wall time includes reasoning and tool scheduling. Improved runs added waveform
and structured overview inspections; rounds 2–4 added split/history checks;
rounds 3–4 repeated views to measure caches. The final round added the negative
batch test. Baseline export ran asynchronously outside its measured start/status
calls; improved runs include about six seconds of export waiting inside a single
CLI call, with 12 internal status requests reported separately. Lower process
call counts do not imply elimination of internal RPC polling.

The final agent used 31 percent fewer CLI calls than baseline while performing
these additional checks. Structured context and help increased text output.
Images were files, never base64 payloads in the command responses.

What changed between rounds
---------------------------

* Baseline found eight manual keyframe calls for image fades. Added trim-aware
  ``clip fade``, named batch references, ``timeline overview``, native waveform
  mode, and client-side export ``--wait``.
* Round 1 wrote ``effects.add`` in a batch because the CLI group is ``effects``.
  Accepted that spelling alongside legacy ``effect.add`` and improved unknown
  method errors. Added ``clip split`` with returned left/right IDs and grouped
  undo/redo. Corrected stale waveform caches, disabled-audio handling, and
  one-based time-remapping coordinates.
* Round 2 expected ``project.profile`` at the start of its edit batch. Added it
  using existing UpdateManager transactions, with private preflight and undo/
  redo tests. Added source-reader reuse and a bounded thumbnail cache.
* Round 3 completed without errors. Clarified waveform extraction versus display
  mapping metrics, included JSON parameter names in command help, supplied
  default track names, and enabled lossless compression for exported frame PNGs.
* Round 4 completed without unexpected errors, including invalid-reference
  rejection with unchanged revision/state. Subsequent review aligned overview
  and fade frame calculations with native rounding for unsnapped clips, covered
  by regression tests.

Measured inspection costs
-------------------------

Final-round repeated full timeline view: **1.494 s to 0.146 s**, with 13 thumbnail
cache hits, no generated thumbnails, and no reader opens. Waveform view:
**1.022 s to 0.213 s**, with three source-cache hits and no audio decoding on the
repeat. Adjusting cached envelopes for the clip's volume/time curves still does
some work and is reported as mapped samples.

The zoomed view's initial cost fell from about 1.8 s in early rounds to about
0.8 s after reader/cache reuse. An isolated comparison of full and zoomed images
before/after that change found identical RGB pixels.

A 640x360 frame PNG fell from **923,528 to 241,526 bytes** with identical pixels
using default PNG compression, costing about 39 ms more encoding in an offline
comparison. Seven final-round PNGs totaled **1,170,053 bytes**, versus 1,852,177
bytes for the corresponding seven third-round images. Native full timeline
images were about 101 KB; waveform views about 58 KB. A five-clip overview was
about 5 KB before the final frame-coordinate clarification.

Validation and artifacts
------------------------

The final regression run passed **343 tests**, covering CLI behavior plus Query,
project data, history, live properties, and timeline helpers. A real GUI launched
under Xvfb also passed named-batch/split/effect edits, failed preflight without
changes, undo/redo, native thumbnail/waveform snapshots, and export waiting while
the session remained responsive. Platform execution in these rounds was Linux;
packaged macOS/Windows execution was not exercised.

Machine-readable summaries are in ``agent_cli_acceptance.json``. The reusable
measurement wrapper is ``src/tests/agent_cli_metrics.py``. Local videos, projects,
images, raw call logs, reports, and verification results are under
``/tmp/openshot-agent-metrics/{baseline,round1,round2,round3,round4}``.

The final reel is ``/tmp/openshot-agent-metrics/round4/reel.mp4``; its editable
project is ``reel.osp`` in the same directory. GUI smoke artifacts and logs are
under ``/tmp/openshot-agent-metrics/gui``.


Profile and export follow-up
----------------------------

Two additional fresh agents used CLI help alone to exercise profile discovery,
source matching, populated-project FPS undo/redo, portable custom profiles,
text/JSON/native-widget inspection, export presets, advanced settings, and
operation/job recovery. Artifacts are in ``/tmp/openshot-cli-profiles/round1``
and ``/tmp/openshot-cli-profiles/round2`` (local development artifacts).

* Round 1: 81 calls, 15.470 seconds cumulative CLI time, 106.474 seconds wall
  time. One product failure exposed nested preset routing with an explicit
  session; this was fixed. Three other failed calls were recoverable workflow
  mistakes. The text view's empty-track mismatch was also corrected.
  Eight-second 720p24 MP4 and audio-only WAV exports decoded cleanly.
* Round 2: 56 calls, 11.176 seconds cumulative CLI time. One existing-path save
  rejection was recovered using a new destination. No product blockers.
  A custom 640x352 24000/1001 profile survived save/reopen, and undo restored
  the original source profile and clip timing. Six-second 720p24 and 360p30
  MP4 exports decoded cleanly; three PNG sequence frames had correct dimensions.
  Export-only profile changes left the saved project byte-for-byte unchanged.

These broader correctness tasks differ from the earlier performance rounds;
their totals are not a controlled speed comparison. Hardware devices and
Windows/macOS packages still require platform acceptance.

Final verification passed 350 regression tests across CLI validation, profiles,
export settings, Query, project data, history, live properties, and timeline
helpers. A running GUI under Xvfb also passed populated-profile FPS changes with
exact undo/redo, session-bound preset discovery, text/native timeline inspection,
and a one-second export. GUI artifacts: ``/tmp/openshot-cli-profiles/gui``.

4K60 screencast trailer acceptance
---------------------------------

A fresh agent created a 24-second 720p30 OpenShot trailer using all ten supplied
4K60 screencasts and an excerpt from the shortest music file. The project used
13 screencast shots, title cards, feature labels, approximate 120 BPM beat-aligned
cuts, and music fades. Project editing and export used the CLI; local Python
created title assets and analyzed music, and FFmpeg verified the export.

Artifacts: ``/tmp/openshot-trailer-acceptance/run1``. These are local development
outputs, not repository assets. The final export decoded cleanly, with decoded
audio peak -2.7 dB. The agent recorded 34 calls and 183.56 seconds cumulative CLI
time, excluding two initial help calls and external analysis. Source contact
sheets took 100.42 seconds; the native timeline image took approximately 43
seconds; the main editing batch took 3.09 seconds. One failed call resulted from
an agent helper script shadowing Python's standard-library ``inspect`` module.

Known follow-up issues (not fixed in this checkpoint):

* Timeline context can label animated music volume as muted when its first
  keyframe is zero, even though later frames are audible.
* Reduced-resolution composed contact sheets showed speckled artifacts not
  apparent in export-derived previews. Identical-frame comparison and root-cause
  investigation remain necessary.
* Small thumbnail output does not eliminate expensive 4K60 source decoding.
  Proxy integration remains deferred.

Desktop sessions additionally passed deferred ``session show`` and immediate
``session start --show`` GUI checks, preserving IDs, revision, and history.
Shared GUI/CLI Qt bootstrap corrected high-DPI font/layout inconsistencies;
a 192-DPI GUI smoke test passed. Desktop Qt backend selection happens at startup,
so offscreen sessions cannot later acquire a visible window.
