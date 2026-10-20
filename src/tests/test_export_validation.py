"""
 @file
 @brief Unit tests for export settings validation
"""

import json
import os
import sys
import unittest
from xml.dom import minidom  # nosec B408 - Parses the bundled preset files, not untrusted input.


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from classes import export_validation
from classes.export_validation import Capabilities, ExportValidator, parse_rate, rate_to_value


ENCODERS = {
    "aac": {"type": "audio", "sample_rates": [96000, 48000, 44100, 22050], "channel_layouts": None,
            "lossy": True, "lossless": False},
    "libopus": {"type": "audio", "sample_rates": [48000, 24000, 16000], "channel_layouts": None,
                "lossy": True, "lossless": False},
    "mp2": {"type": "audio", "sample_rates": [48000, 44100], "channel_layouts": [4, 3],
            "lossy": True, "lossless": False},
    "flac": {"type": "audio", "sample_rates": None, "channel_layouts": None,
             "lossy": False, "lossless": True},
    "libx264": {"type": "video", "pixel_formats": ["yuv420p", "yuv444p"], "quality_options": ["crf", "qp"]},
    "mpeg4": {"type": "video", "pixel_formats": ["yuv420p"], "quality_options": []},
    "libvpx-vp9": {"type": "video", "pixel_formats": ["yuv420p"], "quality_options": ["crf"]},
    "h264_nvenc": {"type": "video", "pixel_formats": ["yuv420p"], "quality_options": ["cq", "qp"],
                   "hardware": True},
    "png": {"type": "video", "pixel_formats": ["rgb24"], "quality_options": []},
}
FORMATS = {
    "mp4": {"default_audio_codec": "aac", "default_video_codec": "mpeg4",
            "audio": ["aac", "mp2", "libopus", "flac"], "video": ["libx264", "mpeg4", "h264_nvenc"]},
    "webm": {"default_audio_codec": "libopus", "default_video_codec": "libvpx-vp9",
             "audio": ["libopus"], "video": ["libvpx-vp9"]},
    "wav": {"default_audio_codec": "mp2", "default_video_codec": "", "audio": ["mp2"], "video": []},
    # Like FFmpeg's mp3 muxer: it publishes no codec list, so every answer is "unknown"
    "mp3": {"default_audio_codec": "mp2", "default_video_codec": "png", "unknown": True},
    "gif": {"default_audio_codec": "", "default_video_codec": "mpeg4", "audio": [], "video": ["mpeg4"]},
    "png": {"default_audio_codec": "", "default_video_codec": "png", "audio": [], "video": ["png"]},
}


class FakeWriter:
    """Stands in for openshot.FFmpegWriter's capability queries."""

    @staticmethod
    def IsValidCodec(name):
        return name in ENCODERS

    @staticmethod
    def GetEncoderInfo(name):
        if name not in ENCODERS:
            return json.dumps({"found": False})
        return json.dumps(dict({"found": True, "name": name, "hardware": False}, **ENCODERS[name]))

    @staticmethod
    def GetFormatInfo(name):
        if name not in FORMATS:
            return json.dumps({"found": False})
        info = FORMATS[name]
        return json.dumps({"found": True, "name": name, "default_audio_codec": info["default_audio_codec"],
                           "default_video_codec": info["default_video_codec"]})

    @staticmethod
    def IsCodecSupportedByFormat(format_name, codec_name):
        info = FORMATS.get(format_name)
        if not info or codec_name not in ENCODERS:
            return 0
        if info.get("unknown"):
            return -1
        return int(codec_name in info["audio"] + info["video"])

    @staticmethod
    def GetEncoders(media_type, format_name=""):
        names = [name for name, info in ENCODERS.items() if info["type"] == media_type]
        if format_name:
            names = [name for name in names if FakeWriter.IsCodecSupportedByFormat(format_name, name)]
        return json.dumps([{"name": name, "long_name": name} for name in names])


class OldWriter:
    """An older libopenshot, which only knows IsValidCodec."""

    @staticmethod
    def IsValidCodec(name):
        return name in ENCODERS


