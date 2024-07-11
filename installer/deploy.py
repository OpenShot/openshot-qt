"""
 @file
 @brief Script used to deploy and publish openshot-qt
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
import datetime
import platform
import traceback
import re
import urllib3
from github3 import login
from github3.models import GitHubError
from requests.auth import HTTPBasicAuth
from requests import post, get, head
from build_server import (
    output, run_command, error, truncate,
    zulip_upload_log, get_release, upload,
    errors_detected, log,
    version_info, parse_version_info)

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))  # Primary openshot folder
RELEASE_NAME_REGEX = re.compile(r'^OpenShot-v.*?(-.*?)-x86[_64]*')
DOWNLOAD_PAGE_URLS = re.compile(r'"(//github.com/OpenShot/openshot-qt/releases/download/v.*?/OpenShot-.*?)"',
                                re.MULTILINE)

# Access info class (for version info)
sys.path.append(os.path.join(PATH, 'src', 'classes'))

# Disable SSL warnings
urllib3.disable_warnings()


def main():
    # Only run this code when directly executing this script.

    zulip_token = None
    github_user = None
    github_pass = None
    github_release = None
    is_publish = False
    script_mode = "deploy"  # deploy or publish
    repo_names = ["openshot-qt", "libopenshot", "libopenshot-audio"]

    try:
        # Validate command-line arguments
        if len(sys.argv) >= 2:
            zulip_token = sys.argv[1]
        if len(sys.argv) >= 4:
            github_user = sys.argv[2]
            github_pass = sys.argv[3]

            # Login and get "GitHub" and repo objects
            repos = {}
            gh = login(github_user, github_pass)
            for repo_name in repo_names:
                repos[repo_name] = gh.repository("OpenShot", repo_name)

        if len(sys.argv) >= 5:
            arg_value = sys.argv[4]
            if arg_value.lower() == "true":
                is_publish = True
                script_mode = "publish"

        # Start log
        output("%s %s Log for %s" % (
            platform.system(),
            script_mode,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        # Detect artifact folder (if any)
        artifact_dir = os.path.join(PATH, "build")

        # Parse artifact version files (if found)
        for repo_name in repo_names:
            data_file = f"{repo_name}.env"
            version_info.update(parse_version_info(
                os.path.join(artifact_dir, "install-x64", "share", data_file)))
        output(str(version_info))

        # Get version info
        openshot_qt_version = version_info.get('openshot-qt', {}).get('VERSION', 'N/A')
        release_git_sha = version_info.get('openshot-qt', {}).get('CI_COMMIT_SHA', 'N/A')

        # Verify branch names are all the same (across the 3 repos)
        # Ignore "develop" branches (since sometimes we have no changes in one or more repos)
        original_git_branch = ''
        for repo_name in repo_names:
            git_branch_name = version_info.get(repo_name, {}).get('CI_COMMIT_REF_NAME')
            if git_branch_name == 'develop':
                continue
            if not original_git_branch:
                original_git_branch = git_branch_name
            if original_git_branch != git_branch_name:
                # Branch names do not match
                raise Exception(
                    "Branch names do not match for all 3 repos: `%s` vs `%s`" %
                    (original_git_branch, git_branch_name))

        # Loop through and get and/or create the GitHub Release objects
        releases = {}
        for repo_name in repo_names:
            # Look for GitHub Release object (if any)
            git_branch_name = version_info.get(repo_name, {}).get('CI_COMMIT_REF_NAME')
            github_release_name = "v%s" % version_info.get(repo_name, {}).get('VERSION')
            if "-" in github_release_name:
                # Ensure the version is set to a correct one (and not a `-dev` one)
                raise Exception("Version cannot contain a '-' character: %s (repo: %s, branch: %s)" %
                                (github_release_name, repo_name, git_branch_name))

            if git_branch_name == 'develop':
                output(f"Skipping develop branch for repo: {repo_name}")
                continue
            if git_branch_name.startswith("release"):
                # Get official version release (i.e. v2.1.0, v2.x.x)
                releases[repo_name] = get_release(repos.get(repo_name), github_release_name)
                if releases.get(repo_name) and releases.get(repo_name).prerelease is False:
                    raise Exception(
                        "GitHub release for version %s is already released. Did we forget to bump a "
                        "version? (repo: %s, branch: %s)" % (
                            github_release_name, repo_name,
                            git_branch_name)
                    )
            else:
                # ignore all branches that don't start with 'release*'
                raise Exception("%s only allowed for branch names that start with 'release*' (repo: %s, branch: %s)" % (script_mode, repo_name, git_branch_name))

        if not is_publish:

            # Read in git logs from all 3 repos (located in artifacts)
            logs = {}
            log_folder = os.path.join(artifact_dir, "install-x64", "share")
            for log_name in os.listdir(log_folder):
                if log_name.endswith(".log"):
                    log_path = os.path.join(log_folder, log_name)
                    with open(log_path, "r", encoding="UTF-8") as f:
                        log_contents = f.read()
                        logs[os.path.splitext(log_name)[0]] = log_contents
            # Combine logs into 1 string (with markdown support)
            log_title = "Highlights & Features:\n===\n - Placeholder 1\n - Placeholder 2\n\n"
            combined_log_markdown = ""
            formatted_logs = {}
            for repo_name in repo_names:
                if repo_name in logs.keys():
                    so_number = version_info.get(repo_name, {}).get('SO')
                    so_title = ""
                    if so_number:
                        so_title = ", SO: %s" % so_number
                    log_markdown = "%s Changelog (Version: %s%s)\n---\n%s\n\n" % (
                        repo_name, version_info.get(repo_name, {}).get('VERSION'), so_title, logs.get(repo_name))
                    formatted_logs[repo_name] = log_title + log_markdown
                    combined_log_markdown += log_markdown

            # Create GitHub Release (if needed)
            for repo_name in repo_names:
                git_branch_name = version_info.get(repo_name, {}).get('CI_COMMIT_REF_NAME')
                if git_branch_name == 'develop':
                    continue
                # If NO release is found, create a new one
                github_release_name = "v%s" % version_info.get(repo_name, {}).get('VERSION')
                if not releases.get(repo_name):
                    # Create a new release if one if missing (for each repo)
                    releases[repo_name] = repos.get(repo_name).create_release(
                        github_release_name,
                        target_commitish=git_branch_name,
                        prerelease=True,
                        body=formatted_logs.get(repo_name)[:125000])

            # Upload all deploy artifacts/installers to GitHub
            # NOTE: ONLY for `openshot-qt` repo
            # github_release_url = github_release.html_url
            github_release = releases.get('openshot-qt')
            for artifact_orig_name in os.listdir(artifact_dir).copy():
                print("--- %s" % artifact_orig_name)
                artifact_path_orig = os.path.join(artifact_dir, artifact_orig_name)
                match = RELEASE_NAME_REGEX.match(artifact_orig_name)
                if match and match.groups():
                    # Rename artifact before uploading
                    file_name_pattern = match.groups()[0]
                    artifact_name = artifact_orig_name.replace(file_name_pattern, "")
                    artifact_path = os.path.join(artifact_dir, artifact_name)
                    os.rename(artifact_path_orig, artifact_path)
                else:
                    # Leave artifact with the original name
                    artifact_name = artifact_orig_name
                    artifact_path = artifact_path_orig
                artifact_base, artifact_ext = os.path.splitext(artifact_name)

                if artifact_ext in ['.torrent', '.verify', '.sha256sum']:
                    # Delete torrent and continue (we'll recreate the torrents below when needed)
                    # The artifact torrents have the incorrect URL inside them
                    os.unlink(artifact_path)
                    continue

                if os.path.exists(artifact_path) and artifact_ext in ['.exe', '.dmg', '.AppImage']:
                    # Valid artifact/installer - Upload to GitHub Release
                    output("GitHub: Uploading %s to GitHub Release: %s" % (artifact_path, github_release.tag_name))
                    download_url = upload(artifact_path, github_release)

                    # Create shasum and torrents for installers-only
                    if artifact_ext in ['.exe', '.dmg', '.AppImage']:
                        output("Generating file hash for %s" % artifact_path)
                        shasum_output = ''
                        for line in run_command('shasum -a 256 "%s"' % artifact_name, artifact_dir):
                            output(line)
                            if line:
                                shasum_output = line.decode('UTF-8').strip()

                        # Download the installer we just uploaded (so we can check the shasum)
                        r = get(download_url)
                        check_artifact_path = artifact_path + ".tmp"
                        with open(check_artifact_path, "wb") as f:
                            f.write(r.content)
                            f.flush()
                            f.seek(0)
                        output("Generating file validation hash for %s" % check_artifact_path)
                        shasum_check_output = ""
                        for line in run_command('shasum -a 256 "%s"' % check_artifact_path, artifact_dir):
                            output(line)
                            if line:
                                shasum_check_output = line.decode('UTF-8').strip()
                        if shasum_output.split(" ")[0] != shasum_check_output.split(" ")[0]:
                            raise Exception(
                                "shasum validation of %s has failed after downloading "
                                "the uploaded installer: %s.\n%s\n%s" % (
                                    check_artifact_path, artifact_path, shasum_check_output, shasum_output)
                            )

                        # Create and upload sha2sum file and instructions
                        output("Hash generated: %s" % shasum_output)
                        sha256sum_path = os.path.join(artifact_dir, "%s.sha256sum") % artifact_name
                        with open(sha256sum_path, "w", encoding="UTF-8") as f:
                            f.write(shasum_output)
                        upload(sha256sum_path, github_release)

                        sha256sum_instructions_path = os.path.join(artifact_dir, "%s.sha256sum.verify") % artifact_name
                        with open(sha256sum_instructions_path, "w", encoding="UTF-8") as f:
                            f.write('Run this command in your terminal in the directory OpenShot was downloaded to verify '
                                    'the SHA256 checksum:%s' % os.linesep)
                            f.write('  echo "%s" | shasum -a 256 --check%s%s' % (shasum_output, os.linesep, os.linesep))
                            f.write('You should get the following output:%s' % os.linesep)
                            f.write('  %s: OK' % artifact_name)
                        upload(sha256sum_instructions_path, github_release)

                        # Create torrent and upload
                        torrent_name = "%s.torrent" % artifact_name
                        torrent_path = os.path.join(artifact_dir, torrent_name)
                        tracker_list = [
                            "udp://tracker.openbittorrent.com:80/announce",
                            "udp://tracker.publicbt.com:80/announce",
                            "udp://tracker.opentrackr.org:1337",
                            ]
                        torrent_command = " ".join([
                            'mktorrent',
                            '-a "%s"' % (", ".join(tracker_list)),
                            '-c "OpenShot Video Editor %s"' % github_release.tag_name,
                            '-w "%s"' % download_url,
                            '-o "%s"' % torrent_name,
                            '"%s"' % artifact_name,
                            ])
                        torrent_output = ""
                        for line in run_command(torrent_command, artifact_dir):
                            output(line)
                            if line:
                                torrent_output = line.decode('UTF-8').strip()

                        if not torrent_output.endswith("Writing metainfo file... done."):
                            # Torrent failed
                            raise Exception("Failed to create .torrent for %s" % download_url)

                        # Torrent succeeded! Upload the torrent to github
                        url = upload(torrent_path, github_release)

            # Submit blog post (if it doesn't already exist) (in draft mode)
            auth = HTTPBasicAuth(os.getenv('OPENSHOT_ORG_USER'), os.getenv('OPENSHOT_ORG_PASS'))
            r = post(
                "https://www.openshot.org/api/release/submit/",
                auth=auth,
                data={
                    "version": openshot_qt_version,
                    "changelog": log_title + combined_log_markdown,
                    "sha": release_git_sha
                    })
            if not r.ok:
                raise Exception(
                    "HTTP post to openshot.org/api/release/submit/ failed: %s (user: %s): %s" % (
                        r.status_code,
                        os.getenv('OPENSHOT_ORG_USER'),
                        r.content.decode('UTF-8'))
                )
        else:
            # Publish the release (make new version visible on openshot.org, and make blog post visible)
            auth = HTTPBasicAuth(os.getenv('OPENSHOT_ORG_USER'), os.getenv('OPENSHOT_ORG_PASS'))
            r = post(
                "https://www.openshot.org/api/release/publish/",
                auth=auth,
                data={"version": openshot_qt_version})
            if not r.ok:
                raise Exception(
                    "HTTP post to openshot.org/api/release/publish/ failed: %s (user: %s): %s" % (
                        r.status_code,
                        os.getenv('OPENSHOT_ORG_USER'),
                        r.content.decode('UTF-8')))

            # Publish GitHub Release objects (in all 3 repos)
            for repo_name in repo_names:
                git_branch_name = version_info.get(repo_name, {}).get('CI_COMMIT_REF_NAME')
                if git_branch_name == 'develop':
                    continue
                # If NO release is found, create a new one
                github_release = releases.get(repo_name)
                if github_release:
                    # Publish github release also
                    github_release.edit(prerelease=False)
                else:
                    raise Exception("Cannot publish missing GitHub release: %s, version: %s" % (repo_name, openshot_qt_version))

            # Verify download links on openshot.org are correct (and include the new release version)
            r = get("https://www.openshot.org/download/")
            if r.ok:
                # Find all release download URLs on openshot.org
                urls = DOWNLOAD_PAGE_URLS.findall(r.content.decode('UTF-8'))
                for url in urls:
                    # Only GET the header of each URL, to validate it is valid and found
                    r = head("https:" + url)
                    if r.ok and r.reason == "Found":
                        output("Validation of URL successful: %s" % url)
                    else:
                        raise Exception(
                            "Validation of URL FAILED: %s, %s, %s" % (
                                url, r.status_code, r.reason)
                        )

                    # Validate the current version is found in each URL
                    if openshot_qt_version not in url:
                        raise Exception(
                            "Validation of URL FAILED. Missing version %s: %s, %s, %s" % (
                                openshot_qt_version, url, r.status_code, r.reason)
                        )
            else:
                raise Exception(
                    "Failed to GET openshot.org/download for URL validation: %s" % r.status_code)

    except Exception as ex:
        tb = traceback.format_exc()
        error("Unhandled %s exception: %s - %s" % (script_mode, str(ex), str(tb)))
        if type(ex) == GitHubError:
            error(str(ex.errors))

    if not errors_detected:
        output("Successfully completed %s script!" % script_mode)
        zulip_upload_log(
            zulip_token, log,
            "%s: %s **success** log" % (platform.system(), script_mode),
            ":congratulations:  successful %s" % script_mode)
    else:
        # Report any errors detected
        output("%s script failed!" % script_mode)
        zulip_upload_log(
            zulip_token, log,
            "%s: %s error log" % (platform.system(), script_mode),
            ":skull_and_crossbones: %s" % truncate(errors_detected[0], 100))
        exit(1)


if __name__ == "__main__":
    main()
