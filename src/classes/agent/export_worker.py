"""
 @file
 @brief Isolated export worker. Receives only an immutable project snapshot.

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
import os
from pathlib import Path
import sys
import shutil

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import openshot
from qt_api import QApplication
from classes.agent.render import make_timeline


def main(directory):
    _app = QApplication([])  # Keep Qt alive throughout rendering.
    directory = Path(directory)
    spec = json.loads((directory/'spec.json').read_text())
    status = json.loads((directory/'status.json').read_text())
    output = Path(spec['output'])
    config = spec['config']
    sequence = config['mode'] == 'image_sequence'
    partial = output.with_name('.' + output.stem + '.' + spec['job_id'] + ('.partial' if sequence else '.partial.'+config['format']))
    timeline = writer = None

    def report(state, **values):
        status.update(state=state, **values)
        temporary = directory/'status.tmp'
        temporary.write_text(json.dumps(status))
        temporary.replace(directory/'status.json')

    try:
        data = spec['project']
        settings = openshot.Settings.Instance()
        for name, attribute in [('encoder_device', 'HW_EN_DEVICE_SET'), ('decoder_device', 'HW_DE_DEVICE_SET'), ('hardware_decoder', 'HARDWARE_DECODER')]:
            if name in config['hardware']:
                setattr(settings, attribute, config['hardware'][name])
        if 'threads' in config:
            settings.FF_THREADS = config['threads']
        timeline = make_timeline(data)
        timeline.SetMaxSize(data['width'], data['height'])
        timeline.ApplyMapperToClips()
        fps = data['fps']
        if sequence:
            partial.mkdir(mode=0o700)
        else:
            from classes.export_settings import configure_writer
            writer = openshot.FFmpegWriter(str(partial))
            configure_writer(writer, spec['video'], spec['audio'], config['mode'], config['quality_mode'],
                             config['video_options'], config['audio_options'])
            writer.Open()
        report('running')
        total = spec['end']-spec['start']+1
        for index, frame in enumerate(range(spec['start'], spec['end']+1)):
            if (directory/'cancel').exists():
                report('cancelled')
                return 0
            native_frame = timeline.GetFrame(frame)
            if sequence:
                native_frame.Save(str(partial / ('frame-{:06d}.'.format(frame)+config['format'])), 1.0, config['format'], -1)
            else:
                writer.WriteFrame(native_frame)
            if index % 15 == 0:
                report('running', progress=(index+1)/total, frames_written=index+1, total_frames=total)
        if writer is not None:
            writer.Close()
            writer = None
        if sequence:
            output.rmdir()
        partial.replace(output)
        report('completed', progress=1, frames_written=total, total_frames=total,
               width=data['width'], height=data['height'], fps=fps)
        return 0
    except Exception as exc:
        report('failed', error=str(exc))
        return 1
    finally:
        if writer is not None:
            writer.Close()
        if timeline is not None:
            timeline.Close()
        if status['state'] != 'completed':
            from classes.agent.render import remove_export_output
            remove_export_output(output)
            if partial.is_dir():
                shutil.rmtree(partial)
            else:
                partial.unlink(missing_ok=True)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
