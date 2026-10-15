.. Copyright (c) 2026 OpenShot Studios, LLC. GPL-3.0-or-later.

Agent CLI
=========

The common packaged entry point is **the installed OpenShot executable followed
by** ``--cli``. Dispatch happens before GUI/Qt initialization. Start with the
command overview and workflow::

   # Linux AppImage
   ./OpenShot.AppImage --cli help
   ./OpenShot.AppImage --cli --help
   ./OpenShot.AppImage --cli session start

   # Windows PowerShell, from the OpenShot installation directory
   & .\openshot-qt.exe --cli help
   & .\openshot-qt-cmd.exe --cli session list

   # macOS (adjust if installed elsewhere)
   "/Applications/OpenShot Video Editor.app/Contents/MacOS/openshot-qt" --cli help

Bare ``--cli``, ``--cli help``, and ``--cli --help`` show the same overview.
Help becomes more specific as you navigate commands::

   openshot-cli clip help
   openshot-cli clip keyframe help
   openshot-cli clip keyframe set help
   openshot-cli edit help

Group help includes editing workflows and examples; operation help describes
arguments and behavior. All of these help commands work without a session.

Windows ``openshot-qt-cmd.exe`` is the console companion, replacing the old
``openshot-qt-cli.exe`` debug-launcher name. Both accept ``--cli``; without it,
both launch the editor. The console companion is useful for interactive shells
that do not wait for GUI-subsystem executables. The main executable restores
missing standard streams for CLI use while retaining redirected pipes/files.
Neither command assumes the installation directory has been added to PATH.

The direct ``openshot-cli`` alias (``openshot-cli.exe`` on Windows) remains
available, including through Python/package console entry points. Throughout
this guide, replace ``openshot-cli`` with your installed executable plus ``--cli``
when using the common entry point. From source, use ``python3 src/launch.py --cli``
or ``python3 src/cli.py`` in the same Python/native-library environment as OpenShot.

The CLI controls a running editor or a persistent headless session. Changes use
the existing Query objects and UpdateManager, including GUI updates and undo/redo.
Windows/macOS frozen artifacts still require platform acceptance testing.

AppImage commands retain the caller's working directory, including relative
media paths and ``@batch.json`` files. Background sessions and export workers
relaunch the backing AppImage so their lifetime does not depend on the client's
mount. Keep the AppImage file available while using the session. Extracted bundles
also support ``./squashfs-root/AppRun --cli ...``; they use local executables and
must remain on disk for the session's lifetime. Normal double-click launches
continue to open the editor.

Help has one consistent pattern::

   openshot-cli help
   openshot-cli session help
   openshot-cli clip add help
   openshot-cli effects list
   openshot-cli effects audiovisualization help
   openshot-cli effects audiovisualization help --property background

``--help`` is equivalent to trailing ``help``. ``agent`` supplies a concise
workflow guide with time conventions, batch semantics, and inspection limits.
Static help needs neither Qt nor libopenshot. Effect-specific help requires the
installed engine, but no running editing session.

``effects list`` is the available catalog, including short descriptions.
``effects instances`` lists effects attached to clips, with parent clip IDs.
Effect help combines explanatory text from OpenShot's user guide with defaults,
enums, types, and property ranges queried from the installed libopenshot.
Class names, display names, and underscore aliases resolve to the same effect.

Sessions and outputs
--------------------

GUI instances register a local command endpoint after startup. A headless session
starts without creating the main editor window::

   openshot-cli session list
   openshot-cli session start
   openshot-cli session start --show
   openshot-cli --session SESSION_ID session show
   openshot-cli --session SESSION_ID project get
   openshot-cli --session SESSION_ID project profile get

On a desktop, ``session show`` creates the editor in the same process and keeps
the live project, IDs, history, export jobs, and connection. Repeated calls raise
the existing window. ``session start --show`` opens it immediately. Sessions
started without a display, or with ``QT_QPA_PLATFORM=offscreen``/``minimal``,
cannot later show a desktop window: Qt selects its display backend at startup.
For those sessions, save and open the project in a new desktop session. Sessions
created before this feature also need a restart. Once shown, close the session
through the editor window.

Global options (``--session``, ``--timeout``) go before the command. Set
``OPENSHOT_SESSION`` to select a session for repeated calls. With no explicit
selection, exactly one reachable session is required. ``session serve`` stays
in the foreground for supervisors; ``session start`` returns after a background
host registers. ``session stop`` refuses unsaved changes and active exports.
Use ``--discard`` only to intentionally discard unsaved edits.

