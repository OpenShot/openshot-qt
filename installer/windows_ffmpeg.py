#!/usr/bin/env python3
"""Keep Windows packages on the selected FFmpeg build after cx_Freeze scans DLLs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

DLL_PATTERNS = ('avcodec-*.dll', 'avformat-*.dll', 'avutil-*.dll', 'avdevice-*.dll',
                'avfilter-*.dll', 'swscale-*.dll', 'swresample-*.dll', 'postproc-*.dll',
                'libvpl.dll')


def stage_ffmpeg_runtime(ffmpeg_root, package_root):
    source = Path(ffmpeg_root) / 'bin'
    target = Path(package_root) / 'lib'
    if not list(source.glob('avcodec-*.dll')):
        raise RuntimeError('No Windows FFmpeg DLLs found in ' + str(source))
    target.mkdir(parents=True, exist_ok=True)
    files = []
    for pattern in DLL_PATTERNS:
        for path in sorted(source.glob(pattern)):
            destination = target / path.name
            # cx_Freeze may have selected the SDK copy first. Always replace it.
            shutil.copy2(str(path), str(destination))
            files.append({'name': path.name, 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest()})
    licensing = Path(ffmpeg_root) / 'share' / 'vpl' / 'licensing'
    if licensing.is_dir():
        licenses = Path(package_root) / 'licenses' / 'oneVPL'
        licenses.mkdir(parents=True, exist_ok=True)
        for path in licensing.iterdir():
            if path.is_file():
                shutil.copy2(str(path), str(licenses / path.name))
    report = {'ffmpeg_root': str(Path(ffmpeg_root)), 'files': files}
    (Path(package_root) / 'windows-ffmpeg-runtime.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ffmpeg_root')
    parser.add_argument('package_root')
    args = parser.parse_args()
    print(json.dumps(stage_ffmpeg_runtime(args.ffmpeg_root, args.package_root), indent=2))
