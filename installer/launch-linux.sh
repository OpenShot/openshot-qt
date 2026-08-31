#!/bin/bash

# Add the current folder the library path
HERE=$(dirname "$(realpath "$0")")
export LD_LIBRARY_PATH="${HERE}"

# Set some environment variables
export QT_PLUGIN_PATH="${HERE}"

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

# Launch application
exec "${HERE}"/openshot-qt "$@"
