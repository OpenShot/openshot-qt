"""
 @file
 @brief Save portable project copies with collected local media.

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
import hashlib
import re
import shutil
import tempfile
from pathlib import Path

from .protocol import CommandError


def collect(service, params):
    """Stage a portable snapshot; do not mutate the live project or move its media."""
    destination = Path(params['directory']).expanduser().resolve()
    name = params.get('name', 'project.osp')
    if Path(name).name != name or Path(name).suffix.lower() != '.osp':
        raise CommandError('invalid_argument', '--name must be a filename ending in .osp.')
    if destination.exists():
        raise CommandError('already_exists', 'Collection directory must be new: ' + str(destination))
    if not destination.parent.is_dir():
        raise CommandError('not_found', 'Collection parent directory must exist.')
    project = service.app.project
    data = copy.deepcopy(project._data)
    data['history'] = {'undo': [], 'redo': []}
    data.pop('runtime_assets_path', None)
    base = Path(project.current_filepath).parent if project.current_filepath else Path.cwd()
    copied = {}
    paths = {'path', 'resource', 'protobuf_data_path', 'lut_path', 'image'}
    with tempfile.TemporaryDirectory(prefix='.openshot-collect-', dir=str(destination.parent)) as folder:
        stage = Path(folder)
        def visit(value):
            if isinstance(value, list):
                for child in value:
                    visit(child)
            elif isinstance(value, dict):
                for key, child in list(value.items()):
                    if key not in paths or not isinstance(child, str) or not child:
                        visit(child)
                        continue
                    source = Path(child).expanduser()
                    if not source.is_absolute():
                        source = base / source
                    source = source.resolve()
                    pattern = re.search(r'%0?\d*d', source.name)
                    sequence = []
                    if pattern:
                        regex = re.compile(re.escape(source.name[:pattern.start()]) + r'\d+' + re.escape(source.name[pattern.end():]) + '$')
                        sequence = [p for p in source.parent.iterdir() if regex.fullmatch(p.name) and p.is_file()] if source.parent.is_dir() else []
                    if not source.exists() and not sequence:
                        if key == 'image':  # Disposable timeline thumbnail, regenerated on open.
                            value[key] = ''
                            continue
                        raise CommandError('missing_media', 'Cannot collect missing asset: ' + str(source))
                    identity = str(source)
                    if identity not in copied:
                        relative = Path('media') / hashlib.sha256(identity.encode()).hexdigest()[:16] / source.name
                        target = stage / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if sequence:
                            for frame in sequence:
                                shutil.copy2(str(frame), str(target.parent / frame.name))
                        elif source.is_dir():
                            shutil.copytree(str(source), str(target))
                        else:
                            shutil.copy2(str(source), str(target))
                        copied[identity] = relative.as_posix()
                    value[key] = copied[identity]
        visit(data)
        # Snapshot paths are already relative to their final project location.
        project.write_to_file(str(stage / name), data, path_mode='ignore')
        created = False
        try:
            destination.mkdir()  # Atomic reservation: never replace an existing directory.
            created = True
            for item in stage.iterdir():
                shutil.move(str(item), str(destination / item.name))
        except Exception:
            if created:
                shutil.rmtree(str(destination))
            raise
    return {'path': str(destination / name), 'directory': str(destination),
            'copied_assets': len(copied), 'history_included': False,
            'live_project_unchanged': True}
