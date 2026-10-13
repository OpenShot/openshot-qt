"""Explicit source-range editing shared by Preview and Split File."""

import importlib
import copy
import os
import uuid

from qt_api import Qt, QLabel, QTimer, QDialogButtonBox, QSizePolicy, QPixmap, QUrl, QT_API
from classes.app import get_app
from classes.query import Clip, File
from classes.thumbnail import FindCachedThumbnail
from windows.views.source_ruler import SourceRuler
from windows.views.timeline_backend.qwidget.timecode import TimecodeLineEdit


class SourceTimecodeEdit(TimecodeLineEdit):
    """Use source-preview punctuation while retaining the timeline parser."""
    def format_frame(self, frame):
        return super().format_frame(frame).replace(',', '.')

    def parse_text(self, text=None):
        return super().parse_text((self.text() if text is None else text).replace('.', ','))

    def set_current_frame_text(self, frame):
        # Range refreshes run synchronously during segment stepping. Preserve
        # the user's segment/caret instead of moving it to the frames suffix.
        cursor = self.cursorPosition()
        start = self.selectionStart()
        length = len(self.selectedText())
        focused = self.hasFocus()
        super().set_current_frame_text(frame)
        if focused:
            if start >= 0 and length:
                if cursor == start:
                    self.setSelection(start+length, -length)
                else:
                    self.setSelection(start, length)
            else:
                self.setCursorPosition(cursor)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # These are permanent dialog fields, not the timeline's popup editor.
            self.commit()
            event.accept()
            return
        super().keyPressEvent(event)


