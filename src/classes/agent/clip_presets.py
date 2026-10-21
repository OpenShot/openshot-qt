"""
 @file
 @brief Editor clip-menu presets (Motion, Look, Speed, Repeat, Waveform) for the CLI.

The preset logic is shared with the timeline context menu; this module only
validates CLI input and saves through Query in the caller's undo transaction.

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
import json
import math
import uuid

import openshot
from classes.clip_utils import clamp_timing_to_media
from classes.look_presets import LOOK_PRESETS, apply_look_preset, reset_look
from classes.query import Clip
from classes.waveform_cache import externalize
from windows.views.motion import apply_motion
from windows.views.repeat import apply_repeat
from windows.views.retime import apply_time_action
from windows.views.timeline_backend.enums import MenuAnimate, MenuTime
from .protocol import CommandError

SPEED_MODES = {'forward': MenuTime.FORWARD, 'backward': MenuTime.BACKWARD, 'reverse': MenuTime.REVERSE,
               'freeze': MenuTime.FREEZE, 'freeze-zoom': MenuTime.FREEZE_ZOOM, 'reset': MenuTime.NONE}


def command(service, name, p):
    clip = service.obj('clip', p['id'])
    data = clip.data
    layer = next((row for row in service.app.project.get('layers') or [] if row['number'] == data.get('layer')), {})
    if layer.get('lock'):
        raise CommandError('locked_track', 'The clip is on a locked track. Unlock it first.', {'layer': data.get('layer')})
    if name == 'waveform':
        return waveform(service, clip, p.get('hide', False))
    reader = data.get('reader') or {}
    if name in ('motion', 'look') and not (reader.get('has_video', True) or data.get('waveform')):
        raise CommandError('unsupported', name.title() + ' presets need a clip with video or a visible waveform.')
    fps = service.fps()
    base = service.native('clip', data)  # Current values, read before any edits.

    if name == 'motion':
        at = p.get('at')
        apply_motion(data, MenuAnimate[p['preset'].upper().replace('-', '_')], fps, base_clip=base,
                     playhead_frame=1 if at is None else math.floor(at * fps + 0.5) + 1,
                     project_size=(service.app.project.get('width'), service.app.project.get('height')),
                     load_reader=mask_reader, new_id=service.app.project.generate_id)
    elif name == 'look':
        effect, preset = p['effect'], p['preset']
        if effect == 'all':
            if preset != 'none':
                raise CommandError('invalid_argument', '--effect all only supports --preset none (reset every Look effect).')
            reset_look(data)
        else:
            if preset not in LOOK_PRESETS[effect]:
                raise CommandError('invalid_argument', '{} presets: {}.'.format(effect, ', '.join(LOOK_PRESETS[effect])))
            apply_look_preset(data, effect, preset, lambda class_name: new_effect(service, class_name))
    elif name == 'speed':
        apply_time_action(clip, SPEED_MODES[p['mode']], fps, *speed_arguments(data, p), base_clip=base)
    else:
        passes = p['passes']
        ramp = p.get('ramp', 0)
        if not 2 <= passes <= 500 or not -1000 <= ramp <= 1000:
            raise CommandError('invalid_argument', 'passes must be 2..500 and ramp -1000..1000 percent.')
        apply_repeat(clip, p.get('pattern', 'loop'), -1 if p.get('reverse') else 1, passes,
                     int(round(p.get('delay', 0) * fps)), ramp / 100.0, fps)

    clamp_timing_to_media(data, Clip.get(id=clip.id))
    service.validate_timing(data)
    service.native('clip', data)  # Parse before distributing to native/UI listeners.
    clip.save()
    if name in ('speed', 'repeat') and (data.get('ui') or {}).get('audio_data'):
        waveform(service, service.obj('clip', clip.id), False)  # Redraw for the new timing.
    return service.obj('clip', clip.id).data


def speed_arguments(data, p):
    """Return Speed menu (speed label, playhead seconds) from CLI flags."""
    mode, factor, at, duration = p['mode'], p.get('factor'), p.get('at'), p.get('duration')
    if (factor is not None) != (mode in ('forward', 'backward')):
        raise CommandError('invalid_argument', '--factor is required for, and only used by, forward/backward.')
    if mode in ('forward', 'backward'):
        if factor <= 0:
            raise CommandError('invalid_argument', '--factor must be greater than 0.')
        return '{}X'.format(factor), 0.0
    if (at is not None or duration is not None) != mode.startswith('freeze'):
        raise CommandError('invalid_argument', '--at and --duration are required for, and only used by, freeze modes.')
    if mode.startswith('freeze'):
        if at is None or not duration:
            raise CommandError('invalid_argument', 'Freeze needs --at (timeline seconds) and --duration > 0.')
        finish = data['position'] + data['end'] - data['start']
        if not data['position'] <= at < finish:
            raise CommandError('out_of_range', '--at must be inside the clip ({} to {} timeline seconds).'.format(data['position'], finish))
        return str(duration), at
    return '1X', 0.0


def mask_reader(path):
    reader = openshot.QtImageReader(path)
    reader.Open()
    try:
        return json.loads(reader.Json())
    finally:
        reader.Close()


def new_effect(service, class_name):
    effect = openshot.EffectInfo().CreateEffect(class_name)
    if effect is None:
        raise CommandError('invalid_effect', class_name + ' is not available in this libopenshot build.')
    effect.Id(service.app.project.generate_id())
    return json.loads(effect.Json())


def waveform(service, clip, hide):
    if hide:
        clip.data = {'ui': {'audio_data': []}}
    else:
        from windows.views.timeline_backend.qwidget.snapshot import snapshot_clips
        clips, _ = snapshot_clips('waveforms', 0, math.inf, service.fps(), clip_ids={clip.id})
        ui = next(c.data.get('ui') or {} for c in clips if c.id == clip.id)
        if not ui.get('audio_data'):
            raise CommandError('no_audio', 'This clip has no audio to draw.')
        clip.data = externalize({'ui': dict(ui, waveform_token=uuid.uuid4().hex)})
    clip.save()
    return service.obj('clip', clip.id).data
