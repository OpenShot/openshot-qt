:: Get the current directory
SET IMAGE_MAGICK_PATH=%~dp0

:: Set some environment variables for ImageMagick
SET DYLD_LIBRARY_PATH=%IMAGE_MAGICK_PATH%
SET MAGICK_CONFIGURE_PATH=%IMAGE_MAGICK_PATH%ImageMagick\etc\configuration
SET MAGICK_CODER_MODULE_PATH=%IMAGE_MAGICK_PATH%ImageMagick\modules-Q16\coders

:: Launch application
launch.exe
