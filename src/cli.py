#!/usr/bin/env python3
"""
 @file
 @brief Agent-first command-line entry point. Help does not import Qt or libopenshot.

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """
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

ROOT_HELP = """Start: session list (connect) or session start (new).
Workflow: inspect -> edit -> project save / export start.
More help: COMMAND help, e.g. clip keyframe help.
"""

COMMAND_SUMMARIES = {
    'session': 'Connect or start an editor',
    'project': 'Open, inspect, and save',
    'profile': 'Find video profiles',
    'operation': 'Check recent edit outcomes',
    'history': 'Undo and redo',
    'file': 'Import and inspect media',
    'clip': 'Edit clips and keyframes',
    'transition': 'Edit transitions',
    'effects': 'Discover and edit effects',
    'timeline': 'Inspect and preview',
    'edit': 'Batch and bulk changes',
    'export': 'Render video or audio',
}

GROUP_HELP = {
    'session': """Start with session list to discover running editors, or session start
--project /path/edit.osp to open a persistent headless session.
Use --session ID before commands when multiple sessions exist.
session show opens the same session's editor. Save before session stop.
After a timeout, check operation list/get before retrying a mutation.""",
    'clip': """Workflow: file import, clip add, then inspect with clip get/properties.
Use project get for real layer numbers and returned IDs for all objects.
position is timeline seconds; start/end are source seconds, with end exclusive.
clip split ID --at 6.5 cuts at timeline time and preserves both halves' animation.
clip set replaces supplied properties; a scalar replaces animation with a constant.
clip adjust adds/multiplies existing values and curves.
Use clip keyframe help for animation; edit bulk help for changes across clips.""",
    'effects': """Discover with effects list, then effects TYPE help for settings and examples.
effects add attaches an effect; effects instances lists attached effects and IDs.
Inspect with effects properties/get before editing. A scalar in effects set
replaces animation with a constant. Use effects keyframe help for animation,
including nested color properties; edit bulk help for applying effects to clips.""",
    'transition': """Inspect transition list/get/properties before editing.
A scalar in transition set replaces animation with a constant.
Use transition keyframe help for the shared animation workflow.""",
    'edit': """Workflow: preview with edit select, validate with edit bulk --dry-run,
then apply with --expect-revision using the revision returned by selection.
Bulk templates inherit each selected clip's id (clip_id for effects.add).
Named references stay local to each selected clip.

edit apply groups different ordered edits into one undo step.
Use --json @commands.json; entries contain method, params, and optional as:
[{"method":"file.import","as":"media","params":{"path":"/path/video.mp4"}},
 {"method":"clip.add","params":{"file_id":{"$ref":"media.id"},"layer":1000000}}]
Substitute a real layer from project get. References name earlier results only.
Batches preflight before editing; runtime failures can leave partial changes.
Limit: 256 expanded commands. history undo/redo shares the editor's history.
Save/open/export stay outside edit batches.""",
}

