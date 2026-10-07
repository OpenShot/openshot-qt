"""Effect discovery from the installed engine and OpenShot's existing user guide."""
import difflib
import json
from pathlib import Path
import re

import openshot
from .protocol import CommandError


def normalize(name):
    return re.sub('[^a-z0-9]', '', name.lower())


def slug(name):
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', name).lower()


def effect_types():
    return [dict(item, alias=slug(item['class_name']),
                 describe='openshot-cli effects ' + slug(item['class_name']) + ' help')
            for item in json.loads(openshot.EffectInfo.Json())]


def resolve_effect(name):
    catalog = effect_types()
    for item in catalog:
        if normalize(name) in (normalize(item['class_name']), normalize(item['name'])):
            return item
    choices = {normalize(item['class_name']): item['class_name'] for item in catalog}
    closest = difflib.get_close_matches(normalize(name), choices, n=1)
    hint = ' Did you mean {}?'.format(choices[closest[0]]) if closest else ''
    raise CommandError('unknown_effect', 'Unknown effect type {!r}.{} Run openshot-cli effects list.'.format(name, hint))


def describe_effect(name, property_name=None):
    item = resolve_effect(name)
    effect = openshot.EffectInfo().CreateEffect(item['class_name'])
    defaults = json.loads(effect.Json())
    properties = json.loads(effect.PropertiesJSON(1))
    guide_path = Path(__file__).resolve().parents[2] / 'resources' / 'agent-effects.json'
    guide = json.loads(guide_path.read_text())['effects']
    details = guide.get(normalize(item['name']), guide.get(normalize(item['class_name']), {}))
    property_docs = details.get('properties', {})
    exposed = {}
    for key, meta in properties.items():
        if key not in defaults:
            continue
        exposed[key] = {'name': meta.get('name', key), 'type': meta.get('type'),
                        'description': re.sub(r'^\([^\n]*?\)\s*', '', property_docs.get(key, '')) or meta.get('memo') or meta.get('name', key),
                        'default': defaults[key], 'keyframe': bool(meta.get('keyframe')),
                        'readonly': bool(meta.get('readonly')) or key in ('id', 'duration', 'type'),
                        'suggested_range': {'min': meta.get('min'), 'max': meta.get('max')},
                        'choices': [{'name': c['name'], 'value': c['value']} for c in meta.get('choices', [])]}
    if property_name:
        if property_name not in exposed:
            from .validation import unknown
            unknown('property', property_name, exposed)
        return {'class_name': item['class_name'], 'property': property_name, **exposed[property_name]}
    notes = [
        'Attach with effects add CLIP_ID TYPE; use the returned effect ID with effects set/properties/remove.',
        'Scalars set a constant keyframed property; effects keyframe set edits an individual point.',
        'Suggested ranges describe GUI controls, not universal engine bounds. Enum choices are validated.',
        'Effects operate on the parent clip; they do not automatically process the mixed timeline audio.',
    ]
    examples = ['openshot-cli effects add CLIP_ID ' + item['alias'],
                'openshot-cli effects properties EFFECT_ID']
    if item['class_name'] == 'AudioVisualization':
        notes += [
            'Use on a clip containing audio for music visualizers, podcast audiograms, or reactive overlays.',
            'Keep clip has_audio on/auto so audio samples are available. Put the visualizer clip above the background video.',
            'Choose background=Transparent for an overlay or Source to retain the source image. The native default is Source.',
            'Keep clip video enabled (has_video=1) when rendering a visualizer; do not leave the clip in audio-only mode.',
            'This draws animated visuals into exported video. It is different from a timecoded waveform inspection image.',
        ]
        transparent = next(c['value'] for c in properties['background']['choices'] if c['name'] == 'Transparent')
        spectrum = next(c['value'] for c in properties['visualization_type']['choices'] if c['name'] == 'Spectrum')
        examples += ['openshot-cli clip set CLIP_ID --json \'{"has_audio":1,"has_video":1}\'',
                     "openshot-cli effects set EFFECT_ID --json '{}'".format(json.dumps(
                         {'visualization_type': spectrum, 'background': transparent, 'intensity': 1.5}, separators=(',', ':')))]
    if item['class_name'] in ('Tracker', 'ObjectDetection', 'Stabilizer'):
        notes.append('This effect can require analysis data or external resources; the MVP CLI does not expose the GUI analysis workflow.')
    return {**item, 'details': details.get('description') or item['description'],
            'usage_notes': notes, 'examples': examples, 'properties': exposed,
            'documentation': 'https://www.openshot.org/static/files/user-guide/effects.html',
            'description_source': 'OpenShot user guide (doc/effects.rst); properties/defaults from installed libopenshot'}
