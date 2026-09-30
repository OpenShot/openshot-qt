"""
 @file
 @brief This file loads the animated title dialog (i.e Blender animation automation)
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2018 OpenShot Studios, LLC
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

import os
import uuid

from qt_api import Qt
from qt_api import (
    QApplication, QDialog, QDialogButtonBox, QPushButton, QLabel, QSizePolicy, QAbstractItemView
)

from classes import info, ui_util, metrics, tabstops
from classes.app import get_app
from classes.distribution import is_snap, blender_unavailable_message
from classes.logger import log
from windows.views.blender_listview import BlenderListView
from windows.notifications import banner_colors


class AnimatedTitle(QDialog):
    """ Animated Title Dialog """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'animated-title.ui')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Load UI from designer & init
        ui_util.load_ui(self, self.ui_path)
        ui_util.init_ui(self)
        self.setObjectName("animatedTitle")

        metrics.track_metric_screen("animated-title-screen")

        app = get_app()
        _ = app._tr
        self.blender_unavailable = is_snap()

        # Keep setup problems in the dialog, above the disabled editor.
        self.blenderNotice = QLabel(self)
        self.blenderNotice.setObjectName("blenderNotice")
        self.blenderNotice.setTextFormat(Qt.PlainText)
        self.blenderNotice.setWordWrap(False)
        self.blenderNotice.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        colors = banner_colors(self)
        self.blenderNotice.setStyleSheet(
            "QLabel#blenderNotice { background: %(surface)s; color: %(text)s; "
            "border: 1px solid %(border)s; border-radius: 4px; padding: 10px; }" % colors)
        self.gridLayout.addWidget(self.blenderNotice, 0, 0)
        self.gridLayout.setRowStretch(1, 1)
        self.blenderNotice.hide()

        # Add render controls
        self.btnRender = QPushButton(_('Render'))
        self.btnRender.setObjectName("acceptButton")
        self.btnCancel = QPushButton(_('Cancel'))
        self.btnCancel.setObjectName("cancelButton")
        self.buttonBox.addButton(self.btnRender, QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton(self.btnCancel, QDialogButtonBox.RejectRole)
        # Set focus policy after adding to buttonBox to prevent override
        self.btnRender.setFocusPolicy(Qt.StrongFocus)
        self.btnCancel.setFocusPolicy(Qt.StrongFocus)

        # Hide render progress until needed
        self.statusContainer.hide()

        # Add blender view
        self.blenderView = BlenderListView(self)
        self.verticalLayout.addWidget(self.blenderView)

        self.imgPreview.setFocusPolicy(Qt.NoFocus)
        self.scrollArea.setFocusPolicy(Qt.NoFocus)
        self.buttonBox.setFocusPolicy(Qt.NoFocus)
        self.splitter.setFocusPolicy(Qt.NoFocus)

        # Init variables
        self.unique_folder_name = str(uuid.uuid1())
        self.output_dir = info.BLENDER_PATH
        self.selected_template = ""
        self.is_rendering = False
        self.my_blender = None

        # Clear all child controls
        self.clear_effect_controls()

        self._apply_tab_order()
        if self.blender_unavailable:
            self.show_blender_error(blender_unavailable_message(_))

    def show_blender_error(self, message):
        """Leave templates visible and Cancel available when Blender cannot run."""
        self.blender_unavailable = True
        self.blenderView.preview_timer.stop()
        self.blenderNotice.setText(" ".join(message.split()))
        self.blenderNotice.show()
        # Disable the contents, not the scrollable views around them.
        self.blenderView.clearSelection()
        self.blenderView.selectionModel().clearCurrentIndex()
        self.blenderView.setSelectionMode(QAbstractItemView.NoSelection)
        self.blenderView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        model = self.blenderView.blender_model.model
        for row in range(model.rowCount()):
            for column in range(model.columnCount()):
                item = model.item(row, column)
                if item is not None:
                    item.setFlags(item.flags() & ~(Qt.ItemIsEnabled | Qt.ItemIsSelectable))
        self.settingsContainer.setEnabled(False)
        self.sliderPreview.setEnabled(False)
        self.btnRefresh.setEnabled(False)
        self.btnRender.setEnabled(False)
        self.statusContainer.hide()
        self.btnCancel.setFocus()

    def _apply_tab_order(self):
        """Apply explicit tab order for animated title dialog."""
        from qt_api import QTimer

        def do_tab_order():
            # Force focus policies on buttons (something is resetting Cancel to NoFocus)
            self.btnCancel.setFocusPolicy(Qt.StrongFocus)
            self.btnRender.setFocusPolicy(Qt.StrongFocus)

            ordered = []
            if getattr(self, "blenderView", None):
                ordered.append(self.blenderView)
            ordered.extend([self.sliderPreview, self.btnRefresh])
            ordered.extend(
                tabstops.collect_focusable_from_layout(
                    self.settingsContainer.layout(),
                    self,
                    include_hidden=True,
                    include_disabled=True,
                )
            )
            ordered.extend([self.btnCancel, self.btnRender])

            # Apply tab order directly
            for first, second in zip(ordered, ordered[1:]):
                tabstops.safe_set_tab_order(first, second)
            if len(ordered) >= 2:
                tabstops.safe_set_tab_order(ordered[-1], ordered[0])

        QTimer.singleShot(0, do_tab_order)

    def accept(self):
        """ Start rendering animation, but don't close window """
        if self.blender_unavailable:
            return
        # Render
        self.blenderView.Render()

    def closeEvent(self, event):
        """ Actually close window and accept dialog """
        self.blenderView.Cancel()
        self.blenderView.end_processing()
        super().accept()

    def reject(self):
        # Stop threads
        self.blenderView.Cancel()
        self.blenderView.end_processing()
        super().reject()

    def clear_effect_controls(self):
        """ Clear all child widgets used for settings """
        self.statusContainer.hide()

        # Loop through child widgets
        for child in self.settingsContainer.children():
            try:
                self.settingsContainer.layout().removeWidget(child)
                child.deleteLater()
            except Exception:
                log.debug('Failed to remove child widget for effect controls')
