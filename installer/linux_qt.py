# Copyright (c) 2026 OpenShot Studios, LLC
# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep Qt's display plugins bundled, and their driver-facing libraries on the host."""
import os
from pathlib import Path
import subprocess


HOST_DISPLAY_LIBRARIES = frozenset({
    'libEGL.so.1', 'libGLESv2.so.2', 'libgbm.so.1',
    'libwayland-client.so.0', 'libwayland-cursor.so.0',
    'libwayland-egl.so.1', 'libwayland-server.so.0',
})
WAYLAND_PLUGINS = (
    'platforms/libqwayland-generic.so',
    'platforms/libqwayland-egl.so',
    'wayland-graphics-integration-client/libqt-plugin-wayland-egl.so',
    'wayland-shell-integration/libxdg-shell.so',
)


def display_plugins(plugin_root):
    """Use the selected Qt installation for both plugins and dependency scanning."""
    root = Path(plugin_root)
    missing = [name for name in WAYLAND_PLUGINS if not (root / name).is_file()]
    if missing:
        raise RuntimeError('Qt Wayland plugins are required (install qtwayland5): ' + ', '.join(missing))
    plugins = list((root / 'platforms').glob('libqwayland*.so'))
    for group in ('xcbglintegrations', 'wayland-decoration-client',
                  'wayland-graphics-integration-client', 'wayland-shell-integration'):
        plugins.extend((root / group).glob('*.so'))
    return [(str(path), str(path.relative_to(root))) for path in sorted(plugins)]


def check_display_runtime(bundle):
    """Reject missing Qt dependencies and old libraries that break host Mesa EGL."""
    root = Path(bundle).resolve()
    required = ('libQt5WaylandClient.so.5',) + WAYLAND_PLUGINS
    missing = [name for name in required if not (root / name).is_file()]
    if missing:
        raise RuntimeError('AppImage is missing Qt Wayland runtime files: ' + ', '.join(missing))
    bundled_host_libraries = sorted(name for name in HOST_DISPLAY_LIBRARIES if (root / name).exists())
    if bundled_host_libraries:
        raise RuntimeError('AppImage must use host display libraries: ' + ', '.join(bundled_host_libraries))
    env = dict(os.environ, LD_LIBRARY_PATH=str(root))
    for name in WAYLAND_PLUGINS:
        result = subprocess.run(['ldd', str(root / name)], env=env, capture_output=True, text=True, check=False)
        if result.returncode or 'not found' in result.stdout or 'not found' in result.stderr:
            raise RuntimeError('Unresolved Qt display dependency for %s:\n%s%s' %
                               (name, result.stdout, result.stderr))
        for line in result.stdout.splitlines():
            if line.strip().startswith('libQt5') and '=>' in line:
                dependency = Path(line.split('=>', 1)[1].strip().split()[0]).resolve()
                if dependency.parent != root:
                    raise RuntimeError('Qt display dependency resolved outside AppImage: ' + str(dependency))
