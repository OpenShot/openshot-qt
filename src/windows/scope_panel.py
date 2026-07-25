"""
 @file
 @brief Scope dock panels: waveform, histogram, vectorscope, and audio meters.
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

import math
import os

from qt_api import (
    Qt, pyqtSignal, pyqtSlot,
    QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy,
    QImage, QPainter, QColor, QPen, QBrush, QIcon,
    QComboBox, QToolButton, QRect, QPainterPath, QPointF,
)
from classes import info
from classes.logger import log
from windows.color_grade_editor import draw_broadcast_hue_ring

# ─── Persistent settings keys ────────────────────────────────────────────────
_S_WAVE_MODE  = "scope-waveform-mode"     # luma|red|green|blue|rgb_overlay|rgb_parade
_S_WAVE_COLOR = "scope-waveform-color"    # green|white|orange
_S_HIST_CH    = "scope-histogram-channel" # rgba|luma|red|green|blue
_S_HIST_SCALE = "scope-histogram-scale"   # log|linear
_S_VEC_DISPLAY = "scope-vectorscope-display"  # colorized|density|intensity
_S_VEC_ZOOM    = "scope-vectorscope-zoom"     # 100|200|400

_VECTORSCOPE_HUE_LABELS = (
    ("R", 108.65, 360.0),
    ("Mg", 51.65, 300.0),
    ("B", 350.76, 240.0),
    ("Cy", 288.65, 180.0),
    ("G", 231.65, 120.0),
    ("Yi", 170.76, 60.0 + 360.0),
)
_vectorscope_geometry_cache = {}
_vectorscope_intensity_lut = None
_vectorscope_label_lut_cache = {}   # size → (6, size*size) float32 numpy array


def N_(message):
    """Mark a deferred UI string for translation without translating at import time."""
    return message


def _settings():
    try:
        from classes.app import get_app
        return get_app().get_settings()
    except Exception:
        return None


def _get(key, default):
    s = _settings()
    if s is None:
        return default
    v = s.get(key)
    return v if v is not None else default


def _set(key, value):
    s = _settings()
    if s is not None:
        try:
            s.set(key, value)
        except Exception as ex:
            log.debug("Unable to save scope setting %s: %s", key, ex)


def _scope_region_icon(size=16):
    icon_path = os.path.join(info.PATH, "themes", "cosmic", "images", "tool-scope-region.svg")
    return QIcon(icon_path)


def _make_scope_region_button(parent):
    from classes.app import get_app
    _ = get_app()._tr
    button = QToolButton(parent)
    button.setCheckable(True)
    button.setAutoRaise(True)
    button.setIcon(_scope_region_icon())
    button.setToolTip(_("Analyze selected preview region"))
    button.setFocusPolicy(Qt.NoFocus)
    return button


def normalize_vectorscope_display(value):
    if value == "monochrome":
        return "density"
    if value == "heatmap":
        return "intensity"
    return value or "colorized"


def _vectorscope_wrap_angle(angle):
    return (angle + 360.0) % 360.0


def _vectorscope_display_hue_for_scope_angle(angle_deg):
    anchors = sorted((_vectorscope_wrap_angle(scope_angle), display_hue)
                     for _, scope_angle, display_hue in _VECTORSCOPE_HUE_LABELS)
    wrapped = _vectorscope_wrap_angle(angle_deg)
    normalized = []
    previous_hue = None
    for scope_angle, display_hue in anchors:
        hue = display_hue
        if previous_hue is not None:
            while hue < previous_hue:
                hue += 360.0
        normalized.append((scope_angle, hue))
        previous_hue = hue
    if wrapped < normalized[0][0]:
        wrapped += 360.0
    extended = normalized + [(normalized[0][0] + 360.0, normalized[0][1] + 360.0)]

    for index in range(len(normalized)):
        a0, h0 = extended[index]
        a1, h1 = extended[index + 1]
        if a0 <= wrapped <= a1:
            span = max(1e-6, a1 - a0)
            t = (wrapped - a0) / span
            return (h0 + ((h1 - h0) * t)) % 360.0

    return normalized[0][1] % 360.0


def _vectorscope_density_to_byte(count, max_val):
    if count <= 0 or max_val <= 0:
        return 0
    return min(255, int(math.sqrt(count / max_val) * 255))


def _build_vectorscope_label_lut(size):
    """Build a (6, size*size) float32 weight matrix — computed once per size."""
    import numpy as np
    half_cone = 45.0
    center = (size - 1) * 0.5
    ix = np.arange(size, dtype=np.float32)
    iy = np.arange(size, dtype=np.float32)
    u_norm = (ix[np.newaxis, :] - center) / center   # (1,size) → broadcast (size,size)
    v_norm = (center - iy[:, np.newaxis]) / center   # (size,1) → broadcast
    radius = np.minimum(np.sqrt(u_norm ** 2 + v_norm ** 2), 1.0)
    angle_deg = np.degrees(np.arctan2(v_norm, u_norm))
    lut = np.empty((6, size * size), dtype=np.float32)
    for i, (_, scope_angle, _) in enumerate(_VECTORSCOPE_HUE_LABELS):
        diff = np.abs(((angle_deg - scope_angle + 180.0) % 360.0) - 180.0)
        weight = np.where(diff < half_cone,
                          np.cos(np.radians(diff * (90.0 / half_cone))), 0.0)
        lut[i] = (weight * radius).ravel().astype(np.float32)
    return lut


def _vectorscope_label_scores(flat_density, size):
    """Return 6 proximity scores [0..1] for each HUE_LABEL, one dot-product away."""
    try:
        import numpy as np
    except ImportError:
        return [0.0] * 6
    if not flat_density or len(flat_density) != size * size:
        return [0.0] * 6
    lut = _vectorscope_label_lut_cache.get(size)
    if lut is None:
        lut = _build_vectorscope_label_lut(size)
        _vectorscope_label_lut_cache[size] = lut
    arr = np.asarray(flat_density, dtype=np.float32)
    total = float(arr.sum())
    if total <= 0.0:
        return [0.0] * 6
    scores = lut @ arr        # (6,) weighted pixel sums
    scores /= total           # average weight per pixel → nominally 0..1
    np.sqrt(scores, out=scores)  # sqrt compresses dynamic range for better feel
    np.clip(scores, 0.0, 1.0, out=scores)
    return scores.tolist()


def _vectorscope_geometry_info(size, zoom_factor):
    key = (int(size), int(round(zoom_factor * 100)))
    cached = _vectorscope_geometry_cache.get(key)
    if cached is not None:
        return cached

    source_indices = [-1] * (size * size)
    colorized_base = bytearray(size * size * 3)
    center = (size - 1) * 0.5
    radius = center
    inv_zoom = 1.0 / max(1.0, zoom_factor)

    for y in range(size):
        row_offset = y * size
        source_y = int(round(center + ((y - center) * inv_zoom)))
        for x in range(size):
            source_x = int(round(center + ((x - center) * inv_zoom)))
            if source_x < 0 or source_x >= size or source_y < 0 or source_y >= size:
                continue

            pixel_index = row_offset + x
            source_indices[pixel_index] = (source_y * size) + source_x

            u = (x - center) / max(1.0, radius)
            v = (center - y) / max(1.0, radius)
            hue = _vectorscope_display_hue_for_scope_angle(math.degrees(math.atan2(v, u)))
            saturation = min(1.0, math.sqrt((u * u) + (v * v)))
            color = QColor.fromHsv(int(hue) % 360, int(255 * saturation), 255)
            color_index = pixel_index * 3
            colorized_base[color_index] = color.red()
            colorized_base[color_index + 1] = color.green()
            colorized_base[color_index + 2] = color.blue()

    cached = (source_indices, colorized_base)
    _vectorscope_geometry_cache[key] = cached
    return cached


def _vectorscope_intensity_lut_bytes():
    global _vectorscope_intensity_lut
    if _vectorscope_intensity_lut is not None:
        return _vectorscope_intensity_lut

    lut = bytearray(256 * 3)
    for t in range(256):
        hue = int(max(0, 240 - (t * 240 / 255)))
        saturation = min(255, 180 + (t * 75 // 255))
        value = min(255, 56 + (t * 199 // 255))
        color = QColor.fromHsv(hue, saturation, value)
        idx = t * 3
        lut[idx] = color.red()
        lut[idx + 1] = color.green()
        lut[idx + 2] = color.blue()
    _vectorscope_intensity_lut = lut
    return _vectorscope_intensity_lut


def build_vectorscope_image(flat, size, zoom_factor, display):
    display = normalize_vectorscope_display(display)
    if not flat or len(flat) != size * size:
        return None

    max_val = max(flat) or 1
    buf = bytearray(size * size * 3)
    source_indices, colorized_base = _vectorscope_geometry_info(size, zoom_factor)
    intensity_lut = _vectorscope_intensity_lut_bytes() if display == "intensity" else None

    for pixel_index, source_index in enumerate(source_indices):
        if source_index < 0:
            continue

        count = flat[source_index]
        if not count:
            continue

        t = _vectorscope_density_to_byte(count, max_val)
        idx = pixel_index * 3
        if display == "density":
            value = min(255, 24 + (t * 231 // 255))
            buf[idx] = value
            buf[idx + 1] = value
            buf[idx + 2] = value
        elif display == "intensity":
            lut_index = t * 3
            buf[idx] = intensity_lut[lut_index]
            buf[idx + 1] = intensity_lut[lut_index + 1]
            buf[idx + 2] = intensity_lut[lut_index + 2]
        else:
            value = min(255, 80 + (t * 175 // 255))
            buf[idx] = (colorized_base[idx] * value) // 255
            buf[idx + 1] = (colorized_base[idx + 1] * value) // 255
            buf[idx + 2] = (colorized_base[idx + 2] * value) // 255
    return QImage(bytes(buf), size, size, size * 3, QImage.Format_RGB888).copy()


# ─── Waveform painter ────────────────────────────────────────────────────────

class WaveformWidget(QWidget):
    """Luma / RGB waveform density heatmap painter."""

    _LUMA_COLORS = {
        "green":  (0,   220,  80),
        "white":  (220, 220, 220),
        "orange": (255, 160,   0),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data  = None
        self._mode  = _get(_S_WAVE_MODE,  "luma")
        self._color = _get(_S_WAVE_COLOR, "green")
        self._ire   = True
        self.setMinimumSize(120, 100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.NoFocus)

    def set_mode(self,  v): self._mode  = v; _set(_S_WAVE_MODE,  v); self.update()
    def set_color(self, v): self._color = v; _set(_S_WAVE_COLOR, v); self.update()

    def update_data(self, video_data):
        self._data = video_data
        self.update()

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _density_to_byte(count, max_val):
        """Boost low-density samples so sparse scopes stay visible."""
        if count <= 0 or max_val <= 0:
            return 0
        return min(255, int(math.sqrt(count / max_val) * 255))

    def _build_img(self, flat, columns, bins, rgb):
        """Build a columns×bins RGB888 QImage from a waveform flat array."""
        if not flat or len(flat) != columns * bins:
            return None
        max_val = max(flat) or 1
        r0, g0, b0 = rgb
        buf = bytearray(columns * bins * 3)
        for col in range(columns):
            base = col * bins
            for b in range(bins):
                count = flat[base + b]
                if not count:
                    continue
                t = self._density_to_byte(count, max_val)
                row = bins - 1 - b
                idx = (row * columns + col) * 3
                buf[idx]     = r0 * t // 255
                buf[idx + 1] = g0 * t // 255
                buf[idx + 2] = b0 * t // 255
        # Detach from the temporary Python buffer so paint reads stable pixels.
        return QImage(bytes(buf), columns, bins, columns * 3, QImage.Format_RGB888).copy()

    # ── paint ────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(0, 0, 0))

        if not self._data or not self._data.get("present"):
            painter.setPen(QColor(80, 80, 80))
            painter.drawText(self.rect(), Qt.AlignCenter, "No Video")
            return

        wf      = self._data.get("waveform", {})
        columns = wf.get("columns", 256)
        bins    = wf.get("bins",    256)
        mode    = self._mode

        if mode == "rgb_parade":
            band_w = w // 3
            for i, (key, rgb) in enumerate([
                ("red",   (220,  60,  60)),
                ("green", ( 60, 190,  60)),
                ("blue",  ( 60, 120, 220)),
            ]):
                img = self._build_img(wf.get(key, []), columns, bins, rgb)
                if img:
                    painter.drawImage(QRect(i * band_w, 0, band_w, h), img)

            # Thin dividers between bands
            painter.setPen(QPen(QColor(50, 50, 50), 1))
            painter.drawLine(band_w,     0, band_w,     h)
            painter.drawLine(band_w * 2, 0, band_w * 2, h)

        elif mode == "rgb_overlay":
            r_flat = wf.get("red",   [])
            g_flat = wf.get("green", [])
            b_flat = wf.get("blue",  [])
            if r_flat and len(r_flat) == columns * bins:
                max_val = max(max(r_flat), max(g_flat) if g_flat else 0,
                              max(b_flat) if b_flat else 0) or 1
                buf = bytearray(columns * bins * 3)
                for col in range(columns):
                    base = col * bins
                    for b in range(bins):
                        rv = r_flat[base + b]
                        gv = g_flat[base + b] if g_flat else 0
                        bv = b_flat[base + b] if b_flat else 0
                        if not (rv or gv or bv):
                            continue
                        row = bins - 1 - b
                        idx = (row * columns + col) * 3
                        buf[idx]     = min(255, self._density_to_byte(rv, max_val) * 220 // 255)
                        buf[idx + 1] = min(255, self._density_to_byte(gv, max_val) * 190 // 255)
                        buf[idx + 2] = min(255, self._density_to_byte(bv, max_val) * 220 // 255)
                img = QImage(bytes(buf), columns, bins, columns * 3,
                             QImage.Format_RGB888).copy()
                painter.drawImage(self.rect(), img)

        else:
            # Single-channel modes: luma, red, green, blue
            rgb_map = {
                "luma":  self._LUMA_COLORS.get(self._color, (0, 220, 80)),
                "red":   (220,  60,  60),
                "green": ( 60, 190,  60),
                "blue":  ( 60, 120, 220),
            }
            flat = wf.get(mode if mode != "luma" else "luma", [])
            img  = self._build_img(flat, columns, bins, rgb_map.get(mode, (200, 200, 200)))
            if img:
                painter.drawImage(self.rect(), img)

        # IRE reference lines at 10 / 50 / 90 %
        if self._ire:
            painter.setPen(QPen(QColor(60, 60, 60), 1, Qt.DashLine))
            for pct in (0.1, 0.5, 0.9):
                y = int(h * (1.0 - pct))
                painter.drawLine(0, y, w, y)


# ─── Histogram painter ───────────────────────────────────────────────────────

class HistogramWidget(QWidget):
    """RGB + luma overlay histogram with channel and scale filters."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data    = None
        self._channel = _get(_S_HIST_CH,    "rgba")
        self._scale   = _get(_S_HIST_SCALE, "log")
        self.setMinimumSize(120, 80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.NoFocus)

    def set_channel(self, v): self._channel = v; _set(_S_HIST_CH,    v); self.update()
    def set_scale(self,   v): self._scale   = v; _set(_S_HIST_SCALE, v); self.update()

    def update_data(self, video_data):
        self._data = video_data
        self.update()

    @staticmethod
    def _bin_span(index, bins, width):
        """Map one source bin to an exact on-screen span without gaps."""
        x0 = index * width // bins
        x1 = (index + 1) * width // bins
        if x1 <= x0:
            x1 = min(width, x0 + 1)
        return x0, x1

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(20, 20, 20))

        if not self._data or not self._data.get("present"):
            painter.setPen(QColor(80, 80, 80))
            painter.drawText(self.rect(), Qt.AlignCenter, "No Video")
            return

        hist  = self._data.get("histogram", {})
        luma  = hist.get("luma",  [])
        red   = hist.get("red",   [])
        green = hist.get("green", [])
        blue  = hist.get("blue",  [])

        if not luma:
            return

        ch = self._channel
        if ch == "rgba":
            to_draw = [
                (blue,  QColor(60,  60,  220, 140)),
                (green, QColor(60,  190,  60, 140)),
                (red,   QColor(220,  60,  60, 140)),
                (luma,  QColor(210, 210, 210,  70)),
            ]
        elif ch == "luma":
            to_draw = [(luma,  QColor(210, 210, 210, 200))]
        elif ch == "red":
            to_draw = [(red,   QColor(220,  60,  60, 200))]
        elif ch == "green":
            to_draw = [(green, QColor( 60, 190,  60, 200))]
        elif ch == "blue":
            to_draw = [(blue,  QColor( 60,  60, 220, 200))]
        else:
            return

        all_vals = [v for vals, _ in to_draw for v in vals]
        max_val  = max(all_vals) if all_vals else 1
        if not max_val:
            max_val = 1
        use_log  = (self._scale == "log")
        log_max  = math.log1p(max_val)
        bins     = len(luma)

        painter.setPen(Qt.NoPen)
        if ch == "rgba":
            painter.setCompositionMode(QPainter.CompositionMode_Plus)
        for vals, color in to_draw:
            painter.setBrush(QBrush(color))
            for i, v in enumerate(vals):
                if not v:
                    continue
                x, x2 = self._bin_span(i, bins, w)
                bar_h = int(math.log1p(v) / log_max * h) if use_log else v * h // max_val
                painter.drawRect(x, h - bar_h, x2 - x, bar_h)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)