Results are JSON on stdout, except the default text timeline view. Errors are JSON on stderr with exit status 1;
argument-parser errors exit 2. Mutations return compact summaries with an
``inspect`` command. ``get`` returns native object JSON. Project replies include
a revision; effect catalog replies do not require a session. Logs from headless
sessions live beside their registry records. ``OPENSHOT_SESSION_DIR`` overrides
the default ``~/.openshot_qt/sessions`` directory.

The transport is length-prefixed JSON-RPC over Qt local IPC: Unix domain sockets
on Linux/macOS and named pipes on Windows. Session records include a random
authentication token and are created with restrictive permissions. Do not share
the session registry with other users. No TCP listener is opened. Commands run
on the application's owning thread; long exports run in a separate process
against a snapshot. Session revisions are local to the running process.

Editing
-------

Use the IDs returned by import/add/list, and discover layer numbers with
``project get``::

   openshot-cli file import /absolute/path/video.mp4
   openshot-cli clip add FILE_ID --layer 2000000 --position 3 --start 10 --end 17 --volume 0
   openshot-cli clip set CLIP_ID --json '{"volume":0.5}'
   openshot-cli clip keyframe set CLIP_ID --property volume --frame 301 --value 0
   openshot-cli clip keyframe set CLIP_ID --property volume --frame 331 --value 1
   openshot-cli effects add CLIP_ID saturation
   openshot-cli effects set EFFECT_ID --json '{"saturation":1.2}'
   openshot-cli project save /absolute/path/edit.osp

The example keyframes assume a 30fps project and a clip trimmed at source 10s.
Position is in timeline seconds; start/end are source seconds, with end exclusive.
Frames start at 1. File thumbnail frames use source FPS. Timeline frames use
project FPS. Clip keyframes use source coordinates at project FPS, so trimming
the clip does not move its first visible keyframe to frame 1.

Choose the project profile early when possible; populated projects also support
profile changes through the existing FPS conversion and undo system. ``--audio-only`` on clip creation
suppresses video, including embedded cover art in music files. To use that clip
for Audio Visualization instead, enable its video and audio, and follow the
effect's help for transparent overlays and layer placement.

``set`` merges top-level properties. Scalars turn keyframed properties into
constants. A supplied nested curve replaces that curve; use ``keyframe set`` to
change just one point. JSON arguments accept inline JSON, ``@file.json``, or
``-`` for stdin. Property names, types, enums, keyframes, references, and timing
are checked before changes enter update listeners. Errors identify the field,
expected value, received value, and a correction where possible. GUI slider
ranges are advisory where the engine supports values beyond them.

``edit apply --json @edits.json --expect-revision 12`` accepts up to 256 ordered
mutation commands, using dotted command names such as ``clip.set`` and
``effects.add`` (the older ``effect.add`` spelling also works)::

   [
     {"method":"project.profile.set","params":{"id":"builtin:01280x0720p0024_16-09"}},
     {"method":"file.import","as":"media","params":{"path":"/tmp/video.mp4"}},
     {"method":"clip.add","as":"shot","params":{"file_id":{"$ref":"media.id"},"layer":1000000,"start":10,"end":15}},
     {"method":"clip.fade","params":{"id":{"$ref":"shot.id"},"fade_in":0.5,"fade_out":0.5}}
   ]

The optional ``as`` binds a result for later commands in the same batch. A
``{"$ref":"shot.id"}`` object substitutes that result's field. References only
resolve earlier names; misspellings, forward references, and duplicate names
fail before live updates. The response includes ordered compact results and a
``refs`` map of actual IDs. IDs still come from Query; the existing UpdateManager
transaction groups all JSON updates for undo/redo.
``project.profile.set`` also supports populated timelines. Opening, saving,
exporting, and inspection commands stay outside edit batches. Each
command's help lists its JSON parameter names, including the underscore spelling
of shell flags (for example, ``--fps-num`` becomes ``fps_num``).

``clip fade ID --in 0.5 --out 0.5`` calculates source-trim keyframe coordinates
automatically. It replaces the alpha curve; ``--property volume --value 0.25``
instead creates an audio fade with a 0.25 peak gain. Durations must fit between
the first and last visible frames; fade-out reaches zero on the last frame.