def settings(**overrides):
    values = {"mode": "video_audio", "vformat": "mp4", "vcodec": "libx264", "video_bitrate": "8 Mb/s",
              "width": 1920, "height": 1080, "acodec": "aac", "sample_rate": 48000,
              "channel_layout": export_validation.LAYOUT_STEREO, "audio_bitrate": "192 kb/s",
              "start_frame": 1, "end_frame": 100, "image_format": "-%05d.png", "folder": ""}
    values.update(overrides)
    return values


class ExportValidationTests(unittest.TestCase):
    def setUp(self):
        self.validator = ExportValidator(Capabilities(FakeWriter))

    def issues(self, **overrides):
        return {(issue.field, issue.severity): issue for issue in self.validator.validate(settings(**overrides))}

    def test_valid_settings_have_no_issues(self):
        self.assertEqual(self.validator.validate(settings()), [])

    def test_rates_parse_like_the_export_dialog(self):
        self.assertEqual(parse_rate("128 kb/s"), (128.0, "kb"))
        self.assertEqual(parse_rate("2.5 Mb/s"), (2.5, "mb"))
        self.assertEqual(parse_rate("23 crf"), (23.0, "crf"))
        self.assertEqual(parse_rate("20 qp"), (20.0, "qp"))
        self.assertIsNone(parse_rate("128"))
        self.assertIsNone(parse_rate("fast kb/s"))
        self.assertEqual(rate_to_value(128, "kb"), 128000)
        self.assertEqual(rate_to_value(99, "crf"), 63)

    def test_codec_the_format_cannot_hold_suggests_one_it_can(self):
        issues = self.issues(vformat="webm")
        self.assertEqual(issues[("vcodec", "error")].fix, "libvpx-vp9")
        self.assertEqual(issues[("acodec", "error")].fix, "libopus")

    def test_missing_and_wrong_type_codecs_are_errors(self):
        self.assertEqual(self.issues(acodec="libfdk_aac")[("acodec", "error")].fix, "aac")
        self.assertIn("not an audio codec", self.issues(acodec="mpeg4")[("acodec", "error")].message)
        self.assertIn("not a video codec", self.issues(vcodec="aac")[("vcodec", "error")].message)

    def test_unknown_format_is_reported_once(self):
        issues = self.issues(vformat="xyz")
        self.assertEqual(list(issues), [("vformat", "error")])
        self.assertEqual(issues[("vformat", "error")].fix, "mp4")
        self.assertIn(("vformat", "error"), self.issues(vformat=""))

    def test_unsupported_sample_rate_snaps_to_the_closest_one(self):
        self.assertEqual(self.issues(sample_rate=44000)[("sample_rate", "error")].fix, 44100)
        self.assertEqual(self.issues(acodec="libopus", vformat="webm", vcodec="libvpx-vp9",
                                     sample_rate=44100)[("sample_rate", "error")].fix, 48000)
        self.assertEqual(self.issues(sample_rate=0)[("sample_rate", "error")].fix, 48000)

    def test_unsupported_channel_layout_suggests_stereo(self):
        issue = self.issues(acodec="mp2", channel_layout=0x60f)[("channel_layout", "error")]
        self.assertEqual(issue.fix, export_validation.LAYOUT_STEREO)
        self.assertEqual(self.issues(acodec="aac", channel_layout=0x60f), {})

    def test_bit_rates_need_units(self):
        self.assertEqual(self.issues(audio_bitrate="128")[("audio_bitrate", "error")].fix, "128 kb/s")
        self.assertEqual(self.issues(audio_bitrate="23 crf")[("audio_bitrate", "error")].fix, "192 kb/s")
        self.assertEqual(self.issues(video_bitrate="5mbps")[("video_bitrate", "error")].fix, "5 Mb/s")
        self.assertEqual(self.issues(video_bitrate="0.1 kb/s")[("video_bitrate", "error")].fix, "8 Mb/s")
        self.assertEqual(self.issues(video_bitrate="80 crf")[("video_bitrate", "error")].fix, "63 crf")
        self.assertIn(("audio_bitrate", "warning"), self.issues(audio_bitrate="16 kb/s"))

    def test_lossless_audio_ignores_the_bit_rate(self):
        self.assertEqual(self.issues(acodec="flac", audio_bitrate=""), {})

    def test_quality_mode_on_a_codec_without_it_is_a_warning(self):
        issues = self.issues(vcodec="mpeg4", video_bitrate="23 crf")
        self.assertEqual(list(issues), [("video_bitrate", "warning")])
        self.assertEqual(self.issues(vcodec="h264_nvenc", video_bitrate="23 crf"), {})

    def test_subsampled_codecs_need_even_sizes(self):
        issues = self.issues(width=1919, height=1079)
        self.assertEqual(issues[("width", "error")].fix, 1918)
        self.assertEqual(issues[("height", "error")].fix, 1078)
        self.assertEqual(self.issues(vcodec="h264_nvenc", width=1919), {})

    def test_mode_decides_which_settings_matter(self):
        self.assertEqual(self.issues(mode="audio", vcodec="not-a-codec", width=1919), {})
        self.assertEqual(self.issues(mode="video", acodec="not-a-codec", audio_bitrate=""), {})
        self.assertIn(("vformat", "warning"), self.issues(vformat="wav", vcodec="", acodec="mp2"))
        self.assertIn(("vformat", "error"), self.issues(mode="video", vformat="wav", vcodec=""))
        self.assertIn(("vformat", "error"), self.issues(mode="audio", vformat="gif", acodec=""))

    def test_blank_codecs_use_the_format_default(self):
        self.assertEqual(self.issues(vcodec="", acodec="", vformat="webm"), {})
        self.assertIn(("sample_rate", "error"), self.issues(acodec="", vformat="webm", vcodec="", sample_rate=44100))

    def test_image_sequences_need_a_frame_number_and_known_type(self):
        self.assertEqual(self.issues(mode="image_sequence", vcodec="x", acodec="y"), {})
        self.assertEqual(self.issues(mode="image_sequence", image_format=".png")[("image_format", "error")].fix,
                         "-%05d.png")
        self.assertEqual(self.issues(mode="image_sequence", image_format="-%05d.xyz")[("image_format", "error")].fix,
                         "-%05d.png")

    def test_frame_range_and_folder(self):
        self.assertIn(("end_frame", "error"), self.issues(start_frame=10, end_frame=10))
        self.assertIn(("folder", "error"), self.issues(folder=os.path.join(PATH, "no-such-folder")))
        self.assertEqual(self.issues(folder=PATH), {})

    def test_cover_image_formats_only_take_an_image_codec(self):
        issue = self.issues(vformat="mp3", vcodec="libx264", acodec="mp2")[("vcodec", "error")]
        self.assertIn("cover image", issue.message)
        self.assertEqual(issue.fix, "png")
        self.assertEqual(self.issues(vformat="mp3", vcodec="png", acodec="mp2"), {})
        self.assertEqual(self.issues(vformat="mp3", vcodec="", acodec="mp2"), {})
        self.assertIn(("vformat", "error"), self.issues(mode="video", vformat="mp3", vcodec="png"))
        # A cover image has no bit rate to check
        self.assertEqual(self.issues(vformat="mp3", vcodec="png", acodec="mp2", video_bitrate="23 crf"), {})

    def test_engine_failures_point_at_the_setting_and_suggest_a_fix(self):
        failed = {"checked": True, "ok": False, "stage": "audio", "message": "mp3: Exactly one MP3 audio stream"}
        issue = self.validator.engine_issue(settings(vformat="mp3", vcodec="png", acodec="aac"), failed)
        self.assertEqual((issue.field, issue.fix), ("acodec", "mp2"))
        self.assertIn("Exactly one MP3 audio stream", issue.message)
        issue = self.validator.engine_issue(settings(vformat="webm", vcodec="libx264", acodec="libopus"),
                                            dict(failed, stage="video"))
        self.assertEqual((issue.field, issue.fix), ("vcodec", "libvpx-vp9"))
        issue = self.validator.engine_issue(settings(), dict(failed, stage="header"))
        self.assertEqual((issue.field, issue.fix), ("vformat", None))
        self.assertIsNone(self.validator.engine_issue(settings(), {"checked": True, "ok": True}))
        self.assertIsNone(self.validator.engine_issue(settings(), dict(failed, checked=False)))

    def test_long_encoder_menus_split_into_short_groups(self):
        from classes.export_validation import MENU_LIMIT, encoder_menu
        encoders = [{"name": "h264_hw%d" % index, "codec": "h264", "hardware": True, "lossy": True}
                    for index in range(4)]
        encoders += [{"name": letter * 3, "codec": letter, "lossy": True} for letter in "abcdefghijklmnopqrstuvwxy"]
        encoders += [{"name": "prores%d" % index, "codec": "prores", "lossy": True, "intra_only": True}
                     for index in range(3)]
        encoders += [{"name": "ffv%d" % index, "codec": "ffv%d" % index, "lossless": True} for index in range(2)]
        menu = encoder_menu(encoders, "video")
        titles = [node[0] for node in menu]
        self.assertEqual(titles, ["Hardware Accelerated (4)", "Delivery (25)", "Editing (Intra-frame) (3)",
                                  "Lossless (2)"])
        # Shared codecs form a family; a long category splits into alphabetical ranges
        self.assertEqual(menu[0][1][0][0], "H264 (4)")
        self.assertEqual([title for title, _ in menu[1][1]], ["A – M", "N – Y"])
        self.assertTrue(all(len(part) <= MENU_LIMIT for _, part in menu[1][1]))
        self.assertEqual(menu[2][1][0][0], "PRORES (3)")
        # Ranges within one letter name their first and last entries
        same = [{"name": "lib%02d" % index, "codec": "c%d" % index, "lossy": True} for index in range(30)]
        self.assertEqual([title for title, _ in encoder_menu(same, "video")], ["lib00 – lib14", "lib15 – lib29"])

        # Name prefixes group families too (i.e. pcm_*), and short lists stay flat
        audio = [{"name": "pcm_%02d" % index, "codec": "pcm_%02d" % index, "lossless": True} for index in range(25)]
        audio += [{"name": "aac", "codec": "aac", "lossy": True}]
        menu = encoder_menu(audio, "audio")
        self.assertEqual([node[0] for node in menu], ["Lossy (1)", "Lossless & Uncompressed (25)"])
        self.assertEqual(menu[1][1][0][0], "PCM (25)")
        self.assertEqual(encoder_menu(audio[-3:], "audio"), sorted(audio[-3:], key=lambda e: e["name"]))

    def test_older_libopenshot_only_checks_what_it_can(self):
        validator = ExportValidator(Capabilities(OldWriter))
        found = {issue.field for issue in validator.validate(settings(vformat="webm", sample_rate=44000))}
        self.assertEqual(found, set())
        found = {issue.field for issue in validator.validate(settings(acodec="libfdk_aac", audio_bitrate="128"))}
        self.assertEqual(found, {"acodec", "audio_bitrate"})


