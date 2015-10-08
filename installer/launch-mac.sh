#!/bin/sh
# Get the current directory
CURR_DIR="$( cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_MAGICK_PATH="$CURR_DIR"

# Set some environment variables for ImageMagick
export DYLD_LIBRARY_PATH="$IMAGE_MAGICK_PATH"
export MAGICK_CONFIGURE_PATH="$IMAGE_MAGICK_PATH/ImageMagick/etc/configuration"
export MAGICK_CODER_MODULE_PATH="$IMAGE_MAGICK_PATH/ImageMagick/modules-Q16/coders"

# Launch application
exec "$CURR_DIR/launch"
