"""Export profile discovery when the optional user directory is missing."""

import os
import importlib
import sys
from pathlib import Path
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

class ExportProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        metrics = ModuleType("classes.metrics")
        metrics.track_metric_screen = Mock()
        metrics.track_metric_error = Mock()
        with patch.dict(sys.modules, {"classes.metrics": metrics}):
            cls.export = importlib.import_module("windows.export")

    def test_idle_dialog_does_not_release_resources(self):
        dialog = SimpleNamespace(_export_resources_claimed=False)
        with patch.object(self.export, "get_app") as get_app:
            self.export.Export.release_export_resources(dialog)
        get_app.assert_not_called()

    def test_export_resources_are_claimed_once_and_restored_once(self):
        old_cache, export_thread, small_cache = Mock(), Mock(), Mock()
        window = SimpleNamespace(cache_object=old_cache, timeline_sync=Mock())
        settings = SimpleNamespace(HIGH_QUALITY_SCALING=False)
        dialog = SimpleNamespace(_export_resources_claimed=False,
                                 cache_thread=None, old_cache_object=None)
        with patch.object(self.export, "get_app", return_value=SimpleNamespace(window=window)), \
                patch.object(self.export.openshot, "Settings") as native_settings, \
                patch.object(self.export.openshot, "CacheMemory", return_value=small_cache) as cache, \
                patch.object(self.export.openshot, "VideoCacheThread", return_value=export_thread) as thread:
            native_settings.Instance.return_value = settings
            self.export.Export.claim_export_resources(dialog)
            self.export.Export.claim_export_resources(dialog)
            self.assertTrue(settings.HIGH_QUALITY_SCALING)
            self.assertIs(window.cache_object, small_cache)
            cache.assert_called_once_with(1 * 1024 * 1024)
            thread.assert_called_once_with()
            old_cache.Clear.assert_called_once_with()
            self.export.Export.release_export_resources(dialog)
            self.export.Export.release_export_resources(dialog)
            self.assertFalse(settings.HIGH_QUALITY_SCALING)
            self.assertIs(window.cache_object, old_cache)
            self.assertFalse(dialog._export_resources_claimed)
            self.assertIsNone(dialog.cache_thread)
            self.assertIsNone(dialog.old_cache_object)
            export_thread.StopThread.assert_called_once_with(10000)
            export_thread.Reader.assert_called_once_with(None)
            self.assertEqual(window.timeline_sync.timeline.SetCache.call_args_list,
                             [unittest.mock.call(small_cache), unittest.mock.call(old_cache)])

    def test_metadata_does_not_open_readers_or_copy_the_project(self):
        dialog = SimpleNamespace()
        source = SimpleNamespace(info=SimpleNamespace(
            width=1280, height=720, fps=SimpleNamespace(num=30, den=1),
            sample_rate=48000, channels=2, channel_layout=3, has_audio=True, has_video=True,
            video_length=1800, duration=60), GetMinTime=lambda: 2, GetMaxTime=lambda: 12)
        timeline = Mock(info=SimpleNamespace())
        app = SimpleNamespace(_tr=lambda text: text, project=Mock(),
                              window=SimpleNamespace(timeline_sync=SimpleNamespace(timeline=source)))
        with patch.object(self.export, 'get_app', return_value=app), \
                patch.object(self.export.openshot, 'Timeline', return_value=timeline), \
                patch.object(self.export.copy, 'deepcopy', side_effect=AssertionError('Opening must not clone the project')):
            self.assertTrue(self.export.Export.load_export_timeline(dialog, load_project=False))
        timeline.SetJson.assert_not_called()
        timeline.Open.assert_not_called()
        self.assertEqual((dialog._export_min_time, dialog._export_max_time), (2, 12))

    def test_deferred_timeline_frame_limits_match_native_fractional_fps(self):
        native = self.export.openshot
        reader = native.DummyReader(native.Fraction(30, 1), 1280, 720, 48000, 2, 10.0)
        clip = native.Clip(reader)
        clip.Position(2.2); clip.End(3.7)
        source = native.Timeline(1280, 720, native.Fraction(30, 1), 48000, 2, native.LAYOUT_STEREO)
        source.AddClip(clip)
        metadata = native.Timeline(1280, 720, native.Fraction(30, 1), 48000, 2, native.LAYOUT_STEREO)
        spin = lambda value: SimpleNamespace(value=lambda: value)
        dialog = SimpleNamespace(timeline=metadata, _export_timeline_loaded=False,
            _export_min_time=source.GetMinTime(), _export_max_time=source.GetMaxTime(),
            update_frame_rate_display=Mock(), txtWidth=spin(1280), txtHeight=spin(720),
            txtSampleRate=spin(48000), txtChannels=spin(2),
            cboChannelLayout=SimpleNamespace(currentData=lambda: native.LAYOUT_STEREO),
            checkStartFirstClip=SimpleNamespace(isChecked=lambda: True),
            checkEndLastClip=SimpleNamespace(isChecked=lambda: True), txtStartFrame=Mock(), txtEndFrame=Mock())
        app = SimpleNamespace(project=SimpleNamespace(get=lambda key: dict(num=30, den=1)))
        with patch.object(self.export, 'get_app', return_value=app):
            for num, den in ((24, 1), (30000, 1001), (60, 1)):
                dialog.txtFrameRateNum=spin(num); dialog.txtFrameRateDen=spin(den)
                source.info.fps.num=num; source.info.fps.den=den
                self.export.Export.updateFrameRate(dialog)
                dialog.txtStartFrame.setValue.assert_called_with(source.GetMinFrame())
                dialog.txtEndFrame.setValue.assert_called_with(source.GetMaxFrame())

    def test_completed_probe_preserves_user_encoder_choice(self):
        from qt_api import QApplication, QComboBox
        self.__class__.app = QApplication.instance() or QApplication([])
        targets, projects = QComboBox(), QComboBox()
        targets.addItem('NVIDIA', 'nvenc')
        projects.addItem('All Formats', 'All Formats')
        initial = dict(vcodec='libx264')
        dialog = SimpleNamespace(cboSimpleTarget=targets, cboSimpleProjectType=projects,
            encoder_probe_timer=Mock(), _encoder_saved_settings=False, _encoder_initial_settings=initial,
            validation=SimpleNamespace(current_settings=lambda: dict(vcodec='h264_nvenc')),
            sync_video_target=Mock(), cboSimpleTarget_index_changed=Mock())
        def populate(*args):
            targets.clear()
            targets.addItem('NVIDIA', 'nvenc')
            targets.addItem('Vulkan', 'vulkan')
            targets.setCurrentIndex(1)
        dialog.cboSimpleProjectType_index_changed = populate
        with patch.object(self.export, 'cached_encoder_capabilities', return_value=dict(state='ready', encoders=())):
            self.export.Export._refresh_encoder_choices(dialog)
        self.assertEqual(targets.currentData(), 'nvenc')
        dialog.cboSimpleTarget_index_changed.assert_not_called()
        dialog.sync_video_target.assert_called_once_with()
        targets.deleteLater(); projects.deleteLater()

    def test_export_settings_ignore_unnamed_controls_and_stale_widget_types(self):
        from qt_api import QApplication, QWidget, QScrollArea, QLineEdit, QCheckBox
        self.__class__.app = QApplication.instance() or QApplication([])
        dialog = QWidget()
        dialog.restoring_defaults = False
        dialog.result_tab = None
        scroll = QScrollArea(dialog)  # Matches an empty name before the text field.
        unnamed = QLineEdit('popup search', dialog)
        filename = QLineEdit('my video', dialog)
        filename.setObjectName('txtFileName')
        stale = QScrollArea(dialog)
        stale.setObjectName('oldTextField')
        dialog.checkStartFirstClip = QCheckBox(dialog)
        dialog.checkEndLastClip = QCheckBox(dialog)
        app = SimpleNamespace(updates=Mock(), project=Mock())
        with patch.object(self.export, 'get_app', return_value=app):
            self.export.Export.save_settings(dialog)
            saved = app.updates.update.call_args.args[1]
            self.assertEqual(saved, [{'name': 'txtFileName', 'type': 'QLineEdit', 'value': 'my video'}])
            app.project.get.return_value = [
                {'name': '', 'type': 'QLineEdit', 'value': 'old popup search'},
                {'name': 'oldTextField', 'type': 'QLineEdit', 'value': 'stale'},
                *saved,
            ]
            filename.clear()
            self.export.Export.load_settings(dialog)
            self.assertEqual(filename.text(), 'my video')
            self.assertEqual(unnamed.text(), 'popup search')
        dialog.deleteLater()

    def test_missing_user_directory_still_loads_installed_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            installed = Path(directory) / "installed"
            installed.mkdir()
            profile = installed / "720p"
            profile.write_text("description=HD 720p\nframe_rate_num=30\nframe_rate_den=1\n"
                               "width=1280\nheight=720\nprogressive=1\nsample_aspect_num=1\n"
                               "sample_aspect_den=1\ndisplay_aspect_num=16\ndisplay_aspect_den=9\n"
                               "colorspace=709\n")
            dialog = SimpleNamespace(cboProfile=Mock(), getProfileName=lambda path: path)
            dialog.getProfilePath = lambda name: dialog.profile_paths[name]
            app = SimpleNamespace(project=Mock())
            app.project.get.return_value = "HD 720p"
            with patch.object(self.export, "get_app", return_value=app), \
                    patch.object(self.export.info, "USER_PROFILES_PATH", os.path.join(directory, "missing")), \
                    patch.object(self.export.info, "PROFILES_PATH", str(installed)):
                self.export.Export.load_profiles(dialog)
            self.assertEqual(dialog.profile_paths, {"HD 720p (1280x720)": str(profile)})
            self.assertEqual(dialog.selected_profile, "HD 720p (1280x720)")
            dialog.cboProfile.addItem.assert_called_once_with("HD 720p (1280x720)", str(profile))

    def test_export_choices_distinguish_missing_nvenc_from_unavailable_vulkan(self):
        from qt_api import QApplication, QComboBox, QSize, Qt
        from classes.export_settings import encoder_support, preferred_export_codec
        self.__class__.app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            installed = Path(directory) / "installed"
            user = Path(directory) / "user"
            installed.mkdir(); user.mkdir()
            for title, codec in (("CPU", "libx264"), ("NVIDIA", "h264_nvenc"), ("Vulkan", "h264_vulkan")):
                (installed / (title + ".xml")).write_text(
                    "<export-option><type>All Formats</type><title>%s</title>"
                    "<videoformat>mp4</videoformat><videocodec>%s</videocodec></export-option>" % (title, codec))
            api = SimpleNamespace(FFmpegWriter=SimpleNamespace(IsValidCodec=Mock(
                side_effect=lambda codec: codec != "h264_nvenc")), GpuEncoders=Mock(return_value=[]))
            target = QComboBox()
            project = QComboBox(); project.addItem("All Formats", "All Formats")
            dialog = SimpleNamespace(cboSimpleTarget=target)
            with patch.object(self.export, "get_app", return_value=SimpleNamespace(_tr=lambda text: text,
                        gpu_diagnostics=SimpleNamespace(encoder_capabilities=lambda: dict(state="ready", encoders=api.GpuEncoders.return_value)))), \
                    patch.object(self.export.info, "EXPORT_PRESETS_PATH", str(installed)), \
                    patch.object(self.export.info, "USER_PRESETS_PATH", str(user)), \
                    patch.object(self.export, "encoder_support", side_effect=lambda codec, **kwargs: encoder_support(codec, api, {}, **kwargs)), \
                    patch.object(self.export, "preferred_export_codec", side_effect=lambda candidates, **kwargs: preferred_export_codec(candidates, api, {}, **kwargs)), \
                    patch.object(self.export.log, "info") as log_info:
                self.export.Export.cboSimpleProjectType_index_changed(dialog, project, 0)
                self.assertEqual([target.itemText(n) for n in range(target.count())], ["CPU"])
                details = log_info.call_args.args[1]
                self.assertIn("not included", details["h264_nvenc"]["reason"])
                self.assertIn("did not open", details["h264_vulkan"]["reason"])
                self.assertEqual(target.iconSize(), QSize(64, 22))
                self.assertIn("Software encoder", target.itemData(0, Qt.ToolTipRole))
                api.FFmpegWriter.IsValidCodec.side_effect = lambda codec: True
                self.export.Export.cboSimpleProjectType_index_changed(dialog, project, 0)
                self.assertEqual([target.itemText(n) for n in range(target.count())], ["CPU"])
                api.GpuEncoders.return_value = ['h264_nvenc']
                self.export.Export.cboSimpleProjectType_index_changed(dialog, project, 0)
                self.assertEqual(target.currentData(), 'NVIDIA')
                self.assertFalse(target.itemIcon(target.currentIndex()).isNull())
                api.GpuEncoders.return_value = ['h264_nvenc', 'h264_vulkan']
                self.export.Export.cboSimpleProjectType_index_changed(dialog, project, 0)
                self.assertEqual(target.currentData(), 'Vulkan')
                with patch.object(self.export, 'cached_encoder_capabilities', return_value=dict(state='checking', encoders=())):
                    self.export.Export.cboSimpleProjectType_index_changed(dialog, project, 0)
                    self.assertFalse(target.model().item(target.findData('Vulkan')).isEnabled())
                    self.assertTrue(target.model().item(target.findData('CPU')).isEnabled())
                api.GpuEncoders.assert_not_called()

    def test_target_badge_tracks_encoder_changes_without_reapplying_presets(self):
        from qt_api import QApplication, QLineEdit
        from windows.views.hardware_combo import HardwareComboBox, BADGES_ROLE
        self.__class__.app = QApplication.instance() or QApplication([])
        combo = HardwareComboBox()
        dialog = SimpleNamespace(cboSimpleTarget=combo,
                                 video_targets={'GPU': ('mp4', 'h264_nvenc'), 'CPU': ('mp4', 'libx264')},
                                 txtVideoFormat=QLineEdit('mp4'), txtVideoCodec=QLineEdit('libx264'))
        support = {'h264_nvenc': ('nvenc', True, 'included'), 'libx264': ('cpu', True, 'software'),
                   'h264_vulkan': ('vulkan', True, 'opened')}
        changed = Mock()
        with patch.object(self.export, "get_app", return_value=SimpleNamespace(_tr=lambda text: text)), \
                patch.object(self.export, "encoder_support", side_effect=lambda codec, **kwargs: support[codec]):
            self.export.add_target_item(combo, 'GPU', 'MP4 (H.264)', 'h264_nvenc', 'nvenc', 'included')
            self.export.add_target_item(combo, 'CPU', 'MP4 (H.264)', 'libx264', 'cpu', 'software')
            combo.currentIndexChanged.connect(changed)
            # A replaced encoder must not leave the NVIDIA preset and its GPU badge selected
            self.export.Export.sync_video_target(dialog)
            self.assertEqual(combo.currentData(), 'CPU')
            self.assertEqual(combo.itemData(combo.currentIndex(), BADGES_ROLE)['mode'], 'cpu')
            dialog.txtVideoCodec.setText('h264_vulkan')
            self.export.Export.sync_video_target(dialog)
            badge = combo.itemData(combo.currentIndex(), BADGES_ROLE)
            self.assertIsNone(combo.currentData())
            self.assertEqual(combo.currentText(), 'mp4 (h264_vulkan)')
            self.assertEqual((badge['mode'], badge['route']), ('gpu', 'Cross-platform'))
            dialog.txtVideoCodec.setText('h264_nvenc')
            self.export.Export.sync_video_target(dialog)
            self.assertEqual(combo.currentData(), 'GPU')
            self.assertEqual(combo.itemData(combo.currentIndex(), BADGES_ROLE)['route'], 'NVIDIA')
            self.assertEqual(combo.count(), 2)
        changed.assert_not_called()
        combo.deleteLater()
        dialog.txtVideoFormat.deleteLater()
        dialog.txtVideoCodec.deleteLater()
