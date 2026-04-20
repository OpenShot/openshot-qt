#!/bin/bash

# Add the current folder the library path
HERE=$(dirname "$(realpath "$0")")
export LD_LIBRARY_PATH="${HERE}"

# Set some environment variables
export QT_PLUGIN_PATH="${HERE}"
if [ -z "${QT_QPA_PLATFORM:-}" ] && [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
    if [ -f "${HERE}/platforms/libqwayland-egl.so" ] || [ -f "${HERE}/platforms/libqwayland-generic.so" ]; then
        export QT_QPA_PLATFORM="wayland"
    fi
fi

# For Debian-based systems with newer openssl, see:
# https://github.com/OpenShot/openshot-qt/issues/3242
# https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=918727
export OPENSSL_CONF="/dev/null"

# Launch application
exec "${HERE}"/openshot-qt "$@"
