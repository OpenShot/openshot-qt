"""Bounded inspection artifacts and snapshot export jobs."""
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

import openshot
from qt_api import QImage, QPainter, QColor, QFont
from .protocol import CommandError, MAX_SAMPLES, cli_command, dimensions, session_dir
from .service import existing, finite, output_path


def snapshot(service):
    # Project data is authoritative, and contains absolute runtime media paths.
    return copy.deepcopy(service.app.project._data)


def make_timeline(data):
    fps = data['fps']
    timeline = openshot.Timeline(data['width'], data['height'], openshot.Fraction(fps['num'], fps['den']),
                                 data['sample_rate'], data['channels'], data['channel_layout'])
    timeline.SetJson(json.dumps(data))
    timeline.Open()
    return timeline


def duration(data):
    return max([c.get('position', 0) + c.get('end', 0) - c.get('start', 0) for c in data.get('clips', [])] or [0])


def timecode(seconds):
    millis = round(seconds * 1000)
    hours, rest = divmod(millis, 3600000)
    minutes, rest = divmod(rest, 60000)
    seconds, millis = divmod(rest, 1000)
    return '{:02d}:{:02d}:{:02d}.{:03d}'.format(hours, minutes, seconds, millis)


def image_format():
    return getattr(QImage, 'Format_ARGB32', None) or QImage.Format.Format_ARGB32


