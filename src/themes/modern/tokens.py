# Design tokens for the Modern Theme
# Centralizes colors, radii, spacing, and fonts for both QSS and Timeline painting.

palette = {
    # Elevation levels
    "window_bg": "#141820",     # Base bg
    "surface_bg": "#1A1F29",    # Panel bg
    "control_bg": "#232A36",    # Control bg
    
    # Inner borders / splitters
    "border_subtle": "#2A3140", 
    "border_highlight": "#384254", # 1px inner highlights
    
    # Text
    "text_primary": "#E8EAED",
    "text_secondary": "#8B95A5", # Dimmed labels
    
    # One single accent hue
    "accent": "#0078FF", 
    
    # Selection and Hover
    "hover_bg": "#2A3140",
    "selected_bg": "#004B99", # Darker accent for selections

    # Timeline specific
    "playhead": "#0078FF",
    "clip_bg": "#1A1F29",
    "clip_border": "#2A3140",
    "track_bg": "#141820",
    "ruler_bg": "#141820",
}

typography = {
    "font_family": "Ubuntu", # Default to system/Ubuntu for now
    "base_size": "13px",     # Controls
    "title_size": "15px",    # Panel titles
    "caption_size": "11px",  # Labels, slightly tracked, dimmed
}

spacing = {
    "panel_radius": "4px",
    "button_radius": "4px",
    "input_radius": "4px",
    "grid_4": "4px",
    "grid_8": "8px",
    "control_height": "28px",
}
