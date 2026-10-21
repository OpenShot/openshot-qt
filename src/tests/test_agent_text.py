"""
 @file
 @brief CLI text commands share the editor's text code, validation, and undo history.

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
from pathlib import Path
import tempfile
import unittest

import openshot
from classes.agent.protocol import CommandError


class AgentTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_query import ensure_open_shot_app
        cls.app, _ = ensure_open_shot_app()

    def setUp(self):
        from tests.agent_test_support import isolate_preferences
        isolate_preferences(self)
        from classes.agent.service import EditingService
        self.app.window = None
        self.app.project.new()
        self.app.updates.reset()
        self.service = EditingService(self.app, 'test-text', 'headless')
        self.layer = self.app.project.get('layers')[0]['number']
        self.added = self.call('text.add', text='Hello', layer=self.layer, position=2, duration=3,
                               color='#ff0000', font_size=60, place='lower-third')

    def call(self, method, **params):
        return self.service.execute(method, params)['data']

    def clip(self, clip_id=None):
        return self.service.obj('clip', clip_id or self.added['clip']['id']).data

    def error(self, method, **params):
        with self.assertRaises(CommandError) as raised:
            self.service.execute(method, params)
        return raised.exception

    def path(self, method, **params):
        """The field an error points at (inside a command, details travel as the cause)."""
        details = self.error(method, **params).details
        return details.get('cause', details)['path']

    def test_add_creates_a_shared_text_and_a_placed_clip_in_one_undo_step(self):
        added = self.added
        self.assertEqual(added['style']['text'], 'Hello')
        self.assertEqual(added['style']['color'], '#ffff0000')
        self.assertEqual(added['style']['font_size'], 60)
        self.assertEqual(added['box']['height'], added['style']['height'])
        clip = self.clip()
        self.assertEqual(clip['file_id'], added['file_id'])
        self.assertEqual((clip['position'], clip['end'], clip['layer']), (2, 3, self.layer))
        self.assertEqual(clip['gravity'], openshot.GRAVITY_BOTTOM_LEFT)
        self.assertAlmostEqual(clip['location_y']['Points'][0]['co']['Y'], -0.15, places=5)
        self.assertEqual(clip['reader']['type'], 'QtTextReader')
        self.assertEqual(added['clip']['keyframe_properties'][0], 'text_color')
        self.call('history.undo')
        self.assertEqual(self.app.project.get('clips'), [])
        self.assertEqual(self.app.project.get('files'), [])

    def test_set_changes_every_clip_sharing_the_text_unless_this_clip_only(self):
        second = self.call('clip.add', file_id=self.added['file_id'], layer=self.layer, position=8)
        self.assertEqual(self.clip(second['id'])['direct_text']['text'], 'Hello')
        result = self.call('text.set', id=self.added['clip']['id'], text='Hi there', font_bold=True)
        self.assertEqual(sorted(result['changed_clip_ids']), sorted([self.added['clip']['id'], second['id']]))
        self.assertEqual(self.clip(second['id'])['direct_text']['text'], 'Hi there')
        self.assertTrue(self.clip(second['id'])['direct_text']['font_bold'])
        result = self.call('text.set', id=second['id'], color='blue', this_clip_only=True)
        self.assertEqual(result['changed_clip_ids'], [second['id']])
        self.assertNotEqual(self.clip(second['id'])['file_id'], self.added['file_id'])
        self.assertEqual(self.clip(second['id'])['direct_text']['color'], '#ff0000ff')
        self.assertEqual(self.clip()['direct_text']['color'], '#ffff0000')
        self.assertEqual(self.call('text.list')['total'], 2)
        self.call('history.undo')
        self.assertEqual(self.clip(second['id'])['file_id'], self.added['file_id'])

    def test_text_keyframes_are_clip_keyframes_and_win_over_the_shared_style(self):
        clip_id = self.added['clip']['id']
        self.call('clip.keyframe.set', id=clip_id, property='text_color.green', space='clip', unit='seconds', at=1, value=255)
        self.assertEqual(self.call('text.get', id=clip_id)['clip']['keyframed'], ['color'])
        self.assertIn('color', self.clip()['reader']['text_animation'])
        result = self.call('text.set', id=clip_id, color='white', stroke_width=2)
        self.assertEqual(result['keyframed_elsewhere'], {clip_id: ['color']})
        self.assertIn('--keyframes-only', result['hint'])
        self.call('text.reset', id=clip_id, keyframes_only=True)
        data = self.clip()
        self.assertEqual(data['text_style_overrides'], [])
        self.assertEqual(data['text_color']['green']['Points'][0]['co']['Y'], 255)
        self.assertEqual(data['direct_text']['stroke_width'], 2)  # Shared style is kept.
        self.call('text.reset', id=clip_id)
        self.assertEqual(self.clip()['direct_text']['stroke_width'], 0)
        self.assertEqual(self.clip()['direct_text']['text'], 'Hello')

    def test_line_spacing_and_corner_radius(self):
        clip_id = self.added['clip']['id']
        height = self.added['style']['height']
        result = self.call('text.set', id=clip_id, line_spacing=1.6, background_corner=18, text='One\nTwo')
        self.assertEqual((result['style']['line_spacing'], result['style']['background_corner']), (1.6, 18))
        self.assertEqual(self.clip()['reader']['line_spacing'], 1.6)
        self.assertGreater(result['style']['height'], height)
        # The radius animates per clip like the colors; line spacing cannot.
        self.call('clip.keyframe.set', id=clip_id, property='text_background_corner', space='clip', unit='seconds',
                  at=1, value=40)
        self.assertEqual(self.call('text.get', id=clip_id)['clip']['keyframed'], ['background_corner'])
        self.assertIn('background_corner', self.clip()['reader']['text_animation'])
        self.assertEqual(self.path('text.set', id=clip_id, line_spacing=0.2), 'params.line_spacing')
        self.assertEqual(self.path('text.set', id=clip_id, background_corner=-1), 'params.background_corner')
        self.assertEqual(self.error('clip.keyframe.set', id=clip_id, property='text_background_corner',
                                    at=1, value=-5).code, 'validation_error')
        error = self.error('clip.keyframe.set', id=clip_id, property='text_line_spacing', at=1, value=2)
        self.assertEqual(error.code, 'invalid_keyframe')
        self.assertIn('text set ID --line-spacing', error.details.get('cause', error.details)['hint'])

    def test_clear_errors_for_invalid_input(self):
        clip_id = self.added['clip']['id']
        error = self.error('text.set', id=clip_id, font_family='Noto Sanz')
        self.assertEqual(error.code, 'validation_error')
        self.assertEqual(error.details['cause']['path'], 'params.font_family')
        self.assertIn('text fonts', str(error))
        self.assertEqual(self.path('text.set', id=clip_id, color='#12'), 'params.color')
        self.assertEqual(self.path('text.set', id=clip_id, font_size=4), 'params.font_size')
        self.assertEqual(self.path('text.set', id=clip_id, font_bold='yes'), 'params.font_bold')
        self.assertEqual(self.error('text.set', id=clip_id, colour='red').code, 'validation_error')
        self.assertEqual(self.error('text.set', id=clip_id).code, 'invalid_argument')
        self.assertEqual(self.error('text.set', id=self.added['file_id'], place='top').code, 'invalid_argument')
        self.assertEqual(self.error('text.get', id='NOPE').code, 'not_found')
        self.assertEqual(self.error('text.add', text='x', layer=12345).code, 'invalid_layer')
        self.assertEqual(self.error('clip.set', id=clip_id, values={'direct_text': {}}).code, 'invalid_property')
        self.assertEqual(self.error('clip.keyframe.set', id=clip_id, property='text_color.red', at=1, value=300).code,
                         'validation_error')
        with tempfile.TemporaryDirectory() as temp:
            from qt_api import QImage, QColor
            from classes.agent.render import image_format
            image = QImage(16, 16, image_format())
            image.fill(QColor('red'))
            path = str(Path(temp) / 'red.png')
            image.save(path)
            media = self.call('file.import', path=path)
            video = self.call('clip.add', file_id=media['id'], layer=self.layer)
        self.assertEqual(self.error('text.get', id=video['id']).code, 'not_text')
        self.assertEqual(self.error('text.get', id=media['id']).code, 'not_text')
        layers = self.app.project.get('layers')
        layers[0]['lock'] = True
        self.assertEqual(self.error('text.set', id=clip_id, color='red').code, 'locked_track')

    def test_list_fonts_and_bulk_selection(self):
        self.call('text.add', text='Second title', layer=self.layer, position=6)
        self.assertEqual([row['text'] for row in self.call('text.list', search='second')['texts']], ['Second title'])
        page = self.call('text.list', limit=1)
        self.assertEqual((len(page['texts']), page['total'], page['next_offset']), (1, 2, 1))
        fonts = self.call('text.fonts', search=self.added['style']['font_family'][:4])
        self.assertIn(self.added['style']['font_family'], fonts['fonts'])
        selection = self.call('edit.select', selection={'text': True})
        self.assertEqual(selection['count'], 2)
        self.call('edit.bulk', selection={'text': True},
                  commands=[{'method': 'text.set', 'params': {'border_width': 3}}])
        self.assertTrue(all(c['direct_text']['border_width'] == 3 for c in self.app.project.get('clips')))

    def test_place_choices_match_the_cli(self):
        from cli import TEXT_PLACES
        from classes.agent.text import PLACES
        self.assertEqual(set(TEXT_PLACES), set(PLACES))
