# SPDX-FileCopyrightText: 2026 OpenShot Studios, LLC
# SPDX-License-Identifier: GPL-3.0-or-later
"""Small snapshots for the GPU debug UI; native code owns all work counters."""
import json


def N_(message):
    """Mark text for extraction; the UI translates it when displayed."""
    return message

# Live stages stay gray until they have this many operations, so the first
# imports, thumbnails and an empty timeline do not set the initial colors.
WARMUP_OPERATIONS = 10


class GpuMeasurements:
    def __init__(self, native, diagnostics=None):
        self.native, self.diagnostics = native, diagnostics

    def reset(self, exporting=False):
        reset = getattr(self.native, 'ResetGpuMetrics', None)
        if callable(reset):
            reset(exporting)
        if not exporting and self.diagnostics:
            with self.diagnostics.lock:
                for preview in self.diagnostics.previews.values():
                    preview.update(native_draws=0, cpu_draws=0, fallback_reasons=[])

    def snapshot(self, exporting=False):
        probe = getattr(self.native, 'GpuMetricsSnapshot', None)
        raw = json.loads(probe(exporting)) if callable(probe) else {}
        raw['native_available'] = callable(probe)
        if not exporting and self.diagnostics:
            previews = self.diagnostics.snapshot()['previews']
            raw['display_gpu'] = sum(p['native_draws'] for p in previews if p['name'] == 'timeline')
            raw['display_cpu'] = sum(p['cpu_draws'] for p in previews if p['name'] == 'timeline')
        return raw


def stages(raw, exporting=False):
    """No activity is unknown, never 0% or a green success. Frozen export reports
    are complete, so only the live preview waits for WARMUP_OPERATIONS."""
    warmup = 1 if exporting else WARMUP_OPERATIONS
    rows = [(N_('Decode'), 'decode_gpu', 'decode_cpu'), (N_('Render'), 'render_gpu', 'render_cpu'),
            (N_('Copy-free'), 'copy_free', None),
            (N_('Encode'), 'encode_gpu', 'encode_cpu') if exporting else (N_('Display'), 'display_gpu', 'display_cpu')]
    result = []
    for label, gpu_key, cpu_key in rows:
        gpu = int(raw.get(gpu_key, 0))
        total = gpu + int(raw.get(cpu_key, 0)) if cpu_key else int(raw.get('gpu_requests', 0))
        if exporting and label == 'Copy-free' and raw.get('export_frames', 0):
            # Rendering can happen on a cache worker, before the encoder's readback.
            # Use complete writer requests so those separate scopes cannot inflate this stage.
            gpu, total = int(raw.get('export_copy_free', 0)), int(raw['export_frames'])
        percent = min(100, max(0, 100 * gpu / total)) if total >= warmup else None
        unit = {'Decode': N_('decoded video frames'), 'Render': N_('render operations'),
                'Copy-free': N_('GPU work requests'), 'Display': N_('presentation attempts'),
                'Encode': N_('encoder submissions')}[label]
        if exporting and label == 'Copy-free' and raw.get('export_frames', 0):
            unit = N_('exported frames')
        result.append(dict(label=label, gpu=gpu, total=total, percent=percent, unit=unit,
                           warming=0 < total < warmup, warmup=warmup))
    return result


def export_acceleration(raw):
    """Describe measured video work; unknown counters must never imply success."""
    rows = stages(raw, exporting=True)
    if raw.get('native_available') is False or not any(row['total'] for row in rows):
        return 'unknown', N_('GPU acceleration unavailable'), N_('Acceleration measurements are unavailable for this export.')
    gpu_work = sum(int(raw.get(key, 0)) for key in ('decode_gpu', 'render_gpu', 'encode_gpu'))
    if not gpu_work:
        return 'none', N_('No GPU acceleration'), N_('Your computer’s main processor handled this export.')
    required = [row for row in rows if row['label'] != 'Decode' or not raw.get('image_sources') or row['total']]
    if all(row['percent'] == 100 for row in required) and not raw.get('readbacks', 0):
        return 'full', N_('Fully GPU accelerated'), N_('Your GPU handled the video from start to finish.')
    if raw.get('encode_cpu', 0) and not raw.get('encode_gpu', 0) and raw.get('render_gpu', 0):
        caption = N_('Your GPU prepared the video. Your CPU encoded the file.')
    else:
        caption = N_('Your GPU handled part of the video processing.')
    return 'partial', N_('Partially GPU accelerated'), caption
