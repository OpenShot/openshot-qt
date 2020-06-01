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
import shutil
import subprocess
import sys
import re
import functools
import json

# Try to get the security-patched XML functions from defusedxml
try:
    from defusedxml import minidom as xml
except ImportError:
    from xml.dom import minidom as xml

from PyQt5.QtCore import (
    Qt, QObject, pyqtSlot, pyqtSignal, QMetaObject, Q_ARG, QThread, QTimer, QSize,
)
from PyQt5.QtWidgets import (
    QApplication, QListView, QMessageBox, QColorDialog,
    QComboBox, QDoubleSpinBox, QLabel, QPushButton, QLineEdit, QPlainTextEdit,
)
from PyQt5.QtGui import QColor, QImage, QPixmap

from classes import info
from classes.logger import log
from classes import settings
from classes.query import File
from classes.app import get_app
from windows.models.blender_model import BlenderModel


class BlenderListView(QListView):
    """ A ListView QWidget used on the animated title window """

    def currentChanged(self, selected, deselected):
        # Get selected item
        self.selected = selected
        self.deselected = deselected

        # Get translation object
        _ = self.app._tr

        # Clear existing settings
        self.win.clear_effect_controls()

        # Get animation details
        animation = self.get_animation_details()
        self.selected_template = animation.get("service")

        # In newer versions of Qt, setting the model invokes the currentChanged signal,
        # but the selection is -1. So, just do nothing here.
        if not self.selected_template:
            return

        # Assign a new unique id for each template selected
        self.generateUniqueFolder()

        # Loop through params
        for param in animation.get("params", []):
            log.info('Using parameter %s: %s' % (param["name"], param["title"]))

            # Is Hidden Param?
            if param["name"] == "start_frame" or param["name"] == "end_frame":
                # add value to dictionary
                self.params[param["name"]] = int(param["default"])

                # skip to next param without rendering the controls
                continue

            # Create Label
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
                box_index = 0
                for k, v in sorted(param["values"].items()):
                    # add dropdown item
                    widget.addItem(_(k), v)

                    # select dropdown (if default)
                    if v == param["default"]:
                        widget.setCurrentIndex(box_index)
                    box_index = box_index + 1

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

        # Enable interface
        self.enable_interface()

        # Init slider values
        self.init_slider_values()

    def spinner_value_changed(self, param, value):
        self.params[param["name"]] = value
        log.info('Animation param %s set to %s' % (param["name"], value))

    def text_value_changed(self, widget, param, value=None):
        try:
            # Attempt to load value from QPlainTextEdit (i.e. multi-line)
            if not value:
                value = widget.toPlainText()
        except Exception:
            log.warning('Failed to read plain text value from widget')
            return
        self.params[param["name"]] = value.replace("\n", "\\n")
        # XXX: This will log every individual KEYPRESS in the text field.
        # log.info('Animation param %s set to %s' % (param["name"], value))

    def dropdown_index_changed(self, widget, param, index):
        value = widget.itemData(index)
        self.params[param["name"]] = value
        log.info('Animation param %s set to %s' % (param["name"], value))

    def color_button_clicked(self, widget, param, index):
        # Get translation object
        _ = get_app()._tr

        # Show color dialog
        color_value = self.params[param["name"]]
        currentColor = QColor("#FFFFFF")
        if len(color_value) >= 3:
            currentColor.setRgbF(color_value[0], color_value[1], color_value[2])
        newColor = QColorDialog.getColor(currentColor, self, _("Select a Color"),
                                         QColorDialog.DontUseNativeDialog)
        if newColor.isValid():
            widget.setStyleSheet("background-color: {}".format(newColor.name()))
            self.params[param["name"]] = [newColor.redF(), newColor.greenF(), newColor.blueF()]
            if "diffuse_color" in param.get("name"):
                self.params[param["name"]].append(newColor.alphaF())

            log.info('Animation param %s set to %s' % (param["name"], newColor.name()))

    def generateUniqueFolder(self):
        """ Generate a new, unique folder name to contain Blender frames """

        # Assign a new unique id for each template selected
        self.unique_folder_name = str(self.app.project.generate_id())

        # Create a folder (if it does not exist)
        if not os.path.exists(os.path.join(info.BLENDER_PATH, self.unique_folder_name)):
            os.mkdir(os.path.join(info.BLENDER_PATH, self.unique_folder_name))

    def disable_interface(self, cursor=True):
        """ Disable all controls on interface """

        # Store keyboard-focused widget
        self.focus_owner = self.win.focusWidget()

        self.win.btnRefresh.setEnabled(False)
        self.win.sliderPreview.setEnabled(False)
        self.win.btnRender.setEnabled(False)

        # Show 'Wait' cursor
        if cursor:
            QApplication.setOverrideCursor(Qt.WaitCursor)

    @pyqtSlot()
    def enable_interface(self):
        """ Disable all controls on interface """
        self.win.btnRefresh.setEnabled(True)
        self.win.sliderPreview.setEnabled(True)
        self.win.btnRender.setEnabled(True)

        # Restore normal cursor and keyboard focus
        QApplication.restoreOverrideCursor()
        if self.focus_owner:
            self.focus_owner.setFocus()

    def init_slider_values(self):
        """ Init the slider and preview frame label to the currently selected animation """

        # Get current preview slider frame
        preview_frame_number = self.win.sliderPreview.value()
        length = int(self.params.get("end_frame", 1))

        # Get the animation speed (if any)
        if not self.params.get("animation_speed"):
            self.params["animation_speed"] = 1
        else:
            # Adjust length (based on animation speed multiplier)
            length *= int(self.params["animation_speed"])

        # Update the preview slider
        middle_frame = int(length / 2)

        self.win.sliderPreview.setMinimum(self.params.get("start_frame", 1))
        self.win.sliderPreview.setMaximum(length)
        self.win.sliderPreview.setValue(middle_frame)

        # Update preview label
        self.win.lblFrame.setText("{}/{}".format(middle_frame, length))

        # Click the refresh button
        self.btnRefresh_clicked(None)

    def btnRefresh_clicked(self, checked):

        # Render current frame
        self.preview_timer.start()

    @pyqtSlot()
    def render_finished(self):
        # Compose image sequence data
        seq_params = {
            "folder_path": os.path.join(info.BLENDER_PATH, self.unique_folder_name),
            "base_name": self.params["file_name"],
            "fixlen": True,
            "digits": 4,
            "extension": "png"
        }

        filename = "{}%04d.png".format(seq_params["base_name"])
        final_path = os.path.join(seq_params["folder_path"], filename)
        log.info('RENDER FINISHED! Adding to project files: {}'.format(filename))

        # Add to project files
        get_app().window.files_model.add_files(final_path, seq_params)

        # We're done here
        self.win.close()

    @pyqtSlot(int)
    def update_progress_bar(self, current_frame):

        # update label and preview slider
        self.win.sliderPreview.setValue(current_frame)

        length = int(self.params["end_frame"])
        self.win.lblFrame.setText("{}/{}".format(current_frame, length))

    def sliderPreview_valueChanged(self, new_value):
        """Get new value of preview slider, and start timer to Render frame"""
        if self.win.sliderPreview.isEnabled():
            self.preview_timer.start()

        # Update preview label
        preview_frame_number = new_value
        length = int(self.params["end_frame"])
        self.win.lblFrame.setText("{}/{}".format(preview_frame_number, length))

    def preview_timer_onTimeout(self):
        """Timer is ready to Render frame"""
        self.preview_timer.stop()

        # Update preview label
        preview_frame_number = self.win.sliderPreview.value()
        log.info('Previewing frame %s' % preview_frame_number)

        # Render current frame
        self.Render(preview_frame_number)

    def get_animation_details(self):
        """ Build a dictionary of all animation settings and properties from XML """

        if not self.selected:
            return {}
        elif self.selected and self.selected.row() == -1:
            return {}

        # Get all selected rows items
        ItemRow = self.blender_model.model.itemFromIndex(self.selected).row()
        animation_title = self.blender_model.model.item(ItemRow, 1).text()
        xml_path = self.blender_model.model.item(ItemRow, 2).text()
        service = self.blender_model.model.item(ItemRow, 3).text()

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
                log.warn("XML parser: {}".format(ex))
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

    def refresh_view(self):
        self.blender_model.update_model()

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
        project_params["output_path"] = os.path.join(info.BLENDER_PATH, self.unique_folder_name,
                                                     self.params["file_name"])

        # return the dictionary
        return project_params

    def error_with_blender(self, version=None, command_output=None):
        """ Show a friendly error message regarding the blender executable or version. """
        _ = self.app._tr
        s = settings.get_settings()

        version_message = ""
        if version:
            version_message = _("Version Detected: {}").format(version)
            log.info("Blender version detected: {}".format(version))

        if command_output:
            version_message = _("Error Output:\n{}").format(command_output)
            log.error("Blender error output:\n{}".format(command_output))

        msg = QMessageBox()
        msg.setText(_("""
Blender, the free open source 3D content creation suite, is required for this action. (http://www.blender.org)
Please check the preferences in OpenShot and be sure the Blender executable is correct.
This setting should be the path of the 'blender' executable on your computer.
Also, please be sure that it is pointing to Blender version {} or greater.
Blender Path: {}
{}""").format(info.BLENDER_MIN_VERSION,
              s.get("blender_command"),
              version_message))
        msg.exec_()

        # Enable the Render button again
        self.enable_interface()

    def inject_params(self, path, frame=None):
        # determine if this is 'preview' mode?
        is_preview = False
        if frame:
            # if a frame is passed in, we are in preview mode.
            # This is used to turn the background color to off-white... instead of transparent
            is_preview = True

        # prepare string to inject
        user_params = "\n#BEGIN INJECTING PARAMS\n"
        for k, v in self.params.items():
            if type(v) == int or type(v) == float or type(v) == list or type(v) == bool:
                user_params += "params['{}'] = {}\n".format(k, v)
            if type(v) == str:
                user_params += "params['{}'] = u'{}'\n".format(k, v.replace("'", r"\'"))

        for k, v in self.get_project_params(is_preview).items():
            if type(v) == int or type(v) == float or type(v) == list or type(v) == bool:
                user_params += "params['{}'] = {}\n".format(k, v)
            if type(v) == str:
                user_params += "params['{}'] = u'{}'\n".format(k, v.replace("'", r"\'").replace("\\", "\\\\"))
        user_params += "#END INJECTING PARAMS\n"

        # Force the Frame to 1 frame (for previewing)
        if frame:
            user_params += "\n#ONLY RENDER 1 FRAME FOR PREVIEW\n"
            user_params += "params['{}'] = {}\n".format("start_frame", frame)
            user_params += "params['{}'] = {}\n".format("end_frame", frame)
            user_params += "#END ONLY RENDER 1 FRAME FOR PREVIEW\n"

        # If GPU rendering is selected, see if GPU enable code is available
        s = settings.get_settings()
        gpu_code_body = None
        if s.get("blender_gpu_enabled"):
            gpu_enable_py = os.path.join(info.PATH, "blender", "scripts", "gpu_enable.py")
            try:
                f = open(gpu_enable_py, 'r')
                gpu_code_body = f.read()
            except IOError as e:
                log.error("Could not load GPU enable code! {}".format(e))

        if gpu_code_body:
            log.info("Injecting GPU enable code from {}".format(gpu_enable_py))
            user_params += "\n#ENABLE GPU RENDERING\n"
            user_params += gpu_code_body
            user_params += "\n#END ENABLE GPU RENDERING\n"

        # Open new temp .py file, and inject the user parameters
        with open(path, 'r') as f:
            script_body = f.read()

        # modify script variable
        script_body = script_body.replace("# INJECT_PARAMS_HERE", user_params)

        # Write update script
        with open(path, "w", encoding="UTF-8", errors="strict") as f:
            f.write(script_body)

    @pyqtSlot(str)
    def update_image(self, image_path):

        # get the pixbuf
        image = QImage(image_path)
        scaled_image = image.scaledToHeight(self.win.imgPreview.height(), Qt.SmoothTransformation)
        pixmap = QPixmap.fromImage(scaled_image)
        self.win.imgPreview.setPixmap(pixmap)

    def Cancel(self):
        """Cancel the current render, if any"""
        QMetaObject.invokeMethod(self.worker, 'Cancel', Qt.DirectConnection)

    def Render(self, frame=None):
        """ Render an images sequence of the current template using Blender 2.62+ and the
        Blender Python API. """

        # Enable the Render button again
        self.disable_interface()

        # Init blender paths
        blend_file_path = os.path.join(info.PATH, "blender", "blend", self.selected_template)
        source_script = os.path.join(info.PATH, "blender", "scripts", self.selected_template.replace(".blend", ".py"))
        target_script = os.path.join(info.BLENDER_PATH, self.unique_folder_name,
                                     self.selected_template.replace(".blend", ".py"))

        # Copy the .py script associated with this template to the temp folder.  This will allow
        # OpenShot to inject the user-entered params into the Python script.
        # XXX: Note that copyfile() is used instead of copy(), as the original
        #      file may be readonly, and we don't want to duplicate those permissions
        shutil.copyfile(source_script, target_script)

        # Open new temp .py file, and inject the user parameters
        self.inject_params(target_script, frame)

        # Create new thread to launch the Blender executable (and read the output)
        if frame:
            # preview mode
            QMetaObject.invokeMethod(self.worker, 'Render', Qt.QueuedConnection,
                                     Q_ARG(str, blend_file_path),
                                     Q_ARG(str, target_script),
                                     Q_ARG(bool, True))
        else:
            # render mode
            # self.my_blender = BlenderCommand(self, blend_file_path, target_script, False)
            QMetaObject.invokeMethod(self.worker, 'Render', Qt.QueuedConnection,
                                     Q_ARG(str, blend_file_path),
                                     Q_ARG(str, target_script),
                                     Q_ARG(bool, False))

    def __init__(self, *args):
        # Invoke parent init
        super().__init__(*args)

        # Get a reference to the window object
        self.app = get_app()
        self.win = args[0]

        # Get Model data
        self.blender_model = BlenderModel()

        # Keep track of mouse press start position to determine when to start drag
        self.selected = None
        self.deselected = None

        # Preview render timer
        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(300)
        self.preview_timer.timeout.connect(self.preview_timer_onTimeout)

        # Init dictionary which holds the values to the template parameters
        self.params = {}

        # Assign a new unique id for each template selected
        self.unique_folder_name = None

        # Disable interface
        self.disable_interface(cursor=False)
        self.selected_template = ""

        # Setup header columns
        self.setModel(self.blender_model.model)
        self.setIconSize(QSize(131, 108))
        self.setGridSize(QSize(102, 92))
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setUniformItemSizes(True)
        self.setWordWrap(True)
        self.setTextElideMode(Qt.ElideRight)

        # Hook up button
        self.win.btnRefresh.clicked.connect(functools.partial(self.btnRefresh_clicked))
        self.win.sliderPreview.valueChanged.connect(functools.partial(self.sliderPreview_valueChanged))

        # Refresh view
        self.refresh_view()

        # Background Worker Thread (for Blender process)
        self.background = QThread(self)
        self.worker = Worker()  # no parent!

        # Hook up signals to Background Worker
        self.worker.closed.connect(self.close)
        self.worker.finished.connect(self.render_finished)
        self.worker.blender_version_error.connect(self.onBlenderVersionError)
        self.worker.blender_error_nodata.connect(self.onBlenderErrorNoData)
        self.worker.progress.connect(self.update_progress_bar)
        self.worker.image_updated.connect(self.update_image)
        self.worker.blender_error_with_data.connect(self.onBlenderErrorMessage)
        self.worker.enable_interface.connect(self.enable_interface)

        # Move Worker to new thread, and Start
        self.worker.moveToThread(self.background)
        self.background.start()

    # Error from blender (with version number) (1003)
    @pyqtSlot(str)
    def onBlenderVersionError(self, version):
        self.error_with_blender(version)

    # Error from blender (with no data) (1004)
    @pyqtSlot()
    def onBlenderErrorNoData(self):
        self.error_with_blender()

    # Signal error from blender (with custom message) (1007)
    @pyqtSlot(str)
    def onBlenderErrorMessage(self, error):
        self.error_with_blender(None, error)


