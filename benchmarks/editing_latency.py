# @file
# @brief Benchmark timeline editing latency
# @author OpenShot Studios, LLC
#
# @section LICENSE
#
# Copyright (c) 2008-2026 OpenShot Studios, LLC
# (http://www.openshotstudios.com). This file is part of
# OpenShot Video Editor (http://www.openshot.org), an open-source project
# dedicated to delivering high quality video editing and animation solutions
# to the world.
#
# OpenShot Video Editor is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenShot Video Editor is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
#

"""Run with --source BASE_WORKTREE to compare identical headless edit workloads.

Times cover Python dispatch, query copies, project mutations, history snapshots,
and binding JSON serialization. They exclude engine apply/decode, real Qt events,
thumbnail/waveform generation and preview rendering; refresh counts are requests.
Synthetic waveform arrays are redistributable; no external media is needed.
"""
import argparse
import cProfile
import json
import os
import platform
import statistics
import sys
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
parser.add_argument("--iterations", type=int, default=25)
parser.add_argument("--warm-query", action="store_true", help="Warm the detached query cache before timing")
parser.add_argument("--profile", help="Write cProfile data for the measured operations")
args = parser.parse_args()
sys.path.insert(0, os.path.join(args.source, "src"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "tests"))
from test_editing_latency import EditingFixture
import openshot
from qt_api import QT_VERSION_STR, PYQT_VERSION_STR

results = {"environment": {"python": sys.version, "platform": platform.platform(),
            "libopenshot": str(openshot.GetVersion()), "binding": openshot.__file__,
            "qt": QT_VERSION_STR, "pyqt": PYQT_VERSION_STR, "warm_query": args.warm_query}, "scenarios": {}}
profiler = cProfile.Profile()
for name, count, samples in [("overlapping_av", 8, 1000),
                             ("long_waveforms", 32, 30000),
                             ("many_short_clips", 500, 1000),
                             ("edit_undo_dispatch", 32, 1000)]:
    for operation in ("split", "trim"):
        timings, refreshes = [], []
        for index in range(args.iterations):
            fixture = EditingFixture(count, samples)
            try:
                if args.warm_query:
                    from classes.query import Clip
                    Clip.get(id="C0")
                if args.profile:
                    profiler.enable()
                start = time.perf_counter()
                getattr(fixture, operation)()
                # Same serialization invoked by native/UI update listeners.
                for action in fixture.updates.actionHistory:
                    action.json()
                if name == "edit_undo_dispatch":
                    fixture.updates.undo()
                    fixture.updates.redo()
                timings.append((time.perf_counter() - start) * 1000)
                if args.profile:
                    profiler.disable()
                refreshes.append(fixture.refreshes)
            finally:
                fixture.close()
        ordered = sorted(timings)
        results["scenarios"][name + "/" + operation] = {
            "first_ms": timings[0], "median_ms": statistics.median(timings),
            "p95_ms": ordered[min(len(ordered)-1, int(len(ordered)*.95))],
            "max_ms": max(timings), "preview_requests": max(refreshes)}
if args.profile:
    profiler.dump_stats(args.profile)
print(json.dumps(results, indent=2))