class SourceRangeMixin:
    def _setup_source_range(self):
        _ = get_app()._tr
        old_slider = self.sliderVideo
        self.sliderVideo = SourceRuler(self)
        self.sliderVideo.ruler_fps = {'num': self.fps_num, 'den': self.fps_den}
        self.sliderVideo.setRange(1, self.video_length)
        self.verticalLayout.removeWidget(old_slider)
        old_slider.hide()
        old_slider.deleteLater()
        self.verticalLayout.insertWidget(self.verticalLayout.indexOf(self.widgetControls), self.sliderVideo)
        self.widgetControls.show()
        self.timeLayout.addStretch()
        self.loopLayout.insertStretch(0)
        for label in (self.lblVideoTime, self.lblSourceDuration):
            label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.txtName.setMaximumWidth(280)
        self.lblInstructions.hide()
        self.lblInstructions.setTextFormat(Qt.PlainText)
        self.btnStart.setMinimumSize(0, 0)
        self.btnEnd.setMinimumSize(0, 0)
        self.btnStart.setText(_('Set'))
        self.btnEnd.setText(_('Set'))
        self.btnStart.setToolTip(_('Set Start to the current frame (I)'))
        self.btnEnd.setToolTip(_('Set End to the current frame, included in the range (O)'))
        self.btnEnd.setEnabled(True)
        self._range_thumb_frames = {}
        self._range_thumb_replies = {}
        self._range_thumb_timer = QTimer(self)
        self._range_thumb_timer.setSingleShot(True)
        self._range_thumb_timer.setInterval(180)
        self._range_thumb_timer.timeout.connect(self._refresh_range_thumbnails)
        self._range_thumb_network = None
        self.btnClear.setText(_('Reset'))
        self.btnClear.setEnabled(True)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Close)
        self.buttonBox.button(QDialogButtonBox.Close).setToolTip(_('Close without applying pending range changes.'))

        self.range_file_id = self.file.id
        self.range_source_data = copy.deepcopy(self.file.data)
        initial_start = float(self.file.data.get('start', 0) or 0)
        initial_end = float(self.file.data.get('end', self.video_length / self.fps))
        trimmed_file = (bool(self.file.data.get('is_split_file')) or initial_start > 0
                        or initial_end < (self.video_length-1) / self.fps)
        self.range_mode = 'clip' if self.range_clip_id else ('preview' if self.is_preview_mode else ('file' if trimmed_file else 'create'))
        target = self._range_target()
        self._range_baseline = self._range_signature(target)
        self._range_editable = True
        self._range_error = ''
        self._range_applying = False
        self.range_dirty = False
        self.range_edits = {}
        for edge, label in (('in', _('Start')), ('out', _('End'))):
            edit = SourceTimecodeEdit(self)
            edit.setObjectName('sourceRangeTime')
            edit.setFrame(True)
            edit.set_context(self.fps_num, self.fps_den, 1)
            edit.setAccessibleName(label)
            edit.setToolTip(_('End is the last included frame.') if edge == 'out' else _('First included source frame.'))
            edit.setFixedWidth(edit.fontMetrics().horizontalAdvance('00:00:00,00') + 24)
            edit.frameCommitted.connect(lambda frame, _preroll, _force, edge=edge: self.sliderVideo.move_edge(edge, frame))
            edit.editCanceled.connect(self._refresh_range_labels)
            edit.show()
            self.range_edits[edge] = edit
            (self.startFields if edge == 'in' else self.endFields).insertWidget(0, edit)
        old_duration = self.range_duration
        self.range_duration = SourceTimecodeEdit(self)
        self.range_duration.setFrame(True)
        self.range_duration.setObjectName('sourceRangeDuration')
        self.range_duration.set_context(self.fps_num, self.fps_den, 1)
        self.range_duration.setAccessibleName(_('Duration'))
        self.range_duration.setToolTip(_('Change End while keeping Start fixed. Limited to the remaining source duration.'))
        self.range_duration.setFixedWidth(self.range_duration.fontMetrics().horizontalAdvance('00:00:00.00') + 8)
        self.range_duration.frameCommitted.connect(self._duration_committed)
        self.range_duration.editCanceled.connect(self._refresh_range_labels)
        self.durationColumn.replaceWidget(old_duration, self.range_duration)
        old_duration.hide()
        old_duration.deleteLater()
        self.range_duration.show()
        self.range_status = QLabel(self)
        self.range_status.setWordWrap(True)
        self.verticalLayout.insertWidget(self.verticalLayout.count() - 1, self.range_status)
        self.range_status.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.widgetControls.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.txtName.setVisible(self.range_mode == 'create')
        self.label.hide()
        self.txtName.setAccessibleName(_('Split file name'))
        self.btnAddClip.setText({'clip': _('Update Clip'), 'file': _('Update'),
                                 'create': _('Create'), 'preview': _('Preview')}[self.range_mode])
        self.btnStart.setAccessibleName(_('Set Start to playhead'))
        self.btnEnd.setAccessibleName(_('Set End to playhead'))
        self.btnRangeStart.clicked.connect(lambda: self._seek_range_edge('in'))
        self.btnRangeEnd.clicked.connect(lambda: self._seek_range_edge('out'))
        self.btnAddClip.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self._style_range_controls()
        tab_order = [self.sliderVideo, self.range_edits['in'], self.range_edits['out'], self.range_duration]
        if self.range_mode in ('create', 'file'):
            tab_order.append(self.txtName)
        tab_order.extend((self.btnClear, self.btnAddClip))
        for previous, following in zip(tab_order, tab_order[1:]):
            self.setTabOrder(previous, following)
        self.sliderVideo.rangeEditStarted.connect(lambda: self.btnPlay_clicked(force='pause'))
        self.sliderVideo.rangeEdited.connect(self._source_range_edited)
        self._reset_source_range()
        self.txtName.textChanged.connect(lambda: self._source_range_edited(self.start_frame, self.end_frame))
        if self.range_mode != 'create' or trimmed_file:
            self._preview_autoplay_active = False
        self._preview_initial_frame = self.start_frame
        self._range_timer = QTimer(self)
        self._range_timer.setInterval(350)
        self._range_timer.timeout.connect(self._check_range_target)
        self._range_timer.start()
        self._save_feedback_timer = QTimer(self)
        self._save_feedback_timer.setSingleShot(True)
        self._save_feedback_timer.timeout.connect(lambda: self.btnAddClip.setText(
            _('Create') if self.range_mode == 'create' else _('Update')))


    def _seek_range_edge(self, edge):
        self.sliderVideo.setValue(self.start_frame if edge == 'in' else self.end_frame)

    def _style_range_controls(self):
        from windows.preview_design import build_preview_design
        build_preview_design(self)

    def _range_target(self):
        if self.range_mode == 'clip':
            return Clip.get(id=self.range_clip_id)
        return File.get(id=self.range_file_id)

    @staticmethod
    def _range_signature(target):
        if target is None:
            return None
        return tuple(target.data.get(key) for key in ('file_id', 'start', 'end', 'name'))

    def _reset_source_range(self):
        target = self._range_target()
        if target is None:
            self._check_range_target()
            return
        data = target.data
        first = round(float(data.get('start', 0) or 0) * self.fps) + 1
        last = round(float(data.get('end', self.video_length / self.fps)) * self.fps)
        self.sliderVideo.set_region(first, last)
        self._range_baseline = self._range_signature(target)
        self.range_dirty = False
        self.txtName.blockSignals(True)
        self.txtName.setText(data.get('name', '') if self.range_mode == 'file' else '')
        self.txtName.blockSignals(False)
        self._refresh_range_labels()
        self._check_range_target()

    def _source_range_edited(self, first, last):
        if self.btnPlay.isChecked() and (first, last) != (self.start_frame, self.end_frame):
            self.btnPlay_clicked(force='pause')
        baseline = self._range_baseline
        self.range_dirty = baseline is None or (first, last) != (
            round(float(baseline[1] or 0) * self.fps) + 1,
            round(float(baseline[2] or self.video_length / self.fps) * self.fps))
        if self.range_mode == 'file' and baseline:
            self.range_dirty |= self.txtName.text().strip() != (baseline[3] or '')
        self._refresh_range_labels()
        self._check_range_target()

    def _refresh_range_labels(self):
        self.start_frame, self.end_frame = self.sliderVideo.in_frame, self.sliderVideo.out_frame
        for edge, frame in (('in', self.start_frame), ('out', self.end_frame)):
            self.range_edits[edge].set_current_frame_text(frame)
        self._range_thumb_timer.start()
        duration = self.end_frame - self.start_frame + 1
        self.range_duration.set_current_frame_text(duration + 1)
        self.lblSourceDuration.setText('/ ' + self.range_edits['in'].format_frame(self.video_length))

    def _duration_committed(self, frame, _preroll, _force):
        # Timecode editors use one-based frame positions; duration is a count.
        duration = max(1, int(frame)-1)
        last = min(self.sliderVideo.maximum(), self.sliderVideo.in_frame+duration-1)
        self.sliderVideo.move_edge('out', last)
        # A clamped value may leave the range unchanged, so refresh explicitly.
        self._refresh_range_labels()

    def _refresh_range_thumbnails(self):
        """Load cached filmstrip samples first; request only missing thumbnails."""
        frames = list(dict.fromkeys(1 + round(i * (self.video_length - 1) / 11) for i in range(12)))
        self.sliderVideo.filmstrip_frames = frames
        fps_data = self.range_source_data.get('fps') or {}
        fps = float(fps_data.get('num') or 0) / float(fps_data.get('den') or 1)
        for frame in frames:
            if frame in self._range_thumb_frames or frame in self._range_thumb_replies:
                continue
            path = FindCachedThumbnail(self.range_file_id, frame, fps)
            if path:
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    self.sliderVideo.filmstrip_images[frame] = pixmap
                    self._range_thumb_frames[frame] = True
        self.sliderVideo.update()
        missing = [frame for frame in frames
                   if frame not in self._range_thumb_frames and frame not in self._range_thumb_replies]
        if not missing:
            return
        server = getattr(get_app().window, 'http_server_thread', None)
        if not server:
            return
        if self._range_thumb_network is None:
            binding = {'pyqt5': 'PyQt5', 'pyqt6': 'PyQt6', 'pyside6': 'PySide6'}[QT_API]
            self._range_thumb_module = importlib.import_module(binding + '.QtNetwork')
            self._range_thumb_network = self._range_thumb_module.QNetworkAccessManager(self)
        host, port = server.server_address
        # A small, fixed sample set keeps requests bounded and survives resizing.
        # Use the same cached source thumbnails as Project Files and the timeline.
        for frame in missing:
            if len(self._range_thumb_replies) >= 2:
                break
            self._range_thumb_frames[frame] = True
            url = QUrl('http://%s:%s/thumbnails/%s/%s/' % (host, port, self.range_file_id, frame))
            reply = self._range_thumb_network.get(self._range_thumb_module.QNetworkRequest(url))
            self._range_thumb_replies[frame] = reply
            reply.finished.connect(lambda frame=frame, reply=reply: self._range_thumbnail_ready(frame, reply))

    def _range_thumbnail_ready(self, frame, reply):
        if self._range_thumb_replies.get(frame) is reply:
            self._range_thumb_replies.pop(frame)
            pixmap = QPixmap()
            if pixmap.loadFromData(bytes(reply.readAll())):
                self.sliderVideo.filmstrip_images[frame] = pixmap
                self.sliderVideo.update()
            self._range_thumb_timer.start(0)
        reply.deleteLater()

    def _stop_range_thumbnails(self):
        self._range_thumb_timer.stop()
        replies = list(self._range_thumb_replies.values())
        self._range_thumb_replies.clear()
        for reply in replies:
            reply.abort()

    def _check_range_target(self):
        if self._range_applying:
            return
        _ = get_app()._tr
        theme = getattr(get_app().window.timeline, 'theme', self.sliderVideo.theme)
        if self.sliderVideo.theme is not theme:
            self.sliderVideo._refresh_theme()
        target = self._range_target()
        error = ''
        if target is None:
            error = _('The target no longer exists in this project.')
        elif self.range_mode == 'clip':
            if target.data.get('file_id') != self.range_file_id:
                error = _('This clip now uses a different source. Reopen its preview.')
            elif get_app().window.timeline._is_track_locked(target.data.get('layer')):
                error = _('The clip is on a locked track. Unlock it to apply a range.')
            else:
                points = (target.data.get('time') or {}).get('Points', [])
                if len(points) > 1 or any(p.get('co', {}).get('Y', 1) != 1 for p in points):
                    error = _('Retimed clip: range preview is available; applying a range is not supported.')
        if not error and self._range_signature(target) != self._range_baseline:
            if self.range_dirty:
                error = _('The saved range changed elsewhere. Reset Range to reload it before applying.')
            else:
                self._reset_source_range()
                return
        self._range_error = error
        name = self.range_source_data.get('name') or os.path.basename(self.range_source_data.get('path', ''))
        if self.range_mode == 'clip':
            title = (target.data.get('title') if target else None) or name
            if target:
                timeline = get_app().window.timeline
                track = next((t for t in getattr(timeline, 'track_list', [])
                              if t.data.get('number') == target.data.get('layer')), None)
                if track:
                    title += ' — ' + timeline._track_display_label(track)
                title += _(' at %.3f s') % float(target.data.get('position', 0))
            self.lblInstructions.setText(_('Timeline clip: %s') % title)
            self.setWindowTitle(_('Preview'))
            detail = _('Only this clip changes. Its timeline position stays fixed; neighboring clips do not move.')
        elif self.range_mode == 'file':
            self.lblInstructions.setText(_('Split file: %s') % name)
            detail = _('Updates this Project Files entry. Existing timeline clips keep their current ranges.')
        else:
            self.lblInstructions.setText(_('Source: %s') % name)
            detail = _('Mark a range to create a new Project Files entry. The source file is unchanged.')
        self.range_status.setText(error)
        self.range_status.setVisible(bool(self.range_status.text()))
        self.btnAddClip.setToolTip(detail)
        self.sliderVideo.setToolTip(self.lblInstructions.text() + '\n' + self.range_duration.text()
                                    + '\n' + _('Drag handles to trim, drag the selected filmstrip to move the range, or drag outside it to draw a new range. Click to seek; drag the ruler to scrub.'))
        self.btnAddClip.setEnabled(not error and (self.range_mode == 'create' or self.range_dirty))

    def _save_source_range(self):
        if self.range_mode == 'preview':
            return
        self._check_range_target()
        if self._range_error or not self.btnAddClip.isEnabled():
            return
        app = get_app()
        target = self._range_target()
        start, end = (self.start_frame-1) / self.fps, self.end_frame / self.fps
        self._range_applying = True
        previous_transaction = app.updates.transaction_id
        transaction = str(uuid.uuid4())
        try:
            if self.range_mode == 'clip':
                data = dict(target.data, start=start, end=end, duration=end-start)
                app.window.timeline.update_clip_data(data, only_basic_props=True, ignore_reader=True,
                                                     transaction_id=transaction)
            else:
                app.updates.transaction_id = transaction
                if self.range_mode == 'create':
                    target = File()
                    target.data = copy.deepcopy(self.range_source_data)
                    target.data.pop('id', None)
                    name = self.txtName.text().strip()
                    if not name:
                        base = os.path.splitext(os.path.basename(self.file_path))[0]
                        name = '%s (%s to %s)' % (base, self.range_edits['in'].format_frame(self.start_frame),
                                                 self.range_edits['out'].format_frame(self.end_frame))
                    target.data['name'] = name
                if self.range_mode == 'file' and ('name' in target.data or self.txtName.text().strip()):
                    target.data['name'] = self.txtName.text().strip()
                target.data.update(start=start, end=end)
                target.data['is_split_file'] = True
                target.save()
            self.range_dirty = False
            self._range_baseline = self._range_signature(self._range_target())
        finally:
            app.updates.transaction_id = previous_transaction
            self._range_applying = False
        self._check_range_target()
        if self.range_mode == 'create':
            self.txtName.clear()
            self.btnAddClip.setToolTip(app._tr('Split file created. Adjust the range to create another.'))
        if self.range_mode in ('create', 'file'):
            self.btnAddClip.setText(app._tr('Created') if self.range_mode == 'create' else app._tr('Saved'))
            self._save_feedback_timer.start(1800)
        return True

    def playback_range(self):
        return self.start_frame, self.end_frame