``clip split ID --at 6.5`` uses timeline seconds, snaps to the nearest project
frame, and keeps both halves. It retains source-coordinate curves and duplicates
effects with fresh IDs on the right half, following the editor's slicing behavior.
The left half retains its ID. The response reports requested/actual split times
and both summaries; a named batch result supports ``{"$ref":"cut.right.id"}``.
Splits reject endpoints and locked tracks. Undo restores the original clip in
one transaction.

All commands in edit batches preflight against a detached project before any live updates.
Invalid input leaves the live project and revision unchanged. Valid batches form
one undo group. Unexpected runtime failures can still produce partial changes;
errors report completed operations. A timeout does not imply cancellation, so
inspect state before retrying mutations.

Precise keyframe editing
------------------------

``clip``, ``transition``, and ``effects`` support ``keyframe list``, ``set``,
``remove``, ``clear``, ``transform``, ``copy``, and ``paste``. Property paths can
address nested curves, such as ``color.red`` on a Chroma Key effect. Editing a
nested curve preserves sibling channels. Run ``keyframe list ID`` without a
property to discover curve paths and point counts. Discovery and point listings
include trim/position timing context; point listings also report native frame
coordinates. ``get`` and ``properties`` expose the complete native object and
property metadata. Errors identify invalid fields, suggest close property names,
and explain coordinate corrections.

Choose coordinates explicitly with ``--space native|clip|timeline`` and
``--unit frames|seconds``. All frames use project FPS and are 1-based; seconds
start at zero and snap to the nearest frame. Native is the existing engine
keyframe coordinate (including source trim). Clip coordinates start at the
visible clip in-point; timeline coordinates start at project time zero. Attached
effects use their parent clip's timing. These coordinates address animation time,
not the media frames selected by a time-remapping curve.

For a clip positioned at 5 seconds, trimmed at 2 seconds, in a 30 fps project,
clip frame 1, timeline frame 151, and native frame 61 address the same point.
Position and trim snap independently to the project frame grid. Listing an entire
curve can include hidden points with nonpositive clip/timeline coordinates.
Legacy ``--frame`` still means a native frame and cannot combine with ``--at``.

Examples::

   openshot-cli clip keyframe set CLIP --property location_x --space clip --unit seconds --at 0 --value -1
   openshot-cli clip keyframe set CLIP --property location_x --space clip --unit seconds --at 1 --value 0 --interpolation bezier --handles '{"handle_left":{"X":0.2,"Y":0.9}}'
   openshot-cli effects keyframe set EFFECT --property color.red --space clip --at 31 --value 200
   openshot-cli clip keyframe list CLIP --property location_x --space clip --unit seconds
   openshot-cli clip keyframe transform CLIP --property location_x --space clip --start 1 --end 31 --scale 2 --offset 15
   openshot-cli clip keyframe copy TARGET --property location_x --source-id SOURCE --space clip --start 1 --end 31 --at 1 --mode merge
   openshot-cli clip keyframe remove CLIP --property location_x --space clip --at 31
   openshot-cli clip keyframe clear CLIP --property location_x --value 0

Keyframe ranges are **inclusive**, unlike clip-selection time ranges. List emits
``points`` whose ``co.X`` values use the requested coordinate space/unit. Pass that
array to ``keyframe paste --json @points.json`` with the same space/unit, choosing
``--mode merge`` (replace matching frames, retain others) or ``--mode replace``
(replace the entire curve). ``copy`` accepts a source of the same object kind,
an optional ``--source-property``, and anchors the first selected source point at
``--at`` on the target. Other curves and source objects remain unchanged.

``transform`` applies a positive time scale around the first selected point, or
``--pivot``, followed by a signed ``--offset`` in the chosen unit. Frame snapping
that creates duplicate coordinates is rejected, including collisions with points
outside the selected range. Native coordinates must remain at least 1. Native
normalized Bézier handles and interpolation travel with each point; handles are
not absolute frame coordinates. ``set --handles`` changes only supplied handles.
Interpolation belongs to the destination point.

``clear`` retains a constant base point at native frame 1: specify ``--value`` or
sample the existing curve with ``--at`` (default native frame 1). Removing the last
point also retains a constant base, so subsequent keyframe additions remain valid.

Selecting and editing many clips
--------------------------------

The existing ``edit apply`` engine remains the transaction and validation engine.
It now accepts ``--dry-run`` to validate without publishing edits. ``edit bulk``
expands a small per-clip command template into that same engine; it does not use
a separate editing or undo implementation.

