""" 
 @file
 @brief This file loads the title editor dialog (i.e SVG creator)
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Andy Finch <andy@openshot.org>
 
 @section LICENSE
 
 Copyright (c) 2008-2016 OpenShot Studios, LLC
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

import sys
import os
import shutil
import functools
import subprocess
from xml.dom import minidom

from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem, QFont
from PyQt5.QtWidgets import *
from PyQt5 import uic, QtSvg, QtGui
from PyQt5.QtWebKitWidgets import QWebView
import openshot

from classes import info, ui_util, settings, qt_types, updates
from classes.logger import log
from classes.app import get_app
from classes.query import File
from classes.metrics import *
from windows.views.titles_listview import TitlesListView

try:
    import json
except ImportError:
    import simplejson as json


class TitleEditor(QDialog):
    """ Title Editor Dialog """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'title-editor.ui')

    def __init__(self, edit_file_path=None, duplicate=False):

        # Create dialog class
        QDialog.__init__(self)

        self.app = get_app()
        self.project = self.app.project
        self.edit_file_path = edit_file_path
        self.duplicate = duplicate

        # Get translation object
        _ = self.app._tr

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init UI
        ui_util.init_ui(self)

        # Track metrics
        track_metric_screen("title-screen")

        # Initialize variables
        self.template_name = ""
        imp = minidom.getDOMImplementation()
        self.xmldoc = imp.createDocument(None, "any", None)

        self.bg_color_code = ""
        self.font_color_code = "#ffffff"

        self.bg_style_string = ""
        self.title_style_string = ""
        self.subtitle_style_string = ""

        self.font_weight = 'normal'
        self.font_style = 'normal'

        self.new_title_text = ""
        self.sub_title_text = ""
        self.subTitle = False

        self.display_name = ""
        self.font_family = "Bitstream Vera Sans"
        self.tspan_node = None

        # Add titles list view
        self.titlesTreeView = TitlesListView(self)
        self.verticalLayout.addWidget(self.titlesTreeView)

        # If editing existing title svg file
        if self.edit_file_path:
            # Hide list of templates
            self.widget.setVisible(False)

            # Display title in graphicsView
            self.filename = self.edit_file_path

            if self.duplicate:
                # Create temp version of title
                self.create_temp_title(self.edit_file_path)

            # Add all widgets for editing
            self.load_svg_template()

            # Display image (slight delay to allow screen to be shown first)
            QTimer.singleShot(50, self.display_svg)

    def txtLine_changed(self, txtWidget):

        # Loop through child widgets (and remove them)
        text_list = []
        for child in self.settingsContainer.children():
            if type(child) == QTextEdit and child.objectName() != "txtFileName":
                text_list.append(child.toPlainText())

        # Update text values in the SVG
        for i in range(0, self.text_fields):
            if len(self.tspan_node[i].childNodes) > 0 and i <= (len(text_list) - 1):
                new_text_node = self.xmldoc.createTextNode(text_list[i])
                old_text_node = self.tspan_node[i].childNodes[0]
                self.tspan_node[i].removeChild(old_text_node)
                # add new text node
                self.tspan_node[i].appendChild(new_text_node)

        # Something changed, so update temp SVG
        self.writeToFile(self.xmldoc)

        # Display SVG again
        self.display_svg()

    def display_svg(self):
        scene = QGraphicsScene(self)
        view = self.graphicsView
        svg = QtGui.QPixmap(self.filename)
        svg_scaled = svg.scaled(self.graphicsView.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        scene.addPixmap(svg_scaled)
        view.setScene(scene)
        view.show()

    def create_temp_title(self, template_path):

        # Set temp file path
        self.filename = os.path.join(info.TITLE_PATH, "temp.svg")

        # Copy template to temp file
        shutil.copy(template_path, self.filename)

        # return temp path
        return self.filename

    def load_svg_template(self):
        """ Load an SVG title and init all textboxes and controls """

        # Get translation object
        _ = get_app()._tr

        # parse the svg object
        self.xmldoc = minidom.parse(self.filename)
        # get the text elements
        self.tspan_node = self.xmldoc.getElementsByTagName('tspan')
        self.text_fields = len(self.tspan_node)

        # Loop through child widgets (and remove them)
        for child in self.settingsContainer.children():
            try:
                self.settingsContainer.layout().removeWidget(child)
                child.deleteLater()
            except:
                pass

        # Get text nodes and rect nodes
        self.text_node = self.xmldoc.getElementsByTagName('text')
        self.rect_node = self.xmldoc.getElementsByTagName('rect')

        # Create Label
        label = QLabel()
        label_line_text = _("File Name:")
        label.setText(label_line_text)
        label.setToolTip(label_line_text)

        # create text editor for file name
        self.txtFileName = QTextEdit()
        self.txtFileName.setObjectName("txtFileName")

        # If edit mode, set file name
        if self.edit_file_path and not self.duplicate:
            # Use existing name (and prevent editing name)
            self.txtFileName.setText(os.path.split(self.edit_file_path)[1])
            self.txtFileName.setEnabled(False)
        else:
            # Find an unused file name
            for i in range(1, 1000):
                possible_path = os.path.join(info.ASSETS_PATH, "TitleFileName-%d.svg" % i)
                if not os.path.exists(possible_path):
                    self.txtFileName.setText(_("TitleFileName-%d") % i)
                    break
        self.txtFileName.setFixedHeight(28)
        self.settingsContainer.layout().addRow(label, self.txtFileName)

        # Get text values
        title_text = []
        for i in range(0, self.text_fields):
            if len(self.tspan_node[i].childNodes) > 0:
                text = self.tspan_node[i].childNodes[0].data
                title_text.append(text)

                # Create Label
                label = QLabel()
                label_line_text = _("Line %s:") % str(i + 1)
                label.setText(label_line_text)
                label.setToolTip(label_line_text)

                # create text editor for each text element in title
                widget = QTextEdit()
                widget.setText(_(text))
                widget.setFixedHeight(28)
                widget.textChanged.connect(functools.partial(self.txtLine_changed, widget))
                self.settingsContainer.layout().addRow(label, widget)


        # Add Font button
        label = QLabel()
        label.setText(_("Font:"))
        label.setToolTip(_("Font:"))
        self.btnFont = QPushButton()
        self.btnFont.setText(_("Change Font"))
        self.settingsContainer.layout().addRow(label, self.btnFont)
        self.btnFont.clicked.connect(self.btnFont_clicked)

        # Add Text color button
        label = QLabel()
        label.setText(_("Text:"))
        label.setToolTip(_("Text:"))
        self.btnFontColor = QPushButton()
        self.btnFontColor.setText(_("Text Color"))
        self.settingsContainer.layout().addRow(label, self.btnFontColor)
        self.btnFontColor.clicked.connect(self.btnFontColor_clicked)

        # Add Background color button
        label = QLabel()
        label.setText(_("Background:"))
        label.setToolTip(_("Background:"))
        self.btnBackgroundColor = QPushButton()
        self.btnBackgroundColor.setText(_("Background Color"))
        self.settingsContainer.layout().addRow(label, self.btnBackgroundColor)
        self.btnBackgroundColor.clicked.connect(self.btnBackgroundColor_clicked)

        # Add Advanced Editor button
        label = QLabel()
        label.setText(_("Advanced:"))
        label.setToolTip(_("Advanced:"))
        self.btnAdvanced = QPushButton()
        self.btnAdvanced.setText(_("Use Advanced Editor"))
        self.settingsContainer.layout().addRow(label, self.btnAdvanced)
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

    def writeToFile(self, xmldoc):
        '''writes a new svg file containing the user edited data'''

        if not self.filename.endswith("svg"):
            self.filename = self.filename + ".svg"
        try:
            file = open(self.filename.encode('UTF-8'), "wb")  # wb needed for windows support
            file.write(bytes(xmldoc.toxml(), 'UTF-8'))
            file.close()
        except IOError as inst:
            log.error("Error writing SVG title")

    def btnFontColor_clicked(self):
        app = get_app()
        _ = app._tr

        # Get color from user
        col = QColorDialog.getColor(Qt.white, self, _("Select a Color"),
                                    QColorDialog.DontUseNativeDialog | QColorDialog.ShowAlphaChannel)

        # Update SVG colors
        if col.isValid():
            self.btnFontColor.setStyleSheet("background-color: %s" % col.name())
            self.set_font_color_elements(col.name(), col.alphaF())

        # Something changed, so update temp SVG
        self.writeToFile(self.xmldoc)

        # Display SVG again
        self.display_svg()

    def btnBackgroundColor_clicked(self):
        app = get_app()
        _ = app._tr

        # Get color from user
        col = QColorDialog.getColor(Qt.white, self, _("Select a Color"),
                                    QColorDialog.DontUseNativeDialog | QColorDialog.ShowAlphaChannel)

        # Update SVG colors
        if col.isValid():
            self.btnBackgroundColor.setStyleSheet("background-color: %s" % col.name())
            self.set_bg_style(col.name(), col.alphaF())

        # Something changed, so update temp SVG
        self.writeToFile(self.xmldoc)

        # Display SVG again
        self.display_svg()

    def btnFont_clicked(self):
        app = get_app()
        _ = app._tr

        # Get font from user
        font, ok = QFontDialog.getFont(QFont(), caption=_("Change Font"))

        # Update SVG font
        if ok:
            fontinfo = QtGui.QFontInfo(font)
            self.font_family = fontinfo.family()
            self.font_style = fontinfo.styleName()
            self.font_weight = fontinfo.weight()
            self.set_font_style()

        # Something changed, so update temp SVG
        self.writeToFile(self.xmldoc)

        # Display SVG again
        self.display_svg()

    def find_in_list(self, l, value):
        '''when passed a partial value, function will return the list index'''
        for item in l:
            if item.startswith(value):
                return l.index(item)

    def update_font_color_button(self):
        """Updates the color shown on the font color button"""

        # Loop through each TEXT element
        for node in self.text_node:

            # Get the value in the style attribute
            s = node.attributes["style"].value

            # split the node so we can access each part
            ar = s.split(";")
            color = self.find_in_list(ar, "fill:")

            try:
                # Parse the result
                txt = ar[color]
                color = txt[5:]
            except:
                # If the color was in an invalid format, try the next text element
                continue

            opacity = self.find_in_list(ar, "opacity:")

            try:
                # Parse the result
                txt = ar[opacity]
                opacity = float(txt[8:])
            except:
                pass

            # Default the font color to white if non-existing
            if color == None:
                color = "#FFFFFF"

            # Default the opacity to fully visible if non-existing
            if opacity == None:
                opacity = 1.0

            color = QtGui.QColor(color)
            # Convert the opacity into the alpha value
            alpha = int(opacity * 65535.0)
            self.btnFontColor.setStyleSheet("background-color: %s; opacity %s" % (color.name(), alpha))

    def update_background_color_button(self):
        """Updates the color shown on the background color button"""

        if self.rect_node:

            # All backgrounds should be the first (index 0) rect tag in the svg
            s = self.rect_node[0].attributes["style"].value

            # split the node so we can access each part
            ar = s.split(";")

            color = self.find_in_list(ar, "fill:")

            try:
                # Parse the result
                txt = ar[color]
                color = txt[5:]
            except ValueError:
                pass

            opacity = self.find_in_list(ar, "opacity:")

            try:
                # Parse the result
                txt = ar[opacity]
                opacity = float(txt[8:])
            except ValueError:
                pass
            except TypeError:
                pass

            # Default the background color to black if non-existing
            if color == None:
                color = "#000000"

            # Default opacity to fully visible if non-existing
            if opacity == None:
                opacity = 1.0

            color = QtGui.QColor(color)
            # Convert the opacity into the alpha value
            alpha = int(opacity * 65535.0)
            # Set the alpha value of the button
            self.btnBackgroundColor.setStyleSheet("background-color: %s; opacity %s" % (color.name(), alpha))

    def set_font_style(self):
        '''sets the font properties'''

        # Loop through each TEXT element
        for text_child in self.text_node:
            # set the style elements for the main text node
            s = text_child.attributes["style"].value
            # split the text node so we can access each part
            ar = s.split(";")
            # we need to find each element that we are changing, shouldn't assume
            # they are in the same position in any given template.

            # ignoring font-weight, as not sure what it represents in Qt.
            fs = self.find_in_list(ar, "font-style:")
            ff = self.find_in_list(ar, "font-family:")
            ar[fs] = "font-style:" + self.font_style
            ar[ff] = "font-family:" + self.font_family
            # rejoin the modified parts
            t = ";"
            self.title_style_string = t.join(ar)

            # set the text node
            text_child.setAttribute("style", self.title_style_string)

        # Loop through each TSPAN
        for tspan_child in self.tspan_node:
            # set the style elements for the main text node
            s = tspan_child.attributes["style"].value
            # split the text node so we can access each part
            ar = s.split(";")
            # we need to find each element that we are changing, shouldn't assume
            # they are in the same position in any given template.

            # ignoring font-weight, as not sure what it represents in Qt.
            fs = self.find_in_list(ar, "font-style:")
            ff = self.find_in_list(ar, "font-family:")
            ar[fs] = "font-style:" + self.font_style
            ar[ff] = "font-family:" + self.font_family
            # rejoin the modified parts
            t = ";"
            self.title_style_string = t.join(ar)

            # set the text node
            tspan_child.setAttribute("style", self.title_style_string)

    def set_bg_style(self, color, alpha):
        '''sets the background color'''

        if self.rect_node:
            # split the node so we can access each part
            s = self.rect_node[0].attributes["style"].value
            ar = s.split(";")
            fill = self.find_in_list(ar, "fill:")
            if fill == None:
                ar.append("fill:" + color)
            else:
                ar[fill] = "fill:" + color

            opacity = self.find_in_list(ar, "opacity:")
            if opacity == None:
                ar.append("opacity:" + str(alpha))
            else:
                ar[opacity] = "opacity:" + str(alpha)

            # rejoin the modifed parts
            t = ";"
            self.bg_style_string = t.join(ar)
            # set the node in the xml doc
            self.rect_node[0].setAttribute("style", self.bg_style_string)

    def set_font_color_elements(self, color, alpha):

        # Loop through each TEXT element
        for text_child in self.text_node:

            # SET TEXT PROPERTIES
            s = text_child.attributes["style"].value
            # split the text node so we can access each part
            ar = s.split(";")
            fill = self.find_in_list(ar, "fill:")
            if fill == None:
                ar.append("fill:" + color)
            else:
                ar[fill] = "fill:" + color

            opacity = self.find_in_list(ar, "opacity:")
            if opacity == None:
                ar.append("opacity:" + str(alpha))
            else:
                ar[opacity] = "opacity:" + str(alpha)

            t = ";"
            text_child.setAttribute("style", t.join(ar))


            # Loop through each TSPAN
            for tspan_child in self.tspan_node:

                # SET TSPAN PROPERTIES
                s = tspan_child.attributes["style"].value
                # split the text node so we can access each part
                ar = s.split(";")
                fill = self.find_in_list(ar, "fill:")
                if fill == None:
                    ar.append("fill:" + color)
                else:
                    ar[fill] = "fill:" + color
                t = ";"
                tspan_child.setAttribute("style", t.join(ar))

    def accept(self):
        app = get_app()
        _ = app._tr

        # If editing file, just update the existing file
        if self.edit_file_path and not self.duplicate:
            # Overwrite title svg file
            self.writeToFile(self.xmldoc)

        else:
            # Create new title (with unique name)
            file_name = "%s.svg" % self.txtFileName.toPlainText().strip()
            file_path = os.path.join(info.ASSETS_PATH, file_name)

            if self.txtFileName.toPlainText().strip():
                # Do we have unsaved changes?
                if os.path.exists(file_path) and not self.edit_file_path:
                    ret = QMessageBox.question(self, _("Title Editor"), _("%s already exists.\nDo you want to replace it?") % file_name,
                                               QMessageBox.No | QMessageBox.Yes)
                    if ret == QMessageBox.No:
                        # Do nothing
                        return

                # Update filename
                self.filename = file_path

                # Save title
                self.writeToFile(self.xmldoc)

                # Add file to project
                self.add_file(self.filename)

        # Close window
        super(TitleEditor, self).accept()

    def add_file(self, filepath):
        path, filename = os.path.split(filepath)

        # Add file into project
        app = get_app()
        _ = get_app()._tr

        # Check for this path in our existing project data
        file = File.get(path=filepath)

        # If this file is already found, exit
        if file:
            return

        # Load filepath in libopenshot clip object (which will try multiple readers to open it)
        clip = openshot.Clip(filepath)

        # Get the JSON for the clip's internal reader
        try:
            reader = clip.Reader()
            file_data = json.loads(reader.Json())

            # Set media type
            file_data["media_type"] = "image"

            # Save new file to the project data
            file = File()
            file.data = file_data
            file.save()
            return True

        except:
            # Handle exception
            msg = QMessageBox()
            msg.setText(_("{} is not a valid video, audio, or image file.".format(filename)))
            msg.exec_()
            return False

    def btnAdvanced_clicked(self):
        _ = self.app._tr
        # use an external editor to edit the image
        try:
            # Get settings
            s = settings.get_settings()

            # get the title editor executable path
            prog = s.get("title_editor")

            # launch advanced title editor
            # debug info
            log.info("Advanced title editor command: {} {} ".format(prog, self.filename))

            p = subprocess.Popen([prog, self.filename])

            # wait for process to finish (so we can update the preview)
            p.communicate()

            # update image preview
            self.load_svg_template()
            self.display_svg()

        except OSError:
            msg = QMessageBox()
            msg.setText(_("Please install {} to use this function").format(prog.capitalize()))
            msg.exec_()
