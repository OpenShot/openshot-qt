"""Reproduce benign 1.x-format fixtures with stable identities and relative media.

Run with PYTHONPATH=src python3 src/tests/fixtures/legacy/generate.py from repo root.
Uses the bundled 1.x record classes, without running their constructors (some
legacy constructors assume GTK/old package imports). No executable payloads.
"""
import importlib
import pickle
from pathlib import Path
import sys

folder = Path(__file__).resolve().parent
modules = ('project', 'sequences', 'track', 'clip', 'keyframe', 'files', 'transition', 'effect', 'marker')
classes = {}
for name in modules:
    module = importlib.import_module('classes.legacy.openshot.classes.' + name)
    alias = 'classes.' + name
    sys.modules[alias] = module
    for key, value in vars(module).items():
        if isinstance(value, type) and value.__module__ == module.__name__:
            value.__module__ = alias
            classes[key] = value


def record(kind, **fields):
    result = object.__new__(classes[kind])
    result.__dict__.update(fields)
    return result


project = record('project', name='Legacy compatibility fixture', sequences=[])
project.project_folder = record('OpenShotFolder', items=[], project=project, queue=[])
media = record('OpenShotFile', name='legacy.ppm', unique_id='F1', project=project)
project.project_folder.items.append(media)
seq = record('sequence', name='Sequence 1', project=project, tracks=[], markers=[])
project.sequences.append(seq)
track = record('track', name='Track 1', parent=seq, clips=[], transitions=[])
seq.tracks.append(track)
clip = record('clip', name='Legacy image', file_object=media, parent=track,
              unique_id='C1', start_time=1.0, end_time=4.0, position_on_track=2.0,
              volume=75.0, video_fade_in=True, video_fade_out=True,
              audio_fade_in=True, audio_fade_out=True,
              video_fade_in_amount=0.5, video_fade_out_amount=0.5,
              audio_fade_in_amount=0.5, audio_fade_out_amount=0.5,
              keyframes={'start': record('keyframe', frame=0, alpha=1.0)},
              effects=[record('effect', service='brightness', paramaters=[])])
track.clips.append(clip)
seq.markers.append(record('marker', name='Café 日本語', position_on_track=2.0, parent=seq))
track.transitions.append(record('transition', name='Dissolve', parent=track,
                                position_on_track=2.0, length=1.0, softness=0.3,
                                resource='', reverse=False))
# Exercise nested folders and shared/cyclic references without capabilities.
project.project_folder.items.append(record('OpenShotFolder', items=[], project=project))
for protocol in (0, 2):
    (folder / ('project-v1-protocol%d.osp' % protocol)).write_bytes(pickle.dumps(project, protocol=protocol))
(folder / 'legacy.ppm').write_text('P3\n2 2\n255\n255 0 0  0 255 0\n0 0 255  255 255 255\n')

# Python 2 old-style instances use INST rather than NEWOBJ/_reconstructor.
# A tiny fixture writer emits only literals, containers, memo references and
# record state; this exercises that historical representation without Python 2.
memo = {}
use_obj = False


def old_style(value):
    if value is None:
        return b'N'
    if type(value) is bool:
        return b'I01\n' if value else b'I00\n'
    if type(value) in (int, float):
        return (('I' if type(value) is int else 'F') + repr(value) + '\n').encode('ascii')
    if type(value) is str:
        return b'V' + value.encode('raw-unicode-escape') + b'\n'
    if id(value) in memo:
        return ('g%d\n' % memo[id(value)]).encode('ascii')
    index = len(memo)
    memo[id(value)] = index
    put = ('p%d\n' % index).encode('ascii')
    if type(value) is list:
        return b'(l' + put + b''.join(old_style(item) + b'a' for item in value)
    if type(value) is dict:
        return b'(d' + put + b''.join(old_style(key) + old_style(item) + b's' for key, item in value.items())
    cls = type(value)
    prefix = ('(c%s\n%s\no' if use_obj else '(i%s\n%s\n') % (cls.__module__, cls.__name__)
    return prefix.encode('ascii') + put + old_style(vars(value)) + b'b'


(folder / 'project-v1-inst.osp').write_bytes(old_style(project) + b'.')

# Early 1.x files also use OBJ and shared audio/video fade durations, as found
# in a real historical 1.x project. Reproduce that schema without customer data.
use_obj = True
memo.clear()
for stream in ('video', 'audio'):
    delattr(clip, stream + '_fade_in_amount')
    delattr(clip, stream + '_fade_out_amount')
    setattr(clip, stream + '_fade_amount', 0.25 if stream == 'audio' else 0.5)
(folder / 'project-v1-obj.osp').write_bytes(old_style(project) + b'.')

# An audio-only fade must not depend on video fade durations being present.
clip.video_fade_in = False
clip.video_fade_out = False
memo.clear()
(folder / 'project-v1-audio-only.osp').write_bytes(old_style(project) + b'.')
