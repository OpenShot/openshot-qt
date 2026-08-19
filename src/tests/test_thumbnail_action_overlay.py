"""
@file
@brief Tests for hover '+' button overlay and one-click timeline insertion for Effects and Transitions.
"""

import os
import sys
import types
import unittest

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_api import (
    QCoreApplication, Qt, QRect, QRectF, QPoint, QPointF,
    QApplication, QStandardItemModel, QStandardItem,
    QMouseEvent, QEvent, QPainter, QPixmap, QStyleOptionViewItem,
)

from tests.qt_test_app import ensure_app_state as ensure_qt_app_state, get_or_create_app
from windows.views.thumbnail_action_overlay import (
    get_thumbnail_decoration_rect,
    calculate_button_rect,
    paint_plus_overlay_button,
    ThumbnailActionDelegate,
    ThumbnailActionViewMixin,
)

QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)


class DummySettings:
    def __init__(self):
        self.values = {
            "default-profile": "HD 720p 30 fps",
            "default-samplerate": 48000,
            "default-channels": 2,
            "default-transition-length": 5.0,
        }

    def get(self, key):
        return self.values.get(key)


class DummyApp(QApplication):
    def __init__(self):
        super().__init__([])
        self.settings = DummySettings()
        self.window = None

    def get_settings(self):
        return self.settings

    def _tr(self, text):
        return text


def ensure_app_state(app):
    return ensure_qt_app_state(app, DummySettings)


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))


class ThumbnailActionOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app, cls._owns_app = get_or_create_app(DummyApp)
        cls.app = ensure_app_state(app)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_owns_app", False) and cls.app:
            cls.app.quit()

    def setUp(self):
        self.orig_window = getattr(self.app, "window", None)

    def tearDown(self):
        self.app.window = self.orig_window

    def test_calculate_button_rect(self):
        deco = QRectF(10, 20, 100, 60)
        btn = calculate_button_rect(deco, button_size=28.0)
        self.assertEqual(btn.width(), 28.0)
        self.assertEqual(btn.height(), 28.0)
        self.assertAlmostEqual(btn.center().x(), deco.center().x())
        self.assertAlmostEqual(btn.center().y(), deco.center().y())

        empty_btn = calculate_button_rect(QRectF())
        self.assertFalse(empty_btn.isValid())

    def test_paint_plus_overlay_button_executes_cleanly(self):
        pix = QPixmap(100, 100)
        painter = QPainter(pix)
        try:
            btn_rect = QRectF(20, 20, 28, 28)
            # Test all 3 visual states
            paint_plus_overlay_button(painter, btn_rect, is_button_hovered=False, is_button_pressed=False)
            paint_plus_overlay_button(painter, btn_rect, is_button_hovered=True, is_button_pressed=False)
            paint_plus_overlay_button(painter, btn_rect, is_button_hovered=True, is_button_pressed=True)
        finally:
            painter.end()

    def test_effects_listview_add_item_to_timeline_selected_clips(self):
        from windows.views.effects_listview import EffectsListView
        from windows.models.effects_model import EffectsModel
        from classes.query import Clip

        apply_effect_to_clip_rec = Recorder()
        timeline = types.SimpleNamespace(
            _apply_effect_to_clip=apply_effect_to_clip_rec,
        )

        win = types.SimpleNamespace(
            timeline=timeline,
            selected_clips=["clip-101"],
            effectsFilter=types.SimpleNamespace(
                text=lambda: "",
                textChanged=types.SimpleNamespace(connect=lambda fn: None),
            ),
            refreshEffectsSignal=types.SimpleNamespace(connect=lambda fn: None),
            actionEffectsShowAll=types.SimpleNamespace(isChecked=lambda: True),
            actionEffectsShowVideo=types.SimpleNamespace(isChecked=lambda: False),
        )
        self.app.window = win

        # Build mock model with row: [Thumb, Name, Desc, Category, Effect]
        model = EffectsModel()
        model.model.clear()
        row = [
            QStandardItem("Blur"),
            QStandardItem("Blur"),
            QStandardItem("Blur description"),
            QStandardItem("Video"),
            QStandardItem("Blur"),
        ]
        model.model.appendRow(row)

        view = EffectsListView(model)
        view.win = win

        # Proxy map index
        idx = model.list_proxy_model.index(0, 0)
        self.assertTrue(idx.isValid())

        # Mock Clip.get
        dummy_clip = types.SimpleNamespace(id="clip-101", data={"layer": 1, "position": 0.0})
        orig_get = Clip.get
        try:
            Clip.get = classmethod(lambda cls, id=None: dummy_clip if id == "clip-101" else None)
            view.add_item_to_timeline(idx)
        finally:
            Clip.get = orig_get

        self.assertEqual(len(apply_effect_to_clip_rec.calls), 1)
        self.assertEqual(apply_effect_to_clip_rec.calls[0][0], (dummy_clip, "Blur"))

    def test_effects_listview_add_item_to_timeline_playhead_clip(self):
        from windows.views.effects_listview import EffectsListView
        from windows.models.effects_model import EffectsModel
        from classes.query import Clip

        apply_effect_to_clip_rec = Recorder()
        timeline = types.SimpleNamespace(
            _apply_effect_to_clip=apply_effect_to_clip_rec,
        )

        win = types.SimpleNamespace(
            timeline=timeline,
            selected_clips=[],
            _current_timeline_seconds=lambda: 3.5,
            effectsFilter=types.SimpleNamespace(
                text=lambda: "",
                textChanged=types.SimpleNamespace(connect=lambda fn: None),
            ),
            refreshEffectsSignal=types.SimpleNamespace(connect=lambda fn: None),
            actionEffectsShowAll=types.SimpleNamespace(isChecked=lambda: True),
            actionEffectsShowVideo=types.SimpleNamespace(isChecked=lambda: False),
        )
        self.app.window = win

        model = EffectsModel()
        model.model.clear()
        row = [
            QStandardItem("Color"),
            QStandardItem("Color"),
            QStandardItem("Color description"),
            QStandardItem("Video"),
            QStandardItem("Color"),
        ]
        model.model.appendRow(row)

        view = EffectsListView(model)
        view.win = win

        idx = model.list_proxy_model.index(0, 0)
        self.assertTrue(idx.isValid())

        clip_low = types.SimpleNamespace(id="c-low", data={"layer": 1, "position": 0.0, "start": 0.0, "end": 10.0})
        clip_high = types.SimpleNamespace(id="c-high", data={"layer": 3, "position": 2.0, "start": 0.0, "end": 8.0})

        orig_filter = Clip.filter
        try:
            Clip.filter = classmethod(lambda cls, intersect=None: [clip_low, clip_high] if intersect == 3.5 else [])
            view.add_item_to_timeline(idx)
        finally:
            Clip.filter = orig_filter

        self.assertEqual(len(apply_effect_to_clip_rec.calls), 1)
        # Should pick the top-most layer (c-high on layer 3)
        self.assertEqual(apply_effect_to_clip_rec.calls[0][0], (clip_high, "Color"))

    def test_transitions_listview_add_item_to_timeline(self):
        from windows.views.transitions_listview import TransitionsListView
        from windows.models.transition_model import TransitionsModel

        add_trans_rec = Recorder()
        select_added_rec = Recorder()
        timeline = types.SimpleNamespace(
            addTransition=add_trans_rec,
            _select_added_items=select_added_rec,
            _nearest_unlocked_track_number=lambda track: track,
            track_list=[types.SimpleNamespace(data={"number": 2})],
        )

        win = types.SimpleNamespace(
            timeline=timeline,
            selected_clips=[],
            selected_transitions=[],
            _current_timeline_seconds=lambda: 4.0,
            transitionsFilter=types.SimpleNamespace(
                text=lambda: "",
                textChanged=types.SimpleNamespace(connect=lambda fn: None),
            ),
            refreshTransitionsSignal=types.SimpleNamespace(connect=lambda fn: None),
            actionTransitionsShowCommon=types.SimpleNamespace(isChecked=lambda: False),
        )
        self.app.window = win

        model = TransitionsModel()
        model.model.clear()
        row = [
            QStandardItem("Fade In"),
            QStandardItem("Fade In"),
            QStandardItem("common"),
            QStandardItem("/dummy/path/fade.svg"),
        ]
        model.model.appendRow(row)

        view = TransitionsListView(model)
        view.win = win

        idx = model.list_proxy_model.index(0, 0)
        self.assertTrue(idx.isValid())

        add_trans_rec.calls.clear()
        def mock_add_trans(path, pos, track, ignore_refresh=False, call_manual_move=False):
            return {"id": "T1", "layer": track, "position": pos.x()}
        timeline.addTransition = mock_add_trans

        view.add_item_to_timeline(idx)

        self.assertEqual(select_added_rec.calls, [(("transition",), {})])

    def test_view_mixin_mouse_events(self):
        from windows.views.effects_listview import EffectsListView
        from windows.models.effects_model import EffectsModel

        win = types.SimpleNamespace(
            timeline=types.SimpleNamespace(_apply_effect_to_clip=Recorder()),
            selected_clips=[],
            effectsFilter=types.SimpleNamespace(
                text=lambda: "",
                textChanged=types.SimpleNamespace(connect=lambda fn: None),
            ),
            refreshEffectsSignal=types.SimpleNamespace(connect=lambda fn: None),
            actionEffectsShowAll=types.SimpleNamespace(isChecked=lambda: True),
            actionEffectsShowVideo=types.SimpleNamespace(isChecked=lambda: False),
        )
        self.app.window = win

        model = EffectsModel()
        model.model.clear()
        row = [
            QStandardItem("Blur"),
            QStandardItem("Blur"),
            QStandardItem("Blur description"),
            QStandardItem("Video"),
            QStandardItem("Blur"),
        ]
        model.model.appendRow(row)

        view = EffectsListView(model)
        view.win = win
        added_items = []
        view.add_item_to_timeline = lambda idx: added_items.append(idx)

        idx = model.list_proxy_model.index(0, 0)
        # Mock indexAt and _button_rect_for_index
        view.indexAt = lambda pos: idx if pos.x() < 100 else model.list_proxy_model.index(-1, -1)
        btn_rect = QRectF(30, 20, 28, 28)
        view._button_rect_for_index = lambda i: btn_rect

        # 1. Mouse move inside button
        move_event = QMouseEvent(QEvent.MouseMove, QPointF(40, 30), Qt.NoButton, Qt.NoButton, Qt.NoModifier)
        view.mouseMoveEvent(move_event)
        self.assertTrue(view._button_hovered)
        self.assertEqual(view.cursor().shape(), Qt.PointingHandCursor)

        # 2. Mouse move outside button but on item
        move_event2 = QMouseEvent(QEvent.MouseMove, QPointF(5, 5), Qt.NoButton, Qt.NoButton, Qt.NoModifier)
        view.mouseMoveEvent(move_event2)
        self.assertFalse(view._button_hovered)
        self.assertNotEqual(view.cursor().shape(), Qt.PointingHandCursor)

        # 3. Mouse press on button
        press_event = QMouseEvent(QEvent.MouseButtonPress, QPointF(40, 30), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        view.mousePressEvent(press_event)
        self.assertTrue(view._button_pressed)

        # 4. Mouse release on button triggers add_item_to_timeline
        release_event = QMouseEvent(QEvent.MouseButtonRelease, QPointF(40, 30), Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
        view.mouseReleaseEvent(release_event)
        self.assertFalse(view._button_pressed)
        self.assertEqual(len(added_items), 1)

        # 5. Leave event clears hover
        leave_event = QEvent(QEvent.Leave)
        view.leaveEvent(leave_event)
        self.assertIsNone(view._hovered_index)
        self.assertFalse(view._button_hovered)

    def test_emoji_list_view_add_item_to_timeline(self):
        from windows.views.emojis_listview import EmojisListView
        from windows.models.emoji_model import EmojisModel

        add_clip_rec = Recorder()
        select_added_rec = Recorder()
        timeline = types.SimpleNamespace(
            addClip=add_clip_rec,
            _select_added_items=select_added_rec,
            _nearest_unlocked_track_number=lambda t: t,
            track_list=[types.SimpleNamespace(data={"number": 2})],
        )

        win = types.SimpleNamespace(
            timeline=timeline,
            selected_clips=[],
            selected_transitions=[],
            _current_timeline_seconds=lambda: 3.5,
            emojisFilter=types.SimpleNamespace(
                text=lambda: "",
                textChanged=types.SimpleNamespace(connect=lambda fn: None),
            ),
            emojiFilterGroup=types.SimpleNamespace(
                clear=lambda: None,
                addItem=lambda *a: None,
                currentIndexChanged=types.SimpleNamespace(connect=lambda fn: None),
                setCurrentIndex=lambda i: None,
            ),
            statusBar=types.SimpleNamespace(showMessage=lambda msg, timeout=0: None),
        )
        self.app.window = win

        model = EmojisModel()
        model.model.clear()
        col = QStandardItem("Smile")
        col.setData("/dummy/path/smile.svg")
        model.model.appendRow([
            col,
            QStandardItem("Smileys"),
            QStandardItem("smileys-emotion"),
        ])

        view = EmojisListView(model)
        view.win = win
        view.add_file = lambda path, name: types.SimpleNamespace(id="F_EMOJI", absolute_path=lambda: path, data={"path": path})

        idx = model.proxy_model.index(0, 0)
        self.assertTrue(idx.isValid())

        def mock_add_clip(file_id, pos, track, ignore_refresh=False, call_manual_move=False, auto_transition=False):
            return {"id": "C_EMOJI", "layer": track, "position": pos.x()}
        timeline.addClip = mock_add_clip

        view.add_item_to_timeline(idx)
        self.assertEqual(select_added_rec.calls, [(("clip",), {})])


if __name__ == "__main__":
    unittest.main()

