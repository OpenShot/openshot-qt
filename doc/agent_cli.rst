.. Copyright (c) 2026 OpenShot Studios, LLC. GPL-3.0-or-later.

.. _cli_ref:

Command Line Interface
======================

Bring OpenShot into your command-line workflow. Import footage, trim and arrange
clips, apply effects, animate properties with keyframes, and export videos from
your terminal. Use a few commands to automate repetitive edits, write a script
for a recurring project, or let an AI agent help assemble and refine a video.

The command line works with the same projects as the editor. You can control an
open editor and review changes as you go, or work in a **headless session** without
opening a window. A session keeps your project open between commands, including
its edits, undo history, and export jobs. Save it as an ``.osp`` project whenever
you want to continue editing later.

Getting started
---------------

Use your installed OpenShot executable followed by ``--cli``. Start with
``intro`` for a short guide to sessions, editing, animation, and saving, or
``help`` for the command overview. These commands do not need an active session.
The examples below require an OpenShot build that includes command-line editing.

.. important::

   Editing commands need a selected session. Starting a session returns a
   ``session_id``; it does **not** select that session for later commands.
   Follow :ref:`cli_session_selection_ref` before running project, timeline,
   editing, or export commands.

.. _cli_appimage_ref:

Linux AppImage
~~~~~~~~~~~~~~

From the directory containing your downloaded AppImage::

   ./OpenShot.AppImage --cli intro
   ./OpenShot.AppImage --cli help

Replace ``OpenShot.AppImage`` with your downloaded filename. If **AppImageLauncher**
shows desktop integration dialogs, set ``APPIMAGELAUNCHER_DISABLE=1`` before
launching the command::

   APPIMAGELAUNCHER_DISABLE=1 ./OpenShot.AppImage --cli intro

For scripts or repeated commands, set it once in your current shell::

   export APPIMAGELAUNCHER_DISABLE=1
   ./OpenShot.AppImage --cli session start

The variable must be set before launching the AppImage: AppImageLauncher can
intercept it before OpenShot receives ``--cli``. Relative media paths and
``@batch.json`` files are resolved from your working directory. Keep the AppImage
file available while its sessions or exports are running.

Linux Snap
~~~~~~~~~~

For the `OpenShot Snap <https://snapcraft.io/openshot-qt>`_, use::

   snap run openshot-qt --cli intro
   snap run openshot-qt --cli help
   snap run openshot-qt --cli session start

Snap's file permissions apply to command-line editing too. Keep media, projects,
and exports in locations the Snap can access, such as your home folder. To allow
access to external drives, connect the removable-media permission::

   sudo snap connect openshot-qt:removable-media

Windows
~~~~~~~

.. important::

   **Use openshot-qt-cmd.exe for command-line editing on Windows.** This console
   executable displays command results, help, and errors in your terminal.
   The desktop executable, ``openshot-qt.exe``, does not display standard output
   in an interactive terminal, leaving commands without visible feedback and
   making the CLI difficult to use.

In PowerShell, from the OpenShot installation directory::

   & .\openshot-qt-cmd.exe --cli intro
   & .\openshot-qt-cmd.exe --cli help
   & .\openshot-qt-cmd.exe --cli session start

If you are in a different directory, use the full path to
``openshot-qt-cmd.exe``. Keep ``--cli`` after the executable name.

macOS
~~~~~

For an installation in Applications::

   "/Applications/OpenShot Video Editor.app/Contents/MacOS/openshot-qt" --cli intro
   "/Applications/OpenShot Video Editor.app/Contents/MacOS/openshot-qt" --cli help

Finding commands
----------------

Throughout this guide, ``openshot-cli`` is shorthand for your installation's
command above, such as ``snap run openshot-qt --cli`` or
``./OpenShot.AppImage --cli``. Some installations also provide an ``openshot-cli``
command directly. When running from source, use ``python3 src/launch.py --cli``
in OpenShot's Python environment.

