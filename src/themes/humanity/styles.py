"""
Timeline theme classes for the Humanity Dark and Retro Qt themes.

Subclass any theme and override only what you need:

    class MyTheme(HumanityDarkTimelineTheme):
        def __init__(self):
            super().__init__()
            self.clip.background = QColor("#ff0000")
            self.track.height    = 80
"""

from qt_api import QColor

from windows.views.timeline_backend.theme import TimelineTheme, _icon


class HumanityDarkTimelineTheme(TimelineTheme):
    """Humanity Dark timeline theme — base for all other themes."""

    def __init__(self):
        super().__init__()

        # ── Timeline ──────────────────────────────────────────────────────
        self.background             = QColor("#191919")
        self.background2            = QColor()
        self.playhead_color         = QColor("#FF0024")
        self.playhead_width         = 2.0
        self.clip_selected          = QColor("#FF0000")
        self.selection              = QColor(42, 130, 218, 102)
        self.selection_border       = QColor(42, 130, 218, 102)
        self.selection_border_width = 1.0
        self.playback_cache_color   = QColor("#4B92AD")
        self.playback_cache_height  = 5.0
        self.ruler_name_background  = QColor("#191919")
        self.ruler_name_background2 = QColor()
        self.ruler_time_font_size   = 13
        self.ruler_time_pad_left    = 17
        self.ruler_time_pad_top     = 12
        self.ruler_label_top        = 6
        self.scrollbar_handle       = QColor("#4B92AD")
        self.scrollbar_track        = QColor("#000000")
        self.scrollbar_width        = 6
        self.waveform_color         = QColor("#2A82DA")
        self.waveform_peak_color    = QColor(42, 130, 218, 128)
        self.keyframe_fill          = QColor("#4D7BFF")
        self.keyframe_border        = QColor("#FFFFFF")
        self.keyframe_inactive_opacity       = 0.7
        self.keyframe_size                   = 10
        self.keyframe_panel_property_bg      = QColor("#2F2F2F")
        self.keyframe_panel_row_border_color = QColor(0, 0, 0, 0)
        self.keyframe_panel_row_border_width = 0.0
        self.keyframe_panel_curve_color      = QColor("#4B92AD")
        self.keyframe_panel_marker_fill      = QColor("#4B92AD")
        self.keyframe_panel_marker_border    = QColor("#7DC3DD")

        # ── Clip ──────────────────────────────────────────────────────────
        self.clip.background    = QColor("#525252")
        self.clip.background2   = QColor("#222628")
        self.clip.top_overlay   = QColor(255, 255, 255, 51)
        self.clip.top_overlay2  = QColor(255, 255, 255, 0)
        self.clip.border_color  = QColor("#4B92AD")
        self.clip.border_radius = 8
        self.clip.border_width  = 2.0
        self.clip.font_color    = QColor("#FFFFFF")
        self.clip.font_size     = 9
        self.clip.height        = 64
        self.clip.shadow_color  = QColor("#000000")
        self.clip.shadow_blur   = 10

        # ── Track ─────────────────────────────────────────────────────────
        self.track.background               = QColor("#060606")
        self.track.background2              = QColor("#323232")
        self.track.border_color             = QColor("#4B92AD")
        self.track.border_radius            = 0
        self.track.height                   = 62
        self.track.gap                      = 8
        self.track.margin_top               = -1
        self.track.font_color               = QColor("#FFFFFF")
        self.track.font_size                = 9
        self.track.name_background          = QColor("#000000")
        self.track.name_width               = 140
        self.track.name_border_color        = QColor("#4B92AD")
        self.track.name_border_width        = 1
        self.track.name_border_top_color    = QColor("#4B92AD")
        self.track.name_border_top_width    = 1
        self.track.name_border_bottom_color = QColor("#4B92AD")
        self.track.name_border_bottom_width = 1
        self.track.name_radius_tl           = 8
        self.track.name_radius_bl           = 8
        self.track.name_top_overlay         = QColor(255, 255, 255, 51)
        self.track.name_top_overlay2        = QColor(255, 255, 255, 0)

        # ── Transition ────────────────────────────────────────────────────
        self.transition.background       = QColor("#0192C1")
        self.transition.background2      = QColor("#3FA1BF")
        self.transition.border_color     = QColor("#0192C1")
        self.transition.border_radius    = 8
        self.transition.border_width     = 2.0
        self.transition.font_color       = QColor("#FFFFFF")
        self.transition.font_size        = 9
        self.transition.height           = 64
        self.transition.background_image = _icon("themes/humanity/images/transition.svg")

        # ── Ruler ─────────────────────────────────────────────────────────
        self.ruler.background   = QColor("#191919")
        self.ruler.background2  = QColor()
        self.ruler.border_color = QColor("#ACACAC")
        self.ruler.font_color   = QColor("#999999")
        self.ruler.font_size    = 10
        self.ruler.height       = 39

        # ── Icons ─────────────────────────────────────────────────────────
        _h = "themes/humanity/images/"
        _c = "themes/cosmic/images/"    # fallback for icons missing a Humanity Dark variant

        self.menu_size               = 12
        self.menu_margin             = 4
        self.playhead_icon           = _icon("themes/humanity/images/playhead.svg")
        self.playhead_icon_width     = 12
        self.playhead_icon_height    = 188
        self.playhead_icon_offset_x  = -6
        self.playhead_icon_offset_y  = 20
        self.marker_icon             = _icon("themes/humanity/images/marker.svg")
        self.marker_icon_width       = 8
        self.marker_icon_height      = 10
        self.marker_icon_offset_x    = -4
        self.marker_icon_offset_y    = 0

        self.track_keyframe_panel_disabled_icon = _icon(_h + "humanity-dark-track-keyframe-panel-show-disabled.svg")
        self.track_keyframe_panel_enabled_icon  = _icon(_h + "humanity-dark-track-keyframe-panel-show-enabled.svg")
        self.keyframe_panel_add_icon            = _icon(_c + "keyframe-panel-add.svg")  # no Humanity Dark variant
        self.track_add_above_disabled_icon      = _icon(_h + "track-add-above-disabled.svg")
        self.track_add_above_enabled_icon       = _icon(_h + "track-add-above-enabled.svg")
        self.track_add_below_disabled_icon      = _icon(_h + "track-add-below-disabled.svg")
        self.track_add_below_enabled_icon       = _icon(_h + "track-add-below-enabled.svg")
        self.track_delete_disabled_icon         = _icon(_h + "track-delete-disabled.svg")
        self.track_delete_enabled_icon          = _icon(_h + "track-delete-enabled.svg")
        self.track_locked_disabled_icon         = _icon(_h + "humanity-dark-track-locked-disabled.svg")
        self.track_locked_enabled_icon          = _icon(_h + "humanity-dark-track-locked-enabled.svg")
        self.track_unlocked_disabled_icon       = _icon(_h + "humanity-dark-track-unlocked-disabled.svg")
        self.track_unlocked_enabled_icon        = _icon(_h + "humanity-dark-track-unlocked-enabled.svg")
        self.track_visible_disabled_icon        = _icon(_h + "track-visible-disabled.svg")
        self.track_visible_enabled_icon         = _icon(_h + "track-visible-enabled.svg")
        self.track_muted_disabled_icon          = _icon(_h + "track-muted-disabled.svg")
        self.track_muted_enabled_icon           = _icon(_h + "track-muted-enabled.svg")

        self.keyframe_toggle_off_icon = self.track_keyframe_panel_disabled_icon
        self.keyframe_toggle_on_icon  = self.track_keyframe_panel_enabled_icon


