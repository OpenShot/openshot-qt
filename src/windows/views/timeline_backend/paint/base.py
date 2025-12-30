"""
 @file
 @brief Base painter helpers for the QWidget timeline backend.
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2025 OpenShot Studios, LLC
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

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QImage, QPainter, QPixmap
from PyQt5.QtSvg import QSvgRenderer
import math
import os


class BasePainter:
    def __init__(self, widget):
        self.w = widget
        self.update_theme()

    def update_theme(self):
        pass

    def scaled_pixmap(self, pixmap, width, height):
        """Return *pixmap* scaled to the requested logical size."""
        if pixmap is None or pixmap.isNull():
            return pixmap
        try:
            w = int(round(width)) if width else pixmap.width()
            h = int(round(height)) if height else pixmap.height()
        except TypeError:
            w = pixmap.width()
            h = pixmap.height()
        w = max(1, w)
        h = max(1, h)

        ratio = 1.0
        try:
            ratio = float(self.w.devicePixelRatioF())
        except AttributeError:
            try:
                ratio = float(self.w.devicePixelRatio())
            except AttributeError:
                ratio = 1.0
        if not math.isfinite(ratio) or ratio <= 0.0:
            ratio = 1.0

        target_w = max(1, int(round(w * ratio)))
        target_h = max(1, int(round(h * ratio)))

        svg_renderer = None
        svg_data = getattr(pixmap, "svg_qbytearray", None)
        if svg_data:
            renderer = QSvgRenderer(svg_data)
            if renderer.isValid():
                svg_renderer = renderer
        else:
            svg_path = getattr(pixmap, "svg_path", None)
            if svg_path:
                if svg_path.startswith(":") or os.path.exists(svg_path):
                    renderer = QSvgRenderer(svg_path)
                    if renderer.isValid():
                        svg_renderer = renderer

        if svg_renderer:
            cache = getattr(pixmap, "_scaled_cache", None)
            cache_key = (target_w, target_h, ratio)
            if isinstance(cache, dict):
                cached = cache.get(cache_key)
                if cached and not cached.isNull():
                    return cached

            image = QImage(target_w, target_h, QImage.Format_ARGB32_Premultiplied)
            image.fill(0)
            painter = QPainter(image)
            svg_renderer.render(painter, QRectF(0, 0, target_w, target_h))
            painter.end()
            scaled = QPixmap.fromImage(image)
            scaled.setDevicePixelRatio(ratio)
            if hasattr(pixmap, "svg_path"):
                scaled.svg_path = pixmap.svg_path
            if hasattr(pixmap, "svg_bytes"):
                scaled.svg_bytes = pixmap.svg_bytes
            if svg_data:
                scaled.svg_qbytearray = svg_data
            if cache is None:
                cache = {}
                try:
                    pixmap._scaled_cache = cache
                except Exception:
                    cache = None
            if cache is not None:
                cache[cache_key] = scaled
            return scaled

        scaled = pixmap.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if ratio != 1.0:
            scaled.setDevicePixelRatio(ratio)
        if hasattr(pixmap, "svg_path") and not hasattr(scaled, "svg_path"):
            scaled.svg_path = pixmap.svg_path
        if hasattr(pixmap, "svg_bytes") and not hasattr(scaled, "svg_bytes"):
            scaled.svg_bytes = pixmap.svg_bytes
        if svg_data and not hasattr(scaled, "svg_qbytearray"):
            scaled.svg_qbytearray = svg_data
        return scaled

    def logical_size(self, pixmap):
        """Return ``(width, height)`` of *pixmap* in logical units."""
        if pixmap is None or pixmap.isNull():
            return 0.0, 0.0

        ratio = 1.0
        try:
            ratio = float(pixmap.devicePixelRatioF())
        except AttributeError:
            try:
                ratio = float(pixmap.devicePixelRatio())
            except AttributeError:
                ratio = 1.0
        if not math.isfinite(ratio) or ratio <= 0.0:
            ratio = 1.0

        return float(pixmap.width()) / ratio, float(pixmap.height()) / ratio
