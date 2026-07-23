"""
Timeline theme class for the Cosmic Dusk Qt theme.

Derives from HumanityDarkTimelineTheme and overrides only what differs.
"""

from qt_api import QColor

from themes.humanity.styles import HumanityDarkTimelineTheme
from windows.views.timeline_backend.theme import _icon
from themes.modern import tokens


class ModernTimelineTheme(HumanityDarkTimelineTheme):
    """Modern timeline theme."""

    def __init__(self):
        super().__init__()

        # ── Timeline ──────────────────────────────────────────────────────
        self.background             = QColor(tokens.palette["window_bg"])
        self.background2            = QColor()
        self.playhead_color         = QColor(tokens.palette["playhead"])
        self.ruler_name_background  = QColor(tokens.palette["window_bg"])
        self.ruler_name_background2 = QColor()
        self.scrollbar_track        = QColor(tokens.palette["window_bg"])
        self.scrollbar_width        = 8
        self.keyframe_inactive_opacity       = 0.5
        self.keyframe_panel_property_bg      = QColor()
        self.keyframe_panel_row_border_color = QColor()
        self.keyframe_panel_curve_color      = QColor()
        self.keyframe_panel_marker_fill      = QColor()
        self.keyframe_panel_marker_border    = QColor()

        # ── Clip ──────────────────────────────────────────────────────────
        self.clip.background    = QColor(tokens.palette["clip_bg"])
        self.clip.background2   = QColor()
        self.clip.top_overlay   = QColor()      # gradient overlay disabled
        self.clip.top_overlay2  = QColor()
        self.clip.border_color  = QColor(tokens.palette["accent"])
        self.clip.border_radius = 8
        self.clip.height        = 48

        # ── Track ─────────────────────────────────────────────────────────
        self.track.background               = QColor(tokens.palette["track_bg"])
        self.track.background2              = QColor()
        self.track.border_color             = QColor(tokens.palette["track_bg"])
        self.track.border_radius            = 0
        self.track.height                   = 48
        self.track.name_background          = QColor(tokens.palette["clip_bg"])
        self.track.name_border_color        = QColor(tokens.palette["accent"])
        self.track.name_border_width        = 4
        self.track.name_border_top_color    = QColor(tokens.palette["clip_bg"])
        self.track.name_border_top_width    = 1
        self.track.name_border_bottom_color = QColor(tokens.palette["clip_bg"])
        self.track.name_border_bottom_width = 1
        self.track.name_radius_tl           = 0   # gradient overlay/radius disabled
        self.track.name_radius_bl           = 0
        self.track.name_top_overlay         = QColor()
        self.track.name_top_overlay2        = QColor()

        # ── Transition ────────────────────────────────────────────────────
        self.transition.height = 48

        # ── Ruler ─────────────────────────────────────────────────────────
        self.ruler.background  = QColor(tokens.palette["window_bg"])
        self.ruler.background2 = QColor()

        # ── Icons ─────────────────────────────────────────────────────────
        _c = "themes/modern/images/"

        self.playhead_icon                      = _icon(_c + "playhead.svg")
        self.track_keyframe_panel_disabled_icon = _icon(_c + "track-keyframe-panel-show-disabled.svg")
        self.track_keyframe_panel_enabled_icon  = _icon(_c + "track-keyframe-panel-show-enabled.svg")
        self.keyframe_panel_add_icon            = _icon(_c + "keyframe-panel-add.svg")
        self.track_add_above_disabled_icon      = _icon(_c + "track-add-above-disabled.svg")
        self.track_add_above_enabled_icon       = _icon(_c + "track-add-above-enabled.svg")
        self.track_add_below_disabled_icon      = _icon(_c + "track-add-below-disabled.svg")
        self.track_add_below_enabled_icon       = _icon(_c + "track-add-below-enabled.svg")
        self.track_delete_disabled_icon         = _icon(_c + "track-delete-disabled.svg")
        self.track_delete_enabled_icon          = _icon(_c + "track-delete-enabled.svg")
        self.track_locked_disabled_icon         = _icon(_c + "track-locked-disabled.svg")
        self.track_locked_enabled_icon          = _icon(_c + "track-locked-enabled.svg")
        self.track_unlocked_disabled_icon       = _icon(_c + "track-unlocked-disabled.svg")
        self.track_unlocked_enabled_icon        = _icon(_c + "track-unlocked-enabled.svg")

        self.keyframe_toggle_off_icon = self.track_keyframe_panel_disabled_icon
        self.keyframe_toggle_on_icon  = self.track_keyframe_panel_enabled_icon
