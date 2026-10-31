"""Rich hardware choices preserve identifiers and paint selected badges sharply."""
import unittest
from unittest.mock import Mock

from qt_api import QApplication, QImage, QPainter, QColor, QRect, QStyleOptionViewItem, QStyle, Qt, QTest, QPoint
from windows.views.hardware_combo import HardwareComboBox, set_hardware_item, export_choice_label, backend_badge


class HardwareComboTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_labels_hide_backend_suffixes_but_preserve_custom_preset_names(self):
        self.assertEqual(export_choice_label('MP4 (h.264 nv)', 'mp4', 'h264_nvenc', 'nvenc'), 'MP4 (H.264)')
        self.assertEqual(export_choice_label('MP4 (HEVC Vulkan)', 'mp4', 'hevc_vulkan', 'vulkan'), 'MP4 (H.265)')
        self.assertEqual(export_choice_label('MP4 (h.264)', 'mp4', 'libx264', 'cpu'), 'MP4 (H.264)')
        self.assertEqual(export_choice_label('MP4 (h.264 lossless)', 'mp4', 'libx264', 'cpu'), 'MP4 (h.264 lossless)')
        self.assertEqual(export_choice_label('My high quality preset', 'mp4', 'h264_nvenc', 'nvenc'), 'My high quality preset')
        self.assertEqual(backend_badge('nvenc'), 'NVIDIA')
        self.assertEqual(backend_badge('qsv'), 'Intel')
        self.assertEqual(backend_badge('vtb'), 'Apple')

    def test_selected_badge_matches_popup_without_small_icon_pixmap_scaling(self):
        combo = HardwareComboBox()
        combo.setStyleSheet('QComboBox { background: #2a3342; color: #e6edf7; '
                           'border: 1px solid #455269; border-radius: 4px; padding: 5px; }')
        combo.resize(440, 36)
        combo.addItem('MP4 (h.264 nv)', 'original preset identifier')
        set_hardware_item(combo, 0, 'gpu', 'MP4 (H.264)', 'NVIDIA',
                          'Hardware encoding · NVIDIA · NVENC')
        combo.setItemData(0, 'NVIDIA NVENC — h264_nvenc', Qt.ToolTipRole)
        self.assertEqual(combo.itemData(0), 'original preset identifier')
        self.assertIn('h264_nvenc', combo.itemData(0, Qt.ToolTipRole))
        combo.sync_details()
        self.assertIn('h264_nvenc', combo.toolTip())
        renderer = Mock(wraps=combo.badge_delegate.renderers['gpu'])
        combo.badge_delegate.renderers['gpu'] = renderer
        combo.show()
        self.app.processEvents()
        selected = combo.grab().toImage()
        selected_rect = renderer.render.call_args.args[1]
        dpr = selected.devicePixelRatioF()
        image = QImage(round(combo.width() * dpr), round(52 * dpr), QImage.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(dpr)
        image.fill(QColor('white'))
        painter = QPainter(image)
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, combo.width(), 52)
        option.font = combo.font()
        option.palette = combo.palette()
        option.state = QStyle.State_Enabled | QStyle.State_Selected
        self.assertGreaterEqual(combo.badge_delegate.sizeHint(
            option, combo.model().index(0, 0)).height(), 52)
        combo.badge_delegate.paint(painter, option, combo.model().index(0, 0))
        painter.end()
        popup_rect = renderer.render.call_args.args[1]
        def interior(source, rect):
            area = QRect(round((rect.x() + 20) * dpr), round((rect.y() + 4) * dpr),
                         round(36 * dpr), round(14 * dpr))
            return source.copy(area).convertToFormat(QImage.Format_ARGB32)
        self.assertEqual(selected_rect.width(), 64)
        self.assertEqual(popup_rect.width(), 64)
        self.assertEqual(interior(selected, selected_rect), interior(image, popup_rect))
        combo.close()

    def test_popup_hover_does_not_scroll_and_mouse_can_select_last_visible_row(self):
        combo = HardwareComboBox()
        combo.resize(440, 36)
        for i in range(24):
            combo.addItem('Format %s' % i, i)
            set_hardware_item(combo, i, 'gpu', details='Hardware encoding · Vulkan')
        combo.show()
        combo.showPopup()
        self.app.processEvents()
        view = combo.popup_view
        scrollbar = view.verticalScrollBar()
        self.assertGreater(scrollbar.maximum(), 0)
        initial = scrollbar.value()
        viewport = view.viewport()
        point = QPoint(viewport.width() // 2, viewport.height() - 8)
        expected = view.indexAt(point)
        self.assertTrue(expected.isValid())
        QTest.mouseMove(viewport, point)
        QTest.qWait(350)
        self.assertEqual(scrollbar.value(), initial)
        QTest.mouseClick(viewport, Qt.LeftButton, pos=point)
        self.assertEqual(combo.currentData(), expected.row())
        combo.close()

    def test_filter_header_preserves_selection_and_searches_details(self):
        combo = HardwareComboBox()
        for mode, details in [('cpu', 'Software encoding'), ('gpu', 'NVIDIA NVENC'), ('gpu', 'Intel QSV')]:
            i = combo.count()
            combo.addItem('MP4 (H.264)', 'preset-%s' % i)
            set_hardware_item(combo, i, mode, details=details)
        combo.show()
        combo.showPopup()
        self.app.processEvents()
        combo._filter_mode('gpu')
        self.assertTrue(combo.popup_view.isRowHidden(0))
        combo.filter_search.setText('intel')
        self.assertTrue(combo.popup_view.isRowHidden(1))
        self.assertFalse(combo.popup_view.isRowHidden(2))
        self.assertEqual(combo.currentData(), 'preset-0')
        combo.filter_search.setText('nothing matches')
        self.assertFalse(combo.filter_empty.isHidden())
        combo._accept_filter_current()
        self.assertEqual(combo.currentData(), 'preset-0')
        combo.filter_search.setText('intel')
        QTest.keyClick(combo.filter_search, Qt.Key_Down)
        self.app.processEvents()
        QTest.keyClick(combo.popup_view, Qt.Key_Return)
        self.assertEqual(combo.currentData(), 'preset-2')
        combo.showPopup()
        self.assertEqual(combo.filter_search.text(), '')
        self.assertFalse(combo.popup_view.isRowHidden(0))
        combo.hidePopup()
        combo.close()