Bare ``--cli``, ``--cli help``, and ``--cli --help`` show the same overview.
Help becomes more specific as you navigate commands::

   openshot-cli clip help
   openshot-cli clip keyframe help
   openshot-cli clip keyframe set help
   openshot-cli edit help
   openshot-cli effects list
   openshot-cli effects audiovisualization help
   openshot-cli effects audiovisualization help --property background

Group help explains workflows with examples; operation help describes arguments
and behavior. ``--help`` is equivalent to trailing ``help``. All help commands
work without an editing session.

``effects list`` shows the available effects with short descriptions.
Effect help explains their properties, defaults, choices, and ranges.
``effects instances`` lists effects already attached to clips, with parent clip
IDs. Class names, display names, and underscore aliases identify the same effect.

Working with scripts and AI agents
----------------------------------

AI coding agents such as **Codex** and **Claude Code** can use the CLI to inspect
and edit OpenShot projects through terminal commands. Give your agent the path
to your OpenShot executable, the media or project to work with, and the desired
result: duration, dimensions, animation style, and output location. Ask it to
read ``--cli intro`` before starting. The same commands work when you type them
yourself or run them from a script.

Start with ``intro``, then use command-specific help as needed. A useful workflow
is to select a session, inspect the project, make a small set of changes, review
the result, and save. Commands return structured JSON so scripts and agents can
use object IDs and results directly instead of interpreting screen output.

* **Inspect before editing.** Use returned IDs and property information instead
  of guessing names, track numbers, or timing. Select a session explicitly when
  more than one project is open.
* **Group repeated edits.** Use ``edit apply`` for a sequence of changes or
  ``edit bulk`` to apply a template to selected clips. Validate with ``--dry-run``
  before applying a batch.
* **Check animation.** Choose a coordinate space, start with a few keyframes,
  and use easing presets for familiar motion. ``keyframe preview`` samples the
  curve so you can spot pauses or jumps before exporting. Review rendered motion
  as well; a contact sheet alone cannot show how an animation feels.
* **Save and follow exports.** Save the project explicitly and check the export
  job's status before treating an output as complete. If a request times out,
  inspect its status before repeating an edit.

The sections below explain these workflows and their timing conventions.

Sessions and outputs
--------------------

Starting or finding a session
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Start one headless session (without an editor window)::

   openshot-cli session start

To open an existing project at startup, add ``--project "/path/project.osp"``.
The successful JSON response contains ``result.session_id``. Copy that value.
If OpenShot is already running, or you have forgotten the ID, find available
sessions with::

   openshot-cli session list

Choose the session for the project you intend to edit. You do not need to start
a new session for each command.

.. _cli_session_selection_ref:

Selecting a session
~~~~~~~~~~~~~~~~~~~

Use the returned ID in subsequent commands. Replace ``SESSION_ID`` below with
the actual value, without angle brackets. Put ``--session`` **after** ``--cli``
and **before** the command group.

Windows PowerShell::

   & .\openshot-qt-cmd.exe --cli --session SESSION_ID timeline view
   & .\openshot-qt-cmd.exe --cli --session SESSION_ID export start "C:\path\test.mp4" --wait

Linux AppImage::

   ./OpenShot.AppImage --cli --session SESSION_ID timeline view
   ./OpenShot.AppImage --cli --session SESSION_ID export start "/path/test.mp4" --wait

For repeated commands, you can select the session once in your current terminal
using ``OPENSHOT_SESSION`` instead of passing ``--session`` every time.

Windows PowerShell::

   $env:OPENSHOT_SESSION = "SESSION_ID"
   & .\openshot-qt-cmd.exe --cli timeline view

Linux or macOS shell::

   export OPENSHOT_SESSION="SESSION_ID"
   ./OpenShot.AppImage --cli timeline view

