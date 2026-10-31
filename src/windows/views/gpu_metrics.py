"""One four-segment visualization for live preview and frozen export reports."""
from qt_api import (Qt, QWidget, QPainter, QColor, QRectF, QSize, QTimer, QVBoxLayout,
                    QHBoxLayout, QLabel, QPushButton, QDockWidget, QFrame, QScrollArea, QPalette)
from classes.gpu_metrics import stages


class GpuSegments(QWidget):
    def __init__(self, translate=lambda text: text, parent=None, exporting=False):
        super().__init__(parent)
        self.translate, self.exporting, self.raw = translate, exporting, {}
        self.setFixedSize(62, 16)
        self.setAccessibleName(translate('GPU pipeline measurements'))
        self.set_snapshot({})

    def set_snapshot(self, raw):
        self.raw = dict(raw)
        self.rows = stages(self.raw, self.exporting)
        _ = self.translate
        lines = []
        for row in self.rows:
            value = (_('No measured work') if row['percent'] is None else
                     '%g%% (%s/%s %s)' % (round(row['percent'], 1), row['gpu'], row['total'], _(row['unit'])))
            lines.append('%s: %s' % (_(row['label']), value))
        if self.raw.get('native_available') is False:
            lines.insert(0, _('Native GPU work counters unavailable. Rebuild libopenshot and restart OpenShot.'))
        lines.extend([_('Green: above 75%. Amber: 75% or less. Gray: no measurements.'),
                      _('Decode/render/encode count operations, not GPU utilization. Cached work is not counted again.'),
                      _('Copy-free: GPU work requests without CPU readback; initial uploads are reported separately.')])
        if self.raw.get('image_sources'):
            lines.append(_('CPU-origin image requests: %s (expected)') % self.raw['image_sources'])
        lines.append(_('CPU readbacks: %s · uploads: %s') % (self.raw.get('readbacks', 0), self.raw.get('uploads', 0)))
        text = '\n'.join(lines)
        self.setToolTip(text)
        self.setAccessibleDescription(text)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        for index, row in enumerate(self.rows):
            color = self.palette().color(QPalette.WindowText)
            color.setAlpha(64)
            if row['percent'] is not None:
                color = QColor('#2fbf71' if row['percent'] > 75 else '#d99b36')
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(index * 16, 4, 13, 8), 2, 2)
        painter.end()


class GpuWorkBar(QWidget):
    """A proportional work bar, without retaining per-frame history."""
    def __init__(self, parent=None, readback=False):
        super().__init__(parent)
        self.readback = readback
        self.percent = None
        self.setFixedHeight(7)
        self.setMinimumWidth(80)

    def set_percent(self, value):
        self.percent = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        bounds = QRectF(0, 0, self.width(), 7)
        track = self.palette().color(QPalette.WindowText)
        track.setAlpha(64)
        painter.setBrush(track if self.percent is None or self.readback else QColor('#d99b36'))
        painter.drawRoundedRect(bounds, 3, 3)
        if self.percent is not None and self.percent > 0:
            painter.setClipRect(QRectF(0, 0, self.width() * self.percent / 100, 7))
            painter.setBrush(QColor('#d99b36' if self.readback else '#2fbf71'))
            painter.drawRoundedRect(bounds, 3, 3)
        painter.end()


class GpuStageRow(QWidget):
    def __init__(self, translate, parent=None):
        super().__init__(parent)
        self.translate = translate
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        heading = QHBoxLayout()
        self.name = QLabel(self)
        self.value = QLabel(self)
        self.value.setStyleSheet('font-size: 17px; font-weight: 600;')
        heading.addWidget(self.name)
        heading.addStretch()
        heading.addWidget(self.value)
        layout.addLayout(heading)
        self.bar = GpuWorkBar(self)
        layout.addWidget(self.bar)
        self.caption = QLabel(self)
        self.caption.setWordWrap(True)
        self.caption.setStyleSheet('color: palette(mid); font-size: 11px;')
        layout.addWidget(self.caption)

    def set_stage(self, row):
        _ = self.translate
        self.name.setText(_(row['label']))
        self.value.setText('—' if row['percent'] is None else '%g%%' % round(row['percent'], 1))
        self.caption.setText(_('No measured work yet') if row['percent'] is None else
                             '%s / %s %s' % (row['gpu'], row['total'], _(row['unit'])))
        self.bar.set_percent(row['percent'])
        self.setToolTip('%s: %s' % (_(row['label']), self.caption.text()))