# ─── Vectorscope painter ─────────────────────────────────────────────────────

class VectorscopeWidget(QWidget):
    """2D chroma density plot with a lightweight vectorscope graticule."""

    _HUE_LABELS = _VECTORSCOPE_HUE_LABELS
    _SKIN_TONE_ANGLE = 123.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = None
        self._display = normalize_vectorscope_display(_get(_S_VEC_DISPLAY, "colorized"))
        self._zoom = _get(_S_VEC_ZOOM, "100")
        self._render_token = 0
        self._cached_scope_image = None
        self._cached_scope_key = None
        self._cached_overlay_image = None
        self._cached_overlay_key = None
        self._label_scores = [0.0] * 6
        self.setMinimumSize(120, 100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.NoFocus)

    def set_display(self, value):
        self._display = normalize_vectorscope_display(value)
        self._render_token += 1
        self._cached_scope_image = None
        self._cached_scope_key = None
        _set(_S_VEC_DISPLAY, self._display)
        self.update()

    def set_zoom(self, value):
        self._zoom = value
        self._render_token += 1
        self._cached_scope_image = None
        self._cached_scope_key = None
        _set(_S_VEC_ZOOM, value)
        self.update()

    def update_data(self, video_data):
        self._data = video_data
        self._render_token += 1
        self._cached_scope_image = None
        self._cached_scope_key = None
        self.update()

    def resizeEvent(self, event):
        self._cached_scope_image = None
        self._cached_scope_key = None
        self._cached_overlay_image = None
        self._cached_overlay_key = None
        super().resizeEvent(event)

    def _build_img(self, flat, size, zoom_factor):
        return build_vectorscope_image(flat, size, zoom_factor, self._display)

    def _draw_guides(self, painter, center_x, center_y, radius):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        ring_pen = QPen(QColor(90, 98, 110, 88), 1)
        spoke_pen = QPen(QColor(90, 98, 110, 68), 1)
        skin_pen = QPen(QColor(210, 170, 120, 110), 1, Qt.DashLine)

        painter.setPen(ring_pen)
        for step in range(1, 7):
            r = radius * step / 6.0
            painter.drawEllipse(QRect(
                int(center_x - r), int(center_y - r),
                int(r * 2), int(r * 2),
            ))

        painter.setPen(spoke_pen)
        for _, angle_deg, _ in self._HUE_LABELS:
            angle = math.radians(angle_deg)
            x = center_x + (math.cos(angle) * radius)
            y = center_y - (math.sin(angle) * radius)
            painter.drawLine(int(center_x), int(center_y), int(x), int(y))

        painter.drawLine(int(center_x - radius), int(center_y), int(center_x + radius), int(center_y))
        painter.drawLine(int(center_x), int(center_y - radius), int(center_x), int(center_y + radius))

        painter.setPen(skin_pen)
        skin_angle = math.radians(self._SKIN_TONE_ANGLE)
        skin_x = center_x + (math.cos(skin_angle) * radius)
        skin_y = center_y - (math.sin(skin_angle) * radius)
        painter.drawLine(int(center_x), int(center_y), int(skin_x), int(skin_y))

        painter.restore()

    def _draw_labels(self, painter, center_x, center_y, radius, scores):
        """Draw hue labels per-frame, tinted toward their target color by proximity score."""
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        base_r, base_g, base_b, base_a = 160, 168, 176, 120
        for i, (label, angle_deg, display_hue) in enumerate(self._HUE_LABELS):
            score = scores[i] if scores else 0.0
            angle = math.radians(angle_deg)
            lx = center_x + (math.cos(angle) * radius * 0.82)
            ly = center_y - (math.sin(angle) * radius * 0.82)
            if score < 0.02:
                color = QColor(base_r, base_g, base_b, base_a)
            else:
                target = QColor.fromHsvF((display_hue % 360.0) / 360.0, 1.0, 1.0)
                r = int(base_r + (target.red()   - base_r) * score)
                g = int(base_g + (target.green() - base_g) * score)
                b = int(base_b + (target.blue()  - base_b) * score)
                a = int(base_a + (255 - base_a) * score)
                color = QColor(r, g, b, a)
            painter.setPen(QPen(color, 1))
            painter.drawText(QRect(int(lx - 18), int(ly - 10), 36, 20), Qt.AlignCenter, label)
        painter.restore()

    def _layout_info(self):
        w, h = self.width(), self.height()
        side = max(10, min(w, h) - 12)
        left = (w - side) // 2
        top = (h - side) // 2
        center_x = left + side / 2.0
        center_y = top + side / 2.0
        radius = side / 2.0
        ring_margin = max(8.0, radius * 0.075)
        plot_radius = max(8.0, radius - ring_margin)
        plot_left = center_x - plot_radius
        plot_top = center_y - plot_radius
        plot_size = plot_radius * 2.0
        plot_rect = QRect(
            int(plot_left),
            int(plot_top),
            int(plot_size),
            int(plot_size),
        )
        return {
            "widget_width": w,
            "widget_height": h,
            "center_x": center_x,
            "center_y": center_y,
            "radius": radius,
            "plot_radius": plot_radius,
            "plot_left": plot_left,
            "plot_top": plot_top,
            "plot_size": plot_size,
            "plot_rect": plot_rect,
        }

    def _ensure_overlay_cache(self, layout):
        key = (
            layout["widget_width"],
            layout["widget_height"],
            int(layout["center_x"] * 10),
            int(layout["center_y"] * 10),
            int(layout["radius"] * 10),
            int(layout["plot_radius"] * 10),
        )
        if self._cached_overlay_key == key and self._cached_overlay_image is not None:
            return

        overlay = QImage(layout["widget_width"], layout["widget_height"], QImage.Format_ARGB32_Premultiplied)
        overlay.fill(QColor(0, 0, 0, 0))
        painter = QPainter(overlay)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            self._draw_guides(painter, layout["center_x"], layout["center_y"], layout["plot_radius"])
            draw_broadcast_hue_ring(
                painter,
                QPointF(layout["center_x"], layout["center_y"]),
                layout["radius"] - 2.0,
                3.0,
                alpha=220,
            )
            painter.setPen(QPen(QColor(120, 128, 138, 110), 1))
            painter.drawEllipse(layout["plot_rect"])
        finally:
            painter.end()

        self._cached_overlay_image = overlay
        self._cached_overlay_key = key

    def _ensure_scope_cache(self, layout):
        vectorscope = self._data.get("vectorscope", {}) if self._data else {}
        size = vectorscope.get("size", 256)
        flat = vectorscope.get("density", [])
        zoom_factor = {"100": 1.0, "200": 2.0, "400": 4.0}.get(str(self._zoom), 1.0)
        key = (
            self._render_token,
            layout["plot_rect"].width(),
            layout["plot_rect"].height(),
            self._display,
            self._zoom,
            size,
            len(flat),
        )
        if self._cached_scope_key == key and self._cached_scope_image is not None:
            return

        self._cached_scope_image = None
        self._cached_scope_key = key
        self._label_scores = _vectorscope_label_scores(flat, size)
        img = vectorscope.get("image")
        if not isinstance(img, QImage) or img.isNull():
            img = self._build_img(flat, size, zoom_factor)
        if img is None:
            return

        scope_image = QImage(layout["widget_width"], layout["widget_height"], QImage.Format_ARGB32_Premultiplied)
        scope_image.fill(QColor(0, 0, 0, 0))
        painter = QPainter(scope_image)
        try:
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            clip_path = QPainterPath()
            clip_path.addEllipse(layout["plot_left"], layout["plot_top"], layout["plot_size"], layout["plot_size"])
            painter.setClipPath(clip_path)
            painter.drawImage(layout["plot_rect"], img)
        finally:
            painter.end()
        self._cached_scope_image = scope_image

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            w, h = self.width(), self.height()
            painter.fillRect(0, 0, w, h, QColor(0, 0, 0))

            if not self._data or not self._data.get("present"):
                painter.setPen(QColor(80, 80, 80))
                painter.drawText(self.rect(), Qt.AlignCenter, "No Video")
                return

            layout = self._layout_info()
            self._ensure_scope_cache(layout)
            self._ensure_overlay_cache(layout)

            if self._cached_scope_image is not None:
                painter.drawImage(0, 0, self._cached_scope_image)
            if self._cached_overlay_image is not None:
                painter.drawImage(0, 0, self._cached_overlay_image)
            self._draw_labels(painter, layout["center_x"], layout["center_y"],
                              layout["plot_radius"], self._label_scores)
        finally:
            painter.end()