On macOS or Snap, substitute your installation's command from Getting started.
**Examples below that omit --session assume OPENSHOT_SESSION is set.** An
explicit ``--session`` overrides the environment variable. Update the ID when
switching projects in different sessions or starting a replacement session.

Automatic selection only works when exactly one reachable session exists.
If you see ``session_required``, run ``session list`` and explicitly select the
intended session. If it is no longer listed, start it again and use the new ID.
Help, ``intro``, and session discovery do not require a selected session.

Capturing the session ID automatically
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Scripts can read ``result.session_id`` directly from the JSON returned by
``session start`` and set ``OPENSHOT_SESSION`` for subsequent commands. There is
no need to copy the ID manually or read a log file. Check that startup succeeded
before using the returned ID.

Windows PowerShell (set the executable path for your installation)::

   $openshot = "C:\Program Files\OpenShot Video Editor\openshot-qt-cmd.exe"
   $reply = & $openshot --cli session start
   if ($LASTEXITCODE -ne 0) { throw "OpenShot session startup failed" }
   $session = $reply | ConvertFrom-Json
   if (-not $session.ok -or -not $session.result.session_id) {
       throw "OpenShot did not return a session ID"
   }
   $env:OPENSHOT_SESSION = $session.result.session_id
   & $openshot --cli timeline view

Linux Bash (requires ``jq`` to read JSON)::

   openshot="/full/path/to/OpenShot.AppImage"
   export APPIMAGELAUNCHER_DISABLE=1
   if reply=$("$openshot" --cli session start) &&
      session_id=$(printf '%s' "$reply" | jq -er 'select(.ok == true) | .result.session_id | strings | select(length > 0)'); then
       export OPENSHOT_SESSION="$session_id"
       "$openshot" --cli timeline view
   else
       echo "OpenShot session startup failed" >&2
   fi

The environment variable selects a session for commands launched from this
terminal; it does not change a system-wide setting. Starting a session does not
set the variable automatically. After stopping the session, clear the selection
with ``Remove-Item Env:OPENSHOT_SESSION`` in PowerShell or
``unset OPENSHOT_SESSION`` in Bash.

Showing and stopping a session
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To show the selected session in the editor::

   openshot-cli session show

On a desktop, ``session show`` creates the editor in the same process and keeps
the live project, IDs, history, export jobs, and connection. Repeated calls raise
the existing window. ``session start --show`` opens it immediately. Sessions
started without a display, or with ``QT_QPA_PLATFORM=offscreen``/``minimal``,
cannot later show a desktop window. For those sessions, save and open the project
in a new desktop session. Once shown, close the session
through the editor window.

Global options (``--session``, ``--timeout``) go before the command.
``session serve`` stays in the foreground for supervisors; ``session start`` returns after a background
host registers. ``session stop`` refuses unsaved changes and active exports.
Use ``--discard`` only to intentionally discard unsaved edits.

Command output
~~~~~~~~~~~~~~

Results are JSON on stdout, except the default text timeline view. Errors are JSON on stderr with exit status 1;
argument-parser errors exit 2. Mutations return compact summaries with an
``inspect`` command. ``get`` returns native object JSON. Project replies include
a revision; effect catalog replies do not require a session. Logs from headless
sessions live beside their registry records. ``OPENSHOT_SESSION_DIR`` overrides
the default ``~/.openshot_qt/sessions`` directory.

Sessions accept commands locally on your computer. Keep the session registry
private, since it contains the credentials used to access your editing sessions.
Exports work from a snapshot, so you can continue editing while a job runs.

Opening and saving projects
---------------------------

An OpenShot project (``.osp``) stores your editable timeline. Exporting creates a
finished video; saving the project lets you return to its clips, effects, and
keyframes later. Save your project separately even when you also export a video.

Opening a project
~~~~~~~~~~~~~~~~~

Start a session with an existing project::

   openshot-cli session start --project "/home/me/Videos/My Project.osp"

