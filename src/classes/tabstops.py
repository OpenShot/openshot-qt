"""
 @file
 @brief Auto-assign tab order based on on-screen widget geometry.
"""

from qt_api import Qt, QPoint, QTimer, isdeleted
from qt_api import (
    QWidget,
    QLayout,
    QToolBar,
    QToolButton,
    QMenuBar,
    QMainWindow,
    QTabBar,
    QDockWidget,
    QLineEdit,
    QTextEdit,
    QPlainTextEdit,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
)


def _parent_dock_widget(widget):
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QDockWidget):
            return parent
        parent = parent.parentWidget()
    return None


def _dock_uses_auto_tab_order(dock):
    if dock is None:
        return True
    return not bool(dock.property("_skip_auto_tab_order"))


def _find_dock_tab_bars(root):
    """Find tab bars that contain dock widget titles and return mapping of dock titles to active status."""
    if not isinstance(root, QMainWindow):
        return {}

    dock_titles = {dock.windowTitle() for dock in root.findChildren(QDockWidget)}
    active_tabs = {}  # dock_title -> is_active

    for tab_bar in root.findChildren(QTabBar):
        if tab_bar.count() < 2:
            continue
        tabs = [tab_bar.tabText(i) for i in range(tab_bar.count())]
        # Check if this tab bar contains dock titles
        matching_titles = [t for t in tabs if t in dock_titles]
        if len(matching_titles) < 2:
            continue
        # This is a dock tab bar - mark which dock is active
        active_title = tab_bar.tabText(tab_bar.currentIndex())
        for title in matching_titles:
            active_tabs[title] = (title == active_title)

    return active_tabs


def _dock_is_active(root, dock, active_tabs=None):
    if dock is None:
        return True
    if not isinstance(root, QMainWindow):
        return dock.isVisibleTo(root)

    if dock.isFloating():
        return dock.isVisibleTo(root)

    if not dock.isVisibleTo(root):
        return False

    dock_title = dock.windowTitle()

    # If we have pre-computed active tabs info, use it
    if active_tabs is not None and dock_title in active_tabs:
        return active_tabs[dock_title]

    # Fallback: check tab bars directly
    for tab_bar in root.findChildren(QTabBar):
        if tab_bar.count() < 2:
            continue
        tabs = [tab_bar.tabText(i) for i in range(tab_bar.count())]
        if dock_title not in tabs:
            continue
        active_title = tab_bar.tabText(tab_bar.currentIndex())
        return active_title == dock_title

    return dock.isVisibleTo(root)


def _is_focusable(widget, root, include_hidden, include_disabled):
    if isdeleted(widget) or (root is not None and isdeleted(root)):
        return False
    if widget is root:
        return False
    if isinstance(widget, QToolBar):
        return False
    if widget.focusPolicy() == Qt.NoFocus:
        return False
    dock = _parent_dock_widget(widget)
    if dock is not None and not _dock_uses_auto_tab_order(dock):
        return False
    if dock is not None and not _dock_is_active(root, dock):
        return False
    if not include_hidden and not widget.isVisibleTo(root):
        return False
    if not include_disabled and not widget.isEnabled():
        return False
    return True


def safe_set_tab_order(first, second):
    """Set tab order only when both widgets share the same window."""
    if first is None or second is None:
        return
    try:
        if first.window() is not second.window():
            return
    except RuntimeError:
        return
    QWidget.setTabOrder(first, second)


