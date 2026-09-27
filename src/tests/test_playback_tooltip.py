"""Playback actions and their toolbar buttons describe the next operation."""
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qt_api import QAction, QApplication, QIcon, QToolBar
from themes.base import BaseTheme
from themes.cosmic.theme import CosmicTheme


class PlaybackTooltipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_label_and_tooltip_follow_playback_in_both_themes(self):
        for theme_type in (BaseTheme, CosmicTheme):
            with self.subTest(theme=theme_type.__name__):
                toolbar = QToolBar()
                action = QAction("Play", toolbar)
                action.setToolTip("Play")
                toolbar.addAction(action)
                button = toolbar.widgetForAction(action)
                theme = theme_type.__new__(theme_type)
                theme.app = SimpleNamespace(
                    _tr={"Play": "Reproducir", "Pause": "Pausa"}.__getitem__,
                    window=SimpleNamespace(actionPlay=action, videoToolbar=toolbar),
                )
                with patch("themes.base.ui_util.setup_icon"), patch.object(
                    theme, "create_svg_icon", return_value=QIcon()
                ):
                    for playing, expected in ((True, "Pausa"), (False, "Reproducir"), (True, "Pausa")):
                        theme.togglePlayIcon(playing)
                        self.assertEqual(action.text(), expected)
                        self.assertEqual(action.toolTip(), expected)
                        self.assertEqual(button.toolTip(), expected)
                    # Action state also updates when no toolbar widget is mounted.
                    toolbar.removeAction(action)
                    theme.togglePlayIcon(False)
                    self.assertEqual(action.toolTip(), "Reproducir")


if __name__ == "__main__":
    unittest.main()
