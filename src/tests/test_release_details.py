"""
 @file
 @brief Unit tests for OpenShot release details helpers
 @author OpenShot Studios, LLC

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.
 """

import json
import os
import tempfile
from unittest.mock import patch
import sys
import unittest


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from classes import release_details


class ReleaseDetailsTests(unittest.TestCase):
    def test_release_details_url_accepts_official_versions(self):
        self.assertEqual(
            release_details.release_details_url("3.5.1"),
            "https://www.openshot.org/releases/3.5.1/",
        )

    def test_release_details_url_skips_development_versions(self):
        self.assertIsNone(release_details.release_details_url("3.5.1-dev"))

    def test_release_details_url_skips_release_candidates(self):
        self.assertIsNone(release_details.release_details_url("3.5.1-rc1"))

    def test_only_nonempty_matching_commit_confirms_release(self):
        for build, release, expected in (
                ({"openshot-qt": {"CI_COMMIT_SHA": "abc"}}, {"sha": "abc"}, True),
                ({"openshot-qt": {"CI_COMMIT_SHA": "daily"}}, {"sha": "abc"}, False),
                ({"openshot-qt": {}}, {}, False),
                ({"openshot-qt": {"CI_COMMIT_SHA": ""}}, {"sha": ""}, False),
                ({"openshot-qt": {"CI_COMMIT_SHA": None}}, {"sha": None}, False),
                ({"openshot-qt": {"CI_COMMIT_SHA": " "}}, {"sha": " "}, False),
                ({"openshot-qt": []}, {"sha": "abc"}, False),
                ({}, {"sha": "abc"}, False),
                (None, None, False)):
            with self.subTest(build=build, release=release):
                self.assertIs(release_details.is_release_build(build, release), expected)

    def test_build_metadata_missing_malformed_and_valid(self):
        with tempfile.TemporaryDirectory() as root, patch.object(release_details.info, "PATH", root):
            self.assertEqual(release_details.get_build_details(), {})
            os.mkdir(os.path.join(root, "settings"))
            path = os.path.join(root, "settings", "version.json")
            for content, expected in (
                    ("invalid json", {}), ("[]", {}), ("null", {}),
                    (json.dumps({"openshot-qt": {"CI_COMMIT_SHA": "abc"}}),
                     {"openshot-qt": {"CI_COMMIT_SHA": "abc"}})):
                with self.subTest(content=content):
                    with open(path, "w") as stream:
                        stream.write(content)
                    self.assertEqual(release_details.get_build_details(), expected)
            with patch("builtins.open", side_effect=PermissionError("unreadable")):
                self.assertEqual(release_details.get_build_details(), {})

    def test_release_lookup_uses_installed_version_and_survives_failure(self):
        with patch.object(release_details.http_client, "get_json", return_value={"sha": "abc"}) as get:
            self.assertEqual(release_details.get_release_details("4.0.1"), {"sha": "abc"})
            self.assertEqual(get.call_args.args[0][0], "https://www.openshot.org/releases/4.0.1/")
            get.reset_mock()
            self.assertIsNone(release_details.get_release_details("4.0.1-dev"))
            get.assert_not_called()
            for response in (None, [], "invalid"):
                get.return_value = response
                self.assertIsNone(release_details.get_release_details("4.0.1"))
            get.side_effect = RuntimeError("offline or missing release")
            self.assertIsNone(release_details.get_release_details("4.0.1"))


if __name__ == "__main__":
    unittest.main()
