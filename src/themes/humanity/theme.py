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


class HumanityLightTheme(BaseTheme):
    def __init__(self, app):
        super().__init__(app)
        self.style_sheet = """
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
              margin-top: 10px;
              color: #000000;
              background: linear-gradient(to bottom, #dedddd, #d2d2d3);
            }
            .track {
              margin-top: 10px;
              background: #e5e7ea;
            }
            .clip {
              background: #fedc66;
              border-top: 1px solid #cd8d00;
              border-bottom: 1px solid #cd8d00;
            }
            .clip_label {
              color: #383730;
            }
            .clip_effects {
              background: rgba(54, 25, 25, 0.6);
            }
        """)
