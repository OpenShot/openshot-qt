#!/usr/bin/env python3
"""Agent-first command-line entry point. Help does not import Qt or libopenshot."""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classes.agent.protocol import CommandError, cli_command, parse_json, records, session_dir

AGENT_GUIDE = """OpenShot automation quick start (protocol 1)

1. Discover: openshot-cli session list
2. Start a persistent headless editor: openshot-cli session start
3. Inspect: openshot-cli --session ID timeline view (text; no media decoding)
4. Import: openshot-cli --session ID file import /absolute/path/video.mp4
   Match its profile: profile match --file FILE_ID
   Set project: project profile set --from-file FILE_ID
   Inspect current profile: project profile get
   Browse profiles: profile list --search "720p"
   No exact match? Inspect alternatives or explicitly use --create-custom.
5. Place: openshot-cli --session ID clip add FILE_ID --layer 1000000 --position 0
   Use project get to discover real layer numbers; never guess IDs.
6. Inspect: openshot-cli --session ID timeline thumbnail --frame 1 --output /tmp/frame.png
7. Save: openshot-cli --session ID project save /absolute/path/edit.osp

Discover effects before adding them: effects list gives short descriptions;
effects audiovisualization help gives purpose, usage, examples and properties.
Use effects audiovisualization help --property background for one setting.
effects instances shows attached instances; effects list shows the catalog.

Every group and operation supports help and --help (e.g. clip add help). Help and this guide work without a session.
Mutations return compact summaries and an inspect command; get returns full native JSON.
Results are JSON except timeline view defaults to text; use --format json for scripts.
Errors are JSON on stderr (exit 1).
Argument errors exit 2. Global --session and --timeout go BEFORE the command group.
A session stays alive between calls. With multiple sessions, --session is required.
GUI edits use the same Query/UpdateManager/undo history as mouse edits.

Time contract:
  position = timeline seconds; start/end = source seconds; end is exclusive.
  Frames are 1-based: frame 1 is time zero. File frames use source FPS;
  timeline frames and keyframe coordinates use project FPS. No SMPTE parser yet.
  Property updates accept native OpenShot JSON (including keyframe Points).
  A scalar replaces a keyframed property with a constant: clip set ID --json
  '{"volume":0}' mutes a clip; '{"volume":0.4}' sets gain; '{"has_video":0}' hides
  video (including album art in music). clip add --audio-only is useful for music.
  clip keyframe set ID --property volume --frame 1 --value 0 edits one point.
  Clip keyframe frames are SOURCE coordinates at PROJECT FPS, not timeline time:
  a clip trimmed at 10s in a 30fps project starts at keyframe frame 301.
  To fade it in over 1s, set volume 0 at frame 301 and volume 1 at frame 331.
  Use get and properties to discover fields. set merges supplied top-level fields;
  nested objects are replaced, so provide a complete keyframe curve.
  clip fade ID --in 0.5 --out 0.5 builds an alpha fade using the clip's trim.
  Use --property volume --value 0.25 for music fades with a 0.25 peak gain.

Each mutating command is one undo group. edit apply accepts an ordered JSON list
of {"method":"clip.set","params":{"id":"...","values":{"position":2}}}.
Name results with "as":"media", then reference an earlier result using
{"$ref":"media.id"}. Example (JSON array for edit apply --json):
[{"method":"file.import","as":"media","params":{"path":"/tmp/video.mp4"}},
 {"method":"clip.add","as":"shot","params":{"file_id":{"$ref":"media.id"},"layer":1000000,"end":5}},
 {"method":"clip.fade","params":{"id":{"$ref":"shot.id"},"fade_in":0.5,"fade_out":0.5}}]
Names last only for this batch. Results include refs with the real generated IDs.
Batch mutations follow command paths: effects.add, effects.set, clip.fade, etc.
project.profile.set accepts an ID, from_file, or values (custom profile JSON).
It uses existing FPS/keyframe conversion, with grouped undo/redo. save/open/export and
inspection commands stay outside batches (they are not undoable edits).
The older singular effect.add/effect.set spelling is also accepted.
Use clip split ID --at 6.5 to cut at timeline seconds (nearest project frame),
keeping both halves and their animation. Returns left/right IDs; batches can
name the result and use {"$ref":"cut.right.id"} in subsequent edits.
Batches preflight all commands before edits. Invalid input applies nothing.
A runtime failure can still leave a partial undo group; completed operations are reported.
Use --expect-revision with edit apply to detect edits since your last inspection.
Do not retry mutations blindly after timeouts. Query the session first.

thumbnail produces one exact frame. strip samples a bounded time range and returns
an image plus tile coordinates/timecodes. timeline view defaults to fast text;
--detail summary|clips|full changes detail; --format json returns structured context.
--format image --output PATH renders the actual QWidget timeline;
--pixels-per-second controls zoom, --start/--end control the viewport.
timeline overview --start 5 --end 12 returns compact IDs, ordered clips, source
and timeline timing, gaps/overlaps and stream state without image bytes.
timeline view --mode waveforms shows audio envelopes in the actual widget;
--mode thumbnails forces thumbnails; auto uses existing cached waveforms.
Limits: 4096 pixels per dimension, 8,388,608 pixels total, 64 strip samples.
Requests beyond limits fail; nothing is silently resized. PNG output paths must
not already exist. Inspections are synchronous; use small ranges in the GUI.

Export starts a background job from a project snapshot. Use export start PATH --wait
or export status JOB_ID --wait. --wait-timeout bounds waiting (default 600s);
a wait timeout leaves the job running and returns its ID for safe status checks.
Export discovery: export preset list; export preset get ID; export capabilities.
Validate without rendering: export validate /tmp/out.mp4 --preset PRESET_ID --profile project
Export uses the current profile by default. --profile ID or --from-file FILE_ID
selects an export-only profile without changing the .osp. Frame ranges use EXPORT FPS.
Advanced --json accepts native encoder options; use export capabilities for fields.
Video/audio, video-only, audio-only and image_sequence modes are supported.
Hardware encoder names/devices are explicit; there is no silent software fallback.
export list finds job IDs/output paths. operation list/get retain recent mutation
results/errors in this session; timeout errors include an operation ID. These are
bounded records, not a crash journal or automatic retry mechanism.
session start creates no editor window; --show opens one immediately.
session show opens or raises the same session's editor, preserving IDs and history.
Desktop sessions support showing later; displayless/offscreen sessions cannot show a UI.
Save before session stop;
stop refuses unsaved changes unless --discard is explicit. No remote transport.
"""


