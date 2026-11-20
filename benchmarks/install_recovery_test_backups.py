# Copyright (c) 2026 OpenShot Studios, LLC
# This file is part of OpenShot Video Editor (https://www.openshot.org).
# SPDX-License-Identifier: GPL-3.0-or-later
#
# OpenShot Video Editor is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenShot Video Editor is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenShot Video Editor. If not, see <https://www.gnu.org/licenses/>.

"""Install the portable test pack's backups into an OpenShot recovery directory."""
import argparse
import json
from pathlib import Path
import shutil
import time
import zipfile


def install_backups(root, recovery_dir):
    """Reserve new filenames and bind intact archives to the extracted projects."""
    root = Path(root).resolve()
    recovery_dir = Path(recovery_dir).expanduser().resolve()
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    recovery_dir.mkdir(parents=True, exist_ok=True)
    installed = []
    now = int(time.time())
    for entry in manifest['backups']:
        source = (root / entry['archive']).resolve()
        project = (root / entry['project']).resolve()
        source.relative_to(root)
        project.relative_to(root)
        timestamp = now - entry['age_seconds']
        while True:
            destination = recovery_dir / '{}-{}.zip'.format(timestamp, project.stem)
            try:
                stream = destination.open('xb')
                break
            except FileExistsError:
                timestamp += 1
        try:
            with stream:
                if entry.get('intentionally_broken'):
                    with source.open('rb') as incoming:
                        shutil.copyfileobj(incoming, stream)
                else:
                    with zipfile.ZipFile(source) as archive:
                        if archive.namelist() != [project.name]:
                            raise ValueError('Unexpected project in test archive: ' + source.name)
                        contents = archive.read(project.name)
                    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                        archive.writestr(project.name, contents)
                        archive.comment = json.dumps({'project_path': str(project)}).encode('utf-8')
        except Exception:
            destination.unlink()
            raise
        installed.append(destination)
    return installed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recovery-dir', type=Path, default=Path.home() / '.openshot_qt' / 'recovery')
    parser.add_argument('--projects', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    for path in install_backups(args.projects, args.recovery_dir):
        print(path)


if __name__ == '__main__':
    main()
