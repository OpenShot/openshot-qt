#!/bin/sh

# Add the current folder the library path
LD_LIBRARY_PATH="."

# Set some environment variables for ImageMagick and Qt5
export QT_PLUGIN_PATH="."
export QT_DEBUG_PLUGINS="1"

# Launch application
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}"/launch "$@"