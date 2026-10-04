Editing latency evidence
========================

Base: `de332e2c4b9d79a1cb374abb5fa2b2731662306d` (`origin/develop`).
Production/test commit: `c5a8d9d4c31594a9d14fd6d08b9c654a52031eea`.
Host: Linux x86_64, AMD Ryzen 9 5900XT, 32 logical CPUs. Python 3.8.10,
Qt 5.12.8, PyQt 5.14.1; fixture generation used FFmpeg 4.2.7-0ubuntu0.1. Loaded binding:
`/usr/local/lib/python3.8/dist-packages/openshot.py`; `GetVersion()` reports
`1.0.1`. These results do not validate a newly rebuilt companion engine.

The inspected develop already batches trim/retime commits, suspends thumbnail
requests during trims, and uses isolated source previews for razor/trim. Those
paths were preserved. Profiling the headless edit workload found 2.54 of 3.67
seconds in JSON encoding. Insert mutations copied the complete sibling clip list
into history, then serialized that list again for the binding diff. The inverse
of insert deletes its ID and never consumes that old sibling list. Insert
`old_values` is now `{}`; old histories containing the list still load. Update
and delete snapshots retain their complete previous values. Action JSON now
serializes once and copies only the top-level dictionary when removing history.
No native API or project schema fields were added.

`Slice_Triggered` previously requested one preview refresh per clip/transition
plus a final refresh, releasing its surrounding batch early. It now passes
`ignore_refresh=True` on the per-item saves and uses its existing `finally` for
the final refresh. Native edit diffs, undo entries, waveform timer and final
commit are retained. No locks, sleeps, or intermediate edit dropping were added.

Reproduce the app overhead comparison (identical harness, same Python/build):

```sh
mkdir -p /tmp/openshot-editing-base
git archive de332e2c4 src | tar -x -C /tmp/openshot-editing-base
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 benchmarks/editing_latency.py --source /tmp/openshot-editing-base --iterations 25
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 benchmarks/editing_latency.py --iterations 25
# Repeat with --warm-query to populate the query cache before each measurement.
# Profile separately; never use profiler timings as performance results.
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 benchmarks/editing_latency.py --source /tmp/openshot-editing-base --iterations 3 --profile /tmp/editing.prof
```

Fresh query cache, 25 iterations; all times milliseconds. Full first-iteration,
median, p95 and maximum measurements are in the adjacent JSON files. The warm
cache comparison uses 10 iterations and is recorded separately. These samples
are local process measurements, with no claim of a release latency guarantee.

| Synthetic data workload | Operation | Median before → after | p95 before → after | Maximum before → after |
| --- | --- | --- | --- | --- |
| 8 overlapping clip records, 1000 waveform samples each | split | 7.36 → 2.27 | 7.84 → 2.49 | 7.86 → 3.41 |
| same | trim | 0.97 → 0.76 | 1.05 → 0.82 | 1.06 → 0.82 |
| 32 records, 30000 waveform samples each | split | 693.43 → 51.50 | 702.40 → 52.50 | 717.96 → 65.01 |
| same | trim | 26.56 → 19.43 | 34.47 → 19.81 | 337.23 → 20.13 |
| 500 short clip records, 1000 waveform samples each | split | 353.39 → 2.41 | 450.18 → 2.55 | 460.35 → 2.71 |
| same | trim | 1.16 → 0.91 | 1.28 → 0.96 | 1.35 → 1.05 |
| 32 records with edit/undo/redo dispatch | split | 56.69 → 7.02 | 60.27 → 9.69 | 87.09 → 56.41 |
| same | trim | 2.78 → 2.57 | 2.92 → 2.60 | 3.79 → 2.62 |

The harness calls real application split/trim helpers, project mutation and
history operations; it serializes binding payloads and counts refresh requests.
It excludes Qt event queue dispatch, native ApplyJsonDiff, reader creation,
cache invalidation, decoding, thumbnail/waveform generation and post-edit preview
rendering. In particular, its edit/undo scenario does **not** exercise an actual
playing native player. UI signals are test doubles. Tail stalls can include host
scheduling/GC; the single 337 ms baseline trim maximum has no attributed cause.

Reusable media for the outstanding UI/native measurements:

```sh
python3 benchmarks/generate_editing_projects.py /tmp/editing-projects
```

This creates a 30-second generated 720p24 test-pattern MP4 with AAC, a generated
MP3 sine tone, and four OSPs: overlapping media, a long-GOP clip (240 frames),
100 short clips, and overlapping media for edits during playback. Media are
synthetic and redistributable. Generation completed locally; ffprobe verified
H.264 1280×720 at 24 fps with AAC and 48 kHz MP3 audio. Enable clip waveforms in the short-clip project,
allow initial thumbnails/waveforms to finish, then repeat timings with their
cache cold and warm. Capture UI dispatch to final committed preview for split
and left/right trim separately, with and without playback; record median/p95/max,
engine build/path, project, zoom and display size. Repeat undo/redo, save/reopen,
linked edits and project close while work is pending. These end-to-end timings,
platform tests and engine/cache request bounds remain outstanding, to be run
with the combined companion changes. The current patch does not replace native
cache/audio validation.

Validation:

- `QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 -m unittest tests.test_editing_latency -q`: 7 tests pass. Covers multiple split final refresh, exception cleanup, mixed clip/transition batching, save/read/reload-history/undo/redo, repeated insert/delete, ID-based undo after sibling reorder, final trim value and preserved waveform, and serialization without snapshot mutation.
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s src/tests -t src/tests --quiet`: 981 tests pass, 20 skipped, 45.201 s.
- `QT_QPA_PLATFORM=offscreen python3 setup.py build --build-base build/ppa-tests`: passes.
- From `build/ppa-tests/lib`, `QT_QPA_PLATFORM=offscreen python3 -m unittest discover --quiet`: 981 tests pass, 20 skipped, 45.868 s.
- `QT_QPA_PLATFORM=offscreen PYTHONPATH=src OPENSHOT_QT_API=PyQt5 python3 -m unittest tests.test_qt_api tests.test_svg_watcher tests.test_preference_switch tests.test_toggle_switch -v`: 21 pass. PyQt6/PySide6, Windows and macOS were not run.

Reviewer checks: verify insert inverse deletes only the inserted ID; confirm
history stripping never mutates snapshots; confirm slice saves keep the batch
active and the final refresh still runs on failure; rerun source/package tests
after combining the direct-text and native patches. Only the two slice save
calls overlap `timeline.py`; preview/player code is unchanged.