First preview a selection::

   openshot-cli edit select --json '{"layer":1000000,"start":5,"end":20,"effect":"Saturation"}'

Selectors support ``ids`` (unique clip ID array), ``layer``, ``start``/``end``
(timeline seconds), ``file_id``, and ``effect`` (class name or alias). Filters
combine with AND. Time ranges select clips overlapping ``[start, end)``; they do
not trim those clips. Results are ordered by position, layer, then ID, and include
IDs, summaries, lock state, and the current revision. Unknown IDs are errors.
An empty selector is rejected; use ``{"all":true}`` explicitly for every clip.
Selections are bounded to 256 clips and are never silently truncated.

For example, save this array as ``templates.json``::

   [
     {"method":"clip.adjust","params":{"values":{"position":{"add":2},"volume":{"multiply":0.5}}}},
     {"method":"effects.add","as":"look","params":{"type":"Saturation"}},
     {"method":"effects.keyframe.set","params":{"id":{"$ref":"look.id"},"property":"saturation","space":"clip","at":1,"value":0}},
     {"method":"effects.keyframe.set","params":{"id":{"$ref":"look.id"},"property":"saturation","space":"clip","at":31,"value":1.2}}
   ]

Validate it, then apply against the revision returned by selection::

   openshot-cli edit bulk --select '{"ids":["CLIP_A","CLIP_B"]}' --json @templates.json --dry-run
   openshot-cli edit bulk --select '{"ids":["CLIP_A","CLIP_B"]}' --json @templates.json --expect-revision 42

Existing-clip commands inherit ``id``; ``effects.add`` inherits ``clip_id``.
Omit these target parameters in templates. Effect edits must reference an earlier
named result. Names are local to each selected clip, so ``look.id`` refers to a
different effect for each clip. To change existing effect instances by explicit
ID, continue using ``edit apply``. The selected ID set is fixed before expansion;
changes to position or effects do not change the remaining targets.

``clip set`` applies absolute properties; ``clip adjust`` applies ``multiply``
then ``add`` to a numeric property or every value in a curve, preserving point
timing, interpolation, and normalized handles. It validates resulting values,
including nonnegative positions and volume. Structural fields remain protected.

Bulk operations reject empty selections, locked target tracks, and more than 256
expanded commands. Every expanded operation passes detached preflight before any
live edit. Dry runs do not reserve generated IDs. Use ``--expect-revision`` to
reject stale selections. Successful batches are one undo step, including after
save/reopen. GUI refreshes are batched. Unexpected runtime/listener errors can
still leave a partial transaction; the error reports completed operations and
undo reverts that group, as with ``edit apply``.

Profiles
--------

Discover profiles and match imported video without guessing IDs::

   openshot-cli profile list --search 720
   openshot-cli profile get builtin:01280x0720p0024_16-09
   openshot-cli profile match --file FILE_ID
   openshot-cli project profile get
   openshot-cli project profile set --from-file FILE_ID
   openshot-cli project profile set builtin:01280x0720p0024_16-09
   openshot-cli project profile set --json '{"width":640,"height":352,"display_ratio":{"num":20,"den":11},"fps":{"num":24000,"den":1001}}'

Catalog entries include stable IDs, descriptions, dimensions, rational FPS,
aspect ratios, and scan settings. List/search is paginated. Source matching
returns exact IDs and ranked alternatives with explicit differences. Setting
from a file requires an exact match unless ``--create-custom`` is specified;
it never silently chooses a nearby profile. Still images and audio-only sources
cannot define a video profile. Matching uses declared source FPS.

Custom settings are embedded in the saved project, including rational rates,
so reopening does not require installing a separate profile file. Project profile
changes use existing frame-rate conversion and one undo transaction. Undo/redo
restores clip timing and keyframes, including rounding-sensitive positions.
Export can independently select a profile without changing the project.

Saved undo history follows the editor's history-limit preference. The limit is
a soft action budget: all records belonging to retained transactions are kept,
so saving cannot truncate a large batch into a partial undo action. Zero disables
saved history. The separate 256-command batch request bound still applies.

Inspection and export
---------------------

Frame images default to 320x180 pixels; contact sheets default to 160x90 per
tile (plus timecode labels). ``--width`` and ``--height`` select output pixels,
independent of desktop DPI. Timeline frame rendering uses the requested size;
source decoding may still need full-resolution frames. Native timeline diagrams
retain their separate 1280px default for readable labels.