KEYFRAME_HELP = """Workflow: list ID to discover curves, then list ID --property NAME to inspect
points. The same operations work for clips, effects, and transitions, including
nested properties such as color.red.

Prefer --space clip --unit seconds for time relative to the visible clip start,
or --space timeline to align animations across clips. Attached effects use their
parent clip's timing. Native coordinates include source trim; frames are 1-based
at project FPS, seconds start at zero.

Example: fade volume over a clip's first visible second:
  clip keyframe set ID --property volume --space clip --unit seconds --at 0 --value 0
  clip keyframe set ID --property volume --space clip --unit seconds --at 1 --value 1

set changes one point; interpolation controls the segment INTO that point.
transform shifts/scales ranges. copy/paste require --mode merge or replace.
clear replaces animation with a constant. Bezier handles are normalized native
handles, not frame offsets. Each operation's help explains its exact arguments.
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


class RootHelpFormatter(CommandRawFormatter):
    def __init__(self, prog):
        super().__init__(prog, width=72, max_help_position=18)


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
    parser = CommandParser(
        prog='openshot-cli', usage='%(prog)s [OPTIONS] COMMAND',
        description=(
            '  []  []  []  []  []  []  []  []\n'
            '  ----------------------------\n'
            '     OpenShot Video Editor\n'
            '  Lights. Camera. Command line.\n'
            '  ----------------------------\n'
            '  []  []  []  []  []  []  []  []'),
        epilog=ROOT_HELP, formatter_class=RootHelpFormatter)
    parser.add_argument('--session', metavar='ID', default=os.environ.get('OPENSHOT_SESSION'),
                        help='Target session (before COMMAND).')
    parser.add_argument('--timeout', metavar='SEC', type=number, default=30,
                        help='Wait limit (default: 30s); work continues.')
    groups = parser.add_subparsers(dest='group')
    def group(name, description, aliases=()):
        p = groups.add_parser(name, aliases=list(aliases), help=COMMAND_SUMMARIES[name], description=description,
                              epilog=GROUP_HELP.get(name), formatter_class=argparse.RawDescriptionHelpFormatter)
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
            add_keyframes(s, kind, command)
        if kind == 'file':
            p = command(s, 'import', 'Import one media file using libopenshot reader detection (undoable).', 'file.import')
            p.add_argument('path', help='Local media path; image sequences are not auto-detected.')
        elif kind == 'clip':
            p = command(s, 'adjust', 'Apply relative add/multiply adjustments to numeric properties or all values in a curve. One undo step.', 'clip.adjust')
            p.add_argument('id', help='Clip ID.')
            p.add_argument('--json', dest='values', required=True, help='Object such as {"position":{"add":2},"volume":{"multiply":0.5}}. Multiply first, then add; preserves curve timing and handles.')
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
    p.add_argument('--json', required=True, dest='commands', help='JSON array, @file.json, or - for stdin. Entry: {"method":"file.import","as":"media","params":{"path":"/tmp/video.mp4"}}. Later params can use {"$ref":"media.id"}. Optional unique as names; earlier results only. One undo group, max 256 commands. See edit help for a complete example.')
    p.add_argument('--expect-revision', type=int, help='Reject before editing if the project revision changed.')
    p.add_argument('--dry-run', action='store_true', help='Preflight only; return command count and revision without changing project/history. Generated IDs are not reserved.')
    p = command(s, 'select', 'Preview a deterministic clip selection without editing. Filters combine with AND; time range is half-open overlap.', 'edit.select')
    p.add_argument('--json', dest='selection', required=True, help='Selector object: ids (array), layer, start/end seconds, file_id, effect (class or alias), or {"all":true}. Empty selectors are rejected.')
    p = command(s, 'bulk', 'Expand per-clip templates into the existing edit.apply transaction. Preflight all targets; one undo group, max 256 expanded commands.', 'edit.bulk')
    p.add_argument('--select', dest='selection', required=True, help='Selector JSON, @file.json, or -. Preview with edit select first; use expect-revision when applying.')
    p.add_argument('--json', dest='commands', required=True, help='Command array. Clip commands inherit id; effects.add inherits clip_id. Named references are local to each clip. Other effect edits must reference an earlier named effect. Explicit target IDs are rejected.')
    p.add_argument('--expect-revision', type=int, help='Reject if the selection/project has changed since preview.')
    p.add_argument('--dry-run', action='store_true', help='Validate the expanded batch without editing; return selected IDs and command count.')
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


def add_keyframes(subs, kind, command):
    parent = command(subs, 'keyframe', 'Inspect and edit curves, including nested properties such as color.red. Uses the existing undo transaction.')
    parent.epilog = KEYFRAME_HELP
    parent.formatter_class = CommandRawFormatter
    children = parent.add_subparsers(dest='keyframe_operation')
    descriptions = {
        'list': 'Discover curve property paths, or return points for --property in explicit coordinates. Optional inclusive range.',
        'set': 'Add/update one point; interpolation belongs to the destination point. Existing handles are preserved unless supplied.',
        'remove': 'Remove points in an inclusive range or at one coordinate. Removing the last point retains its value as a constant at native frame 1.',
        'clear': 'Replace animation with a constant. Use value, or evaluate at the supplied coordinate (default native frame 1).',
        'transform': 'Move/scale an inclusive point range around its first point or an explicit pivot. Reject collisions; leave other points untouched.',
        'copy': 'Copy a source curve range to this object/property, anchored at at. Source uses the same space/unit; handles and interpolation are retained.',
        'paste': 'Paste point JSON from keyframe list (points array), using the chosen space/unit. Explicit merge or replace required.',
    }
    for op, description in descriptions.items():
        p = command(children, op, description, kind + '.keyframe.' + op)
        p.add_argument('id', help='Target object ID.')
        p.add_argument('--property', required=op != 'list', help='Keyframe property path, e.g. volume or color.red. Omit for list to discover all editable curves.')
        p.add_argument('--space', choices=['native', 'clip', 'timeline'], default='native', help='native = source-trim keyframe coordinates; clip = visible clip start; timeline = project start. Attached effects use parent clip timing.')
        p.add_argument('--unit', choices=['frames', 'seconds'], default='frames', help='Frames are 1-based at project FPS; seconds start at zero and snap to nearest frame. Hidden points may have nonpositive clip/timeline coordinates.')
        if op in ('set', 'remove', 'clear', 'copy'):
            p.add_argument('--at', type=float, help='Coordinate in space/unit; required for set/copy unless legacy frame is supplied for set.')
        if op == 'set':
            p.add_argument('--frame', type=int, help='Legacy 1-based native frame; cannot combine with at or non-native coordinates.')
        if op in ('set', 'clear'):
            p.add_argument('--value', type=float, required=op == 'set', help='Numeric value; clear defaults to evaluating the original curve.')
        if op == 'set':
            p.add_argument('--interpolation', choices=['linear', 'bezier', 'constant'], default='linear', help='Interpolation to this point.')
            p.add_argument('--handles', help='JSON object with handle_left/handle_right {X,Y} and/or handle_type (0..2); native normalized handles, not frame coordinates.')
        if op in ('list', 'remove', 'transform', 'copy'):
            p.add_argument('--start', type=float, help='Inclusive range start, in space/unit; copy uses source coordinates.')
            p.add_argument('--end', type=float, help='Inclusive range end, in space/unit; copy uses source coordinates.')
        if op == 'transform':
            p.add_argument('--offset', type=float, default=0, help='Signed time shift in unit, applied after scaling.')
            p.add_argument('--scale', type=float, default=1, help='Positive time scale factor; collisions after frame snapping are rejected.')
            p.add_argument('--pivot', type=float, help='Scale origin in space/unit; default first selected point.')
        if op == 'copy':
            p.add_argument('--source-id', required=True, help='Source object ID of the same kind.')
            p.add_argument('--source-property', help='Source property path; defaults to target property.')
        if op == 'paste':
            p.add_argument('--json', dest='points', required=True, help='Array of point objects from keyframe list, @file.json, or -. co.X uses space/unit.')
        if op in ('copy', 'paste'):
            p.add_argument('--mode', choices=['merge', 'replace'], required=True, help='merge replaces points at matching frames; replace replaces the entire target curve.')


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
    from classes.cli_console import ensure_standard_streams
    ensure_standard_streams()
    argv = list(sys.argv[1:] if argv is None else argv)
    # The dedicated console alias also accepts the common executable prefix.
    if argv[:1] == ['--cli']:
        argv.pop(0)
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
                for key in ('values', 'commands', 'config', 'selection', 'points', 'handles'):
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