def inspect_command(service, method, p):
    output = output_path(p['output'], '.png')
    if method == 'timeline.view':
        return timeline_view(service, p, output)
    is_strip = method.endswith('.strip')
    width, height = p.get('width', 160 if is_strip else 320), p.get('height', 90 if is_strip else 180)
    dimensions(width, height)
    if is_strip:
        start, end = finite(p.get('start', 0), 'start'), finite(p['end'], 'end')
        count, columns = p.get('count', 8), p.get('columns', 4)
        if not 1 <= count <= MAX_SAMPLES or not 1 <= columns <= MAX_SAMPLES or end <= start:
            raise CommandError('invalid_range', 'Require end > start and count/columns between 1 and 64.')
        columns = min(count, columns)
        canvas_width, canvas_height = columns * width, math.ceil(count/columns) * (height + 24)
        dimensions(canvas_width, canvas_height)
    else:
        frame_number = p['frame']
        if not isinstance(frame_number, int) or frame_number < 1:
            raise CommandError('invalid_frame', 'Frame numbers are integers starting at 1.')
    if method.startswith('file.'):
        file = service.obj('file', p['id'])
        reader = openshot.Clip.CreateReader(existing(file.absolute_path()), False)
        reader.Open()
        fps = reader.info.fps.num / reader.info.fps.den
        length = float(reader.info.duration)
        if file.data.get('media_type') == 'image':
            length = float('inf')
    else:
        data = snapshot(service)
        fps = service.fps()
        length = duration(data)
        if length <= 0:
            raise CommandError('empty_timeline', 'Add a clip before rendering timeline frames.')
        reader = make_timeline(data)
        reader.SetMaxSize(width, height)
    try:
        if is_strip:
            if end > length + 1e-6:
                raise CommandError('out_of_range', 'Requested range exceeds source/timeline duration: ' + str(length))
            frames = [int(math.floor((start + (end-start)*i/count)*fps)) + 1 for i in range(count)]
        else:
            frames = [frame_number]
        if any((f - 1)/fps >= length for f in frames):
            raise CommandError('out_of_range', 'Requested frame is beyond the source/timeline.')
        tiles = []
        with tempfile.TemporaryDirectory(prefix='openshot-inspect-') as directory:
            if is_strip:
                canvas = QImage(canvas_width, canvas_height, image_format())
                canvas.fill(QColor('#171b21'))
                painter = QPainter(canvas)
            try:
                for i, frame_number in enumerate(frames):
                    target = str(Path(directory) / (str(i) + '.png')) if is_strip else output
                    frame = reader.GetFrame(frame_number)
                    frame.Thumbnail(target, width, height, '', '', '#000000', False, 'png', 90 if is_strip else -1, 0.0, openshot.SCALE_FIT)
                    if not Path(target).is_file():
                        raise CommandError('render_failed', 'Renderer did not produce an image.')
                    seconds = (frame_number - 1)/fps
                    tile = {'frame': frame_number, 'seconds': seconds, 'timecode': timecode(seconds)}
                    if is_strip:
                        x, y = (i % columns)*width, (i // columns)*(height+24)
                        painter.drawImage(x, y, QImage(target))
                        painter.setPen(QColor('white'))
                        painter.drawText(x+5, y+height+17, '{}  f{}'.format(tile['timecode'], frame_number))
                        tile.update(x=x, y=y, width=width, height=height)
                    tiles.append(tile)
            finally:
                if is_strip:
                    painter.end()
            if is_strip and not canvas.save(output, 'PNG'):
                raise CommandError('render_failed', 'Cannot save ' + output)
        return {'path': output, 'image_bytes': Path(output).stat().st_size,
                'width': canvas_width if is_strip else width,
                'height': canvas_height if is_strip else height, 'fps': fps, 'tiles': tiles,
                'timebase': 'source' if method.startswith('file.') else 'timeline'}
    finally:
        reader.Close()


def timeline_view(service, p, output):
    from windows.views.timeline_backend.qwidget.snapshot import render_timeline_snapshot
    start = finite(p.get('start', 0), 'start')
    end = finite(p.get('end', max(start + 1, duration(snapshot(service)))), 'end')
    if end <= start:
        raise CommandError('invalid_range', 'end must be greater than start.')
    width = p.get('width', 1280)
    height = p.get('height')
    dimensions(width, height or 1)
    if width < 320:
        raise CommandError('image_limit', 'Timeline width must be at least 320 pixels for track names and ruler.')
    zoom = p.get('pixels_per_second')
    if zoom is not None:
        finite(zoom, 'pixels_per_second', 0.001)
    try:
        return render_timeline_snapshot(output, start=start, end=end, width=width,
                                        height=height, pixels_per_second=zoom,
                                        all_tracks=p.get('all_tracks', False),
                                        track_size=p.get('track_size', 'relaxed'),
                                        mode=p.get('mode', 'auto'),
                                        track_label_width=p.get('track_label_width', 220),
                                        validate_size=dimensions, max_thumbnails=MAX_SAMPLES)
    except ValueError as exc:
        raise CommandError('image_limit', str(exc))


def export_command(service, operation, p):
    from .exporting import resolve, public, catalogue
    if operation in ('preset.list', 'preset.get', 'capabilities'):
        return catalogue('export.'+operation, p)
    if operation == 'list':
        return [export_command(service, 'status', {'job_id': job_id}) for job_id in reversed(list(service.jobs))]
    if operation in ('start', 'validate'):
        spec = resolve(service, p)
        if operation == 'validate':
            return public(spec)
        output = spec['output']
        job_id = uuid.uuid4().hex
        directory = session_dir() / 'jobs' / job_id
        directory.mkdir(parents=True, mode=0o700)
        spec.update(job_id=job_id, revision=service.app.updates.data_version)
        (directory/'spec.json').write_text(json.dumps(spec))
        status = {'job_id': job_id, 'state': 'queued', 'progress': 0, 'output': output, 'revision': spec['revision'], 'mode': spec['config']['mode'], 'profile': spec['profile'], 'config': spec['config']}
        (directory/'status.json').write_text(json.dumps(status))
        # Reserve the output before starting a worker; never overwrite someone else's file.
        if spec['config']['mode'] == 'image_sequence':
            Path(output).mkdir(mode=0o700)
        else:
            fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        try:
            with (directory/'worker.log').open('wb') as log:
                process = subprocess.Popen(cli_command('--_export-worker', str(directory)), stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        except Exception:
            remove_export_output(output)
            raise
        service.jobs[job_id] = {'directory': directory, 'process': process, 'output': output}
        return status
    job = service.jobs.get(p['job_id'])
    if not job:
        raise CommandError('not_found', 'Job is not owned by this session.')
    if operation == 'cancel' and job['process'].poll() is None:
        (job['directory']/'cancel').touch()
    result = json.loads((job['directory']/'status.json').read_text())
    if job['process'].poll() is not None and result['state'] in ('queued', 'running'):
        result.update(state='failed', error='Worker exited unexpectedly; see ' + str(job['directory']/'worker.log'))
        remove_export_output(job['output'])
    return result


def remove_export_output(path):
    path = Path(path)
    if path.is_dir():
        # Reserved image-sequence directories are empty until completion.
        try:
            path.rmdir()
        except OSError:
            pass
    else:
        path.unlink(missing_ok=True)
