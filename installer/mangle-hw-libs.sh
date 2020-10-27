#!/bin/sh


usage()
{
    progname="$(basename "$0")"
    cat << __EOM__
${progname} - Replace system paths encoded into shared libraries

Usage: ${progname} HW_LIB_DIR
Arguments:
  HW_LIB_DIR	The directory containing libraries to be processed.
            	(Files will be modified IN PLACE, without backups.)
__EOM__
}

# Bail with usage information, if the directory path is unset
[ -z "$1" ] && usage && exit -1

# We take one argument, the path in which to look for target libraries
if [ -d "$1" ]; then
  hw_lib_dir="$1"
else
  usage && exit -1
fi

fix_va_lib()
{
  lname="$1"
  echo -n "Looking for ${lname}..."
  hwlib="${hw_lib_dir}/${lname}"
  if [ -w "${hwlib}" ]; then
    echo -n " found, processing..."
    # /usr/lib/x86_64-linux-gnu/dri => ./../lib/x86_64-linux-gnu/dri
    sed -i -e 's,/usr\(/lib/x86_64-linux-gnu/dri\),\./\.\.\1,g' "${hwlib}"
    echo " done."
  else
    echo " NOT found, skipping."
  fi
}

for libname in "libva.so.1" "libva.so.2"; do
  fix_va_lib $libname;
done

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
else
  echo " NOT found, skipping."
fi

exit 0