Frame images and contact sheets include exact sample/frame metadata::

   openshot-cli file thumbnail FILE_ID --frame 301 --output /tmp/source.png
   openshot-cli file strip FILE_ID --start 10 --end 20 --count 12 --output /tmp/source-strip.png
   openshot-cli timeline thumbnail --frame 91 --output /tmp/timeline-frame.png
   openshot-cli timeline strip --start 0 --end 20 --count 12 --output /tmp/timeline-strip.png
   openshot-cli timeline view --start 0 --end 20 --pixels-per-second 80 --output /tmp/tracks.png
   openshot-cli timeline overview --start 5 --end 12
   openshot-cli timeline view --start 5 --end 12 --mode waveforms --output /tmp/waves.png
   openshot-cli export start /tmp/highlight.mp4 --wait
   openshot-cli export status JOB_ID --wait --wait-timeout 600

``timeline view`` defaults to compact text with used tracks, object IDs,
timeline/source intervals, stream state, gain, and gaps/overlaps. Use
``--detail summary|clips|full`` to choose detail, ``--format json`` for structured
context, and ``--start/--end``, ``--layer``, and pagination to focus the result.

``timeline view --format image --output /tmp/tracks.png`` renders the actual
QWidget timeline offscreen; specifying ``--output`` also selects image format.
It reuses the
editor's geometry, themes, ruler, thumbnails, effect icons, transitions, and cached
waveforms. It does not change the interactive viewport or project. The default
width is 1280px and height fits used tracks. Native relaxed track sizing and a
220px label column keep the snapshot readable; ``--track-size`` and
``--track-label-width`` override these settings; ``--width``, ``--height``, and
``--all-tracks`` override sizing. The start/end range determines zoom, or specify
``--pixels-per-second`` to derive width. ``timeline thumbnail`` renders the actual
video composition. Images are limited to 4096 pixels per
axis, 8,388,608 total pixels, and 64 contact-sheet samples. Requests beyond limits
fail before rendering. Image paths must be new PNG files in existing directories.
Inspection is synchronous; large valid requests can briefly occupy the GUI.

``timeline overview`` supplies compact structured context without image bytes:
ordered IDs, sequence per track, timeline/source intervals, visible trim ranges,
frame coordinates, audio/video state, effects, and neighboring gaps or overlaps.
Intervals and frame spans are end-exclusive; frame numbers are one-based.
Source frames use source FPS; timeline and keyframe coordinates use project FPS.
Use ``--layer`` and ``--start/--end`` to focus, and ``--limit/--offset`` to paginate
(default 100, maximum 500 items). Time-remapped clips explicitly withhold inferred
source mappings. Use the returned revision with ``edit apply --expect-revision``.

Timeline images return clip IDs and timing alongside pixel bounds. ``--mode auto``
uses existing cached waveform display; ``--mode thumbnails`` forces thumbnails;
``--mode waveforms`` computes audio envelopes on private copies using the engine's
extraction and existing widget waveform painter. The project is unchanged.
These are source peak/RMS envelopes with clip volume/time adjustments, before
audio effects or mixing. Uncached extraction decodes whole sources, limited to
600 seconds per source and 1200 source-seconds per request. The session retains
a bounded source cache; responses report generation time, cache hits, decoded
duration, newly extracted samples, and samples mapped for display. Mapping
cached samples still costs some work, but does not decode the source again.
Narrowing the viewport does not shorten a
whole-source decode; precompute longer-source waveforms in the editor or use
thumbnail mode. Images themselves remain files, not base64 JSON payloads.
Every image response includes ``image_bytes``. Single-frame PNGs use default
lossless compression. Timeline thumbnails reuse readers within a request and a
32 MiB session cache keyed by source file metadata, frame, and rendering settings.
The ``thumbnails`` metrics distinguish generated images from cache hits and count
reader opens. Repeated views can therefore avoid decoding entirely.

Export defaults to MP4/H.264/AAC at the current project profile. Discover the
installed presets and advanced configuration schema before choosing settings::

   openshot-cli export preset list
   openshot-cli export preset get builtin:format_mp4_x264
   openshot-cli export capabilities
   openshot-cli export validate /tmp/reel.mp4 --preset builtin:format_mp4_x264
   openshot-cli export start /tmp/reel.mp4 --preset builtin:format_mp4_x264 --quality med --wait
   openshot-cli export start /tmp/small.mp4 --profile builtin:00640x0360p0030_16-09 --json '{"video_options":{"preset":"fast"}}' --wait
   openshot-cli export start /tmp/music.wav --json '{"mode":"audio","format":"wav","audio_codec":"pcm_s16le"}' --wait
   openshot-cli export start /tmp/frames --json '{"mode":"image_sequence","format":"png"}' --end-frame 3 --wait