Add ``--show`` to open its editor window too. To use an editor that is already
running, find it with ``session list``. Use the returned session ID when opening
or inspecting a project::

   openshot-cli --session SESSION_ID project open "/home/me/Videos/My Project.osp"
   openshot-cli --session SESSION_ID project get

Replace the example path with your own, and quote paths containing spaces.
``project open`` replaces the selected session's current project. It refuses to
discard unsaved edits unless you explicitly add ``--discard``; save those edits
first if you want to keep them. Opening through the CLI does not show interactive
missing-media dialogs, so keep the project's source media available.

For a new, empty project, use ``session start`` without ``--project``, then import
media and add clips as described under Editing.

Saving a project or a copy
~~~~~~~~~~~~~~~~~~~~~~~~~~

Save to a new file, or create a separate version before making more changes::

   openshot-cli --session SESSION_ID project save "/home/me/Videos/My Project v2.osp"

To update an existing file, explicitly allow replacement::

   openshot-cli --session SESSION_ID project save "/home/me/Videos/My Project v2.osp" --overwrite

Always supply the destination path. Saving an ``.osp`` does not package all your
source footage into that file; keep the referenced media available when moving
or reopening the project.

Exporting a video
-----------------

Automate rendering and exporting from scripts or AI agents, using the project's
settings or choosing a different output profile for each render. Export jobs can
run in the background or wait for completion before your script continues.
To render an MP4 using the project's resolution and frame rate::

   openshot-cli --session SESSION_ID export start "/home/me/Videos/video.mp4" --wait

By default, OpenShot uses H.264 video and AAC audio. Replace the example path
with your destination, using an existing folder and a new filename. Existing
outputs are never overwritten. Exporting does not save your editable ``.osp``
project; use ``project save`` separately to keep your editing work.

The ``--wait`` option keeps the command running until the export completes or
reports a failure. Review the finished video before sharing it.

Checking export progress
~~~~~~~~~~~~~~~~~~~~~~~~

Leave off ``--wait`` to start an export in the background. The response includes
a job ID you can use to check its progress::

   openshot-cli --session SESSION_ID export start "/home/me/Videos/video.mp4"
   openshot-cli --session SESSION_ID export status JOB_ID
   openshot-cli --session SESSION_ID export status JOB_ID --wait
   openshot-cli --session SESSION_ID export list

Replace ``JOB_ID`` with the returned ID. If waiting times out, the export keeps
running; check the same job instead of starting another export. To stop a job,
use ``export cancel JOB_ID``. Each job captures the timeline when it starts,
so later edits do not change an export already in progress.

Waiting defaults to 600 seconds; adjust this with ``--wait-timeout``. This is
separate from the global per-request ``--timeout``. Export failures,
cancellation, and wait timeouts exit with status 1 and include job details.

Exporting in multiple profiles
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Export the same timeline at different resolutions or aspect ratios by choosing
an export profile for each output. **An export profile applies only to that job**;
it does not change the editing project's profile. A profile sets dimensions,
frame rate, and aspect ratio; an export preset selects encoding settings such
as MP4/H.264.

Find the available profiles and inspect their settings::

   openshot-cli profile list --search 720
   openshot-cli profile list --search 1080
   openshot-cli profile get builtin:01280x0720p0030_16-09

For example, export landscape versions at 720p and 1080p, then a square version
at 1080 by 1080. These profiles all use 30 fps::

   openshot-cli --session SESSION_ID export start "/home/me/Videos/video-720p.mp4" --profile builtin:01280x0720p0030_16-09 --wait
   openshot-cli --session SESSION_ID export start "/home/me/Videos/video-1080p.mp4" --profile builtin:01920x1080p0030_16-09 --wait
   openshot-cli --session SESSION_ID export start "/home/me/Videos/video-square.mp4" --profile builtin:01080x1080p0030_01-01 --wait

Use a different output filename for each version. Keep edits unchanged between
jobs when you want matching versions. Changing aspect ratio can change framing:
review each output, especially titles and animated subjects.
For a separately composed square or portrait version, save a project copy, change
its project profile, and adjust the clips before exporting. See Profiles and
the export settings below for custom profiles and encoding options.

