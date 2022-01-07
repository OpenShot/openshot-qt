#!/bin/sh -x

if [ ! -d ".git" ]; then
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
#chcon -R -t container_file_t docs
