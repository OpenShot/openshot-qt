"""
 @file
 @brief Shared Qt-free easing presets for GUI menus and CLI animation.

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

def easing_presets(translate=lambda text: text):
    """Return stable IDs, CSS control points, and translated display labels."""
    _ = translate
    return [
        ('ease', (0.250, 0.100, 0.250, 1.000), _('Ease (Default)')),
        ('ease-in', (0.420, 0.000, 1.000, 1.000), _('Ease In')),
        ('ease-out', (0.000, 0.000, 0.580, 1.000), _('Ease Out')),
        ('ease-in-out', (0.420, 0.000, 0.580, 1.000), _('Ease In/Out')),
        ('ease-in-quad', (0.550, 0.085, 0.680, 0.530), _('Ease In (Quad)')),
        ('ease-in-cubic', (0.550, 0.055, 0.675, 0.190), _('Ease In (Cubic)')),
        ('ease-in-quart', (0.895, 0.030, 0.685, 0.220), _('Ease In (Quart)')),
        ('ease-in-quint', (0.755, 0.050, 0.855, 0.060), _('Ease In (Quint)')),
        ('ease-in-sine', (0.470, 0.000, 0.745, 0.715), _('Ease In (Sine)')),
        ('ease-in-expo', (0.950, 0.050, 0.795, 0.035), _('Ease In (Expo)')),
        ('ease-in-circ', (0.600, 0.040, 0.980, 0.335), _('Ease In (Circ)')),
        ('ease-in-back', (0.600, -0.280, 0.735, 0.045), _('Ease In (Back)')),
        ('ease-out-quad', (0.250, 0.460, 0.450, 0.940), _('Ease Out (Quad)')),
        ('ease-out-cubic', (0.215, 0.610, 0.355, 1.000), _('Ease Out (Cubic)')),
        ('ease-out-quart', (0.165, 0.840, 0.440, 1.000), _('Ease Out (Quart)')),
        ('ease-out-quint', (0.230, 1.000, 0.320, 1.000), _('Ease Out (Quint)')),
        ('ease-out-sine', (0.390, 0.575, 0.565, 1.000), _('Ease Out (Sine)')),
        ('ease-out-expo', (0.190, 1.000, 0.220, 1.000), _('Ease Out (Expo)')),
        ('ease-out-circ', (0.075, 0.820, 0.165, 1.000), _('Ease Out (Circ)')),
        ('ease-out-back', (0.175, 0.885, 0.320, 1.275), _('Ease Out (Back)')),
        ('ease-in-out-quad', (0.455, 0.030, 0.515, 0.955), _('Ease In/Out (Quad)')),
        ('ease-in-out-cubic', (0.645, 0.045, 0.355, 1.000), _('Ease In/Out (Cubic)')),
        ('ease-in-out-quart', (0.770, 0.000, 0.175, 1.000), _('Ease In/Out (Quart)')),
        ('ease-in-out-quint', (0.860, 0.000, 0.070, 1.000), _('Ease In/Out (Quint)')),
        ('ease-in-out-sine', (0.445, 0.050, 0.550, 0.950), _('Ease In/Out (Sine)')),
        ('ease-in-out-expo', (1.000, 0.000, 0.000, 1.000), _('Ease In/Out (Expo)')),
        ('ease-in-out-circ', (0.785, 0.135, 0.150, 0.860), _('Ease In/Out (Circ)')),
        ('ease-in-out-back', (0.680, -0.550, 0.265, 1.550), _('Ease In/Out (Back)')),
    ]


def keyframe_bezier_presets(translate=lambda text: text):
    """Legacy GUI tuple shape: x1, y1, x2, y2, label."""
    return [(*control, label) for _, control, label in easing_presets(translate)]
