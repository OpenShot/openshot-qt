"""
 @file
 @brief This file loads the title editor dialog (i.e SVG creator)
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Andy Finch <andy@openshot.org>

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
import re
import shutil
import sys
import functools
import subprocess
import tempfile
import threading
import time

# TODO: Is there a defusedxml substitute for getDOMImplementation?
# Is one even necessary, or is it safe to use xml.dom.minidom for that?
from xml.dom import minidom

from PyQt5.QtCore import Qt, pyqtSlot, QTimer, pyqtSignal, QRect, QPoint, QSize, QEvent
from PyQt5.QtGui import QFontDatabase, QColor, QIcon, QFont, QFontInfo, QPixmap, QPainter
from PyQt5.QtWidgets import (
    QWidget,
    QMessageBox, QDialog, QColorDialog, QFontDialog,
    QPushButton, QLineEdit, QLabel, QDialogButtonBox
)

import openshot

from classes import info, ui_util
from classes.logger import log
from classes.app import get_app
from classes.metrics import track_metric_screen
from windows.color_picker import ColorPicker, draw_checkerboard
from classes.style_tools import style_to_dict, dict_to_style, set_if_existing
from windows.views.titles_listview import TitlesListView


class TitleEditor(QDialog):
    """ Title Editor Dialog """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'title-editor.ui')
    thumbnailReady = pyqtSignal(object)

    def __init__(self, *args, edit_file_path=None, duplicate=False, **kwargs):

        # Create dialog class
        super().__init__(*args, **kwargs)

        # Init font DB
        self.font_db = QFontDatabase()

        # A timer to pause until user input stops before updating the svg
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(50)
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.save_and_reload)

        self.app = get_app()
        self.project = self.app.project
        self.edit_file_path = edit_file_path
        self.duplicate = duplicate
        self.filename = None
        self.env = dict(os.environ)

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init UI
        ui_util.init_ui(self)

        # In your widget's initialization:
        self.lblPreviewLabel.installEventFilter(self)

        # Set up the buttons
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.saveButton = self.buttonBox.button(QDialogButtonBox.Save)
        self.cancelButton = self.buttonBox.button(QDialogButtonBox.Cancel)

        # Set object names (for theme styles)
        self.saveButton.setObjectName("acceptButton")
        self.cancelButton.setObjectName("cancelButton")
        self.layout().addWidget(self.buttonBox)

        # Connect the buttons
        self.saveButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)

        # Track metrics
        track_metric_screen("title-screen")

        # Get environment variables needed for launching a process without trying to load libraries
        # from our frozen app bundle
        if sys.platform == "linux":
            self.env.pop('LD_LIBRARY_PATH', None)
            log.debug('Removing custom LD_LIBRARY_PATH from environment variables when launching Inkscape')

        # Initialize variables
        self.is_thread_busy = False
        self.template_name = ""
        imp = minidom.getDOMImplementation()
        self.xmldoc = imp.createDocument(None, "any", None)

        self.bg_color_code = QColor(Qt.black)
        self.font_color_code = QColor(Qt.white)

        self.bg_style_string = ""
        self.title_style_string = ""
        self.subtitle_style_string = ""

        self.new_title_text = ""
        self.sub_title_text = ""
        self.subTitle = False

        self.display_name = ""
        self.tspan_nodes = None

        self.default_font_family = "DejaVu Sans"
        self.qfont = self.get_font(self.default_font_family)

        # Add titles list view
        self.titlesView = TitlesListView(parent=self, window=self)
        self.verticalLayout.addWidget(self.titlesView)

        # Disable Save button on window load
        self.buttonBox.button(self.buttonBox.Save).setEnabled(False)

        # Connect thumbnail listener
        self.thumbnailReady.connect(self.display_pixmap)

        # If editing existing title svg file
        if self.edit_file_path:
            # Hide list of templates
            self.widget.setVisible(False)

            # Create temp version of title
            self.create_temp_title(self.edit_file_path)

            # Add all widgets for editing
            self.load_svg_template()

            # Display image (slight delay to allow screen to be shown first)
            QTimer.singleShot(50, self.display_svg)

    def eventFilter(self, obj, event):
        if obj is self.lblPreviewLabel and event.type() == QEvent.Resize:
            # Update preview image when label is resized
            self.update_timer.start(50)
        return super(TitleEditor, self).eventFilter(obj, event)

    def get_font(self, requested_font_name):
        """
        Checks for a valid font name and returns a QFont object.
        If the requested font is not available, it falls back to common fonts.

        :param requested_font_name: The name of the font to search for.
        :return: QFont object of either the requested font or the first available fallback font.
        """
        available_fonts = self.font_db.families()
        fallback_fonts = ['DejaVu Sans', 'Liberation Sans', 'Noto Sans', 'FreeSans',
                          'Ubuntu', 'Cantarell', 'Open Sans', 'Sans-serif', 'Arial']

        # Check if the requested font is available
        available_fonts = self.font_db.families()
        for font in available_fonts:
            if requested_font_name in font:
                return QFont(font)

        # Try fallback fonts
        for fallback in fallback_fonts:
            for font in available_fonts:
                if fallback in font:
                    return QFont(font)

        # Return the default font
        return QFont()

    def display_pixmap(self, display_pixmap):
        """Display pixmap of SVG on UI thread"""
        self.lblPreviewLabel.setPixmap(display_pixmap)

    def txtLine_changed(self, txtWidget):

        # Loop through child widgets (and remove them)
        text_list = []
        for child in self.settingsContainer.children():
            if type(child) == QLineEdit and child.objectName() != "txtFileName":
                text_list.append(child.text())

        # Update text values in the SVG
        for i, node in enumerate(self.tspan_nodes):
            if len(node.childNodes) > 0 and i <= (len(text_list) - 1):
                new_text_node = self.xmldoc.createTextNode(text_list[i])
                old_text_node = node.childNodes[0]
                node.removeChild(old_text_node)
                # add new text node
                node.appendChild(new_text_node)

        # Something changed, so update temp SVG
        self.update_timer.start()

    def display_svg(self):
        # Create a temp file for the thumbnail image
        new_file, tmp_filename = tempfile.mkstemp(suffix=".png")
        os.close(new_file)

        # Create a clip object and get the reader
        clip = openshot.Clip(self.filename)
        reader = clip.Reader()

        # Get the device pixel ratio (for high DPI)
        scale = get_app().devicePixelRatio()

        # Get the available size (logical) and the original title size
        avail_size = self.lblPreviewLabel.rect().size()
        orig_size = QSize(reader.info.width, reader.info.height)

        # Compute the target rectangle that preserves the title's aspect ratio
        target_size = orig_size.scaled(avail_size, Qt.KeepAspectRatio)
        target_rect = QRect(QPoint(0, 0), target_size)
        target_rect.moveCenter(self.lblPreviewLabel.rect().center())

        # Determine thumbnail dimensions in physical pixels
        thumb_width = round(target_rect.width() * scale)
        thumb_height = round(target_rect.height() * scale)

        # Generate the thumbnail.
        reader.Open()
        reader.GetFrame(1).Thumbnail(
            tmp_filename,
            thumb_width,
            thumb_height,
            "", "", "#00000000", False, "png", 85, 0.0)
        reader.Close()
        clip.Close()

        # Load the thumbnail pixmap and set its device pixel ratio
        preview_pixmap = QIcon(tmp_filename).pixmap(thumb_width, thumb_height)
        preview_pixmap.setDevicePixelRatio(scale)
        os.unlink(tmp_filename)

        # Create the final pixmap filled with the label's background color
        final_pixmap = QPixmap(avail_size * scale)
        final_pixmap.setDevicePixelRatio(scale)
        bg_color = self.lblPreviewLabel.palette().color(self.lblPreviewLabel.backgroundRole())
        final_pixmap.fill(bg_color)

        # Composite the checkerboard and the preview image into the target area
        painter = QPainter(final_pixmap)
        draw_checkerboard(painter, target_rect)
        painter.drawPixmap(target_rect, preview_pixmap)
        painter.end()

        # Emit the final pixmap
        self.thumbnailReady.emit(final_pixmap)

    def create_temp_title(self, template_path):
        """Set temp file path & make copy of template"""
        self.filename = os.path.join(info.USER_PATH, "title", "temp.svg")
        # Copy template to temp file (NOT preserving attributes)
        shutil.copyfile(template_path, self.filename)
        return self.filename

    def detect_font(self):
        """ Detect font from SVG: TEXT and TSPAN nodes (or use fallback font) """
        # Detect font from SVG
        for node in self.tspan_nodes:
            style = node.getAttribute("style")
            if style:
                style_dict = style_to_dict(style)
                font_family = style_dict.get("font-family", "").strip("'\"")
                font_style = style_dict.get("font-style", "normal")
                font_weight = style_dict.get("font-weight", "normal")
                font_size = style_dict.get("font-size")

                if font_family:
                    # Clean font_family string
                    if QFont(self.get_font(font_family)).exactMatch():
                        self.qfont = QFont(self.get_font(font_family))

                        # Set font style
                        if font_style == "italic":
                            self.qfont.setItalic(True)
                        else:
                            self.qfont.setItalic(False)

                        # Set font weight
                        if font_weight == "bold":
                            self.qfont.setWeight(QFont.Bold)
                        else:
                            self.qfont.setWeight(QFont.Normal)

                        # Set font size
                        if font_size:
                            if font_size.endswith("px"):
                                self.qfont.setPixelSize(int(float(font_size[:-2])))
                            elif font_size.endswith("pt"):
                                self.qfont.setPointSizeF(float(font_size[:-2]))
                        break

        # Reset default font (if none detected)
        if not self.qfont:
            self.qfont = QFont(self.get_font(self.default_font_family))

    def load_svg_template(self, filename_field=None):
        """ Load an SVG title and init all textboxes and controls """

        log.debug("Loading SVG file %s as title template", self.filename)
        # Get translation object
        _ = get_app()._tr

        # The container for all our widgets
        layout = self.settingsContainer.layout()

        # Parse the svg object
        self.xmldoc = minidom.parse(self.filename)
        # get the text elements
        self.tspan_nodes = self.xmldoc.getElementsByTagName('tspan')

        # Detect font from template (or default font as a fallback)
        self.detect_font()

        # Loop through child widgets (and remove them)
        for child in self.settingsContainer.children():
            try:
                if isinstance(child, QWidget):
                    layout.removeWidget(child)
                    child.deleteLater()
            except Exception as ex:
                log.debug('Failed to delete child settings widget: %s', ex)

        # Get text nodes and rect nodes
        self.text_nodes = self.xmldoc.getElementsByTagName('text')
        self.rect_node = self.xmldoc.getElementsByTagName('rect')

        # Create Label
        label = QLabel(self)
        label_line_text = _("File Name:")
        label.setText(label_line_text)
        label.setToolTip(label_line_text)

        # create text editor for file name
        self.txtFileName = QLineEdit(self)
        self.txtFileName.setObjectName("txtFileName")

        # If edit mode or reload, set file name
        if filename_field:
            self.txtFileName.setText(filename_field)
        elif self.edit_file_path and not self.duplicate:
            # Use existing name (and prevent editing name)
            self.txtFileName.setText(os.path.basename(self.edit_file_path))
            self.txtFileName.setEnabled(False)
        else:
            name = _("TitleFileName (%d)")
            offset = 0
            if self.duplicate and self.edit_file_path:
                # Re-use current name
                name = os.path.basename(self.edit_file_path)
                # Splits the filename into:
                #  [base-part][optional space][([number])].svg
                # Match groups are:
                #  1: Base name ("title", "Title-2", "Title number 3000")
                #  2: Space(s) preceding groups 3+4, IFF 3/4 are a match
                #  3: The entire parenthesized number ("(1)", "(20)", "(1000)")
                #  4: Just the number inside the parens ("1", "20", "1000")
                match = re.match(r"^(.+?)(\s*)(\(([0-9]*)\))?\.svg$", name)
                # Make sure the new title has " (%d)" appended by default
                name = match.group(1) + " (%d)"
                if match.group(4):
                    # Filename already contained a number -> start counting from there
                    offset = int(match.group(4))
                    # -> only include space(s) if there before
                    name = match.group(1) + match.group(2) + "(%d)"
            # Find an unused file name
            for i in range(1, 1000):
                curname = name % (offset + i)
                possible_path = os.path.join(info.TITLE_PATH, "%s.svg" % curname)
                if not os.path.exists(possible_path):
                    self.txtFileName.setText(curname)
                    break
        self.txtFileName.setFixedHeight(28)
        layout.addRow(label, self.txtFileName)

        # Get text values
        title_text = []
        for i, node in enumerate(self.tspan_nodes):
            if len(node.childNodes) < 1:
                continue
            text = node.childNodes[0].data
            title_text.append(text)

            # Create Label
            label_line_text = _("Line %s:") % str(i + 1)
            label = QLabel(label_line_text)
            label.setToolTip(label_line_text)

            # create text editor for each text element in title
            widget = QLineEdit(text)
            widget.setFixedHeight(28)
            widget.textChanged.connect(functools.partial(self.txtLine_changed, widget))
            layout.addRow(label, widget)

        # Apply font attributes to SVG: TEXT and TSPAN nodes
        self.set_font_attributes()

        # Write SVG temp file
        self.writeToFile(self.xmldoc)

        # Add Font button
        label = QLabel(_("Font:"))
        label.setToolTip(_("Font:"))
        self.btnFont = QPushButton(_("Change Font"))
        layout.addRow(label, self.btnFont)
        self.btnFont.clicked.connect(self.btnFont_clicked)

        # Add Text color button
        label = QLabel(_("Text:"))
        label.setToolTip(_("Text:"))
        self.btnFontColor = QPushButton(_("Text Color"))
        layout.addRow(label, self.btnFontColor)
        self.btnFontColor.clicked.connect(self.btnFontColor_clicked)

        # Add Background color button
        label = QLabel(_("Background:"))
        label.setToolTip(_("Background:"))
        self.btnBackgroundColor = QPushButton(_("Background Color"))
        layout.addRow(label, self.btnBackgroundColor)
        self.btnBackgroundColor.clicked.connect(self.btnBackgroundColor_clicked)

        # Add Advanced Editor button
        label = QLabel(_("Advanced:"))
        label.setToolTip(_("Advanced:"))
        self.btnAdvanced = QPushButton(_("Use Advanced Editor"))
        layout.addRow(label, self.btnAdvanced)
        self.btnAdvanced.clicked.connect(self.btnAdvanced_clicked)

        # Update color buttons
        self.update_font_color_button()
        self.update_background_color_button()

        # Enable / Disable buttons based on # of text nodes
        if len(title_text) >= 1:
            self.btnFont.setEnabled(True)
            self.btnFontColor.setEnabled(True)
            self.btnBackgroundColor.setEnabled(True)
            self.btnAdvanced.setEnabled(True)
        else:
            self.btnFont.setEnabled(False)
            self.btnFontColor.setEnabled(False)

        # Enable Save button when a template is selected
        self.buttonBox.button(self.buttonBox.Save).setEnabled(True)

    def writeToFile(self, xmldoc):
        '''writes a new svg file containing the user edited data'''

        if not self.filename.endswith("svg"):
            self.filename = self.filename + ".svg"
        try:
            file = open(os.fsencode(self.filename), "wb")  # wb needed for windows support
            file.write(bytes(xmldoc.toxml(), 'UTF-8'))
            file.close()
        except IOError as inst:
            log.error("Error writing SVG title: {}".format(inst))

    def save_and_reload(self):
        """Something changed, so update temp SVG and redisplay"""
        if not self.is_thread_busy:
            t = threading.Thread(target=self.save_and_reload_thread, daemon=True)
            t.start()
        else:
            # Keep retrying until we succeed
            self.update_timer.start()

    def save_and_reload_thread(self):
        """Run inside thread, to update and display new SVG - so we don't block the main UI thread"""
        if not self.filename:
            return

        self.is_thread_busy = True
        self.writeToFile(self.xmldoc)
        self.display_svg()
        self.is_thread_busy = False

    @pyqtSlot(QColor)
    def color_callback(self, save_fn, refresh_fn, color):
        """Update SVG color after user selection"""
        if not color or not color.isValid():
            return
        save_fn(color.name(), color.alphaF())
        refresh_fn()
        self.update_timer.start()

    @staticmethod
    def best_contrast(bg: QColor) -> QColor:
        """Choose text color for best contrast against a background"""
        colrgb = bg.getRgbF()
        # Compute perceptive luminance of background color
        lum = (0.299 * colrgb[0] + 0.587 * colrgb[1] + 0.114 * colrgb[2])
        if (lum < 0.5):
            return QColor(Qt.white)
        return QColor(Qt.black)

    def btnFontColor_clicked(self):
        app = get_app()
        _ = app._tr

        callback_func = functools.partial(
            self.color_callback,
            self.set_font_color_elements,
            self.update_font_color_button)
        # Get color from user
        log.debug("Launching color picker for %s", self.font_color_code.name())
        ColorPicker(
            self.font_color_code, parent=self,
            title=_("Select a Color"),
            callback=callback_func)

    def btnBackgroundColor_clicked(self):
        app = get_app()
        _ = app._tr

        callback_func = functools.partial(
            self.color_callback,
            self.set_bg_style,
            self.update_background_color_button)
        # Get color from user
        log.debug("Launching color picker for %s", self.bg_color_code.name())
        ColorPicker(
            self.bg_color_code, parent=self,
            title=_("Select a Color"),
            callback=callback_func)

    def btnFont_clicked(self):
        app = get_app()
        _ = app._tr

        # Default to previously-selected font
        oldfont = self.qfont

        # Get font from user
        font, ok = QFontDialog.getFont(oldfont, caption=("Change Font"))

        # Update SVG font
        if ok and font is not oldfont:
            # Set new font
            self.qfont = font

            # Determine font-size change in scale (i.e. % larger or smaller)
            fontinfo = QFontInfo(font)
            oldfontinfo = QFontInfo(oldfont)
            font_size_ratio = 1.0
            if oldfontinfo.pixelSize() > 0:
                font_size_ratio = fontinfo.pixelSize() / oldfontinfo.pixelSize()

            # Apply font attributes to SVG: TEXT and TSPAN nodes
            # Scale font-size up or down (if size changed)
            self.set_font_attributes(font_size_ratio)
            self.update_timer.start()

    def update_font_color_button(self):
        """Updates the color shown on the font color button"""

        # Loop through each TEXT element
        for node in self.text_nodes + self.tspan_nodes:

            # Get the value in the style attribute and turn into a dict
            s = node.getAttribute("style")
            ard = style_to_dict(s)
            # Get fill color or default to white
            color = ard.get("fill", "#FFF")
            # Look up color if needed
            # Some colors are located in a different node
            if color.startswith("url(#") and self.xmldoc.getElementsByTagName("defs").length == 1:
                color_ref_id = color[5:-1]
                ref_color = self.get_ref_color(color_ref_id)
                if ref_color:
                    color = ref_color
            # Get opacity or default to opaque
            opacity = float(ard.get("opacity", 1.0))

            color = QColor(color)
            text_color = self.best_contrast(color)
            # Set the color of the button, ignoring alpha
            self.btnFontColor.setStyleSheet(
                "background-color: %s; opacity: %s; color: %s;"
                % (color.name(), 1, text_color.name()))
            # Store the opacity as the color's alpha level
            color.setAlphaF(opacity)
            self.font_color_code = color
            log.debug("Set color of font-color button to %s", color.name())

    def get_ref_color(self, id):
        """Get the color value from a reference id (i.e. linearGradient3267)"""
        for ref_node in self.xmldoc.getElementsByTagName("defs")[0].childNodes:
            if ref_node.attributes and "id" in ref_node.attributes:
                ref_node_id = ref_node.attributes["id"].value
                if id == ref_node_id:
                    # Found a matching color reference
                    if "xlink:href" in ref_node.attributes:
                        # look up color reference again
                        xlink_ref_id = ref_node.attributes["xlink:href"].value[1:]
                        return self.get_ref_color(xlink_ref_id)
                    if "href" in ref_node.attributes:
                        # look up color reference again
                        xlink_ref_id = ref_node.attributes["href"].value[1:]
                        return self.get_ref_color(xlink_ref_id)
                    elif ref_node.childNodes:
                        for stop_node in ref_node.childNodes:
                            if stop_node.nodeName == "stop":
                                # get color from stop
                                ard = style_to_dict(stop_node.getAttribute("style"))
                                if "stop-color" in ard:
                                    return ard.get("stop-color")
        return ""

    def update_background_color_button(self):
        """Updates the color shown on the background color button"""

        if self.rect_node:
            # All backgrounds should be the first (index 0) rect tag in the svg
            s = self.rect_node[0].getAttribute("style")
            ard = style_to_dict(s)

            # Get fill color or default to black + full opacity
            color = ard.get("fill", "#000")
            opacity = float(ard.get("opacity", 1.0))

            color = QColor(color)
            text_color = self.best_contrast(color)

            # Set the colors of the button, ignoring opacity
            self.btnBackgroundColor.setStyleSheet(
                "background-color: %s; opacity: %s; color: %s;"
                % (color.name(), 1, text_color.name()))

            # Store the opacity as the color's alpha level
            color.setAlphaF(opacity)
            self.bg_color_code = color
            log.debug("Set color of background-color button to %s", color.name())

    def set_font_attributes(self, font_size_ratio=1.0):
        '''sets the QFont properties to all SVG: TEXT and TSPAN nodes'''
        log.debug(f"Setting font-family to {self.qfont.family()}.")

        # Loop through each TEXT element
        for text_child in self.text_nodes + self.tspan_nodes:
            # set the style elements for the main text node
            s = text_child.getAttribute("style")
            ard = style_to_dict(s)
            if self.qfont.family():
                ard["font-family"] = f"'{self.qfont.family()}'"
            if self.qfont.italic():
                ard["font-style"] = "italic"
            else:
                ard["font-style"] = "normal"
            if self.qfont.bold():
                ard["font-weight"] = "bold"
            else:
                ard["font-weight"] = "normal"
            if font_size_ratio != 1.0:
                new_font_size_pixel = 100
                if 'font-size' in ard:
                    new_font_size_pixel = font_size_ratio * float(ard['font-size'][:-2])
                set_if_existing(ard, "font-size", f"{new_font_size_pixel}px")
            self.title_style_string = dict_to_style(ard)

            # set the text node
            text_child.setAttribute("style", self.title_style_string)
        log.debug("Updated font styles to %s", self.title_style_string)

    def set_bg_style(self, color, alpha):
        '''sets the background color'''

        if self.rect_node:
            # Turn the style attribute into a dict for modification
            s = self.rect_node[0].getAttribute("style")
            ard = style_to_dict(s)
            ard.update({
                "fill": color,
                "opacity": str(alpha),
                })
            # Convert back to a string and update the node in the xml doc
            self.bg_style_string = dict_to_style(ard)
            self.rect_node[0].setAttribute("style", self.bg_style_string)
            log.debug("Updated background style to %s", self.bg_style_string)

    def set_font_color_elements(self, color, alpha):
        # Loop through each TEXT element
        for text_child in self.text_nodes + self.tspan_nodes:
            # SET TEXT PROPERTIES
            s = text_child.getAttribute("style")
            ard = style_to_dict(s)
            ard.update({
                "fill": color,
                "opacity": str(alpha),
                })
            text_child.setAttribute("style", dict_to_style(ard))
        log.debug("Set text node style, fill:%s opacity:%s", color, alpha)

    def accept(self):
        app = get_app()
        _ = app._tr

        # If editing file, just update the existing file
        if self.edit_file_path and not self.duplicate:
            # Update filename
            self.filename = self.edit_file_path

            # Overwrite title svg file
            self.writeToFile(self.xmldoc)

        else:
            # Create new title (with unique name)
            file_name = "%s.svg" % self.txtFileName.text().strip()
            file_path = os.path.join(info.TITLE_PATH, file_name)

            if self.txtFileName.text().strip():
                # Do we have unsaved changes?
                if os.path.exists(file_path) and not self.edit_file_path:
                    ret = QMessageBox.question(
                        self, _("Title Editor"),
                        _("%s already exists.\nDo you want to replace it?") % file_name,
                        QMessageBox.No | QMessageBox.Yes
                    )
                    if ret == QMessageBox.No:
                        # Do nothing
                        return

                # Update filename
                self.filename = file_path

                # Save title
                self.writeToFile(self.xmldoc)

                # Add file to project
                app.window.files_model.add_files(self.filename, prevent_image_seq=True, prevent_recent_folder=True)

        # Close window
        super().accept()

    def btnAdvanced_clicked(self):
        """Use an external editor to edit the image"""
        _ = self.app._tr
        s = get_app().get_settings()
        prog = s.get("title_editor").strip()
        filename_text = self.txtFileName.text().strip()

        # Define the title and both platform-specific messages
        error_title = _("Error launching editor")
        error_msg_linux = _(
            "The editor did not launch: <b>{cmd}</b><br><br>"
            "If you used Snap or Flatpak, try installing the editor with your package manager."
        ).format(cmd=prog)
        error_msg_other = _(
            "The editor did not launch: <b>{cmd}</b><br><br>"
            "Please check that the editor is installed and working."
        ).format(cmd=prog)

        # Pick the message for this platform
        error_msg = error_msg_linux if sys.platform.startswith("linux") else error_msg_other

        try:
            log.info("Advanced title editor command: %s", str([prog, self.filename]))
            start_time = time.time()
            p = subprocess.Popen(
                [prog, self.filename],
                env=self.env,
                cwd=info.HOME_PATH,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
            p.communicate()
            elapsed = time.time() - start_time

            # Show error if the editor exited too quickly
            if elapsed < 4:
                QMessageBox.warning(self, error_title, error_msg)
            else:
                self.load_svg_template(filename_field=filename_text)
                self.display_svg()

        except Exception as ex:
            log.error("Failed to launch advanced title editor: %s", ex)
            QMessageBox.warning(self, error_title, error_msg)
