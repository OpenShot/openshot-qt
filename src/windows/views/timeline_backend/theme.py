"""Timeline theme data structures."""

import os
from typing import Optional

from qt_api import QColor, QPixmap, QByteArray
from classes.info import PATH


def _apply_overrides(obj, overrides: dict, *, allow_unknown: bool = False) -> None:
    if not overrides:
        return
    allowed = set(obj.__dict__.keys())
    for key, value in overrides.items():
        if key not in allowed:
            if allow_unknown:
                continue
            raise TypeError("Unexpected theme option '%s'" % key)
        setattr(obj, key, value)


def _icon(rel_path: Optional[str]) -> Optional[QPixmap]:
    """Load a pixmap from *rel_path* (relative to PATH) with SVG metadata attached."""
    if not rel_path:
        return None
    path = os.path.normpath(os.path.join(PATH, rel_path))
    if not os.path.exists(path):
        return None
    pix = QPixmap(path)
    if pix.isNull():
        return None
    pix.svg_path = path
    if path.lower().endswith(".svg"):
        try:
            with open(path, "rb") as fh:
                data = fh.read()
            pix.svg_bytes = data
            try:
                pix.svg_qbytearray = QByteArray(data)
            except Exception:
                pass
        except Exception:
            pass
    return pix


class BasicTheme:
    """Common style options for timeline elements."""

    def __init__(self, **kwargs):
        self.background: QColor = QColor()
        self.background2: QColor = QColor()
        self.border_color: QColor = QColor()
        self.border_radius: int = 0
        self.border_width: float = 0
        self.font_color: QColor = QColor()
        self.font_size: int = 0
        self.height: int = 0
        self.background_image: Optional[QPixmap] = None
        self.shadow_color: QColor = QColor()
        self.shadow_blur: int = 0
        self.thumb_width: int = 0
        self.thumb_height: int = 0
        self.top_overlay: QColor = QColor()
        self.top_overlay2: QColor = QColor()
        _apply_overrides(self, kwargs)


class TrackTheme(BasicTheme):
    """Theme for tracks."""

    def __init__(self, **kwargs):
        super().__init__()
        self.menu_icon: Optional[QPixmap] = None
        self.name_background: QColor = QColor()
        self.name_width: int = 0
        self.gap: int = 0
        self.margin_top: int = -1
        self.name_border_color: QColor = QColor()
        self.name_border_width: int = 0
        self.name_border_top_color: QColor = QColor()
        self.name_border_top_width: int = 0
        self.name_border_bottom_color: QColor = QColor()
        self.name_border_bottom_width: int = 0
        self.name_border_right_color: QColor = QColor()
        self.name_border_right_width: int = 0
        self.name_radius_tl: int = 0
        self.name_radius_bl: int = 0
        self.name_top_overlay: QColor = QColor()
        self.name_top_overlay2: QColor = QColor()
        _apply_overrides(self, kwargs)


class TimelineTheme:
    """Container for all timeline painting values."""

    def __init__(self, **kwargs):
        self.background: QColor = QColor("#000")
        self.background2: QColor = QColor()
        self.playhead_color: QColor = QColor("#FFF")
        self.playhead_width: float = 0.0
        self.clip_selected: QColor = QColor("#FFF")
        self.selection: QColor = QColor(255, 255, 255, 80)
        self.selection_border: QColor = QColor()
        self.selection_border_width: float = 0.0
        self.playback_cache_color: QColor = QColor("#4B92AD")
        self.playback_cache_height: float = 5.0

        self.clip: BasicTheme = BasicTheme()
        self.transition: BasicTheme = BasicTheme()
        self.track: TrackTheme = TrackTheme()
        self.ruler: BasicTheme = BasicTheme()
        self.ruler_name_background: QColor = QColor()
        self.ruler_name_background2: QColor = QColor()
        self.label_font_scale: float = 1.0
        self.ruler_time_font_size: int = 0
        self.menu_icon: Optional[QPixmap] = None
        self.menu_size: int = 0
        self.menu_margin: int = 0
        self.keyframe_toggle_off_icon: Optional[QPixmap] = None
        self.keyframe_toggle_on_icon: Optional[QPixmap] = None
        self.track_keyframe_panel_disabled_icon: Optional[QPixmap] = None
        self.track_keyframe_panel_enabled_icon: Optional[QPixmap] = None
        self.track_add_above_disabled_icon: Optional[QPixmap] = None
        self.track_add_above_enabled_icon: Optional[QPixmap] = None
        self.track_add_below_disabled_icon: Optional[QPixmap] = None
        self.track_add_below_enabled_icon: Optional[QPixmap] = None
        self.track_delete_disabled_icon: Optional[QPixmap] = None
        self.track_delete_enabled_icon: Optional[QPixmap] = None
        self.track_locked_disabled_icon: Optional[QPixmap] = None
        self.track_locked_enabled_icon: Optional[QPixmap] = None
        self.track_unlocked_disabled_icon: Optional[QPixmap] = None
        self.track_unlocked_enabled_icon: Optional[QPixmap] = None
        self.keyframe_panel_add_icon: Optional[QPixmap] = None
        self.keyframe_panel_property_bg: QColor = QColor()
        self.keyframe_panel_row_border_color: QColor = QColor()
        self.keyframe_panel_row_border_width: float = 1.0
        self.keyframe_panel_curve_color: QColor = QColor()
        self.keyframe_panel_marker_fill: QColor = QColor()
        self.keyframe_panel_marker_border: QColor = QColor()
        self.playhead_icon: Optional[QPixmap] = None
        self.playhead_icon_width: int = 0
        self.playhead_icon_height: int = 0
        self.playhead_icon_offset_x: int = 0
        self.playhead_icon_offset_y: int = 0
        self.marker_icon: Optional[QPixmap] = None
        self.marker_icon_width: int = 0
        self.marker_icon_height: int = 0
        self.marker_icon_offset_x: Optional[int] = None
        self.marker_icon_offset_y: Optional[int] = None
        self.marker_hit_padding: float = 4.0
        self.ruler_time_pad_left: int = 0
        self.ruler_time_pad_top: int = 0
        self.ruler_label_top: int = 0
        self.scrollbar_handle: QColor = QColor()
        self.scrollbar_track: QColor = QColor()
        self.scrollbar_width: int = 0
        self.waveform_color: QColor = QColor(42, 130, 218)
        self.waveform_peak_color: QColor = QColor(42, 130, 218, 128)
        self.keyframe_fill: QColor = QColor("#4d7bff")
        self.keyframe_border: QColor = QColor("#ffffff")
        self.keyframe_inactive_opacity: float = 0.5
        self.keyframe_size: int = 10
        _apply_overrides(self, kwargs)


DEFAULT_THEME = TimelineTheme()
