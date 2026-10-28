# Vulkan MVP

## Goal

Find out how fast real 4K editing and export can be on an NVIDIA desktop and, later, an AMD Radeon laptop. Current focus: NVIDIA desktop only. Prioritize responsive timeline and file-preview playback, fast seeking, and fast exports in OpenShot itself.

## Scope and design

- One libopenshot codebase with CPU and Vulkan builds. Use `vulkan-mvp` branches based on the release branches in repositories needing changes.
- One build setting: `OPENSHOT_RENDER_BACKEND=cpu|vulkan`. CPU builds must retain current performance and require no Vulkan dependencies.
- Preserve existing libopenshot APIs, project behavior, audio, and timing. Check visual parity explicitly.
- Use reusable C++ surface/ownership wrappers and shared operation parameters to minimize duplication. Keep GPU frames resident across operations; materialize CPU images only when needed.
- Support import, file thumbnails, timeline thumbnail strips, timeline playback, and the file-preview dialog.
- Support basic track compositing and clip transforms: `scale_x/y`, `shear_x/y`, rotation, alpha, scale mode, and gravity.
- Hardware decode → GPU processing → GPU preview or hardware encode where supported. Report CPU fallbacks and transfers.
- Thumbnails: hardware decode → GPU scale → thumbnail-sized readback → CPU image encoding. Preserve existing frame/save APIs.
- Exclude effects, advanced transforms, and GPU still-image encoding from this MVP.

## Plan

- [x] Compile the optional Vulkan benchmark and smoke-test NVIDIA hardware decoding/compositing.
- [ ] Record CPU baselines and choose repeatable real 4K test clips/projects on both machines.
- [x] Add the build switch and GPU-backed frame abstraction, preserving the CPU path.
- [ ] Prove one 4K clip with basic transforms in the actual Qt preview, avoiding CPU readback. Cover both timeline and file-preview dialog.
- [ ] Complete basic compositing/transforms, thumbnails, seeking, and overlapping-clip playback.
- [ ] Connect full-resolution GPU rendering to hardware export, preserving audio and timing.
- [ ] Validate NVIDIA and AMD, compare visual output, and record final benchmarks.

## Success criteria and benchmarks

Measure playback at the actual preview size and exports at full resolution. Test a single 4K clip, then overlapping transformed clips. Record source codec/FPS, project settings, preview size, export codec/quality, hardware, drivers, build revisions, and commands alongside results. Separate startup and cold seeks from steady playback; repeat comparable runs.

Success means compatible basic editing, source-rate playback with minimal dropped frames on the selected workloads, responsive seeks, faster comparable exports, and no material CPU-build regression. Results—not assumptions—will establish the practical 4K limits.

| Machine / workload | Backend | Playback FPS / dropped frames | Seek-to-visible p50 / p95 | Export FPS | CPU↔GPU transfers / fallback |
| --- | --- | --- | --- | --- | --- |
| NVIDIA / TBD | CPU baseline | Pending | Pending | Pending | Pending |
| NVIDIA / TBD | Vulkan | Pending | Pending | Pending | Pending |
| AMD / TBD | CPU baseline | Pending | Pending | Pending | Pending |
| AMD / TBD | Vulkan | Pending | Pending | Pending | Pending |

## Progress notes — 2026-10-27/28

- **Implemented:** deferred GPU frame ownership, Vulkan decode/scale, progressive frame mapping, affine transforms and source-over compositing. Real 4K timeline frames remain GPU-backed across overlapping clips. GPU caches now honor byte budgets.
- **Preview:** Vulkan/OpenGL sharing preserves QPainter overlays. The native framebuffer test passes without CPU materialization. Basic editing works in OpenShot against the Vulkan build (confirmed manually 2026-10-28); full timeline and file-preview validation continues. Each repaint still rebuilds GL/Vulkan interop resources and waits on the GPU — the next playback-performance target.
- **Thumbnails:** real 4K decode → GPU resize → CPU PNG save and forward/backward seeks pass.
- **Export:** GPU RGBA → GPU NV12 → CUDA → NVENC works. The earlier black-frame problem is fixed: a 48-frame, two-layer 4K export matches the CPU build on every frame (PSNR ≥ 44.7 dB), at 30.8 fps vs 7.5 fps including startup. Audio validation is still pending. A failed GPU export falls back to CPU encoding for the rest of the export. Native FFmpeg Vulkan encoding crashed and is not used.
- **Compatibility:** CPU Frame, FrameMapper, Clip, FFmpegReader and FFmpegWriter suites pass. GPU ownership, renderer and compositor tests pass. Bilinear interpolation/chroma sampling still differ from CPU output; do not claim pixel identity. High-quality scaling and unsupported formats use CPU fallback. Accelerated source formats currently: 8-bit YUV420P/NV12/RGBA.
- **Fallbacks:** `OPENSHOT_RENDER_BACKEND=cpu` disables Vulkan at runtime in a GPU build; libopenshot then follows the unchanged CPU path (export output is bit-identical to a CPU build) and openshot-qt keeps the QWidget preview. Vulkan decode failures reopen the reader in software; transform/composite failures read back and use the CPU path; preview failures present a CPU image.
- **Machine:** RTX 5070, driver 580.82.09; local FFmpeg 7 and Vulkan headers. Python bindings use system Python 3.8 for PyQt5. ComfyUI restarted with permission to release cached VRAM. AMD testing deferred by request.

## Build, launch and measure

Repositories needing changes use `vulkan-mvp`; libopenshot-audio is unchanged. Build helper: `libopenshot-git/examples/build-render-backend.sh`. Launch helper: `openshot-qt-git/benchmarks/run-render-backend.sh`. Both accept `OPENSHOT_RENDER_BACKEND` and `OPENSHOT_BUILD_DIR`; dependency paths can be passed to the build helper as CMake arguments.

Existing desktop builds: GPU `libopenshot-git/build-vk`, matching-FFmpeg CPU `libopenshot-git/build-cpu-ffmpeg7`. The original CPU build remains available separately. From openshot-qt:

```sh
OPENSHOT_RENDER_BACKEND=vulkan OPENSHOT_BUILD_DIR=../libopenshot-git/build-vk \
  benchmarks/run-render-backend.sh
```

Build either backend from the same source: `-DENABLE_GPU_FRAME=ON` adds Vulkan (requires Vulkan headers and `glslangValidator`; shaders are embedded in the library), while the default `OFF` build has no Vulkan dependencies.

Tests: `ctest` in either build. Vulkan tests run automatically when a Vulkan device (and, for presentation, a display with OpenGL interop) is available, and are reported as skipped otherwise. Set `OPENSHOT_VULKAN_TEST_VIDEO` to exercise the reader cache test with a 4K clip.

`libopenshot-git/examples/run-timeline-benchmarks.py` runs sequential CPU/GPU comparisons and records JSON, commands and dependency versions. `openshot-export-benchmark` exercises full-resolution rendering with NVENC and optional audio. Final measurements must follow functional validation; earlier standalone/prototype timings are not final playback results.
