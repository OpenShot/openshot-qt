"""Expose keyboard focus within a dock to theme stylesheets."""

from qt_api import QApplication, QObject, QDockWidget, QTabBar, QEvent, QTimer, Slot, isdeleted
from classes import tabstops


class DockFocusController(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self.refresh)
        QApplication.instance().focusChanged.connect(self.request_refresh)

    @Slot()
    def request_refresh(self):
        # StyleChange rebuilds QTabBar's internal layout. Never send it from
        # inside currentChanged/focusChanged while Qt is switching dock tabs.
        # The owned timer also cancels pending work when the window is deleted.
        if not isdeleted(self.window) and not getattr(self.window, 'shutting_down', False):
            if not self._refresh_timer.isActive():
                self._refresh_timer.start(0)

    @staticmethod
    def _set_property(widget, name, value):
        if widget is None or widget.property(name) == value:
            return
        widget.setProperty(name, value)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        if isinstance(widget, QTabBar):
            # QTabBar caches tab sizes, including subcontrol borders.
            QApplication.sendEvent(widget, QEvent(QEvent.StyleChange))
        widget.updateGeometry()
        widget.update()

    @Slot()
    def refresh(self):
        if isdeleted(self.window) or getattr(self.window, 'shutting_down', False):
            return
        focus = QApplication.focusWidget()
        active = focus if isinstance(focus, QDockWidget) else (
            tabstops._parent_dock_widget(focus) if focus else None)
        active_tabs = set()
        dock_tabs = set()
        for dock in self.window.findChildren(QDockWidget):
            siblings = self.window.tabifiedDockWidgets(dock) if not dock.isFloating() else []
            bar = tabstops._dock_tab_bar(self.window, dock, siblings)
            if bar is not None:
                dock_tabs.add(bar)
                if dock is active:
                    active_tabs.add(bar)
                if not bar.property('_dockFocusConnected'):
                    bar.setProperty('_dockFocusConnected', True)
                    bar.currentChanged.connect(self.request_refresh)
            titlebar = dock.titleBarWidget()
            self._set_property(titlebar, 'focusWithin', dock is active and bar is None)
            self._set_property(getattr(titlebar, 'title_label', None), 'focusWithin',
                               dock is active and bar is None)
        for bar in self.window.findChildren(QTabBar):
            self._set_property(bar, 'dockFocusTabs', bar in dock_tabs)
            self._set_property(bar, 'focusWithin',
                               bar in dock_tabs and (bar in active_tabs or bar is focus))
