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

"""Recovery must preserve source bytes and disclose every discarded clip."""
import copy
import json
import os
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from classes.project_recovery import parse_project, previous_versions, read_version, save_recovered_copy


class ProjectRecoveryTests(unittest.TestCase):
    def project(self):
        return {"clips": [{"id": "C1", "position": 2, "start": 0, "end": 5,
                           "layer": 1000000, "reader": {"type": "QtImageReader"}}],
                "files": [], "layers": [], "fps": {"num": 30, "den": 1},
                "unknown": {"text": 'keep ,} and ,] and \\"'}}

    def test_legacy_260_unquoted_keys_are_repaired_without_changing_strings(self):
        project = self.project()
        project['version'] = {'openshot-qt': '2.6.0'}
        project['files'] = [{'id': 'F1', 'path': 'C:/media/clip.mp4'}]
        project['unknown']['text'] = 'literal id: and files: must remain unchanged'
        text = json.dumps(project, indent=1).replace('"files":', 'files:').replace('"id": "F1"', 'id: "F1"')
        repaired, report = parse_project(text, repair=True)
        self.assertEqual(repaired, project)
        self.assertIn('Quoted 2 project keys', report[0])
        modern = text.replace('2.6.0', '4.2.0')
        with self.assertRaises(ValueError):
            parse_project(modern, repair=True)

    def test_invalid_history_records_are_rejected_before_opening(self):
        for actions in ([None], [{'key': []}], [{'key': 'clips'}]):
            project = self.project()
            project['history'] = {'undo': actions, 'redo': []}
            with self.subTest(actions=actions), self.assertRaisesRegex(ValueError, 'history entry'):
                parse_project(json.dumps(project))

    def test_repair_only_discards_nonfinite_waveform_caches(self):
        data = self.project()
        data["files"] = [{"ui": {"audio_data": [0.5, float("nan")],
                                  "audio_data_rms": [float("inf")]}}]
        text = json.dumps(data)
        with self.assertRaises(ValueError):
            parse_project(text)
        repaired, changes = parse_project(text, repair=True)
        self.assertEqual(repaired["files"][0]["ui"], {"audio_data": [], "audio_data_rms": []})
        self.assertEqual(repaired["clips"], data["clips"])
        self.assertEqual(len(changes), 2)
        for value in (float("nan"), float("inf"), -float("inf")):
            data["clips"][0]["position"] = value
            with self.assertRaises(ValueError):
                parse_project(json.dumps(data), repair=True)
        with self.assertRaises(ValueError):
            parse_project('{"files": [], "files": [], "clips": [], "layers": []}', repair=True)

    def test_history_repair_keeps_reachable_suffix_and_whole_transactions(self):
        def action(transaction):
            return {"type": "update", "key": ["clips"], "transaction": transaction}
        data = self.project()
        # A is non-contiguous. Removing its older part must remove its newer
        # part too; this also crosses B, so only C remains reachable.
        actions = [action("A"), None, action("B"), action("A"), action("B"), action("C")]
        data["history"] = {"undo": actions, "redo": [action("R")]}
        repaired, changes = parse_project(json.dumps(data), repair=True)
        self.assertEqual(repaired["history"], {"undo": [action("C")], "redo": [action("R")]})
        self.assertIn("discarded 5 of 6", changes[0])
        data["history"]["redo"] = [action("R"), None]
        repaired, _ = parse_project(json.dumps(data), repair=True)
        self.assertEqual(repaired["history"]["redo"], [])
        self.assertEqual(repaired["clips"], data["clips"])

    def test_unreadable_history_requires_complete_current_collections(self):
        data = self.project()
        prefix = json.dumps(data)[:-1]
        damaged = prefix + ', "history": {"undo": [{"key": ['
        repaired, changes = parse_project(damaged, repair=True)
        self.assertEqual(repaired, dict(data, history={"undo": [], "redo": []}))
        self.assertIn("unreadable remainder", changes[0])
        for text in ('{"history": {"undo": [',
                     prefix + ', "unknown": {"bad": [',
                     damaged.replace('"files": []', '"files": null'),
                     prefix + ', "history": {}, "tail": ['):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_project(text, repair=True)

    def test_filename_quote_repair_requires_one_existing_file(self):
        with tempfile.TemporaryDirectory() as root:
            original = os.path.join(root, "movie.osp")
            filename = 'say "hello".svg'
            data = self.project()
            data["clips"][0]["reader"]["path"] = './' + filename
            text = json.dumps(data, indent=1)
            damaged = text.replace('say \\"hello', 'say /"hello')
            self.assertNotEqual(text, damaged)
            with self.assertRaises(ValueError):
                parse_project(damaged, repair=True, original_path=original)
            with open(os.path.join(root, filename), "w") as stream:
                stream.write("<svg/>")
            repaired, changes = parse_project(damaged, repair=True, original_path=original)
            self.assertEqual(repaired, data)
            self.assertIn("verified existing file", changes[0])
            # Both interpretations exist: do not choose one.
            os.mkdir(os.path.join(root, 'say '))
            with open(os.path.join(root, 'say ', '"hello".svg'), "w") as stream:
                stream.write("<svg/>")
            with self.assertRaisesRegex(ValueError, "found 2"):
                parse_project(damaged, repair=True, original_path=original)

    def test_filename_quote_repair_resolves_project_assets(self):
        with tempfile.TemporaryDirectory() as root:
            original = os.path.join(root, "movie.osp")
            assets = os.path.join(root, "movie_assets", "title")
            os.makedirs(assets)
            filename = '"hello".svg'
            with open(os.path.join(assets, filename), "w") as stream:
                stream.write("<svg/>")
            data = self.project()
            data["clips"][0]["reader"]["path"] = "@assets/title/" + filename
            text = json.dumps(data, indent=1)
            damaged = text.replace('title/\\"hello', 'title//"hello')
            repaired, changes = parse_project(damaged, repair=True, original_path=original)
            self.assertEqual(repaired, data)
            self.assertEqual(len(changes), 1)
            self.assertEqual(parse_project(text, repair=True, original_path=original), (data, []))

    def test_automatic_recovery_naming_skips_existing_files_and_asset_folders(self):
        from classes.project_recovery import save_recovery_automatically
        with tempfile.TemporaryDirectory() as root:
            original = os.path.join(root, 'movie.osp')
            with open(original, 'w') as stream:
                stream.write('damaged original')
            with open(os.path.join(root, 'movie-recovered.osp'), 'w') as stream:
                stream.write('existing copy')
            os.mkdir(os.path.join(root, 'movie-recovered-2_assets'))
            destination = save_recovery_automatically(self.project(), original)
            self.assertEqual(destination, os.path.join(root, 'movie-recovered-3.osp'))
            with open(original) as stream:
                self.assertEqual(stream.read(), 'damaged original')
            with open(os.path.join(root, 'movie-recovered.osp')) as stream:
                self.assertEqual(stream.read(), 'existing copy')

    def test_archives_are_complete_unique_and_match_original_folder(self):
        from classes.project_recovery import archive_previous_version
        with tempfile.TemporaryDirectory() as root:
            original = os.path.join(root, "movie.osp")
            recovery = os.path.join(root, "recovery")
            with open(original, "w") as stream:
                stream.write(json.dumps(self.project()))
            first = archive_previous_version(original, recovery, 123)
            second = archive_previous_version(original, recovery, 123)
            self.assertNotEqual(first, second)
            self.assertEqual(len(previous_versions(original, recovery)), 2)
            self.assertEqual(previous_versions(os.path.join(root, "other", "movie.osp"), recovery), [])
            data, _ = parse_project(read_version(first, original))
            self.assertEqual(data, self.project())
            self.assertEqual(len(os.listdir(recovery)), 2)

    def test_archive_sync_uses_a_writable_descriptor_before_publication(self):
        from classes.project_recovery import archive_previous_version
        with tempfile.TemporaryDirectory() as root:
            original = os.path.join(root, "movie.osp")
            recovery = os.path.join(root, "recovery")
            destination = os.path.join(recovery, "123-movie.zip")
            contents = json.dumps(self.project())
            with open(original, "w", encoding="utf-8") as stream:
                stream.write(contents)
            fsync = os.fsync

            def sync_writable_descriptor(descriptor):
                # Windows requires write access to flush a file. A zero-byte
                # write enforces that requirement on Linux/macOS as well.
                os.write(descriptor, b"")
                self.assertFalse(os.path.exists(destination))
                fsync(descriptor)

            with patch("classes.project_recovery.os.fsync", side_effect=sync_writable_descriptor) as sync:
                self.assertEqual(archive_previous_version(original, recovery, 123), destination)
            sync.assert_called_once()
            with zipfile.ZipFile(destination) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(archive.read("movie.osp").decode("utf-8"), contents)
            with open(original, encoding="utf-8") as stream:
                self.assertEqual(stream.read(), contents)
            self.assertEqual(os.listdir(recovery), ["123-movie.zip"])

    def test_archive_sync_failure_preserves_original_and_removes_temporary(self):
        from classes.project_recovery import archive_previous_version
        with tempfile.TemporaryDirectory() as root:
            original = os.path.join(root, "movie.osp")
            recovery = os.path.join(root, "recovery")
            with open(original, "w", encoding="utf-8") as stream:
                stream.write("original project")
            with patch("classes.project_recovery.os.fsync", side_effect=OSError("flush failed")):
                with self.assertRaisesRegex(OSError, "flush failed"):
                    archive_previous_version(original, recovery, 123)
            self.assertEqual(os.listdir(recovery), [])
            with open(original, encoding="utf-8") as stream:
                self.assertEqual(stream.read(), "original project")

    def test_recovered_native_image_clip_can_be_opened_and_rendered(self):
        import openshot
        from qt_api import QImage, QColor
        from classes.json_data import JsonDataStore
        with tempfile.TemporaryDirectory() as root:
            original = os.path.join(root, "movie.osp")
            destination = os.path.join(root, "recovered.osp")
            assets = os.path.join(root, "movie_assets")
            os.mkdir(assets)
            image_path = os.path.join(assets, "image.png")
            image = QImage(16, 16, QImage.Format_ARGB32)
            image.fill(QColor("blue"))
            self.assertTrue(image.save(image_path))
            data = self.project()
            data['clips'] = [json.loads(openshot.Clip(image_path).Json())]
            data['clips'][0].update(id="native", position=0, start=0, end=2, layer=1000000)
            text = json.dumps(data)[:-1] + ',}'
            repaired, changes = parse_project(text, repair=True)
            self.assertTrue(changes)
            save_recovered_copy(repaired, original, destination)
            reopened = JsonDataStore().read_from_file(destination, path_mode="absolute")
            native = openshot.Clip()
            native.SetJson(json.dumps(reopened['clips'][0]))
            native.Open()
            try:
                frame = native.GetFrame(1)
                self.assertGreater(frame.GetWidth(), 0)
            finally:
                native.Close()

    def test_ambiguous_fields_and_nonfinite_numbers_are_not_silently_repaired(self):
        text = json.dumps(self.project())
        for candidate in ('{"clips": [], "clips": []}', text.replace('"position": 2', '"position": NaN')):
            with self.assertRaises(ValueError):
                parse_project(candidate, repair=True)

    def test_asset_copy_failure_keeps_original_and_removes_partial_output(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "source.osp")
            destination = os.path.join(root, "copy.osp")
            os.mkdir(os.path.join(root, "source_assets"))
            with open(source, "w") as stream:
                stream.write("original")

            def fail_copy(_source, target):
                os.mkdir(target)
                raise OSError("disk full")
            with patch("shutil.copytree", side_effect=fail_copy):
                with self.assertRaisesRegex(OSError, "disk full"):
                    save_recovered_copy(self.project(), source, destination)
            self.assertFalse(os.path.exists(destination))
            self.assertFalse(os.path.exists(os.path.join(root, "copy_assets")))
            with open(source) as stream:
                self.assertEqual(stream.read(), "original")

    def test_repairs_only_delimiters_outside_strings_and_bom(self):
        data = self.project()
        text = '\ufeff' + json.dumps(data)[:-1] + ',}'
        repaired, report = parse_project(text, repair=True)
        self.assertEqual(repaired, data)
        self.assertEqual(len(report), 2)
        with self.assertRaises(ValueError):
            parse_project(text)

    def test_incomplete_clips_require_repair_and_are_reported(self):
        data = self.project()
        data['clips'].append({'id': 'broken', 'position': 2.75})
        with self.assertRaisesRegex(ValueError, 'broken'):
            parse_project(json.dumps(data))
        repaired, report = parse_project(json.dumps(data), repair=True)
        self.assertEqual(len(repaired['clips']), 1)
        self.assertIn('broken', report[0])
        self.assertIn('2.75', report[0])
        self.assertEqual(repaired['unknown'], data['unknown'])

    def test_truncation_and_invalid_frame_rate_are_not_guessed(self):
        text = json.dumps(self.project())
        for candidate in ('{"clips": [,], "files": [], "layers": []}', text[:-5], text.replace('"den": 1', '"den": 0')):
            with self.assertRaises(ValueError):
                parse_project(candidate, repair=True)

    def test_exact_archive_matching_and_safe_read(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, 'movie.osp')
            for name in ('100-movie.zip', '101-movie-long.zip', '102-movie.osp'):
                with open(os.path.join(root, name), 'w'):
                    pass
            paths = previous_versions(source, root)
            self.assertEqual([os.path.basename(path) for path in paths], ['102-movie.osp', '100-movie.zip'])
            archive = os.path.join(root, '100-movie.zip')
            with zipfile.ZipFile(archive, 'w') as stream:
                stream.writestr('../movie.osp', '{}')
            with self.assertRaises(ValueError):
                read_version(archive, source)
            self.assertFalse(os.path.exists(source))

    def test_separate_copy_copies_assets_and_preserves_source_and_unknown_fields(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, 'movie.osp')
            destination = os.path.join(root, 'recovered.osp')
            assets = os.path.join(root, 'movie_assets')
            os.mkdir(assets)
            title = os.path.join(assets, 'title.svg')
            with open(title, 'w') as stream:
                stream.write('<svg/>')
            with open(source, 'w') as stream:
                stream.write('damaged original')
            data = self.project()
            data['clips'][0]['reader']['path'] = '@assets/title.svg'
            original = copy.deepcopy(data)
            save_recovered_copy(data, source, destination)
            self.assertEqual(data, original)
            with open(source) as stream:
                self.assertEqual(stream.read(), 'damaged original')
            with open(destination) as stream:
                recovered = json.load(stream)
            self.assertEqual(recovered['unknown'], data['unknown'])
            self.assertEqual(recovered['clips'][0]['reader']['path'], '@assets/title.svg')
            self.assertTrue(os.path.exists(os.path.join(root, 'recovered_assets', 'title.svg')))
            with self.assertRaises(ValueError):
                save_recovered_copy(data, source, destination)
