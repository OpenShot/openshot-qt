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
        self.playhead_width         = 1.5
        self.clip_selected          = QColor("#6BA3FF")            # accent-hi ring replaces red

        sel_fill = QColor(tokens.palette["accent"])
        sel_fill.setAlpha(45)
        self.selection              = sel_fill

        sel_border = QColor(tokens.palette["accent"])
        sel_border.setAlpha(160)
        self.selection_border       = sel_border
        self.selection_border_width = 1.0

        self.ruler_name_background  = QColor("#10141B")
        self.ruler_name_background2 = QColor()
        self.ruler_time_font_size   = 10
        self.scrollbar_track        = QColor(tokens.palette["window_bg"])
        self.scrollbar_handle       = QColor("#232A3A")
        self.scrollbar_width        = 8
        self.waveform_color         = QColor("#4EC28A")
        self.waveform_peak_color    = QColor(78, 194, 138, 110)
        self.keyframe_fill          = QColor("#6BA3FF")
        self.keyframe_border        = QColor(tokens.palette["window_bg"])
        self.keyframe_inactive_opacity       = 0.5
        self.keyframe_panel_property_bg      = QColor()
        self.keyframe_panel_row_border_color = QColor()
        self.keyframe_panel_curve_color      = QColor()
        self.keyframe_panel_marker_fill      = QColor()
        self.keyframe_panel_marker_border    = QColor()

        # ── Clip ──────────────────────────────────────────────────────────
        self.clip.background    = QColor("#232A3A")          # fallback fill (bg-3)
        self.clip.background2   = QColor()
        self.clip.top_overlay   = QColor()      # gradient overlay disabled
        self.clip.top_overlay2  = QColor()
        self.clip.border_color  = QColor("#232830")        # hairline outline
        self.clip.border_radius = 3
        self.clip.type_styles = {
            "video": {"fill": QColor("#152034"), "edge": QColor("#4C8DFF")},
            "audio": {"fill": QColor("#162624"), "edge": QColor("#4EC28A")},
            "image": {"fill": QColor("#28221C"), "edge": QColor("#E5A24B")},
        }
        self.clip.height        = 48

        # ── Track ─────────────────────────────────────────────────────────
        self.track.background               = QColor(tokens.palette["track_bg"])
        self.track.background2              = QColor()
        self.track.border_color             = QColor(tokens.palette["border_subtle"])
        self.track.border_radius            = 0
        self.track.height                   = 48
        self.track.name_background          = QColor("#151A22")
        self.track.name_border_color        = QColor("#4C8DFF")
        self.track.name_border_width        = 3
        self.track.name_border_top_color    = QColor(tokens.palette["border_subtle"])
        self.track.name_border_top_width    = 1
        self.track.name_border_bottom_color = QColor(tokens.palette["border_subtle"])
        self.track.name_border_bottom_width = 1
        self.track.name_radius_tl           = 0   # gradient overlay/radius disabled
        self.track.name_radius_bl           = 0
        self.track.name_top_overlay         = QColor()
        self.track.name_top_overlay2        = QColor()

        # ── Transition ────────────────────────────────────────────────────
        self.transition.height = 48
        self.transition.background = QColor("#221F32")
        self.transition.border_color = QColor("#B586FF")

        # ── Ruler ─────────────────────────────────────────────────────────
        self.ruler.background   = QColor("#10141B")
        self.ruler.background2  = QColor()
        self.ruler.border_color = QColor(tokens.palette["border_subtle"])
        self.ruler.font_color   = QColor("#6B7688")
        self.ruler.font_family = "IBM Plex Mono"     # new attribute, consumed by ruler painter

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
        self.track_visible_enabled_icon         = _icon(_c + "track-visible-enabled.svg")
        self.track_visible_disabled_icon        = _icon(_c + "track-visible-disabled.svg")
        self.track_muted_enabled_icon           = _icon(_c + "track-muted-enabled.svg")
        self.track_muted_disabled_icon          = _icon(_c + "track-muted-disabled.svg")

        self.keyframe_toggle_off_icon = self.track_keyframe_panel_disabled_icon
        self.keyframe_toggle_on_icon  = self.track_keyframe_panel_enabled_icon
