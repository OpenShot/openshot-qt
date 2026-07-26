"""
 @file
 @brief Unit tests for tutorial target handling
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

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

import types
import sys
import unittest
from unittest.mock import MagicMock, patch

metrics = types.ModuleType("classes.metrics")
metrics.track_metric_screen = MagicMock()
with patch.dict(sys.modules, {"classes.metrics": metrics}):
    from windows.views import tutorial as tutorial_module

TutorialManager = tutorial_module.TutorialManager


class TutorialManagerTests(unittest.TestCase):
    def make_manager(self, tutorial_objects, targets):
        manager = types.SimpleNamespace(
            current_dialog=None,
            tutorial_objects=tutorial_objects,
            tutorial_enabled=True,
            tutorial_ids=[],
            position_widget=None,
            offset=None,
            win=MagicMock(),
            get_object=lambda object_id: targets.get(object_id),
            re_show_dialog=MagicMock(),
            re_position_dialog=MagicMock(),
            next_tip=MagicMock(),
            hide_tips=MagicMock(),
        )
        return manager

    def test_get_play_object_tolerates_missing_pause_action(self):
        action_play = MagicMock()
        action_play.associatedWidgets.return_value = []
        manager = types.SimpleNamespace(
            win=types.SimpleNamespace(actionPlay=action_play),
        )
        manager._get_associated_widgets = (
            lambda action: TutorialManager._get_associated_widgets(manager, action)
        )

        tutorial_object = TutorialManager.get_object(manager, "actionPlay")

        self.assertIsNone(tutorial_object)
        action_play.associatedWidgets.assert_called_once_with()

    def test_process_ignores_unavailable_target(self):
        manager = self.make_manager(
            [{"id": "3", "object_id": "actionPlay"}],
            {},
        )

        TutorialManager.process(manager)

        self.assertIsNone(manager.current_dialog)
        manager.re_show_dialog.assert_not_called()

    @patch.object(tutorial_module.QTimer, "singleShot")
    @patch.object(tutorial_module, "TutorialDialog")
    def test_process_skips_unavailable_target_and_shows_next(
            self, mock_dialog_class, mock_single_shot):
        visible_target = MagicMock()
        visible_target.visibleRegion.return_value.isEmpty.return_value = False
        tutorials = [
            {"id": "3", "object_id": "actionPlay"},
            {
                "id": "4",
                "object_id": "propertyTableView",
                "x": 0,
                "y": 0,
                "text": "Properties",
                "arrow": True,
            },
        ]
        manager = self.make_manager(
            tutorials,
            {"propertyTableView": visible_target},
        )
        dialog = mock_dialog_class.return_value

        TutorialManager.process(manager)

        self.assertIs(manager.position_widget, visible_target)
        self.assertIs(manager.current_dialog, dialog)
        manager.re_show_dialog.assert_called_once()
        mock_single_shot.assert_called_once_with(0, manager.re_position_dialog)


if __name__ == "__main__":
    unittest.main()
