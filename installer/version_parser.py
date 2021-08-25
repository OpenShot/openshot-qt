"""
 @file
 @brief Parse version info files for libopenshot-audio, libopenshot, and openshot-qt (created on gitlab-ci.yml)
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2016 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

import os
import sys
import json
import datetime

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))  # Primary openshot folder
sys.path.append(os.path.join(PATH, 'src', 'classes'))


def parse_version_info(version_path):
    """Parse version info from gitlab artifacts"""
    version_info = {"date": f'{datetime.datetime.now():%Y-%m-%d %H:%M}'}

    # Get name of version file
    file_name = os.path.basename(version_path)
    version_name = os.path.splitext(file_name)[0]
    version_info[version_name] = {
        "CI_PROJECT_NAME": None,
        "CI_COMMIT_REF_NAME": None,
        "CI_COMMIT_SHA": None,
        "CI_JOB_ID": None,
        "CI_PIPELINE_ID": None,
        "VERSION": None,
        "SO": None,
        }

    if os.path.exists(version_path):
        with open(version_path, "r") as f:
            # Parse each line in f as a 'key:value' string
            version_info[version_name].update(
                (ln.strip().split(':') for ln in f.readlines())
            )

    return version_info


def parse_build_name(version_info, git_branch_name=""):
    """Calculate the build name used in URLs and Installers from the version_info dict"""
    # Check for all version info needed to construct the build URL
    build_name = ""
    release_label = ""

    # Determine release type string to inject
    if git_branch_name.startswith("release"):
        # Release candidate
        release_label = "release-candidate"
    else:
        # Daily
        release_label = "daily"

    if all(key in version_info for key in ("libopenshot", "libopenshot-audio", "openshot-qt")):
        # Construct base build URL pattern
        if release_label:
            # Daily and Release Candidates
            build_name = "OpenShot-v%s-%s-%s-%s-%s" % (
                version_info.get('openshot-qt', {}).get('VERSION'),
                release_label,
                version_info.get('openshot-qt', {}).get('CI_PIPELINE_ID', 'NA'),
                version_info.get('libopenshot', {}).get('CI_COMMIT_SHA', 'NA')[:8],
                version_info.get('libopenshot-audio', {}).get('CI_COMMIT_SHA', 'NA')[:8],
            )
        else:
            # Official releases
            build_name = "OpenShot-v%s" % version_info.get('openshot-qt', {}).get('VERSION')

    return build_name


if __name__ == "__main__":
    """Run these methods manually for testing"""
    # Determine absolute PATH of OpenShot folder
    PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))  # Primary openshot folder

    version_info = {}
    settings_path = os.path.join(PATH, "src", "settings")

    # Parse all version info (if found)
    for git_log_filename in os.listdir(settings_path):
        if git_log_filename.endswith(".env"):
            # Metadata file, parse version info
            git_log_filepath = os.path.join(settings_path, git_log_filename)
            version_info.update(parse_version_info(git_log_filepath))

    # Calculate build name from version info
    version_info["build_name"] = parse_build_name(version_info, "daily")
    version_info["build_name"] = parse_build_name(version_info, "release-123-abc")
    version_info["build_name"] = parse_build_name(version_info, "master")

    # Dump version info to json string
    print(json.dumps(version_info, indent=4, sort_keys=True))
