#!/bin/sh


usage()
{
    progname=$(basename $0)
    cat << __EOM__
${progname} - Replace system paths encoded into shared libraries

Usage: ${progname} HW_LIB_DIR
Arguments:
  HW_LIB_DIR	The directory containing libraries to be processed.
            	(Files will be modified IN PLACE, without backups.)
__EOM__
}

# Bail with usage information, if the directory path is unset
[ -z $1 ] && usage && exit -1

# We take one argument, the path in which to look for target libraries
hw_lib_dir=$(realpath "$1")

# Count files processed
((processed=0))

echo -n "Looking for libvdpau.so.1..."
hwlib="${hw_lib_dir}/libvdpau.so.1"
if [ -w "${hwlib}" ]; then
  echo -n " found, processing..."
  # 1: /usr/lib/x86_64-linux-gnu/vdpau => ./../lib/x86_64-linux-gnu/vdpau
  # 2: /usr/lib/vdpau => ./../lib/vdpau
  sed -i \
    -e 's,/usr\(/lib/x86_64-linux-gnu/vdpau\),\./\.\.\1,g' \
    -e 's,/usr\(/lib/vdpau\),\./\.\.\1,g' \
    "${hwlib}"
  echo " done."
  ((processed+=1))
else
  echo " NOT found, skipping."
fi

echo -n "Looking for libva.so.1..."
hwlib="${hw_lib_dir}/libva.so.1"
if [ -w "${hwlib}" ]; then
  echo -n " found, processing..."
  # /usr/lib/x86_64-linux-gnu/dri => ./../lib/x86_64-linux-gnu/dri
  sed -i -e 's,/usr\(/lib/x86_64-linux-gnu/dri\),\./\.\.\1,g' "${hwlib}"
  echo " done."
  ((processed+=1))
else
  echo " NOT found, skipping."
fi

# Final summary
echo "Files processed: ${processed}" && exit 0

