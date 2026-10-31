"""Regression tests for update listener dispatch."""

import unittest
from unittest.mock import Mock

from qt_api import QApplication, QEvent, QObject
from classes.updates import UpdateAction, UpdateManager


class UpdateDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_deleted_qt_listener_does_not_block_live_listeners(self):
        manager = UpdateManager()
        deleted = QObject()
        deleted.changed = Mock(side_effect=lambda action: deleted.objectName())
        live = Mock()
        manager.add_listener(deleted)
        manager.add_listener(live)
        deleted.deleteLater()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)

        action = UpdateAction("load", [], {})
        manager.dispatch_action(action)

        self.assertNotIn(deleted, manager.updateListeners)
        deleted.changed.assert_not_called()
        live.changed.assert_called_once_with(action)

    def test_failed_insert_retains_exception_and_action_path(self):
        manager = UpdateManager()
        failed = Mock()
        failed.changed.side_effect = MemoryError()
        following = Mock()
        manager.add_listener(failed)
        manager.add_listener(following)
        action = UpdateAction("insert", ["clips"], {"id": "new"})

        with self.assertLogs("OpenShot", level="ERROR") as logs:
            manager.dispatch_action(action)

        record = logs.records[0]
        self.assertIs(record.exc_info[0], MemoryError)
        self.assertIn("clips", record.getMessage())
        self.assertIn("insert", record.getMessage())
        # Do not notify later views of an insertion the project rejected.
        following.changed.assert_not_called()
