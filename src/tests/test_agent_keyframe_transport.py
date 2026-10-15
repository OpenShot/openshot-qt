"""
 @file
 @brief Exercise agent-facing keyframe/bulk commands through a real local session.

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
import subprocess
import sys
import tempfile
import time
import unittest
import uuid


class KeyframeTransportTests(unittest.TestCase):
    def test_shell_json_files_discovery_errors_and_batch_undo(self):
        root = Path(__file__).resolve().parents[1]
        cli = root / 'launch.py'
        with tempfile.TemporaryDirectory(prefix='openshot-cli-test-') as temporary:
            directory = Path(temporary)
            from tests.agent_test_support import subprocess_environment
            env = subprocess_environment(QT_QPA_PLATFORM='offscreen', OPENSHOT_SESSION_DIR=str(directory / 'sessions'))
            env.pop('OPENSHOT_SESSION', None)
            session_id = uuid.uuid4().hex
            with (directory / 'server.log').open('w') as log:
                process = subprocess.Popen([sys.executable, str(cli), '--cli', 'session', 'serve', '--session-id', session_id],
                                           env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
                try:
                    deadline = time.monotonic() + 20
                    record = directory / 'sessions' / (session_id + '.json')
                    while not record.exists() and process.poll() is None and time.monotonic() < deadline:
                        time.sleep(.05)
                    self.assertTrue(record.exists(), (directory / 'server.log').read_text())

                    def run(*args, ok=True):
                        result = subprocess.run([sys.executable, str(cli), '--cli', '--session', session_id, *args],
                                                env=env, capture_output=True, text=True, timeout=20)
                        self.assertEqual(result.returncode, 0 if ok else 1, result.stderr)
                        payload = json.loads(result.stdout if ok else result.stderr)
                        return payload['result'] if ok else payload['error']

                    run('project', 'profile', 'set', 'builtin:01280x0720p0030_16-09')
                    layer = run('project', 'get')['data']['layers'][0]['number']
                    source = root / 'images' / 'cache' / 'openshot_logo.png'
                    file_id = run('file', 'import', str(source))['data']['id']
                    clips = [run('clip', 'add', file_id, '--layer', str(layer), '--position', str(pos), '--start', '2', '--end', '5')['data']['id'] for pos in (5, 10)]
                    discovery = run('clip', 'keyframe', 'list', clips[0])['data']
                    self.assertIn('location_x', [row['property'] for row in discovery['properties']])
                    run('clip', 'keyframe', 'set', clips[0], '--property', 'location_x', '--space', 'clip', '--unit', 'seconds', '--at', '0', '--value', '-1')
                    run('clip', 'keyframe', 'set', clips[0], '--property', 'location_x', '--space', 'clip', '--unit', 'seconds', '--at', '1', '--value', '0', '--interpolation', 'bezier', '--handles', '{"handle_left":{"X":0.2,"Y":0.9}}')
                    points = run('clip', 'keyframe', 'list', clips[0], '--property', 'location_x', '--space', 'clip', '--start', '1')['data']['points']
                    point_file = directory / 'points.json'
                    point_file.write_text(json.dumps(points))
                    run('clip', 'keyframe', 'paste', clips[1], '--property', 'location_x', '--space', 'clip', '--mode', 'replace', '--json', '@' + str(point_file))
                    self.assertEqual(run('clip', 'keyframe', 'list', clips[1], '--property', 'location_x', '--space', 'clip')['data']['points'], points)
                    selector = json.dumps({'ids': clips})
                    selected = run('edit', 'select', '--json', selector)['data']
                    templates = directory / 'templates.json'
                    templates.write_text(json.dumps([
                        {'method': 'effects.add', 'as': 'look', 'params': {'type': 'Saturation'}},
                        {'method': 'effects.keyframe.set', 'params': {'id': {'$ref': 'look.id'}, 'property': 'saturation', 'space': 'clip', 'at': 31, 'value': .5}},
                    ]))
                    preview = run('edit', 'bulk', '--select', selector, '--json', '@' + str(templates), '--dry-run')
                    self.assertEqual(preview['data']['command_count'], 4)
                    self.assertEqual(preview['revision'], selected['revision'])
                    applied = run('edit', 'bulk', '--select', selector, '--json', '@' + str(templates), '--expect-revision', str(selected['revision']))
                    self.assertEqual(applied['selected_ids'], clips)
                    self.assertEqual(len(run('effects', 'instances')['data']), 2)
                    run('history', 'undo')
                    self.assertEqual(run('effects', 'instances')['data'], [])
                    run('history', 'redo')
                    self.assertEqual(len(run('effects', 'instances')['data']), 2)
                    error = run('clip', 'keyframe', 'set', clips[0], '--property', 'locaton_x', '--at', '1', '--value', '0', ok=False)
                    self.assertEqual(error['code'], 'invalid_keyframe')
                    self.assertIn('location_x', error['message'])
                    run('session', 'stop', '--discard')
                    process.wait(timeout=10)
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
