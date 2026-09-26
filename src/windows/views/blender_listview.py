"""
 @file
 @brief This file contains the blender file listview, used by the 3d animated titles screen
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
import subprocess
import sys
import re
import functools
import shlex
import json
from time import sleep, monotonic
import signal
import tempfile

# Try to get the security-patched XML functions from defusedxml
try:
    from defusedxml import minidom as xml
except ImportError:
    from xml.dom import minidom as xml

from qt_api import (
    Qt, QObject, pyqtSlot, pyqtSignal, QThread, QTimer, QSize,
)
from qt_api import (
    QApplication, QListView, QMessageBox,
    QComboBox, QDoubleSpinBox, QLabel, QPushButton, QLineEdit, QPlainTextEdit,
)
from qt_api import QColor, QImage, QPixmap, QIcon

from classes import info
from classes.logger import log
from classes.query import File
from classes.app import get_app
from classes.feedback import record_feedback_action

from windows.models.blender_model import BlenderModel
from windows.color_picker import ColorPicker


class BlenderListView(QListView):
    """ A ListView QWidget used on the animated title window """

    # Our signals
    start_render = pyqtSignal(str, str, int)

    def currentChanged(self, selected, deselected):
        # Get selected item
        self.selected = selected
        self.deselected = deselected

        if not selected or not selected.isValid():
            return
        if getattr(self, "_last_selected_index", None) == selected:
            return

        # Get translation object
        _ = self.app._tr

        animation = self.get_animation_details()
        self.selected_template = animation.get("service")

        # In newer versions of Qt, setting the model invokes the currentChanged signal,
        # but the selection is -1. So, just do nothing here.
        if not self.selected_template:
            return

        self._last_selected_index = selected
        self.win.clear_effect_controls()

        # Assign a new unique id for each template selected
        self.generateUniqueFolder()

        # Loop through params
        for param in animation.get("params", []):
            log.debug('Using parameter %s: %s' % (param["name"], param["title"]))

            # Is Hidden Param?
            if param["name"] in ["start_frame", "end_frame"]:
                # add value to dictionary
                self.params[param["name"]] = int(param["default"])
                # skip to next param without rendering a control
                continue

            widget = None
            label = QLabel()
            label.setText(_(param["title"]))
            label.setToolTip(_(param["title"]))

            if param["type"] == "spinner":
                # add value to dictionary
                self.params[param["name"]] = float(param["default"])

                # create spinner
                widget = QDoubleSpinBox()
                widget.setMinimum(float(param["min"]))
                widget.setMaximum(float(param["max"]))
                widget.setValue(float(param["default"]))
                widget.setSingleStep(0.01)
                widget.setToolTip(param["title"])
                widget.valueChanged.connect(functools.partial(self.spinner_value_changed, param))

            elif param["type"] == "text":
                # add value to dictionary
                self.params[param["name"]] = _(param["default"])

                # create spinner
                widget = QLineEdit()
                widget.setText(_(param["default"]))
                widget.textChanged.connect(functools.partial(self.text_value_changed, widget, param))

            elif param["type"] == "multiline":
                # add value to dictionary
                self.params[param["name"]] = _(param["default"])

                # create spinner
                widget = QPlainTextEdit()
                widget.setPlainText(_(param["default"]).replace("\\n", "\n"))
                widget.textChanged.connect(functools.partial(self.text_value_changed, widget, param))

            elif param["type"] == "dropdown":
                # add value to dictionary
                self.params[param["name"]] = param["default"]

                # create spinner
                widget = QComboBox()
                widget.currentIndexChanged.connect(functools.partial(self.dropdown_index_changed, widget, param))

                # Add values to dropdown
                if "project_files" in param["name"]:
                    # override files dropdown
                    param["values"] = {}
                    for file in File.filter():
                        if file.data["media_type"] not in ("image", "video"):
                            continue

                        fileName = os.path.basename(file.data["path"])
                        fileExtension = os.path.splitext(fileName)[1]

                        if fileExtension.lower() in (".svg"):
                            continue

                        param["values"][fileName] = "|".join(
                            (file.data["path"],
                             str(file.data["height"]),
                             str(file.data["width"]),
                             file.data["media_type"],
                             str(file.data["fps"]["num"] / file.data["fps"]["den"])
                             )
                        )

                # Add normal values
                for i, (k, v) in enumerate(sorted(param["values"].items())):
                    # add dropdown item
                    widget.addItem(_(k), v)

                    # select dropdown (if default)
                    if v == param["default"]:
                        widget.setCurrentIndex(i)

                if not param["values"]:
                    widget.addItem(_("No Files Found"), "")
                    widget.setEnabled(False)

            elif param["type"] == "color":
                # add value to dictionary
                color = QColor(param["default"])
                self.params[param["name"]] = [color.redF(), color.greenF(), color.blueF()]
                if "diffuse_color" in param.get("name"):
                    self.params[param["name"]].append(color.alphaF())
                widget = QPushButton()
                widget.setText("")
                widget.setStyleSheet("background-color: {}".format(param["default"]))
                widget.clicked.connect(functools.partial(self.color_button_clicked, widget, param))

            # Add Label and Widget to the form
            if (widget and label):
                self.win.settingsContainer.layout().addRow(label, widget)
            elif (label):
                self.win.settingsContainer.layout().addRow(label)

        self.end_processing()
        self.init_slider_values()

        if hasattr(self.win, "_apply_tab_order"):
            self.win._apply_tab_order()

    def spinner_value_changed(self, param, value):
        self.params[param["name"]] = value
        log.info('Animation param %s set to %s' % (param["name"], value))

    def text_value_changed(self, widget, param, value=None):
        try:
            # Attempt to load value from QPlainTextEdit (i.e. multi-line)
            if not value:
                value = widget.toPlainText()
        except Exception:
            log.debug('Failed to read plain text value from widget')
            return
        self.params[param["name"]] = value
        # XXX: This will log every individual KEYPRESS in the text field.
        # log.info('Animation param %s set to %s' % (param["name"], value))

    def dropdown_index_changed(self, widget, param, index):
        value = widget.itemData(index)
        self.params[param["name"]] = value
        log.info('Animation param %s set to %s' % (param["name"], value))
        if param["name"] == "length_multiplier":
            # Convert value to float (and multiply with project FPS diff)
            # This converts all length_multipliers to the correct project FPS reference.
            # For example, a 1X multiplier would be 1.2X for a 30 FPS project
            # using a 25 FPS animated title - to scale up to the correct # of frames.
            self.params[param["name"]] = float(value) * self.project_fps_diff
            self.init_slider_values()

    def color_button_clicked(self, widget, param, index):
        # Get translation object
        _ = get_app()._tr

        color_value = self.params[param["name"]]
        currentColor = QColor("#FFFFFF")
        if len(color_value) >= 3:
            alpha = color_value[3] if len(color_value) >= 4 else 1.0
            currentColor.setRgbF(color_value[0], color_value[1], color_value[2], alpha)
        # Store our arguments for the callback to pick up again
        self._color_scratchpad = (widget, param)
        ColorPicker(currentColor, callback=self.color_selected, parent=self.win)

    @pyqtSlot(QColor)
    def color_selected(self, newColor):
        """Callback when the user chooses a color in the dialog"""
        if not self._color_scratchpad:
            log.warning("ColorPicker callback called without parameter to set")
            return
        (widget, param) = self._color_scratchpad
        if not newColor or not newColor.isValid():
            return
        widget.setStyleSheet("background-color: {}".format(newColor.name()))
        self.params[param["name"]] = [
            newColor.redF(), newColor.greenF(), newColor.blueF()
            ]
        if "diffuse_color" in param.get("name"):
            self.params[param["name"]].append(newColor.alphaF())
        log.info('Animation param %s set to %s', param["name"], newColor.name())

    def generateUniqueFolder(self):
        """ Generate a new, unique folder name to contain Blender frames """

        # Assign a new unique id for each template selected
        self.unique_folder_name = str(self.app.project.generate_id())

        # Create a folder (if it does not exist)
        if not os.path.exists(os.path.join(info.BLENDER_PATH, self.unique_folder_name)):
            os.mkdir(os.path.join(info.BLENDER_PATH, self.unique_folder_name))

    def processing_mode(self, cursor=True, restore_focus=True):
        """ Disable all controls on interface """

        # Store keyboard-focused widget when we plan to restore it
        self.focus_owner = self.win.focusWidget() if restore_focus else None

        self.win.btnRefresh.setEnabled(False)
        self.win.sliderPreview.setEnabled(False)
        self.win.btnRender.setEnabled(False)

        # Show 'Wait' cursor
        if cursor:
            get_app().window.WaitCursorSignal.emit(True)

    @pyqtSlot()
    def end_processing(self):
        """ Enable all controls on interface """
        self.win.btnRefresh.setEnabled(True)
        self.win.sliderPreview.setEnabled(True)
        self.win.btnRender.setEnabled(True)
        self.win.statusContainer.hide()

        # Restore normal cursor and keyboard focus
        get_app().window.WaitCursorSignal.emit(False)
        if self.focus_owner:
            self.focus_owner.setFocus()

    def init_slider_values(self):
        """ Init the slider and preview frame label to the currently selected animation """

        # Get current preview slider frame
        length = int(self.params.get("end_frame", 1) * self.params.get("length_multiplier", 1.0))

        # Update the preview slider
        middle_frame = int(length / 2)

        self.win.sliderPreview.setMinimum(self.params.get("start_frame", 1))
        self.win.sliderPreview.setMaximum(length)
        self.win.sliderPreview.setValue(middle_frame)

        # Trigger a refresh of the preview
        self.preview_timer.start()

    @pyqtSlot()
    def render_finished(self):
        # Don't try to capture image sequences for preview frames
        if not self.final_render or self.worker is None or self.worker.canceled:
            return

        # Compose image sequence data
        filename = "{}%04d.png".format(self.params["file_name"])
        seq_params = {
            "folder_path": os.path.join(info.BLENDER_PATH, self.unique_folder_name),
            "base_name": self.params["file_name"],
            "fixlen": True,
            "digits": 4,
            "extension": "png",
            "fps": {
                "num": self.fps.get("num", 25),
                "den": self.fps.get("den", 1)
            },
            "pattern": filename,
            "path": os.path.join(os.path.join(info.BLENDER_PATH, self.unique_folder_name), filename)
        }
        log.info('RENDER FINISHED! Adding to project files: {}'.format(filename))

        # Add to project files
        get_app().window.files_model.add_files(seq_params.get("path"), seq_params, prevent_recent_folder=True)
        if not self.worker.canceled and self.worker.process.returncode == 0:
            record_feedback_action("titles")

        # We're done here
        self.win.close()

    @pyqtSlot(str)
    def render_stage(self, stage=None):
        _ = get_app()._tr
        self.win.frameProgress.setRange(0, 0)
        self.win.frameStatus.setText(_("Generating"))
        log.debug("Set Blender progress to Generating step")

    @pyqtSlot(int, int)
    def render_progress(self, step_value, step_max):
        _ = get_app()._tr
        self.win.frameProgress.setRange(0, step_max)
        self.win.frameProgress.setValue(step_value)
        self.win.frameStatus.setText(_("Rendering"))
        log.debug(
            "set Blender progress to Rendering step, %d of %d complete",
            step_value, step_max)

    @pyqtSlot(int)
    def render_saved(self, frame=None):
        _ = get_app()._tr
        self.win.frameProgress.setValue(self.win.frameProgress.maximum() + 1)
        self.win.frameStatus.setText(_("Saved"))
        log.debug("Set Blender progress to Saved step")

    @pyqtSlot()
    def render_initialize(self):
        _ = get_app()._tr
        self.win.frameProgress.setRange(0, 0)
        self.win.frameStatus.setText(_("Initializing"))
        self.win.statusContainer.show()
        log.debug("Set Blender progress to Initializing step")

    @pyqtSlot(int)
    def update_progress_bar(self, current_frame):

        # update label and preview slider
        was_blocked = self.win.sliderPreview.blockSignals(True)
        self.win.sliderPreview.setValue(current_frame)
        self.win.sliderPreview.blockSignals(was_blocked)

        length = int(self.params.get("end_frame", 1) * self.params.get("length_multiplier", 1.0))
        self.win.lblFrame.setText("{}/{}".format(current_frame, length))

    @pyqtSlot(int)
    def sliderPreview_valueChanged(self, new_value):
        """Get new value of preview slider, and start timer to Render frame"""
        if self.win.sliderPreview.isEnabled():
            self.preview_timer.start()

        # Update preview label
        length = int(self.params.get("end_frame", 1) * self.params.get("length_multiplier", 1.0))
        self.win.lblFrame.setText("{}/{}".format(new_value, length))

    def preview_timer_onTimeout(self):
        """Timer is ready to Render frame"""
        # Update preview label
        preview_frame_number = self.win.sliderPreview.value()
        log.info('Previewing frame %s' % preview_frame_number)

        # Render current frame
        self.Render(preview_frame_number)

    def get_animation_details(self):
        """ Build a dictionary of all animation settings and properties from XML """

        # Get current selection (if any)
        current = self.selectionModel().currentIndex()
        if not current.isValid():
            return {}

        # Get all selected rows items
        animation_title = current.sibling(current.row(), 1).data(Qt.DisplayRole)
        xml_path = current.sibling(current.row(), 2).data(Qt.DisplayRole)
        service = current.sibling(current.row(), 3).data(Qt.DisplayRole)

        # load xml effect file
        xmldoc = xml.parse(xml_path)

        # Get list of params
        animation = {"title": animation_title, "path": xml_path, "service": service, "params": []}

        # Loop through params
        for param in xmldoc.getElementsByTagName("param"):
            # Set up item dict, "default" key is required
            param_item = {"default": ""}

            # Get details of param
            for att in ["title", "description", "name", "type"]:
                if param.attributes[att]:
                    param_item[att] = param.attributes[att].value

            for tag in ["min", "max", "step", "digits", "default"]:
                for p in param.getElementsByTagName(tag):
                    if p.childNodes:
                        param_item[tag] = p.firstChild.data

            try:
                # Build values dict from list of (name, num) tuples
                param_item["values"] = dict([
                    (p.attributes["name"].value, p.attributes["num"].value)
                    for p in param.getElementsByTagName("value") if (
                        "name" in p.attributes and "num" in p.attributes
                    )
                ])
            except (TypeError, AttributeError) as ex:
                log.warn("XML parser: %s", ex)
                pass

            # Append param object to list
            animation["params"].append(param_item)

        # Free up XML document memory
        xmldoc.unlink()

        # Return animation dictionary
        return animation

    def mousePressEvent(self, event):
        # Ignore event, propagate to parent
        event.ignore()
        super().mousePressEvent(event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        # Select first item when user tabs into the listview.
        if not self.selectionModel().hasSelection() and self.model().rowCount() > 0:
            first = self.model().index(0, 0)
            if first.isValid():
                self.setCurrentIndex(first)

    def refresh_view(self):
        self.blender_model.update_model()

        # Sort by column 0
        self.blender_model.proxy_model.sort(0)

    def get_project_params(self, is_preview=True):
        """ Return a dictionary of project related settings, needed by the Blender python script. """

        project = self.app.project
        project_params = {}

        # Append some project settings
        fps = project.get("fps")
        project_params["fps"] = fps["num"]
        if fps["den"] != 1:
            project_params["fps_base"] = fps["den"]

        project_params["resolution_x"] = project.get("width")
        project_params["resolution_y"] = project.get("height")

        if is_preview:
            project_params["resolution_percentage"] = 50
        else:
            project_params["resolution_percentage"] = 100
        project_params["quality"] = 100
        project_params["file_format"] = "PNG"
        project_params["color_mode"] = "RGBA"
        project_params["alpha_mode"] = 1
        project_params["horizon_color"] = (0.57, 0.57, 0.57)
        project_params["animation"] = True
        project_params["output_path"] = os.path.join(
            info.BLENDER_PATH,
            self.unique_folder_name,
            self.params["file_name"])

        # return the dictionary
        return project_params

    # Error from blender (with version number)
    @pyqtSlot(str)
    def onBlenderVersionError(self, version):
        self.error_with_blender(version, None)

    # Signal error from blender (with custom message)
    @pyqtSlot()
    @pyqtSlot(str)
    def onBlenderError(self, error=None):
        self.error_with_blender(None, error)

    def error_with_blender(self, version=None, worker_message=None):
        """ Show a friendly error message regarding the blender executable or version. """
        _ = self.app._tr
        s = self.app.get_settings()

        error_message = ""
        if version:
            error_message = _("Version Detected: {}").format(version)
            log.info("Blender version detected: {}".format(version))

        if worker_message:
            error_message = _("Error Output:\n{}").format(worker_message)
            log.error("Blender error: {}".format(worker_message))

        QMessageBox.critical(self, error_message,
            _("""
