"""
 @file
 @brief Deterministic CLI test preferences without changing saved user settings.

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
from unittest.mock import patch


def isolate_preferences(test):
    settings = test.app.get_settings()
    original = settings.get
    defaults = {"default-profile": "HD 720p 30 fps", "default-samplerate": 48000,
                "default-channellayout": "LAYOUT_STEREO", "history-limit": 100}
    override = patch.object(settings, "get", side_effect=lambda key: defaults[key] if key in defaults else original(key))
    override.start()
    test.addCleanup(override.stop)
