#!/bin/bash

# Add the current folder the library path
HERE=$(dirname "$(realpath "$0")")
export LD_LIBRARY_PATH="${HERE}"

# Set some environment variables
export QT_PLUGIN_PATH="${HERE}"

# Prefer native file dialogs via XDG Desktop Portal, but only if a portal
# is actually reachable -- otherwise Qt's file dialogs silently fail to
# open. Ping instead of checking NameHasOwner so portals that are merely
# lazy-activated (not yet running) aren't skipped.
if [[ -z "${QT_QPA_PLATFORMTHEME:-}" \
      && -f "${HERE}/platformthemes/libqxdgdesktopportal.so" ]] \
      && command -v dbus-send >/dev/null 2>&1 \
      && timeout 2 dbus-send --session --print-reply \
           --dest=org.freedesktop.portal.Desktop \
           /org/freedesktop/portal/desktop \
           org.freedesktop.DBus.Peer.Ping >/dev/null 2>&1; then
    export QT_QPA_PLATFORMTHEME="xdgdesktopportal"
fi

# For Debian-based systems with newer openssl, see:
# https://github.com/OpenShot/openshot-qt/issues/3242
# https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=918727
export OPENSSL_CONF="/dev/null"

# Launch application
exec "${HERE}"/openshot-qt "$@"
