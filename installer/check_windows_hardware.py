#!/usr/bin/env python3
"""Check the frozen Windows app's export presets without runner DLLs or a GPU."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

REQUIRED_ENCODERS = ('h264_nvenc', 'hevc_nvenc', 'h264_qsv', 'hevc_qsv', 'h264_amf', 'hevc_amf')


def check_package(package):
    package = Path(package).resolve()
    executable = package / 'openshot-qt-cmd.exe'
    if not executable.is_file():
        raise RuntimeError('Missing packaged console executable: ' + str(executable))
    env = os.environ.copy()
    windows = env.get('SystemRoot', r'C:\Windows')
    env['PATH'] = os.pathsep.join((str(Path(windows) / 'System32'), windows))
    for name in ('PYTHONPATH', 'PYTHONHOME', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH'):
        env.pop(name, None)
    for name in ('openshot-qt-cmd.exe', 'openshot-cli.exe'):
        executable = package / name
        with tempfile.TemporaryDirectory(prefix='openshot-package-check-') as work:
            result = subprocess.run(
                [str(executable), '--cli', 'export', 'preset', 'list'],
                env=env, cwd=work, capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise RuntimeError(name + ' failed to load:\n' + result.stdout + result.stderr)
        # Startup diagnostics may precede the single CLI JSON response.
        responses = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        if not responses or not responses[-1].get('ok'):
            raise RuntimeError(name + ' returned no successful preset catalogue:\n' + result.stdout)
        presets = responses[-1]['result']
        available = {row['video_codec'] for row in presets if row['codecs_available']}
        missing = sorted(set(REQUIRED_ENCODERS) - available)
        if missing:
            raise RuntimeError(name + ' is missing hardware export presets/encoders: ' + ', '.join(missing))
    report = {'package': str(package), 'encoders': list(REQUIRED_ENCODERS),
              'validation': 'Frozen app loads without runner paths; compiled support only. GPU tests are separate.'}
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', help='Directory containing openshot-qt-cmd.exe')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = check_package(args.package)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
