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

"""Measure autosave capture and Qt responsiveness with realistic synthetic JSON.

Run with the application's Python/native-library environment, for example:
  QT_QPA_PLATFORM=offscreen PYTHONPATH=src:<bindings> python3 \
    benchmarks/project_save_snapshot.py --output /tmp/save-snapshot.json

The animated-point count is spread across four curves; the remaining native
curves keep their default single point. No project loading or rendering is timed. A real native image-clip template,
20 detached undo records, the production autosave callback/worker, asset copying,
recovery compression, path conversion and atomic writes are exercised. Logging
is suppressed. Each row uses fresh in-memory data and a warm local temp folder.
"""
import argparse
import copy
import gc
import json
from pathlib import Path
import platform
import resource
import statistics
import sys
import tempfile
import time
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import openshot
from qt_api import QApplication, QObject, QTimer, Qt, QImage, QColor, pyqtSignal, pyqtSlot, QT_API, QT_VERSION_STR
from classes import info
from classes.json_data import JsonDataStore
from classes.project_data import ProjectDataStore
from classes.updates import UpdateManager, UpdateAction
from classes.logger import log


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clips", nargs="+", type=int, default=[100, 1000, 10000])
    parser.add_argument("--keyframes", nargs="+", type=int, default=[48, 96])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    app._tr = lambda text: text
    settings = {"history-limit": 20, "recovery-limit": 10}
    app.get_settings = lambda: types.SimpleNamespace(get=settings.get)
    # MainWindow imports telemetry at module scope; disable it for this harness.
    metrics = types.ModuleType("classes.metrics")
    for name in ("track_metric_session", "track_metric_screen", "track_metric_error"):
        setattr(metrics, name, lambda *args, **kwargs: None)
    sys.modules["classes.metrics"] = metrics
    from windows.main_window import MainWindow
    log.setLevel("WARNING")

    class Harness(QObject):
        AutoSaveFinished = pyqtSignal(object, str)
        ProjectSaved = pyqtSignal(str)
        ProjectSaveFailed = pyqtSignal(str, str)
        save_recovery = MainWindow.save_recovery
        manage_recovery_files = MainWindow.manage_recovery_files

        def __init__(self):
            super().__init__()
            self.last_auto_save_data_version = -1
            self.errors = []
            self.AutoSaveFinished.connect(self.finished, Qt.QueuedConnection)
            self.ProjectSaveFailed.connect(lambda path, error: self.errors.append(error))

        @pyqtSlot(object, str)
        def finished(self, job, error):
            MainWindow._on_autosave_finished(self, job, error)

    results = {
        "environment": {
            "python": sys.version, "platform": platform.platform(), "cpu": platform.processor(),
            "qt_api": QT_API, "qt_version": QT_VERSION_STR,
            "libopenshot": openshot.OPENSHOT_VERSION_FULL, "bindings": openshot.__file__,
            "repeats": args.repeats, "history_records": 20, "timer_interval_ms": 10},
        "matrix": [],
    }
    with tempfile.TemporaryDirectory(prefix="openshot-save-matrix-") as directory:
        root = Path(directory)
        runtime = root / "runtime"
        runtime.mkdir()
        image_path = runtime / "fixture.png"
        image = QImage(16, 16, QImage.Format_ARGB32)
        image.fill(QColor("blue"))
        if not image.save(str(image_path)):
            raise OSError("Could not create the benchmark image.")
        template = json.loads(openshot.Clip(str(image_path)).Json())
        reader = dict(template["reader"], id="F0", media_type="image")
        fields = {"USER_PATH": str(runtime), "ASSETS_PATH": str(runtime),
                  "BACKUP_FILE": str(root / "backup.osp"), "RECOVERY_PATH": str(root / "recovery")}
        asset_folders = (("THUMBNAIL_PATH", "thumbnail"), ("TITLE_PATH", "title"),
                         ("BLENDER_PATH", "blender"), ("PROTOBUF_DATA_PATH", "protobuf_data"),
                         ("CLIPBOARD_PATH", "clipboard"), ("COMFYUI_OUTPUT_PATH", "comfyui-output"),
                         ("PROXY_PATH", "optimized"))
        for name, folder in asset_folders:
            fields[name] = str(runtime / folder)
            Path(fields[name]).mkdir()
        Path(fields["RECOVERY_PATH"]).mkdir()
        with patch.multiple(info, **fields):
            for count in args.clips:
                for keyframes in args.keyframes:
                    project = ProjectDataStore.__new__(ProjectDataStore)
                    JsonDataStore.__init__(project)
                    project._data = json.loads((ROOT / "src/settings/_default.project").read_text())
                    project._data["files"] = [dict(reader, path=str(image_path))]
                    project._data["clips"] = []
                    for index in range(count):
                        clip = copy.deepcopy(template)
                        clip.update(id="C%d" % index, file_id="F0", position=index * 2.,
                                    start=0., end=2., duration=2., layer=1000000)
                        clip["reader"]["id"] = "F0"
                        for curve in ("alpha", "location_x", "location_y", "scale_x"):
                            point = clip[curve]["Points"][0]
                            clip[curve]["Points"] = []
                            for number in range(keyframes // 4):
                                item = copy.deepcopy(point)
                                item["co"] = {"X": number * 2 + 1, "Y": number / 24.}
                                clip[curve]["Points"].append(item)
                        project._data["clips"].append(clip)
                    # Verify that the generated clip is accepted by native code.
                    native = openshot.Clip()
                    native.SetJson(json.dumps(project._data["clips"][0]))
                    project.current_filepath = str(root / ("matrix-%d-%d.osp" % (count, keyframes)))
                    project.has_unsaved_changes = True
                    app.project = project
                    app.updates = UpdateManager()
                    for index in range(20):
                        app.updates.actionHistory.append(UpdateAction(
                            "update", ["clips", {"id": "C0"}], copy.deepcopy(project._data["clips"][0]),
                            old_values=copy.deepcopy(project._data["clips"][0])))
                    # Ensure every worker also compresses a previous on-disk version.
                    initial = project.capture_save_snapshot(app.updates.export_history(20))
                    Path(project.current_filepath).write_bytes(b"".join(initial.chunks()))
                    del initial
                    trials = []
                    for repeat in range(args.repeats):
                        harness = Harness()
                        phases = {}
                        captured = []
                        original_capture = project.capture_save_snapshot
                        original_history = app.updates.export_history

                        def timed_capture(history):
                            start = time.perf_counter()
                            contents = original_capture(history)
                            phases["snapshot_ms"] = (time.perf_counter() - start) * 1000
                            captured.append(contents)
                            return contents

                        def timed_history(limit):
                            start = time.perf_counter()
                            history = original_history(limit)
                            phases["history_ms"] = (time.perf_counter() - start) * 1000
                            return history

                        gaps = []
                        last_tick = [time.perf_counter()]
                        timer = QTimer()
                        timer.setInterval(10)

                        def tick():
                            now = time.perf_counter()
                            gaps.append((now - last_tick[0]) * 1000)
                            last_tick[0] = now
                        timer.timeout.connect(tick)
                        timer.start()
                        gc.collect()
                        with patch.object(project, "capture_save_snapshot", timed_capture), patch.object(
                                app.updates, "export_history", timed_history):
                            started = time.perf_counter()
                            MainWindow.auto_save_project(harness)
                            phases["ui_capture_and_start_ms"] = (time.perf_counter() - started) * 1000
                        last_tick[0] = time.perf_counter()  # measure worker gaps separately
                        worker_start = last_tick[0]
                        while harness._autosave_job is not None:
                            app.processEvents()
                            if time.perf_counter() - started > 300:
                                raise RuntimeError("Autosave worker timed out")
                            time.sleep(.001)
                        phases["worker_remaining_ms"] = (time.perf_counter() - worker_start) * 1000
                        tick()
                        timer.stop()
                        if harness.errors:
                            raise RuntimeError(harness.errors)
                        phases["snapshot_mib"] = sum(len(chunk) for chunk in captured[0].chunks()) / (1024 * 1024)
                        phases["worker_max_event_gap_ms"] = max(gaps)
                        phases["worker_p95_event_gap_ms"] = sorted(gaps)[min(len(gaps) - 1, int(len(gaps) * .95))]
                        phases["file_mib"] = Path(project.current_filepath).stat().st_size / (1024 * 1024)
                        # Read through the real reader, including relative-path conversion.
                        reopened = project.read_from_file(project.current_filepath, path_mode="absolute")
                        if len(reopened["clips"]) != count:
                            raise RuntimeError("Saved project did not retain the expected clip count.")
                        if reopened["clips"][-1]["alpha"] != project._data["clips"][-1]["alpha"]:
                            raise RuntimeError("Saved project changed the sampled clip's keyframes.")
                        if reopened["files"][0]["path"] != str(image_path):
                            raise RuntimeError("Saved project did not preserve its media path.")
                        del reopened
                        trials.append(phases)
                        message = ("%d clips / %d keyframes, run %d: UI %.1f ms, "
                                   "snapshot %.1f ms, worker max gap %.1f ms")
                        print(message % (count, keyframes, repeat + 1, phases["ui_capture_and_start_ms"],
                                         phases["snapshot_ms"], phases["worker_max_event_gap_ms"]),
                              file=sys.stderr, flush=True)
                    results["matrix"].append({
                        "clips": count, "animated_keyframes_per_clip": keyframes,
                        "total_keyframes_per_clip": sum(
                            len(value["Points"]) for value in clip.values()
                            if isinstance(value, dict) and "Points" in value),
                        "trials": trials,
                        "median": {key: statistics.median(trial[key] for trial in trials) for key in trials[0]},
                    })
                    # Release large fixtures before constructing the next row.
                    app.project = None
                    app.updates = None
                    del project, native, clip, harness
                    gc.collect()
                    Path(args.output).write_text(json.dumps(results, indent=2) + "\n")
    results["peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    Path(args.output).write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