# ─── Audio meter painter ─────────────────────────────────────────────────────

class AudioMeterWidget(QWidget):
    """Per-channel RMS/peak VU bars with clip indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = None
        self.setMinimumSize(60, 80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.NoFocus)

    def update_data(self, audio_data):
        self._data = audio_data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(20, 20, 20))

        if not self._data or not self._data.get("present"):
            painter.setPen(QColor(80, 80, 80))
            painter.drawText(self.rect(), Qt.AlignCenter, "No Audio")
            return

        summary   = self._data.get("summary", {})
        peak_vals = summary.get("peak", [])
        rms_vals  = summary.get("rms", [])
        clipped   = summary.get("clipped_samples", [])
        channels  = self._data.get("channels", 0)

        if not channels:
            return

        gap   = 4
        bar_w = max(8, (w - (channels + 1) * gap) // channels)

        for ch in range(channels):
            x             = gap + ch * (bar_w + gap)
            rms           = rms_vals[ch]  if ch < len(rms_vals)  else 0.0
            peak          = peak_vals[ch] if ch < len(peak_vals) else 0.0
            clipped_count = clipped[ch]   if ch < len(clipped)   else 0

            painter.fillRect(x, 0, bar_w, h, QColor(40, 40, 40))

            rms_h = int(rms * h)
            for row in range(rms_h):
                ratio = row / h
                if ratio > 0.8:
                    color = QColor(220, 50, 50)
                elif ratio > 0.6:
                    color = QColor(220, 200, 50)
                else:
                    color = QColor(50, 200, 50)
                painter.fillRect(x, h - row - 1, bar_w, 1, color)

            if peak > 0:
                peak_y = int((1.0 - peak) * h)
                painter.setPen(QPen(QColor(255, 240, 80), 2))
                painter.drawLine(x, peak_y, x + bar_w - 1, peak_y)

            if clipped_count > 0:
                painter.fillRect(x, 0, bar_w, 5, QColor(255, 40, 40))


# ─── Filter toolbar helpers ──────────────────────────────────────────────────

def _make_combo(parent, items):
    """Create a QComboBox from a list of (data_key, display_label) tuples."""
    from classes.app import get_app
    _ = get_app()._tr
    cb = QComboBox(parent)
    cb.setSizeAdjustPolicy(QComboBox.AdjustToContents)
    for key, label in items:
        cb.addItem(_(label), key)
    return cb


def _restore_combo(combo, value):
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return


# ─── Waveform dock content (painter + toolbar) ───────────────────────────────

class WaveformDockContent(QWidget):
    """Waveform dock widget: filter toolbar above the waveform painter."""
    scopeRegionToggled = pyqtSignal(bool)
    renderSettingsChanged = pyqtSignal()

    _MODES = [
        ("luma",        N_("Luma")),
        ("rgb_overlay", N_("RGB Overlay")),
        ("rgb_parade",  N_("RGB Parade")),
        ("red",         N_("Red")),
        ("green",       N_("Green")),
        ("blue",        N_("Blue")),
    ]
    _COLORS = [
        ("green",  N_("Green")),
        ("white",  N_("White")),
        ("orange", N_("Orange")),
    ]
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 6)
        layout.setSpacing(4)

        toolbar = QWidget(self)
        toolbar.setFocusPolicy(Qt.NoFocus)
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(6)

        self._mode_cb  = _make_combo(toolbar, self._MODES)
        self._color_cb = _make_combo(toolbar, self._COLORS)
        self._region_btn = _make_scope_region_button(toolbar)
        tl.addWidget(self._mode_cb)
        tl.addWidget(self._color_cb)
        tl.addStretch()
        tl.addWidget(self._region_btn)

        self.waveform = WaveformWidget(self)
        layout.addWidget(toolbar)
        layout.addWidget(self.waveform)

        # Restore saved state
        _restore_combo(self._mode_cb,  _get(_S_WAVE_MODE,  "luma"))
        _restore_combo(self._color_cb, _get(_S_WAVE_COLOR, "green"))
        self._sync_color_visibility()

        self._mode_cb.currentIndexChanged.connect(self._on_mode)
        self._color_cb.currentIndexChanged.connect(self._on_color)
        self._region_btn.toggled.connect(self.scopeRegionToggled.emit)

    def _sync_color_visibility(self):
        self._color_cb.setVisible(self._mode_cb.currentData() == "luma")

    def _on_mode(self):
        self.waveform.set_mode(self._mode_cb.currentData())
        self._sync_color_visibility()
        self.renderSettingsChanged.emit()

    def _on_color(self):
        self.waveform.set_color(self._color_cb.currentData())

    def render_settings(self):
        return {
            "columns": max(32, int(self.waveform.width() or 256)),
        }

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.renderSettingsChanged.emit()

    def set_scope_region_enabled(self, enabled):
        self._region_btn.blockSignals(True)
        self._region_btn.setChecked(bool(enabled))
        self._region_btn.blockSignals(False)

    @pyqtSlot(dict)
    def update_data(self, video_data):
        self.waveform.update_data(video_data)


# ─── Histogram dock content (painter + toolbar) ──────────────────────────────

class HistogramDockContent(QWidget):
    """Histogram dock widget: filter toolbar above the histogram painter."""
    scopeRegionToggled = pyqtSignal(bool)

    _CHANNELS = [
        ("rgba",  N_("All Channels")),
        ("luma",  N_("Luma")),
        ("red",   N_("Red")),
        ("green", N_("Green")),
        ("blue",  N_("Blue")),
    ]
    _SCALES = [
        ("log",    N_("Logarithmic")),
        ("linear", N_("Linear")),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 6)
        layout.setSpacing(4)

        toolbar = QWidget(self)
        toolbar.setFocusPolicy(Qt.NoFocus)
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(6)

        self._ch_cb    = _make_combo(toolbar, self._CHANNELS)
        self._scale_cb = _make_combo(toolbar, self._SCALES)
        self._region_btn = _make_scope_region_button(toolbar)
        tl.addWidget(self._ch_cb)
        tl.addWidget(self._scale_cb)
        tl.addStretch()
        tl.addWidget(self._region_btn)

        self.histogram = HistogramWidget(self)
        layout.addWidget(toolbar)
        layout.addWidget(self.histogram)

        _restore_combo(self._ch_cb,    _get(_S_HIST_CH,    "rgba"))
        _restore_combo(self._scale_cb, _get(_S_HIST_SCALE, "log"))

        self._ch_cb.currentIndexChanged.connect(self._on_channel)
        self._scale_cb.currentIndexChanged.connect(self._on_scale)
        self._region_btn.toggled.connect(self.scopeRegionToggled.emit)

    def _on_channel(self):
        self.histogram.set_channel(self._ch_cb.currentData())

    def _on_scale(self):
        self.histogram.set_scale(self._scale_cb.currentData())

    def set_scope_region_enabled(self, enabled):
        self._region_btn.blockSignals(True)
        self._region_btn.setChecked(bool(enabled))
        self._region_btn.blockSignals(False)

    @pyqtSlot(dict)
    def update_data(self, video_data):
        self.histogram.update_data(video_data)


class VectorscopeDockContent(QWidget):
    """Vectorscope dock widget with a minimal toolbar."""
    scopeRegionToggled = pyqtSignal(bool)
    renderSettingsChanged = pyqtSignal()

    _DISPLAYS = [
        ("colorized", N_("Colorized")),
        ("density", N_("Density")),
        ("intensity", N_("Intensity")),
    ]
    _ZOOMS = [
        ("100", "100%"),
        ("200", "200%"),
        ("400", "400%"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 6)
        layout.setSpacing(4)

        toolbar = QWidget(self)
        toolbar.setFocusPolicy(Qt.NoFocus)
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(6)

        self._display_cb = _make_combo(toolbar, self._DISPLAYS)
        self._zoom_cb = _make_combo(toolbar, self._ZOOMS)
        self._region_btn = _make_scope_region_button(toolbar)
        tl.addWidget(self._display_cb)
        tl.addWidget(self._zoom_cb)
        tl.addStretch()
        tl.addWidget(self._region_btn)

        self.vectorscope = VectorscopeWidget(self)
        layout.addWidget(toolbar)
        layout.addWidget(self.vectorscope)

        _restore_combo(self._display_cb, _get(_S_VEC_DISPLAY, "colorized"))
        _restore_combo(self._zoom_cb, _get(_S_VEC_ZOOM, "100"))

        self._display_cb.currentIndexChanged.connect(self._on_display)
        self._zoom_cb.currentIndexChanged.connect(self._on_zoom)
        self._region_btn.toggled.connect(self.scopeRegionToggled.emit)

    def _on_display(self):
        self.vectorscope.set_display(self._display_cb.currentData())
        self.renderSettingsChanged.emit()

    def _on_zoom(self):
        self.vectorscope.set_zoom(self._zoom_cb.currentData())
        self.renderSettingsChanged.emit()

    def render_settings(self):
        return {
            "display": normalize_vectorscope_display(self._display_cb.currentData()),
            "zoom": str(self._zoom_cb.currentData() or "100"),
        }

    def set_scope_region_enabled(self, enabled):
        self._region_btn.blockSignals(True)
        self._region_btn.setChecked(bool(enabled))
        self._region_btn.blockSignals(False)

    @pyqtSlot(dict)
    def update_data(self, video_data):
        self.vectorscope.update_data(video_data)
