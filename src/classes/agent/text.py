"""
 @file
 @brief Text commands for the CLI: add, inspect, and style editor text clips.

Text uses the same code as the editor. Words, font, size, alignment, box width
and default colors belong to the text in Project Files and are shared by every
clip using it. Position, scale, rotation, opacity and timing are ordinary clip
properties, and each clip can animate its own text colors and outline/border
widths with the text_* keyframe properties.

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
import difflib
import json

import openshot
from classes.direct_text import (TEXT_ANIMATED, default_text, new_text_clip, save_text_asset, save_clip_data,
                                 reset_text_clips, initialize_text_curves)
from classes.query import Clip, File
from .protocol import CommandError
from .validation import fail, numeric

# Style parameters, named like the text's style keys: (kind, minimum, maximum).
STYLE = {
    'font_family': ('font', None, None),
    'font_size': ('int', 8, 1000),
    'font_bold': ('bool', None, None),
    'font_italic': ('bool', None, None),
    'alignment': ('choice', None, None),
    'width': ('int', 64, 8192),
    'letter_spacing': ('int', -50, 200),
    'line_spacing': ('number', 0.5, 5),
    'background_padding': ('int', 0, 200),
    'background_corner': ('number', 0, 200),
    'color': ('color', None, None),
    'background': ('color', None, None),
    'stroke': ('color', None, None),
    'border': ('color', None, None),
    'stroke_width': ('number', 0, 30),
    'border_width': ('number', 0, 30),
}
ALIGNMENTS = ('left', 'center', 'right')
KEYFRAME_PROPERTIES = ['text_' + key for key in TEXT_ANIMATED]
# Clip placement presets: gravity, then location_x/location_y as fractions of the frame.
PLACES = {
    'center': (openshot.GRAVITY_CENTER, 0.0, 0.0),
    'top': (openshot.GRAVITY_TOP, 0.0, 0.05),
    'bottom': (openshot.GRAVITY_BOTTOM, 0.0, -0.05),
    'top-left': (openshot.GRAVITY_TOP_LEFT, 0.05, 0.05),
    'top-right': (openshot.GRAVITY_TOP_RIGHT, -0.05, 0.05),
    'bottom-left': (openshot.GRAVITY_BOTTOM_LEFT, 0.05, -0.05),
    'bottom-right': (openshot.GRAVITY_BOTTOM_RIGHT, -0.05, -0.05),
    'lower-third': (openshot.GRAVITY_BOTTOM_LEFT, 0.05, -0.15),
}


def command(service, name, p):
    if name == 'fonts':
        return fonts(p)
    if name == 'list':
        return text_list(service, p)
    if name == 'add':
        return add(service, p)
    clip, asset = target(service, p['id'])
    if name == 'get':
        return describe(service, asset, clip)
    if clip and locked(service, clip):
        raise CommandError('locked_track', 'The clip is on a locked track. Unlock it first.', {'layer': clip.data['layer']})
    if name == 'reset':
        if not clip:
            raise CommandError('invalid_argument', 'text reset needs a text clip ID; it also removes that clip\'s own text keyframes.')
        if p.get('keyframes_only'):
            data = copy.deepcopy(clip.data)
            for key in TEXT_ANIMATED:
                data.pop('text_' + key, None)
            data['text_style_overrides'] = []
            data['_text_asset_update'] = True  # Default curves are not this clip's own edits.
            save_clip_data(initialize_text_curves(data))
        else:
            reset_text_clips([clip.id], service.app.project.get('width'), service.app.project.get('height'))
        return describe(service, File.get(id=asset.id), Clip.get(id=clip.id))
    return update(service, clip, asset, p)


def target(service, object_id):
    """A text clip and its text, or just a text from Project Files."""
    clip = Clip.get(id=object_id)
    if clip and clip.id == object_id:
        if not clip.data.get('direct_text'):
            raise CommandError('not_text', 'Clip {} is not a text clip. Use text list to find texts.'.format(object_id))
        asset = File.get(id=clip.data.get('file_id'))
        if not asset:
            raise CommandError('not_found', 'The text for clip {} is missing from Project Files.'.format(object_id))
        return clip, asset
    asset = File.get(id=object_id)
    if asset and asset.id == object_id:
        if asset.data.get('type') != 'QtTextReader':
            raise CommandError('not_text', 'File {} is not a text. Use text list to find texts.'.format(object_id))
        return None, asset
    raise CommandError('not_found', 'No text clip or text with ID {}. Use text list or timeline overview.'.format(object_id))


def locked(service, clip):
    return any(row['number'] == clip.data['layer'] and row.get('lock') for row in service.app.project.get('layers') or [])


def style_changes(p):
    """Validated style values from params, in the text's own format."""
    changes = {}
    if 'text' in p:
        if not isinstance(p['text'], str) or not p['text'].strip():
            fail('params.text', 'non-empty text', p.get('text'), 'Use a real newline character for more lines.')
        changes['text'] = p['text']
    for key, (kind, minimum, maximum) in STYLE.items():
        if key not in p:
            continue
        value, path = p[key], 'params.' + key
        if kind == 'font':
            value = font_family(value)
        elif kind == 'bool':
            if not isinstance(value, bool):
                fail(path, 'a boolean', value)
        elif kind == 'choice':
            if value not in ALIGNMENTS:
                fail(path, 'one of ' + ', '.join(ALIGNMENTS), value)
        elif kind == 'color':
            value = color(value, path)
        else:
            numeric(value, path, integer=kind == 'int', minimum=minimum, maximum=maximum)
        changes[key] = value
    return changes


