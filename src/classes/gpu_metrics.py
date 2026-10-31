"""Small snapshots for the GPU debug UI; native code owns all work counters."""
import json


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
    """No activity is unknown, never 0% or a green success."""
    rows = [('Decode', 'decode_gpu', 'decode_cpu'), ('Render', 'render_gpu', 'render_cpu'),
            ('Copy-free', 'copy_free', None),
            ('Encode', 'encode_gpu', 'encode_cpu') if exporting else ('Display', 'display_gpu', 'display_cpu')]
    result = []
    for label, gpu_key, cpu_key in rows:
        gpu = int(raw.get(gpu_key, 0))
        total = gpu + int(raw.get(cpu_key, 0)) if cpu_key else int(raw.get('gpu_requests', 0))
        percent = min(100, max(0, 100 * gpu / total)) if total else None
        unit = {'Decode': 'decoded video frames', 'Render': 'render operations',
                'Copy-free': 'GPU work requests', 'Display': 'presentation attempts',
                'Encode': 'encoder submissions'}[label]
        result.append(dict(label=label, gpu=gpu, total=total, percent=percent, unit=unit))
    return result