class PresetValidationTests(unittest.TestCase):
    """Every bundled preset should be valid with the FFmpeg OpenShot runs on."""

    def test_presets_are_valid(self):
        try:
            caps = Capabilities()
        except ImportError:
            self.skipTest("libopenshot is not available")
        if not caps.available:
            self.skipTest("libopenshot is too old to describe encoders")
        validator = ExportValidator(caps)
        modes = {"Video Only": "video", "Audio Only": "audio", "Image Sequence": "image_sequence"}
        preset_folder = os.path.join(PATH, "presets")

        def text(document, tag):
            nodes = document.getElementsByTagName(tag)
            return nodes[0].childNodes[0].data if nodes and nodes[0].childNodes else ""

        for name in sorted(os.listdir(preset_folder)):
            document = minidom.parse(os.path.join(preset_folder, name))  # nosec B318 - Bundled preset file.
            vcodec, acodec = text(document, "videocodec"), text(document, "audiocodec")
            if not all(caps.encoder(codec).get("found") for codec in (vcodec, acodec) if codec):
                continue  # This FFmpeg build doesn't have the encoder (i.e. hardware or AV1)
            video_rates = document.getElementsByTagName("videobitrate")
            audio_rates = document.getElementsByTagName("audiobitrate")
            for quality in ("low", "med", "high"):
                video_rate = video_rates[0].getAttribute(quality) if video_rates else "8 Mb/s"
                audio_rate = audio_rates[0].getAttribute(quality) if audio_rates else "192 kb/s"
                if not video_rate and not audio_rate:
                    continue  # The preset doesn't offer this quality
                with self.subTest(preset=name, quality=quality):
                    issues = validator.validate(settings(
                        mode=modes.get(text(document, "export-to"), "video_audio"),
                        vformat=text(document, "videoformat"), vcodec=vcodec, acodec=acodec,
                        sample_rate=int(text(document, "samplerate") or 0),
                        channel_layout=int(text(document, "audiochannellayout") or 3),
                        video_bitrate=video_rate or "8 Mb/s", audio_bitrate=audio_rate or "192 kb/s"))
                    self.assertEqual([issue for issue in issues if issue.is_error], [])



