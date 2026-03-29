#!/bin/bash

# Add the current folder the library path
HERE=$(dirname "$(realpath "$0")")
export LD_LIBRARY_PATH="${HERE}:${HERE}/lib:${LD_LIBRARY_PATH}"

# Ensure bundled Python modules are found before system site-packages
# (prevents conflicts with system-installed python3-openshot)
export PYTHONPATH="${HERE}/lib:${PYTHONPATH}"

# Set some environment variables
export QT_PLUGIN_PATH="${HERE}"

# For Debian-based systems with newer openssl, see:
# https://github.com/OpenShot/openshot-qt/issues/3242
# https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=918727
export OPENSSL_CONF="/dev/null"

# Launch application
exec "${HERE}"/zenvi "$@"
