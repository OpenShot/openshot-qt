"""
 @file
 @brief Render the real timeline widget without changing the interactive viewport.

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
import time
from collections import OrderedDict
from pathlib import Path
import tempfile

from classes.waveform_cache import samples as waveform_samples
from qt_api import QImage, QPixmap
from classes.app import get_app
from classes.query import File, Clip, Transition
from classes.thumbnail import GenerateThumbnail
from . import TimelineWidget

_THUMBNAILS = OrderedDict()
_MAX_THUMBNAIL_BYTES = 32 * 1024 * 1024
_WAVEFORMS = OrderedDict()
_MAX_SOURCE_SECONDS = 600
_MAX_REQUEST_SECONDS = 1200
_MAX_CACHE_SAMPLES = 240000


def snapshot_clips(mode, start, end, fps, clip_ids=None):
    """Attach bounded, private waveform envelopes to snapshot-only Query clones.

    Source extraction and envelope display use the same engine and Qt painter as
    the GUI. No Query.save(), update listeners, or project UI fields are touched.
    clip_ids optionally limits waveform generation to those clips.
    """
    import openshot
    from classes.waveform import ABSOLUTE_WAVEFORM_FORMAT
    metrics = {"generated_sources": 0, "cache_hits": 0, "clips": 0,
               "decoded_source_seconds": 0, "mapped_samples": 0, "extracted_samples": 0, "extraction_samples_per_second": 200,
               "semantics": "Source peak/RMS envelope with clip volume and time curves; before audio effects and mixing."}
    began = time.monotonic()
    clips = copy.deepcopy(list(Clip.filter()))
    files = {file.id: file for file in File.filter()}
    for clip in clips:
        data = clip.data
        if mode == "thumbnails":
            data.setdefault("ui", {}).pop("audio_data", None)
            continue
        position = data.get("position", 0)
        if clip_ids is not None and clip.id not in clip_ids:
            continue
        if mode != "waveforms" or position >= end or position + data.get("end", 0) - data.get("start", 0) <= start:
            continue
        file = files.get(data.get("file_id"))
        if not file or not file.data.get("has_audio"):
            continue
        metrics["clips"] += 1
        ui = data.setdefault("ui", {})
        # Existing clip envelopes have no provenance for volume/time edits.
        # Rebuild from raw source/file cache so explicit inspection is current.
        rate = 200
        channel = int(data.get("channel_filter", {}).get("Points", [{"co": {"Y": -1}}])[0]["co"]["Y"])
        path = Path(file.absolute_path())
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size, rate, channel)
        file_ui = file.data.get("ui", {})
        cached_peaks = waveform_samples(file_ui.get("audio_data"))
        if channel == -1 and len(cached_peaks) > 1:
            from classes.waveform import waveform_sample_rate, waveform_data_format
            peaks = cached_peaks
            rms = waveform_samples(file_ui.get("audio_data_rms"))
            rate = waveform_sample_rate(file_ui)
            data_format = waveform_data_format(file_ui)
            metrics["cache_hits"] += 1
        elif key in _WAVEFORMS:
            peaks, rms = _WAVEFORMS[key]
            _WAVEFORMS.move_to_end(key)
            data_format = ABSOLUTE_WAVEFORM_FORMAT
            metrics["cache_hits"] += 1
        else:
            seconds = float(file.data.get("duration", 0))
            if seconds <= 0 or seconds > _MAX_SOURCE_SECONDS or metrics["decoded_source_seconds"] + seconds > _MAX_REQUEST_SECONDS:
                raise ValueError("Waveform extraction limit for file {}: {} source seconds. Maximum {} seconds per uncached source and {} per request. Extraction decodes the whole source, so a narrower viewport does not shorten a source. Generate/cache its waveform in the GUI first, use shorter media, or use --mode thumbnails.".format(file.id, seconds, _MAX_SOURCE_SECONDS, _MAX_REQUEST_SECONDS))
            reader = openshot.FFmpegReader(str(path))
            reader.Open()
            try:
                envelope = openshot.AudioWaveformer(reader).ExtractSamples(channel, rate, False)
                vectors = envelope.vectors()
                peaks, rms = list(vectors[0]), list(vectors[1])
                envelope.clear()
            finally:
                reader.Close()
            if len(peaks) > _MAX_CACHE_SAMPLES:
                raise ValueError("Waveform extraction exceeded the {} sample limit.".format(_MAX_CACHE_SAMPLES))
            _WAVEFORMS[key] = (peaks, rms)
            while sum(len(value[0]) for value in _WAVEFORMS.values()) > _MAX_CACHE_SAMPLES:
                _WAVEFORMS.popitem(last=False)
            metrics["generated_sources"] += 1
            metrics["extracted_samples"] += len(peaks)
            metrics["decoded_source_seconds"] += seconds
            data_format = ABSOLUTE_WAVEFORM_FORMAT
        if not peaks:
            continue
        volume = openshot.Keyframe(1.0)
        volume.SetJson(json.dumps(data["volume"]))
        enabled = openshot.Keyframe(-1.0)
        if data.get("has_audio"):
            enabled.SetJson(json.dumps(data["has_audio"]))
        timing = openshot.Keyframe(1.0)
        timing.SetJson(json.dumps(data["time"]))
        # Mirror the GUI envelope mapping, whose arrays use source-time origin 0.
        # Keep the entire envelope so the native painter handles trim and viewport.
        count = max(len(peaks), int(math.ceil(data.get("end", 0) * rate)))
        if count + metrics["mapped_samples"] > _MAX_CACHE_SAMPLES:
            raise ValueError("Waveform snapshot exceeds {} generated samples while processing clip {} ({} already generated, {} additional). Use fewer clips or shorter media.".format(_MAX_CACHE_SAMPLES, clip.id, metrics["mapped_samples"], count))
        metrics["mapped_samples"] += count
        adjusted, adjusted_rms = [], []
        for index in range(count):
            frame_position = index / rate * fps
            frame = math.floor(frame_position) + 1
            source = index
            if timing.GetCount() > 1:
                # Frames are 1-based, samples 0-based. Preserve the fractional
                # position inside a frame when traversing the envelope.
                mapped = timing.GetValue(frame)
                delta = timing.GetValue(frame + 1) - mapped
                source = round((mapped - 1 + delta * (frame_position - (frame - 1))) / fps * rate)
            gain = 0 if enabled.GetInt(frame) == 0 else volume.GetValue(frame)
            if source < 0 or source >= len(peaks):
                adjusted.append(0.0)
                adjusted_rms.append(0.0)
                continue
            adjusted.append(peaks[source] * gain)
            adjusted_rms.append(rms[source] * abs(gain) if source < len(rms) else 0.0)
        ui.update(audio_data=adjusted, audio_data_rms=adjusted_rms,
                  audio_data_rate=rate, audio_data_format=data_format)
    metrics["elapsed_seconds"] = round(time.monotonic() - began, 6)
    return clips, metrics



class SnapshotThumbnails:
    """Collect the painters' visible requests, then resolve them synchronously.

    No HTTP server, UI event pumping, or project mutation is needed. Existing disk
    thumbnails are still reused by ClipPainter before it reaches this provider.
    """
    def __init__(self, widget):
        self.widget = widget
        self.requests = {}
        self.metrics = {"requested": 0, "generated": 0, "cache_hits": 0, "reader_opens": 0}

    def request_thumbnail(self, clip_id, file_id, frame, generation):
        self.requests[(clip_id, frame)] = (file_id, generation)

    def clear_pending(self):
        self.requests.clear()

    def shutdown(self):
        self.clear_pending()

    def resolve(self, directory, maximum):
        import openshot
        from classes.thumbnail import (GetThumbDeviceScale, THUMBNAIL_DECODE_SCALE,
                                       THUMBNAIL_CACHE_VERSION, GenerateThumbnailFromFrame)
        began = time.monotonic()
        self.metrics['requested'] = len(self.requests)
        if len(self.requests) > maximum:
            raise ValueError('Timeline needs {} thumbnails; maximum is {}. Narrow the range, reduce width, or use fewer tracks.'.format(len(self.requests), maximum))
        files = {f.id: f for f in File.filter()}
        scale = GetThumbDeviceScale()
        readers = {}
        try:
            # Per-source sequential frame order reduces decoder seeks. Multiple
            # clips using a source/frame share one cached pixmap.
            for index, ((clip_id, frame), (file_id, _generation)) in enumerate(sorted(self.requests.items(), key=lambda item: (str(item[1][0]), item[0][1]))):
                file = files.get(file_id)
                path = str(Path(directory) / '{}.png'.format(index))
                pixmap = QPixmap()
                if file:
                    source = file.absolute_path()
                    try:
                        stat = Path(source).stat()
                        key = (source, stat.st_mtime_ns, stat.st_size, frame, 320, 180, scale, THUMBNAIL_CACHE_VERSION)
                    except OSError:
                        key = None
                    if key is not None and key in _THUMBNAILS:
                        pixmap = _THUMBNAILS[key]
                        _THUMBNAILS.move_to_end(key)
                        self.metrics['cache_hits'] += 1
                    else:
                        try:
                            if source not in readers:
                                reader = openshot.Clip.CreateReader(source, False)
                                if not reader:
                                    raise RuntimeError('No reader available for thumbnail generation')
                                readers[source] = reader
                                if hasattr(reader, 'SetMaxDecodeSize'):
                                    reader.SetMaxDecodeSize(round(320*scale*THUMBNAIL_DECODE_SCALE), round(180*scale*THUMBNAIL_DECODE_SCALE))
                                reader.Open()
                                self.metrics['reader_opens'] += 1
                            GenerateThumbnailFromFrame(readers[source].GetFrame(frame), path, 320, 180, '', '')
                        except RuntimeError:
                            # Existing helper retries with inspection and renders
                            # the normal missing-media placeholder when needed.
                            GenerateThumbnail(source, path, frame, 320, 180, '', '')
                        pixmap = QPixmap(path)
                        self.metrics['generated'] += 1
                        if key is not None and not pixmap.isNull():
                            _THUMBNAILS[key] = pixmap
                            while sum(p.width()*p.height()*4 for p in _THUMBNAILS.values()) > _MAX_THUMBNAIL_BYTES:
                                _THUMBNAILS.popitem(last=False)
                self.widget.clip_painter.thumb_cache[(clip_id, frame)] = pixmap
        finally:
            for reader in readers.values():
                if reader:
                    try:
                        reader.Close()
                    except RuntimeError:
                        pass
        self.widget.clip_painter.clear_render_cache()
        self.metrics['elapsed_seconds'] = round(time.monotonic()-began, 6)


def render_timeline_snapshot(output, *, start, end, width=1280, height=None,
                             pixels_per_second=None, all_tracks=False,
                             track_size='relaxed', track_label_width=220, mode='auto',
                             validate_size=None, max_thumbnails=64):
    """Return a PNG plus exact viewport geometry from the editor's own painters."""
    app = get_app()
    widget = TimelineWidget(snapshot=True)
    try:
        live = getattr(app.window, 'timeline', None)
        if live and hasattr(live, '_base_theme'):
            widget.apply_theme(live._base_theme)
            widget.setFont(live.font())
            widget.thumbnail_style = live.thumbnail_style
        else:
            # Reuse the same concrete timeline theme classes as the GUI, without
            # applying the surrounding main-window stylesheet or creating docks.
            theme_name = app.get_settings().get('theme')
            if theme_name == 'Cosmic Dusk':
                from themes.cosmic.styles import CosmicDuskTimelineTheme
                widget.apply_theme(CosmicDuskTimelineTheme())
            elif theme_name == 'Retro':
                from themes.humanity.styles import RetroTimelineTheme
                widget.apply_theme(RetroTimelineTheme())
            else:
                from themes.humanity.styles import HumanityDarkTimelineTheme
                widget.apply_theme(HumanityDarkTimelineTheme())
        if not 140 <= track_label_width <= 512:
            raise ValueError('Track label width must be between 140 and 512 pixels.')
        if mode not in ("auto", "thumbnails", "waveforms"):
            raise ValueError("Timeline mode must be auto, thumbnails, or waveforms.")
        widget.set_track_size(track_size)
        widget.track_name_width = track_label_width
        used = {item.data.get('layer') for item in Clip.filter() + Transition.filter()}
        widget.visible_track_numbers = None if all_tracks else used
        widget.geometry.mark_dirty()
        widget.geometry.ensure()
        track_count = len(widget.geometry.track_list)
        if pixels_per_second is not None:
            width = math.ceil((end-start)*pixels_per_second + widget.track_name_width + widget.scroll_bar_thickness)
        if height is None:
            height = math.ceil(widget.ruler_height + widget.track_margin_top +
                               max(1, track_count)*(widget.track_height+widget.track_gap) + widget.scroll_bar_thickness)
        if validate_size:
            validate_size(width, height)
        if width < widget.track_name_width + 32 or height < widget.ruler_height + widget.scroll_bar_thickness + 1:
            raise ValueError('Timeline dimensions are too small for its native ruler and track headers.')
        widget.resize(width, height)
        # Polish and deliver only this widget's pending resize, without processing
        # GUI events or changing the human editor's zoom/scroll/selection.
        widget.ensurePolished()
        viewport = width-widget.track_name_width-widget.scroll_bar_thickness
        pps = viewport/(end-start)
        widget.zoom_factor = (app.project.get('tick_pixels') or 100)/pps
        widget._project_duration_override = max(end, widget._furthest_timeline_edge(), 1)
        timeline_width = max(viewport, widget._project_duration_override*pps)
        widget.scrollbar_position[0] = start*pps/timeline_width
        widget.current_frame = round(start*widget.fps_float)+1
        widget.geometry.mark_dirty()
        widget.geometry.ensure()
        widget._snapshot_clips, waveform_metrics = snapshot_clips(mode, start, end, widget.fps_float)
        widget.geometry.mark_dirty()
        widget.geometry.ensure()
        provider = SnapshotThumbnails(widget)
        widget.thumbnail_manager = provider
        image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        widget.render(image)
        # render() delivers a pending resize; restore the explicitly requested
        # viewport in case any resize bookkeeping adjusted it.
        widget.delayed_resize_timer.stop()
        widget.zoom_factor = (app.project.get('tick_pixels') or 100)/pps
        widget.scrollbar_position[0] = start*pps/timeline_width
        widget.geometry.mark_dirty()
        widget.geometry.ensure()
        with tempfile.TemporaryDirectory(prefix='openshot-timeline-') as directory:
            provider.resolve(directory, max_thumbnails)
            widget.render(image)
        if not image.save(output, 'PNG'):
            raise OSError('Cannot save timeline PNG: ' + output)
        items = []
        for rect, obj, _selected, kind in widget.geometry.iter_items():
            items.append({'id': obj.id, 'kind': kind, 'x': rect.x(), 'y': rect.y(),
                          'width': rect.width(), 'height': rect.height(),
                          'file_id': obj.data.get('file_id'), 'layer': obj.data.get('layer'),
                          'position': obj.data.get('position'), 'source_start': obj.data.get('start'),
                          'source_end': obj.data.get('end'),
                          'visible_timeline_start': max(start, obj.data.get('position', 0)),
                          'visible_timeline_end': min(end, obj.data.get('position', 0) + obj.data.get('end', 0) - obj.data.get('start', 0)),
                          'timeline_end': obj.data.get('position', 0) + obj.data.get('end', 0) - obj.data.get('start', 0)})
        return {'path': output, 'image_bytes': Path(output).stat().st_size,
                'renderer': 'qwidget', 'width': width, 'height': height,
                'start': start, 'end': end, 'pixels_per_second': pps, 'mode': mode,
                'waveforms': waveform_metrics,
                'tracks': [t.data['number'] for t in widget.geometry.track_list],
                'track_labels': {t.data['number']: widget._track_display_label(t) for t in widget.geometry.track_list},
                'items': items, 'generated_thumbnails': provider.metrics['generated'],
                'thumbnails': provider.metrics}
    finally:
        widget.close()
        widget.deleteLater()
