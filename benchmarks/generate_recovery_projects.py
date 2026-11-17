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

"""Generate a portable recovery test folder and, optionally, a distributable ZIP."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import time
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import openshot  # noqa: E402 - Requires the checkout path and native runtime.
from classes import info  # noqa: E402
from qt_api import QApplication, QColor, QFont, QImage, QPainter, Qt  # noqa: E402


CASES = {
    'valid': '00 - Valid project.osp',
    'comma': '01 - Trailing comma.osp',
    'many': '02 - Incomplete clips - 48 issues.osp',
    'truncated': '03 - Truncated JSON - backups available.osp',
    'bad_backup': '04 - Broken latest backup.osp',
    'no_backup': '05 - Truncated JSON - no backups.osp',
    'bom': '06 - UTF-8 BOM.osp',
    'legacy': '07 - Legacy 2.6.0 key quoting.osp',
}


INSTRUCTIONS = '''OPENSHOT PROJECT RECOVERY TEST PACK

1. Extract this whole folder anywhere writable. Keep Media beside the projects.
2. Install the sample backups before testing Restore Backup:
   - Recommended: run `python3 install_backups.py` (Windows: `py install_backups.py`).
   - For an isolated profile: add `--recovery-dir /path/to/profile/recovery`.
   - Without Python: copy the ZIP files inside Backups into your OpenShot recovery
     directory, usually ~/.openshot_qt/recovery or %USERPROFILE%\\.openshot_qt\\recovery.
     The supplied archives deliberately omit folder metadata so this fallback is portable.
3. In the OpenShot checkout/build being reviewed, use File > Open on these samples.
   These fixtures do not change which OpenShot executable your OS opens by default.

00 - Valid project
  Opens normally with one title clip. File > Recovery has sample versions:
  newest has two clips; older has one. Restore opens a separate named copy.
01 - Trailing comma
  Repair should open a copy and show the JSON correction in the modeless report.
02 - Incomplete clips - 48 issues
  Repair should omit the 48 incomplete entries and retain the title clip.
  Scroll the report to its last entry, resize it, select/copy text, and verify that
  Close remains visible. Backups offer intact one- and two-clip sample projects.
03 - Truncated JSON - backups available
  Repair should fail in the same dialog and disable Repair. Then restore a backup.
04 - Broken latest backup
  Restore should fail for the newest entry, mark and dim that entry, and select
  another copy. The older copy should open when restored.
05 - Truncated JSON - no backups
  Restore starts disabled. Repair should fail, leaving Details and Cancel.
06 - UTF-8 BOM
  Repair should remove the byte-order mark and open a copy.
07 - Legacy 2.6.0 key quoting
  Repair should quote the damaged key and preserve strings and media paths.

CHECKS FOR EVERY THEME
  Try Cosmic Dusk, Humanity: Dark, and Retro. Check disabled entries in the OPEN
  dropdown and the closed field when every backup fails. No filename picker or
  success confirmation should appear. Cancel must not open a recovery copy.
  Repeating recovery must choose another filename, not overwrite an existing copy.
  A report describes changes; it does not establish that every edit or asset works.

NOTES
  Only these numbered OSP inputs are intentionally damaged. Media is generated
  test artwork, not customer footage. No logs, personal settings, native libraries,
  recovered outputs, or machine-specific launchers are included.
  Automatic saving needs separate testing with writable/unwritable destinations
  and live editing. This pack does not simulate autosave failure or stress playback.
  Original-folder provenance is added by the optional installer. Moving the pack
  afterward requires installing its backups again for that new location.
  All generated project/media fixtures and scripts: Copyright (c) 2026 OpenShot
  Studios, LLC; GPL-3.0-or-later. See COPYING.
'''


def generate(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('Choose an empty output folder; existing test data is never replaced.')
    app = QApplication.instance() or QApplication([])
    media = output / 'Media'
    media.mkdir()
    image_path = media / 'Recovery test title.png'
    image = QImage(1280, 720, QImage.Format_ARGB32)
    image.fill(QColor('#234368'))
    painter = QPainter(image)
    painter.setPen(QColor('white'))
    painter.setFont(QFont('Sans', 48))
    painter.drawText(image.rect(), Qt.AlignCenter, 'OpenShot Recovery Test')
    painter.end()
    if not image.save(str(image_path)):
        raise OSError('Could not create the sample title image.')
    native = openshot.Clip(str(image_path))
    clip = json.loads(native.Json())
    clip.update(id='VALID-CLIP', file_id='F1', position=0, start=0, end=8, duration=8, layer=3000000)
    clip['reader'].update(id='F1', path='Media/' + image_path.name, media_type='image')
    project = json.loads((ROOT / 'src/settings/_default.project').read_text(encoding='utf-8'))
    project.update(profile='HD 720p 30 fps', width=1280, height=720, fps={'num': 30, 'den': 1},
                   display_ratio={'num': 16, 'den': 9}, pixel_ratio={'num': 1, 'den': 1},
                   clips=[clip], files=[copy.deepcopy(clip['reader'])], history={'undo': [], 'redo': []},
                   version={'openshot-qt': info.VERSION, 'libopenshot': openshot.OPENSHOT_VERSION_FULL})
    newer = copy.deepcopy(project)
    second = copy.deepcopy(clip)
    second.update(id='SECOND-CLIP', position=8)
    newer['clips'].append(second)
    for name in CASES.values():
        (output / name).write_text(json.dumps(project, ensure_ascii=False, indent=1), encoding='utf-8')
    text = json.dumps(project, ensure_ascii=False, indent=1)
    (output / CASES['comma']).write_text(text[:-1] + ',}', encoding='utf-8')
    broken = copy.deepcopy(project)
    broken['clips'].extend(
        {'id': 'INCOMPLETE-%02d' % index, 'position': index * 2.75} for index in range(1, 49))
    (output / CASES['many']).write_text(json.dumps(broken, indent=1), encoding='utf-8')
    for key in ('truncated', 'bad_backup', 'no_backup'):
        (output / CASES[key]).write_text('{"clips": [{"id": "CUT-OFF"', encoding='utf-8')
    (output / CASES['bom']).write_text('\ufeff' + text, encoding='utf-8')
    legacy = copy.deepcopy(project)
    legacy['version']['openshot-qt'] = '2.6.0'
    legacy_text = json.dumps(legacy, indent=1).replace('"files":', 'files:', 1)
    (output / CASES['legacy']).write_text(legacy_text, encoding='utf-8')
    backups = output / 'Backups'
    backups.mkdir()
    entries = []
    timestamp = int(time.time())
    for key in ('valid', 'many', 'truncated', 'bad_backup'):
        name = CASES[key]
        for age, data in ((3600, newer), (7200, project)):
            archive = backups / '{}-{}.zip'.format(timestamp - age, Path(name).stem)
            bad = key == 'bad_backup' and age == 3600
            if bad:
                archive.write_bytes(b'Intentionally broken ZIP archive for the recovery test.')
            else:
                with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as stream:
                    stream.writestr(name, json.dumps(data, ensure_ascii=False, indent=1))
            entries.append({'project': name, 'archive': archive.relative_to(output).as_posix(),
                            'age_seconds': age, 'intentionally_broken': bad})
    (output / 'manifest.json').write_text(json.dumps({'cases': CASES, 'backups': entries}, indent=2), encoding='utf-8')
    (output / 'START HERE.txt').write_text(INSTRUCTIONS, encoding='utf-8')
    shutil.copyfile(ROOT / 'COPYING', output / 'COPYING')
    shutil.copyfile(Path(__file__).with_name('install_recovery_test_backups.py'), output / 'install_backups.py')
    # Keep the QApplication alive until every Qt/native fixture is serialized.
    app.processEvents()
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--zip', dest='zip_path', type=Path)
    args = parser.parse_args()
    output = generate(args.output)
    if args.zip_path:
        args.zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.zip_path, 'x', zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(output.rglob('*')):
                if path.is_file():
                    archive.write(path, (Path(output.name) / path.relative_to(output)).as_posix())
        print(args.zip_path)
    print(output)


if __name__ == '__main__':
    main()