Blender, the free open source 3D content creation suite, is required for this action. (http://www.blender.org)

Please check the preferences in OpenShot and be sure the Blender executable is correct.
This setting should be the path of the 'blender' executable on your computer.
Also, please be sure that it is pointing to Blender version {} or greater.

Blender Path: {}
{}""").format(info.BLENDER_MIN_VERSION,
              s.get("blender_command"),
              error_message))

        # Close the blender interface
        self.win.close()

    def inject_params(self, source_path, out_path, frame=None):
        # determine if this is 'preview' mode?
        is_preview = False
        if frame:
            # if a frame is passed in, we are in preview mode.
            # This is used to turn the background color to off-white... instead of transparent
            is_preview = True

        # prepare string to inject
        user_params = "\n#BEGIN INJECTING PARAMS\n"

        param_data = json.loads(json.dumps(self.params))
        param_data.update(self.get_project_params(is_preview))

        param_serialization = json.dumps(param_data)
        user_params += 'params_json = r' + '"""{}"""'.format(
            param_serialization)

        user_params += "\n#END INJECTING PARAMS\n"

        # If GPU rendering is selected, see if GPU enable code is available
        s = self.app.get_settings()
        gpu_code_body = None
        if s.get("blender_gpu_enabled"):
            gpu_enable_py = os.path.join(info.PATH, "blender", "scripts", "gpu_enable.py.in")
            try:
                with open(gpu_enable_py, 'r') as f:
                    gpu_code_body = f.read()
                if gpu_code_body:
                    log.info("Injecting GPU enable code from {}".format(gpu_enable_py))
                    user_params += "\n#ENABLE GPU RENDERING\n"
                    user_params += gpu_code_body
                    user_params += "\n#END ENABLE GPU RENDERING\n"
            except IOError as e:
                log.error("Could not load GPU enable code! %s", e)

        # Read Python source from script file
        with open(source_path, 'r') as f:
            script_body = f.read()

        # Prepend shared helper library to every script (keeps templates lightweight)
        base_path = os.path.join(info.PATH, "blender", "scripts", "base.py.in")
        try:
            with open(base_path, 'r') as f:
                base_body = f.read()
            script_body = base_body + "\n\n" + script_body
        except IOError:
            log.error("Could not load base Blender helper script at %s", base_path)

        # insert our modifications to script source
        script_body = script_body.replace("# INJECT_PARAMS_HERE", user_params)

        # Write final script to output dir
        try:
            with open(out_path, "w", encoding="UTF-8", errors="strict") as f:
                f.write(script_body)
        except Exception:
            log.error("Could not write blender script to %s", out_path, exc_info=1)

    @pyqtSlot(str)
    def update_image(self, image_path):
        # Scale preview for high DPI display (if any)
        scale = get_app().devicePixelRatio()
        display_pixmap = QIcon(image_path).pixmap(self.win.imgPreview.size())
        display_pixmap.setDevicePixelRatio(scale)
        self.win.imgPreview.setPixmap(display_pixmap)

    def Cancel(self):
        """Cancel the current render, if any"""
        self.preview_timer.stop()
        background = getattr(self, "background", None)
        if background is not None:
            if background.isRunning():
                try:
                    self.worker.Cancel()
                except RuntimeError:
                    # The worker may already have completed and been deleted.
                    pass
                background.quit()
                # A QThread must finish before its owning dialog is destroyed.
                # Worker subprocess reads are bounded and cancellation kills the
                # process group, including during the version check.
                background.wait()
            background.deleteLater()
            self.background = None
            self.worker = None

    def Render(self, frame=None):
        """ Render an images sequence of the current template using Blender 2.62+ and the
        Blender Python API. """

        self.Cancel()
        self.processing_mode(restore_focus=frame is None)

        # Init blender paths
        blend_file_path = os.path.join(
            info.PATH, "blender", "blend", self.selected_template)
        source_script = os.path.join(
            info.PATH, "blender", "scripts",
            self.selected_template.replace(".blend", ".py.in"))
        target_script = os.path.join(
            info.BLENDER_PATH, self.unique_folder_name,
            self.selected_template.replace(".blend", ".py"))

        # Background Worker Thread (for Blender process)
        self.background = QThread(self)
        self.background.setObjectName("openshot_renderer")
        self.worker = Worker(blend_file_path, target_script, int(frame or 0))  # no parent!
        self.worker.setObjectName("render_worker")
        # Move Worker to new thread
        self.worker.moveToThread(self.background)

        # Hook up signals to/from Background Worker
        self.background.started.connect(self.worker.Render)

        self.worker.render_complete.connect(self.render_finished)

        # State changes
        self.worker.end_processing.connect(self.end_processing)
        self.worker.start_processing.connect(self.render_initialize)

        # Actual communication between the worker and front-end
        self.worker.blender_version_error.connect(self.onBlenderVersionError)
        self.worker.blender_error_nodata.connect(self.onBlenderError)
        self.worker.blender_error_with_data.connect(self.onBlenderError)
        self.worker.progress.connect(self.update_progress_bar)
        self.worker.image_updated.connect(self.update_image)
        self.worker.frame_saved.connect(self.render_saved)
        self.worker.frame_stage.connect(self.render_stage)
        self.worker.frame_render.connect(self.render_progress)

        # Cleanup signals all 'round
        self.worker.finished.connect(self.background.quit, Qt.DirectConnection)
        # Keep the QThread wrapper until Cancel joins/releases it. Otherwise a
        # later dialog close can call into an already-deleted wrapper.
        self.background.finished.connect(self.worker.deleteLater)

        # Read .py file, inject user parameters, and write to output path
        self.inject_params(source_script, target_script, frame)

        # Note whether we're rendering a preview or an animation
        self.final_render = frame is None

        # Run worker in background thread
        self.background.start()

    def __init__(self, parent, *args):
        # Invoke base class init
        super().__init__(*args)

        self.win = parent
        self.app = get_app()
        self.app.aboutToQuit.connect(self.Cancel)

        # Get Model data
        self.blender_model = BlenderModel()

        self.selected = None
        self.deselected = None
        self._color_scratchpad = None
        self.selected_template = ""
        self.final_render = False
        self._last_selected_index = None

        # Preview render timer
        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(300)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.preview_timer_onTimeout)

        # Calculate diff between project FPS and title FPS
        # All animated titles are created at an assumed default 25.0 FPS
        self.fps = self.app.project.get("fps")
        fps_float = self.fps["num"] / float(self.fps["den"])

        # NOTE: Blender can only use INT precision when remapping
        # frames. 1X, 2X, 3X, etc...  not 1.2X
        self.project_fps_diff = round(fps_float / 25.0)

        # Init dictionary which holds the values to the template parameters
        self.params = {}

        # Assign a new unique id for each template selected
        self.unique_folder_name = None

        # Disable interface
        self.processing_mode(cursor=False)

        # Setup header columns
        self.setModel(self.blender_model.proxy_model)
        self.setIconSize(info.LIST_ICON_SIZE)
        self.setGridSize(info.LIST_GRID_SIZE)
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setUniformItemSizes(True)
        self.setWordWrap(True)
        self.setTextElideMode(Qt.ElideRight)

        # Hook up controls
        self.win.btnRefresh.clicked.connect(self.preview_timer.start)
        self.win.sliderPreview.valueChanged.connect(functools.partial(self.sliderPreview_valueChanged))

        # Refresh view
        self.refresh_view()


class Worker(QObject):
    """ Background Worker Object (to run the Blender commands) """

    finished = pyqtSignal()
    blender_version_error = pyqtSignal(str)
    blender_error_nodata = pyqtSignal()
    blender_error_with_data = pyqtSignal(str)
    progress = pyqtSignal(int)
    image_updated = pyqtSignal(str)
    frame_stage = pyqtSignal(str)
    frame_render = pyqtSignal(int, int)
    frame_saved = pyqtSignal(int)
    start_processing = pyqtSignal()
    end_processing = pyqtSignal()
    render_complete = pyqtSignal()

    def __init__(self, blend_file_path, target_script, preview_frame=0):
        super().__init__()

        # Capture arguments
        self.blend_file_path = blend_file_path
        self.target_script = target_script
        self.preview_frame = preview_frame

        s = get_app().get_settings()
        self.blender_exec_path = s.get("blender_command")

        # Init regex expression used to determine blender's render progress
        self.blender_version_re = re.compile(
            r"Blender ([0-9a-z\.]*)", flags=re.MULTILINE)
        self.blender_frame_re = re.compile(r"Fra:([0-9,]+)")
        self.blender_frame_alt_re = re.compile(r"[Ff]rame[s]?[^\d]*([0-9]+)")
        self.blender_saved_re = re.compile(r"Saved: '(.*\.png)")
        self.blender_syncing_re = re.compile(
            r"\| Syncing (.*)$", flags=re.MULTILINE)
        self.blender_rendering_re = re.compile(
            r"Rendering ([0-9]*) / ([0-9]*) samples")

        self.version = None
        self.process = None
        self.canceled = False
        self._output_writer = None
        self._output_reader = None
        self._output_path = None

        # Get environment variables needed for launching a process without trying to load libraries
        # from our frozen app bundle
        self.env = dict(os.environ)
        if sys.platform == "linux":
            self.env.pop('LD_LIBRARY_PATH', None)
            log.debug('Removing custom LD_LIBRARY_PATH from environment variables when launching Blender')

        self.startupinfo = None
        self.creationflags = 0
        if sys.platform == 'win32':
            self.startupinfo = subprocess.STARTUPINFO()
            self.startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            self.creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    def Cancel(self):
        """Cancel worker render"""
        self.canceled = True
        process = self.process
        if process is not None:
            log.debug("Terminating Blender Process")
            try:
                if sys.platform != "win32":
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.terminate()
            except (OSError, ProcessLookupError):
                pass  # Process already terminated
            for _ in range(30):
                if process.poll() is not None:
                    break
                sleep(0.05)
            if sys.platform != "win32" or process.poll() is None:
                try:
                    if sys.platform != "win32":
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                except Exception as ex:
                    log.debug("Failed to kill Blender process: %s", ex)

    def _close_output(self):
        """Release Windows output capture without waiting on pipe readers."""
        for stream in (self._output_reader, self._output_writer):
            if stream is not None:
                stream.close()
        self._output_reader = self._output_writer = None
        if self._output_path:
            try:
                os.remove(self._output_path)
            except FileNotFoundError:
                pass
            except OSError:
                log.warning("Unable to remove Blender output log %s", self._output_path)
            self._output_path = None

    def _spawn_process(self, command):
        self._close_output()
        output = subprocess.PIPE
        if sys.platform == "win32":
            # Windows communicate() buffers until EOF in a background reader
            # thread. Use separate regular-file handles so progress is visible
            # immediately and cancellation cannot block closing a pipe reader.
            self._output_writer = tempfile.NamedTemporaryFile(
                prefix="openshot-blender-", suffix=".log", delete=False)
            self._output_path = self._output_writer.name
            self._output_reader = open(self._output_path, "rb")
            output = self._output_writer
        self.process = subprocess.Popen(
            command, stdout=output, stderr=subprocess.STDOUT,
            startupinfo=self.startupinfo, creationflags=self.creationflags,
            start_new_session=(sys.platform != "win32"),
            env=self.env, cwd=info.HOME_PATH,
        )

    def _read_output_file(self, timeout=None, progress=False):
        deadline = monotonic() + timeout if timeout is not None else None
        output = bytearray()
        pending = b""
        while not self.canceled:
            # Poll before reading: after exit, drain the last bytes as well.
            complete = self.process.poll() is not None
            chunk = self._output_reader.read()
            if progress:
                pending += chunk
                end = len(pending) if complete else pending.rfind(b"\n") + 1
                for line in pending[:end].splitlines():
                    self.process_line(line)
                pending = pending[end:]
            else:
                output.extend(chunk)
            if complete:
                return bytes(output)
            if deadline is not None and monotonic() >= deadline:
                raise subprocess.TimeoutExpired(self.process.args, timeout)
            sleep(0.05)
        return None

    def _communicate(self, timeout=None, progress=False):
        """Drain output without an uninterruptible readline or losing fast exits."""
        if self._output_reader is not None:
            return self._read_output_file(timeout, progress)
        deadline = monotonic() + timeout if timeout is not None else None
        consumed = 0
        while not self.canceled:
            complete = False
            try:
                output, _ = self.process.communicate(timeout=0.1)
                complete = True
            except subprocess.TimeoutExpired as ex:
                output = ex.output or b""
                if deadline is not None and monotonic() >= deadline:
                    raise
            if progress:
                # communicate retries return cumulative bytes. Only parse new,
                # complete lines; flush any final unterminated line on exit.
                end = len(output) if complete else output.rfind(b"\n") + 1
                if end > consumed:
                    for line in output[consumed:end].splitlines():
                        self.process_line(line)
                    consumed = end
            if complete:
                return output
        return None

    def blender_version_check(self):
        # Check the version of Blender
        command_get_version = [
            self.blender_exec_path,
            '--factory-startup',
            '-v',
            ]
        log.debug("Checking Blender version, command: {}".format(
            " ".join([shlex.quote(x) for x in command_get_version])))

        try:
            if self.process:
                self.process.terminate()
            self._spawn_process(command_get_version)
            # Give Blender up to 10 seconds to respond
            out = self._communicate(timeout=10)
            if self.canceled:
                return False
        except subprocess.TimeoutExpired:
            log.error("Blender version check timed out")
            self.Cancel()
            self.blender_error_nodata.emit()
            return False
        except FileNotFoundError:
            log.info("Blender executable not found at path: %s", self.blender_exec_path)
            self.blender_error_nodata.emit()
            return False
        except Exception:
            # Error running command.  Most likely the blender executable path in
            # the settings is incorrect, or is not a supported Blender version
            log.error("Version check exception", exc_info=1)
            self.blender_error_nodata.emit()
            return False

        ver_string = out.decode('utf-8', errors='ignore')
        log.debug("Blender output:\n%s", ver_string)

        ver_match = self.blender_version_re.search(ver_string)
        if not ver_match:
            raise Exception("No Blender version detected in output")
        log.debug("Matched %s in output", str(ver_match.group(0)))

        self.version = ver_match.group(1)
        log.info("Found Blender version {}".format(self.version))

        if self.version < info.BLENDER_MIN_VERSION:
            # Wrong version of Blender.
            self.blender_version_error.emit(self.version)
        return (self.version >= info.BLENDER_MIN_VERSION)

    def process_line(self, out_line):
        line = out_line.decode('utf-8', errors='replace').strip()

        # Skip blank output lines
        if not line:
            return

        # append all output into a variable, and log
        self.command_output += line + "\n"
        log.debug("  {}".format(line))

        # Look for progress info in the Blender Output
        output_frame = self.blender_frame_re.search(line)
        if output_frame and self.current_frame != int(output_frame.group(1).replace(',', '')):
            self.current_frame = int(output_frame.group(1).replace(',', ''))
            # update progress on frame change
            self.progress.emit(self.current_frame)
        else:
            alt_frame = self.blender_frame_alt_re.search(line)
            if alt_frame:
                try:
                    new_frame = int(alt_frame.group(1))
                    if new_frame != self.current_frame:
                        self.current_frame = new_frame
                        self.progress.emit(self.current_frame)
                except ValueError:
                    pass

        output_syncing = self.blender_syncing_re.search(line)
        if output_syncing:
            self.frame_stage.emit(output_syncing.group(1))

        output_rendering = self.blender_rendering_re.search(line)
        if output_rendering:
            self.frame_render.emit(
                int(output_rendering.group(1)),
                int(output_rendering.group(2)),
            )

        output_saved = self.blender_saved_re.search(line)
        if output_saved:
            # Try to infer frame number from the saved filename (Blender 5 logs)
            saved_path = output_saved.group(1)
            base_name = os.path.splitext(os.path.basename(saved_path))[0]
            if self.preview_frame > 0:
                self.current_frame = self.preview_frame
            else:
                frame_from_name = re.search(r"([0-9]{1,5})$", base_name)
                if frame_from_name:
                    try:
                        guessed_frame = int(frame_from_name.group(1))
                        self.current_frame = guessed_frame
                    except ValueError:
                        pass
            self.frame_count += 1
            log.debug("Saved frame %d", self.current_frame)
            # Emit progress on save to update UI even if render lines were missed
            self.progress.emit(self.current_frame)
            self.frame_saved.emit(self.current_frame)
            # Update preview image
            self.image_updated.emit(output_saved.group(1))

    @pyqtSlot()
    def Render(self):
        """Render and always release the process and worker thread."""
        _ = get_app()._tr
        self.command_output = ""
        self.current_frame = 0
        self.frame_count = 0
        try:
            if self.canceled:
                return
            if not self.version and not self.blender_version_check():
                return
            if self.canceled:
                return

            command_render = [
                self.blender_exec_path,
                '--factory-startup',
                '-b', self.blend_file_path,
                '-y',
                '-P', self.target_script,
            ]
            if self.preview_frame > 0:
                command_render.extend(['-f', str(self.preview_frame)])
            else:
                command_render.extend(['-a'])

            log.debug("Running Blender, command: %s", " ".join(
                shlex.quote(x) for x in command_render))
            log.debug("Blender output:")
            self._spawn_process(command_render)
            self.start_processing.emit()
            self._communicate(progress=True)
            if self.canceled:
                return

            log.info("Blender process exited (%s), %d frames saved.",
                     self.process.returncode, self.frame_count)
            if self.process.returncode != 0 or self.frame_count < 1:
                log.warning("Blender output:\n%s", self.command_output)
                self.blender_error_with_data.emit(
                    self.command_output or _("No frame was found in the output from Blender"))
            else:
                self.render_complete.emit()
        except Exception as ex:
            log.error("Blender worker exception", exc_info=True)
            if not self.canceled:
                self.blender_error_with_data.emit(str(ex))
        finally:
            try:
                if self.process is not None:
                    if self.canceled or self.process.poll() is None:
                        self.Cancel()
                    try:
                        self.process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        log.warning("Blender process did not exit after cancellation")
                    if self.process.stdout:
                        self.process.stdout.close()
            finally:
                try:
                    self._close_output()
                finally:
                    self.end_processing.emit()
                    self.finished.emit()
