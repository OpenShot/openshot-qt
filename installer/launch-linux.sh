#!/bin/bash

# Query the current display DPI
#   This is to fix the AppImage, and scale the UI correctly
#   for high DPI displays. Ignore this logic if QT_SCREEN_SCALE_FACTOR
#   is already defined as an environment
if [[ -z "${QT_SCREEN_SCALE_FACTORS}" ]]; then
  regex="^.*resolution:\s*([0-9]*)x"
  DPI_OUTPUT=$(xdpyinfo | grep -B 2 resolution)
  [[ $DPI_OUTPUT =~ $regex ]]
  DPI=$(bc <<<"scale=2;${BASH_REMATCH[1]}/92")
  export QT_SCREEN_SCALE_FACTORS="$DPI"
fi

# Add the current folder the library path
HERE=$(dirname "$(realpath "$0")")
export LD_LIBRARY_PATH="${HERE}"

# Set some environment variables
export QT_PLUGIN_PATH="${HERE}"

# For Debian-based systems with newer openssl, see:
# https://github.com/OpenShot/openshot-qt/issues/3242
# https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=918727 
export OPENSSL_CONF="/dev/null"

# Launch application
exec "${HERE}"/openshot-qt "$@"