class RetroTimelineTheme(HumanityDarkTimelineTheme):
    """Retro (light) timeline theme."""

    def __init__(self):
        super().__init__()

        # ── Timeline ──────────────────────────────────────────────────────
        self.background             = QColor("#F0F0F0")
        self.background2            = QColor()
        self.ruler_name_background  = QColor("#0A070A")
        self.ruler_name_background2 = QColor("#3C3C3C")
        self.keyframe_inactive_opacity    = 0.72
        self.keyframe_panel_property_bg   = QColor("#E5E7EA")
        self.keyframe_panel_marker_border = QColor("#3A748A")

        # ── Clip ──────────────────────────────────────────────────────────
        self.clip.background    = QColor("#FEDC66")
        self.clip.background2   = QColor()
        self.clip.top_overlay   = QColor()      # gradient overlay disabled
        self.clip.top_overlay2  = QColor()
        self.clip.border_color  = QColor("#CD8D00")
        self.clip.border_radius = 0
        self.clip.font_color    = QColor("#FFFFFF")

        # ── Track ─────────────────────────────────────────────────────────
        self.track.background        = QColor("#E5E7EA")
        self.track.background2       = QColor()
        self.track.border_radius     = 0
        self.track.font_color        = QColor("#000000")
        self.track.name_background   = QColor("#DEDDDD")
        self.track.name_radius_tl    = 0         # gradient overlay/radius disabled
        self.track.name_radius_bl    = 0
        self.track.name_top_overlay  = QColor()
        self.track.name_top_overlay2 = QColor()

        # ── Transition ────────────────────────────────────────────────────
        self.transition.border_radius = 0

        # ── Ruler ─────────────────────────────────────────────────────────
        self.ruler.background  = QColor("#0A070A")
        self.ruler.background2 = QColor("#3C3C3C")
        self.ruler.font_color  = QColor("#C9C9C9")

        # ── Icons ─────────────────────────────────────────────────────────
        _h = "themes/humanity/images/"

        self.track_keyframe_panel_disabled_icon = _icon(_h + "retro-track-keyframe-panel-show-disabled.svg")
        self.track_keyframe_panel_enabled_icon  = _icon(_h + "retro-track-keyframe-panel-show-enabled.svg")
        self.keyframe_panel_add_icon            = _icon(_h + "keyframe-panel-add.svg")
        self.track_locked_disabled_icon         = _icon(_h + "retro-track-locked-disabled.svg")
        self.track_locked_enabled_icon          = _icon(_h + "retro-track-locked-enabled.svg")
        self.track_unlocked_disabled_icon       = _icon(_h + "retro-track-unlocked-disabled.svg")
        self.track_unlocked_enabled_icon        = _icon(_h + "retro-track-unlocked-enabled.svg")

        self.keyframe_toggle_off_icon = self.track_keyframe_panel_disabled_icon
        self.keyframe_toggle_on_icon  = self.track_keyframe_panel_enabled_icon
