"""Restricted legacy pickle compatibility and adversarial reconstruction tests."""

import copyreg
import io
from pathlib import Path
import pickle  # nosec B403 - controlled, non-executing test fixtures
import tempfile
import unittest
from unittest.mock import patch

from classes.legacy_project import LegacyProjectUnpickler, read_legacy_project, _RECORDS, _reconstruct, legacy_media_path
from tests.source_tree import source_path

FIXTURES = source_path('src/tests/fixtures/legacy')


class LegacyProjectTests(unittest.TestCase):
    # Saved and reopened by the official 1.4.3-1 PPA application in Ubuntu 12.04.
    # Decoding needs no media. Conversion still omits transforms, clip effects,
    # mute/hide and the project profile; keep this fixture for future import work.
    def test_native_143_project_and_shared_references(self):
        project = read_legacy_project(FIXTURES / 'native-1-4-3.osp')
        self.assertEqual(project.project_type, 'HD 720p 25 fps')
        seq = project.sequences[0]
        self.assertIs(seq.project, project)
        self.assertIs(project.tabs[0], seq)
        self.assertEqual(len(project.project_folder.items), 5)
        self.assertEqual(len(seq.tracks), 5)
        self.assertEqual(sum(len(track.clips) for track in seq.tracks), 8)
        self.assertFalse(seq.tracks[0].play_video)
        self.assertFalse(seq.tracks[1].play_audio)
        self.assertIs(seq.tracks[0].clips[0].file_object, seq.tracks[2].clips[2].file_object)

    def test_native_143_animation_effects_and_clip_flags(self):
        project = read_legacy_project(FIXTURES / 'native-1-4-3.osp')
        red, blue, silent, hidden = project.sequences[0].tracks[2].clips
        for key, expected in (('start', (50.0, 75.0, -20.0, 10.0, 0.6)),
                              ('end', (125.0, 110.0, 20.0, -10.0, 1.0))):
            frame = red.keyframes[key]
            self.assertEqual((frame.width, frame.height, frame.x, frame.y, frame.alpha), expected)
        self.assertEqual(red.effects[0].service, 'brightness')
        self.assertEqual(red.effects[0].paramaters, [{'start': '0.75'}, {'end': '1.25'}])
        self.assertEqual(blue.effects[0].service, 'frei0r.saturat0r')
        self.assertEqual(blue.effects[0].paramaters, [{'Saturation': '0.2'}])
        self.assertEqual(blue.rotation, 12.0)
        self.assertFalse(silent.play_audio)
        self.assertFalse(hidden.play_video)

    def test_native_143_fades_volume_and_transitions(self):
        project = read_legacy_project(FIXTURES / 'native-1-4-3.osp')
        seq = project.sequences[0]
        blue = seq.tracks[2].clips[1]
        self.assertEqual((blue.video_fade_in_amount, blue.video_fade_out_amount), (0.75, 1.25))
        self.assertEqual((blue.audio_fade_in_amount, blue.audio_fade_out_amount), (0.25, 0.5))
        tone = seq.tracks[4].clips[0]
        self.assertEqual((tone.volume, tone.audio_fade_in_amount, tone.audio_fade_out_amount), (35.0, 0.5, 1.5))
        wipe, dissolve = seq.tracks[2].transitions
        self.assertEqual((wipe.position_on_track, wipe.length, wipe.softness, wipe.reverse), (3.5, 1.0, 0.15, True))
        self.assertEqual((dissolve.position_on_track, dissolve.length, dissolve.softness, dissolve.reverse),
                         (7.5, 0.5, 0.7, False))

    def read_bytes(self, contents):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test.osp'
            path.write_bytes(contents)
            return read_legacy_project(path)

    def test_legacy_projects_and_module_aliases(self):
        for fixture in sorted(FIXTURES.glob('project-v1-*.osp')):
            data = fixture.read_bytes()
            for prefix in (b'classes.', b'openshot.classes.', b'classes.legacy.openshot.classes.'):
                # GLOBAL/INST module names are newline-delimited in these protocols.
                contents = data.replace(b'classes.', prefix)
                with self.subTest(fixture=fixture.name, prefix=prefix):
                    project = self.read_bytes(contents)
                    self.assertIs(type(project), _RECORDS['project'])
                    self.assertIs(project.project_folder.project, project)
                    seq = project.sequences[0]
                    clip = seq.tracks[0].clips[0]
                    self.assertIs(seq.project, project)
                    self.assertIs(clip.file_object, project.project_folder.items[0])
                    self.assertEqual(clip.start_time, 1.0)
                    self.assertEqual(clip.volume, 75.0)
                    for stream in ('video', 'audio'):
                        for direction in ('in', 'out'):
                            if getattr(clip, stream + '_fade_' + direction):
                                expected = 0.25 if stream == 'audio' and fixture.name in ('project-v1-obj.osp', 'project-v1-audio-only.osp') else 0.5
                                self.assertEqual(getattr(clip, stream + '_fade_' + direction + '_amount'), expected)
                    self.assertEqual(seq.tracks[0].transitions[0].softness, 0.3)
                    self.assertIs(type(clip.effects[0]), _RECORDS['effect'])
                    self.assertIs(type(clip.keyframes['start']), _RECORDS['keyframe'])
                    self.assertIs(type(seq.markers[0]), _RECORDS['marker'])
                    self.assertEqual(seq.markers[0].name, 'Café 日本語')

    def test_original_legacy_classes_are_never_imported_or_constructed(self):
        path = str(FIXTURES / 'project-v1-protocol2.osp')
        with patch('builtins.__import__', wraps=__import__) as imports:
            project = read_legacy_project(path)
        self.assertFalse(any(call.args[0].startswith('classes.') for call in imports.call_args_list))
        self.assertEqual(project.name, 'Legacy compatibility fixture')

    def test_forbidden_globals_never_resolve_or_invoke(self):
        for module, name in (('os', 'system'), ('posix', 'system'), ('builtins', 'eval'),
                             ('builtins', 'getattr'), ('builtins', '__import__'),
                             ('subprocess', 'Popen'), ('classes.project', 'unexpected'),
                             ('classes.legacy_project', '_RECORDS'), ('classes.project', 'project.__new__')):
            with self.subTest(module=module, name=name), \
                    patch('builtins.__import__', wraps=__import__) as imports:
                with self.assertRaises(pickle.UnpicklingError):
                    self.read_bytes(('c%s\n%s\n.' % (module, name)).encode('ascii'))
                self.assertFalse(any(call.args[0] == module for call in imports.call_args_list))

    def test_benign_reduce_callable_is_blocked_before_invocation(self):
        class Payload:
            def __reduce__(self):
                return (print, ('benign fixture',))
        for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
            data = pickle.dumps(Payload(), protocol=protocol)
            with self.subTest(protocol=protocol), patch('builtins.print') as called:
                with self.assertRaises(pickle.UnpicklingError):
                    self.read_bytes(data)
                called.assert_not_called()

    def test_extension_cache_cannot_bypass_global_restrictions(self):
        # Put a harmless callable directly in CPython's cache: EXT opcodes can
        # otherwise bypass find_class. Never execute an external payload.
        for opcode, code in ((b'\x82\x01', 1), (b'\x83\x00\x01', 256),
                             (b'\x84\x00\x00\x01\x00', 65536)):
            with self.subTest(code=code), patch('builtins.print') as called, \
                    patch.dict(copyreg._extension_cache, {code: called}):
                with self.assertRaises(pickle.UnpicklingError):
                    LegacyProjectUnpickler(io.BytesIO(b'\x80\x02' + opcode + b')R.')).load()
                called.assert_not_called()

    def test_persistent_references_are_rejected(self):
        for data in (b'Pexternal\n.', b'\x80\x02NQ.'):
            with self.subTest(data=data), self.assertRaises(pickle.UnpicklingError):
                self.read_bytes(data)

    def test_object_state_and_constructor_arguments_are_checked(self):
        base = b'\x80\x02cclasses.project\nproject\n'
        for tail in (b')\x81]b.',  # BUILD with list state
                     b')\x81}X\x09\x00\x00\x00__class__Nsb.',
                     b')\x81}K\x01Nsb.',  # Non-string state key
                     b')}X\x01\x00\x00\x00xK\x01s\x92.',  # NEWOBJ_EX kwargs
                     b'K\x01\x85R.',  # REDUCE with arguments
                     b'K\x01\x85\x81.'):  # NEWOBJ with arguments
            with self.subTest(tail=tail), self.assertRaises(pickle.UnpicklingError):
                self.read_bytes(base + tail)
        for args in ((print, object, None), (_RECORDS['project'], list, None),
                     (_RECORDS['project'], object, {})):
            with self.subTest(args=args), self.assertRaises(pickle.UnpicklingError):
                _reconstruct(*args)

    def test_invalid_roots_truncation_and_trailing_bytes_are_rejected(self):
        contents = (FIXTURES / 'project-v1-protocol2.osp').read_bytes()
        for data in (b'', contents[:1], contents[:-1], contents + b'N.',
                     pickle.dumps({'legacy': True}), pickle.dumps([]),
                     pickle.dumps(object())):
            with self.subTest(data=data[:20]), self.assertRaises((pickle.UnpicklingError, EOFError)):
                self.read_bytes(data)

    def test_missing_converter_fields_are_rejected(self):
        contents = (FIXTURES / 'project-v1-protocol0.osp').read_bytes()
        for data in (contents.replace(b'Vsequences\n', b'Vwrong_key\n'),
                     contents.replace(b'Vstart_time\n', b'Vbad_time\n'),
                     contents.replace(b'F1.0\n', b'Fnan\n'),
                     contents[:-1] + b'(dVextra\nc__builtin__\nobject\nsb.'):
            with self.subTest(data=data[:20]), self.assertRaises(pickle.UnpicklingError):
                self.read_bytes(data)

    def test_early_shared_fade_durations_and_explicit_precedence(self):
        contents = (FIXTURES / 'project-v1-obj.osp').read_bytes()
        self.assertIn(b'Vvideo_fade_amount\nF0.5\ns', contents)
        explicit = contents.replace(
            b'Vvideo_fade_amount\nF0.5\ns',
            b'Vvideo_fade_amount\nF9.0\nsVvideo_fade_in_amount\nF0.25\nsVvideo_fade_out_amount\nF0.75\ns')
        clip = self.read_bytes(explicit).sequences[0].tracks[0].clips[0]
        self.assertEqual(clip.video_fade_in_amount, 0.25)
        self.assertEqual(clip.video_fade_out_amount, 0.75)
        self.assertEqual(clip.audio_fade_in_amount, 0.25)
        missing = contents.replace(b'Vvideo_fade_amount\n', b'Vold_unused_video\n')
        missing = missing.replace(b'Vaudio_fade_amount\n', b'Vold_unused_audio\n')
        with self.assertRaises(pickle.UnpicklingError):
            self.read_bytes(missing)
        # No amount is needed when the old file has all fades disabled.
        clip = self.read_bytes(missing.replace(b'I01\n', b'I00\n')).sequences[0].tracks[0].clips[0]
        self.assertFalse(clip.video_fade_in)
        self.assertFalse(hasattr(clip, 'video_fade_in_amount'))

    def test_relative_media_resolves_beside_project_without_rewriting_absolute_paths(self):
        project = Path(tempfile.gettempdir()) / 'extracted pack' / 'example.osp'
        self.assertEqual(legacy_media_path(project, 'Media/red.png'),
                         str(project.parent / 'Media' / 'red.png'))
        for path in ('', '/original/media.png', r'C:\Original\media.png', r'\\server\media.png'):
            with self.subTest(path=path):
                self.assertEqual(legacy_media_path(project, path), path)
