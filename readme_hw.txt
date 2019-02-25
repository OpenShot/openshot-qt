Observations for developers wanting to make hardware acceleration work:

All observations are for Linux.

HW accel is supported from ffmpeg version 3.2 (3.3 for nVidia drivers)
HW accel was removed for nVidia drivers in Ubuntu for ffmpeg 4.0 and up

I could not manage to built a version of ffmpeg 4.1 with the nVidia SDK
that worked with nVidia cards. There might be a problem in ffmpeg 4.0
and up that prohibits this.

Notice: The ffmpeg versions of Ubuntu and PPAs for Ubuntu schow the
same behaviour. ffmpeg 3 has working nVidia hardware acceleration while
ffmpeg 4.0 and up has no support for nVidia hardware acceleration
included.

The correct version of libva is needed (libva in Ubuntu 16.04 or libva2
 in Ubuntu 18.04) for the AppImage to work with hardware acceleration.
 A AppImage that works on both systems, libva and libva2, might be possible
 when no libva is included in the AppImage.

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

---------------------------------------------------------------------------
DESPERATELY NEEDED: a way to compile ffmpeg 4.0 and up with working nVidia
hardware acceleration support on Ubuntu Linux!!!!!!!!!!!!!!!!!!!!!!!!!