Batch exporting multiple projects
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Reuse one headless session to render several saved projects in sequence. Open a
project, export it with ``--wait``, then open the next project. The examples below
use each project's own resolution and frame rate and create MP4 files beside the
``.osp`` files. Add ``--profile PROFILE_ID`` to the export command to use one
output profile for every project.

First run the matching automatic session-ID example above successfully, in the
same terminal. It defines ``openshot`` and selects the new session. Replace the
project paths below with your own. Use distinct output names that do not already
exist; the examples check all destinations before starting the batch.

Windows PowerShell::

   $projects = @(
       "C:\VideoProjects\First.osp",
       "C:\VideoProjects\Second.osp"
   )
   foreach ($project in $projects) {
       if (-not (Test-Path -LiteralPath $project -PathType Leaf)) {
           throw "Project not found: $project"
       }
       $output = [System.IO.Path]::ChangeExtension($project, ".mp4")
       if (Test-Path -LiteralPath $output) { throw "Output already exists: $output" }
   }
   foreach ($project in $projects) {
       $output = [System.IO.Path]::ChangeExtension($project, ".mp4")
       & $openshot --cli project open $project
       if ($LASTEXITCODE -ne 0) { throw "Could not open: $project" }
       & $openshot --cli export start $output --wait --wait-timeout 86400
       if ($LASTEXITCODE -ne 0) { throw "Export needs attention: $output" }
   }
   & $openshot --cli session stop
   if ($LASTEXITCODE -ne 0) { throw "Could not stop the session" }
   Remove-Item Env:OPENSHOT_SESSION

Linux Bash (the parentheses keep error handling local to the batch)::

   (
       set -e
       : "${OPENSHOT_SESSION:?Run the session startup example first}"
       projects=(
           "/home/me/VideoProjects/First.osp"
           "/home/me/VideoProjects/Second.osp"
       )
       for project in "${projects[@]}"; do
           test -f "$project" || { echo "Project not found: $project" >&2; exit 1; }
           output="${project%.osp}.mp4"
           test ! -e "$output" || { echo "Output already exists: $output" >&2; exit 1; }
       done
       for project in "${projects[@]}"; do
           "$openshot" --cli project open "$project"
           "$openshot" --cli export start "${project%.osp}.mp4" --wait --wait-timeout 86400
       done
       "$openshot" --cli session stop
   ) && unset OPENSHOT_SESSION

Both recipes stop the batch on a command failure and leave the session available
for inspection. The wait limit here is 24 hours per export. A wait timeout leaves
the render running: use ``export list`` and ``export status JOB_ID --wait`` before
retrying. Completed videos remain on disk; remove completed projects from the
batch before resuming. After resolving a failure, stop the session and clear its
environment variable when you are finished.

Choosing presets and encoding settings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Discover the installed export presets and supported settings::

   openshot-cli export preset list
   openshot-cli export preset get builtin:format_mp4_x264
   openshot-cli export capabilities
   openshot-cli export start /tmp/reel.mp4 --preset builtin:format_mp4_x264 --quality med --wait

Export also accepts ``--from-file FILE_ID`` with optional ``--create-custom``.
Settings resolve in this order: project defaults, preset, advanced JSON, explicit
profile/quality/range flags. Advanced JSON exposes video/audio codecs and bitrate,
audio layout/rate/channels, native codec options, hardware device settings, and
thread counts.

For example, select an encoder option through advanced JSON::

   openshot-cli export start /tmp/small.mp4 --profile builtin:00640x0360p0030_16-09 --json '{"video_options":{"preset":"fast"}}' --wait

Validating export settings
~~~~~~~~~~~~~~~~~~~~~~~~~~

Check settings before starting a render::

   openshot-cli export validate /tmp/reel.mp4 --preset builtin:format_mp4_x264