class ExportDialogValidationTests(unittest.TestCase):
    """The export dialog's outlines, section badges, and Export button follow the issues."""

    @classmethod
    def setUpClass(cls):
        from qt_api import QApplication
        from tests.qt_test_app import get_or_create_app
        cls.app, _ = get_or_create_app(lambda: QApplication([]))

    def dialog(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from qt_api import QDialog, QPushButton, load_ui
        from windows.export_validation_ui import ExportValidationUI

        dialog = QDialog()
        self.addCleanup(dialog.deleteLater)
        load_ui(os.path.join(PATH, "windows", "ui", "export.ui"), dialog)
        dialog.export_button = QPushButton("Export Video")
        dialog.buttonBox.addButton(dialog.export_button, dialog.buttonBox.AcceptRole)
        for option in ("Video & Audio", "Video Only", "Audio Only", "Image Sequence"):
            dialog.cboExportTo.addItem(option)
        for name, value in (("Mono", export_validation.LAYOUT_MONO), ("Stereo", export_validation.LAYOUT_STEREO),
                            ("5.1", 0x60f)):
            dialog.cboChannelLayout.addItem(name, value)
        dialog.cboChannelLayout.setCurrentIndex(1)
        dialog.txtEndFrame.setMaximum(1000)
        dialog.txtEndFrame.setValue(100)
        dialog.txtWidth.setValue(1920)
        dialog.txtHeight.setValue(1080)
        dialog.txtSampleRate.setValue(48000)
        for widget, text in ((dialog.txtVideoFormat, "mp4"), (dialog.txtVideoCodec, "libx264"),
                             (dialog.txtVideoBitRate, "8 Mb/s"), (dialog.txtAudioCodec, "aac"),
                             (dialog.txtAudioBitrate, "192 kb/s"), (dialog.txtImageFormat, "-%05d.png")):
            widget.setText(text)
        with patch("windows.export_validation_ui.get_app", return_value=SimpleNamespace(_tr=lambda text: text)):
            validation = ExportValidationUI(dialog, ExportValidator(Capabilities(FakeWriter)))
        return dialog, validation

    def test_invalid_setting_is_outlined_badged_and_blocks_export(self):
        dialog, validation = self.dialog()
        self.assertTrue(dialog.export_button.isEnabled())
        self.assertEqual(dialog.txtAudioCodec.property("exportIssue"), "")

        dialog.txtAudioCodec.setText("libfdk_aac")
        validation.validate()
        audio_page = dialog.toolBox.indexOf(dialog.pageAudioSettings)
        self.assertEqual(dialog.txtAudioCodec.property("exportIssue"), "error")
        self.assertIn("libfdk_aac", dialog.txtAudioCodec.toolTip())
        self.assertFalse(dialog.toolBox.itemIcon(audio_page).isNull())
        self.assertTrue(dialog.toolBox.itemIcon(dialog.toolBox.indexOf(dialog.pageVideoSettings)).isNull())
        self.assertFalse(dialog.exportTabs.tabIcon(validation.toolbox_tab).isNull())
        self.assertFalse(dialog.export_button.isEnabled())
        self.assertFalse(validation.status_button.isHidden())

        validation.fix_all()
        self.assertEqual(dialog.txtAudioCodec.text(), "aac")
        self.assertEqual(dialog.txtAudioCodec.property("exportIssue"), "")
        self.assertTrue(dialog.toolBox.itemIcon(audio_page).isNull())
        self.assertTrue(dialog.export_button.isEnabled())
        self.assertTrue(validation.status_button.isHidden())

    def test_warnings_do_not_block_export(self):
        dialog, validation = self.dialog()
        dialog.txtAudioBitrate.setText("16 kb/s")
        validation.validate()
        self.assertEqual(dialog.txtAudioBitrate.property("exportIssue"), "warning")
        self.assertTrue(dialog.export_button.isEnabled())

    def test_running_export_keeps_the_button_off(self):
        dialog, validation = self.dialog()
        dialog.exportTabs.setEnabled(False)
        validation.validate()
        self.assertFalse(dialog.export_button.isEnabled())

    def test_presets_only_adjust_audio_details_quietly(self):
        dialog, validation = self.dialog()
        dialog.txtSampleRate.setValue(44000)
        dialog.txtAudioCodec.setText("libopus")
        dialog.txtVideoFormat.setText("webm")
        dialog.txtVideoCodec.setText("libvpx-vp9")
        validation.request_auto_fix()
        validation.validate()
        self.assertEqual(dialog.txtSampleRate.value(), 48000)

        dialog.txtVideoCodec.setText("libx264")
        validation.request_auto_fix()
        validation.validate()
        self.assertEqual(dialog.txtVideoCodec.text(), "libx264")
        self.assertFalse(dialog.export_button.isEnabled())

    def test_choices_follow_the_format_and_codec(self):
        dialog, validation = self.dialog()
        choices, more = validation.choices("acodec")
        self.assertEqual([value for _label, value in choices], ["aac", "libopus", "flac", "mp2"])
        dialog.txtVideoFormat.setText("webm")
        self.assertEqual([value for _label, value in validation.choices("acodec")[0]], ["libopus"])
        dialog.txtAudioCodec.setText("libopus")
        self.assertEqual([value for _label, value in validation.choices("sample_rate")[0]], [48000, 24000, 16000])
        self.assertIn("23 crf", [value for _label, value in validation.choices("video_bitrate")[0]])
        self.assertEqual(more, [])

    def test_lossless_audio_disables_the_bit_rate_and_unusable_layouts(self):
        dialog, validation = self.dialog()
        dialog.txtAudioCodec.setText("flac")
        validation.validate()
        self.assertFalse(dialog.txtAudioBitrate.isEnabled())
        dialog.txtAudioCodec.setText("mp2")
        validation.validate()
        self.assertTrue(dialog.txtAudioBitrate.isEnabled())
        self.assertFalse(dialog.cboChannelLayout.model().item(2).isEnabled())
        self.assertTrue(dialog.cboChannelLayout.model().item(1).isEnabled())


    def test_engine_check_runs_in_the_background_and_gates_export(self):
        from unittest.mock import patch
        dialog, validation = self.dialog()
        calls = []

        def fake_test_writer(path, video, audio, mode, quality_mode):
            calls.append((os.path.splitext(path)[1], video["vcodec"], audio["acodec"], mode))
            if audio["acodec"] == "aac" and path.endswith(".mp3"):
                return {"checked": True, "ok": False, "stage": "audio", "message": "mp3: needs MP3 audio",
                        "log": [], "elapsed_ms": 1}
            return {"checked": True, "ok": True, "stage": "", "message": "", "log": [], "elapsed_ms": 1}

        def writer_settings():
            video = {"vformat": dialog.txtVideoFormat.text(), "vcodec": dialog.txtVideoCodec.text(),
                     "width": 1920, "height": 1080, "start_frame": 1, "end_frame": 100}
            return video, {"acodec": dialog.txtAudioCodec.text()}, "video_audio", None

        def settle():
            from qt_api import QApplication
            import time
            deadline = time.time() + 5
            while validation.engine_running and time.time() < deadline:
                QApplication.processEvents()
                time.sleep(0.01)
            QApplication.processEvents()

        dialog.writer_settings = writer_settings
        validation.engine_available = True
        with patch("windows.export_validation_ui.test_writer", side_effect=fake_test_writer):
            # Both problems show at once: the video codec (a quick check) and the audio (the engine,
            # checking the audio stream alone)
            dialog.txtVideoFormat.setText("mp3")
            dialog.txtVideoCodec.setText("libx264")
            validation.validate()
            settle()
            self.assertEqual(dialog.txtVideoCodec.property("exportIssue"), "error")
            self.assertEqual(dialog.txtAudioCodec.property("exportIssue"), "error")
            self.assertEqual(calls[-1][3], "audio")

            dialog.txtVideoCodec.setText("png")
            validation.validate()
            settle()
            # The background check found what the quick checks couldn't
            self.assertEqual(dialog.txtAudioCodec.property("exportIssue"), "error")
            self.assertIn("needs MP3 audio", dialog.txtAudioCodec.toolTip())
            self.assertFalse(dialog.export_button.isEnabled())

            # Unchanged settings reuse the result; a fix checks again
            count = len(calls)
            validation.validate()
            settle()
            self.assertEqual(len(calls), count)
            validation.fix_all()
            settle()
            self.assertEqual(dialog.txtAudioCodec.text(), "mp2")
            self.assertEqual(dialog.txtAudioCodec.property("exportIssue"), "")
            self.assertTrue(dialog.export_button.isEnabled())
            # Export reuses a passing result for unchanged settings
            count = len(calls)
            self.assertTrue(validation.confirm_with_engine())
            self.assertEqual(len(calls), count)

            # A failure is never reused: Export checks again
            dialog.txtAudioCodec.setText("aac")
            validation.validate()
            settle()
            count = len(calls)
            self.assertFalse(validation.confirm_with_engine())
            self.assertEqual(len(calls), count + 1)

    def test_icons_are_sharp_on_high_dpi_screens(self):
        from qt_api import QSize
        from windows.export_validation_ui import chevron_icon, issue_icon
        from qt_api import QColor
        for icon, size in ((issue_icon(export_validation.ERROR), 14), (chevron_icon(QColor("white")), 16)):
            sizes = icon.availableSizes()
            self.assertIn(QSize(size, size), sizes)
            self.assertIn(QSize(size * 2, size * 2), sizes)
            self.assertIn(QSize(size * 3, size * 3), sizes)

    def test_problem_menu_wraps_long_messages_and_applies_fixes(self):
        from windows.export_validation_ui import MESSAGE_WIDTH, IssueMenuItem
        dialog, validation = self.dialog()
        dialog.txtAudioCodec.setText("libfdk_aac")
        dialog.txtAudioBitrate.setText("128")
        validation.validate()
        menu = validation.issue_menu()
        items = [action.defaultWidget() for action in menu.actions() if hasattr(action, "defaultWidget")
                 and isinstance(action.defaultWidget(), IssueMenuItem)]
        self.assertEqual(len(items), 2)
        for item in items:
            self.assertTrue(item.message.wordWrap())
            self.assertLessEqual(item.message.width(), MESSAGE_WIDTH)
            self.assertTrue(item.fix.text().startswith("Use "))
        self.assertTrue(dialog.txtAudioCodec.toolTip().startswith("<qt>"))
        items[0].clicked.emit()
        self.assertEqual(len(validation.errors), 1)

    def test_cover_image_formats_only_offer_image_codecs(self):
        dialog, validation = self.dialog()
        dialog.txtVideoFormat.setText("mp3")
        choices, more = validation.choices("vcodec")
        self.assertEqual([value for _label, value in choices + more], ["png"])

if __name__ == "__main__":
    unittest.main()
