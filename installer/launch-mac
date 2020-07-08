#!/bin/sh
# Get the current directory
CURR_DIR="$( cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_MAGICK_PATH="$CURR_DIR"

# Set some environment variables for ImageMagick and Qt5
export DYLD_LIBRARY_PATH="$IMAGE_MAGICK_PATH"
export MAGICK_CONFIGURE_PATH="$IMAGE_MAGICK_PATH/ImageMagick/etc/configuration"
export MAGICK_CODER_MODULE_PATH="$IMAGE_MAGICK_PATH/ImageMagick/modules-Q16/coders"
export QT_PLUGIN_PATH="$CURR_DIR"
export QT_DEBUG_PLUGINS="1"
export DYLD_PRINT_LIBRARIES="1"

echo "$CURR_DIR"
echo "$DYLD_LIBRARY_PATH"
echo "$QT_PLUGIN_PATH"

# Launch application
exec "$CURR_DIR/openshot-qt"
