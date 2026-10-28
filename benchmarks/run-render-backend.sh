#!/usr/bin/env bash
# Launch the checkout against a locally built libopenshot; installs are untouched.
# OPENSHOT_RENDER_BACKEND=vulkan bash benchmarks/run-render-backend.sh [OpenShot args]
# Add --check to validate imports without opening the editor.
set -euo pipefail

backend=${OPENSHOT_RENDER_BACKEND:-cpu}
case "$backend" in
    cpu) default_build=build-cpu-ffmpeg7 ;;
    vulkan) default_build=build-vk ;;
    *) echo 'OPENSHOT_RENDER_BACKEND must be cpu or vulkan' >&2; exit 2 ;;
esac
qt_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
lib_root=${OPENSHOT_LIB_ROOT:-"$(dirname -- "$qt_root")/libopenshot-git"}
if [[ -f "$lib_root/build-mvp-$backend/CMakeCache.txt" ]]; then
    default_build="build-mvp-$backend"
fi
build_dir=${OPENSHOT_BUILD_DIR:-"$lib_root/$default_build"}
if [[ ! -f "$build_dir/CMakeCache.txt" ]]; then
    echo "Missing build: $build_dir/CMakeCache.txt. Set OPENSHOT_BUILD_DIR to a configured libopenshot build." >&2
    exit 2
fi
build_dir=$(cd -- "$build_dir" && pwd)
cache="$build_dir/CMakeCache.txt"
cache_value() {
    awk -v key="$1" 'index($0,key ":")==1 {sub(/^[^=]*=/, ""); print; exit}' "$cache"
}
gpu_enabled=$(cache_value ENABLE_GPU_FRAME)
if [[ "$backend" == vulkan && "$gpu_enabled" != ON ]]; then
    echo 'Selected Vulkan build must be configured with ENABLE_GPU_FRAME=ON.' >&2; exit 2
elif [[ "$backend" == cpu && "$gpu_enabled" == ON ]]; then
    echo 'Selected CPU build has ENABLE_GPU_FRAME=ON; choose a CPU build directory.' >&2; exit 2
fi
bindings="$build_dir/bindings/python"
if [[ ! -f "$bindings/openshot.py" || ! -f "$bindings/_openshot.so" ]]; then
    echo "Missing Python bindings. Build them with: cmake --build '$build_dir' --target pyopenshot" >&2
    exit 2
fi
python=$(cache_value PYTHON_EXECUTABLE)
if [[ -z "$python" ]]; then python=$(cache_value Python3_EXECUTABLE); fi
if [[ -z "$python" || ! -x "$python" ]]; then
    echo 'No usable Python interpreter recorded in CMakeCache.txt. Reconfigure libopenshot Python bindings.' >&2
    exit 2
fi
ffmpeg_library=$(cache_value FFmpeg_avcodec_LIBRARIES)
ffmpeg_library=${ffmpeg_library%%;*}
if [[ ! -f "$ffmpeg_library" ]]; then
    echo "Cannot locate FFmpeg from build cache: $ffmpeg_library" >&2; exit 2
fi
export LD_LIBRARY_PATH="$build_dir/src:$(dirname -- "$ffmpeg_library")${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$bindings${PYTHONPATH:+:$PYTHONPATH}"
export OPENSHOT_RENDER_BACKEND="$backend"
export OPENSHOT_QT_API=${OPENSHOT_QT_API:-pyqt5}
# Older Vulkan loaders can choose llvmpipe before NVIDIA. Respect explicit ICDs.
if [[ "$backend" == vulkan && -z "${VK_ICD_FILENAMES:-}" && -z "${VK_DRIVER_FILES:-}" &&
      -f /usr/share/vulkan/icd.d/nvidia_icd.json ]] && command -v nvidia-smi >/dev/null && nvidia-smi -L >/dev/null 2>&1; then
    export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json
fi
"$python" - "$bindings" <<'PY'
import pathlib
import sys
try:
    import openshot
    import PyQt5.QtCore
except ImportError as error:
    raise SystemExit("Local OpenShot/PyQt5 import failed using %s: %s" % (sys.executable, error))
if pathlib.Path(openshot.__file__).resolve().parent != pathlib.Path(sys.argv[1]).resolve():
    raise SystemExit("Wrong openshot module loaded: " + openshot.__file__)
print("Python: " + sys.executable)
print("Bindings: " + openshot.__file__)
PY
printf 'Backend: %s; local build: %s\n' "$backend" "$build_dir"
if [[ "${1:-}" == --check ]]; then exit 0; fi
cd -- "$qt_root"
exec "$python" "$qt_root/src/launch.py" "$@"
