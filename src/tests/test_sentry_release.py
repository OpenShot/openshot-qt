"""Release classification through the startup version check and Sentry SDK."""

import os
import sys
import tempfile
import json
import unittest
from unittest.mock import Mock, patch

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.insert(0, PATH)

from classes import info, release_details, sentry, version


class SentryReleaseTests(unittest.TestCase):
    def test_startup_classifies_before_sentry_initializes(self):
        rates = dict(openshot_version="4.0.1", error_rate_stable=0.1,
                     error_rate_unstable=0.9, trans_rate_stable=0.2,
                     trans_rate_unstable=0.8)
        # The same version can represent the release, a daily, or an unknown
        # build. A promoted RC is recognized by SHA, not by its filename.
        for build_sha, release, latest, expected in (
                ("release-sha", {"sha": "release-sha"}, "4.0.1", "production"),
                ("daily-sha", {"sha": "release-sha"}, "4.0.1", "unstable"),
                # Once a newer version is current, even a matching release SHA
                # must use the unstable environment and sampling rates.
                ("release-sha", {"sha": "release-sha"}, "4.0.2", "unstable"),
                ("", {"sha": ""}, "4.0.1", "unstable"),
                (None, {"sha": "release-sha"}, "4.0.1", "unstable"),
                ("release-sha", RuntimeError("offline"), "4.0.1", "unstable"),
                ("release-sha", {}, "4.0.1", "unstable")):
            with self.subTest(build_sha=build_sha, release=release, latest=latest), \
                    tempfile.TemporaryDirectory() as root:
                os.mkdir(os.path.join(root, "settings"))
                if build_sha is not None:
                    with open(os.path.join(root, "settings", "version.json"), "w") as stream:
                        json.dump({"openshot-qt": {"CI_COMMIT_SHA": build_sha},
                                   "build_name": "OpenShot-v4.0.1-release-candidate-123"}, stream)
                sdk = Mock()
                app = Mock()
                # The real startup callback initializes Sentry upon this signal.
                app.window.FoundVersionSignal.emit.side_effect = lambda _: sentry.init_tracing()
                with patch.multiple(info, PATH=root, VERSION="4.0.1",
                                    ERROR_REPORT_IS_RELEASE=True,
                                    ERROR_REPORT_STABLE_VERSION=None,
                                    ERROR_REPORT_RATE_STABLE=0.0,
                                    ERROR_REPORT_RATE_UNSTABLE=0.0,
                                    TRANS_REPORT_RATE_STABLE=0.0,
                                    TRANS_REPORT_RATE_UNSTABLE=0.0), \
                        patch.object(version, "get_app", return_value=app), \
                        patch.object(release_details.http_client, "get_json", side_effect=[
                            dict(rates, openshot_version=latest), release]) as get, \
                        patch.object(sentry, "sdk", sdk):
                    version.get_version_from_http()
                    app.window.FoundVersionSignal.emit.assert_called_once_with(latest)
                    sdk.init.assert_called_once()
                    options = sdk.init.call_args.kwargs
                    self.assertEqual(options["release"], "openshot@4.0.1")
                    self.assertEqual(options["environment"], expected)
                    stable = expected == "production"
                    self.assertEqual(options["sample_rate"], 0.1 if stable else 0.9)
                    self.assertEqual(options["traces_sample_rate"], 0.2 if stable else 0.8)
                    self.assertEqual(get.call_args.args[0][0],
                                     "https://www.openshot.org/releases/4.0.1/")

    def test_failed_version_lookup_clears_previous_confirmation(self):
        with patch.object(info, "ERROR_REPORT_IS_RELEASE", True), \
                patch.object(version.http_client, "get_json", side_effect=RuntimeError("offline")), \
                patch.object(version, "get_app") as get_app:
            version.get_version_from_http()
            self.assertFalse(info.ERROR_REPORT_IS_RELEASE)
            get_app.assert_not_called()


if __name__ == "__main__":
    unittest.main()