def number(value):
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise argparse.ArgumentTypeError('must be a finite non-negative number')
    return result


class CommandHelpMixin:
    def _format_action(self, action):
        if isinstance(action, argparse._SubParsersAction):
            return ''.join(self._format_action(command) for command in action._get_subactions())
        return super()._format_action(action)


class CommandHelpFormatter(CommandHelpMixin, argparse.HelpFormatter):
    pass


class CommandDefaultsFormatter(CommandHelpMixin, argparse.ArgumentDefaultsHelpFormatter):
    pass


class CommandRawFormatter(CommandHelpMixin, argparse.RawDescriptionHelpFormatter):
    pass


class CommandParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        formatter = kwargs.get('formatter_class', argparse.HelpFormatter)
        kwargs['formatter_class'] = {
            argparse.HelpFormatter: CommandHelpFormatter,
            argparse.ArgumentDefaultsHelpFormatter: CommandDefaultsFormatter,
            argparse.RawDescriptionHelpFormatter: CommandRawFormatter,
        }.get(formatter, formatter)
        super().__init__(*args, **kwargs)

    def add_subparsers(self, **kwargs):
        kwargs.setdefault('title', 'commands')
        kwargs.setdefault('metavar', 'COMMAND')
        return super().add_subparsers(**kwargs)


