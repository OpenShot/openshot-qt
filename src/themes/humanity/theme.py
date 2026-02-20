"""
 @file
 @brief This file contains a theme's colors and UI dimensions
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
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

from ..base import BaseTheme


class HumanityDarkTheme(BaseTheme):
    def __init__(self, app):
        super().__init__(app)
        self.style_sheet = """
QToolTip {
    color: #ffffff;
    background-color: #2a82da;
    border: 0px solid white;
}

QComboBox::item {
    height: 24px;
}

QComboBox {
    combobox-popup: 0;
}

.property_value {
    foreground-color: #217dd4;
    background-color: #565656;
}

.zoom_slider_playhead {
    background-color: #ff0024;
}

QWidget#videoPreview {
    background-color: #191919;
}

/* Flowcut Assistant chat: match Humanity dark #191919, #ffffff, #2a82da */
QDockWidget#AIChatWindow QWidget#AIChatWindowContents {
    background-color: #191919;
}
QDockWidget#AIChatWindow QFrame#chatPreamble {
    background-color: #252525;
    border: 1px solid #404040;
    border-radius: 0;
}
QDockWidget#AIChatWindow QLabel#chatPreambleLabel {
    color: #ffffff;
    font-size: 12px;
}
QDockWidget#AIChatWindow QTextEdit#chatBox {
    background-color: #191919;
    color: #ffffff;
    border: 1px solid #404040;
    border-radius: 0;
    padding: 8px;
}
QDockWidget#AIChatWindow QTextEdit#msgInput {
    background-color: #252525;
    color: #ffffff;
    border: 1px solid #404040;
    border-radius: 0;
    padding: 6px;
}
QDockWidget#AIChatWindow QPushButton#sendBtn,
QDockWidget#AIChatWindow QPushButton#clearBtn {
    background-color: #353535;
    color: #ffffff;
    border: 1px solid #404040;
    border-radius: 0;
}
QDockWidget#AIChatWindow QPushButton#sendBtn:hover,
QDockWidget#AIChatWindow QPushButton#clearBtn:hover {
    background-color: #2a82da;
    color: #ffffff;
}
QDockWidget#AIChatWindow QComboBox#modelCombo {
    background-color: #252525;
    color: #ffffff;
    border: 1px solid #404040;
    border-radius: 0;
}
        """

    def apply_theme(self):
        super().apply_theme()

        from classes import ui_util
        from classes.logger import log
        from PyQt5.QtWidgets import QStyleFactory

        log.info("Setting Fusion dark palette")
        self.app.setStyle(QStyleFactory.create("Fusion"))
        dark_palette = ui_util.make_dark_palette(self.app.palette())
        self.app.setPalette(dark_palette)
        self.app.setStyleSheet(self.style_sheet)

        # Apply timeline theme
        self.app.window.timeline.apply_theme("")

        # Emit signal
        self.app.window.ThemeChangedSignal.emit(self)

class Retro(BaseTheme):
    def __init__(self, app):
        super().__init__(app)
        self.style_sheet = """
QComboBox::item {
    height: 24px;
}

QMainWindow::separator:hover {
    background: #dedede;
}

.property_value {
    foreground-color: #217dd4;
    background-color: #7f7f7f;
}

.zoom_slider_playhead {
    background-color: #ff0024;
}

QWidget#videoPreview {
    background-color: #dedede;
}

QComboBox {
    combobox-popup: 0;
}