Export also accepts ``--from-file FILE_ID`` with optional ``--create-custom``.
Settings resolve in this order: project defaults, preset, advanced JSON, explicit
profile/quality/range flags. Advanced JSON exposes video/audio codecs and bitrate,
audio layout/rate/channels, native codec options, hardware device settings, and
thread counts. CLI workers and the GUI share writer configuration logic.
Capabilities report compiled codec availability, not physical GPU availability.
Validation checks data, profiles, paths, and compiled encoders; actual codec,
container, native option, and hardware compatibility is checked when the worker
opens the writer. ``runtime_checked`` makes this distinction explicit.

Frame ranges are inclusive and one-based at the **export profile's FPS**.
Workers render an immutable snapshot and convert its frame-rate-dependent
coordinates when needed; subsequent edits do not change the job. Image sequences
require a new output directory. Existing outputs are never overwritten.

``--wait`` polls within the CLI process and returns once completed; failures and
cancellation exit 1 with job details. ``--wait-timeout`` defaults to 600 seconds
and leaves the job running on timeout, returning its ID; resume with
``export status ID --wait``. This is separate from the global per-request
``--timeout``. Wait results include elapsed waiting time and internal request
count. ``export cancel`` requests cancellation between frames. ``export list``
finds jobs belonging to the current session.

Recovery
--------

A request timeout does not mean a mutation failed. Use the operation ID in the
error with ``operation get ID`` before retrying. ``operation list`` discovers
recent mutations and their states, revisions, and outcomes. Completed operations
retain their results when small enough, including returned object IDs. Storage
is bounded to 100 operations and 4 MiB, with individual result bodies omitted
above 256 KiB. This is in-memory session recovery, not a crash journal or a
retry-deduplication mechanism. Export jobs have their own status/list commands.

Inspection images remain synchronous and bounded; this work does not change the
GUI's asynchronous architecture. Remote connections and analysis-dependent
effect workflows remain outside the current acceptance coverage.

Acceptance checks
-----------------

The initial implementation was exercised by fresh agents using help alone:

* A 20-second title/trailer/credits/music reel, exported at 720p30.
* A second 20-second reel with fades and saturation, including invalid-JSON and
  invalid-batch recovery checks.
* A 17-second 720p24 reel, saved, reopened, undone/redone, and exported.
* A 5-second transparent audio spectrum over a title card, chosen using effect help.

The runs exposed and drove fixes for property discovery, effect timing validation,
profile persistence, enum documentation drift, audio-only controls, and timeline
labels. GUI smoke tests also exercised discovery, clip edits, undo, and rendering.
A 320-test regression run covered the new CLI tests plus existing Query, project,
color-grade history, live-property, and timeline tests. Coverage includes help
traversal, framing, validation before listeners, headless history, native
rendering, effects, and transitions. A fresh-agent follow-up also verified native
QWidget timeline snapshots at different ranges and sizes, with used/all tracks
and unchanged project state.

To measure future fresh-agent rounds, use ``src/tests/agent_cli_metrics.py`` as
the CLI wrapper. Set ``OPENSHOT_METRICS_DIR`` to a per-round output directory;
optionally set ``OPENSHOT_CLI_COMMAND`` to a JSON argv array for the executable.
The wrapper preserves stdout, stderr, and exit codes while recording command
arguments, elapsed time, response bytes, errors, image sizes, and cache/wait
metrics in ``calls.jsonl``. It defaults to the source ``src/cli.py`` entry point::

   OPENSHOT_METRICS_DIR=/tmp/round1 python3 src/tests/agent_cli_metrics.py help
   python3 src/tests/agent_cli_metrics.py --summarize /tmp/round1

Whole-workflow wall time includes agent reasoning and tool scheduling; summed
CLI time includes export waiting when ``--wait`` is used. Report these separately
and preserve internal wait polling counts. Compare matching operations and note
extra test tasks rather than treating differing whole-workflow runs as controlled
performance benchmarks. See ``agent_cli_acceptance.rst`` for measured rounds.
