import os

with open("/Users/safwan/Code/Video/Openshot/repo_openshot_qt/src/themes/modern/styles.py", "r") as f:
    content = f.read()

# Add tokens import
content = content.replace("from windows.views.timeline_backend.theme import _icon", "from windows.views.timeline_backend.theme import _icon\nfrom themes.modern import tokens")

# Rename CosmicDuskTimelineTheme to ModernTimelineTheme
content = content.replace("CosmicDuskTimelineTheme", "ModernTimelineTheme")
content = content.replace("Cosmic Dusk timeline theme.", "Modern timeline theme.")
content = content.replace('themes/cosmic/images/', 'themes/modern/images/')
content = content.replace('_c = "themes/cosmic/images/"', '_c = "themes/modern/images/"')

# Color replacements
# #141923 -> track_bg / ruler_bg etc. Let's just use tokens.palette["window_bg"] for most
content = content.replace('QColor("#141923")', 'QColor(tokens.palette["window_bg"])')
content = content.replace('QColor("#192332")', 'QColor(tokens.palette["clip_bg"])')
content = content.replace('QColor("#0078FF")', 'QColor(tokens.palette["accent"])')
content = content.replace('QColor("#283241")', 'QColor(tokens.palette["track_bg"])')
content = content.replace('QColor("#FABE0A")', 'QColor(tokens.palette["playhead"])')

with open("/Users/safwan/Code/Video/Openshot/repo_openshot_qt/src/themes/modern/styles.py", "w") as f:
    f.write(content)