def color(value, path):
    from qt_api import QColor
    parsed = QColor(value) if isinstance(value, str) else QColor()
    if not parsed.isValid():
        fail(path, 'a color like #ffffff, #80000000 (#AARRGGBB) or a CSS name', value,
             'Use transparent or #00000000 for none.')
    return parsed.name(QColor.HexArgb)


def installed_fonts():
    from qt_api import QFontDatabase
    return sorted(set(QFontDatabase().families()), key=str.lower)


def font_family(value):
    families = installed_fonts()
    if isinstance(value, str):
        match = next((family for family in families if family.lower() == value.strip().lower()), None)
        if match:
            return match
    close = difflib.get_close_matches(str(value), families, n=3, cutoff=0.5)
    hint = ('Did you mean {}?'.format(', '.join(repr(c) for c in close)) if close else '') + \
        ' Run text fonts --search NAME to list installed fonts.'
    fail('params.font_family', 'an installed font family', value, hint.strip())


def fonts(p):
    search = (p.get('search') or '').lower()
    rows = [family for family in installed_fonts() if search in family.lower()]
    limit, offset = p.get('limit', 50), p.get('offset', 0)
    numeric(limit, 'params.limit', integer=True, minimum=1, maximum=500)
    numeric(offset, 'params.offset', integer=True, minimum=0)
    return {'fonts': rows[offset:offset+limit], 'total': len(rows),
            'next_offset': offset+limit if offset+limit < len(rows) else None}


def text_list(service, p):
    search = (p.get('search') or '').lower()
    clips = Clip.filter()
    rows = []
    for asset in File.filter():
        style = asset.data.get('direct_text')
        if asset.data.get('type') != 'QtTextReader' or not isinstance(style, dict):
            continue
        if search and search not in ' '.join((asset.data.get('name', ''), style.get('text', ''),
                                              style.get('font_family', ''))).lower():
            continue
        rows.append({'id': asset.id, 'name': asset.data.get('name'), 'text': style.get('text'),
                     'font_family': style.get('font_family'), 'font_size': style.get('font_size'),
                     'clip_ids': [c.id for c in clips if c.data.get('file_id') == asset.id]})
    limit, offset = p.get('limit', 50), p.get('offset', 0)
    numeric(limit, 'params.limit', integer=True, minimum=1, maximum=500)
    numeric(offset, 'params.offset', integer=True, minimum=0)
    return {'texts': rows[offset:offset+limit], 'total': len(rows),
            'next_offset': offset+limit if offset+limit < len(rows) else None}


