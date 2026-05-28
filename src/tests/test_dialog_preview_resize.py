import os
import sys
import types
import unittest
import json
from unittest.mock import patch

from qt_api import QRect, QSize
from qt_api import QApplication
import openshot


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

TEST_MEDIA_ROOT = os.path.join(os.sep, "mock-media")

from tests.qt_test_app import ensure_app_state, get_or_create_app


class DummySettings:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key, False)

    def set(self, key, value):
        self.values[key] = value


class DummyApp(QApplication):
    def __init__(self):
        super().__init__([])
        self.settings = DummySettings()


app, _owns_app = get_or_create_app(DummyApp)
ensure_app_state(app, DummySettings, extra_attrs={"window": types.SimpleNamespace()})

from windows.cutting import Cutting
from windows.region import SelectRegion
from windows.preview_thread import PlayerWorker
from windows.video_widget import VideoWidget


class DummySignal:
    def __init__(self):
        self.calls = 0

    def emit(self, *args):
        self.calls += 1

    def connect(self, *args, **kwargs):
        return None


class DummyVideoPreview:
    def __init__(self, viewport):
        self._viewport = viewport
        self.aspect_ratio = None

    def centeredViewport(self, width, height):
        _ = (width, height)
        return self._viewport

    def width(self):
        return self._viewport.width()

    def height(self):
        return self._viewport.height()


class DummyFraction:
    def __init__(self, num, den):
        self.num = num
        self.den = den

    def Reduce(self):
        return None


