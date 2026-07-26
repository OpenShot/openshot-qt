"""
 @file
 @brief This file loads the Initialize Effects / Pre-process effects dialog
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
import time
import json
import functools
import webbrowser
import hashlib
import zipfile
from urllib.parse import urljoin

from qt_api import Qt, pyqtSignal, QCoreApplication, QTimer, QSize
from qt_api import QPainter
from qt_api import (
    QPushButton, QDialog, QLabel, QDoubleSpinBox, QSpinBox, QLineEdit,
    QCheckBox, QComboBox, QDialogButtonBox, QSizePolicy, QMessageBox,
    QFileDialog, QProgressDialog, QApplication, QWidget, QHBoxLayout,
)
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info
from classes import http_client
from classes import ui_util
from classes.app import get_app
from classes.logger import log
from classes.metrics import *

YOLO_MODELS_PATH = os.path.join(info.RESOURCES_PATH, "yolo-models.json")
EFFICIENT_SAM_MODELS_PATH = os.path.join(info.RESOURCES_PATH, "efficient-sam-models.json")
CUTIE_MODELS_PATH = os.path.join(info.RESOURCES_PATH, "cutie-models.json")
YOLO_MODEL_FILENAME = "model.onnx"
YOLO_CLASSES_FILENAME = "classes.names"
YOLO_INSTALL_METADATA = "install.json"
YOLO_FALLBACK_MODEL_NAME = "YOLO"
EFFICIENT_SAM_INSTALL_METADATA = "install-efficient-sam.json"
CUTIE_INSTALL_METADATA = "install-cutie.json"

EFFICIENT_SAM_MODEL_FILES = {
    "efficient-sam-tiny-1024": "image_segmentation_efficientsam_ti_2025april.onnx",
    "efficient-sam-small-static-1024": "image_segmentation_efficientsam_s_static_1024.onnx",
}

CUTIE_MODEL_FILES = {
    "cutie-low": {
        "encode-key": "cutie-encode-key-480x272.onnx",
        "encode-value": "cutie-encode-value-480x272.onnx",
        "memory-readout": "cutie-memory-readout-floatmask-valid-480x272-m6-topk30-opencv.onnx",
        "decode": "cutie-decode-480x272.onnx",
    },
    "cutie-medium": {
        "encode-key": "cutie-encode-key-640x368.onnx",
        "encode-value": "cutie-encode-value-640x368.onnx",
        "memory-readout": "cutie-memory-readout-floatmask-valid-640x368-m6-topk30-opencv.onnx",
        "decode": "cutie-decode-640x368.onnx",
    },
    "cutie-high": {
        "encode-key": "cutie-encode-key-960x544.onnx",
        "encode-value": "cutie-encode-value-960x544.onnx",
        "memory-readout": "cutie-memory-readout-floatmask-valid-960x544-m6-topk30-opencv.onnx",
        "decode": "cutie-decode-960x544.onnx",
    },
    "cutie-very-high": {
        "encode-key": "cutie-encode-key-1280x720.onnx",
        "encode-value": "cutie-encode-value-1280x720.onnx",
        "memory-readout": "cutie-memory-readout-floatmask-valid-1280x720-m6-topk30-opencv.onnx",
        "decode": "cutie-decode-1280x720.onnx",
    },
}


class DownloadCancelled(Exception):
    """Raised when a user cancels an in-progress download."""


def load_yolo_models_manifest():
    """Load the packaged allow-list of YOLO model downloads."""
    return load_model_manifest(YOLO_MODELS_PATH)


def load_model_manifest(path):
    """Load a packaged allow-list of model downloads."""
    with open(path, "r", encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    manifest.setdefault("models", [])
    return manifest


def recommended_model(models):
    """Return the recommended model entry, or the first available entry."""
    for model in models:
        if model.get("recommended"):
            return model
    return models[0] if models else None


def yolo_model_dir(model):
    """Return the install directory for a packaged YOLO model entry."""
    model_id = model.get("id", "")
    if not model_id or os.path.basename(model_id) != model_id:
        raise ValueError("Invalid YOLO model id: %s" % model_id)
    return os.path.join(info.YOLO_PATH, model_id)


def model_install_dir(model):
    """Return the shared AI model install directory for a manifest entry."""
    return yolo_model_dir(model)


def yolo_model_path(model):
    """Return the installed ONNX path for a packaged YOLO model entry."""
    return os.path.join(yolo_model_dir(model), YOLO_MODEL_FILENAME)


def yolo_classes_path(model):
    """Return the installed class names path for a packaged YOLO model entry."""
    return os.path.join(yolo_model_dir(model), YOLO_CLASSES_FILENAME)


def yolo_model_label(model):
    """Return the dropdown label for a packaged YOLO model entry."""
    return model_label(model, YOLO_FALLBACK_MODEL_NAME)


def model_label(model, fallback_name="Model"):
    """Return the dropdown label for a packaged model entry."""
    label = model.get("name") or model.get("id") or fallback_name
    description = model.get("description")
    if description:
        label = "%s (%s)" % (label, description)
    return label


def translated_model_label(model, fallback_name="Model"):
    """Return a translated dropdown label for a packaged model entry."""
    _ = get_app()._tr
    label = _(model.get("name") or model.get("id") or fallback_name)
    description = model.get("description")
    if description:
        label = "%s (%s)" % (label, _(description))
    return label


def compact_model_label(model, fallback_name="Model"):
    """Return a compact dropdown label without descriptive prose."""
    return model.get("name") or model.get("id") or fallback_name


def object_mask_quality_label(model):
    """Return the Object Mask quality label for a Cutie manifest entry."""
    return model_label(model)


def yolo_download_button_label(model=None):
    """Return the download button label for a packaged YOLO model entry."""
    return model_download_button_label(model)


def model_download_button_label(model=None):
    """Return the download button label for a packaged model entry."""
    _ = get_app()._tr
    if not model or not model.get("bytes"):
        return _("Download")
    return _("Download (%s MB)") % max(1, int(round(model.get("bytes") / 1000000.0)))


class RegionButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.qimage = None

    def setImage(self, qimage):
        self.qimage = qimage
        self.update()  # Trigger a repaint

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.qimage:
            painter = QPainter(self)
            resized_qimage = self.qimage.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            painter.drawImage(0, 0, resized_qimage)
        else:
            super().paintEvent(event)  # Draw the normal button


class ProcessEffect(QDialog):
    """ Choose Profile Dialog """
    progress = pyqtSignal(int)

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'process-effect.ui')

    def __init__(self, clip_id, effect_class, effect_params):

        if not openshot.Clip().COMPILED_WITH_CV:
            raise ModuleNotFoundError("Openshot not compiled with OpenCV")

        # Create dialog class
        super().__init__()
        # Track effect details
        self.clip_id = clip_id
        self.effect_name = ""
        self.effect_class = effect_class
        self.context = {}
        self.file_fields = {}
        self.selection_fields = {}
        self.download_groups = []
        self.advanced_rows = []
        self.advanced_buttons = []
        self.advanced_visible = False
        self.onnx_validation_cache = {}
        self.yolo_models_manifest = None
        self.yolo_models = []
        self.model_manifests = {}
        self.processing_effect = False
        self.validation_wait_cursor = False
        self.file_validation_timer = QTimer(self)
        self.file_validation_timer.setInterval(300)
        self.file_validation_timer.setSingleShot(True)
        self.file_validation_timer.timeout.connect(self.update_file_validation)

        # Get all effect JSON data, and find effect's display name (based on the class name)
        raw_effects_list = json.loads(openshot.EffectInfo.Json())
        for raw_effect in raw_effects_list:
            if raw_effect.get("class_name") == self.effect_class:
                self.effect_name = raw_effect.get("name")
                break

        # Access C++ timeline and find the Clip instance which this effect should be applied to
        timeline_instance = get_app().window.timeline_sync.timeline
        for clip_instance in timeline_instance.Clips():
            if clip_instance.Id() == self.clip_id:
                self.clip_instance = clip_instance
                break

        # Load UI from designer & init
        ui_util.load_ui(self, self.ui_path)
        ui_util.init_ui(self)

        # get translations
        _ = get_app()._tr

        # Update window title
        self.setWindowTitle(self.windowTitle() % _(self.effect_name))

        # Pause playback
        get_app().window.PauseSignal.emit()

        # Track metrics
        track_metric_screen("process-effect-screen")

        # Loop through options and create widgets
        form_layout = self.scrollAreaWidgetContents.layout()
        for param in effect_params:
            # Create Label
            widget = None
            label = QLabel()
            label.setText(_(param["title"]))
            label.setToolTip(_(param["title"]))

            if param["type"] == "link":
                # create a clickable link
                label.setText('<a href="%s">%s</a>' % (param["value"], _(param["title"])))
                label.setTextInteractionFlags(Qt.TextBrowserInteraction)
                label.linkActivated.connect(functools.partial(self.link_activated, widget, param))

            if param["type"] in ("download-yolo", "download-yolo5", "download-object-mask"):
                widget = self.create_model_download_widget(param)

            if param["type"] == "spinner":
                # create QDoubleSpinBox
                widget = QDoubleSpinBox()
                widget.setMinimum(float(param["min"]))
                widget.setMaximum(float(param["max"]))
                widget.setValue(float(param["value"]))
                widget.setSingleStep(1.0)
                widget.setToolTip(_(param["title"]))
                widget.valueChanged.connect(functools.partial(self.spinner_value_changed, widget, param))

                # Set initial context
                self.context[param["setting"]] = float(param["value"])

            if param["type"] == "rect":
                # create QPushButton which opens up a display of the clip, with ability to select Rectangle
                widget = RegionButton(_("Click to Select"))
                widget.setMinimumHeight(80)
                widget.setToolTip(_(param["title"]))
                widget.clicked.connect(functools.partial(self.rect_select_clicked, widget, param))

                # Set initial context
                self.context[param["setting"]] = {"button-clicked": False, "x": 0, "y": 0, "width": 0, "height": 0}

            if param["type"] == "object-mask-selection":
                widget = QWidget()
                widget_layout = QHBoxLayout(widget)
                widget_layout.setContentsMargins(0, 0, 0, 0)
                widget_layout.setSpacing(6)

                select_button = QPushButton(_("Select Point / Region"))
                select_button.setToolTip(_("Choose a positive point or rectangle, and optional negative points."))
                select_button.clicked.connect(functools.partial(self.object_mask_select_clicked, select_button, param))

                status_widget = QLabel()
                status_widget.setMinimumWidth(20)
                status_widget.setToolTip(_("Point or region has not been selected."))

                select_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                status_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
                widget_layout.addWidget(select_button, 1, Qt.AlignVCenter)
                widget_layout.addWidget(status_widget, 0, Qt.AlignVCenter)

                self.context[param["setting"]] = {}
                self.selection_fields[param["setting"]] = {
                    "param": param,
                    "button": select_button,
                    "status": status_widget,
                    "valid": False,
                }

            if param["type"] == "spinner-int":
                # create QDoubleSpinBox
                widget = QSpinBox()
                widget.setMinimum(int(param["min"]))
                widget.setMaximum(int(param["max"]))
                widget.setValue(int(param["value"]))
                widget.setSingleStep(1)
                widget.setToolTip(_(param["title"]))
                widget.valueChanged.connect(functools.partial(self.spinner_value_changed, widget, param))

                # Set initial context
                self.context[param["setting"]] = int(param["value"])

            elif param["type"] == "text":
                # create QLineEdit
                widget = QLineEdit()
                widget.setText(_(param["value"]))
                widget.textChanged.connect(functools.partial(self.text_value_changed, widget, param))

                # Set initial context
                self.context[param["setting"]] = param["value"]

            elif param["type"] == "file":
                widget = QWidget()
                widget_layout = QHBoxLayout(widget)
                widget_layout.setContentsMargins(0, 0, 0, 0)
                widget_layout.setSpacing(6)

                path_widget = QLineEdit()
                path_widget.setText(param["value"])
                path_widget.setToolTip(_(param["title"]))
                path_widget.textChanged.connect(functools.partial(self.file_value_changed, path_widget, param))

                status_widget = QLabel()
                status_widget.setMinimumWidth(20)
                status_widget.setToolTip(_("File has not been validated yet."))

                browse_button = QPushButton(_("Browse"))
                browse_button.setToolTip(_("Choose a file from disk."))
                browse_button.clicked.connect(functools.partial(self.file_browse_clicked, path_widget, param))

                path_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                status_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
                browse_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

                widget_layout.addWidget(path_widget, 1, Qt.AlignVCenter)
                widget_layout.addWidget(status_widget, 0, Qt.AlignVCenter)
                widget_layout.addWidget(browse_button, 0, Qt.AlignVCenter)

                self.context[param["setting"]] = param["value"]
                self.file_fields[param["setting"]] = {
                    "param": param,
                    "path": path_widget,
                    "status": status_widget,
                }

            elif param["type"] == "bool":
                # create spinner
                widget = QCheckBox()
                if param["value"] == True:
                    widget.setCheckState(Qt.Checked)
                    self.context[param["setting"]] = True
                else:
                    widget.setCheckState(Qt.Unchecked)
                    self.context[param["setting"]] = False
                widget.stateChanged.connect(functools.partial(self.bool_value_changed, widget, param))

            elif param["type"] == "dropdown":

                # create spinner
                widget = QComboBox()

                # Get values
                value_list = param["values"]

                # Add normal values
                box_index = 0
                for value_item in value_list:
                    k = value_item["name"]
                    v = value_item["value"]
                    i = value_item.get("icon", None)

                    # add dropdown item
                    widget.addItem(_(k), v)

                    # select dropdown (if default)
                    if v == param["value"]:
                        widget.setCurrentIndex(box_index)

                        # Set initial context
                        self.context[param["setting"]] = param["value"]
                    box_index = box_index + 1

                widget.currentIndexChanged.connect(functools.partial(self.dropdown_index_changed, widget, param))

            # Add Label and Widget to the form
            if widget and label:
                # Add minimum size
                label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
                label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

                form_layout.addRow(label, widget)
                if param.get("advanced"):
                    label.setVisible(self.advanced_visible)
                    widget.setVisible(self.advanced_visible)
                    self.advanced_rows.append((label, widget))
                if param["type"] in ("download-yolo", "download-yolo5", "download-object-mask"):
                    for group in self.download_groups:
                        if group["param"] is param:
                            status_label = QLabel(_("Status"))
                            status_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
                            status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                            form_layout.addRow(status_label, group["status-widget"])
                            break

            elif not widget and label:
                label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
                label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                form_layout.addRow(label)

        # Add buttons
        self.cancel_button = QPushButton(_('Cancel'))
        self.process_button = QPushButton(_('Process Effect'))
        self.buttonBox.addButton(self.process_button, QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton(self.cancel_button, QDialogButtonBox.RejectRole)
        self.sync_download_groups_to_selected_models()
        self.update_file_validation()

        # flag to close the clip processing thread
        self.cancel_clip_processing = False
        self.effect = None

    def load_manifest_models(self, key, path):
        """Load and cache a model manifest by resource path."""
        if key not in self.model_manifests:
            self.model_manifests[key] = load_model_manifest(path)
        return self.model_manifests[key]

    def create_model_download_widget(self, param):
        """Create the shared model dropdown, download button, status, and advanced toggle."""
        _ = get_app()._tr
        group_type = param["type"]
        if group_type in ("download-yolo", "download-yolo5"):
            self.load_yolo_models()
            models = self.yolo_models
            selected_model = recommended_model(models)
            button_tooltip = _("Download selected YOLO model files.")
            button_callback = self.download_yolo_clicked
        else:
            manifest = self.load_manifest_models("cutie", CUTIE_MODELS_PATH)
            models = manifest.get("models", [])
            selected_model = recommended_model(models)
            button_tooltip = _("Download selected Object Mask model files.")
            button_callback = self.download_object_mask_clicked

        widget = QWidget()
        control_layout = QHBoxLayout(widget)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(6)

        model_combo = QComboBox()
        selected_index = 0
        selected_id = selected_model.get("id") if selected_model else None
        for index, model in enumerate(models):
            label_text = translated_model_label(model, YOLO_FALLBACK_MODEL_NAME)
            model_combo.addItem(label_text, model.get("id"))
            if model.get("id") == selected_id:
                selected_index = index

        download_button = QPushButton(model_download_button_label(selected_model))
        download_button.setToolTip(button_tooltip)
        download_button.clicked.connect(
            functools.partial(button_callback, download_button, model_combo, param)
        )

        if models:
            model_combo.setCurrentIndex(selected_index)
            model_combo.currentIndexChanged.connect(
                functools.partial(self.model_download_index_changed, model_combo, download_button, param)
            )

        model_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        download_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        control_layout.addWidget(model_combo, 1, Qt.AlignVCenter)
        control_layout.addWidget(download_button, 0, Qt.AlignVCenter)

        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(6)

        status_label = QLabel(_("Not Downloaded"))
        status_label.setStyleSheet("color: #e53935; font-weight: bold;")
        status_label.setToolTip(_("Required model files are not downloaded."))

        advanced_button = QPushButton(_("Advanced"))
        advanced_button.setCheckable(True)
        advanced_button.setToolTip(_("Show model file paths."))
        advanced_button.setFlat(True)
        advanced_button.setObjectName("advancedLinkButton")
        advanced_button.setStyleSheet(
            "QPushButton#advancedLinkButton {"
            "border: none; background: transparent; padding: 0;"
            "text-decoration: underline; color: palette(link);"
            "}"
            "QPushButton#advancedLinkButton:hover { color: palette(highlight); }"
        )
        advanced_button.clicked.connect(functools.partial(self.advanced_clicked, advanced_button))

        status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        advanced_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        status_layout.addWidget(status_label, 1, Qt.AlignVCenter)
        status_layout.addWidget(advanced_button, 0, Qt.AlignVCenter)

        self.download_groups.append({
            "param": param,
            "type": group_type,
            "combo": model_combo,
            "button": download_button,
            "status": status_label,
            "status-widget": status_widget,
            "file-settings": list(param.get("file-settings", [])),
        })
        self.advanced_buttons.append(advanced_button)
        return widget

    def advanced_clicked(self, button, checked):
        """Show or hide advanced file path rows."""
        _ = get_app()._tr
        self.advanced_visible = bool(checked)
        for label, widget in self.advanced_rows:
            label.setVisible(self.advanced_visible)
            widget.setVisible(self.advanced_visible)
        for advanced_button in self.advanced_buttons:
            advanced_button.blockSignals(True)
            advanced_button.setChecked(self.advanced_visible)
            advanced_button.setText(_("Hide Advanced") if self.advanced_visible else _("Advanced"))
            advanced_button.blockSignals(False)

    def sync_download_groups_to_selected_models(self):
        """Apply selected manifest entries to hidden file path fields."""
        for group in self.download_groups:
            self.apply_download_group_selection(group)

    def selected_download_group_model(self, group):
        """Return the selected model for a download group."""
        model_id = group["combo"].itemData(group["combo"].currentIndex())
        if group["type"] in ("download-yolo", "download-yolo5"):
            return self.yolo_model_by_id(model_id)
        manifest = self.load_manifest_models("cutie", CUTIE_MODELS_PATH)
        for model in manifest.get("models", []):
            if model.get("id") == model_id:
                return model
        return recommended_model(manifest.get("models", []))

    def apply_download_group_selection(self, group):
        """Update hidden file path fields for the selected model group."""
        model = self.selected_download_group_model(group)
        if not model:
            return
        group["button"].setText(model_download_button_label(model))
        if group["type"] in ("download-yolo", "download-yolo5"):
            self.set_yolo_file_fields(group["param"], model)
        else:
            self.set_object_mask_file_fields(group["param"], model)

    def set_file_field_path(self, setting, path):
        """Update a file field path and context without emitting intermediate callbacks."""
        if not setting or not path:
            return
        self.context[setting] = path
        field = self.file_fields.get(setting)
        if field:
            field["path"].blockSignals(True)
            field["path"].setText(path)
            field["path"].blockSignals(False)

    def model_download_index_changed(self, combo_widget, download_button, param, index):
        """Model download dropdown selection changed."""
        for group in self.download_groups:
            if group["combo"] is combo_widget:
                self.apply_download_group_selection(group)
                self.start_file_validation_wait_cursor(group)
                self.file_validation_timer.start()
                return

    def start_file_validation_wait_cursor(self, group=None):
        """Show the wait cursor while selected model file paths are being validated."""
        if group:
            group["ready"] = False
            group["validating"] = True
        model = self.selected_download_group_model(group) if group else None
        log.debug(
            "Validating selected model paths: type=%s id=%s name=%s paths=%s",
            group.get("type") if group else "",
            model.get("id") if model else "",
            model.get("name") if model else "",
            {
                setting: self.context.get(setting)
                for setting in (group.get("file-settings", []) if group else [])
            },
        )
        if not self.validation_wait_cursor:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.validation_wait_cursor = True
        self.update_selection_validation()
        if hasattr(self, "process_button"):
            self.process_button.setEnabled(False)
        QCoreApplication.processEvents()

    def restore_file_validation_wait_cursor(self):
        """Restore the cursor after model file validation completes."""
        if self.validation_wait_cursor:
            QApplication.restoreOverrideCursor()
            self.validation_wait_cursor = False

    def link_activated(self, widget, param, value):
        """Link activated"""
        webbrowser.open(value, new=1)

    def model_message(self, message, model=None):
        """Format a translated message with the object detection model name."""
        model_name = (model or {}).get("name") or YOLO_FALLBACK_MODEL_NAME
        return message % {"model": model_name}

    def load_yolo_models(self):
        """Load packaged YOLO model metadata for the Object Detection initializer."""
        if self.yolo_models_manifest is None:
            self.yolo_models_manifest = load_yolo_models_manifest()
            self.yolo_models = self.yolo_models_manifest.get("models", [])

    def yolo_model_by_id(self, model_id):
        """Return a YOLO model manifest entry by id."""
        for model in self.yolo_models:
            if model.get("id") == model_id:
                return model
        return self.yolo_models[0] if self.yolo_models else None

    def selected_yolo_model(self, widget):
        """Return the model selected in the YOLO download dropdown."""
        return self.yolo_model_by_id(widget.itemData(widget.currentIndex()))

    def yolo_model_index_changed(self, widget, download_button, param, index):
        """YOLO model selection changed."""
        model = self.yolo_model_by_id(widget.itemData(index))
        if model:
            download_button.setText(yolo_download_button_label(model))
            self.set_yolo_file_fields(param, model)

    def efficient_sam_model_by_id(self, model_id=None):
        """Return an EfficientSAM manifest entry by id or the recommended entry."""
        manifest = self.load_manifest_models("efficient-sam", EFFICIENT_SAM_MODELS_PATH)
        models = manifest.get("models", [])
        for model in models:
            if model.get("id") == model_id:
                return model
        return recommended_model(models)

    def object_mask_cutie_paths(self, cutie_model):
        """Return Object Mask Cutie paths for the selected quality tier."""
        model_files = CUTIE_MODEL_FILES.get(cutie_model.get("id"), CUTIE_MODEL_FILES["cutie-medium"])
        install_dir = model_install_dir(cutie_model)
        return {key: os.path.join(install_dir, filename) for key, filename in model_files.items()}

    def object_mask_efficient_sam_path(self, efficient_sam_model):
        """Return the Object Mask EfficientSAM path for the selected SAM model."""
        filename = EFFICIENT_SAM_MODEL_FILES.get(
            efficient_sam_model.get("id"),
            EFFICIENT_SAM_MODEL_FILES["efficient-sam-tiny-1024"],
        )
        return os.path.join(model_install_dir(efficient_sam_model), filename)

    def set_object_mask_file_fields(self, param, cutie_model):
        """Point the Object Mask file inputs at the selected quality files."""
        efficient_sam_model = self.efficient_sam_model_by_id()
        self.context["cutie_model_dir"] = model_install_dir(cutie_model)
        self.context["model_size"] = 1024
        path_updates = {
            param.get("efficient-sam-setting"): self.object_mask_efficient_sam_path(efficient_sam_model),
        }
        cutie_paths = self.object_mask_cutie_paths(cutie_model)
        for file_key, setting in (param.get("cutie-settings") or {}).items():
            path_updates[setting] = cutie_paths.get(file_key)

        log.debug(
            "Object Mask model selection applied: cutie_id=%s cutie_name=%s efficient_sam_id=%s paths=%s",
            cutie_model.get("id") if cutie_model else "",
            cutie_model.get("name") if cutie_model else "",
            efficient_sam_model.get("id") if efficient_sam_model else "",
            path_updates,
        )
        for setting, path in path_updates.items():
            self.set_file_field_path(setting, path)

    def spinner_value_changed(self, widget, param, value):
        """Spinner value change callback"""
        self.context[param["setting"]] = value
        log.info(self.context)

    def bool_value_changed(self, widget, param, state):
        """Boolean value change callback"""
        if state == Qt.Checked:
            self.context[param["setting"]] = True
        else:
            self.context[param["setting"]] = False
        log.info(self.context)

    def dropdown_index_changed(self, widget, param, index):
        """Dropdown value change callback"""
        value = widget.itemData(index)
        self.context[param["setting"]] = value
        log.info(self.context)

    def text_value_changed(self, widget, param, value=None):
        """Textbox value change callback"""
        try:
            # Attempt to load value from QTextEdit (i.e. multi-line)
            if not value:
                value = widget.toPlainText()
        except:
            log.debug('Failed to get plain text from widget')

        self.context[param["setting"]] = value
        log.info(self.context)

    def file_value_changed(self, widget, param, value=None):
        """File path textbox change callback"""
        if value is None:
            value = widget.text()
        self.context[param["setting"]] = value
        log.debug("File path changed, scheduling validation: setting=%s path=%s", param["setting"], value)
        group = next(
            (
                download_group
                for download_group in self.download_groups
                if param["setting"] in download_group.get("file-settings", [])
            ),
            None,
        )
        self.start_file_validation_wait_cursor(group)
        self.file_validation_timer.start()
        log.info(self.context)

    def file_browse_clicked(self, widget, param):
        """Browse for a file path."""
        _ = get_app()._tr
        current_path = widget.text()
        start_dir = os.path.dirname(current_path) if current_path else info.USER_PATH
        selected_path = QFileDialog.getOpenFileName(
            self,
            _("Choose %s") % _(param["title"]),
            start_dir,
            _(param.get("file-filter", "All files (*)")),
        )[0]
        if selected_path:
            widget.setText(selected_path)

    def validate_onnx_model_load(self, path):
        """Return whether OpenCV can load this ONNX model."""
        _ = get_app()._tr
        try:
            stat = os.stat(path)
        except OSError:
            return False, _("File not found")

        cache_key = (os.path.abspath(path), stat.st_mtime_ns, stat.st_size)
        cached = self.onnx_validation_cache.get(cache_key)
        if cached:
            return cached

        try:
            error_text = openshot.ClipProcessingJobs.ValidateONNXModel(path)
        except Exception as ex:
            error_text = str(ex)

        if not error_text:
            result = (True, _("Ready"))
        else:
            log.error("ONNX model validation failed: %s", error_text)
            result = (False, error_text)
            if "Unsupported data type: FLOAT16" in error_text:
                result = (
                    False,
                    self.model_message(_("%(model)s requires an FP32 model file for this OpenCV build.")),
                )

        self.onnx_validation_cache[cache_key] = result
        return result

    def validate_file_param(self, param, path):
        """Validate a pre-processing file field."""
        _ = get_app()._tr
        if param.get("required") and not path:
            return False, _("Required file")
        if not path:
            return True, ""
        if not os.path.isfile(path):
            return False, _("File not found")

        validator = param.get("validator")
        if validator == "onnx":
            if not path.lower().endswith(".onnx"):
                return False, _("Expected a model file.")
            if os.path.getsize(path) <= 0:
                return False, _("Model file is empty.")
            return self.validate_onnx_model_load(path)
        if validator == "classes":
            try:
                with open(path, "r", encoding="utf-8") as classes_file:
                    class_names = [line.strip() for line in classes_file if line.strip()]
            except OSError:
                return False, _("Unable to read class names")
            if not class_names:
                return False, _("Class names file is empty")
        return True, _("Ready")

    @staticmethod
    def object_mask_payload_to_source_pixels(payload, preview_size, source_size):
        """Scale annotation payload coordinates from preview pixels to source-frame pixels."""
        if not isinstance(payload, dict):
            return payload
        if not preview_size or not source_size:
            return payload

        try:
            preview_width = float(preview_size.width())
            preview_height = float(preview_size.height())
            source_width = float(source_size.width())
            source_height = float(source_size.height())
        except Exception:
            return payload
        if preview_width <= 0.0 or preview_height <= 0.0 or source_width <= 0.0 or source_height <= 0.0:
            return payload

        scale_x = source_width / preview_width
        scale_y = source_height / preview_height
        scaled = json.loads(json.dumps(payload))

        for frame_payload in (scaled.get("frames") or {}).values():
            if not isinstance(frame_payload, dict):
                continue
            for key in ("positive_points", "negative_points"):
                for point in frame_payload.get(key) or []:
                    if not isinstance(point, dict):
                        continue
                    point["x"] = float(point.get("x", 0.0)) * scale_x
                    point["y"] = float(point.get("y", 0.0)) * scale_y
            for key in ("positive_rects", "negative_rects"):
                for rect in frame_payload.get(key) or []:
                    if not isinstance(rect, dict):
                        continue
                    rect["x1"] = float(rect.get("x1", 0.0)) * scale_x
                    rect["x2"] = float(rect.get("x2", 0.0)) * scale_x
                    rect["y1"] = float(rect.get("y1", 0.0)) * scale_y
                    rect["y2"] = float(rect.get("y2", 0.0)) * scale_y

        return scaled

    @staticmethod
    def object_mask_context_from_payload(payload):
        """Convert SelectRegion annotation payload into ObjectMask preprocessing settings."""
        if not isinstance(payload, dict):
            return {}, False
        frames = payload.get("frames") or {}
        if not isinstance(frames, dict) or not frames:
            return {}, False

        try:
            seed_frame_key = str(payload.get("seed_frame") or sorted(int(f) for f in frames.keys())[0])
        except Exception:
            seed_frame_key = sorted(frames.keys())[0]
        frame_payload = frames.get(seed_frame_key) or frames.get(str(seed_frame_key)) or {}

        context = {}
        positive_points = frame_payload.get("positive_points") or []
        negative_points = frame_payload.get("negative_points") or []
        positive_rects = frame_payload.get("positive_rects") or []
        negative_rects = frame_payload.get("negative_rects") or []
        context["positive_points"] = list(positive_points)
        context["negative_points"] = list(negative_points)
        context["positive_rects"] = list(positive_rects)
        context["negative_rects"] = list(negative_rects)

        if positive_rects:
            rect = positive_rects[0]
            x1 = float(rect.get("x1", 0.0))
            y1 = float(rect.get("y1", 0.0))
            x2 = float(rect.get("x2", 0.0))
            y2 = float(rect.get("y2", 0.0))
            context.update({
                "rect_x1": min(x1, x2),
                "rect_y1": min(y1, y2),
                "rect_x2": max(x1, x2),
                "rect_y2": max(y1, y2),
            })
            if not positive_points:
                context.update({
                    "positive_x": (x1 + x2) / 2.0,
                    "positive_y": (y1 + y2) / 2.0,
                })

        if positive_points:
            point = positive_points[0]
            context.update({
                "positive_x": float(point.get("x", 0.0)),
                "positive_y": float(point.get("y", 0.0)),
            })

        if negative_points:
            point = negative_points[0]
            context.update({
                "negative_x": float(point.get("x", 0.0)),
                "negative_y": float(point.get("y", 0.0)),
            })

        return context, "positive_x" in context and "positive_y" in context

    def object_mask_processing_frame_size(self, payload):
        """Return the frame size that libopenshot will use while processing ObjectMask."""
        if not isinstance(payload, dict):
            return QSize()
        try:
            frames = payload.get("frames") or {}
            seed_frame = int(payload.get("seed_frame") or sorted(int(f) for f in frames.keys())[0])
        except Exception:
            seed_frame = 1
        try:
            frame = self.clip_instance.GetFrame(max(1, seed_frame))
            if frame:
                width = int(frame.GetWidth())
                height = int(frame.GetHeight())
                if width > 0 and height > 0:
                    return QSize(width, height)
        except Exception as ex:
            log.warning("Unable to read Object Mask processing frame size: %s", ex)
        return QSize()

    def update_selection_validation(self):
        """Update selection indicators and return whether all required selections are valid."""
        _ = get_app()._tr
        all_valid = True
        object_mask_ready = all(
            group.get("ready")
            for group in self.download_groups
            if group.get("type") == "download-object-mask"
        )
        for setting, field in self.selection_fields.items():
            valid = bool(field.get("valid"))
            button = field.get("button")
            if button is not None:
                button.setEnabled(object_mask_ready)
                if object_mask_ready:
                    button.setToolTip(_("Choose a positive point or rectangle, and optional negative points."))
                else:
                    button.setToolTip(_("Download valid Object Mask model files before selecting points."))
            status = field["status"]
            status.setText("✓" if valid else "✕")
            status.setStyleSheet("color: #4caf50; font-weight: bold;" if valid else "color: #e53935; font-weight: bold;")
            if valid:
                status.setToolTip(_("Ready"))
            elif object_mask_ready:
                status.setToolTip(_("Select a positive point or rectangle."))
            else:
                status.setToolTip(_("Object Mask model files are not ready."))
            all_valid = all_valid and valid
        return all_valid

    def update_file_validation(self):
        """Update validation indicators and Process button state."""
        if self.file_validation_timer.isActive():
            self.file_validation_timer.stop()

        try:
            all_valid = True
            file_results = {}
            for setting, field in self.file_fields.items():
                path = field["path"].text()
                valid, message = self.validate_file_param(field["param"], path)
                file_results[setting] = {
                    "valid": valid,
                    "message": message,
                    "path": path,
                }
                status = field["status"]
                status.setText("✓" if valid else "✕")
                status.setStyleSheet("color: #4caf50; font-weight: bold;" if valid else "color: #e53935; font-weight: bold;")
                status.setToolTip(message)
                all_valid = all_valid and valid

            self.update_download_group_statuses(file_results)
            all_valid = all_valid and self.update_selection_validation()

            if hasattr(self, "process_button"):
                self.process_button.setEnabled(all_valid and not self.processing_effect)
        finally:
            self.restore_file_validation_wait_cursor()

    def update_download_group_statuses(self, file_results):
        """Update visible status text for model download groups."""
        _ = get_app()._tr
        for group in self.download_groups:
            expected_settings = group.get("file-settings", [])
            results = [
                file_results[setting]
                for setting in expected_settings
                if setting in file_results
            ]
            status = group["status"]
            group["validating"] = False
            partial_downloads = self.download_group_partial_files(group)
            if not results or len(results) != len(expected_settings):
                group["ready"] = False
                log.debug(
                    "Model path validation incomplete: type=%s expected=%s available=%s",
                    group.get("type"),
                    expected_settings,
                    sorted(file_results.keys()),
                )
                status.setText(_("Not Downloaded"))
                status.setStyleSheet("color: #e53935; font-weight: bold;")
                status.setToolTip(_("Required model files are not downloaded."))
                continue

            missing = any(
                not result.get("path") or result.get("message") in (_("File not found"), _("Required file"))
                for result in results
            )
            valid = all(result.get("valid") for result in results)
            group["ready"] = valid and not partial_downloads
            log.debug(
                "Model path validation complete: type=%s ready=%s valid=%s partials=%s results=%s",
                group.get("type"),
                group.get("ready"),
                valid,
                partial_downloads,
                {
                    setting: {
                        "valid": file_results[setting].get("valid"),
                        "path": file_results[setting].get("path"),
                        "message": file_results[setting].get("message"),
                    }
                    for setting in expected_settings
                    if setting in file_results
                },
            )
            if valid and not partial_downloads:
                status.setText(_("Ready"))
                status.setStyleSheet("color: #4caf50; font-weight: bold;")
                status.setToolTip(_("All required model files are ready."))
            elif partial_downloads:
                status.setText(_("Not Downloaded"))
                status.setStyleSheet("color: #e53935; font-weight: bold;")
                status.setToolTip(_("A model download is incomplete. Download again to finish installation."))
            elif missing:
                status.setText(_("Not Downloaded"))
                status.setStyleSheet("color: #e53935; font-weight: bold;")
                status.setToolTip(_("Required model files are not downloaded."))
            else:
                status.setText(_("Invalid"))
                status.setStyleSheet("color: #e53935; font-weight: bold;")
                status.setToolTip(_("One or more model files are invalid."))

    def download_group_partial_files(self, group):
        """Return leftover partial downloads for a model download group."""
        dirs = []
        if group.get("type") in ("download-yolo", "download-yolo5"):
            model = self.selected_download_group_model(group)
            if model:
                dirs.append(yolo_model_dir(model))
        elif group.get("type") == "download-object-mask":
            cutie_model = self.selected_download_group_model(group)
            efficient_sam_model = self.efficient_sam_model_by_id()
            if efficient_sam_model:
                dirs.append(model_install_dir(efficient_sam_model))
            if cutie_model:
                dirs.append(model_install_dir(cutie_model))

        partials = []
        for directory in dirs:
            try:
                for filename in os.listdir(directory):
                    if filename.endswith((".download", ".zip")):
                        partials.append(os.path.join(directory, filename))
            except OSError:
                continue
        return partials

    def set_processing_controls_enabled(self, enabled):
        """Enable or disable editable processing controls."""
        self.scrollArea.setEnabled(enabled)
        self.process_button.setEnabled(enabled)
        self.cancel_button.setEnabled(True)

    @staticmethod
    def cancel_processing_job(processing, max_wait_seconds=1.0):
        """Cancel a native processing job and tolerate its handle becoming invalid."""
        try:
            processing.CancelProcessing()
        except RuntimeError:
            # Cancellation can invalidate the SWIG-backed job immediately.
            return

        wait_start = time.time()
        while (time.time() - wait_start) < max_wait_seconds:
            try:
                if processing.IsDone():
                    return
            except RuntimeError:
                # An invalid handle after CancelProcessing means there is
                # nothing left for the dialog to poll.
                return
            QCoreApplication.processEvents()
            time.sleep(0.01)

    def file_sha256(self, path):
        """Return the SHA256 checksum of a file."""
        digest = hashlib.sha256()
        with open(path, "rb") as input_file:
            for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def yolo_installed_files_match(self, model):
        """Return whether an installed YOLO model matches recorded metadata."""
        model_path = yolo_model_path(model)
        classes_path = yolo_classes_path(model)
        metadata_path = os.path.join(yolo_model_dir(model), YOLO_INSTALL_METADATA)
        try:
            with open(metadata_path, "r", encoding="utf-8") as metadata_file:
                metadata = json.load(metadata_file)
            return (
                metadata.get("id") == model.get("id")
                and metadata.get("asset_sha256") == model.get("sha256")
                and os.path.isfile(model_path)
                and os.path.isfile(classes_path)
                and metadata.get("model_sha256") == self.file_sha256(model_path)
                and metadata.get("classes_sha256") == self.file_sha256(classes_path)
            )
        except (OSError, ValueError):
            return False

    def set_yolo_file_fields(self, param, model):
        """Point the YOLO file inputs at the selected model files."""
        for setting, path in (
            (param.get("model-setting"), yolo_model_path(model)),
            (param.get("classes-setting"), yolo_classes_path(model)),
        ):
            self.set_file_field_path(setting, path)

    def yolo_model_download_url(self, model):
        """Return the download URL for a YOLO model manifest entry."""
        base_url = self.yolo_models_manifest.get("base_url", "")
        return urljoin("%s/" % base_url.rstrip("/"), model.get("asset", ""))

    def model_download_url(self, manifest, model):
        """Return the download URL for a generic model manifest entry."""
        base_url = manifest.get("base_url", "")
        return urljoin("%s/" % base_url.rstrip("/"), model.get("asset", ""))

    def extract_yolo_zip_member(self, yolo_zip, suffixes, destination_path):
        """Extract the first matching file from a verified YOLO model archive."""
        if isinstance(suffixes, str):
            suffixes = (suffixes,)
        for member in yolo_zip.infolist():
            if member.is_dir():
                continue
            if os.path.basename(member.filename).lower().endswith(tuple(suffixes)):
                with yolo_zip.open(member) as source_file, open(destination_path, "wb") as output_file:
                    output_file.write(source_file.read())
                return
        raise ValueError("Downloaded YOLO files are invalid.")

    def extract_zip_members_to_dir(self, zip_path, destination_dir):
        """Extract all regular files from a verified model archive."""
        os.makedirs(destination_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path) as model_zip:
            for member in model_zip.infolist():
                if member.is_dir():
                    continue
                filename = os.path.basename(member.filename)
                if not filename:
                    continue
                destination_path = os.path.join(destination_dir, filename)
                download_path = "{}.download".format(destination_path)
                with model_zip.open(member) as source_file, open(download_path, "wb") as output_file:
                    output_file.write(source_file.read())
                if os.path.getsize(download_path) <= 0:
                    os.remove(download_path)
                    raise ValueError("Downloaded model files are invalid.")
                os.replace(download_path, destination_path)

    def write_model_install_metadata(self, install_dir, metadata_name, model, installed_paths):
        """Record extracted-file hashes for future already-downloaded checks."""
        metadata_path = os.path.join(install_dir, metadata_name)
        metadata_download_path = "{}.download".format(metadata_path)
        with open(metadata_download_path, "w", encoding="utf-8") as metadata_file:
            json.dump(
                {
                    "id": model.get("id"),
                    "asset": model.get("asset"),
                    "asset_sha256": model.get("sha256"),
                    "files": {
                        os.path.basename(path): self.file_sha256(path)
                        for path in installed_paths
                    },
                },
                metadata_file,
                indent=2,
                sort_keys=True,
            )
            metadata_file.write("\n")
        os.replace(metadata_download_path, metadata_path)

    def installed_model_files_match(self, install_dir, metadata_name, model, installed_paths):
        """Return whether installed model files match recorded metadata."""
        metadata_path = os.path.join(install_dir, metadata_name)
        try:
            with open(metadata_path, "r", encoding="utf-8") as metadata_file:
                metadata = json.load(metadata_file)
            file_hashes = metadata.get("files", {})
            return (
                metadata.get("id") == model.get("id")
                and metadata.get("asset_sha256") == model.get("sha256")
                and all(
                    os.path.isfile(path)
                    and file_hashes.get(os.path.basename(path)) == self.file_sha256(path)
                    for path in installed_paths
                )
            )
        except (OSError, ValueError):
            return False

    def download_manifest_archive(self, manifest, model, install_dir, metadata_name, installed_paths, progress, start, end):
        """Download, verify, and extract a generic model archive."""
        _ = get_app()._tr
        os.makedirs(install_dir, exist_ok=True)
        if self.installed_model_files_match(install_dir, metadata_name, model, installed_paths):
            return

        zip_download_path = os.path.join(install_dir, "%s.download" % model.get("asset", "model.zip"))

        def report_progress(downloaded_size, total_size):
            if total_size > 0:
                fraction = min(1.0, downloaded_size / float(total_size))
                progress.setValue(int(start + (end - start) * fraction))
            else:
                progress.setValue(start)
            QCoreApplication.processEvents()
            if progress.wasCanceled():
                raise DownloadCancelled()

        try:
            http_client.download_file(
                self.model_download_url(manifest, model),
                zip_download_path,
                model_label(model),
                report_progress,
                cancel_exceptions=(DownloadCancelled,),
            )
            if self.file_sha256(zip_download_path) != model.get("sha256"):
                raise ValueError(_("Downloaded model files are invalid."))
            self.extract_zip_members_to_dir(zip_download_path, install_dir)
            if not all(os.path.isfile(path) and os.path.getsize(path) > 0 for path in installed_paths):
                raise ValueError(_("Downloaded model files are invalid."))
            self.write_model_install_metadata(install_dir, metadata_name, model, installed_paths)
        finally:
            if os.path.exists(zip_download_path):
                os.remove(zip_download_path)

    def write_yolo_install_metadata(self, model, model_path, classes_path):
        """Record extracted-file hashes for future already-downloaded checks."""
        metadata_path = os.path.join(yolo_model_dir(model), YOLO_INSTALL_METADATA)
        metadata_download_path = "{}.download".format(metadata_path)
        with open(metadata_download_path, "w", encoding="utf-8") as metadata_file:
            json.dump(
                {
                    "id": model.get("id"),
                    "asset": model.get("asset"),
                    "asset_sha256": model.get("sha256"),
                    "model": YOLO_MODEL_FILENAME,
                    "model_sha256": self.file_sha256(model_path),
                    "classes": YOLO_CLASSES_FILENAME,
                    "classes_sha256": self.file_sha256(classes_path),
                },
                metadata_file,
                indent=2,
                sort_keys=True,
            )
            metadata_file.write("\n")
        os.replace(metadata_download_path, metadata_path)

    def download_yolo_clicked(self, widget, combo_widget, param):
        """Download the selected YOLO model files."""
        _ = get_app()._tr
        model = self.selected_yolo_model(combo_widget)
        if not model:
            QMessageBox.warning(self, _("Download Failed"), _("No YOLO models are available."))
            return

        model_dir = yolo_model_dir(model)
        model_path = yolo_model_path(model)
        classes_path = yolo_classes_path(model)
        os.makedirs(model_dir, exist_ok=True)

        if self.yolo_installed_files_match(model):
            self.set_yolo_file_fields(param, model)
            self.update_file_validation()
            QMessageBox.information(
                self,
                self.model_message(_("Download %(model)s Files"), model),
                self.model_message(_("The %(model)s files are already downloaded."), model),
            )
            return

        progress = QProgressDialog(
            self.model_message(_("Downloading %(model)s files..."), model),
            _("Cancel"),
            0,
            100,
            self,
        )
        progress.setWindowTitle(self.model_message(_("Download %(model)s Files"), model))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        zip_download_path = os.path.join(model_dir, "%s.download" % model.get("asset", "model.zip"))
        model_download_path = "{}.download".format(model_path)
        classes_download_path = "{}.download".format(classes_path)
        metadata_download_path = os.path.join(model_dir, "%s.download" % YOLO_INSTALL_METADATA)

        def remove_partial_downloads():
            for path in (zip_download_path, model_download_path, classes_download_path, metadata_download_path):
                if os.path.exists(path):
                    os.remove(path)

        def report_progress(downloaded_size, total_size):
            if total_size > 0:
                progress.setValue(min(100, int(downloaded_size * 100 / total_size)))
            else:
                progress.setValue(0)
            QCoreApplication.processEvents()
            if progress.wasCanceled():
                raise DownloadCancelled()

        try:
            http_client.download_file(
                self.yolo_model_download_url(model),
                zip_download_path,
                self.model_message(_("%(model)s files"), model),
                report_progress,
                cancel_exceptions=(DownloadCancelled,),
            )
            if self.file_sha256(zip_download_path) != model.get("sha256"):
                raise ValueError(self.model_message(_("Downloaded %(model)s files are invalid."), model))

            with zipfile.ZipFile(zip_download_path) as yolo_zip:
                self.extract_yolo_zip_member(yolo_zip, ".onnx", model_download_path)
                self.extract_yolo_zip_member(yolo_zip, (".names", ".txt"), classes_download_path)

            if os.path.getsize(model_download_path) <= 0 or os.path.getsize(classes_download_path) <= 0:
                raise ValueError(self.model_message(_("Downloaded %(model)s files are invalid."), model))

            os.replace(model_download_path, model_path)
            os.replace(classes_download_path, classes_path)
            self.write_yolo_install_metadata(model, model_path, classes_path)
        except DownloadCancelled:
            remove_partial_downloads()
            log.info("YOLO file download cancelled")
            self.update_file_validation()
            return
        except Exception as ex:
            remove_partial_downloads()
            progress.close()
            QMessageBox.warning(self, _("Download Failed"), str(ex))
            log.error("Failed to download YOLO files: %s", ex)
            self.update_file_validation()
            return
        finally:
            if os.path.exists(zip_download_path):
                os.remove(zip_download_path)
            progress.close()

        self.set_yolo_file_fields(param, model)
        self.update_file_validation()

    def download_object_mask_clicked(self, widget, combo_widget, param):
        """Download the selected Object Mask model files."""
        _ = get_app()._tr
        cutie_manifest = self.load_manifest_models("cutie", CUTIE_MODELS_PATH)
        cutie_model = self.selected_download_group_model({
            "type": "download-object-mask",
            "combo": combo_widget,
        })
        efficient_sam_manifest = self.load_manifest_models("efficient-sam", EFFICIENT_SAM_MODELS_PATH)
        efficient_sam_model = self.efficient_sam_model_by_id()
        if not cutie_model or not efficient_sam_model:
            QMessageBox.warning(self, _("Download Failed"), _("No Object Mask models are available."))
            return

        self.set_object_mask_file_fields(param, cutie_model)
        cutie_paths_by_key = self.object_mask_cutie_paths(cutie_model)
        cutie_paths = [
            cutie_paths_by_key[file_key]
            for file_key in ("encode-key", "encode-value", "memory-readout", "decode")
        ]
        efficient_sam_path = self.object_mask_efficient_sam_path(efficient_sam_model)
        efficient_sam_install_dir = model_install_dir(efficient_sam_model)
        cutie_install_dir = model_install_dir(cutie_model)

        efficient_sam_ready = self.installed_model_files_match(
            efficient_sam_install_dir,
            EFFICIENT_SAM_INSTALL_METADATA,
            efficient_sam_model,
            [efficient_sam_path],
        )
        cutie_ready = self.installed_model_files_match(
            cutie_install_dir,
            CUTIE_INSTALL_METADATA,
            cutie_model,
            cutie_paths,
        )

        if efficient_sam_ready and cutie_ready:
            self.update_file_validation()
            QMessageBox.information(
                self,
                _("Download Object Mask Files"),
                _("The Object Mask files are already downloaded."),
            )
            return

        progress = QProgressDialog(
            _("Downloading Object Mask files..."),
            _("Cancel"),
            0,
            100,
            self,
        )
        progress.setWindowTitle(_("Download Object Mask Files"))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        if efficient_sam_ready:
            efficient_sam_range = None
            cutie_range = (0, 100)
        elif cutie_ready:
            efficient_sam_range = (0, 100)
            cutie_range = None
        else:
            efficient_sam_range = (0, 35)
            cutie_range = (35, 100)

        try:
            if efficient_sam_range:
                self.download_manifest_archive(
                    efficient_sam_manifest,
                    efficient_sam_model,
                    efficient_sam_install_dir,
                    EFFICIENT_SAM_INSTALL_METADATA,
                    [efficient_sam_path],
                    progress,
                    efficient_sam_range[0],
                    efficient_sam_range[1],
                )
            if cutie_range:
                self.download_manifest_archive(
                    cutie_manifest,
                    cutie_model,
                    cutie_install_dir,
                    CUTIE_INSTALL_METADATA,
                    cutie_paths,
                    progress,
                    cutie_range[0],
                    cutie_range[1],
                )
        except DownloadCancelled:
            log.info("Object Mask file download cancelled")
            self.update_file_validation()
            return
        except Exception as ex:
            QMessageBox.warning(self, _("Download Failed"), str(ex))
            log.error("Failed to download Object Mask files: %s", ex)
            self.update_file_validation()
            return
        finally:
            progress.close()

        self.set_object_mask_file_fields(param, cutie_model)
        self.update_file_validation()

    def rect_select_clicked(self, widget, param):
        """Rect select button clicked"""
        _ = get_app()._tr
        self.context[param["setting"]].update({"button-clicked": True})

        # show dialog
        from windows.region import SelectRegion
        from classes.query import File, Clip

        c = Clip.get(id=self.clip_id)
        reader_path = c.data.get('reader', {}).get('path','')
        f = File.get(path=reader_path)
        if f:
            win = SelectRegion(f, self.clip_instance, parent=self)
            # Run the dialog event loop - blocking interaction on this window during that time
            result = win.exec_()
            if result == QDialog.Accepted:
                # self.first_frame = win.current_frame
                # Region selected (get coordinates if any)
                selected_rect = win.selected_rect_normalized() if hasattr(win, "selected_rect_normalized") else None
                if selected_rect:
                    x1 = float(selected_rect.get("normalized_x", 0.0))
                    y1 = float(selected_rect.get("normalized_y", 0.0))
                    xw = float(selected_rect.get("normalized_width", 0.0))
                    yh = float(selected_rect.get("normalized_height", 0.0))
                else:
                    topLeft = win.videoPreview.regionTopLeftHandle
                    bottomRight = win.videoPreview.regionBottomRightHandle
                    curr_frame_size = win.videoPreview.curr_frame_size
                    if not topLeft or not bottomRight or not curr_frame_size:
                        QMessageBox.warning(
                            self,
                            _("Invalid Region"),
                            _("Please draw a rectangle region before clicking Select Region."),
                        )
                        return
                    x1 = topLeft.x() / curr_frame_size.width()
                    y1 = topLeft.y() / curr_frame_size.height()
                    x2 = bottomRight.x() / curr_frame_size.width()
                    y2 = bottomRight.y() / curr_frame_size.height()
                    xw = x2 - x1
                    yh = y2 - y1

                # Get QImage of region
                region_qimage = win.selected_region_qimage() if hasattr(win, "selected_region_qimage") else None
                if region_qimage is None and win.videoPreview.region_qimage:
                    region_qimage = win.videoPreview.region_qimage
                if region_qimage:

                    # Resize QImage to match button size
                    resized_qimage = region_qimage.scaled(widget.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

                    # Remove button text (so region QImage is more visible)
                    widget.setImage(resized_qimage)
                    widget.setText("")

                # If data found, add to context
                self.context[param["setting"]].update({"normalized_x": x1, "normalized_y": y1,
                                                       "normalized_width": xw,
                                                       "normalized_height": yh,
                                                       "first-frame": win.current_frame,
                                                       })
                log.info(self.context)

        else:
            log.error('No file found with path: %s' % reader_path)

    def object_mask_select_clicked(self, widget, param):
        """Open annotation selector for Object Mask prompts."""
        _ = get_app()._tr
        from windows.region import SelectRegion
        from classes.query import File, Clip

        self.sync_download_groups_to_selected_models()
        self.update_file_validation()
        object_mask_groups = [
            group for group in self.download_groups
            if group.get("type") == "download-object-mask"
        ]
        if object_mask_groups and not all(group.get("ready") for group in object_mask_groups):
            QMessageBox.warning(
                self,
                _("Object Mask Models Not Ready"),
                _("Download valid Object Mask model files before selecting points."),
            )
            return

        c = Clip.get(id=self.clip_id)
        reader_path = c.data.get('reader', {}).get('path', '')
        f = File.get(path=reader_path)
        if not f:
            log.error('No file found with path: %s' % reader_path)
            return

        log.debug(
            "Opening Object Mask selector with preview models: efficient_sam=%s cutie_key=%s "
            "cutie_value=%s cutie_memory=%s cutie_decode=%s processing_device=%s",
            self.context.get("efficient_sam_model"),
            self.context.get("cutie_encode_key_model"),
            self.context.get("cutie_encode_value_model"),
            self.context.get("cutie_memory_readout_model"),
            self.context.get("cutie_decode_model"),
            self.context.get("processing-device") or self.context.get("processing_device"),
        )
        win = SelectRegion(
            f,
            self.clip_instance,
            selection_mode="annotate",
            parent=self,
            object_mask_preview_context=dict(self.context),
        )
        result = win.exec_()
        if result != QDialog.Accepted:
            return

        payload = win.selection_payload() if hasattr(win, "selection_payload") else {}
        preview_size = getattr(win.videoPreview, "curr_frame_size", None)
        processing_size = self.object_mask_processing_frame_size(payload)
        if not processing_size.isValid() or processing_size.width() <= 0 or processing_size.height() <= 0:
            processing_size = QSize(int(getattr(win, "width", 0) or 0), int(getattr(win, "height", 0) or 0))
        log.debug(
            "Object Mask selection scale: preview=%sx%s processing=%sx%s",
            preview_size.width() if preview_size else 0,
            preview_size.height() if preview_size else 0,
            processing_size.width(),
            processing_size.height(),
        )
        payload = self.object_mask_payload_to_source_pixels(payload, preview_size, processing_size)

        prompt_context, valid = self.object_mask_context_from_payload(payload)
        if not valid:
            QMessageBox.warning(
                self,
                _("Invalid Selection"),
                _("Please select a positive point or rectangle."),
            )
            return

        self.context[param["setting"]] = payload
        self.context.update(prompt_context)

        field = self.selection_fields.get(param["setting"])
        if field:
            field["valid"] = True
            includes = len(prompt_context.get("positive_points") or []) + len(prompt_context.get("positive_rects") or [])
            excludes = len(prompt_context.get("negative_points") or []) + len(prompt_context.get("negative_rects") or [])
            if includes == 0 and "positive_x" in prompt_context:
                includes = 1
            label_args = {
                "include": includes,
                "exclude": excludes,
            }
            if excludes > 0:
                button_text = _("Selection: %(include)s include, %(exclude)s exclude") % label_args
            else:
                button_text = _("Selection: %(include)s include") % label_args
            field["button"].setText(
                button_text
            )
        self.update_file_validation()
        log.info(self.context)

    def accept(self):
        """ Start processing effect """
        _ = get_app()._tr
        self.update_file_validation()
        if self.file_fields and not self.process_button.isEnabled():
            return

        # Enable ProgressBar
        self.progressBar.setEnabled(True)
        self.processing_effect = True
        self.set_processing_controls_enabled(False)

        # Print effect settings
        log.info(self.context)

        # Create effect Id and protobuf data path
        ID = get_app().project.generate_id()

        # Create protobuf data path
        protobufPath = os.path.join(info.PROTOBUF_DATA_PATH, ID + '.data')
        if os.name == 'nt' : protobufPath = protobufPath.replace("\\", "/")

        self.context["protobuf_data_path"] = protobufPath

        # Load into JSON string info about protobuf data path
        jsonString = json.dumps(self.context)

        def show_processing_error(message=None):
            """Show a processing failure and leave the dialog open for correction."""
            if not message:
                message = _("Unable to process this effect. Check the model files and settings.")
            self.progressBar.setEnabled(False)
            self.processing_effect = False
            self.set_processing_controls_enabled(True)
            self.update_file_validation()
            QMessageBox.warning(self, _("Processing Failed"), message)

        # Generate processed data
        try:
            processing = openshot.ClipProcessingJobs(self.effect_class, jsonString)
            processing.processClip(self.clip_instance, jsonString)
        except Exception as ex:
            log.error("Failed to start effect processing: %s", ex)
            show_processing_error(str(ex))
            return

        # get processing status
        blank_error_start = None
        while(not processing.IsDone() ):
            if processing.GetError():
                message = (processing.GetErrorMessage() or "").strip()
                if message:
                    log.error("Effect processing failed: %s", message)
                    self.cancel_processing_job(processing)
                    show_processing_error(message)
                    return
                if blank_error_start is None:
                    blank_error_start = time.time()
                elif time.time() - blank_error_start > 3.0:
                    log.error("Effect processing failed without an error message")
                    self.cancel_processing_job(processing)
                    show_processing_error()
                    return
            else:
                blank_error_start = None

            # update progressbar
            progressionStatus = processing.GetProgress()
            self.progressBar.setValue(int(progressionStatus))
            time.sleep(0.01)

            # Process any queued events
            QCoreApplication.processEvents()

            # if the cancel button was pressed, close the processing thread
            if(self.cancel_clip_processing):
                self.cancel_processing_job(processing)
                return

        if not self.cancel_clip_processing and processing.GetError():
            message = (processing.GetErrorMessage() or "").strip()
            log.error(
                "Effect processing failed%s",
                ": %s" % message if message else "",
            )
            show_processing_error(message)
            return

        if(not self.cancel_clip_processing):
            # Load processed data into effect
            self.effect = openshot.EffectInfo().CreateEffect(self.effect_class)
            self.effect.SetJson( '{"protobuf_data_path": "%s"}' % protobufPath )
            self.effect.Id(ID)

            # Accept dialog
            self.restore_file_validation_wait_cursor()
            super(ProcessEffect, self).accept()

    def reject(self):
        # Cancel dialog
        self.exporting = False
        self.cancel_clip_processing = True
        self.restore_file_validation_wait_cursor()
        super(ProcessEffect, self).reject()
