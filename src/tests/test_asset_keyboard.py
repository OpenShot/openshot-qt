"""Asset browser focus and keyboard application without mouse positioning."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from qt_api import (Qt, QMainWindow, QDockWidget, QListView, QLineEdit,
                    QStandardItemModel, QStandardItem, QMimeData, QItemSelectionModel)
from classes.asset_keyboard import AssetKeyboardMixin
from classes.query import Clip
from classes.keyboard_shortcuts import migrate_timeline_shortcuts
from tests.qt_test_app import get_or_create_app
from tests.test_main_window import DummyApp, ensure_app_state


class AssetModel(QStandardItemModel):
    def mimeData(self, indexes):
        mime = QMimeData()
        mime.setText(json.dumps([index.data(Qt.UserRole) for index in indexes]))
        return mime


class AssetWindow(AssetKeyboardMixin, QMainWindow):
    pass


class AssetKeyboardTests(unittest.TestCase):
    def setUp(self):
        self.app, _ = get_or_create_app(DummyApp)
        ensure_app_state(self.app)
        self.window = AssetWindow()
        self.window.setCentralWidget(QLineEdit())
        self.models = []
        for dock_name, view_name in (('dockFiles', 'filesView'), ('dockEffects', 'effectsView'),
                                    ('dockTransitions', 'transitionsView'), ('dockEmojis', 'emojiListView')):
            dock = QDockWidget(dock_name, self.window)
            view = QListView()
            view.setSelectionMode(QListView.ExtendedSelection)
            model = AssetModel()
            for value in ('first', 'second'):
                item = QStandardItem(value)
                item.setData(value, Qt.UserRole)
                model.appendRow(item)
            self.models.append(model)
            view.setModel(model)
            dock.setWidget(view)
            self.window.addDockWidget(Qt.LeftDockWidgetArea, dock)
            setattr(self.window, dock_name, dock)
            setattr(self.window, view_name, view)
        self.window.tabifyDockWidget(self.window.dockFiles, self.window.dockEffects)
        self.window.selected_clips = ['selected']
        self.window.preview_thread = SimpleNamespace(current_frame=61)
        self.window.addSelection = Mock()
        self.window._asset_message = Mock()
        timeline = Mock()
        timeline.item_ids = ['existing-drag-id']
        timeline._keyboard_layer = None
        timeline._keyboard_anchor.return_value = SimpleNamespace(data={'layer': 2})
        timeline.track_list = [SimpleNamespace(data={'number': n}) for n in (3, 2, 1)]
        timeline._is_track_locked.return_value = False
        self.created = []
        self.transactions = []
        self.updates = SimpleNamespace(transaction_id=None)
        def add(asset, pos, layer, **kwargs):
            self.transactions.append(self.updates.transaction_id)
            item = dict(id='added-' + asset, position=pos.x(), layer=layer, start=1, end=3)
            self.created.append(item)
            return item
        timeline.addClip.side_effect = add
        timeline.addTransition.side_effect = add
        self.window.timeline = timeline
        self.project = Mock()
        self.project.get.return_value = {'num': 30, 'den': 1}
        patcher = patch('classes.asset_keyboard.get_app', return_value=SimpleNamespace(
            updates=self.updates, project=self.project, _tr=lambda text: text))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.window.resize(800, 600)
        self.window.show()
        self.window.activateWindow()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_focus_shortcuts_reveal_hidden_docks_and_enter_asset_list(self):
        for method, view_name, dock_name in (
            ('focusProjectFiles', 'filesView', 'dockFiles'),
            ('focusEffects', 'effectsView', 'dockEffects'),
            ('focusTransitions', 'transitionsView', 'dockTransitions'),
            ('focusEmojis', 'emojiListView', 'dockEmojis'),
        ):
            with self.subTest(method=method):
                getattr(self.window, dock_name).hide()
                getattr(self.window, method)()
                self.app.processEvents()
                view = getattr(self.window, view_name)
                self.assertTrue(view.hasFocus())
                self.assertEqual(view.currentIndex().row(), 0)
        self.assertEqual(self.window.selected_clips, ['selected'])

    def test_multiple_files_follow_browser_order_and_keep_focus(self):
        w = self.window
        w.focusProjectFiles()
        view = w.filesView
        view.selectionModel().select(self.models[0].index(1, 0), QItemSelectionModel.Select)
        w.addSelectedAsset()
        self.assertEqual([c['id'] for c in self.created], ['added-first', 'added-second'])
        self.assertEqual([c['position'] for c in self.created], [2, 4])
        self.assertEqual([c['layer'] for c in self.created], [2, 2])
        self.assertTrue(view.hasFocus())
        self.assertEqual(len(view.selectionModel().selectedRows()), 2)
        self.assertEqual(len(set(self.transactions)), 1)
        self.assertIsNotNone(self.transactions[0])
        self.assertIsNone(self.updates.transaction_id)
        self.assertEqual(w.timeline.item_ids, ['existing-drag-id'])
        w.timeline.addClip.assert_called_with('second', unittest.mock.ANY, 2,
                                             call_manual_move=False, auto_transition=False)

    def test_emoji_import_and_clip_share_transaction_and_default_creation_path(self):
        w = self.window
        w.focusEmojis()
        view = w.emojiListView
        model = self.models[3]
        model.mapToSource = lambda index: index
        view.group_model = SimpleNamespace(mapToSource=lambda index: index)
        view.emojis_model = SimpleNamespace(model=model)
        imported_transactions = []
        def add_file(path, name):
            self.assertEqual((path, name), ('first', 'first'))
            imported_transactions.append(self.updates.transaction_id)
            return SimpleNamespace(id='emoji-file')
        view.add_file = Mock(side_effect=add_file)
        w.addSelectedAsset()
        self.assertEqual(self.created[0]['id'], 'added-emoji-file')
        self.assertEqual(imported_transactions, self.transactions)
        self.assertTrue(view.hasFocus())
        w.timeline._is_track_locked.return_value = True
        w.addSelectedAsset()
        view.add_file.assert_called_once()

    def test_track_fallback_remembers_destination_and_skips_locked_default(self):
        timeline = self.window.timeline
        timeline._keyboard_anchor.return_value = None
        timeline._keyboard_layer = None
        timeline._is_track_locked.side_effect = lambda layer: layer == 3
        self.window.focusProjectFiles()
        self.assertEqual(timeline._asset_target_layer, 2)
        timeline._keyboard_layer = 1
        self.window.focusTransitions()
        self.assertEqual(timeline._asset_target_layer, 1)

    def test_configured_panel_shortcuts_and_ctrl_enter(self):
        from pathlib import Path
        import importlib
        from qt_api import QT_API, QShortcut, QKeySequence
        binding = {'pyqt5': 'PyQt5', 'pyqt6': 'PyQt6', 'pyside6': 'PySide6'}[QT_API]
        QTest = importlib.import_module(binding + '.QtTest').QTest
        defaults = json.loads((Path(__file__).parents[1] / 'settings/_default.settings').read_text())
        values = {item['setting']: item['value'] for item in defaults}
        shortcuts = []
        for name in ('focusProjectFiles', 'focusTransitions', 'focusEffects', 'focusEmojis', 'addSelectedAsset'):
            for sequence in values[name].split('|'):
                shortcuts.append(QShortcut(QKeySequence(sequence.strip()), self.window,
                                           activated=getattr(self.window, name)))
        self.window.focusProjectFiles()
        self.app.processEvents()
        for key, view_name in ((Qt.Key_7, 'transitionsView'), (Qt.Key_8, 'effectsView'),
                               (Qt.Key_9, 'emojiListView'), (Qt.Key_1, 'filesView')):
            QTest.keyClick(self.app.focusWidget(), key, Qt.ShiftModifier)
            self.app.processEvents()
            self.assertTrue(getattr(self.window, view_name).hasFocus(), view_name)
        QTest.keyClick(self.app.focusWidget(), Qt.Key_Return, Qt.ControlModifier)
        self.assertEqual(len(self.created), 1)
        QTest.keyClick(self.app.focusWidget(), Qt.Key_Enter, Qt.ControlModifier)
        self.assertEqual(len(self.created), 2)

    def test_transition_added_at_playhead_and_locked_track_blocks_add(self):
        w = self.window
        w.focusTransitions()
        w.addSelectedAsset()
        self.assertEqual(self.created[0]['position'], 2)
        w.timeline.addTransition.assert_called_once()
        w.timeline._is_track_locked.return_value = True
        w.addSelectedAsset()
        w.timeline.addTransition.assert_called_once()
        w._asset_message.assert_called_once()

    def test_effect_applies_to_selected_clips_and_preserves_selection(self):
        w = self.window
        w.focusEffects()
        w.selected_clips = ['a', 'b']
        clips = [SimpleNamespace(id=identity, data={'layer': 2}) for identity in w.selected_clips]
        with patch.object(Clip, 'get', side_effect=clips):
            w.addSelectedAsset()
        self.assertEqual(w.timeline._apply_effect_to_clip.call_count, 2)
        self.assertEqual(w.selected_clips, ['a', 'b'])
        w.addSelection.assert_not_called()
        self.assertTrue(w.effectsView.hasFocus())
        w.selected_clips = []
        w.addSelectedAsset()
        w._asset_message.assert_called_once()

    def test_typing_elsewhere_does_not_add_selected_assets(self):
        self.window.focusProjectFiles()
        self.window.centralWidget().setFocus()
        self.window.addSelectedAsset()
        self.assertEqual(self.created, [])

    def test_transaction_restored_after_failed_add(self):
        w = self.window
        w.focusProjectFiles()
        self.updates.transaction_id = 'outer'
        w.timeline.addClip.side_effect = RuntimeError('reader failure')
        with self.assertRaises(RuntimeError):
            w.addSelectedAsset()
        self.assertEqual(self.updates.transaction_id, 'outer')
        self.assertEqual(w.timeline.item_ids, ['existing-drag-id'])

    def test_version_one_settings_gain_asset_keys_without_overwriting_customizations(self):
        from pathlib import Path
        defaults = json.loads((Path(__file__).parents[1] / 'settings/_default.settings').read_text())
        saved = [{'setting': 'timeline-keyboard-version', 'value': 1},
                 {'setting': 'timelineSelectNext', 'value': 'Alt+N'},
                 {'setting': 'actionAbout', 'value': 'Shift+1'}]
        migrated = migrate_timeline_shortcuts(defaults, saved)
        values = {item['setting']: item['value'] for item in migrated}
        self.assertEqual(values['timelineSelectNext'], 'Alt+N')
        self.assertEqual(values['actionAbout'], 'Shift+1')
        self.assertNotEqual(values['focusProjectFiles'], 'Shift+1')
        self.assertEqual(values['focusEffects'], 'Shift+8')
        self.assertEqual(values['timeline-keyboard-version'], 3)
        self.assertEqual(migrate_timeline_shortcuts(defaults, migrated), migrated)

    def test_initial_asset_defaults_migrate_to_requested_panel_order(self):
        from pathlib import Path
        defaults = json.loads((Path(__file__).parents[1] / 'settings/_default.settings').read_text())
        saved = [{'setting': 'timeline-keyboard-version', 'value': 2},
                 {'setting': 'focusEffects', 'value': 'Shift+7'},
                 {'setting': 'focusTransitions', 'value': 'Shift+8'}]
        values = {item['setting']: item['value'] for item in migrate_timeline_shortcuts(defaults, saved)}
        self.assertEqual(values['focusTransitions'], 'Shift+7')
        self.assertEqual(values['focusEffects'], 'Shift+8')
        saved[1]['value'] = 'Alt+E'
        values = {item['setting']: item['value'] for item in migrate_timeline_shortcuts(defaults, saved)}
        self.assertEqual(values['focusEffects'], 'Alt+E')