class Worker(QObject):
    """ Background Worker Object (to run the Blender commands) """

    closed = pyqtSignal()  # 1001
    finished = pyqtSignal()  # 1002
    blender_version_error = pyqtSignal(str)  # 1003
    blender_error_nodata = pyqtSignal()  # 1004
    progress = pyqtSignal(int)  # 1005
    image_updated = pyqtSignal(str)  # 1006
    blender_error_with_data = pyqtSignal(str)  # 1007
    enable_interface = pyqtSignal()  # 1008

    @pyqtSlot()
    def Cancel(self):
        """Cancel worker render"""
        self.is_running = False
        if self.process:
            # Stop blender process if running
            self.process.terminate()

    @pyqtSlot(str, str, bool)
    def Render(self, blend_file_path, target_script, preview_mode=False):
        """ Worker's Render method which invokes the Blender rendering commands """

        # Init regex expression used to determine blender's render progress
        s = settings.get_settings()

        _ = get_app()._tr

        # get the blender executable path
        self.blender_exec_path = s.get("blender_command")
        self.preview_mode = preview_mode
        self.frame_detected = False
        self.last_frame = 0
        self.version = None
        self.command_output = ""
        self.process = None
        self.is_running = False

        blender_frame_re = re.compile(r"Fra:([0-9,]*)")
        blender_saved_re = re.compile(r"Saved: '(.*\.png)")
        blender_version_re = re.compile(r"Blender (.*?) ")

        startupinfo = None
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:
            # Shell the blender command to create the image sequence
            command_get_version = [self.blender_exec_path, '-v']
            command_render = [self.blender_exec_path, '-b', blend_file_path, '-P', target_script]

            # Check the version of Blender
            import shlex
            log.info("Checking Blender version, command: {}".format(
                " ".join([shlex.quote(x) for x in command_get_version])))

            self.process = subprocess.Popen(
                command_get_version,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                startupinfo=startupinfo,
            )

            # Check the version of Blender
            try:
                # Give Blender up to 10 seconds to respond
                (out, err) = self.process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                self.blender_error_nodata.emit()
                return

            ver_string = out.decode('utf-8')
            ver_match = blender_version_re.search(ver_string)

            if not ver_match:
                raise Exception("No Blender version detected in output")

            self.version = ver_match.group(1)
            log.info("Found Blender version {}".format(self.version))

            if self.version < info.BLENDER_MIN_VERSION:
                # Wrong version of Blender.
                self.blender_version_error.emit(self.version)
                return

            # debug info
            log.info("Running Blender, command: {}".format(
                " ".join([shlex.quote(x) for x in command_render])))
            log.info("Blender output:")

            # Run real command to render Blender project
            self.process = subprocess.Popen(
                command_render, bufsize=512,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                startupinfo=startupinfo,
            )
            self.is_running = True

        except subprocess.SubprocessError:
            # Error running command.  Most likely the blender executable path in
            # the settings is incorrect, or is not a supported Blender version
            self.is_running = False
            self.blender_error_nodata.emit()
            raise
        except Exception as ex:
            log.error("Worker exception: {}".format(ex))
            return

        while self.is_running and self.process.poll() is None:
            for outline in iter(self.process.stdout.readline, b''):
                line = outline.decode('utf-8').strip()

                # Skip blank output
                if not line:
                    continue

                # append all output into a variable, and log
                self.command_output = self.command_output + line + "\n"
                log.info("  {}".format(line))

                # Look for progress info in the Blender Output
                output_frame = blender_frame_re.search(line)
                output_saved = blender_saved_re.search(line)

                # Does it have a match?
                if output_frame or output_saved:
                    # Yes, we have a match
                    self.frame_detected = True

                if output_frame:
                    current_frame = int(output_frame.group(1))

                    # Update progress bar
                    if current_frame != self.last_frame and not self.preview_mode:
                        # update progress on frame change, if in 'render' mode
                        self.progress.emit(current_frame)

                    self.last_frame = current_frame

                if output_saved:
                    # Update preview image
                    self.image_updated.emit(output_saved.group(1))

        log.info("Blender process exited.")

        # Re-enable the interface
        self.enable_interface.emit()

        # Check if NO FRAMES are detected
        if not self.frame_detected:
            # Show Error that no frames are detected.  This is likely caused by
            # the wrong command being executed... or an error in Blender.
            self.blender_error_with_data.emit(_("No frame was found in the output from Blender"))

        # Done with render (i.e. close window)
        elif self.is_running and not self.preview_mode:
            # only add file to project data if in 'render' mode and not canceled
            self.finished.emit()

        # Thread finished
        if not self.is_running:
            # close window if thread was killed
            self.closed.emit()

        # mark thread as finished
        self.is_running = False
