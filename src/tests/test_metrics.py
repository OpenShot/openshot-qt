"""
 @file
 @brief Unit tests for anonymous metrics delivery
 @author OpenShot Studios, LLC

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
 """

import os
import sys
import types
import unittest
from unittest.mock import Mock, patch

from qt_api import QApplication


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from tests.qt_test_app import ensure_app_state, get_or_create_app


class DummySettings:
    def __init__(self, send_metrics=True):
        self.values = {
            "send_metrics": send_metrics,
            "unique_install_id": "test-install-id",
        }

    def get(self, key):
        return self.values.get(key, False)


class DummyApp(QApplication):
    def __init__(self):
        super().__init__([])
        self.settings = DummySettings()

    def get_settings(self):
        return self.settings


app, _owns_app = get_or_create_app(DummyApp)
ensure_app_state(app, DummySettings, extra_attrs={"window": types.SimpleNamespace()})

from classes import metrics


class MetricsTests(unittest.TestCase):
    def setUp(self):
        metrics.s = DummySettings(send_metrics=True)
        metrics.metric_queue.clear()
        metrics.metric_worker_active = False

    def tearDown(self):
        metrics.metric_queue.clear()
        metrics.metric_worker_active = False

    def test_send_metric_starts_background_worker_without_posting_inline(self):
        thread_instance = Mock()
        with patch.object(metrics.threading, "Thread", return_value=thread_instance) as thread_cls, \
                patch.object(metrics.http_client, "post_json") as post:
            metrics.send_metric({"name": "screen_view", "params": {}})

        post.assert_not_called()
        thread_cls.assert_called_once()
        thread_instance.start.assert_called_once()
        self.assertTrue(metrics.metric_worker_active)
        self.assertEqual(len(metrics.metric_queue), 1)

    def test_metric_worker_uses_short_timeout_and_clears_queue(self):
        metrics.metric_queue.append({"name": "screen_view", "params": {}})
        metrics.metric_worker_active = True
        response = types.SimpleNamespace(status_code=204)

        with patch.object(metrics.http_client, "post_json", return_value=response) as post, \
                patch.object(metrics.time, "sleep"):
            metrics._send_metric_worker()

        post.assert_called_once()
        self.assertEqual(
            post.call_args[1]["timeout"],
            (metrics.METRIC_CONNECT_TIMEOUT, metrics.METRIC_READ_TIMEOUT),
        )
        self.assertFalse(metrics.metric_queue)
        self.assertFalse(metrics.metric_worker_active)

    def test_metric_worker_requeues_failed_payload(self):
        event = {"name": "screen_view", "params": {}}
        metrics.metric_queue.append(event)
        metrics.metric_worker_active = True

        with patch.object(metrics.http_client, "post_json", side_effect=RuntimeError("blocked")), \
                patch.object(metrics.log, "warning"):
            metrics._send_metric_worker()

        self.assertEqual(metrics.metric_queue, [event])
        self.assertFalse(metrics.metric_worker_active)


if __name__ == "__main__":
    unittest.main()
