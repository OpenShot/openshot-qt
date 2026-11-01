#!/usr/bin/env python3
"""Check compiled hardware exports using only the AppImage's FFmpeg runtime."""
import ctypes
import os
from pathlib import Path
import subprocess  # nosec B404 - Runs controlled package checks without a shell.
import sys

ENCODERS = ('h264_nvenc', 'hevc_nvenc', 'h264_qsv', 'hevc_qsv', 'h264_amf', 'hevc_amf')


def check_runtime(bundle):
    bundle = Path(bundle).resolve()
    codec = ctypes.CDLL(str(bundle / 'libavcodec.so.61'))
    ctypes.CDLL(str(bundle / 'libvpl.so.2'))
    codec.avcodec_find_encoder_by_name.argtypes = [ctypes.c_char_p]
    codec.avcodec_find_encoder_by_name.restype = ctypes.c_void_p
    for encoder in ENCODERS:
        if not codec.avcodec_find_encoder_by_name(encoder.encode('ascii')):
            raise RuntimeError('Bundled FFmpeg lacks encoder: ' + encoder)
    # Reject accidental resolution from the runner SDK or system FFmpeg.
    for line in Path('/proc/self/maps').read_text().splitlines():
        path = line.split()[-1]
        if Path(path).name.startswith(('libavcodec.so.', 'libavformat.so.', 'libavutil.so.',
                                       'libswscale.so.', 'libswresample.so.', 'libvpl.so.')):
            if Path(path).resolve().parent != bundle:
                raise RuntimeError('Hardware export dependency loaded outside bundle: ' + path)
    print('PASS: bundled FFmpeg provides NVENC, QSV and AMF; FFmpeg and oneVPL resolve inside bundle')


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: check-linux-hardware.py APPIMAGE_USR_BIN')
    bundle = Path(sys.argv[1]).resolve()
    # Match launch-linux.sh: discard the build machine's SDK library path.
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(bundle)
    env.pop('LD_PRELOAD', None)
    subprocess.run([sys.executable,  # nosec B603 - Fixed interpreter and local checker; no shell. '-c',
                    'import runpy,sys; runpy.run_path(sys.argv[1])["check_runtime"](sys.argv[2])',
                    str(Path(__file__).resolve()), str(bundle)], env=env, check=True)


if __name__ == '__main__':
    main()
