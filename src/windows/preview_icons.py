"""Reuse Cosmic artwork at the preview's semantic accent colors."""
import os
import re
from qt_api import Qt, QIcon, QPixmap, QPainter, QSvgRenderer, QByteArray
from classes import info
from qt_api import QApplication

START_COLOR = '#36c644'
END_COLOR = '#ff771c'
ACCENT_COLOR = '#0088ff'


def preview_icon(name, color=None):
    path = os.path.join(info.PATH, 'themes', 'cosmic', 'images', name + '.svg')
    if color is None:
        color = QApplication.palette().text().color().name()
    with open(path, 'r', encoding='utf-8') as source:
        svg = re.sub(r'#[0-9a-fA-F]{6}', color, source.read())
        svg = svg.replace('"white"', '"%s"' % color).replace('"black"', '"%s"' % color)
    renderer = QSvgRenderer(QByteArray(svg.encode('utf-8')))
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def preview_colors():
    """Preserve the preview's established styling with theme-specific colors."""
    from classes.app import get_app
    app = get_app()
    manager = getattr(app, 'theme_manager', None)
    theme = manager.get_current_theme() if manager else None
    if getattr(theme, 'name', '') == 'Cosmic Dusk':
        return dict(window='#09151e', window_end='#111f2c', panel='#101d29',
                    panel_end='#152333', field='#0b1722', border='#26394b',
                    text='#e5edff', muted='#afc6e8', button='#233244',
                    button_end='#202c3b', hover='#2b4059', accent='#007bff',
                    accent_hover='#1892ff', on_accent='#ffffff', grip='#e2f4ff')
    palette = QApplication.palette()
    base = palette.window().color()
    text = palette.text().color()
    # Subtle container outlines, without changing the established visual weight.
    from qt_api import QColor
    border = QColor(*[round(a*.8+b*.2) for a, b in zip(
        (base.red(), base.green(), base.blue()), (text.red(), text.green(), text.blue()))])
    field_base = palette.base().color()
    field = QColor(*[round(a*.8+b*.2) for a, b in zip(
        (base.red(), base.green(), base.blue()),
        (field_base.red(), field_base.green(), field_base.blue()))])
    colors = dict(window=base.name(), window_end=base.name(),
                panel=base.name(), panel_end=base.name(), field=field.name(),
                border=border.name(), text=text.name(), muted=text.name(),
                button=palette.button().color().name(), button_end=palette.button().color().name(),
                hover=palette.alternateBase().color().name(), accent=palette.highlight().color().name(),
                accent_hover=palette.highlight().color().lighter(115).name(),
                on_accent='#ffffff' if palette.highlight().color().lightness() < 160 else '#111111',
                grip=text.name())
    if getattr(theme, 'name', '') == 'Retro':
        colors.update(range_grip='#d8eaff', range_grip_detail='#007bff',
                      range_grip_active='#007bff', range_grip_active_detail='#ffffff')
    return colors


def preview_toggle_icon(name, active_when_checked=True):
    """Indicate toggle state through icon color, without button decorations."""
    colors = preview_colors()
    icon = QIcon()
    off, on = (colors['text'], colors['accent']) if active_when_checked else (colors['accent'], colors['text'])
    for state, color in ((QIcon.Off, off), (QIcon.On, on)):
        pixmap = preview_icon(name, color).pixmap(64, 64)
        for mode in (QIcon.Normal, QIcon.Active):
            icon.addPixmap(pixmap, mode, state)
    return icon
