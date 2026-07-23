# Design tokens for the Modern Theme
# Centralizes colors, radii, spacing, and fonts for both QSS and Timeline painting.

palette = {
    "window_bg": "#0E1116",
    "surface_bg": "#181C23",
    "border_subtle": "#2A2F3A",
    "text_primary": "#E8EAED",
    "text_secondary": "#9AA3B2",
    "accent": "#7FB8FF",
    "cta_gradient_start": "#0078FF", # Fallback gradient colors
    "cta_gradient_end": "#00C6FF",
    
    # Selection and Hover
    "hover_bg": "#222733",
    "selected_bg": "#1A2E4C",

    # Timeline specific
    "playhead": "#7FB8FF",
    "clip_bg": "#181C23",
    "clip_border": "#2A2F3A",
    "track_bg": "#0E1116",
    "ruler_bg": "#0E1116",
}

typography = {
    "font_family": "Ubuntu",
    "base_size": "10pt",
    "title_size": "13px",
    "caption_size": "9pt",
}

spacing = {
    "panel_radius": "12px",
    "button_radius": "16px",
    "input_radius": "8px",
    "padding_small": "4px",
    "padding_medium": "8px",
    "padding_large": "16px",
}
