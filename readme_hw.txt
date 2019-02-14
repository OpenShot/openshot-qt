Observations for developers wanting to make hardware acceleration work:

HW accel is supported from ffmpeg version 3.2 (3.3 for nVidia drivers)
HW accel was removed for nVidia drivers in Ubuntu for ffmpeg 4.0 and up

The correct version of libva is needed (libva in Ubuntu 16.04 or libva2
 in Ubuntu 18.04) for the AppImage to work with hardware acceleration.

vaapi is working for intel, AMD
vaapi is working for import only for nouveau (nouveau only has decode)
nVidia driver is working for export only.

If the computer has multiple grafic cards installed one can be used for
input and one for output. It is also possible to use one for input and
output, or use only one for input or output.

Decoding and encoding on the (AMD) GPU can be done on systems where ROCm
is installed and run. Possible use for GPU acceleration of effects, ...

This information can be wrong. If you find something new or an error
please communicate the finding.
