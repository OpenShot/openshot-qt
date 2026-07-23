import re
import os

with open("/Users/safwan/Code/Video/Openshot/repo_openshot_qt/src/themes/modern/theme.py", "r") as f:
    content = f.read()

# Rename CosmicTheme to ModernTheme
content = content.replace("class CosmicTheme(BaseTheme):", "from themes.modern import tokens\n\nclass ModernTheme(BaseTheme):")

# Fix CosmicTheme references
content = content.replace("CosmicTheme", "ModernTheme")
content = content.replace("themes/cosmic/", "themes/modern/")

# Let's replace the whole self.style_sheet assignment
# We'll extract everything between `self.style_sheet = """` and `"""\n        path_unix_slashes`
start_idx = content.find('self.style_sheet = """')
end_idx = content.find('"""\n        path_unix_slashes')

qss = content[start_idx + len('self.style_sheet = """'):end_idx]

# Replace colors
color_map = {
    "#192332": '{tokens.palette["window_bg"]}',
    "#141923": '{tokens.palette["surface_bg"]}',
    "#91C3FF": '{tokens.palette["text_primary"]}',
    "#9bb2cc": '{tokens.palette["text_secondary"]}',
    "#0078FF": '{tokens.palette["accent"]}',
    "#283241": '{tokens.palette["hover_bg"]}',
    "#323C50": '{tokens.palette["selected_bg"]}',
    "#121212": '{tokens.palette["surface_bg"]}',
    "#006EE6": '{tokens.palette["cta_gradient_start"]}',
    "#1a86ff": '{tokens.palette["cta_gradient_end"]}',
    "#ffffff": '{tokens.palette["text_primary"]}',
    "#FFFFFF": '{tokens.palette["text_primary"]}',
}

for old, new in color_map.items():
    qss = qss.replace(old, new)

# Phase 1: Typography
qss += """
/* Typography Scales */
QWidget { font-family: {tokens.typography["font_family"]}; font-size: {tokens.typography["base_size"]}; }
QLabel#dock-title-label { font-size: {tokens.typography["title_size"]}; font-weight: bold; }
QLabel#lblMissingFileHint { font-size: {tokens.typography["caption_size"]}; }
"""

# Phase 2 QSS overrides
qss += """
/* Phase 2: Modernization */
QDockWidget QWidget {
    border-radius: {tokens.spacing["panel_radius"]};
}

QPushButton {
    border-radius: {tokens.spacing["button_radius"]};
}

QPushButton#acceptButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {tokens.palette["cta_gradient_start"]}, stop:1 {tokens.palette["cta_gradient_end"]});
    border-radius: {tokens.spacing["button_radius"]};
    color: white;
}

QTabWidget::pane {
    border-radius: {tokens.spacing["panel_radius"]};
}

QTabBar::tab {
    border-radius: 10px;
    padding: 6px 12px;
    margin: 2px;
}
QTabBar::tab:selected {
    background-color: {tokens.palette["selected_bg"]};
}

QScrollBar:vertical {
    width: 6px;
}
QScrollBar::handle:vertical {
    border-radius: 3px;
}
QScrollBar:horizontal {
    height: 6px;
}
QScrollBar::handle:horizontal {
    border-radius: 3px;
}
"""

new_qss_assignment = f'self.style_sheet = f"""{qss}"""\n        path_unix_slashes'
content = content[:start_idx] + new_qss_assignment + content[end_idx + len('"""\n        path_unix_slashes'):]

# Replace the f-string concat below
content = content.replace("self.style_sheet = f\"\"\"\nQMessageBox", "self.style_sheet = f\"\"\"\nQMessageBox")

# Phase 1 Typography font setting
content = content.replace('font.setPointSizeF(8)', 'font.setPointSizeF(10)')

with open("/Users/safwan/Code/Video/Openshot/repo_openshot_qt/src/themes/modern/theme.py", "w") as f:
    f.write(content)
