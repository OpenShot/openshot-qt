"""
 @file
 @brief Check an export snapshot with the installed engine, without rendering

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
import sys

import openshot
from classes.export_settings import test_writer

# The export setting a failed check points at, by the stage that failed
STAGE_SETTINGS = {'video': 'params.config.video_codec', 'audio': 'params.config.audio_codec',
                  'format': 'params.config.format', 'header': 'params.config.format'}


def apply_engine_settings(config):
    """Apply hardware device and thread selections before opening a writer."""
    settings = openshot.Settings.Instance()
    for name, attribute in [('encoder_device', 'HW_EN_DEVICE_SET'), ('decoder_device', 'HW_DE_DEVICE_SET'),
                            ('hardware_decoder', 'HARDWARE_DECODER')]:
        if name in config['hardware']:
            setattr(settings, attribute, config['hardware'][name])
    if 'threads' in config:
        settings.FF_THREADS = config['threads']


def check(spec, path=None):
    """Open the encoders and write the header to memory, exactly as the export would."""
    config = spec['config']
    if config['mode'] == 'image_sequence':
        # Frames are saved as images; no writer is opened
        return {'ok': True}
    apply_engine_settings(config)
    return test_writer(path or spec['output'], spec['video'], spec['audio'], config['mode'],
                       config['quality_mode'], config['video_options'], config['audio_options'])


def main(spec_path):
    """Print the check result as one JSON line (run in its own process, like the export worker)."""
    with open(spec_path) as handle:
        spec = json.load(handle)
    print(json.dumps(check(spec)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
