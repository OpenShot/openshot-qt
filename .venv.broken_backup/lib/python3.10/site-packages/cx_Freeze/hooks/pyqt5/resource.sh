#!/bin/bash

# Get script directory (without using /usr/bin/realpath)
THIS_DIR=$(cd `dirname "${BASH_SOURCE[0]}"` && pwd)

pushd $THIS_DIR
pyrcc5 -o resource.py resource.qrc
popd
