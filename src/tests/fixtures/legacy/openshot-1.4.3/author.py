#!/usr/bin/env python2
"""Author a real project using the installed OpenShot 1.4.3 application.

Run inside the historical container described in README.txt, with this directory
as the working directory. This uses real constructors, media probing, the GTK
window and Project.Save; it does not synthesize pickle records or rewrite bytes.
"""
from __future__ import print_function

import locale
import os
import shutil
import sys

sys.path.insert(0, '/usr/lib/pymodules/python2.7/openshot')

import gtk
from classes import effect, info, lock, open_project, project
from windows.MainGTK import frmMain


def main():
    assert info.VERSION == '1.4.3', info.VERSION
    locale.setlocale(locale.LC_ALL, '')
    lock.check_pid(os.path.expanduser('~/.openshot'))
    gtk.gdk.threads_init()
    current = project.project()
    window = frmMain(project=current, version=info.VERSION)

    current.name = 'OpenShot 1.4.3 settings sampler'
    current.folder = os.getcwd()
    if not os.path.isdir('thumbnail'):
        os.mkdir('thumbnail')
    current.project_type = 'HD 720p 25 fps'
    current.mlt_profile = None
    seq = current.sequences[0]
    seq.name = 'Twelve second settings sampler'
    seq.length = 30.0
    seq.scale = 1.0
    seq.tick_pixels = 100
    seq.tracks = []
    for name in reversed(('Hidden track', 'Muted track', 'Animated overlay', 'Background', 'Audio bed')):
        seq.AddTrack(name, position='below')
    hidden, muted, overlay, background, audio = seq.tracks
    hidden.play_video = False
    muted.play_audio = False

    media = {}
    for name in ('red.png', 'green.png', 'blue.png', 'tone.wav', 'pattern.mp4'):
        path = os.path.abspath(os.path.join('media', name))
        result = current.project_folder.AddFile(path, ignore_image_sequences=True)
        assert result[0] == 1, (path, result)
        media[name] = current.project_folder.items[-1]
        assert media[name].name == path, media[name].name

    def add(track, label, name, position, start, end):
        return track.AddClip(label, 'Gold', position, start, end, media[name])

    red = add(overlay, 'Animated scale position opacity', 'red.png', 0.0, 0.0, 4.0)
    red.keyframes['start'].set_all(75.0, 50.0, -20.0, 10.0, 0.6)
    red.keyframes['end'].set_all(110.0, 125.0, 20.0, -10.0, 1.0)
    red.fill = False
    red.halign = 'left'
    red.valign = 'top'
    red.volume = 80.0
    red.effects.append(effect.effect('brightness', [{'start': '0.75'}, {'end': '1.25'}]))

    blue = add(overlay, 'Separate fades rotation saturation', 'blue.png', 4.0, 1.0, 5.0)
    blue.rotation = 12.0
    blue.distort = True
    blue.volume = 60.0
    blue.video_fade_in = blue.video_fade_out = True
    blue.video_fade_in_amount = 0.75
    blue.video_fade_out_amount = 1.25
    blue.audio_fade_in = blue.audio_fade_out = True
    blue.audio_fade_in_amount = 0.25
    blue.audio_fade_out_amount = 0.5
    blue.effects.append(effect.effect('frei0r.saturat0r', [{'Saturation': '0.2'}]))

    silent = add(overlay, 'Clip audio muted', 'pattern.mp4', 8.0, 1.0, 3.0)
    silent.play_audio = False
    silent.volume = 65.0
    invisible = add(overlay, 'Clip video hidden', 'pattern.mp4', 10.0, 3.0, 5.0)
    invisible.play_video = False
    invisible.volume = 20.0
    add(background, 'Green background', 'green.png', 0.0, 0.0, 12.0)
    hidden_clip = add(hidden, 'Hidden by track', 'pattern.mp4', 0.0, 0.0, 3.0)
    hidden_clip.play_audio = False
    muted_clip = add(muted, 'Muted by track', 'pattern.mp4', 8.0, 2.0, 4.0)
    muted_clip.play_video = False
    tone = add(audio, 'Tone with volume and audio fades', 'tone.wav', 0.0, 0.0, 12.0)
    tone.play_video = False
    tone.volume = 35.0
    tone.audio_fade_in = tone.audio_fade_out = True
    tone.audio_fade_in_amount = 0.5
    tone.audio_fade_out_amount = 1.5

    # An empty resource is the application's native dissolve representation.
    wipe_path = os.path.join(current.TRANSITIONS_DIR, 'wipe_left_to_right.svg')
    assert os.path.isfile(wipe_path), wipe_path
    shutil.copyfile(wipe_path, 'media/wipe.svg')
    wipe = overlay.AddTransition('Reverse wipe', 3.5, 1.0, os.path.abspath('media/wipe.svg'))
    wipe.reverse = True
    wipe.softness = 0.15
    dissolve = overlay.AddTransition('Soft dissolve', 7.5, 0.5, '')
    dissolve.softness = 0.7
    for name, position in (('Scale animation', 0.0), ('Fades and effects', 4.0),
                           ('Mute and hide', 8.0)):
        seq.AddMarker(name, position)

    current.fps()  # Populate the profile before GenerateXML writes its header.
    current.GenerateXML('reference.mlt')
    window.refresh()
    current.Save(os.path.join(current.folder, 'settings-sampler.osp'))
    print('SAVED with OpenShot', info.VERSION)
    print('Profile:', current.project_type, 'FPS:', current.fps())
    print('Files:', len(current.project_folder.items), 'Tracks:', len(seq.tracks),
          'Clips:', sum(len(track.clips) for track in seq.tracks))
    # Reopen only the project this process just authored, using 1.4.3's own
    # Open command. Production code/tests use the restricted modern reader.
    open_project.open_project(current, os.path.join(current.folder, 'settings-sampler.osp'))
    loaded = window.project
    assert loaded.project_type == 'HD 720p 25 fps'
    assert len(loaded.project_folder.items) == 5
    assert len(loaded.sequences[0].tracks) == 5
    loaded_red = loaded.sequences[0].tracks[2].clips[0]
    assert loaded_red.keyframes['end'].width == 125.0
    assert loaded_red.effects[0].service == 'brightness'
    print('REOPENED successfully in OpenShot', info.VERSION)
    # The application starts preview and thumbnail threads; exit after Save has
    # completed rather than waiting indefinitely in its interactive event loop.
    sys.stdout.flush()
    os._exit(0)


if __name__ == '__main__':
    main()
