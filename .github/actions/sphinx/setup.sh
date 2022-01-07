#!/bin/sh -x

if [ ! -d ".git" -a ! -z "$GITHUB_WORKSPACE" ]; then
	cd "$GITHUB_WORKSPACE"
fi

if [ -e "docs/_docker" ]; then
	echo "Directory 'docs/_docker' already exists."
	exit 0
elif [ ! -d "docs" ]; then
	echo "ERROR!! Don't see 'docs' subdirectory of `pwd`. Cannot continue."
	exit -1
fi

mkdir docs/_docker
cp src/classes/info.py          docs/_docker/info.py
cp xdg/openshot-arrow.png       docs/_docker/openshot-arrow.png
cp xdg/openshot-qt.ico          docs/_docker/openshot-qt.ico
cp xdg/icon/512/openshot-qt.png docs/_docker/openshot-qt.png
cd docs/_docker

echo "
import info
import os
if os.path.exists('docs_version.txt'):
    os.unlink('docs_version.txt')
with open('docs_version.txt', 'w') as f:
    f.write(f'{info.VERSION}')
" | python3

