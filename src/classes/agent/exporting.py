"""
 @file
 @brief Resolve GUI presets and native profiles into a validated export snapshot.

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
import copy
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import openshot
from classes import info
from classes.convert_framerate import change_profile
from classes.keyframe_scaler import KeyframeScaler
from .protocol import CommandError
from .validation import fail, numeric, unknown
from . import profiles

SCHEMA = {
    'mode': 'video_audio (default), video, audio, image_sequence',
    'format': 'Container/extension, e.g. mp4, mov, webm, wav; image_sequence uses png or jpg',
    'profile': 'Complete native profile object, or installed ID, or project',
    'video_codec': 'Installed encoder name, including explicit hardware encoders such as h264_nvenc',
    'audio_codec': 'Installed audio encoder name',
    'video_bitrate': 'Integer bits/second, or quality number when quality_mode is crf/cqp/qp',
    'audio_bitrate': 'Integer bits/second', 'quality_mode': 'bitrate, crf, cqp, qp',
    'sample_rate': 'Positive integer Hz', 'channels': 'Positive integer', 'channel_layout': 'Native channel-layout integer',
    'top_field_first': 'Boolean for interlaced output',
    'video_options': 'Object of native FFmpegWriter SetOption names to scalar values; overrides preset defaults',
    'audio_options': 'Object of native FFmpegWriter SetOption names to scalar values',
    'hardware': 'Object: encoder_device and decoder_device integer indices; hardware_decoder native decoder selection integer',
    'threads': 'Positive FFmpeg thread count, optional',
}


def presets(search=None):
    rows = []
    for origin, folder in [('builtin', info.EXPORT_PRESETS_PATH), ('user', info.USER_PRESETS_PATH)]:
        for path in sorted(Path(folder).glob('*.xml')):
            try:
                root = ET.parse(path).getroot()
                get = lambda tag, default='': (root.findtext(tag) or default).strip()
                row = {'id': origin+':'+path.stem, 'title': get('title'), 'category': get('type'),
                       'format': get('videoformat'), 'video_codec': get('videocodec'), 'audio_codec': get('audiocodec'),
                       'sample_rate': int(get('samplerate', '48000')), 'channels': int(get('audiochannels', '2')),
                       'channel_layout': int(get('audiochannellayout', '3')),
                       'mode': {'Video & Audio': 'video_audio', 'Video Only': 'video', 'Audio Only': 'audio', 'Image Sequence': 'image_sequence'}.get(get('export-to'), 'video_audio'),
                       'video_quality': dict(root.find('videobitrate').attrib) if root.find('videobitrate') is not None else {},
                       'audio_quality': dict(root.find('audiobitrate').attrib) if root.find('audiobitrate') is not None else {},
                       'suggested_profiles': [p.text for p in root.findall('projectprofile')]}
                row['codecs_available'] = all(openshot.FFmpegWriter.IsValidCodec(row[key]) for key in ('video_codec', 'audio_codec') if row[key])
                if not search or search.casefold() in json.dumps(row).casefold():
                    rows.append(row)
            except (ET.ParseError, ValueError, OSError):
                continue
    return rows


def preset(identifier):
    rows = [row for row in presets() if identifier in (row['id'], row['title'])]
    if len(rows) != 1:
        raise CommandError('preset_not_found', 'Select an exact preset ID from export preset list.', {'requested': identifier})
    return rows[0]


def catalogue(method, p):
    if method == 'export.preset.get':
        return preset(p['id'])
    if method == 'export.preset.list':
        return presets(p.get('search'))
    return {'config_fields': SCHEMA, 'presets': [{'id': r['id'], 'title': r['title'], 'available': r['codecs_available']} for r in presets()],
            'availability': 'Codec availability means compiled encoder support. Device availability, container compatibility and native options are checked when the isolated worker opens the writer. No automatic hardware fallback.',
            'precedence': 'Defaults, preset, JSON config, explicit flags. Output frame numbers use export FPS. Custom export profiles never edit the project.'}


def bitrate(text):
    match = re.fullmatch(r'\s*([0-9.]+)\s*(crf|cqp|qp|kb/s|mb/s|b/s)?\s*', str(text), re.I)
    if not match:
        raise CommandError('invalid_preset', 'Unsupported preset bitrate: '+str(text))
    value, unit = float(match[1]), (match[2] or 'b/s').lower()
    return int(value * {'kb/s': 1000, 'mb/s': 1000000}.get(unit, 1)), unit if unit in ('crf', 'cqp', 'qp') else 'bitrate'


def resolve(service, params):
    data = copy.deepcopy(service.app.project._data)
    config = {'mode': 'video_audio', 'format': Path(params['output']).suffix.lstrip('.').lower() or 'mp4',
              'video_codec': 'libx264', 'audio_codec': 'aac', 'video_bitrate': 5000000, 'audio_bitrate': 192000,
              'quality_mode': 'bitrate', 'sample_rate': data['sample_rate'], 'channels': data['channels'],
              'channel_layout': data['channel_layout'], 'top_field_first': False,
              'video_options': {}, 'audio_options': {}, 'hardware': {}}
    selected_preset = params.get('preset')
    if selected_preset:
        row = preset(selected_preset)
        for key in ('mode', 'format', 'video_codec', 'audio_codec', 'sample_rate', 'channels', 'channel_layout'):
            config[key] = row[key]
        tier = params.get('quality', 'high')
        if row['video_quality'].get(tier):
            config['video_bitrate'], config['quality_mode'] = bitrate(row['video_quality'][tier])
        if row['audio_quality'].get(tier):
            config['audio_bitrate'], _ = bitrate(row['audio_quality'][tier])
    elif params.get('quality'):
        raise CommandError('invalid_argument', '--quality selects a tier of --preset; choose a preset first.')
    supplied = params.get('config') or {}
    for key in supplied:
        if key not in SCHEMA:
            unknown('params.config', key, SCHEMA)
    config.update(copy.deepcopy(supplied))
    selected = params.get('profile')
    if selected and params.get('from_file'):
        raise CommandError('invalid_argument', 'Choose --profile or --from-file, not both.')
    if params.get('from_file'):
        profile = profiles.resolve(service, {'from_file': params['from_file'], 'create_custom': params.get('create_custom', False)})
    else:
        value = selected or config.pop('profile', 'project')
        # Remove JSON profile even when an explicit selector overrides it.
        config.pop('profile', None)
        profile = profiles.validate(value) if isinstance(value, dict) else profiles.resolve(service, {'profile': value})
    config.pop('profile', None)
    if config['mode'] not in ('video_audio', 'video', 'audio', 'image_sequence'):
        fail('params.config.mode', SCHEMA['mode'], config['mode'])
    if not isinstance(config['format'], str) or not re.fullmatch(r'[a-zA-Z0-9]+', config['format']):
        fail('params.config.format', 'a container/extension name', config['format'])
    mode = config['mode']
    if mode == 'image_sequence':
        if config['format'] not in ('png', 'jpg', 'jpeg'):
            fail('params.config.format', 'png or jpg for image_sequence', config['format'])
        config['video_codec'] = 'mjpeg' if config['format'] in ('jpg', 'jpeg') else 'png'
    for key, enabled in [('video_codec', mode != 'audio'), ('audio_codec', mode in ('video_audio', 'audio'))]:
        if enabled and (not isinstance(config[key], str) or not openshot.FFmpegWriter.IsValidCodec(config[key])):
            fail('params.config.'+key, 'an encoder available in the installed engine', config[key], 'Inspect export preset list or export capabilities. Hardware requests never silently fall back.')
    if config['quality_mode'] not in ('bitrate', 'crf', 'cqp', 'qp'):
        fail('params.config.quality_mode', SCHEMA['quality_mode'], config['quality_mode'])
    for key in ('video_bitrate', 'audio_bitrate', 'sample_rate', 'channels', 'channel_layout'):
        numeric(config[key], 'params.config.'+key, integer=True, minimum=0 if key == 'video_bitrate' and config['quality_mode'] != 'bitrate' else 1)
    if not isinstance(config['top_field_first'], bool):
        fail('params.config.top_field_first', 'a boolean', config['top_field_first'])
    for key in ('video_options', 'audio_options'):
        if not isinstance(config[key], dict):
            fail('params.config.'+key, 'an object of native option names and scalar values', config[key])
        for name, value in config[key].items():
            if not name or isinstance(value, (dict, list, type(None), bool)):
                fail('params.config.'+key+'.'+name, 'a string or number', value)
    if not isinstance(config['hardware'], dict):
        fail('params.config.hardware', 'an object of device/decoder selections', config['hardware'])
    for key, value in config['hardware'].items():
        if key not in ('encoder_device', 'decoder_device', 'hardware_decoder'):
            unknown('params.config.hardware', key, ('encoder_device', 'decoder_device', 'hardware_decoder'))
        numeric(value, 'params.config.hardware.'+key, integer=True, minimum=0)
    if 'threads' in config:
        numeric(config['threads'], 'params.config.threads', integer=True, minimum=1, maximum=256)
    output = Path(params['output']).expanduser().resolve()
    if output.exists():
        raise CommandError('already_exists', 'Export output already exists; choose a new file/directory: '+str(output))
    if not output.parent.is_dir():
        raise CommandError('not_found', 'Export parent directory does not exist: '+str(output.parent))
    if mode != 'image_sequence' and output.suffix.lstrip('.').lower() != config['format']:
        raise CommandError('format_mismatch', 'Output extension must match resolved format '+config['format']+'.', {'output': str(output), 'format': config['format']})
    old_fps = data['fps']['num']/data['fps']['den']
    fps = profile['fps']['num']/profile['fps']['den']
    if fps != old_fps:
        KeyframeScaler(fps/old_fps)(data)
    native = openshot.Profile(); native.SetJson(json.dumps(profile))
    if fps != old_fps:
        change_profile(data['clips']+data['effects']+data.get('markers', []), native)
    for key in ('width', 'height', 'fps', 'pixel_ratio', 'display_ratio'):
        data[key] = copy.deepcopy(profile[key])
    data.update(profile=profile['description'], profile_settings=profile,
                sample_rate=config['sample_rate'], channels=config['channels'], channel_layout=config['channel_layout'])
    length = max([0]+[c['position']+c['end']-c['start'] for c in data['clips']])
    start, end = params.get('start_frame', 1), params.get('end_frame', math.floor(length*fps+0.5))
    numeric(start, 'params.start_frame', integer=True, minimum=1)
    numeric(end, 'params.end_frame', integer=True, minimum=start, maximum=math.ceil(length*fps))
    video = {'vcodec': config['video_codec'], 'fps': profile['fps'], 'width': profile['width'], 'height': profile['height'],
             'pixel_ratio': profile['pixel_ratio'], 'interlace': not profile['progressive'], 'topfirst': config['top_field_first'],
             'spherical': profile['spherical'], 'video_bitrate': config['video_bitrate']}
    audio = {'acodec': config['audio_codec'], **{key: config[key] for key in ('sample_rate', 'channels', 'channel_layout', 'audio_bitrate')}}
    return {'project': data, 'output': str(output), 'start': start, 'end': end, 'config': config,
            'profile': profile, 'video': video, 'audio': audio,
            'validation': {'schema': True, 'encoder_names': True, 'runtime_checked': False,
                           'note': 'Native options, container compatibility, and hardware devices are checked in the isolated export worker.'}}


def public(spec):
    return {key: value for key, value in spec.items() if key != 'project'}
