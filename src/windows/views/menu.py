"""
 @file
 @brief This file creates a styled QMenu (which supports border radius and border color)
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

from classes.easing import keyframe_bezier_presets as shared_bezier_presets

import logging
import re
import functools

from qt_api import QMenu, isdeleted
from qt_api import (QPainter, QPen, QColor, QLabel, QFontMetrics, QToolButton,
                    QStyleOptionToolButton, QStylePainter, QStyle, QIcon, QSize, QRect, QPalette)
from qt_api import Qt, QRectF
from classes.app import get_app


logger = logging.getLogger(__name__)


class StyledContextMenu(QMenu):
    def __init__(self, title=None, parent=None):
        super().__init__(title, parent)
        self.app = get_app()
        self.border = self.get_border()
        self.border_radius = self.get_border_radius()

    def show_at(self, event_or_pos):
        """Show the menu at a position or context menu event."""
        pos = event_or_pos
        if hasattr(event_or_pos, "globalPosition"):
            try:
                pos = event_or_pos.globalPosition().toPoint()
            except Exception:
                pos = event_or_pos
        if hasattr(event_or_pos, "globalPos"):
            try:
                pos = event_or_pos.globalPos()
            except Exception:
                pos = event_or_pos
        exec_fn = getattr(self, "exec", None) or getattr(self, "exec_", None)
        if exec_fn:
            try:
                exec_fn(pos)
            finally:
                if self.objectName() == "timelineObjectMenu":
                    self.deleteLater()
        else:
            self.popup(pos)

    def get_border(self):
        """Parses border width and color from app.styleSheet()"""
        pattern = r'QMenu\s*{\s*[^}]*border:\s*([^;]+);'
        match = re.search(pattern, self.app.styleSheet(), re.IGNORECASE)
        if match:
            border_parts = match.group(1).split()
            # Typically, border is defined as width style color
            if len(border_parts) >= 3:
                width = float(border_parts[0].replace('px', ''))  # Remove 'px' and convert to float
                style = border_parts[1]
                color = QColor(border_parts[2])
                return {'width': width, 'style': style, 'color': color}
        return None

    def get_border_radius(self):
        """Parses border radius from app.styleSheet()"""
        pattern = r'QMenu\s*{\s*[^}]*border-radius:\s*([^;]+);'
        match = re.search(pattern, self.app.styleSheet(), re.IGNORECASE)
        if match:
            # Split the radius values by whitespace and remove 'px' unit
            radius_values = match.group(1).replace('px', '').split()
            if len(radius_values) == 1:
                radius = float(radius_values[0])
                return {'x': radius, 'y': radius}
            if len(radius_values) == 2:
                return {'x': float(radius_values[0]), 'y': float(radius_values[1])}
        return None

    def paintEvent(self, event):
        """Paint optional borders and corner radius on QMenu"""
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.border:
            pen = QPen(self.border.get('color'), self.border.get('width'))
            painter.setPen(pen)

        if self.border_radius:
            rect = QRectF(0, 0, self.width(), self.height())
            painter.drawRoundedRect(rect, self.border_radius.get('x'), self.border_radius.get('y'), Qt.AbsoluteSize)

        painter.end()


def _resolve_live_owner(owner):
    """Resolve a live QObject owner for menu action metadata/trigger lookup."""
    if owner is None:
        return get_app().window
    try:
        if not isdeleted(owner):
            return owner
    except Exception:
        return get_app().window
    return get_app().window


def add_bound_action(menu, owner, action_name, fallback_text, callback=None, enabled=None):
    """Add a fresh menu-owned action and resolve the current slot at trigger time."""
    owner = _resolve_live_owner(owner)
    source_action = getattr(owner, action_name, None)
    label = fallback_text
    icon = None
    if source_action is not None:
        try:
            if not isdeleted(source_action):
                label = source_action.text() or fallback_text
                icon = source_action.icon()
                if enabled is None:
                    enabled = source_action.isEnabled()
        except Exception as exc:
            logger.debug("menu: failed to read source action metadata for %s: %s", action_name, exc, exc_info=True)
    action = menu.addAction(icon, label) if icon and not icon.isNull() else menu.addAction(label)
    if enabled is not None:
        action.setEnabled(bool(enabled))

    def trigger_slot():
        live_owner = _resolve_live_owner(owner)
        live_callback = callback
        if isinstance(callback, str):
            live_callback = getattr(live_owner, callback, None)
        if live_callback is None:
            live_callback = getattr(live_owner, f"{action_name}_trigger", None)
        if live_callback is None:
            raise AttributeError(f"Unable to resolve callback for {action_name}")
        live_callback()

    action.triggered.connect(lambda checked=False: trigger_slot())
    return action


def keyframe_bezier_presets():
    return shared_bezier_presets(get_app()._tr)


def populate_keyframe_context_menu(
    menu,
    *,
    bezier_callback,
    linear_callback,
    constant_callback,
    remove_callback=None,
    remove_enabled=True,
    bezier_icon=None,
    linear_icon=None,
    constant_icon=None,
    remove_text=None,
):
    _ = get_app()._tr

    bez_menu = menu.addMenu(bezier_icon, _("Bezier")) if bezier_icon else menu.addMenu(_("Bezier"))
    for preset in keyframe_bezier_presets():
        action = bez_menu.addAction(preset[4])
        action.triggered.connect(functools.partial(bezier_callback, preset))

    linear_action = menu.addAction(linear_icon, _("Linear")) if linear_icon else menu.addAction(_("Linear"))
    linear_action.triggered.connect(linear_callback)

    constant_action = menu.addAction(constant_icon, _("Constant")) if constant_icon else menu.addAction(_("Constant"))
    constant_action.triggered.connect(constant_callback)

    if remove_callback is not None:
        menu.addSeparator()
        remove_action = menu.addAction(remove_text or _("Remove Keyframe"))
        remove_action.setEnabled(bool(remove_enabled))
        remove_action.triggered.connect(remove_callback)
        return remove_action
    return None


def context_icon(menu, name, color_override=None):
    """Keep the shared SVGs vector-based and recolor them for the current theme."""
    import hashlib
    import os
    from pathlib import Path
    from classes import info
    from qt_api import QIcon
    owner = menu.parentWidget()
    theme = getattr(owner, "theme", None)
    color = (QColor(color_override) if color_override is not None else
             QColor(theme.track_control_color) if theme else menu.palette().color(menu.foregroundRole()))
    cache = getattr(menu, "_context_icons", {})
    key = (name, color.rgba())
    if key not in cache:
        source = Path(info.PATH) / "themes/common/icons" / ("menu-" + name + ".svg")
        svg = source.read_bytes().replace(b"#000000", color.name().encode("ascii"))
        # A file-backed SVG icon lets Qt render at the actual display scale,
        # instead of resampling a fixed-resolution bitmap at fractional DPI.
        folder = Path(info.CACHE_PATH) / "menu-icons"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / (hashlib.sha256(svg).hexdigest() + ".svg")
        if not target.exists():
            temporary = target.with_suffix(".%s.tmp" % os.getpid())
            temporary.write_bytes(svg)
            os.replace(temporary, target)
        cache[key] = QIcon(str(target))
        menu._context_icons = cache
    return cache[key]


def style_object_menu(menu):
    """Keep object menus and their submenus calm and consistent in every theme."""
    menu.setObjectName("timelineObjectMenu")
    owner = menu.parentWidget()
    theme = getattr(owner, "theme", None)
    if theme:
        border = theme.track.border_color.name()
        hover = theme.track.border_color.lighter(115).name()
        menu.setStyleSheet(
            "QMenu#timelineObjectMenu { padding: 6px 10px; } "
            "QMenu#timelineObjectMenu::item { padding: 6px 12px; } "
            "QMenu#timelineObjectMenu::icon { padding-left: 8px; } "
            "QMenu#timelineObjectMenu::item:selected { background: %s; } "
            "QMenu#timelineObjectMenu::separator { height: 1px; margin: 4px 0px; background: %s; }"
            % (hover, border))
    children = [action.menu() for action in menu.actions() if action.menu()]
    children.extend(button.menu() for button in menu.findChildren(QToolButton) if button.menu())
    seen = set()
    for child in children:
        if id(child) in seen:
            continue
        seen.add(id(child))
        if child.parentWidget() is not menu:
            child.setParent(menu, child.windowFlags())
        style_object_menu(child)


class _ContextTitleLabel(QLabel):
    def __init__(self, title, parent):
        super().__init__(title, parent)
        self._full_title = title
        self.setTextFormat(Qt.PlainText)
        self.setToolTip(title)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setText(QFontMetrics(self.font()).elidedText(
            self._full_title, Qt.ElideRight, self.contentsRect().width()))


def add_context_heading(menu, title, preview=None):
    from qt_api import QWidget, QWidgetAction, QHBoxLayout, QLabel, QSizePolicy
    header = QWidget(menu)
    header.setObjectName("objectMenuHeading")
    theme = getattr(menu.parentWidget(), "theme", None)
    hover = theme.track.border_color.lighter(115).name() if theme else menu.palette().color(menu.backgroundRole()).name()
    header.setStyleSheet(
        "QWidget#objectMenuHeading { border: none; padding: 0; } "
        "QLabel { padding: 0; border: none; } "
        "QToolButton { border: none; padding: 3px 6px; margin: 0; background: transparent; border-radius: 3px; } "
        "QToolButton:hover { background: %s; }" % hover)
    layout = QHBoxLayout(header)
    layout.setContentsMargins(8, 4, 8, 4)
    label = _ContextTitleLabel(title, header)
    label.setToolTip(title)
    label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    label.setMinimumWidth(80)
    layout.addWidget(label, 1)
    if preview:
        button = _context_button(header, preview, menu)
        layout.addWidget(button)
    action = QWidgetAction(menu)
    action.setObjectName("objectMenuHeadingAction")
    action.setDefaultWidget(header)
    menu.addAction(action)
    menu.addSeparator()


class _ContextButton(QToolButton):
    """Align icons, labels and inline chevrons independently of native menu arrows."""
    def sizeHint(self):
        size = super().sizeHint()
        metrics = QFontMetrics(self.font())
        text_width = metrics.boundingRect(self.text().replace("&", "")).width()
        width = 16 + (22 if not self.icon().isNull() and not getattr(self, "_text_only", False) else 0) + text_width + (14 if self.menu() else 0)
        return QSize(max(size.width(), width), max(size.height(), metrics.height() + 10))

    def paintEvent(self, event):
        option = QStyleOptionToolButton()
        self.initStyleOption(option)
        option.text = ""
        option.icon = QIcon()
        features = getattr(QStyleOptionToolButton, "ToolButtonFeature", QStyleOptionToolButton)
        option.features &= ~features.HasMenu
        painter = QStylePainter(self)
        controls = getattr(QStyle, "ComplexControl", QStyle)
        painter.drawComplexControl(controls.CC_ToolButton, option)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(8, 0, -8, 0)
        left = rect.left()
        if not self.icon().isNull() and not getattr(self, "_text_only", False):
            modes = getattr(QIcon, "Mode", QIcon)
            self.icon().paint(painter, QRect(left, (self.height() - 16) // 2, 16, 16),
                              Qt.AlignCenter, modes.Normal if self.isEnabled() else modes.Disabled)
            left += 22
        roles = getattr(QPalette, "ColorRole", QPalette)
        groups = getattr(QPalette, "ColorGroup", QPalette)
        color = option.palette.color(groups.Active if self.isEnabled() else groups.Disabled, roles.ButtonText)
        painter.setPen(color)
        label = self.text().replace("&", "")
        metrics = QFontMetrics(self.font())
        room = max(0, rect.right() - left - (14 if self.menu() else 0))
        label = metrics.elidedText(label, Qt.ElideRight, room)
        if getattr(self, "_text_only", False):
            group_width = metrics.boundingRect(label).width() + (14 if self.menu() else 0)
            left = max(rect.left(), round(rect.center().x() - group_width / 2))
        painter.drawText(QRect(left, 0, room, self.height()), Qt.AlignLeft | Qt.AlignVCenter, label)
        if self.menu():
            x = left + metrics.boundingRect(label).width() + 7
            y = self.height() / 2.0
            painter.setPen(QPen(color, 1.3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            from qt_api import QPointF
            painter.drawLine(QPointF(x, y - 1.5), QPointF(x + 3, y + 1.5))
            painter.drawLine(QPointF(x + 3, y + 1.5), QPointF(x + 6, y - 1.5))


def add_context_remove(menu, action):
    """Use a subdued destructive color without changing the shared action."""
    from qt_api import QWidgetAction
    theme = getattr(menu.parentWidget(), "theme", None)
    dark = theme.track.name_background.lightness() < 128 if theme else True
    red = "#DF9494" if dark else "#AA4040"
    action.setIcon(context_icon(menu, "remove", red))
    button = _context_button(menu, action, menu)
    button.setObjectName("contextRemoveButton")
    hover = theme.track.border_color.lighter(115).name() if theme else "#555555"
    button.setStyleSheet(
        "QToolButton#contextRemoveButton { color: %s; background: transparent; border: none; "
        "padding: 6px 8px; margin: 0; border-radius: 3px; } "
        "QToolButton#contextRemoveButton:hover { background: %s; } "
        "QToolButton#contextRemoveButton:disabled { color: #808080; }" % (red, hover))
    wrapper = QWidgetAction(menu)
    wrapper.setText(action.text())
    wrapper.setEnabled(action.isEnabled())
    wrapper.setDefaultWidget(button)
    wrapper.triggered.connect(action.trigger)
    menu.addAction(wrapper)
    return wrapper


def _context_button(parent, action, menu):
    import weakref
    from qt_api import QToolButton, QSizePolicy
    button = _ContextButton(parent)
    button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    button.setFocusPolicy(Qt.StrongFocus)
    button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    button._context_action = action
    if action.menu():
        button.setText(action.text())
        button.setIcon(action.icon())
        button.setEnabled(action.isEnabled())
        button.setMenu(action.menu())
        button.setPopupMode(getattr(QToolButton, "ToolButtonPopupMode", QToolButton).InstantPopup)
    else:
        button.setDefaultAction(action)
        menu_ref = weakref.ref(menu)
        def close_menu(_checked=False):
            live_menu = menu_ref()
            if live_menu is not None:
                live_menu.close()
        button.clicked.connect(close_menu)
    return button


def add_context_action_row(menu, actions):
    from qt_api import QWidget, QWidgetAction, QHBoxLayout, QFrame
    row = QWidget(menu)
    row.setObjectName("objectMenuActionRow")
    owner = menu.parentWidget()
    theme = getattr(owner, "theme", None)
    border = theme.track.border_color.name() if theme else "#777777"
    hover = QColor(border).lighter(115).name()
    row.setStyleSheet(
        "QWidget#objectMenuActionRow { border: none; padding: 0; } "
        "QToolButton { border: none; margin: 0; padding: 4px 8px; background: transparent; border-radius: 3px; } "
        "QToolButton:hover { background: %s; } "
        "QFrame { border: none; padding: 0; background: %s; }" % (hover, border))
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 2, 0, 2)
    layout.setSpacing(4)
    for action in actions:
        if layout.count():
            divider = QFrame(row)
            divider.setFixedWidth(1)
            layout.addWidget(divider)
        button = _context_button(row, action, menu)
        button._text_only = True
        layout.addWidget(button, 1)
    wrapper = QWidgetAction(menu)
    wrapper.setObjectName("objectMenuActionRowAction")
    wrapper.setDefaultWidget(row)
    menu.addAction(wrapper)
    return wrapper