/* Flowcut Assistant chat: match Retro (light) #dedede, #333 */
QDockWidget#AIChatWindow QWidget#AIChatWindowContents {
    background-color: #f0f0f0;
}
QDockWidget#AIChatWindow QFrame#chatPreamble {
    background-color: #e8e8e8;
    border: 1px solid #ccc;
    border-radius: 0;
}
QDockWidget#AIChatWindow QLabel#chatPreambleLabel {
    color: #333333;
    font-size: 12px;
}
QDockWidget#AIChatWindow QTextEdit#chatBox {
    background-color: #f0f0f0;
    color: #333333;
    border: 1px solid #ccc;
    border-radius: 0;
    padding: 8px;
}
QDockWidget#AIChatWindow QTextEdit#msgInput {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ccc;
    border-radius: 0;
    padding: 6px;
}
QDockWidget#AIChatWindow QPushButton#sendBtn,
QDockWidget#AIChatWindow QPushButton#clearBtn {
    background-color: #e8e8e8;
    color: #333333;
    border: 1px solid #ccc;
    border-radius: 0;
}
QDockWidget#AIChatWindow QPushButton#sendBtn:hover,
QDockWidget#AIChatWindow QPushButton#clearBtn:hover {
    background-color: #217dd4;
    color: #ffffff;
}
QDockWidget#AIChatWindow QComboBox#modelCombo {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ccc;
    border-radius: 0;
}
        """

    def apply_theme(self):
        super().apply_theme()

        # Apply timeline theme
        self.app.window.timeline.apply_theme("""
            body {
              background: #f0f0f0;
            }
            #ruler_time {
              color: #c9c9c9;
            }
           .ruler_time {
              color: #c9c9c9;
            }
            #ruler_label {
              height: 43px;
              background: linear-gradient(to bottom, #3c3c3c, #0a070a);
              margin-bottom: 0px;
            }
            #scrolling_ruler {
              background: linear-gradient(to bottom, #3c3c3c, #0a070a);
              margin-bottom: 0px;
            }
            .track_name {
              margin-top: 8px;
              color: #000000;
              background: linear-gradient(to bottom, #dedddd, #d2d2d3);
              box-shadow: none;
            }
            .track {
              margin-top: 8px;
              background: #e5e7ea;
              box-shadow: none;
            }
            .track-resize-handle {
              background-color: #BEBFC1;
            }
            .track-resize-handle:hover {
              background-color: #F7F8FA;
            }
            .transition_top {
              background: none;
              border-radius: 0px;
            }
            .transition {
              border: 1px solid #0192c1;
              border-radius: 0px;
              box-shadow: none;
            }
            .clip {
              border-radius: 0px;
              background: #fedc66;
              border: 1px solid #cd8d00;
              box-shadow: none;
            }
            .ui-selected {
                filter: brightness(1.1);
            }
            .clip_label {
              color: #383730;
            }
            .clip_effects {
              background: rgba(54, 25, 25, 0.6);
            }
            .point_bezier {
              background-image: url(../themes/humanity/images/keyframe-bezier.svg);
            }
            .point_linear {
              background-image: url(../themes/humanity/images/keyframe-linear.svg);
            }
            .point_constant {
              background-image: url(../themes/humanity/images/keyframe-constant.svg);
            }
            .track-keyframe-panel-disabled {
              background-image: url(../themes/humanity/images/track-keyframe-panel-show-disabled.svg);
            }
            .track-keyframe-panel-enabled {
              background-image: url(../themes/humanity/images/track-keyframe-panel-show-enabled.svg);
            }
            .track-add-above-disabled {
              background-image: url(../themes/humanity/images/track-add-above-disabled.svg);
            }
            .track-add-above-enabled {
              background-image: url(../themes/humanity/images/track-add-above-enabled.svg);
            }
            .track-add-below-disabled {
              background-image: url(../themes/humanity/images/track-add-below-disabled.svg);
            }
            .track-add-below-enabled {
              background-image: url(../themes/humanity/images/track-add-below-enabled.svg);
            }
            .track-delete-disabled {
              background-image: url(../themes/humanity/images/track-delete-disabled.svg);
            }
            .track-delete-enabled {
              background-image: url(../themes/humanity/images/track-delete-enabled.svg);
            }
            .track-locked-disabled {
              background-image: url(../themes/humanity/images/track-locked-disabled.svg);
            }
            .track-locked-enabled {
              background-image: url(../themes/humanity/images/track-locked-enabled.svg);
            }
            .track-unlocked-disabled {
              background-image: url(../themes/humanity/images/track-unlocked-disabled.svg);
            }
            .track-unlocked-enabled {
              background-image: url(../themes/humanity/images/track-unlocked-enabled.svg);
            }
            .keyframe-panel-add {
              background-image: url(../themes/humanity/images/keyframe-panel-add.svg);
            }
        """)

        # Emit signal
        self.app.window.ThemeChangedSignal.emit(self)
