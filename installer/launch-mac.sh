#!/bin/sh
CURR_DIR="$( cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_MAGICK_PATH="$CURR_DIR"

export DYLD_LIBRARY_PATH="$IMAGE_MAGICK_PATH"
export MAGICK_CONFIGURE_PATH="$IMAGE_MAGICK_PATH/ImageMagick/etc/configuration"
export MAGICK_CODER_MODULE_PATH="$IMAGE_MAGICK_PATH/ImageMagick/modules-Q16/coders"

# run application
exec "$CURR_DIR/launch"