def build_parser():
    parser = CommandParser(prog='openshot-cli', description=(
        'Control a running OpenShot editor or persistent headless session. '
        'JSON results; stable object IDs; edits share OpenShot undo/redo.'), epilog=(
        'Start here: session list (running editors), session start (headless), agent '
        '(workflow and time conventions). Every command and subcommand accepts help or --help. '
        'Global options precede the command.'))
    parser.add_argument('--session', default=os.environ.get('OPENSHOT_SESSION'), help='Target session ID (or OPENSHOT_SESSION); auto-select only when exactly one is live.')
    parser.add_argument('--timeout', type=number, default=30, help='Response timeout in seconds (default: 30); a timeout does not cancel an edit.')
    groups = parser.add_subparsers(dest='group')
    guide = groups.add_parser('agent', help='Read the agent workflow, time/JSON conventions, limits, and examples.', description=AGENT_GUIDE, formatter_class=argparse.RawDescriptionHelpFormatter)
    guide.set_defaults(local='agent')

    def group(name, description, aliases=()):
        p = groups.add_parser(name, aliases=list(aliases), help=description, description=description)
        p.set_defaults(help_parser=p)
        return p.add_subparsers(dest='operation')

    def command(subs, name, description, method=None, aliases=()):
        p = subs.add_parser(name, aliases=list(aliases), help=description, description=description, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        p.set_defaults(method=method, help_parser=p)
        return p

    s = group('session', 'Discover, start, inspect, or stop persistent editing sessions.')
    command(s, 'list', 'List reachable GUI and headless sessions.', 'session.list').set_defaults(local='list')
    for name in ('start', 'serve'):
        p = command(s, name, 'Start a headless session ' + ('in the background.' if name == 'start' else 'in the foreground (for supervision).'))
        p.add_argument('--project', help='Existing .osp file to open; otherwise create an empty project.')
        p.add_argument('--show', action='store_true', help='Open the editor window in this session (requires a desktop display).')
        p.add_argument('--session-id', default=None, help=argparse.SUPPRESS)
        p.set_defaults(local=name)
    command(s, 'status', 'Return session mode, project, revision, and undo/redo availability.', 'session.status')
    command(s, 'show', 'Show or raise this session\'s editor window, preserving the live project and undo history. Requires a desktop display.', 'session.show')
    p = command(s, 'stop', 'Stop a headless session. GUI sessions must be closed in the editor.', 'session.stop')
    p.add_argument('--discard', action='store_true', help='Explicitly discard unsaved edits.')
    s = group('project', 'Inspect, open, and save the editing project.')
    command(s, 'get', 'Return profile, layers, object counts, path, and dirty state.', 'project.get')
    p = command(s, 'open', 'Open an existing .osp without interactive missing-media dialogs.', 'project.open')
    p.add_argument('path', help='Existing project path.')
    p.add_argument('--discard', action='store_true', help='Allow replacement of unsaved edits.')
    p = command(s, 'save', 'Save through the existing OpenShot project serializer.', 'project.save')
    p.add_argument('path', help='Destination .osp path (existing destination requires --overwrite).')
    p.add_argument('--overwrite', action='store_true', help='Allow replacing an existing project file.')
    p = command(s, 'profile', 'Inspect or change the project profile. Changes share existing frame-rate conversion and undo/redo.')
    ps = p.add_subparsers(dest='profile_operation')
    command(ps, 'get', 'Return full current profile settings and exact installed matches.', 'project.profile.get')
    p = command(ps, 'set', 'Set an installed or custom project profile, retiming existing clips/keyframes through OpenShot. One undo transaction.', 'project.profile.set')
    add_profile_selection(p, positional=True)
    p.add_argument('--width', type=int, help='Legacy exact installed-profile selector; also supply --height.')
    p.add_argument('--height', type=int, help='Height for legacy width/FPS selection.')
    p.add_argument('--fps-num', type=int, help='FPS numerator for legacy width selection; default 30.')
    p.add_argument('--fps-den', type=int, help='FPS denominator for legacy width selection; default 1.')
    s = group('profile', 'List/search installed profiles, inspect settings, and match source-video properties.')
    p = command(s, 'list', 'List installed and user profiles with stable IDs. No session required.', 'profile.list')
    p.add_argument('--search', help='Case-insensitive text in profile filename or description.')
    p.add_argument('--limit', type=int, default=50, help='Results per page, 1..500.')
    p.add_argument('--offset', type=int, default=0, help='Start offset into the filtered catalogue.')
    p = command(s, 'get', 'Get full profile settings by stable ID (builtin:filename or user:filename). No session required.', 'profile.get')
    p.add_argument('id', help='Profile ID from profile list.')
    p = command(s, 'match', 'Rank profiles against a video source; return exact IDs and explicit differences for alternatives.', 'profile.match')
    p.add_argument('--file', dest='file_id', required=True, help='Imported video ID. Images/audio do not define a video profile.')
    p.add_argument('--limit', type=int, default=10, help='Maximum ranked alternatives, 1..100.')
    s = group('operation', 'Inspect recent session-local operation outcomes after uncertain responses. No automatic retry or crash journal.')
    command(s, 'list', 'List recent mutations and exports, with operation IDs and outcomes.', 'operation.list')
    p = command(s, 'get', 'Get the recorded result/error for a recent operation ID returned by a response or timeout.', 'operation.get')
    p.add_argument('id', help='Operation ID. Records expire with the session or bounded history.')
    s = group('history', 'Use the same undo/redo history as the editor.')
    for op in ('undo', 'redo'):
        command(s, op, op.title() + ' the latest transaction, including a CLI batch.', 'history.' + op)
    for kind, description in [('file', 'Import and inspect source media.'), ('clip', 'Place and edit timeline clips.'), ('transition', 'Create and edit timeline mask transitions.'), ('effect', 'Browse with effects list; learn with effects TYPE help; inspect attached effects with instances/get.')]:
        s = group('effects' if kind == 'effect' else kind, description)
        command(s, 'instances' if kind == 'effect' else 'list', 'List project objects with stable IDs and summary fields.', kind + '.list')
        p = command(s, 'get', 'Return the full native JSON for one object.', kind + '.get')
        p.add_argument('id', help='Object ID returned by list or add/import.')
        p = command(s, 'remove', ('Remove an imported file; rejected while any clip uses it. Undoable.' if kind == 'file' else 'Remove this project object. Undoable.'), kind + '.remove')
        p.add_argument('id', help='Object ID.')
        if kind != 'file':
            p = command(s, 'set', ('Merge clip properties: volume:0 mutes, has_video:0 hides album art. Scalars set constants; Points replace curves. See properties.' if kind == 'clip' else 'Merge editable properties from get/properties. Scalars set constant keyframes; Points replace the whole curve.'), kind + '.set')
            p.add_argument('id', help='Object ID.')
            p.add_argument('--json', required=True, dest='values', help='JSON object, @file.json, or - for stdin. IDs, readers, and nested effects cannot be replaced.')
            p = command(s, 'properties', 'Return libopenshot property metadata and evaluated values at a 1-based frame.', kind + '.properties')
            p.add_argument('id', help='Object ID.')
            p.add_argument('--frame', type=int, default=1, help='Native clip/effect keyframe coordinate, 1-based.')
            kp = command(s, 'keyframe', 'Edit individual keyframe points without replacing the curve.')
            ks = kp.add_subparsers(dest='keyframe_operation')
            p = command(ks, 'set', 'Add/replace a point. Clip coordinates use source seconds * project FPS + 1; trimmed clips do not start at frame 1. Interpolation belongs to this destination point.', kind + '.keyframe.set')
            p.add_argument('id', help='Object ID.')
            p.add_argument('--property', required=True, help='Keyframed property from get/properties, e.g. volume or alpha.')
            p.add_argument('--frame', required=True, type=int, help='1-based native keyframe coordinate at project FPS.')
            p.add_argument('--value', required=True, type=float, help='Numeric property value; use properties for range/units.')
            p.add_argument('--interpolation', choices=['linear', 'bezier', 'constant'], default='linear', help='Interpolation to this point.')
        if kind == 'file':
            p = command(s, 'import', 'Import one media file using libopenshot reader detection (undoable).', 'file.import')
            p.add_argument('path', help='Local media path; image sequences are not auto-detected.')
        elif kind == 'clip':
            p = command(s, 'split', 'Split a clip at timeline seconds, snapped to the nearest project frame. Keeps both halves, source animation and effects; left keeps its ID, right receives new IDs. One undo group.', 'clip.split')
            p.add_argument('id', help='Clip ID from timeline overview or clip list.')
            p.add_argument('--at', required=True, type=number, help='Timeline seconds at the start of the right half, strictly inside the clip. Response reports actual snapped time and both IDs.')
            p = command(s, 'fade', 'Replace alpha or volume animation with a linear fade in/out, using source trim and project FPS automatically. One undo step; other properties unchanged.', 'clip.fade')
            p.add_argument('id', help='Clip ID.')
            p.add_argument('--in', dest='fade_in', type=number, default=0, help='Fade-in duration in seconds, starting at the clip in-point.')
            p.add_argument('--out', dest='fade_out', type=number, default=0, help='Fade-out duration in seconds, ending on the last visible frame.')
            p.add_argument('--property', choices=['alpha', 'volume'], default='alpha', help='alpha fades video; volume fades audio.')
            p.add_argument('--value', type=number, default=1, help='Peak alpha or linear audio gain; replaces the entire property curve.')
            p = command(s, 'add', 'Place an imported file on an existing project layer.', 'clip.add')
            p.add_argument('file_id', help='Imported file ID.')
            p.add_argument('--layer', type=int, required=True, help='Layer number from project get.')
            p.add_argument('--position', type=number, default=0, help='Timeline position in seconds.')
            p.add_argument('--start', type=number, default=0, help='Source in-point in seconds.')
            p.add_argument('--audio-only', action='store_true', help='Disable video/embedded album art; keep audio.')
            p.add_argument('--volume', type=number, default=1, help='Constant linear gain: 0=mute, 1=original, 0.5=half amplitude.')
            p.add_argument('--end', type=number, help='Exclusive source out-point; default media duration (10s for images).')
        elif kind == 'transition':
            p = command(s, 'add', 'Add a mask transition; brightness runs +1 to -1 (fade in), or reversed.', 'transition.add')
            p.add_argument('--mask', required=True, help='Local mask image/SVG path.')
            p.add_argument('--layer', type=int, required=True, help='Existing layer number from project get.')
            p.add_argument('--position', type=number, default=0, help='Timeline seconds.')
            p.add_argument('--duration', type=number, default=1, help='Duration in seconds, at least one project frame.')
            p.add_argument('--reverse', action='store_true', help='Fade out instead of in.')
        else:
            command(s, 'list', 'Browse available effects with short descriptions. Use effects TYPE help for guidance and properties. No session required.', 'effect.types')
            p = command(s, 'help', 'Detailed effect help: effects TYPE help. Includes purpose, usage, examples and properties. No session required.', 'effect.describe')
            p.add_argument('type', help='Class name or alias, e.g. AudioVisualization, audio_visualization, or "Audio Visualization".')
            p.add_argument('--property', help='Show details for just one property, e.g. visualization_type.')
            p = command(s, 'add', 'Attach a native effect to a clip; use effects list to discover names.', 'effect.add')
            p.add_argument('clip_id', help='Parent clip ID.')
            p.add_argument('type', help='Class name, display name, or alias from effects list, e.g. Blur or audio_visualization.')
        if kind == 'file':
            add_images(s, kind, command)
    s = group('timeline', 'Inspect text/JSON structure, native QWidget timeline images, or composed video frames.')
    p = command(s, 'overview', 'Compact timeline context: ordered IDs, source/timeline ranges, frame coordinates, stream state, effects, neighboring gaps/overlaps. No image or native property payload.', 'timeline.overview')
    p.add_argument('--start', type=number, default=0, help='Inclusive timeline seconds; show items intersecting this range.')
    p.add_argument('--end', type=number, help='Exclusive timeline seconds; default end of last item.')
    p.add_argument('--layer', type=int, help='Filter one layer number from project get or overview tracks.')
    p.add_argument('--limit', type=int, default=100, help='Maximum returned items, 1..500. Use next_offset for subsequent pages.')
    p.add_argument('--offset', type=int, default=0, help='Item offset into the filtered, ordered result.')
    add_images(s, 'timeline', command)
    p = command(s, 'view', 'Inspect the timeline as fast text (default), JSON, or an actual QWidget image. Fits used tracks and project duration; --output implies image for compatibility.', 'timeline.view')
    p.add_argument('--start', type=number, default=0, help='Viewport start in timeline seconds.')
    p.add_argument('--end', type=number, help='Exclusive viewport end in timeline seconds; default end of last clip.')
    p.add_argument('--pixels-per-second', type=number, help='Optional zoom override; derives width from range plus native track headers. Max width 4096.')
    p.add_argument('--width', type=int, default=1280, help='Image width including native track headers, 320..4096; range fits this width unless zoom override supplied.')
    p.add_argument('--height', type=int, help='Image height; default fits used tracks. A smaller explicit height crops lower tracks.')
    p.add_argument('--all-tracks', action='store_true', help='Include unused tracks instead of fitting only tracks containing clips/transitions.')
    p.add_argument('--track-size', choices=['minimal', 'compact', 'default', 'relaxed'], default='relaxed', help='Existing QWidget track-size preset; relaxed makes thumbnails and names easier to inspect.')
    p.add_argument('--track-label-width', type=int, default=220, help='Width reserved for native track labels and controls, 140..512 pixels.')
    p.add_argument('--mode', choices=['auto', 'thumbnails', 'waveforms'], default='auto', help='auto uses cached waveforms; thumbnails forces images; waveforms generates bounded audio envelopes for visible audio streams without changing the project.')
    p.add_argument('--output', help='New PNG path for image format; implies image when --format is omitted.')
    p.add_argument('--format', choices=['text', 'json', 'image'], help='Default text, or image when --output is supplied. JSON stays structured for scripts.')
    p.add_argument('--detail', choices=['summary', 'clips', 'full'], default='clips', help='Text/JSON detail: track summary, compact clip rows, or full timing/effect context.')
    p.add_argument('--layer', type=int, help='Filter text/JSON to one track number.')
    p.add_argument('--limit', type=int, default=100, help='Text/JSON items per page, 1..500.')
    p.add_argument('--offset', type=int, default=0, help='Text/JSON item pagination offset.')
    s = group('edit', 'Preflight ordered mutations, then apply as one undo group; supports project.profile and file/clip/transition/effects edits.')
    p = command(s, 'apply', 'Validate every command on a detached project before editing. Invalid input applies nothing. Runtime failures report completed operations; undo reverts the group.', 'edit.apply')
    p.add_argument('--json', required=True, dest='commands', help='JSON array, @file.json, or - for stdin. Entry: {"method":"file.import","as":"media","params":{"path":"/tmp/video.mp4"}}. Later params can use {"$ref":"media.id"}. Optional unique as names; earlier results only. One undo group, max 256 commands. Run agent for a complete example.')
    p.add_argument('--expect-revision', type=int, help='Reject before editing if the project revision changed.')
    s = group('export', 'Inspect presets, validate settings, and export snapshots using the installed engine.')
    p = command(s, 'preset', 'Browse existing OpenShot XML export presets; hardware availability depends on the installed engine and machine.')
    ps = p.add_subparsers(dest='preset_operation')
    p = command(ps, 'list', 'List export presets and codec availability. No session required.', 'export.preset.list')
    p.add_argument('--search', help='Filter preset ID/title/codec.')
    p = command(ps, 'get', 'Inspect preset codecs, quality tiers and defaults. No session required.', 'export.preset.get')
    p.add_argument('id', help='Preset ID from export preset list.')
    command(s, 'capabilities', 'Report preset encoder availability and advanced configuration schema. Hardware runtime availability is checked by the export worker.', 'export.capabilities')
    command(s, 'list', "List this session's export jobs, including completed/failed jobs and their outputs.", 'export.list')
    for op in ('validate', 'start'):
        p = command(s, op, 'Resolve and validate configuration without rendering.' if op == 'validate' else 'Export an immutable snapshot. Profile changes affect only this job; existing outputs are never overwritten.', 'export.'+op)
        p.add_argument('output', help='New destination file, or new directory for image_sequence mode.')
        p.add_argument('--preset', help='Existing preset ID from export preset list.')
        p.add_argument('--profile', help='Profile ID or project (default). Cannot combine with --from-file.')
        p.add_argument('--from-file', help="Match this imported video's profile exactly; use --create-custom if no installed match.")
        p.add_argument('--create-custom', action='store_true', help='Allow source-derived profile when no installed profile matches.')
        p.add_argument('--quality', choices=['low', 'med', 'high'], help='Preset quality tier (default high).')
        p.add_argument('--json', dest='config', help='Advanced export config object, @file.json, or -. See export capabilities for schema. Precedence: defaults, preset, JSON, explicit flags.')
        p.add_argument('--start-frame', type=int, help='First frame at EXPORT FPS, 1-based inclusive; default 1.')
        p.add_argument('--end-frame', type=int, help='Last frame at EXPORT FPS, inclusive; default end of composition.')
        if op == 'start':
            add_wait(p)
    for op in ('status', 'cancel'):
        p = command(s, op, 'Inspect job progress/result.' if op == 'status' else 'Cancel a running export and remove its partial output.', 'export.' + op)
        p.add_argument('job_id', help='Job ID returned by export start or export list.')
        if op == 'status':
            add_wait(p)
    # Show the actual JSON names alongside shell flags so agents can construct
    # batches without guessing hyphen/underscore or positional argument mappings.
    def annotate_json_help(parent):
        method = parent.get_default('method')
        if method:
            fields = [action.dest for action in parent._actions
                      if not isinstance(action, (argparse._HelpAction, argparse._SubParsersAction))
                      and action.dest not in ('wait', 'wait_timeout')]
            if fields:
                parent.epilog = 'JSON method: {}. Parameter names: {}. Shell flags such as --fps-num use the JSON name fps_num.'.format(method.replace('effect.', 'effects.', 1), ', '.join(fields))
        for action in parent._actions:
            if isinstance(action, argparse._SubParsersAction):
                for child in action.choices.values():
                    annotate_json_help(child)
    annotate_json_help(parser)
    return parser


def add_profile_selection(parser, positional=False):
    parser.add_argument('id', nargs='?', help='Installed profile ID from profile list.')
    parser.add_argument('--from-file', help='Imported video ID; selects an exact matching profile.')
    parser.add_argument('--create-custom', action='store_true', help='Embed a portable source-derived profile if no installed match exists.')
    parser.add_argument('--json', dest='values', help='Custom profile JSON, @file.json, or -. Supply width/height/FPS/aspect ratios and description; omitted fields inherit current values.')


def add_wait(parser):
    parser.add_argument('--wait', action='store_true', help='Wait client-side for completed/failed/cancelled state. Export failures exit 1; the editor remains responsive.')
    parser.add_argument('--wait-timeout', type=number, default=600, help='Maximum wait in seconds; timeout exits 1 with job ID, leaving the export running. Separate from global per-request --timeout.')


def add_images(subs, kind, command):
    for op in ('thumbnail', 'strip'):
        p = command(subs, op, ('Render any exact 1-based frame.' if op == 'thumbnail' else 'Render a timecoded contact sheet and return tile/frame metadata.') + ' PNG only; max 4096px per dimension and 8 Mi pixels.', kind + '.' + op)
        if kind == 'file':
            p.add_argument('id', help='Imported media ID; source time/FPS.')
        if op == 'thumbnail':
            p.add_argument('--frame', type=int, required=True, help='1-based frame number; timeline uses project FPS, file uses source FPS.')
            p.add_argument('--width', type=int, default=320, help='Output width in pixels, 1..4096; smaller previews reduce image size.')
            p.add_argument('--height', type=int, default=180, help='Output height in pixels, 1..4096; aspect ratio is preserved with padding.')
        else:
            p.add_argument('--start', type=number, default=0, help='Range start in seconds (inclusive).')
            p.add_argument('--end', type=number, required=True, help='Range end in seconds (exclusive).')
            p.add_argument('--count', type=int, default=8, help='Evenly spaced samples, 1..64.')
            p.add_argument('--columns', type=int, default=4, help='Grid columns, 1..64.')
            p.add_argument('--width', type=int, default=160, help='Per-tile image width in pixels; canvas width is columns times this value.')
            p.add_argument('--height', type=int, default=90, help='Per-tile image height in pixels; timecode labels add 24px.')
        p.add_argument('--output', required=True, help='New PNG path; parent directory must exist.')


def read_json(value):
    if value == '-':
        return parse_json(sys.stdin.read())
    if value.startswith('@'):
        return parse_json(Path(value[1:]).read_text())
    return parse_json(value)


def normalize_help(argv):
    """Support trailing help uniformly, plus effect-specific native help."""
    argv = list(argv)
    if argv and argv[0] == 'help':
        argv = argv[1:] + ['help']
    index = 0
    while index < len(argv) and argv[index].startswith('--'):
        if argv[index] in ('--session', '--timeout'):
            index += 2
        elif '=' in argv[index]:
            index += 1
        else:
            break
    if index < len(argv) and argv[index] == 'effects':
        commands = {'list', 'instances', 'get', 'remove', 'set', 'properties', 'keyframe', 'add', 'help', '--help', '-h'}
        if len(argv) > index+2 and argv[index+1] not in commands and argv[index+2] in ('help', '--help', '-h'):
            return argv[:index] + ['effects', 'help', argv[index+1]] + argv[index+3:]
    if argv and argv[-1] == 'help':
        argv[-1] = '--help'
    return argv


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) == 2 and argv[0] == '--_export-worker':
        from classes.agent.export_worker import main as export_worker
        return export_worker(argv[1])
    if 'project' in argv:
        index = argv.index('project')
        if argv[index+1:index+2] == ['profile'] and any(flag in argv[index+2:] for flag in ('--width', '--height')) and argv[index+2:index+3] != ['set']:
            argv.insert(index+2, 'set')
    parser = build_parser()
    args = parser.parse_args(normalize_help(argv))
    if not args.group or (not getattr(args, 'method', None) and not getattr(args, 'local', None)):
        getattr(args, 'help_parser', parser).print_help()
        return 0
    try:
        local = getattr(args, 'local', None)
        if local == 'agent':
            print(AGENT_GUIDE)
            return 0
        if local == 'serve':
            import openshot  # Load the native engine before Qt, as in GUI startup.
            from classes.qt_bootstrap import configure_qt
            configure_qt()
            from classes.agent.host import serve
            return serve(args.project, args.session_id, show=args.show)
        if local == 'start':
            result = start_session(args.project, show=args.show)
        else:
            from classes.agent.client import discover, request, select
            if getattr(args, 'method', '') in ('effect.types', 'effect.describe') and not args.session:
                os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
                import openshot  # Native engine before Qt, matching the GUI bootstrap.
                from qt_api import QApplication
                app = QApplication.instance() or QApplication([])
                from classes.agent.catalog import effect_types, describe_effect
                result = effect_types() if args.method == 'effect.types' else describe_effect(args.type, args.property)
            elif getattr(args, 'method', '') in ('profile.list', 'profile.get', 'export.preset.list', 'export.preset.get', 'export.capabilities') and not args.session:
                import openshot
                from classes.agent.profiles import command as profile_command
                from classes.agent.exporting import catalogue
                params = {key: value for key, value in vars(args).items() if key in ('id', 'search', 'limit', 'offset') and value is not None}
                result = profile_command(args.method, params) if args.method.startswith('profile.') else catalogue(args.method, params)
            elif local == 'list':
                result = [status for _, status in discover()]
            else:
                params = {k: v for k, v in vars(args).items() if k not in (
                    'group', 'operation', 'keyframe_operation', 'profile_operation', 'preset_operation', 'method', 'session', 'timeout', 'help_parser', 'local') and v is not None}
                for key in ('values', 'commands', 'config'):
                    if key in params:
                        params[key] = read_json(params[key])
                for key in ('path', 'mask', 'output'):
                    if key in params:
                        params[key] = str(Path(params[key]).expanduser().resolve())
                wait = params.pop('wait', False)
                wait_timeout = params.pop('wait_timeout', 600)
                record = select(args.session)
                result = request(record, args.method, params, args.timeout)
                if wait:
                    from classes.agent.waiting import wait_for_export
                    result = wait_for_export(record, result, request, args.timeout, wait_timeout)
        if isinstance(result, dict) and isinstance(result.get('data'), dict) and result['data'].get('format') == 'text':
            print(result['data']['text'])
        else:
            print(json.dumps({'ok': True, 'result': result}, allow_nan=False))
        return 0
    except (CommandError, OSError, ValueError, ImportError) as exc:
        error = {'code': getattr(exc, 'code', 'client_error'), 'message': str(exc)}
        if getattr(exc, 'details', None) is not None:
            error['details'] = exc.details
        print(json.dumps({'ok': False, 'error': error}), file=sys.stderr)
        return 1


def start_session(project, show=False):
    directory = session_dir()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    session_id = uuid.uuid4().hex
    log_path = directory / (session_id + '.log')
    command = cli_command('session', 'serve', '--session-id', session_id)
    if show:
        command.append('--show')
    if project:
        command += ['--project', str(Path(project).expanduser().resolve())]
    options = {'start_new_session': True} if os.name != 'nt' else {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
    with log_path.open('wb') as output:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output, stderr=output, **options)
    from classes.agent.client import request
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        for record in records():
            if record['session_id'] == session_id:
                try:
                    return request(record, 'session.status', timeout=1)['data']
                except CommandError:
                    pass
        if process.poll() is not None:
            raise CommandError('startup_failed', 'Headless startup failed; see ' + str(log_path))
        time.sleep(0.1)
    raise CommandError('startup_timeout', 'Session may still be starting. Run session list; log: ' + str(log_path))


if __name__ == '__main__':
    sys.exit(main())