Capabilities report compiled codec availability, not physical GPU availability.
Validation checks data, profiles, paths, and compiled encoders; actual codec,
container, native option, and hardware compatibility is checked when the worker
opens the writer. ``runtime_checked`` makes this distinction explicit.

Rendering a frame range
~~~~~~~~~~~~~~~~~~~~~~~

Use ``--start-frame`` and ``--end-frame`` to render part of the timeline.
Ranges are inclusive and one-based at the **export profile's FPS**. For example,
render the first 90 frames at 30 fps (three seconds)::

   openshot-cli export start /tmp/excerpt.mp4 --profile builtin:01280x0720p0030_16-09 --start-frame 1 --end-frame 90 --wait

Audio-only exports and image sequences
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Choose an output mode with advanced JSON::

   openshot-cli export start /tmp/music.wav --json '{"mode":"audio","format":"wav","audio_codec":"pcm_s16le"}' --wait
   openshot-cli export start /tmp/frames --json '{"mode":"image_sequence","format":"png"}' --end-frame 3 --wait

Image sequences require a new output directory. Existing outputs are never
overwritten.

Editing
-------

Adding clips and effects
~~~~~~~~~~~~~~~~~~~~~~~~

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

Choose the project profile early when possible; populated projects also support
profile changes through the existing FPS conversion and undo system. ``--audio-only`` on clip creation
suppresses video, including embedded cover art in music files. To use that clip
for Audio Visualization instead, enable its video and audio, and follow the
effect's help for transparent overlays and layer placement.

Understanding clip timing
~~~~~~~~~~~~~~~~~~~~~~~~~

The example keyframes assume a 30fps project and a clip trimmed at source 10s.
Position is in timeline seconds; start/end are source seconds, with end exclusive.
Frames start at 1. File thumbnail frames use source FPS. Timeline frames use
project FPS. Clip keyframes use source coordinates at project FPS, so trimming
the clip does not move its first visible keyframe to frame 1.

Changing properties
~~~~~~~~~~~~~~~~~~~

``set`` merges top-level properties. Scalars turn keyframed properties into
constants. A supplied nested curve replaces that curve; use ``keyframe set`` to
change just one point. JSON arguments accept inline JSON, ``@file.json``, or
``-`` for stdin. Property names, types, enums, keyframes, references, and timing
are validated before editing the project. Errors identify the field,
expected value, received value, and a correction where possible. GUI slider
ranges are advisory where the engine supports values beyond them.

Adding fades
~~~~~~~~~~~~

``clip fade ID --in 0.5 --out 0.5`` calculates source-trim keyframe coordinates
automatically. It replaces the alpha curve; ``--property volume --value 0.25``
instead creates an audio fade with a 0.25 peak gain. Durations must fit between
the first and last visible frames; fade-out reaches zero on the last frame.

Splitting clips
~~~~~~~~~~~~~~~

``clip split ID --at 6.5`` uses timeline seconds, snaps to the nearest project
frame, and keeps both halves. It retains source-coordinate curves and duplicates
effects with fresh IDs on the right half, following the editor's slicing behavior.
The left half retains its ID. The response reports requested/actual split times
and both summaries; a named batch result supports ``{"$ref":"cut.right.id"}``.
Splits reject endpoints and locked tracks. Undo restores the original clip in
one transaction.

Applying a batch of edits
~~~~~~~~~~~~~~~~~~~~~~~~~

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
``refs`` map of actual IDs. All changes in a successful batch form one undo/redo step.
``project.profile.set`` also supports populated timelines. Opening, saving,
exporting, and inspection commands stay outside edit batches. Each
command's help lists its JSON parameter names, including the underscore spelling
of shell flags (for example, ``--fps-num`` becomes ``fps_num``).

