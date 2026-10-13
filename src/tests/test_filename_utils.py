"""
 @file
 @brief This file contains unit tests for export file name validation
 @author Jonathan Thomas <jonathan@openshot.org>

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

import unittest

from classes.filename_utils import invalid_characters, is_valid_file_name


class FileNameValidationTest(unittest.TestCase):
    """File names the operating system refuses must be reported, and names it
    accepts must be left alone (issue #6081)."""

    def test_windows_rejects_colon_in_reported_file_name(self):
        # The exact name from #6081: Windows cannot write it, and OpenShot used
        # to export under a different name without saying so.
        self.assertEqual(invalid_characters("5-1 : Example file 1.mp4", platform="win32"), [":"])
        self.assertFalse(is_valid_file_name("5-1 : Example file 1.mp4", platform="win32"))

    def test_windows_rejects_every_forbidden_character(self):
        name = "a<b>c:d\"e/f\\g|h?i*j.mp4"
        self.assertEqual(
            invalid_characters(name, platform="win32"),
            ['"', "*", "/", ":", "<", ">", "?", "\\", "|"],
        )

    def test_windows_rejects_trailing_dot_or_space(self):
        self.assertTrue(invalid_characters("my movie.", platform="win32"))
        self.assertTrue(invalid_characters("my movie ", platform="win32"))
        self.assertFalse(is_valid_file_name("my movie.", platform="win32"))

    def test_windows_accepts_semicolon_and_colon_free_names(self):
        # A semicolon is legal on Windows - only the colon in #6081 was the problem.
        self.assertTrue(is_valid_file_name("5-1 ; Example file 1.mp4", platform="win32"))
        self.assertTrue(is_valid_file_name("My Movie (final)_v2.mp4", platform="win32"))

    def test_posix_leaves_windows_only_characters_alone(self):
        # ":", "?" and "*" are ordinary file name characters on Linux/macOS, so a
        # Linux export must not be blocked by a Windows rule.
        for name in ("5-1 : Example file 1.mp4", "what?.mp4", "100*.mp4", "my movie. "):
            self.assertTrue(is_valid_file_name(name, platform="linux"), name)
            self.assertEqual(invalid_characters(name, platform="linux"), [])

    def test_posix_rejects_path_separator(self):
        # "/" starts a new path component on POSIX (and is illegal for Windows too).
        self.assertEqual(invalid_characters("clip/export.mp4", platform="linux"), ["/"])
        self.assertFalse(is_valid_file_name("clip/export.mp4", platform="linux"))
        self.assertTrue(is_valid_file_name("clip_export.mp4", platform="linux"))

    def test_empty_names_are_invalid_everywhere(self):
        for platform in ("win32", "linux", "darwin"):
            self.assertFalse(is_valid_file_name("", platform=platform))
            self.assertFalse(is_valid_file_name("   ", platform=platform))
            self.assertFalse(is_valid_file_name(None, platform=platform))

    def test_null_character_is_rejected(self):
        for platform in ("win32", "linux"):
            self.assertFalse(is_valid_file_name("clip\x00.mp4", platform=platform))

    def test_defaults_to_the_current_platform(self):
        # Smoke check for the no-platform call used by the export screen.
        self.assertTrue(is_valid_file_name("My Movie.mp4"))


if __name__ == "__main__":
    unittest.main()