def describe(service, asset, clip=None):
    """A text's shared style, the clips using it, and one clip's own text keyframes."""
    style = asset.data['direct_text']
    result = {'file_id': asset.id, 'name': asset.data.get('name'), 'style': copy.deepcopy(style),
              'box': {'width': style['width'], 'height': style['height']},
              'clip_ids': [c.id for c in Clip.filter() if c.data.get('file_id') == asset.id]}
    if clip:
        data = clip.data
        result['clip'] = dict(service.summary('clip', data),
                              keyframed=sorted(key for key in data.get('text_style_overrides', []) if key in TEXT_ANIMATED),
                              keyframe_properties=KEYFRAME_PROPERTIES)
    return result


def place(data, name):
    gravity, x, y = PLACES[name]
    data['gravity'] = gravity
    data['location_x'] = json.loads(openshot.Keyframe(x).Json())
    data['location_y'] = json.loads(openshot.Keyframe(y).Json())


def add(service, p):
    project = service.app.project
    layer = service.layer(p['layer'])
    position = p.get('position', 0)
    duration = p.get('duration', 5)
    numeric(position, 'params.position', minimum=0)
    numeric(duration, 'params.duration', minimum=1 / service.fps())
    style = default_text(project.get('width'), project.get('height'))
    style.update(style_changes(p))
    data = new_text_clip(style, None, position, layer, duration)
    data['id'] = project.generate_id()
    place(data, p.get('place', 'center'))
    service.native('clip', data)  # Parse before distributing to native/UI listeners.
    asset = save_text_asset(data['direct_text'])
    data['file_id'] = asset.id
    data['reader'] = copy.deepcopy(asset.data)
    save_clip_data(data)
    return describe(service, File.get(id=asset.id), Clip.get(id=data['id']))


def update(service, clip, asset, p):
    changes = style_changes(p)
    if p.get('place') and not clip:
        raise CommandError('invalid_argument', '--place moves one clip; pass a text clip ID instead of a file ID.')
    if p.get('this_clip_only') and not clip:
        raise CommandError('invalid_argument', '--this-clip-only needs a text clip ID.')
    if not changes and not p.get('place'):
        raise CommandError('invalid_argument', 'Nothing to change. Pass --text, --place, or a style option; see text set help.')
    shared = [c.id for c in Clip.filter() if c.data.get('file_id') == asset.id]
    if changes:
        style = copy.deepcopy(asset.data['direct_text'])
        style.update(changes)
        if p.get('this_clip_only') and len(shared) > 1:
            # A separate copy of the text, for this clip only.
            asset = save_text_asset(style)
            data = copy.deepcopy(Clip.get(id=clip.id).data)
            data.update(file_id=asset.id, reader=copy.deepcopy(asset.data), direct_text=copy.deepcopy(asset.data['direct_text']))
            data['_text_asset_update'] = True
            save_clip_data(data)
            shared = [clip.id]
        else:
            asset = save_text_asset(style, asset.id)
    if p.get('place'):
        data = copy.deepcopy(Clip.get(id=clip.id).data)
        place(data, p['place'])
        save_clip_data(data)
    result = describe(service, File.get(id=asset.id), Clip.get(id=clip.id) if clip else None)
    result['changed_clip_ids'] = shared if changes else [clip.id]
    # Clips that animate a style keep their own value instead of the new shared one.
    hidden = {c.id: sorted(set(changes) & set(c.data.get('text_style_overrides', [])))
              for c in (Clip.get(id=cid) for cid in shared) if c}
    hidden = {cid: keys for cid, keys in hidden.items() if keys}
    if hidden:
        result['keyframed_elsewhere'] = hidden
        result['hint'] = ('These clips animate their own value for these styles, which wins over the shared style. '
                          'text reset CLIP --keyframes-only makes a clip follow the shared style again.')
    return result
