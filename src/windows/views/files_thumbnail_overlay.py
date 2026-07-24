"""
 @file
 @brief Dynamic media-type overlay painter for project file thumbnails.
"""

import os

from qt_api import QRectF
from qt_api import QPainter
from qt_api import QSvgRenderer

from classes import info


_VIDEO_OVERLAY_ICON = "tool-media-play.svg"
_OPTIMIZE_PREVIEW_READY_ICON = "tool-optimize-preview.svg"
_OPTIMIZE_PREVIEW_MISSING_ICON = "tool-optimize-preview-missing.svg"


def _overlay_icon_path(media_type):
    if str(media_type or "").strip().lower() != "video":
        return ""
    return os.path.join(info.PATH, "themes", "cosmic", "images", _VIDEO_OVERLAY_ICON)


def paint_media_overlay(painter, deco_rect, media_type, hovered=False):
    """Paint a centered play glyph for video thumbnails, dim at rest and full on hover."""
    if not deco_rect or not deco_rect.isValid():
        return

    icon_path = _overlay_icon_path(media_type)
    if not icon_path or not os.path.exists(icon_path):
        return

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setOpacity(0.9 if hovered else 0.32)

    glyph_size = max(16.0, min(deco_rect.width(), deco_rect.height()) * (0.30 if hovered else 0.22))
    glyph_rect = QRectF(
        deco_rect.center().x() - (glyph_size / 2.0),
        deco_rect.center().y() - (glyph_size / 2.0),
        glyph_size,
        glyph_size,
    )
    renderer = QSvgRenderer(icon_path)
    renderer.render(painter, glyph_rect)

    painter.restore()


def paint_proxy_badge(painter, deco_rect, proxy_state):
    """Paint a bottom-right lightning badge for proxy-ready/missing files."""
    proxy_state = str(proxy_state or "").strip().lower()
    if proxy_state not in ("ready", "missing"):
        return
    if not deco_rect or not deco_rect.isValid():
        return

    icon_name = _OPTIMIZE_PREVIEW_MISSING_ICON if proxy_state == "missing" else _OPTIMIZE_PREVIEW_READY_ICON
    icon_path = os.path.join(info.PATH, "themes", "cosmic", "images", icon_name)
    if not os.path.exists(icon_path):
        return

    badge_size = max(14.0, min(deco_rect.width(), deco_rect.height()) * 0.24)
    margin_x = 1.5
    margin_y = 4.0
    glyph_rect = QRectF(
        deco_rect.right() - badge_size - margin_x,
        deco_rect.bottom() - badge_size - margin_y,
        badge_size,
        badge_size,
    )

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setOpacity(0.95)
    renderer = QSvgRenderer(icon_path)
    renderer.render(painter, glyph_rect)
    painter.restore()


def _paint_scrim(painter, deco_rect):
    """Soft bottom gradient so overlaid text stays legible without hard chip edges."""
    from qt_api import QLinearGradient, QPointF, QColor
    top = deco_rect.bottom() - deco_rect.height() * 0.42
    grad = QLinearGradient(QPointF(0, top), QPointF(0, deco_rect.bottom()))
    grad.setColorAt(0.0, QColor(0, 0, 0, 0))
    grad.setColorAt(1.0, QColor(0, 0, 0, 145))
    painter.fillRect(QRectF(deco_rect.left(), top, deco_rect.width(), deco_rect.bottom() - top), grad)


def _paint_label(painter, x, y, text, font_family, pixel_size, weight_demibold, fg, align_right=False, align_bottom=False, shadow=True):
    """Paint plain text (optionally with a soft drop shadow) - no chip background."""
    from qt_api import QFont, QColor, QRectF, Qt
    font = QFont(font_family)
    font.setPixelSize(pixel_size)
    if weight_demibold:
        if hasattr(QFont, "Weight"):
            font.setWeight(QFont.Weight.DemiBold)
        else:
            font.setBold(True)
    painter.setFont(font)
    fm = painter.fontMetrics()
    tw = fm.horizontalAdvance(text)
    th = fm.height()
    rx = x - tw if align_right else x
    ry = y - th if align_bottom else y
    rect = QRectF(rx, ry, tw, th)
    align_center = Qt.AlignmentFlag.AlignCenter if hasattr(Qt, "AlignmentFlag") else Qt.AlignCenter
    if shadow:
        painter.setPen(QColor(0, 0, 0, 190))
        painter.drawText(rect.translated(0.6, 0.6), align_center, text)
    painter.setPen(QColor(fg))
    painter.drawText(rect, align_center, text)


def paint_meta_badges(painter, deco_rect, media_type, duration=0.0, width=0, height=0, hovered=False):
    """Paint a subtle kind label always, and a combined resolution/duration readout on hover only."""
    if not deco_rect or not deco_rect.isValid():
        return
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    m = 7.0
    mt = str(media_type or "").strip().lower()
    kind = mt.upper()

    if hovered and deco_rect.width() >= 70:
        _paint_scrim(painter, deco_rect)

    if kind:
        _paint_label(
            painter, deco_rect.left() + m, deco_rect.top() + m, kind,
            "Inter", 9, True, "#E7ECF3", shadow=True)

    if hovered and deco_rect.width() >= 70:
        parts = []
        if mt in ("video", "image") and width and height:
            parts.append("%d×%d" % (int(width), int(height)))
        if mt in ("video", "audio") and duration and duration > 0:
            secs = int(round(float(duration)))
            if secs >= 3600:
                parts.append("%d:%02d:%02d" % (secs // 3600, (secs % 3600) // 60, secs % 60))
            else:
                parts.append("%02d:%02d" % (secs // 60, secs % 60))
        if parts:
            _paint_label(
                painter, deco_rect.right() - m, deco_rect.bottom() - m, "  ·  ".join(parts),
                "IBM Plex Mono", 9, False, "#E7ECF3",
                align_right=True, align_bottom=True, shadow=True)

    painter.restore()
