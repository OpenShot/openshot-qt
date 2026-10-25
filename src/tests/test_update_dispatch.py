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
