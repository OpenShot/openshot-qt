"""Apply restart-only GPU preferences before the first native device is created."""
import os


def apply_gpu_preferences(settings, environ=None, native=None):
    environ = os.environ if environ is None else environ
    if 'OPENSHOT_RENDER_BACKEND' not in environ:
        environ['OPENSHOT_RENDER_BACKEND'] = ('cpu' if settings.get('gpu-mode') == 'cpu' else 'vulkan')
    device = settings.get('gpu-device')
    if device and 'OPENSHOT_VULKAN_DEVICE' not in environ:
        environ['OPENSHOT_VULKAN_DEVICE'] = str(device)
    configure = getattr(native, 'ConfigureGpuEnvironment', None)
    if callable(configure):
        configure(environ.get('OPENSHOT_RENDER_BACKEND', 'vulkan'),
                  environ.get('OPENSHOT_VULKAN_DEVICE', ''))
