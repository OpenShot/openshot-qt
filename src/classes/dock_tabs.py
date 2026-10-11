"""Separate keyboard focus from activation of QMainWindow's dock tabs."""

from qt_api import (
    Qt, QObject, QEvent, QTimer, QAbstractButton, QPainter,
    QStyle, QStyleOptionTab, QDockWidget, QWidget, isdeleted,
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
            # Ask the tab's own style to paint focus, including its margins
            # and border thickness, instead of drawing a separate focus box.
            controls = getattr(QStyle, 'ControlElement', QStyle)
            bar.style().drawControl(controls.CE_TabBarTabShape, option, painter, bar)


class DockTabStops(QObject):
    def __init__(self, bar, window):
        super().__init__(bar)
        self.bar = bar
        self.window = window
        self.buttons = []
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
