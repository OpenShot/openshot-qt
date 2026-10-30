#!/bin/bash

# Add the current folder the library path
HERE=$(dirname "$(realpath "$0")")
export LD_LIBRARY_PATH="${HERE}"

# Set some environment variables
export QT_PLUGIN_PATH="${HERE}"

# Opt into Vulkan video decoding for this experimental build before loading Mesa.
# Each driver reads only its own settings. Encoding remains driver-default.
if [[ "${OPENSHOT_RENDER_BACKEND:-vulkan}" != cpu ]]; then
    case ",${RADV_PERFTEST:-}," in
        *,video_decode,*) ;;
        *) RADV_PERFTEST="${RADV_PERFTEST:+${RADV_PERFTEST},}video_decode" ;;
    esac
    export RADV_PERFTEST

    # Older Intel ANV uses a boolean; newer versions use an ANV_DEBUG flag.
    # Keep an explicit opt-out effective with either driver version.
    export ANV_VIDEO_DECODE="${ANV_VIDEO_DECODE-1}"
    case "${ANV_VIDEO_DECODE,,}" in
        0|false|no|off|'') ;;
        *)
            case ",${ANV_DEBUG:-}," in
                *,video-decode,*) ;;
                *) ANV_DEBUG="${ANV_DEBUG:+${ANV_DEBUG},}video-decode" ;;
            esac
            export ANV_DEBUG
            ;;
    esac
fi

# Prefer native desktop file dialogs through XDG Desktop Portal. Respect an
# explicit user override, and only select the theme when it was bundled.
if [[ -z "${QT_QPA_PLATFORMTHEME:-}" \
      && -f "${HERE}/platformthemes/libqxdgdesktopportal.so" ]]; then
    export QT_QPA_PLATFORMTHEME="xdgdesktopportal"
fi

# For Debian-based systems with newer openssl, see:
# https://github.com/OpenShot/openshot-qt/issues/3242
# https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=918727
export OPENSSL_CONF="/dev/null"

# The shared executable dispatches a leading --cli before importing Qt.
# Forward every argument verbatim; normal desktop launches still open the GUI.
# Launch application
exec "${HERE}"/openshot-qt "$@"