Validating batches and handling errors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All commands in edit batches preflight against a detached project before any live updates.
Invalid input leaves the live project and revision unchanged. Valid batches form
one undo group. Unexpected runtime failures can still produce partial changes;
errors report completed operations. A timeout does not imply cancellation, so
inspect state before retrying mutations.

Precise keyframe editing
~~~~~~~~~~~~~~~~~~~~~~~~

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

Interpolation, easing, and preview
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Interpolation describes the segment **into the destination point**.
Linear gives a steady rate between points. Constant holds the preceding
value until the destination, then jumps. Native default Bezier handles
ease at both ends of each segment. Adding an intermediate point can therefore
introduce an unintended slowdown; for one eased move, start with two endpoints.
Normally leave handles alone and choose a named preset for a specific style.

Discover the same easing presets used by the editor's menus, without a session::

   openshot-cli clip keyframe presets

Apply a preset to the incoming segment by setting its destination::

   openshot-cli clip keyframe set CLIP --property scale_x --space clip --unit seconds --at 0 --value 1
   openshot-cli clip keyframe set CLIP --property scale_x --space clip --unit seconds --at 4 --value 1.2 --easing ease-in-out

The easing option implies Bezier. It sets the previous point's outgoing handle
and the destination's incoming handle together, preserving other handles and
point values. An earlier point must exist. Do not combine it with custom
handles or a different interpolation. Presets work in batches and bulk templates.
The GUI preset **ease** ("Ease (Default)") differs from the native handles used
by plain Bezier interpolation. Back presets can overshoot endpoint values.

Inspect motion **before rendering**, using the native curve evaluator::

   openshot-cli clip keyframe preview CLIP --property scale_x --space clip --unit seconds --start 0 --end 4
   openshot-cli clip keyframe preview CLIP --property scale_x --space clip --unit seconds --at 2

Preview is read-only and works identically for effects and transitions.
It returns values and signed incoming_rate / outgoing_rate in property units
per second, calculated from immediately adjacent frames. These are finite
differences, not analytic derivatives. At native frame 1 the incoming rate is
null. Adjacent-frame rates can inspect outside the requested range.
Near-zero rates around an interior point reveal a pause; differing rates reveal
a speed change. Constant interpolation reveals a jump at the destination.

Without a range, preview spans the curve's first and last points. Ranges are
inclusive, with 17 evenly spaced samples by default (--count: 2–256).
Keyframes and their immediate neighbors inside the range are also included,
so a sparse sample count will not hide a keyframe stall. The maximum is 1024
samples; larger requests require a narrower range. --at samples one frame.
Preview reports requested-space coordinates and actual native frames;
seconds snap to project frames as they do for editing.

For advanced custom handles, both X and Y are normalized to the segment:
X is a fraction of its frame span; Y is a fraction of its value change.
The first control comes from the previous point's handle_right, the second
from the destination's handle_left. Native defaults are right=(0.5, 0),
left=(0.5, 1), with flat endpoint tangents. Changing handle_type alone does not
recalculate a continuous tangent through surrounding points. Existing handles
are preserved when moving a point.

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``edit apply --dry-run`` to validate a batch without changing the project.
Use ``edit bulk`` to repeat a small command template for each selected clip,
with all changes grouped into one undo step.

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

Inspecting media and timelines
------------------------------

Inspect clip timing and track layout as text or JSON, or render images to review
composition and framing before exporting.

Timeline summaries
~~~~~~~~~~~~~~~~~~

Use a text view for a quick overview, or structured JSON for scripts and agents::

   openshot-cli timeline view --start 5 --end 12
   openshot-cli timeline view --start 5 --end 12 --format json
   openshot-cli timeline overview --start 5 --end 12

``timeline view`` defaults to compact text with used tracks, object IDs,
timeline/source intervals, stream state, gain, and gaps/overlaps. Use
``--detail summary|clips|full`` to choose detail, ``--format json`` for structured
context, and ``--start/--end``, ``--layer``, and pagination to focus the result.

