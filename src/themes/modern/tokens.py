# Design tokens for the Modern Theme
# Centralizes colors, radii, spacing, and fonts for both QSS and Timeline painting.

palette = {
    # 4-tier surface elevation (from reference design)
    "window_bg": "#0E1116",      # bg-0 app/canvas
    "surface_bg": "#151A22",     # bg-1 panels
    "control_bg": "#1C2230",     # bg-2 inputs/controls
    "hover_bg": "#232A3A",       # bg-3 hover/raised
    "panel_hdr": "#10141B",      # panel header strips (darker than panels)

    # hairline borders (white-alpha pre-blended over bg-1)
    "border_subtle": "#232830",     # line-1
    "border_highlight": "#2C3138",  # line-2
    "border_strong": "#3A3F45",     # line-3

    # 4-tier text
    "text_primary": "#E7ECF3",
    "text_secondary": "#A9B2C0",
    "text_tertiary": "#6B7688",
    "text_disabled": "#4B5464",

    # accent — one hue
    "accent": "#4C8DFF",
    "accent_hi": "#6BA3FF",
    "accent_dim": "#1F2F4A",     # 18% accent over bg-1 (selection fills)
    "accent_line": "#33599B",    # 55% accent over bg-1 (focus borders)

    # signal colors
    "ok": "#4EC28A",
    "warn": "#E5A24B",
    "err": "#E5695B",

    # CTA is flat accent now (no gradient)
    "cta_gradient_start": "#4C8DFF",
    "cta_gradient_end": "#4C8DFF",

    # selection / hover
    "selected_bg": "#1F2F4A",

    # timeline canvas
    "playhead": "#6BA3FF",
    "clip_bg": "#232A3A",
    "clip_border": "#4C8DFF",
    "track_bg": "#0E1116",
    "ruler_bg": "#10141B",
}

typography = {
    "font_family": "Inter",
    "mono_family": "IBM Plex Mono",
    "base_size": "13px",
    "title_size": "11px",     # panel titles: uppercase, tracked (styled in QSS)
    "caption_size": "11px",
}

spacing = {
    "panel_radius": "6px",
    "button_radius": "6px",
    "input_radius": "6px",
    "radius_small": "3px",
    "grid_4": "4px",
    "grid_8": "8px",
    "grid_12": "12px",
    "control_height": "28px",
    "header_height": "32px",
    "status_height": "24px",
}
