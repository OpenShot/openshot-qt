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


def paint_media_overlay(painter, deco_rect, media_type):
    """Paint a centered translucent play glyph for video thumbnails."""
    if not deco_rect or not deco_rect.isValid():
        return

    icon_path = _overlay_icon_path(media_type)
    if not icon_path or not os.path.exists(icon_path):
        return

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setOpacity(0.7)

    glyph_size = max(16.0, min(deco_rect.width(), deco_rect.height()) * 0.36)
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


def _paint_chip(painter, x, y, text, bg, fg, align_right=False, align_bottom=False):
    from qt_api import QFont, QColor, QRectF, QPainterPath, Qt
    font = QFont("IBM Plex Mono")
    font.setPixelSize(9)
    if hasattr(QFont, "Weight"):
        font.setWeight(QFont.Weight.DemiBold)
    else:
        font.setBold(True)
    painter.setFont(font)
    fm = painter.fontMetrics()
    tw = fm.horizontalAdvance(text)
    th = fm.height()
    pad_h, pad_v = 5.0, 2.0
    w = tw + pad_h * 2
    h = th + pad_v * 2
    rx = x - w if align_right else x
    ry = y - h if align_bottom else y
    path = QPainterPath()
    path.addRoundedRect(QRectF(rx, ry, w, h), 3.0, 3.0)
    painter.fillPath(path, QColor(*bg))
    painter.setPen(QColor(fg))
    align_center = Qt.AlignmentFlag.AlignCenter if hasattr(Qt, "AlignmentFlag") else Qt.AlignCenter
    painter.drawText(QRectF(rx, ry, w, h), align_center, text)


def paint_meta_badges(painter, deco_rect, media_type, duration=0.0, width=0, height=0):
    """Paint kind/duration/resolution chips over a thumbnail rect."""
    if not deco_rect or not deco_rect.isValid():
        return
    painter.save()
    from qt_api import QPainter
    painter.setRenderHint(QPainter.Antialiasing, True)
    m = 6.0
    kind = str(media_type or "").strip().upper()
    if kind:
        _paint_chip(painter, deco_rect.left() + m, deco_rect.top() + m, kind, (0, 0, 0, 165), "#E7ECF3")
    if deco_rect.width() >= 70:
        mt = str(media_type or "").strip().lower()
        if mt in ("video", "audio") and duration and duration > 0:
            secs = int(round(float(duration)))
            if secs >= 3600:
                txt = "%d:%02d:%02d" % (secs // 3600, (secs % 3600) // 60, secs % 60)
            else:
                txt = "%02d:%02d" % (secs // 60, secs % 60)
            _paint_chip(painter, deco_rect.right() - m, deco_rect.bottom() - m, txt, (0, 0, 0, 178), "#E7ECF3", align_right=True, align_bottom=True)
        if mt in ("video", "image") and width and height:
            _paint_chip(painter, deco_rect.left() + m, deco_rect.bottom() - m, "%d×%d" % (int(width), int(height)), (0, 0, 0, 140), "#A9B2C0", align_bottom=True)
    painter.restore()