class DialogPreviewResizeTests(unittest.TestCase):
    def test_cutting_preview_window_title_prefers_friendly_name(self):
        title = Cutting._preview_window_title(
            types.SimpleNamespace(data={"name": "My Friendly File", "path": os.path.join(TEST_MEDIA_ROOT, "raw-name.mp4")}),
            lambda text: text,
        )

        self.assertEqual(title, "Preview: My Friendly File")

    def test_cutting_preview_window_title_falls_back_to_plain_preview(self):
        title = Cutting._preview_window_title(
            types.SimpleNamespace(data={"name": "", "path": ""}),
            lambda text: text,
        )

        self.assertEqual(title, "Preview")

    def test_cutting_select_reader_data_uses_proxy_when_target_fits(self):
        proxy = {"path": "/proxy.mp4", "width": 1280, "height": 720}
        source = {"path": "/source.mp4", "width": 3840, "height": 2160}
        fake = types.SimpleNamespace(
            proxy_reader_data=proxy,
            source_reader_data=source,
            _reader_capacity=lambda data: Cutting._reader_capacity(None, data),
        )

        reader_data = Cutting._select_reader_data_for_size(fake, QSize(960, 540))

        self.assertEqual(reader_data, proxy)

    def test_cutting_select_reader_data_promotes_to_source_when_proxy_too_small(self):
        proxy = {"path": "/proxy.mp4", "width": 1280, "height": 720}
        source = {"path": "/source.mp4", "width": 3840, "height": 2160}
        fake = types.SimpleNamespace(
            proxy_reader_data=proxy,
            source_reader_data=source,
            _reader_capacity=lambda data: Cutting._reader_capacity(None, data),
        )

        reader_data = Cutting._select_reader_data_for_size(fake, QSize(1920, 1080))

        self.assertEqual(reader_data, proxy)

    def test_cutting_target_preview_max_size_caps_to_reader_resolution(self):
        fake = types.SimpleNamespace(
            videoPreview=DummyVideoPreview(QRect(0, 0, 2400, 1350)),
            devicePixelRatioF=lambda: 1.0,
            width=1280,
            height=720,
        )

        size = Cutting._target_preview_max_size(fake)

        self.assertEqual(size, QSize(1280, 720))

    def test_region_target_preview_max_size_scales_with_viewport(self):
        fake = types.SimpleNamespace(
            videoPreview=DummyVideoPreview(QRect(0, 0, 900, 500)),
            devicePixelRatioF=lambda: 1.0,
            width=1920,
            height=1080,
        )

        size = SelectRegion._target_preview_max_size(fake)

        self.assertEqual(size, QSize(900, 500))

    def test_cutting_target_preview_max_size_uses_project_floor_for_single_image_media(self):
        fake = types.SimpleNamespace(
            videoPreview=DummyVideoPreview(QRect(0, 0, 900, 500)),
            devicePixelRatioF=lambda: 1.0,
            width=64,
            height=64,
            reader_data={"media_type": "image"},
            file=types.SimpleNamespace(data={"media_type": "image"}),
        )
        fake_app = types.SimpleNamespace(project=types.SimpleNamespace(get=lambda key: {"width": 1920, "height": 1080}.get(key, 0)))

        with patch("windows.cutting.get_app", return_value=fake_app):
            size = Cutting._target_preview_max_size(fake)

        self.assertEqual(size, QSize(900, 500))

    def test_cutting_apply_dynamic_preview_max_size_refreshes_when_size_changes(self):
        calls = []
        timeline = types.SimpleNamespace(
            preview_width=320,
            preview_height=180,
            SetMaxSize=lambda w, h: calls.append(("set", w, h)),
            ClearAllCache=lambda deep: calls.append(("clear", deep)),
        )
        fake = types.SimpleNamespace(
            initialized=True,
            r=timeline,
            _target_preview_max_size=lambda: QSize(640, 360),
            _select_reader_data_for_size=lambda size: {"path": "/source.mp4"},
            reader_data={"path": "/source.mp4"},
            PauseSignal=DummySignal(),
            refreshFrameSignal=DummySignal(),
        )

        Cutting._apply_dynamic_preview_max_size(fake)

        self.assertEqual(fake.PauseSignal.calls, 1)
        self.assertEqual(fake.refreshFrameSignal.calls, 1)
        self.assertEqual(calls, [("set", 640, 360), ("clear", True)])

    def test_cutting_apply_dynamic_preview_max_size_resumes_playback_when_was_playing(self):
        calls = []
        timeline = types.SimpleNamespace(
            preview_width=320,
            preview_height=180,
            SetMaxSize=lambda w, h: calls.append(("set", w, h)),
            ClearAllCache=lambda deep: calls.append(("clear", deep)),
        )
        player = types.SimpleNamespace(
            Mode=lambda: openshot.PLAYBACK_PLAY,
            Speed=lambda: 1.0,
        )
        fake = types.SimpleNamespace(
            initialized=True,
            r=timeline,
            preview_thread=types.SimpleNamespace(player=player),
            _target_preview_max_size=lambda: QSize(640, 360),
            _select_reader_data_for_size=lambda size: {"path": "/source.mp4"},
            reader_data={"path": "/source.mp4"},
            PauseSignal=DummySignal(),
            refreshFrameSignal=DummySignal(),
        )
        play_calls = []
        fake.btnPlay_clicked = lambda force=None: play_calls.append(force)

        with patch("windows.cutting.QTimer.singleShot", side_effect=lambda delay, fn: fn()):
            Cutting._apply_dynamic_preview_max_size(fake)

        self.assertEqual(fake.PauseSignal.calls, 1)
        self.assertEqual(fake.refreshFrameSignal.calls, 1)
        self.assertEqual(play_calls, ["play"])

    def test_cutting_preview_ready_seeks_frame_one_without_preroll(self):
        seek_calls = []
        fake = types.SimpleNamespace(
            is_preview_mode=True,
            preview_thread=types.SimpleNamespace(Seek=lambda frame, start_preroll=True: seek_calls.append((frame, start_preroll))),
            _preview_autoplay_active=False,
            SeekSignal=DummySignal(),
        )

        Cutting._preview_ready(fake)

        self.assertEqual(seek_calls, [(1, False)])

    def test_player_worker_play_honors_pending_seek_preroll_flag(self):
        applied = []
        player = types.SimpleNamespace(Play=lambda: applied.append(("play",)))
        worker = types.SimpleNamespace(
            parent=types.SimpleNamespace(initialized=True),
            player=player,
            _take_pending_seek=lambda: (1, False),
            _apply_seek=lambda frame, start_preroll: applied.append((frame, start_preroll)),
        )

        PlayerWorker.Play(worker)

        self.assertEqual(applied, [(1, False), ("play",)])

    def test_video_widget_resize_event_skips_pause_for_dialog_preview(self):
        pause_calls = []
        timer_calls = []
        fake = types.SimpleNamespace(
            delayed_size=None,
            size=lambda: QSize(640, 360),
            delayed_resize_timer=types.SimpleNamespace(start=lambda: timer_calls.append("start")),
            watch_project=False,
            win=types.SimpleNamespace(PauseSignal=types.SimpleNamespace(emit=lambda: pause_calls.append("pause"))),
        )
        event = types.SimpleNamespace(accept=lambda: None)

        VideoWidget.resizeEvent(fake, event)

        self.assertEqual(timer_calls, ["start"])
        self.assertEqual(pause_calls, [])

    def test_video_widget_init_preserves_dialog_watch_project_flag(self):
        fake_updates = types.SimpleNamespace(add_listener=lambda listener: None)
        fake_window = types.SimpleNamespace(
            PlaySignal=DummySignal(),
            PauseSignal=DummySignal(),
            SpeedSignal=DummySignal(),
            StopSignal=DummySignal(),
            TransformSignal=DummySignal(),
            KeyFrameTransformSignal=DummySignal(),
            SelectRegionSignal=DummySignal(),
            refreshFrameSignal=DummySignal(),
        )
        fake_app = types.SimpleNamespace(
            _tr=lambda text: text,
            get_settings=DummySettings,
            updates=fake_updates,
            window=fake_window,
        )

        with patch("windows.video_widget.get_app", return_value=fake_app):
            widget = VideoWidget(watch_project=False)

        try:
            self.assertFalse(widget.watch_project)
        finally:
            widget.deleteLater()

    def test_cutting_build_preview_timeline_uses_source_dimensions(self):
        timeline_args = []
        timeline_setmax = []

        class FakeTimeline:
            def __init__(self, width, height, fps, sample_rate, channels, channel_layout):
                timeline_args.append((width, height, fps, sample_rate, channels, channel_layout))
                self.info = types.SimpleNamespace()

            def SetMaxSize(self, width, height):
                timeline_setmax.append((width, height))

            def AddClip(self, clip):
                self.clip = clip

            def Open(self):
                pass

        class FakeClipReaderInfo:
            has_video = True
            has_audio = False

        class FakeClipReader:
            info = FakeClipReaderInfo()

        class FakeClip:
            def __init__(self, path):
                self.path = path
                self.reader = FakeClipReader()
                self.display = None

            def SetJson(self, payload):
                self.payload = payload

            def Open(self):
                pass

            def Start(self, value):
                self.start = value

            def End(self, value):
                self.end = value

            def Reader(self):
                return self.reader

        fake = types.SimpleNamespace(
            width=3840,
            height=2160,
            fps_num=30,
            fps_den=1,
            sample_rate=48000,
            channels=2,
            channel_layout=3,
            file=types.SimpleNamespace(absolute_path=lambda: "/source.mp4", data={"start": 0.0, "duration": 5.0}),
            videoPreview=DummyVideoPreview(QRect(0, 0, 640, 360)),
            video_length=150,
            source_reader_data={"path": "/source.mp4"},
            proxy_reader_data={"path": ""},
        )
        fake_app = types.SimpleNamespace(project=types.SimpleNamespace(get=lambda key: {
            "sample_rate": 44100,
            "channels": 2,
            "channel_layout": 3,
        }.get(key, 0)))

        with patch("windows.cutting.openshot.Timeline", FakeTimeline), \
             patch("windows.cutting.openshot.Clip", FakeClip), \
             patch("windows.cutting.openshot.Fraction", DummyFraction), \
             patch("windows.cutting.openshot.FRAME_DISPLAY_CLIP", 7), \
             patch("windows.cutting.get_app", return_value=fake_app):
            Cutting._build_preview_timeline(fake, {"path": "/source.mp4"}, QSize(640, 360))

        self.assertEqual(timeline_args[0][0:2], (3840, 2160))
        self.assertEqual(timeline_args[0][3:6], (44100, 2, 3))
        self.assertEqual(timeline_setmax, [(640, 360)])
        self.assertEqual(json.loads(fake.clip.payload), {
            "reader_orientation_mode": "reader",
            "reader": {"path": "/source.mp4"},
        })

    def test_cutting_build_preview_timeline_uses_project_floor_for_single_image_media(self):
        timeline_args = []
        clip_payloads = []

        class FakeTimeline:
            def __init__(self, width, height, fps, sample_rate, channels, channel_layout):
                timeline_args.append((width, height, fps, sample_rate, channels, channel_layout))
                self.info = types.SimpleNamespace()

            def SetMaxSize(self, width, height):
                self.max_size = (width, height)

            def AddClip(self, clip):
                self.clip = clip

            def Open(self):
                pass

        class FakeClipReaderInfo:
            has_video = True
            has_audio = False

        class FakeClipReader:
            info = FakeClipReaderInfo()

        class FakeClip:
            def __init__(self, path):
                self.path = path
                self.reader = FakeClipReader()
                self.display = None

            def SetJson(self, payload):
                clip_payloads.append(payload)
                self.payload = payload

            def Open(self):
                pass

            def Start(self, value):
                self.start = value

            def End(self, value):
                self.end = value

            def Reader(self):
                return self.reader

        fake = types.SimpleNamespace(
            width=64,
            height=64,
            fps_num=30,
            fps_den=1,
            sample_rate=48000,
            channels=2,
            channel_layout=3,
            file=types.SimpleNamespace(
                absolute_path=lambda: "/emoji.svg",
                data={"start": 0.0, "duration": 5.0, "media_type": "image"},
            ),
            videoPreview=DummyVideoPreview(QRect(0, 0, 640, 360)),
            video_length=150,
            source_reader_data={"path": "/emoji.svg", "media_type": "image"},
            proxy_reader_data={"path": ""},
        )
        fake_app = types.SimpleNamespace(project=types.SimpleNamespace(get=lambda key: {"width": 1920, "height": 1080}.get(key, 0)))

        with patch("windows.cutting.openshot.Timeline", FakeTimeline), \
             patch("windows.cutting.openshot.Clip", FakeClip), \
             patch("windows.cutting.openshot.Fraction", DummyFraction), \
             patch("windows.cutting.openshot.FRAME_DISPLAY_CLIP", 7), \
             patch("windows.cutting.get_app", return_value=fake_app):
            Cutting._build_preview_timeline(fake, {"path": "/emoji.svg", "media_type": "image"}, QSize(640, 360))

        self.assertEqual(timeline_args[0][0:2], (1920, 1080))
        self.assertEqual(clip_payloads, [])


if __name__ == "__main__":
    unittest.main()
