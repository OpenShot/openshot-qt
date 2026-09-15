"""
 @file
 @brief Unit tests for shared HTTP helpers
 @author OpenShot Studios, LLC

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.
 """

import os
import sys
import types
import unittest
from unittest.mock import patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from classes import http_client


class HttpClientTests(unittest.TestCase):
    def test_urls_with_http_fallback_prefers_https(self):
        self.assertEqual(
            http_client.urls_with_http_fallback("https://example.com/file.zip"),
            ["https://example.com/file.zip", "http://example.com/file.zip"],
        )

    def test_get_json_falls_back_to_http_after_https_failure(self):
        class Response:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"ok": True}

        with patch.object(
            http_client.requests,
            "get",
            side_effect=[RuntimeError("ssl failed"), Response()],
        ) as get:
            result = http_client.get_json(
                ["https://example.com/version/json/", "http://example.com/version/json/"],
                "test metadata",
            )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(get.call_args_list[0][0][0], "https://example.com/version/json/")
        self.assertEqual(get.call_args_list[1][0][0], "http://example.com/version/json/")

    def test_download_file_does_not_fallback_after_cancel(self):
        class Cancelled(Exception):
            pass

        def progress_callback(_downloaded, _total):
            raise Cancelled()

        class Response:
            headers = {"Content-Length": "4"}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size):
                return b"data"

        with patch.object(http_client, "ssl_context", return_value=object()), \
                patch.object(http_client.urllib.request, "urlopen", return_value=Response()) as urlopen:
            with self.assertRaises(Cancelled):
                http_client.download_file(
                    ["https://example.com/file.zip", "http://example.com/file.zip"],
                    os.devnull,
                    "test download",
                    progress_callback,
                    cancel_exceptions=(Cancelled,),
                )

        urlopen.assert_called_once()

    def test_configure_ssl_environment_sets_certifi_paths(self):
        certifi_stub = types.SimpleNamespace(where=lambda: "/tmp/cacert.pem")
        with patch.dict(sys.modules, {"certifi": certifi_stub}), \
                patch("classes.http_client.os.path.exists", return_value=True), \
                patch.dict(os.environ, {}, clear=True):
            self.assertEqual(http_client.configure_ssl_environment(), "/tmp/cacert.pem")
            self.assertEqual(os.environ["SSL_CERT_FILE"], "/tmp/cacert.pem")
            self.assertEqual(os.environ["REQUESTS_CA_BUNDLE"], "/tmp/cacert.pem")


if __name__ == "__main__":
    unittest.main()
