"""
 @file
 @brief This file contains the ThemeManager singleton, used to easily switch UI themes
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

from enum import Enum


class ThemeName(Enum):
    """Friendly UI theme names used in settings"""
    NO_THEME = "No Theme"
    HUMANITY_LIGHT = "Humanity"
    HUMANITY_DARK = "Humanity: Dark"
    COSMIC = "Cosmic Dusk"

    @staticmethod
    def get_sorted_theme_names():
        """Return a sorted list of theme names"""
        return sorted([theme.value for theme in ThemeName])

    @staticmethod
    def find_by_name(name):
        """Return a theme ENUM which matches a name"""
        for theme in ThemeName:
            if theme.value == name:
                return theme
        return ThemeName.NO_THEME


class ThemeManager:
    """Singleton Theme Manager class, used to easily switch between UI themes"""
    _instance = None

    def __new__(cls, app=None):
        """Override new method, so the same instance is always returned (i.e. singleton)"""
        if cls._instance is None:
            cls._instance = super(ThemeManager, cls).__new__(cls)
            cls._instance.app = app
            cls._instance.original_style = app.style().objectName() if app else None
            cls._instance.original_palette = app.palette() if app else None
            cls._instance.current_theme = None
        return cls._instance

    def apply_theme(self, theme_name):
        """Apply a new UI theme. Expects a ThemeName ENUM as the arg."""
        if theme_name == ThemeName.HUMANITY_DARK:
            from themes.humanity.theme import HumanityDarkTheme
            self.current_theme = HumanityDarkTheme(self.app)
        elif theme_name == ThemeName.HUMANITY_LIGHT:
            from themes.humanity.theme import HumanityLightTheme
            self.current_theme = HumanityLightTheme(self.app)
        elif theme_name == ThemeName.COSMIC:
            from themes.cosmic.theme import CosmicTheme
            self.current_theme = CosmicTheme(self.app)
        else:
            from themes.base import BaseTheme
            self.current_theme = BaseTheme(self.app)

        self.current_theme.apply_theme()

    def get_current_theme(self):
        """Return the current theme instance, or None if no theme is applied."""
        return self.current_theme