class GpuMetricsDock(QDockWidget):
    def __init__(self, measurements, translate, parent=None):
        super().__init__(translate('GPU Inspector'), parent)
        self.setObjectName('dockGpuInspector')
        self.measurements, self.translate = measurements, translate
        surface = QWidget(self)
        surface.setObjectName('dockGpuInspectorContents')
        surface.setAttribute(Qt.WA_StyledBackground, True)
        outer = QVBoxLayout(surface)
        outer.setContentsMargins(0, 0, 0, 0)
        panel = QWidget(surface)
        panel.setObjectName('gpuMetricsPanel')
        outer.addWidget(panel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(15)
        top = QHBoxLayout()
        subtitle = QLabel(translate('Observed GPU work'), panel)
        subtitle.setStyleSheet('color: palette(mid); font-size: 11px;')
        top.addWidget(subtitle)
        top.addStretch()
        reset = QPushButton(translate('Reset'), panel)
        reset.clicked.connect(self.reset)
        top.addWidget(reset)
        layout.addLayout(top)
        self.notice = QLabel(panel)
        self.notice.setWordWrap(True)
        self.notice.setStyleSheet('color: #d99b36; font-size: 11px;')
        layout.addWidget(self.notice)
        self.stage_rows = [GpuStageRow(translate, panel) for _ in range(4)]
        for row in self.stage_rows:
            layout.addWidget(row)
        divider = QFrame(panel)
        divider.setFrameShape(QFrame.HLine)
        layout.addWidget(divider)
        transfer_title = QLabel(translate('CPU transfers'), panel)
        layout.addWidget(transfer_title)
        transfers = QHBoxLayout()
        self.transfer_values = {}
        for key, title in [('readbacks', 'Readbacks'), ('uploads', 'Uploads'), ('image_sources', 'Image requests')]:
            column = QVBoxLayout()
            number = QLabel('—', panel)
            number.setStyleSheet('font-size: 19px; font-weight: 600;')
            caption = QLabel(translate(title), panel)
            caption.setStyleSheet('color: palette(mid); font-size: 11px;')
            column.addWidget(number)
            column.addWidget(caption)
            transfers.addLayout(column, 1)
            self.transfer_values[key] = number
        layout.addLayout(transfers)
        self.details = QLabel(panel)
        self.details.setWordWrap(True)
        self.details.setTextFormat(Qt.PlainText)
        self.details.setStyleSheet('color: palette(mid); font-size: 11px;')
        layout.addWidget(self.details)
        self.reason_bars = []
        for _ in range(5):
            row = QWidget(panel)
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            label = QLabel(row)
            label.setStyleSheet('font-size: 11px;')
            bar = GpuWorkBar(row, readback=True)
            row_layout.addWidget(label)
            row_layout.addWidget(bar)
            layout.addWidget(row)
            self.reason_bars.append((row, label, bar))
        layout.addStretch()
        scroll = QScrollArea(self)
        scroll.setObjectName('gpuMetricsScroll')
        scroll.setAutoFillBackground(False)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(surface)
        scroll.viewport().setAutoFillBackground(False)
        surface.setAutoFillBackground(False)
        panel.setAutoFillBackground(False)
        self.setWidget(scroll)
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.refresh)
        self.visibilityChanged.connect(lambda visible: self.timer.start() if visible else self.timer.stop())
        self.refresh()

    def reset(self):
        self.measurements.reset()
        self.refresh()

    def refresh(self):
        raw = self.measurements.snapshot()
        available = raw.get('native_available', True)
        self.notice.setText(self.translate('Native work counters are unavailable in the loaded library. Rebuild libopenshot and restart OpenShot. Display measurements remain available.'))
        self.notice.setVisible(not available)
        for widget, row in zip(self.stage_rows, stages(raw)):
            widget.set_stage(row)
        for key, label in self.transfer_values.items():
            label.setText(str(raw.get(key, 0)) if available else '—')
        reasons = sorted(((reason, count) for reason, count in raw.get('readback_reasons', {}).items() if count),
                         key=lambda item: -item[1])
        for index, (widget, label, bar) in enumerate(self.reason_bars):
            widget.setVisible(index < len(reasons))
            if index < len(reasons):
                reason, count = reasons[index]
                label.setText('%s: %s' % (self.translate(reason), count))
                bar.set_percent(100 * count / max(1, raw.get('readbacks', count)))
        self.details.setText(self.translate('Image sources are expected CPU-origin work, not GPU decode failures.') if available else '')
        if reasons:
            self.details.setText(self.details.text() + '\n' + self.translate('Readback causes'))
        self.setToolTip(self.translate('Green bar = GPU path; amber = CPU path. Copy-free shows GPU work without readback. Counts exclude repeated cached work.'))


class GpuPreviewSegments(GpuSegments):
    def __init__(self, measurements, translate, window, parent=None):
        super().__init__(translate, parent)
        self.measurements, self.window = measurements, window
        self.setCursor(Qt.PointingHandCursor)
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    def refresh(self):
        self.set_snapshot(self.measurements.snapshot())
        self.setToolTip(self.toolTip() + '\n' + self.translate('Click to open GPU Inspector.'))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            dock = getattr(self.window, 'gpuMetricsDock', None)
            if dock is None:
                dock = self.window.gpuMetricsDock = GpuMetricsDock(self.measurements, self.translate, self.window)
                self.window.addDockWidget(Qt.RightDockWidgetArea, dock)
            dock.show()
            dock.raise_()
        super().mouseReleaseEvent(event)
