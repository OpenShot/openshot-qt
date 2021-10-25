#!/bin/bash

# Query the current display DPI
#   Fix the AppImage devicePixelRatio and scale the UI correctly
#   for High DPI displays. Ignore this logic if QT_SCREEN_SCALE_FACTORS
#   is already defined as an environment. The format is a
#   semicolon-separated list of scale factors in the same order as
#   QGuiApplication::screens().
if [[ -z "${QT_SCREEN_SCALE_FACTORS}" ]]; then

  regex="^.*resolution:\s*([0-9]*)x"
  SCREENS=""
  xdpyinfo | while read -r line ; do
    # Loop through display results, looking for regex matches
    [[ $line =~ $regex ]]
    if [[ -n "${BASH_REMATCH[1]}" ]]; then
      # Found a DPI results match
      SCALE_FACTOR=$(bc <<<"scale=2;${BASH_REMATCH[1]}/92")
      SCREENS+="${SCALE_FACTOR};"
      echo "Detected scale factor: ${SCREENS}"
      export QT_SCREEN_SCALE_FACTORS="$SCREENS"
    fi

  done
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
