"""Measured work, empty stages, session boundaries and shared visualization."""
import json
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from pathlib import Path
import sys

SOURCE_ROOT = str(Path(__file__).resolve().parents[1])
if SOURCE_ROOT not in sys.path:
    sys.path.insert(0, SOURCE_ROOT)

from qt_api import QApplication
from classes.gpu_metrics import GpuMeasurements, stages
from windows.views.gpu_metrics import GpuSegments, GpuMetricsDock


class GpuMetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_threshold_is_strict_and_no_activity_is_neutral(self):
        rows = stages({'decode_gpu': 3, 'decode_cpu': 1, 'render_gpu': 4,
                       'copy_free': 2, 'gpu_requests': 4})
        self.assertEqual([r['percent'] for r in rows], [75, 100, 50, None])
        self.assertTrue(all(r['percent'] is None for r in stages({})))
        self.assertEqual(stages({'encode_gpu': 9, 'encode_cpu': 1}, True)[3]['percent'], 90)

    def test_export_snapshot_is_independent_and_reset_keeps_preview_registration(self):
        native = SimpleNamespace(GpuMetricsSnapshot=Mock(return_value=json.dumps({'decode_gpu': 5})),
                                 ResetGpuMetrics=Mock())
        diagnostics = SimpleNamespace(lock=threading.RLock(), previews={7: dict(name='timeline', native_draws=9,
                                             cpu_draws=1, fallback_reasons=['reason'])})
        diagnostics.snapshot = lambda: dict(previews=list(diagnostics.previews.values()))
        measurements = GpuMeasurements(native, diagnostics)
        self.assertEqual(stages(measurements.snapshot())[3]['percent'], 90)
        self.assertNotIn('display_gpu', measurements.snapshot(True))
        measurements.reset(True)
        self.assertEqual(diagnostics.previews[7]['native_draws'], 9)
        measurements.reset()
        self.assertIn(7, diagnostics.previews)
        self.assertEqual(diagnostics.previews[7]['native_draws'], 0)
        native.ResetGpuMetrics.assert_called_with(False)

    def test_old_bindings_leave_native_stages_unknown(self):
        raw = GpuMeasurements(SimpleNamespace()).snapshot()
        self.assertTrue(all(row['percent'] is None for row in stages(raw)))
        self.assertFalse(raw['native_available'])

    def test_export_widget_freezes_its_snapshot_and_explains_cpu_images(self):
        raw = {'decode_gpu': 8, 'decode_cpu': 2, 'image_sources': 4,
               'copy_free': 9, 'gpu_requests': 10, 'encode_gpu': 10}
        widget = GpuSegments(exporting=True)
        widget.set_snapshot(raw)
        raw['decode_gpu'] = 0
        self.assertEqual(widget.rows[0]['percent'], 80)
        self.assertEqual(widget.rows[3]['label'], 'Encode')
        self.assertIn('expected', widget.toolTip())
        self.assertIn('not GPU utilization', widget.toolTip())
        self.assertIn('readback', widget.toolTip())
        widget.close()

    def test_dock_reset_and_bounded_reason_details(self):
        measurements = Mock()
        measurements.snapshot.return_value = {'readbacks': 3, 'readback_reasons': {'Effect': 3}}
        dock = GpuMetricsDock(measurements, lambda text: text)
        self.assertEqual(dock.reason_bars[0][1].text(), 'Effect: 3')
        self.assertEqual(dock.reason_bars[0][2].percent, 100)
        dock.reset()
        measurements.reset.assert_called_once_with()
        dock.close()

    def test_inspector_explains_missing_native_counters_instead_of_silent_zeros(self):
        measurements = Mock()
        measurements.snapshot.return_value = {'native_available': False, 'display_gpu': 99, 'display_cpu': 1}
        dock = GpuMetricsDock(measurements, lambda text: text)
        self.assertFalse(dock.notice.isHidden())
        self.assertIn('Rebuild libopenshot', dock.notice.text())
        self.assertEqual(dock.transfer_values['readbacks'].text(), '—')
        self.assertEqual(dock.stage_rows[3].value.text(), '99%')
        self.assertIsNone(dock.stage_rows[0].bar.percent)
        dock.close()

    def test_cosmic_padding_survives_outer_dock_margin_changes(self):
        from qt_api import QPalette, QPoint
        from themes.cosmic.theme import CosmicTheme
        old_style = self.app.styleSheet()
        old_palette = QPalette(self.app.palette())
        measurements = Mock()
        measurements.snapshot.return_value = {'decode_gpu': 10}
        dock = GpuMetricsDock(measurements, lambda text: text)
        try:
            self.app.setStyleSheet(CosmicTheme(self.app).compose_stylesheet())
            dock.resize(300, 520)
            dock.show()
            surface = dock.widget().widget()
            surface.layout().setContentsMargins(0, 0, 0, 0)
            surface.setContentsMargins(0, 0, 0, 0)
            self.app.processEvents()
            point = dock.stage_rows[0].name.mapTo(surface, QPoint(0, 0))
            self.assertGreaterEqual(point.x(), 20)
            self.assertEqual(surface.grab().toImage().pixelColor(2, 100).name(), '#141923')
        finally:
            dock.close()
            self.app.setStyleSheet(old_style)
            self.app.setPalette(old_palette)
