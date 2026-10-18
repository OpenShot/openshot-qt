"""Dock focus indicators follow child controls without changing geometry."""

import unittest

from qt_api import Qt, QMainWindow, QDockWidget, QLineEdit, QColor, QWidget
from classes.dock_focus import DockFocusController
from classes.title_bar import HiddenTitleBar
from classes import tabstops
from tests.qt_test_app import get_or_create_app
from tests.test_main_window import DummyApp, ensure_app_state


class DockFocusTests(unittest.TestCase):
    def setUp(self):
        self.app, _ = get_or_create_app(DummyApp)
        ensure_app_state(self.app)
        from themes.cosmic.theme import CosmicTheme
        self.window = QMainWindow()
        self.window.setStyleSheet(CosmicTheme(self.app).compose_stylesheet())
        self.outside = QLineEdit()
        self.window.setCentralWidget(self.outside)
        self.docks = []
        for name in ('Files', 'Effects'):
            dock = QDockWidget(name, self.window)
            dock.setWidget(QLineEdit())
            dock.setTitleBarWidget(HiddenTitleBar(dock, name))
            self.window.addDockWidget(Qt.LeftDockWidgetArea, dock)
            self.docks.append(dock)
        self.controller = DockFocusController(self.window)
        self.window.resize(800, 500)
        self.window.show()
        self.window.activateWindow()
        self.app.processEvents()

    def tearDown(self):
        self.app.focusChanged.disconnect(self.controller.request_refresh)
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def focus(self, widget):
        widget.setFocus(Qt.TabFocusReason)
        self.app.processEvents()
        self.app.processEvents()  # Focus changes during layout queue a style refresh.
        self.assertTrue(widget.hasFocus())

    def blue_pixels(self, widget):
        image = widget.grab().toImage()
        blue = QColor('#5aa2e6').rgba()
        return sum(image.pixel(x, y) == blue for x in range(image.width())
                   for y in range(image.height()))

    def test_focus_refresh_ignores_deleted_window(self):
        from qt_api import QCoreApplication, QEvent, isdeleted
        window = QMainWindow()
        controller = DockFocusController(window)
        window.deleteLater()
        QCoreApplication.sendPostedEvents(window, QEvent.DeferredDelete)
        self.assertTrue(isdeleted(window))
        controller.refresh()

    def test_tab_switch_defers_style_changes_until_signal_returns(self):
        from unittest.mock import patch
        first, second = self.docks
        self.window.tabifyDockWidget(first, second)
        first.raise_()
        self.app.processEvents()
        self.controller.refresh()
        bar = tabstops._dock_tab_bar(self.window, first, [second])
        self.focus(first.widget())
        with patch.object(self.controller, '_set_property',
                          wraps=self.controller._set_property) as update:
            bar.setCurrentIndex(1 - bar.currentIndex())
            self.outside.setFocus()
            self.assertFalse(update.called)
            self.assertTrue(self.controller._refresh_timer.isActive())
            self.app.processEvents()
            self.assertTrue(update.called)

    def test_pending_focus_refresh_is_cancelled_when_window_is_deleted(self):
        from qt_api import QCoreApplication, QEvent, isdeleted
        window = QMainWindow()
        controller = DockFocusController(window)
        controller.request_refresh()
        self.assertTrue(controller._refresh_timer.isActive())
        window.deleteLater()
        QCoreApplication.sendPostedEvents(window, QEvent.DeferredDelete)
        self.assertTrue(isdeleted(controller))
        self.app.processEvents()

    def test_repeated_tab_switches_with_content_and_titlebar_replacement(self):
        from qt_api import QCoreApplication, QEvent
        first, second = self.docks
        self.window.tabifyDockWidget(first, second)
        self.app.processEvents()
        tabstops.apply_auto_tab_order(self.window)
        for index in range(100):
            dock = self.docks[index % 2]
            dock.raise_()
            dock.widget().setFocus()
            # Exercise replacement/deletion with a focus refresh still queued.
            previous = dock.widget()
            dock.setWidget(QLineEdit())
            previous.deleteLater()
            title = dock.titleBarWidget()
            dock.setTitleBarWidget(HiddenTitleBar(dock, ''))
            title.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            self.focus(dock.widget())
            bar = tabstops._dock_tab_bar(self.window, first, [second])
            self.assertTrue(bar.property('focusWithin'))

    def test_title_and_buttons_show_focus_without_changing_size(self):
        dock = self.docks[0]
        title = dock.titleBarWidget()
        self.focus(self.outside)
        self.assertFalse(title.property('focusWithin'))
        self.assertEqual(self.blue_pixels(title), 0)
        size = title.size()
        self.focus(dock.widget())
        self.assertTrue(title.property('focusWithin'))
        label = title.title_label
        self.assertGreater(self.blue_pixels(label), 10)
        self.assertLessEqual(self.blue_pixels(title), label.fontMetrics().horizontalAdvance(label.text()) + 2)
        self.assertEqual(self.blue_pixels(title), self.blue_pixels(label))
        self.assertEqual(title.size(), size)
        for button in (title.close_button, title.undock_button):
            size = button.size()
            self.focus(button)
            self.assertTrue(title.property('focusWithin'))
            self.assertGreater(self.blue_pixels(button), 10)
            self.assertEqual(button.size(), size)
        self.focus(self.docks[1].widget())
        self.assertFalse(title.property('focusWithin'))
        self.assertTrue(self.docks[1].titleBarWidget().property('focusWithin'))

    def test_untitled_timeline_has_no_focus_line(self):
        dock = self.docks[0]
        dock.setObjectName('dockTimeline')
        dock.setTitleBarWidget(QWidget())
        self.controller.refresh()
        self.focus(dock.widget())
        self.assertEqual(self.blue_pixels(dock), 0)

    def test_dock_dropdown_has_focus_border_without_resizing(self):
        from qt_api import QComboBox
        combo = QComboBox()
        combo.setObjectName('emojiFilterGroup')
        combo.addItems(['All', 'Smileys & Emotion'])
        self.docks[0].setWidget(combo)
        self.app.processEvents()
        self.focus(self.outside)
        size = combo.size()
        self.assertEqual(self.blue_pixels(combo), 0)
        self.window.setAttribute(Qt.WA_KeyboardFocusChange, True)
        self.focus(combo)
        self.assertGreater(self.blue_pixels(combo), 10)
        self.assertEqual(combo.size(), size)
        self.focus(self.outside)
        self.assertEqual(self.blue_pixels(combo), 0)

    def test_dock_buttons_keep_background_when_focused_hovered_or_pressed(self):
        title = self.docks[0].titleBarWidget()
        for button in (title.close_button, title.undock_button):
            self.focus(self.outside)
            button.setAttribute(Qt.WA_UnderMouse, False)
            normal = button.grab().toImage()
            # Stay inside the rounded border, including the icon and its background.
            right_margin = 16 if button is title.close_button else 0
            interior = normal.rect().adjusted(4, 4, -4 - right_margin, -4)
            expected = normal.copy(interior)
            # Keyboard navigation enables Qt's native focus decoration. Merely
            # calling setFocus(TabFocusReason) does not enable it in these tests.
            self.window.setAttribute(Qt.WA_KeyboardFocusChange, True)
            self.focus(button)
            self.assertGreater(self.blue_pixels(button), 10)
            self.assertEqual(button.grab().toImage().copy(interior), expected)
            button.setAttribute(Qt.WA_UnderMouse, True)
            self.assertEqual(button.grab().toImage().copy(interior), expected)
            button.setDown(True)
            self.assertEqual(button.grab().toImage().copy(interior), expected)
            button.setDown(False)
            button.setAttribute(Qt.WA_UnderMouse, False)

    def test_focused_tab_title_matches_active_dock_underline(self):
        first, second = self.docks
        self.window.tabifyDockWidget(first, second)
        first.raise_()
        self.app.processEvents()
        tabstops.apply_auto_tab_order(self.window)
        bar = tabstops._dock_tab_bar(self.window, first, [second])
        index = next(i for i in range(bar.count()) if bar.tabText(i) == second.windowTitle())
        self.focus(bar._dock_tab_stops.buttons[index])
        def blue_positions():
            image = bar.grab().toImage()
            blue = QColor('#5aa2e6').rgba()
            return {(x, y) for x in range(image.width()) for y in range(image.height())
                    if image.pixel(x, y) == blue}
        focused = blue_positions()
        self.assertGreater(len(focused), 10)
        self.assertEqual(len({y for x, y in focused}), 1)
        self.assertEqual(bar.tabText(bar.currentIndex()), first.windowTitle())
        second.raise_()
        self.focus(second.widget())
        self.assertEqual(blue_positions(), focused)

    def test_keyboard_overlays_preserve_tab_title_pixels(self):
        first, second = self.docks
        first.setWindowTitle('Project Files')
        second.setWindowTitle('Transitions')
        self.window.tabifyDockWidget(first, second)
        first.raise_()
        self.app.processEvents()
        tabstops.apply_auto_tab_order(self.window)
        bar = tabstops._dock_tab_bar(self.window, first, [second])
        stops = bar._dock_tab_stops
        for index, button in enumerate(stops.buttons):
            self.assertEqual(button.text(), '')
            self.assertEqual(button.accessibleName(), bar.tabText(index))
        self.focus(self.outside)
        # Compare against Qt's own tab rendering without the keyboard overlays.
        bar.removeEventFilter(stops)
        for button in stops.buttons:
            button.hide()
        original = bar.grab().toImage()
        stops.sync()
        self.assertEqual(bar.grab().toImage(), original)
        for button in stops.buttons:
            self.window.setAttribute(Qt.WA_KeyboardFocusChange, True)
            self.focus(button)
            focused = bar.grab().toImage()
            # Only the bottom focus underline may differ, never the title text.
            text_area = original.rect().adjusted(0, 0, 0, -3)
            self.assertEqual(focused.copy(text_area), original.copy(text_area))

    def test_tab_titles_focus_without_activation_and_enter_opens_content(self):
        import importlib
        from qt_api import QT_API, QToolBar, QVBoxLayout, QAction
        binding = {'pyqt5': 'PyQt5', 'pyqt6': 'PyQt6', 'pyside6': 'PySide6'}[QT_API]
        QTest = importlib.import_module(binding + '.QtTest').QTest
        for name in ('Transitions', 'Emojis'):
            dock = QDockWidget(name, self.window)
            dock.setTitleBarWidget(HiddenTitleBar(dock, ''))
            self.window.addDockWidget(Qt.LeftDockWidgetArea, dock)
            self.docks.append(dock)
        children = []
        for dock in self.docks:
            content = QWidget()
            layout = QVBoxLayout(content)
            toolbar = QToolBar()
            layout.addWidget(toolbar)
            buttons = []
            for name in ('Show All', 'Video', 'Audio', 'Image'):
                action = QAction(name, toolbar)
                toolbar.addAction(action)
                buttons.append(toolbar.widgetForAction(action))
            dock.setWidget(content)
            children.append(buttons)
        first = self.docks[0]
        for dock in self.docks[1:]:
            self.window.tabifyDockWidget(first, dock)
        first.raise_()
        self.app.processEvents()
        tabstops.apply_auto_tab_order(self.window, include_hidden=True)
        bar = tabstops._dock_tab_bar(self.window, first, self.docks[1:])
        titles = bar._dock_tab_stops.buttons
        active = bar.currentIndex()
        self.focus(self.outside)
        for _ in range(30):
            QTest.keyClick(self.app.focusWidget(), Qt.Key_Tab)
            if titles[0].hasFocus():
                break
        self.assertTrue(titles[0].hasFocus())
        for title in titles[1:]:
            QTest.keyClick(self.app.focusWidget(), Qt.Key_Tab)
            self.assertTrue(title.hasFocus())
            self.assertEqual(bar.currentIndex(), active)
        QTest.keyClick(titles[-1], Qt.Key_Backtab)
        self.assertTrue(titles[-2].hasFocus())
        self.assertEqual(bar.currentIndex(), active)
        for index, key in ((1, Qt.Key_Return), (2, Qt.Key_Space)):
            self.focus(titles[index])
            QTest.keyClick(titles[index], key)
            self.app.processEvents()
            self.assertEqual(bar.currentIndex(), index)
            target = next(i for i, dock in enumerate(self.docks)
                          if dock.windowTitle() == bar.tabText(index))
            self.assertTrue(children[target][0].hasFocus())
            # Walk a full cycle: no control in an inactive page may receive focus.
            for _ in range(24):
                QTest.keyClick(self.app.focusWidget(), Qt.Key_Tab)
                focus = self.app.focusWidget()
                self.assertTrue(focus.isVisibleTo(self.window))
                dock = tabstops._parent_dock_widget(focus)
                if dock is not None:
                    self.assertIs(dock, self.docks[target])
        # Mouse/programmatic activation must restore the page's tab stops too.
        first.raise_()
        self.app.processEvents()
        self.assertNotEqual(children[0][0].focusPolicy(), Qt.NoFocus)
        self.assertEqual(children[1][0].focusPolicy(), Qt.NoFocus)

        # Clicking a different or already active tab enters its first control.
        # Tab must then continue within that page, not the previously focused dock.
        for index in (1, 1, 0):
            self.focus(self.outside)
            QTest.mouseClick(bar, Qt.LeftButton, pos=bar.tabRect(index).center())
            self.app.processEvents()
            self.app.processEvents()  # Deferred content focus then deferred styling.
            target = next(i for i, dock in enumerate(self.docks)
                          if dock.windowTitle() == bar.tabText(index))
            self.assertEqual(bar.currentIndex(), index)
            self.assertTrue(children[target][0].hasFocus())
            self.assertTrue(bar.property('focusWithin'))
            self.assertGreater(self.blue_pixels(bar), 10)
            QTest.keyClick(self.app.focusWidget(), Qt.Key_Tab)
            self.assertTrue(children[target][1].hasFocus())

    def test_focused_dock_tab_keeps_label_on_opaque_background(self):
        from qt_api import QStyleFactory
        from classes.ui_util import make_dark_palette
        # Exercise native Fusion painting, not a stylesheet-defined tab shape.
        self.window.setStyleSheet("")
        self.window.setStyle(QStyleFactory.create("Fusion"))
        self.window.setPalette(make_dark_palette(self.window.palette()))
        first, second = self.docks
        self.window.tabifyDockWidget(first, second)
        self.app.processEvents()
        tabstops.apply_auto_tab_order(self.window)
        bar = tabstops._dock_tab_bar(self.window, first, [second])
        for button in bar._dock_tab_stops.buttons:
            self.focus(self.outside)
            before = bar.grab().toImage().copy(button.geometry())
            self.focus(button)
            image = bar.grab().toImage().copy(button.geometry())
            self.assertNotEqual(image, before, "Focused tab needs a visible indicator")
            light_pixels = sum(
                image.pixelColor(x, y).lightness() > 180
                for x in range(image.width()) for y in range(image.height()))
            self.assertGreater(light_pixels, 10, button.accessibleName())

    def test_tab_stops_survive_garbage_collection_without_orphan_controls(self):
        import gc
        import weakref
        from classes.dock_tabs import DockTabButton, DockTabStops
        from qt_api import QCoreApplication, QEvent, isdeleted
        window = QMainWindow()
        self.addCleanup(lambda: None if isdeleted(window) else window.deleteLater())
        first, second = [QDockWidget(name, window) for name in ('Files', 'Emojis')]
        for dock in (first, second):
            dock.setWidget(QLineEdit())
            window.addDockWidget(Qt.LeftDockWidgetArea, dock)
        window.tabifyDockWidget(first, second)
        # Match startup: create the stops before showing the main window.
        bar = tabstops._dock_tab_bar(window, first, [second])
        bar._dock_tab_stops = DockTabStops(bar, window)
        reference = weakref.ref(bar)
        del bar
        # Qt owns its internal tab bar. Do not keep a test-local reference to
        # its Python wrapper: ordinary application GC must preserve our stops.
        for _ in range(5):
            gc.collect()
            self.assertIsNotNone(reference())
            tabstops.apply_auto_tab_order(window)
            self.app.processEvents()
        window.show()
        self.app.processEvents()
        bar = tabstops._dock_tab_bar(window, first, [second])
        focusable = [child for child in bar.findChildren(QWidget)
                     if child.isVisibleTo(window) and child.focusPolicy() & Qt.TabFocus]
        self.assertEqual(len(focusable), bar.count())
        self.assertTrue(all(isinstance(child, DockTabButton) for child in focusable))
        # Destroying the Qt owner must release the registry, too.
        registry = window._dock_tab_stops_by_bar
        window.deleteLater()
        QCoreApplication.sendPostedEvents(window, QEvent.DeferredDelete)
        self.assertEqual(registry, {})

    def test_tabbed_docks_use_tab_indicator_and_clear_when_focus_leaves(self):
        first, second = self.docks
        self.window.tabifyDockWidget(first, second)
        second.raise_()
        self.app.processEvents()
        self.controller.refresh()
        bar = tabstops._dock_tab_bar(self.window, second, [first])
        self.assertIsNotNone(bar)
        self.focus(second.widget())
        self.assertTrue(bar.property('focusWithin'))
        self.assertFalse(second.titleBarWidget().property('focusWithin'))
        self.assertGreater(self.blue_pixels(bar), 10)
        first.raise_()
        self.focus(first.widget())
        self.assertTrue(bar.property('focusWithin'))
        self.focus(self.outside)
        self.assertFalse(bar.property('focusWithin'))
        self.assertEqual(self.blue_pixels(bar), 0)
        first.setFloating(True)
        self.controller.refresh()
        self.focus(first.widget())
        self.assertTrue(first.titleBarWidget().property('focusWithin'))
        self.assertFalse(bar.property('focusWithin'))