``timeline overview`` supplies compact structured context without image bytes:
ordered IDs, sequence per track, timeline/source intervals, visible trim ranges,
frame coordinates, audio/video state, effects, and neighboring gaps or overlaps.
Intervals and frame spans are end-exclusive; frame numbers are one-based.
Source frames use source FPS; timeline and keyframe coordinates use project FPS.
Use ``--layer`` and ``--start/--end`` to focus, and ``--limit/--offset`` to paginate
(default 100, maximum 500 items). Time-remapped clips explicitly withhold inferred
source mappings. Use the returned revision with ``edit apply --expect-revision``.

Frame previews and contact sheets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Render a single frame with ``thumbnail`` or sample a range with ``strip``.
Use ``file`` to inspect source media and ``timeline`` to inspect the composed
video, including effects and layered clips::

   openshot-cli file thumbnail FILE_ID --frame 301 --output /tmp/source.png
   openshot-cli file strip FILE_ID --start 10 --end 20 --count 12 --output /tmp/source-strip.png
   openshot-cli timeline thumbnail --frame 91 --output /tmp/timeline-frame.png
   openshot-cli timeline strip --start 0 --end 20 --count 12 --output /tmp/timeline-strip.png

Frame images default to 320x180 pixels; contact sheets default to 160x90 per
tile, plus timecode labels. Use ``--width`` and ``--height`` to choose output
pixels. Responses include exact sample/frame metadata. Contact sheets help
review composition across a sequence; use keyframe previews and rendered video
to assess motion between those samples.

Timeline images
~~~~~~~~~~~~~~~

Capture the editor's track layout, including its ruler, thumbnails, effects,
transitions, and waveforms::

   openshot-cli timeline view --start 0 --end 20 --pixels-per-second 80 --output /tmp/tracks.png

Specifying ``--output`` selects image format; ``--format image`` also selects it
explicitly. The capture does not change the editor's viewport or project.
Responses include clip IDs and timing alongside pixel bounds.

Images default to 1280 pixels wide, with height fitted to used tracks. Use
``--width``, ``--height``, or ``--all-tracks`` to adjust the layout, and
``--track-size`` or ``--track-label-width`` to adjust tracks and labels.
The start/end range determines zoom; ``--pixels-per-second`` instead derives
the width from the time range.

Audio waveform views
~~~~~~~~~~~~~~~~~~~~

Choose ``--mode waveforms`` to inspect audio envelopes on the timeline::

   openshot-cli timeline view --start 5 --end 12 --mode waveforms --output /tmp/waves.png

``--mode auto`` uses the existing cached waveform display; ``--mode thumbnails``
shows thumbnails instead. Waveforms represent source peak/RMS levels with clip
volume and timing adjustments, before audio effects or mixing.

Uncached waveform extraction decodes whole sources, limited to 600 seconds per
source and 1200 source-seconds per request. Narrowing the visible range does not
reduce that decoding work. For longer sources, generate waveforms in the editor
first or use thumbnail mode. Subsequent requests can reuse cached waveforms.

Image output and limits
~~~~~~~~~~~~~~~~~~~~~~~

Image paths must be new PNG files in existing directories. Images are limited
to 4096 pixels per axis, 8,388,608 total pixels, and 64 contact-sheet samples.
Requests beyond these limits fail before rendering.

Images are written to files; JSON responses include their paths and
``image_bytes`` sizes. Inspection waits for the image to finish, and large
requests can briefly occupy the editor.

Handling command timeouts
-------------------------

A request timeout does not mean a mutation failed. Use the operation ID in the
error with ``operation get ID`` before retrying. ``operation list`` discovers
recent mutations and their states, revisions, and outcomes. Completed operations
retain their results when small enough, including returned object IDs. Storage
is bounded to 100 operations and 4 MiB, with individual result bodies omitted
above 256 KiB. These records last only for the running session. They do not
restore projects after a crash or prevent a repeated command from applying the
same edit again. Export jobs have their own status/list commands.
