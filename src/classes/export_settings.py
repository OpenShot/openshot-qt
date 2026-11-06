"""
 @file
 @brief Writer configuration shared by the export dialog and agent worker.

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
import logging
import os
import time

import openshot


log = logging.getLogger('OpenShot')


def _set_writer_option(writer, stream, name, value):
    """Safely apply a writer option, logging any unsupported option exceptions."""
    try:
        writer.SetOption(stream, name, str(value))
    except (RuntimeError, ValueError, AttributeError) as ex:
        log.debug("Failed to set writer option %s=%s: %s", name, value, ex)


def configure_writer(writer, video, audio, mode='video_audio', quality_mode=None,
                     video_options=None, audio_options=None):
    if mode in ('video_audio', 'video', 'image_sequence'):
        writer.SetVideoOptions(True, video['vcodec'],
                               openshot.Fraction(video['fps']['num'], video['fps']['den']),
                               video['width'], video['height'],
                               openshot.Fraction(video['pixel_ratio']['num'], video['pixel_ratio']['den']),
                               video['interlace'], video['topfirst'], video['video_bitrate'])
    if mode in ('video_audio', 'audio'):
        writer.SetAudioOptions(True, audio['acodec'], audio['sample_rate'], audio['channels'],
                               audio['channel_layout'], audio['audio_bitrate'])
    writer.PrepareStreams()
    if video.get('spherical'):
        writer.AddSphericalMetadata('equirectangular', 0.0, 0.0, 0.0)
    stream = openshot.AUDIO_STREAM if mode == 'audio' else openshot.VIDEO_STREAM
    _set_writer_option(writer, stream, 'muxing_preset', 'mp4_faststart')
    if mode != 'audio':
        if quality_mode in ('crf', 'cqp', 'qp'):
            _set_writer_option(writer, openshot.VIDEO_STREAM, quality_mode, str(int(video['video_bitrate'])))
        if (video.get('vcodec') or '').lower() in ('libx264', 'libx265', 'libvpx-vp9'):
            for name, value in [('g', '48'), ('allow_b_frames', '1'), ('max_b_frames', '3')]:
                _set_writer_option(writer, openshot.VIDEO_STREAM, name, value)
    for stream, values in [(openshot.VIDEO_STREAM, video_options), (openshot.AUDIO_STREAM, audio_options)]:
        for key, value in (values or {}).items():
            _set_writer_option(writer, stream, key, value)


# Setup errors (raised before Test() runs) and the stream they belong to
SETUP_ERRORS = [
    ("valid video codec", "video"),
    ("valid audio codec", "audio"),
    ("sample rate", "audio"),
    ("channel layout", "audio"),
    ("output format", "format"),
    ("AVFormatContext", "format"),
]


def describe_settings(video, audio, mode='video_audio', fmt=''):
    """A short summary for the log, i.e. 'mp4 · libx264 1920x1080 · aac 48000 Hz'."""
    parts = [fmt] if fmt else []
    if mode in ('video_audio', 'video', 'image_sequence'):
        parts.append('%s %sx%s' % (video.get('vcodec') or 'default', video.get('width'), video.get('height')))
    if mode in ('video_audio', 'audio'):
        parts.append('%s %s Hz' % (audio.get('acodec') or 'default', audio.get('sample_rate')))
    return ' · '.join(parts)


def _run_test(path, video, audio, mode, quality_mode, video_options, audio_options):
    started = time.time()
    result = {'ok': True, 'stage': '', 'message': '', 'log': [], 'elapsed_ms': 0}
    try:
        writer = openshot.FFmpegWriter(path)
        configure_writer(writer, video, audio, mode, quality_mode, video_options, audio_options)
        if hasattr(writer, 'Test'):
            result.update(json.loads(writer.Test()))
        else:
            result['ok'] = True
    except Exception as ex:  # libopenshot raises RuntimeError for its own exceptions
        message = str(ex).split(' for file ')[0].strip()
        stage = next((stage for text, stage in SETUP_ERRORS if text in message), 'header')
        result.update(ok=False, stage=stage, message=message)
    result['elapsed_ms'] = int((time.time() - started) * 1000)
    return result


def test_writer(path, video, audio, mode='video_audio', quality_mode=None,
                video_options=None, audio_options=None):
    """Try export settings without writing a file.

    The encoders (including hardware encoders) are opened, and the header is written to memory,
    so the result matches what a real export would do. Returns a dict with ok, stage ("format",
    "video", "audio", or "header" when the format rejects the pair), message, log, and elapsed_ms.
    """
    result = _run_test(path, video, audio, mode, quality_mode, video_options, audio_options)
    if result['stage'] == 'header' and mode == 'video_audio':
        # The format rejected the pair; find out which codec it can't hold
        for single, stage in (('audio', 'audio'), ('video', 'video')):
            alone = _run_test(path, video, audio, single, quality_mode, video_options, audio_options)
            result['elapsed_ms'] += alone['elapsed_ms']
            if not alone['ok']:
                result['stage'] = stage
                break
    elif result['stage'] == 'header':
        # With a single stream, the format can only be rejecting that stream's codec
        result['stage'] = 'audio' if mode == 'audio' else 'video'

    summary = describe_settings(video, audio, mode, os.path.splitext(path)[1].lstrip('.'))
    if result['ok']:
        log.info('Checking export settings: %s … OK (%d ms)', summary, result['elapsed_ms'])
    else:
        log.info('Checking export settings: %s … not supported: %s (%d ms)',
                 summary, result['message'], result['elapsed_ms'])
    return result
