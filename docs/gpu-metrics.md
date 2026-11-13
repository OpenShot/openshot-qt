# Experimental GPU measurements

The live preview and each completed export use the same four-segment widget.
Green means **above 75%**; amber means measured coverage at or below 75%; gray
means no applicable measurements. These are work-path percentages, not GPU
utilization, elapsed time, or a guarantee of an end-to-end host-free pipeline.

- Decode counts decoded hardware/software **video frames**. CPU-origin image
  requests are listed separately. Decoder readahead can exceed output frames.
- Render counts observed GPU/CPU operations, including source conversion,
  transforms, compositing and effects. It does not weight operations by cost.
- Copy-free counts GPU work requests that finish without a recorded readback.
  Initial CPU uploads are allowed and separately reported. Cache-only requests
  do not invent new work. This is not full per-frame pixel lineage tracking.
- Display counts the timeline preview's native/CPU presentation attempts.
- Encode counts successfully accepted hardware/software encoder submissions.

`libopenshot/src/GpuMetrics.{h,cpp}` owns two bounded counter sets: playback and
export. Thread-local `Scope` follows synchronous work and ignores unscoped
thumbnail/reader activity. A separate export timeline is marked before serving
frames. `FFmpegWriter::WriteMeasuredFrame` keeps reading, rendering and encoding
inside the same export scope, without adding per-frame Python callbacks.
Export prefetch belongs to the export's work counts; unrelated playback does not.

The scopes allocate no memory per frame. Event updates use relaxed atomic
increments. Readbacks have fixed reason categories rather than stack traces,
file paths, or an unbounded caller table. `Reason` tags the caller around an
operation that might materialize GPU pixels. Add counters only at an actual
operation/transfer, not at a capability check or repeated CPU-image access.

Reset swaps the counter generation. In-flight old work cannot change the new
session. New/Open Project resets playback; the dock's Reset does the same.
An export resets before its cache worker starts and freezes its snapshot after
that worker stops. The UI currently supports one measured export at a time.

`classes/gpu_metrics.py` interprets snapshots and preserves unknown stages for
older bindings. `windows/views/gpu_metrics.py` contains the reusable visualization,
its lightweight inspector dock, and the live preview adapter. Live UI reads cached
counters twice a second; completed export cards retain a frozen snapshot.

Unscoped transfers, including presentation outside native timeline work, are not
part of the copy-free denominator. Display is measured separately. Unknown caller
sites are grouped as Other. These limitations are deliberate for the first,
low-overhead development version; do not describe these counters as complete
memory-copy tracing.

CPU-origin artwork uses a bounded upload cache in `VulkanFrameImage.cpp`
(16 entries, at most 64 MiB of retained GPU allocations). The cache follows
QImage pixel cache keys, so changed pixels get a new upload and existing surfaces
remain immutable. Vulkan memory cleanup releases it; resetting measurements does
not force another upload of an already resident image. Decode remains neutral
for PNG/SVG sources, while transform/compositing and presentation can use GPU.
