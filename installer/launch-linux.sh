#!/bin/sh

# Add the current folder the library path
HERE="$(dirname "$(readlink -f "${0}")")"
export LD_LIBRARY_PATH="${HERE}"

# Set some environment variables
export QT_PLUGIN_PATH="${HERE}"

# Launch application
exec "${HERE}"/openshot-qt "$@"
