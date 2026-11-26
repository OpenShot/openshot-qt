"""
 @file
 @brief Unit tests for EDL and Final Cut Pro XML import/export behavior.
"""

import builtins
import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from xml.dom import minidom


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)


class _Signal:
    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


class _Project:
    def __init__(self, **overrides):
        self.current_filepath = overrides.pop("current_filepath", "")
        self._data = {
            "fps": {"num": 24, "den": 1},
            "width": 1920,
            "height": 1080,
            "sample_rate": 48000,
            "channels": 2,
            "layers": [{"number": 1, "label": "Main", "lock": False}],
            "id": "project-1",
            "pixel_ratio": {"num": 1, "den": 1},
            "interlaced_frame": False,
        }
        self._data.update(overrides)

    def get(self, key):
        return self._data.get(key)


class _App:
    def __init__(self, project=None):
        self.project = project or _Project()
        self.window = types.SimpleNamespace(
            refreshFrameSignal=_Signal(),
            propertyTableView=types.SimpleNamespace(select_frame=lambda *_: None),
            preview_thread=types.SimpleNamespace(player=types.SimpleNamespace(Position=lambda: 0)),
        )

    def _tr(self, value):
        return value


class _TrackRecord:
    saved = []

    def __init__(self, number=None, data=None):
        self.data = data or {}
        if number is not None:
            self.data.setdefault("number", number)

    def save(self):
        self.__class__.saved.append(self)


class _ClipRecord:
    saved = []

    def __init__(self, data=None):
        self.data = data or {}

    def save(self):
        self.__class__.saved.append(self)


class _FileRecord:
    def __init__(self, file_id, path, media_type="video", **data):
        self.id = file_id
        self.data = {
            "id": file_id,
            "path": path,
            "name": os.path.basename(path),
            "media_type": media_type,
            "duration": 10.0,
            "width": 1920,
            "height": 1080,
            "fps": {"num": 24, "den": 1},
            "sample_rate": 48000,
            "channels": 2,
        }
        self.data.update(data)

    def absolute_path(self):
        return self.data["path"]


class _FileQuery:
    by_id = {}
    by_path = {}

    @classmethod
    def reset(cls, files):
        cls.by_id = {f.id: f for f in files}
        cls.by_path = {f.data["path"]: f for f in files}

    @classmethod
    def get(cls, **kwargs):
        if "id" in kwargs:
            return cls.by_id.get(kwargs["id"])
        if "path" in kwargs:
            return cls.by_path.get(kwargs["path"])
        return None


class _OpenShotClip:
    def __init__(self, path):
        self.path = path

    def Json(self):
        has_audio = self.path.lower().endswith((".wav", ".mp3", ".aac"))
        has_video = not has_audio
        return json.dumps({
            "id": "clip-from-reader",
            "reader": {"path": self.path, "has_audio": has_audio, "has_video": has_video},
        })

    def Reader(self):
        media_type = "audio" if self.path.lower().endswith((".wav", ".mp3", ".aac")) else "video"
        return types.SimpleNamespace(Json=lambda: json.dumps({
            "path": self.path,
            "media_type": media_type,
            "has_audio": media_type == "audio",
            "has_video": media_type == "video",
        }))


class InterchangeImportExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.edl_importer = importlib.import_module("classes.importers.edl")
        cls.edl_exporter = importlib.import_module("classes.exporters.edl")
        cls.fcp_importer = importlib.import_module("classes.importers.final_cut_pro")
        cls.fcp_exporter = importlib.import_module("classes.exporters.final_cut_pro")

    def setUp(self):
        _TrackRecord.saved = []
        _ClipRecord.saved = []
        _FileQuery.reset([])

    def test_edl_create_clip_sets_svg_audio_thumbnail_for_audio_only_clip(self):
        audio_path = "/tmp/audio.wav"
        _FileQuery.reset([_FileRecord("audio-file", audio_path, media_type="audio")])
        app = _App()
        track = types.SimpleNamespace(data={"number": 7})
        context = {
            "clip_path": audio_path,
            "clip_title": "Audio Clip",
            "audio_ctx": [{
                "reel": "AX",
                "clip_start_time": "00:00:00:00",
                "clip_end_time": "00:00:01:00",
                "timeline_position": "00:00:02:00",
            }],
        }

        with patch.object(self.edl_importer, "get_app", return_value=app), \
             patch.object(self.edl_importer, "find_missing_file", return_value=(audio_path, False, False)), \
             patch.object(self.edl_importer, "File", _FileQuery), \
             patch.object(self.edl_importer, "Clip", _ClipRecord), \
             patch.object(self.edl_importer.openshot, "Clip", _OpenShotClip):
            self.edl_importer.create_clip(context, track)

        self.assertEqual(len(_ClipRecord.saved), 1)
        clip_data = _ClipRecord.saved[0].data
        self.assertEqual(clip_data["file_id"], "audio-file")
        self.assertEqual(clip_data["layer"], 7)
        self.assertFalse(clip_data["has_video"]["Points"][0]["co"]["Y"])
        self.assertTrue(clip_data["image"].endswith(os.path.join("images", "AudioThumbnail.svg")))

    def test_edl_import_parses_grouped_clip_source_and_keyframe_comments(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            media_path = os.path.join(tmpdir, "clip.mp4")
            edl_path = os.path.join(tmpdir, "input.edl")
            with open(edl_path, "w", encoding="utf-8") as handle:
                handle.write(
                    "TITLE: Test Sequence\n"
                    "FCM: NON-DROP FRAME\n\n"
                    "001  AX       V     C        00:00:00:00 00:00:01:00 00:00:02:00 00:00:03:00\n"
                    "001  AX       A     C        00:00:00:00 00:00:01:00 00:00:02:00 00:00:03:00\n"
                    "* FROM CLIP NAME: clip.mp4\n"
                    "* SOURCE FILE: clip.mp4\n"
                    "* VIDEO LEVEL AT 00:00:00:12 IS 50% BEZIER\n"
                    "* AUDIO LEVEL AT 00:00:00:12 IS -6.00 DB HOLD\n"
                    "* SCALE X AT 00:00:00:12 IS 125% LINEAR\n"
                )

            contexts = []
            app = _App(_Project(layers=[{"number": 1, "label": "Existing"}]))

            with patch.object(self.edl_importer, "get_app", return_value=app), \
                 patch.object(self.edl_importer.QFileDialog, "getOpenFileName", return_value=(edl_path, "")), \
                 patch.object(self.edl_importer, "Track", _TrackRecord), \
                 patch.object(self.edl_importer, "create_clip", side_effect=lambda ctx, track: contexts.append(dict(ctx))):
                self.edl_importer.import_edl()

        self.assertEqual(len(_TrackRecord.saved), 1)
        self.assertEqual(len(contexts), 1)
        ctx = contexts[0]
        self.assertEqual(ctx["clip_path"], media_path)
        self.assertEqual(ctx["video_ctx"]["timeline_position"], "00:00:02:00")
        self.assertEqual(ctx["audio_ctx"][0]["clip_end_time"], "00:00:01:00")
        self.assertAlmostEqual(ctx["opacity"][0]["value"], 0.5)
        self.assertAlmostEqual(ctx["volume"][0]["value"], self.edl_importer._db_to_volume(-6.0), places=4)
        self.assertAlmostEqual(ctx["scale_x"][0]["value"], 1.25)

    def test_edl_import_reads_non_ascii_clip_names_as_utf8(self):
        # export_edl() writes UTF-8, so import_edl() must read UTF-8 even when
        # the locale encoding is something else (e.g. cp1252 or cp949 on Windows).
        clip_name = "\u0141ukasz \u2728.mp4"

        def locale_open(file, mode="r", *args, encoding=None, **kwargs):
            if "b" not in mode and encoding is None:
                encoding = "cp1252"
            return builtins.open(file, mode, *args, encoding=encoding, **kwargs)

        with tempfile.TemporaryDirectory() as tmpdir:
            media_path = os.path.join(tmpdir, clip_name)
            edl_path = os.path.join(tmpdir, "input.edl")
            with open(edl_path, "w", encoding="utf-8") as handle:
                handle.write(
                    "TITLE: Test Sequence\n"
                    "FCM: NON-DROP FRAME\n\n"
                    "001  AX       V     C        00:00:00:00 00:00:01:00 00:00:02:00 00:00:03:00\n"
                    "* FROM CLIP NAME: %s\n"
                    "* SOURCE FILE: %s\n" % (clip_name, clip_name)
                )

            contexts = []
            app = _App(_Project(layers=[{"number": 1, "label": "Existing"}]))

            with patch.object(self.edl_importer, "open", locale_open, create=True), \
                 patch.object(self.edl_importer, "get_app", return_value=app), \
                 patch.object(self.edl_importer.QFileDialog, "getOpenFileName", return_value=(edl_path, "")), \
                 patch.object(self.edl_importer, "Track", _TrackRecord), \
                 patch.object(self.edl_importer, "create_clip", side_effect=lambda ctx, track: contexts.append(dict(ctx))):
                self.edl_importer.import_edl()

        self.assertEqual(len(contexts), 1)
        self.assertEqual(contexts[0]["clip_title"], clip_name)
        self.assertEqual(contexts[0]["clip_path"], media_path)

    def test_edl_export_writes_tracks_gap_media_rows_and_keyframe_comments(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            media_path = os.path.join(tmpdir, "media.mp4")
            out_base = os.path.join(tmpdir, "out.edl")
            _FileQuery.reset([_FileRecord("file-1", media_path, media_type="video")])
            app = _App(_Project(fps={"num": 24, "den": 1}, layers=[{"number": 1, "label": "Main"}]))
            clip = _ClipRecord({
                "id": "clip-1",
                "file_id": "file-1",
                "title": "Clip One",
                "position": 1.0,
                "start": 0.0,
                "end": 2.0,
                "reel": "R1",
                "reader": {"path": media_path, "has_video": True, "has_audio": True},
                "alpha": {"Points": [{"co": {"X": 1, "Y": 0.5}, "interpolation": 0}]},
                "volume": {"Points": [{"co": {"X": 1, "Y": 0.5}, "interpolation": 2}]},
                "scale_x": {"Points": [{"co": {"X": 1, "Y": 1.25}, "interpolation": 1}]},
            })

            with patch.object(self.edl_exporter, "get_app", return_value=app), \
                 patch.object(self.edl_exporter.QFileDialog, "getSaveFileName", return_value=(out_base, "")), \
                 patch.object(self.edl_exporter, "File", _FileQuery), \
                 patch.object(self.edl_exporter.Track, "get", return_value=_TrackRecord(number=1)), \
                 patch.object(self.edl_exporter.Clip, "filter", return_value=[clip]):
                self.edl_exporter.export_edl()

            exported_path = os.path.join(tmpdir, "out-Main.edl")
            with open(exported_path, "r", encoding="utf-8") as handle:
                exported = handle.read()

        self.assertIn("TITLE: out - Main", exported)
        self.assertIn("FCM: NON-DROP FRAME", exported)
        self.assertIn("001  BL", exported)
        self.assertIn("002  R1       V", exported)
        self.assertIn("002  R1       A", exported)
        self.assertIn("* FROM CLIP NAME: Clip One", exported)
        self.assertIn("* SOURCE FILE: media.mp4", exported)
        self.assertIn("* VIDEO LEVEL AT 00:00:00:00 IS 50% BEZIER", exported)
        self.assertIn("* AUDIO LEVEL AT 00:00:00:00 IS -6.02 DB HOLD", exported)
        self.assertIn("* SCALE X AT 00:00:00:00 IS 125% LINEAR", exported)

    def test_fcp_import_audio_only_clip_uses_svg_thumbnail_and_imports_volume(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.wav")
            xml_path = os.path.join(tmpdir, "input.xml")
            with open(xml_path, "w", encoding="utf-8") as handle:
                handle.write(f"""<?xml version="1.0"?>
<xmeml version="4"><sequence><media><audio><track><locked>TRUE</locked>
<clipitem id="a1"><name>Audio Only</name><start>24</start><end>48</end><in>0</in><out>24</out>
<file id="f1"><pathurl>{audio_path}</pathurl></file>
<filter><effect><effectid>audiolevels</effectid><keyframe><when>12</when><value>0.25</value><interpolation><name>hold</name></interpolation></keyframe></effect></filter>
</clipitem></track></audio></media></sequence></xmeml>""")

            _FileQuery.reset([_FileRecord("audio-file", audio_path, media_type="audio")])
            app = _App(_Project(layers=[{"number": 1, "label": "Existing"}]))

            with patch.object(self.fcp_importer, "get_app", return_value=app), \
                 patch.object(self.fcp_importer.QFileDialog, "getOpenFileName", return_value=(xml_path, "")), \
                 patch.object(self.fcp_importer, "find_missing_file", return_value=(audio_path, False, False)), \
                 patch.object(self.fcp_importer, "File", _FileQuery), \
                 patch.object(self.fcp_importer, "Track", _TrackRecord), \
                 patch.object(self.fcp_importer, "Clip", _ClipRecord), \
                 patch.object(self.fcp_importer.openshot, "Clip", _OpenShotClip):
                self.fcp_importer.import_xml()

        self.assertEqual(len(_TrackRecord.saved), 1)
        self.assertTrue(_TrackRecord.saved[0].data["lock"])
        self.assertEqual(len(_ClipRecord.saved), 1)
        clip_data = _ClipRecord.saved[0].data
        self.assertEqual(clip_data["title"], "Audio Only")
        self.assertEqual(clip_data["position"], 1.0)
        self.assertTrue(clip_data["image"].endswith(os.path.join("images", "AudioThumbnail.svg")))
        self.assertEqual(clip_data["volume"]["Points"][0]["co"], {"X": 12, "Y": 0.25})
        self.assertEqual(clip_data["volume"]["Points"][0]["interpolation"], self.fcp_importer.openshot.CONSTANT)

    def test_fcp_import_video_clip_imports_opacity_motion_and_thumbnail_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "video.mp4")
            xml_path = os.path.join(tmpdir, "input.xml")
            with open(xml_path, "w", encoding="utf-8") as handle:
                handle.write(f"""<?xml version="1.0"?>
<xmeml version="4"><sequence><media><video><track><locked>FALSE</locked>
<clipitem id="v1"><name>Video Clip</name><start>24</start><end>72</end><in>12</in><out>60</out>
<file id="f1"><pathurl>{video_path}</pathurl></file>
<filter>
<effect><effectid>opacity</effectid>
<keyframe><when>12</when><value>50</value><interpolation><name>bezier</name></interpolation></keyframe>
</effect>
<effect><effectid>basic</effectid>
<parameter><parameterid>center</parameterid>
<keyframe><when>12</when><value><horiz>1056</horiz><vert>486</vert></value><interpolation><name>linear</name></interpolation></keyframe>
</parameter>
<parameter><parameterid>scale</parameterid>
<keyframe><when>12</when><value>125</value><interpolation><name>linear</name></interpolation></keyframe>
</parameter>
<parameter><parameterid>rotation</parameterid>
<keyframe><when>12</when><value>15</value><interpolation><name>hold</name></interpolation></keyframe>
</parameter>
</effect>
</filter>
</clipitem></track></video></media></sequence></xmeml>""")

            _FileQuery.reset([_FileRecord("video-file", video_path, media_type="video", width=1920, height=1080)])
            app = _App(_Project(layers=[{"number": 1, "label": "Existing"}], width=1920, height=1080))

            with patch.object(self.fcp_importer, "get_app", return_value=app), \
                 patch.object(self.fcp_importer.QFileDialog, "getOpenFileName", return_value=(xml_path, "")), \
                 patch.object(self.fcp_importer, "find_missing_file", return_value=(video_path, False, False)), \
                 patch.object(self.fcp_importer, "File", _FileQuery), \
                 patch.object(self.fcp_importer, "Track", _TrackRecord), \
                 patch.object(self.fcp_importer, "Clip", _ClipRecord), \
                 patch.object(self.fcp_importer.openshot, "Clip", _OpenShotClip):
                self.fcp_importer.import_xml()

        self.assertEqual(len(_ClipRecord.saved), 1)
        clip_data = _ClipRecord.saved[0].data
        self.assertEqual(clip_data["title"], "Video Clip")
        self.assertEqual(clip_data["position"], 1.0)
        self.assertEqual(clip_data["start"], 0.5)
        self.assertEqual(clip_data["end"], 2.5)
        self.assertTrue(clip_data["image"].endswith(os.path.join("thumbnail", "video-file.png")))
        self.assertEqual(clip_data["alpha"]["Points"][0]["co"], {"X": 12, "Y": 0.5})
        self.assertAlmostEqual(clip_data["location_x"]["Points"][0]["co"]["Y"], 0.05)
        self.assertAlmostEqual(clip_data["location_y"]["Points"][0]["co"]["Y"], -0.05)
        self.assertEqual(clip_data["scale_x"]["Points"][0]["co"], {"X": 12, "Y": 1.25})
        self.assertEqual(clip_data["scale_y"]["Points"][0]["co"], {"X": 12, "Y": 1.25})
        self.assertEqual(clip_data["rotation"]["Points"][0]["co"], {"X": 12, "Y": 15.0})
        self.assertEqual(clip_data["rotation"]["Points"][0]["interpolation"], self.fcp_importer.openshot.CONSTANT)

    def test_fcp_pathurl_to_path_decodes_file_urls_relative_paths_and_internal_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(
                self.fcp_importer._pathurl_to_path("file:///tmp/My%20Clip.mov", tmpdir),
                os.path.normpath("/tmp/My Clip.mov"),
            )
            self.assertEqual(
                self.fcp_importer._pathurl_to_path("media/clip.mov", tmpdir),
                os.path.normpath(os.path.join(tmpdir, "media", "clip.mov")),
            )
            with patch.object(self.fcp_importer, "absolute_media_path", return_value="/resolved/internal.mov"):
                self.assertEqual(self.fcp_importer._pathurl_to_path("@assets/internal.mov", tmpdir), "/resolved/internal.mov")

    def test_fcp_export_writes_video_audio_tracks_links_and_effect_keyframes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            media_path = os.path.join(tmpdir, "media.mp4")
            out_path = os.path.join(tmpdir, "out.xml")
            _FileQuery.reset([_FileRecord("file-1", media_path, media_type="video", duration=4.0)])
            app = _App(_Project(
                fps={"num": 24, "den": 1},
                layers=[{"number": 1, "label": "Main", "lock": True}],
                width=1280,
                height=720,
            ))
            clip = _ClipRecord({
                "id": "clip-1",
                "file_id": "file-1",
                "title": "Linked Clip",
                "position": 1.0,
                "start": 0.0,
                "end": 2.0,
                "scale": self.fcp_exporter.openshot.SCALE_FIT,
                "gravity": self.fcp_exporter.openshot.GRAVITY_CENTER,
                "reader": {"path": media_path, "has_video": True, "has_audio": True},
                "alpha": {"Points": [{"co": {"X": 1, "Y": 0.5}, "interpolation": self.fcp_exporter.openshot.BEZIER}]},
                "volume": {"Points": [{"co": {"X": 1, "Y": 0.25}, "interpolation": self.fcp_exporter.openshot.CONSTANT}]},
                "scale_x": {"Points": [{"co": {"X": 1, "Y": 1.25}, "interpolation": self.fcp_exporter.openshot.LINEAR}]},
                "scale_y": {"Points": [{"co": {"X": 1, "Y": 1.25}, "interpolation": self.fcp_exporter.openshot.LINEAR}]},
                "rotation": {"Points": [{"co": {"X": 1, "Y": 15.0}, "interpolation": self.fcp_exporter.openshot.LINEAR}]},
            })

            with patch.object(self.fcp_exporter, "get_app", return_value=app), \
                 patch.object(self.fcp_exporter.QFileDialog, "getSaveFileName", return_value=(out_path, "")), \
                 patch.object(self.fcp_exporter, "File", _FileQuery), \
                 patch.object(self.fcp_exporter.Track, "get", return_value=_TrackRecord(number=1)), \
                 patch.object(self.fcp_exporter.Clip, "filter", side_effect=lambda layer=None: [clip]), \
                 patch.object(self.fcp_exporter, "_validate_export"):
                self.fcp_exporter.export_xml()

            doc = minidom.parse(out_path)

        clipitems = doc.getElementsByTagName("clipitem")
        self.assertGreaterEqual(len(clipitems), 2)
        self.assertEqual(doc.getElementsByTagName("sequence")[0].getAttribute("id"), "project-1")
        self.assertEqual(doc.getElementsByTagName("width")[0].firstChild.nodeValue, "1280")
        self.assertEqual(doc.getElementsByTagName("locked")[0].firstChild.nodeValue, "TRUE")
        self.assertTrue(any(node.getAttribute("id") == "clip-1" for node in clipitems))
        self.assertTrue(any(node.getAttribute("id") == "clip-1-audio" for node in clipitems))
        self.assertTrue(doc.getElementsByTagName("link"))

        xml_text = doc.toxml()
        doc.unlink()
        self.assertIn("<effectid>opacity</effectid>", xml_text)
        self.assertIn("<effectid>audiolevels</effectid>", xml_text)
        self.assertIn("<value>50.0</value>", xml_text)
        self.assertIn("<value>0.25</value>", xml_text)
        self.assertIn("<value>125.0</value>", xml_text)
        self.assertIn("<value>15.0</value>", xml_text)


if __name__ == "__main__":
    unittest.main()
