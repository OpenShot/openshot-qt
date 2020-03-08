#!/bin/sh

# Add the current folder the library path
LD_LIBRARY_PATH="."

# Set some environment variables
export QT_PLUGIN_PATH="."

# For Debian-based systems with newer openssl, see:
# https://github.com/OpenShot/openshot-qt/issues/3242
# https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=918727 
export OPENSSL_CONF=/dev/null

# Launch application
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}"/openshot-qt "$@"
