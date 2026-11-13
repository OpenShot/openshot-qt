"""Separate keyboard focus from activation of QMainWindow's dock tabs."""

from qt_api import (
    Qt, QObject, QEvent, QTimer, QAbstractButton, QPainter,
    QStyle, QStyleOptionTab, QDockWidget, QWidget, isdeleted, QtGui,
)


class DockTabButton(QAbstractButton):
    def __init__(self, tabs, index):
        super().__init__(tabs.bar)
        self.tabs = tabs
        self.index = index
        # A keyboard target, not a styled push button. QTabBar owns the text
        # and the only painting here is its theme's focus indicator.
        self.setFocusPolicy(Qt.TabFocus)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.clicked.connect(self.activate)

    def activate(self):
        self.tabs.bar.setCurrentIndex(self.index)
        QTimer.singleShot(0, self.tabs.focus_content)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.activate()
            event.accept()
        elif event.key() in (Qt.Key_Left, Qt.Key_Right):
            index = self.index + (-1 if event.key() == Qt.Key_Left else 1)
            if 0 <= index < len(self.tabs.buttons):
                self.tabs.buttons[index].setFocus(Qt.TabFocusReason)
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        if self.hasFocus():
            painter = QPainter(self)
            bar = self.tabs.bar
            option = QStyleOptionTab()
            option.initFrom(bar)
            option.rect = bar.tabRect(self.index).translated(-self.pos())
            option.text = bar.tabText(self.index)
            option.shape = bar.shape()
            option.state |= QStyle.State_HasFocus
            if self.index == bar.currentIndex():
                option.state |= QStyle.State_Selected
            else:
                option.state &= ~QStyle.State_Selected
            # Preserve the label already painted by QTabBar. Native themes
            # paint an opaque shape; transparent themes must not have their
            # antialiased text painted twice either.
            elements = getattr(QStyle, "SubElement", QStyle)
            text_rect = bar.style().subElementRect(
                elements.SE_TabBarTabText, option, bar)
            text_rect = bar.style().itemTextRect(
                bar.fontMetrics(), text_rect, Qt.AlignCenter,
                bar.isTabEnabled(self.index), option.text)
            # Native styles may replace the painter's clip while drawing.
            # Render separately, then clip the final overlay ourselves.
            overlay = QtGui.QPixmap(self.size() * self.devicePixelRatioF())
            overlay.setDevicePixelRatio(self.devicePixelRatioF())
            overlay.fill(Qt.transparent)
            overlay_painter = QPainter(overlay)
            controls = getattr(QStyle, 'ControlElement', QStyle)
            bar.style().drawControl(controls.CE_TabBarTabShape, option, overlay_painter, bar)
            overlay_painter.end()
            # Native tab shapes often ignore HasFocus entirely (Qt normally
            # draws that indicator with the label). Supply a visible focus
            # frame only when the style has no focused shape of its own.
            normal = QtGui.QPixmap(overlay.size())
            normal.setDevicePixelRatio(overlay.devicePixelRatio())
            normal.fill(Qt.transparent)
            normal_painter = QPainter(normal)
            option.state &= ~QStyle.State_HasFocus
            bar.style().drawControl(controls.CE_TabBarTabShape, option, normal_painter, bar)
            normal_painter.end()
            if normal.toImage() == overlay.toImage():
                painter.setPen(QtGui.QPen(bar.palette().highlight().color(), 1, Qt.DotLine))
                painter.drawRect(self.rect().adjusted(3, 3, -4, -4))
                return
            painter.setClipRegion(
                QtGui.QRegion(option.rect).subtracted(QtGui.QRegion(text_rect)))
            painter.drawPixmap(0, 0, overlay)


class DockTabStops(QObject):
    def __init__(self, bar, window):
        super().__init__(bar)
        self.bar = bar
        self.window = window
        self.buttons = []
        # QMainWindow owns the C++ tab bar, but does not retain its Python
        # wrapper. The bar/stops/buttons reference cycle alone can be collected,
        # leaving Qt-owned buttons in the focus chain without their Python key
        # and paint handlers. Root the wrappers in the window until Qt deletes
        # the bar, including while dock groups are being rebuilt.
        if not hasattr(window, '_dock_tab_stops_by_bar'):
            window._dock_tab_stops_by_bar = {}
        registry = window._dock_tab_stops_by_bar
        registry[bar] = self
        bar.destroyed.connect(lambda: registry.pop(bar, None))
        bar.installEventFilter(self)
        self.sync()

    def sync(self):
        if isdeleted(self.bar):
            return
        self.bar.setFocusPolicy(Qt.NoFocus)
        while len(self.buttons) > self.bar.count():
            button = self.buttons.pop()
            button.hide()
            button.deleteLater()
        while len(self.buttons) < self.bar.count():
            self.buttons.append(DockTabButton(self, len(self.buttons)))
        for index, button in enumerate(self.buttons):
            text = self.bar.tabText(index)
            # QTabBar owns the visible label. Keep the overlay's button text
            # empty: stylesheet painting can draw it outside paintEvent.
            button.setAccessibleName(text)
            rect = self.bar.tabRect(index).intersected(self.bar.rect())
            if button.geometry() != rect:
                button.setGeometry(rect)
            button.setEnabled(self.bar.isTabEnabled(index))
            button.setVisible(not rect.isEmpty())

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Resize, QEvent.Show, QEvent.LayoutRequest, QEvent.Paint):
            self.sync()
        elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            index = self.bar.tabAt(event.pos())
            if index >= 0 and self.bar.isTabEnabled(index):
                # Wait for QTabBar/QMainWindow to finish switching the visible
                # dock, including when the user clicks the already active tab.
                QTimer.singleShot(0, self.focus_content)
        return False

    def focus_content(self):
        if isdeleted(self.window) or isdeleted(self.bar):
            return
        from classes import tabstops
        tabstops.apply_auto_tab_order(self.window)
        title = self.bar.tabText(self.bar.currentIndex())
        dock = next((dock for dock in self.window.findChildren(QDockWidget)
                     if dock.windowTitle() == title and not dock.isFloating()), None)
        if dock is None or dock.widget() is None:
            return
        content = dock.widget()
        candidates = [widget for widget in [content] + content.findChildren(QWidget)
                      if widget.isVisibleTo(self.window) and widget.isEnabled()
                      and widget.focusPolicy() & Qt.TabFocus]
        if candidates:
            first = min(candidates, key=lambda widget: getattr(widget, '_tab_order_key', (float('inf'),)))
            first.setFocus(Qt.TabFocusReason)