def _position_key(widget, root, fallback_index, row_tolerance):
    try:
        pos = widget.mapTo(root, QPoint(0, 0))
        x, y = pos.x(), pos.y()
    except Exception:
        x = y = 0

    if widget.size().isEmpty():
        parent = widget.parentWidget()
        if parent is not None:
            try:
                parent_pos = parent.mapTo(root, QPoint(0, 0))
                x, y = parent_pos.x(), parent_pos.y()
            except Exception:
                x = y = 0

    if row_tolerance and row_tolerance > 0:
        row = int((y + (row_tolerance / 2)) // row_tolerance)
    else:
        row = y

    return (row, x, y, fallback_index)


def _prepare_main_window(root):
    """Configure MainWindow and its menubar focus policies."""
    if not isinstance(root, QMainWindow):
        return
    if root.focusPolicy() != Qt.NoFocus:
        root.setFocusPolicy(Qt.NoFocus)
    menubar = root.menuBar()
    if menubar is not None and menubar.focusPolicy() == Qt.NoFocus:
        menubar.setFocusPolicy(Qt.StrongFocus)


def _prepare_tab_bars(root):
    """Configure tab bar focus policies."""
    for tab_bar in root.findChildren(QTabBar):
        if tab_bar.count() < 2:
            tab_bar.setFocusPolicy(Qt.NoFocus)
        elif tab_bar.focusPolicy() == Qt.NoFocus:
            tab_bar.setFocusPolicy(Qt.StrongFocus)


def _prepare_toolbars(root):
    """Configure toolbar widget focus policies."""
    focusable_types = (
        QToolButton, QLineEdit, QTextEdit, QPlainTextEdit,
        QComboBox, QSpinBox, QDoubleSpinBox,
    )
    for toolbar in root.findChildren(QToolBar):
        for action in toolbar.actions():
            widget = toolbar.widgetForAction(action)
            if widget is not None and isinstance(widget, focusable_types):
                if widget.focusPolicy() == Qt.NoFocus:
                    widget.setFocusPolicy(Qt.StrongFocus)
        for button in toolbar.findChildren(QToolButton):
            if button.focusPolicy() == Qt.NoFocus:
                button.setFocusPolicy(Qt.StrongFocus)


def _prepare_menubars(root):
    """Configure menubar focus policies."""
    for menubar in root.findChildren(QMenuBar):
        if menubar.focusPolicy() == Qt.NoFocus:
            menubar.setFocusPolicy(Qt.StrongFocus)


def _prepare_focusable_containers(root):
    """Ensure menubars/toolbars/actions are eligible for focus and tab order."""
    if root is None:
        return
    _prepare_main_window(root)
    _prepare_tab_bars(root)
    _prepare_toolbars(root)
    _prepare_menubars(root)


_TOOLBAR_FOCUSABLE_TYPES = (
    QToolButton,
    QLineEdit,
    QTextEdit,
    QPlainTextEdit,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
)


def _process_toolbar_action_widget(widget, widgets, overflow_buttons):
    """Process a single toolbar action widget, sorting into regular or overflow."""
    if widget is None:
        return
    if isinstance(widget, _TOOLBAR_FOCUSABLE_TYPES):
        if widget.focusPolicy() == Qt.NoFocus:
            widget.setFocusPolicy(Qt.StrongFocus)
    elif widget.focusPolicy() == Qt.NoFocus:
        return
    if isinstance(widget, QToolButton) and widget.objectName() == "qt_toolbar_ext_button":
        overflow_buttons.append(widget)
    else:
        widgets.append(widget)


def _collect_overflow_buttons(toolbar, widgets, overflow_buttons):
    """Find overflow buttons that may not be in the actions list."""
    for ext_button in toolbar.findChildren(QToolButton):
        if ext_button.objectName() != "qt_toolbar_ext_button":
            continue
        if ext_button in widgets or ext_button in overflow_buttons:
            continue
        if ext_button.focusPolicy() == Qt.NoFocus:
            ext_button.setFocusPolicy(Qt.StrongFocus)
        overflow_buttons.append(ext_button)


def _collect_toolbar_button_groups(root, scope=None):
    groups = []
    if root is None:
        return groups

    if scope is None:
        toolbars = [
            tb for tb in root.findChildren(QToolBar)
            if _parent_dock_widget(tb) is None
        ]
    else:
        toolbars = scope.findChildren(QToolBar)

    for index, toolbar in enumerate(toolbars):
        widgets = []
        overflow_buttons = []
        for action in toolbar.actions():
            _process_toolbar_action_widget(
                toolbar.widgetForAction(action), widgets, overflow_buttons
            )
        _collect_overflow_buttons(toolbar, widgets, overflow_buttons)
        widgets.extend(overflow_buttons)
        if widgets:
            groups.append((_position_key(toolbar, root, index, 8), widgets))
    groups.sort(key=lambda item: item[0])
    return [group[1] for group in groups]


def _collect_menu_bars(root):
    if root is None:
        return []
    menubars = []
    if isinstance(root, QMainWindow):
        menubar = root.menuBar()
        if menubar is not None:
            menubars.append(menubar)
    menubars.extend(root.findChildren(QMenuBar))
    return [m for m in menubars if m is not None]

def _dock_tab_bar(root, dock, tabified):
    if root is None or dock is None:
        return None
    if not tabified:
        return None
    dock_title = dock.windowTitle()
    group_titles = [dock_title] + [d.windowTitle() for d in tabified]
    for tab_bar in root.findChildren(QTabBar):
        if tab_bar.count() == 0:
            continue
        tabs = [tab_bar.tabText(i) for i in range(tab_bar.count())]
        if dock_title not in tabs:
            continue
        if not any(title in tabs for title in group_titles):
            continue
        return tab_bar
    return None


def _collect_titlebar_widgets(dock, excluded_widgets):
    """Collect focusable widgets from a dock's titlebar."""
    titlebar_widgets = []
    titlebar = dock.titleBarWidget()
    if titlebar is None:
        return titlebar_widgets
    for widget in titlebar.findChildren(QWidget):
        if widget.focusPolicy() != Qt.NoFocus:
            titlebar_widgets.append(widget)
            excluded_widgets.add(widget)
    return titlebar_widgets


def _process_dock_tab_bar(root, dock, titlebar_widgets, seen_tab_bars, excluded_widgets):
    """Process the tab bar for tabified docks."""
    tabified = root.tabifiedDockWidgets(dock)
    tab_bar = _dock_tab_bar(root, dock, tabified)
    if tab_bar is None or tab_bar in seen_tab_bars:
        return
    seen_tab_bars.add(tab_bar)
    # Include dock tab bar in tab order so users can switch tabs with arrow keys
    if tab_bar.focusPolicy() == Qt.NoFocus:
        tab_bar.setFocusPolicy(Qt.StrongFocus)
    titlebar_widgets.insert(0, tab_bar)
    excluded_widgets.add(tab_bar)


def _collect_dock_content_widgets(dock, content, root, toolbar_widgets,
                                   include_hidden, include_disabled, excluded_widgets):
    """Collect and order focusable widgets from dock content."""
    all_focusables = [
        w for w in content.findChildren(QWidget)
        if _is_focusable(w, root, include_hidden, include_disabled)
    ]
    excluded_widgets.update(all_focusables)

    ordered_content = list(toolbar_widgets)

    # Special handling for properties dock
    if dock.objectName() == "dockProperties":
        for name in ("btnSelectionName", "txtPropertyFilter", "propertyTableView"):
            widget = dock.findChild(QWidget, name)
            if widget and widget not in ordered_content:
                ordered_content.append(widget)

    content_layout = content.layout()
    layout_widgets = (
        collect_focusable_from_layout(
            content_layout, root,
            include_hidden=include_hidden, include_disabled=include_disabled
        ) if content_layout else []
    )

    # Add layout widgets and their focusable children
    for widget in layout_widgets:
        if widget in ordered_content:
            continue
        ordered_content.append(widget)
        for child in widget.findChildren(QWidget):
            if child not in ordered_content and _is_focusable(child, root, include_hidden, include_disabled):
                ordered_content.append(child)

    # Append remaining focusables in geometry order
    remaining = [w for w in all_focusables if w not in ordered_content]
    remaining.sort(key=lambda w: _position_key(w, root, 0, 8))
    ordered_content.extend(remaining)

    # Deduplicate while preserving order
    toolbar_set = set(toolbar_widgets)
    seen = set()
    content_widgets = []
    for widget in ordered_content:
        if widget in seen:
            continue
        seen.add(widget)
        if widget in toolbar_set or _is_focusable(widget, root, include_hidden, include_disabled):
            content_widgets.append(widget)
    return content_widgets


def _collect_dock_groups(root, include_hidden, include_disabled):
    groups = []
    if not isinstance(root, QMainWindow):
        return groups, set()

    seen_tab_bars = set()
    excluded_widgets = set()

    # Pre-compute which docks are active in tab bars
    active_tabs = _find_dock_tab_bars(root)

    for index, dock in enumerate(root.findChildren(QDockWidget)):
        if not _dock_uses_auto_tab_order(dock):
            continue
        if not _dock_is_active(root, dock, active_tabs):
            # Exclude all widgets from inactive docks and disable their focus
            for widget in dock.findChildren(QWidget):
                excluded_widgets.add(widget)
                # Store original focus policy and set to NoFocus so Tab skips them
                if widget.focusPolicy() != Qt.NoFocus:
                    widget.setProperty("_original_focus_policy", widget.focusPolicy())
                    widget.setFocusPolicy(Qt.NoFocus)
            continue

        # Restore focus policy for widgets in active docks
        for widget in dock.findChildren(QWidget):
            original_policy = widget.property("_original_focus_policy")
            if original_policy is not None:
                widget.setFocusPolicy(Qt.FocusPolicy(original_policy))
                widget.setProperty("_original_focus_policy", None)

        titlebar_widgets = _collect_titlebar_widgets(dock, excluded_widgets)
        _process_dock_tab_bar(root, dock, titlebar_widgets, seen_tab_bars, excluded_widgets)

        toolbar_groups = _collect_toolbar_button_groups(root, scope=dock)
        toolbar_widgets = [w for group in toolbar_groups for w in group]
        excluded_widgets.update(toolbar_widgets)

        content = dock.widget()
        if content is not None:
            content_widgets = _collect_dock_content_widgets(
                dock, content, root, toolbar_widgets,
                include_hidden, include_disabled, excluded_widgets
            )
        else:
            content_widgets = []

        group_widgets = titlebar_widgets + content_widgets
        if group_widgets:
            # Use larger row tolerance for docks (100px) so docks on same visual row
            # are grouped together regardless of tab bar height differences
            groups.append((_position_key(dock, root, index, 100), group_widgets))

    groups.sort(key=lambda item: item[0])
    return [group[1] for group in groups], excluded_widgets

def apply_auto_tab_order(root, include_hidden=False, include_disabled=False, row_tolerance=8):
    """Apply top-to-bottom, left-to-right tab order on a widget tree."""
    if root is None:
        return

    _prepare_focusable_containers(root)

    menu_bars = _collect_menu_bars(root)
    toolbar_groups = _collect_toolbar_button_groups(root)
    toolbar_widgets = [w for group in toolbar_groups for w in group]
    dock_groups, dock_excluded = _collect_dock_groups(
        root, include_hidden, include_disabled
    )

    widgets = []
    for index, widget in enumerate(root.findChildren(QWidget)):
        if widget in toolbar_widgets or widget in menu_bars or widget in dock_excluded:
            continue
        if _is_focusable(widget, root, include_hidden, include_disabled):
            widgets.append((widget, index))

    widgets.sort(key=lambda item: _position_key(item[0], root, item[1], row_tolerance))

    ordered_widgets = []
    for menubar in menu_bars:
        if _is_focusable(menubar, root, include_hidden, include_disabled):
            ordered_widgets.append(menubar)
    ordered_widgets.extend(
        [w for w in toolbar_widgets if _is_focusable(w, root, include_hidden, include_disabled)]
    )
    for group in dock_groups:
        ordered_widgets.extend(group)
    ordered_widgets.extend([item[0] for item in widgets])
    for index, widget in enumerate(ordered_widgets):
        try:
            widget._tab_order_key = (index, 0, 0, 0)
        except (AttributeError, RuntimeError):
            pass  # Widget may not support dynamic attributes or may be deleted

    for first, second in zip(ordered_widgets, ordered_widgets[1:]):
        safe_set_tab_order(first, second)


def apply_auto_tab_order_later(root, include_hidden=False, include_disabled=False, row_tolerance=8):
    """Defer tab order assignment until after the event loop runs."""
    QTimer.singleShot(
        0,
        lambda: apply_auto_tab_order(
            root,
            include_hidden=include_hidden,
            include_disabled=include_disabled,
            row_tolerance=row_tolerance,
        ),
    )

def _collect_focusable_from_layout(layout, root, include_hidden, include_disabled):
    if layout is None:
        return []
    widgets = []
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item is None:
            continue
        child_layout = item.layout()
        if child_layout is not None:
            widgets.extend(
                _collect_focusable_from_layout(
                    child_layout, root, include_hidden, include_disabled
                )
            )
            continue
        widget = item.widget()
        if widget is not None and _is_focusable(widget, root, include_hidden, include_disabled):
            widgets.append(widget)
    return widgets


def apply_explicit_tab_order(
    widgets, root=None, include_hidden=False, include_disabled=False
):
    """Apply tab order using an explicit widget list."""
    if root is not None and isdeleted(root):
        return
    ordered = []
    seen = set()
    for widget in widgets:
        if widget is None or widget in seen or isdeleted(widget):
            continue
        target_root = root or widget.window()
        if _is_focusable(widget, target_root, include_hidden, include_disabled):
            ordered.append(widget)
            seen.add(widget)
    for first, second in zip(ordered, ordered[1:]):
        safe_set_tab_order(first, second)


def apply_explicit_tab_order_later(
    widgets, root=None, include_hidden=False, include_disabled=False
):
    """Defer explicit tab order assignment until after the event loop runs."""
    QTimer.singleShot(
        0,
        lambda: apply_explicit_tab_order(
            widgets,
            root=root,
            include_hidden=include_hidden,
            include_disabled=include_disabled,
        ),
    )


def collect_focusable_from_layout(
    layout, root, include_hidden=False, include_disabled=False
):
    """Collect focusable widgets from a layout in layout order."""
    if not isinstance(layout, QLayout):
        return []
    return _collect_focusable_from_layout(
        layout, root, include_hidden, include_disabled
    )


def sort_widgets_left_to_right(widgets, root):
    """Return widgets sorted left-to-right in root coordinates."""
    ordered = [w for w in widgets if w is not None]
    if not ordered:
        return []

    def _x_pos(widget):
        try:
            return widget.mapTo(root, QPoint(0, 0)).x()
        except Exception:
            return 0

    return sorted(ordered, key=_x_pos)
