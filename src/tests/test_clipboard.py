"""Timeline clipboard JSON/metadata compatibility and rejection regressions."""

import copy
import json
import unittest
from unittest.mock import patch

from qt_api import QMimeData
from classes.clipboard import ClipboardManager
from classes.query import Clip, Transition, Effect

MIME = 'application/x-openshot-generic'


def item(cls, data, source_id='source'):
    result = cls()
    result.id = source_id
    result.data = copy.deepcopy(data)
    return result


class ClipboardTests(unittest.TestCase):
    def test_single_types_preserve_json_text_identity_and_partial_data(self):
        samples = [
            (Clip, {'id': 'source', 'reader': {'path': 'movie.mp4'}, 'position': 2.5,
                    'layer': 3000000, 'start': 1.0, 'end': 5.0, 'effects': []}),
            (Transition, {'id': 'source', 'reader': {'path': 'fade.svg'},
                          'position': 1.0, 'start': 0.0, 'end': 1.0}),
            (Effect, {'id': 'source', 'class_name': 'Blur', 'radius': {'Points': []}}),
            (Clip, {'alpha': {'Points': [{'co': {'X': 1, 'Y': 0.5}}]}}),
            (Clip, {'effects': [{'id': 'E1', 'class_name': 'Blur'}]}),
            (Clip, {'text_style': {'font': 'Noto Sans', 'text': '你好 🎬'}}),
            (Clip, {}),
            (Transition, {'brightness': {'Points': []}, 'contrast': {'Points': []}}),
        ]
        for cls, data in samples:
            for wrapped in (False, True):
                with self.subTest(cls=cls.__name__, data=data, wrapped=wrapped):
                    source = item(cls, data)
                    mime = ClipboardManager.to_mime([source] if wrapped else source)
                    self.assertEqual(mime.text(), json.dumps(data, indent=4))
                    metadata = json.loads(bytes(mime.data(MIME)))
                    self.assertEqual(metadata, {'version': 1, 'items': [
                        {'type': cls.__name__.lower(), 'id': 'source'}]})
                    result = ClipboardManager.from_mime(mime)
                    self.assertIs(type(result), cls)
                    self.assertEqual(result.id, 'source')
                    self.assertEqual(result.data, data)
                    self.assertEqual(source.data, data)
                    result.data['changed'] = True
                    self.assertNotIn('changed', source.data)

    def test_mixed_selection_round_trips_through_new_mime_instance(self):
        originals = [item(Clip, {'position': 5, 'layer': 3, 'id': 'C1'}, 'C1'),
                     item(Transition, {'position': 7, 'layer': 2, 'id': 'T1'}, 'T1')]
        source = ClipboardManager.to_mime(originals)
        # Represents a different window/process receiving only serialized formats.
        received = QMimeData()
        received.setText(source.text())
        received.setData(MIME, source.data(MIME))
        decoded = ClipboardManager.from_mime(received)
        self.assertEqual([type(obj) for obj in decoded], [Clip, Transition])
        self.assertEqual([obj.id for obj in decoded], ['C1', 'T1'])
        self.assertEqual([obj.data for obj in decoded], [obj.data for obj in originals])
        self.assertEqual(source.text(), json.dumps([obj.data for obj in originals], indent=4))
        metadata = bytes(source.data(MIME))
        self.assertNotIn(b'position', metadata)
        self.assertNotIn(b'layer', metadata)

    def test_empty_selection_and_unsaved_identity(self):
        self.assertEqual(ClipboardManager.from_mime(ClipboardManager.to_mime([])), [])
        source = item(Clip, {'alpha': {}}, source_id=None)
        self.assertIsNone(ClipboardManager.from_mime(ClipboardManager.to_mime(source)).id)

    def test_plain_text_has_no_openshot_semantics(self):
        mime = QMimeData()
        mime.setText('{"position": 1}')
        self.assertIsNone(ClipboardManager.from_mime(mime))

    def test_malformed_metadata_and_mismatched_text_are_ignored(self):
        good = {'version': 1, 'items': [{'type': 'clip', 'id': 'C1'}]}
        for metadata, text in [
                (b'', '{}'), (b'\xff', '{}'), (b'{', '{}'), (b'null', '{}'),
                (json.dumps({'version': True, 'items': []}).encode(), '[]'),
                (json.dumps({'version': 2, 'items': []}).encode(), '[]'),
                (json.dumps({'version': 1, 'items': [None]}).encode(), '{}'),
                (json.dumps({'version': 1, 'items': [{'type': ['clip']}]}).encode(), '{}'),
                (json.dumps({'version': 1, 'items': [{'type': 'eval'}]}).encode(), '{}'),
                (json.dumps({'version': 1, 'items': [{'type': 'clip', 'id': {}}]}).encode(), '{}'),
                (json.dumps(good).encode(), '[]'), (json.dumps(good).encode(), '[{}, {}]'),
                (json.dumps(good).encode(), 'null'), (json.dumps(good).encode(), '{'),
                (json.dumps(good).encode(), '{"position": "bad"}'),
                (json.dumps(good).encode(), '{"position": NaN}'),
                (json.dumps(good).encode(), '{"end": 1e999}'),
                (json.dumps(good).encode(), '{"effects": [null]}'),
                (json.dumps(good).encode(), '{"reader": []}')]:
            with self.subTest(metadata=metadata, text=text):
                mime = QMimeData()
                mime.setData(MIME, metadata)
                mime.setText(text)
                self.assertIsNone(ClipboardManager.from_mime(mime))

    def test_missing_text_is_ignored(self):
        mime = ClipboardManager.to_mime(item(Clip, {}))
        mime.removeFormat('text/plain')
        self.assertIsNone(ClipboardManager.from_mime(mime))

    def test_old_pickle_bytes_are_never_deserialized(self):
        # Controlled primitive fixture bytes, not an executable payload.
        for payload in (b'\x80\x02}q\x00.', b'(dp0\n.', b'\x80', b''):
            with self.subTest(payload=payload), patch('pickle.load') as load, patch('pickle.loads') as loads:
                mime = QMimeData()
                mime.setData(MIME, payload)
                mime.setText('{}')
                self.assertIsNone(ClipboardManager.from_mime(mime))
                load.assert_not_called()
                loads.assert_not_called()

    def test_invalid_copy_objects_publish_no_partial_formats(self):
        for value in ({}, object(), [item(Clip, {}), object()], item(Clip, []),
                      item(Clip, {'position': float('nan')})):
            with self.subTest(value=value):
                self.assertEqual(ClipboardManager.to_mime(value).formats(), [])
