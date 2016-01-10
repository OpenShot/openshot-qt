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
import fnmatch
import shutil
import functools
import subprocess
from xml.dom import minidom

from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import *
from PyQt5 import uic, QtSvg, QtGui
from PyQt5.QtWebKitWidgets import QWebView
import openshot

from classes import info, ui_util, settings, qt_types, updates
from classes.logger import log
from classes.app import get_app
from classes.query import File

try:
    import json
except ImportError:
    import simplejson as json


class TitleEditor(QDialog):
    """ Title Editor Dialog """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'title-editor.ui')

    def __init__(self):

        # Create dialog class
        QDialog.__init__(self)

        self.app = get_app()
        self.project = self.app.project

        # Get translation object
        _ = self.app._tr

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init UI
        ui_util.init_ui(self)

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

        # Hide all textboxes
        self.hide_textboxes()

        # Remove temp file (if found)
        temp_svg_path = os.path.join(info.TITLE_PATH, "temp.svg")
        if os.path.exists(temp_svg_path):
            os.remove(temp_svg_path)

        # load the template files
        self.cmbTemplate.addItem("<Select a template>")

        # Add user-defined titles (if any)
        for file in sorted(os.listdir(info.TITLE_PATH)):
            # pretty up the filename for display purposes
            if fnmatch.fnmatch(file, '*.svg'):
                (fileName, fileExtension) = os.path.splitext(file)
            self.cmbTemplate.addItem(fileName.replace("_", " "), os.path.join(info.TITLE_PATH, file))

        # Add built-in titles
        self.template_dir = os.path.join(info.PATH, 'titles')
        for file in sorted(os.listdir(self.template_dir)):
            # pretty up the filename for display purposes
            if fnmatch.fnmatch(file, '*.svg'):
                (fileName, fileExtension) = os.path.splitext(file)
            self.cmbTemplate.addItem(fileName.replace("_", " "), os.path.join(self.template_dir, file))

        # set event handlers
        self.cmbTemplate.activated.connect(functools.partial(self.cmbTemplate_activated))
        self.btnFontColor.clicked.connect(functools.partial(self.btnFontColor_clicked))
        self.btnBackgroundColor.clicked.connect(functools.partial(self.btnBackgroundColor_clicked))
        self.btnFont.clicked.connect(functools.partial(self.btnFont_clicked))
        self.btnAdvanced.clicked.connect(functools.partial(self.btnAdvanced_clicked))
        self.txtLine1.textChanged.connect(functools.partial(self.txtLine_changed))
        self.txtLine2.textChanged.connect(functools.partial(self.txtLine_changed))
        self.txtLine3.textChanged.connect(functools.partial(self.txtLine_changed))
        self.txtLine4.textChanged.connect(functools.partial(self.txtLine_changed))
        self.txtLine5.textChanged.connect(functools.partial(self.txtLine_changed))
        self.txtLine6.textChanged.connect(functools.partial(self.txtLine_changed))

    def txtLine_changed(self):

        # Update text values in the SVG
        text_list = []
        text_list.append(self.txtLine1.toPlainText())
        text_list.append(self.txtLine2.toPlainText())
        text_list.append(self.txtLine3.toPlainText())
        text_list.append(self.txtLine4.toPlainText())
        text_list.append(self.txtLine5.toPlainText())
        text_list.append(self.txtLine6.toPlainText())
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

    def hide_textboxes(self):
        """ Hide all text inputs """
        self.txtLine1.setVisible(False)
        self.lblLine1.setVisible(False)
        self.txtLine2.setVisible(False)
        self.lblLine2.setVisible(False)
        self.txtLine3.setVisible(False)
        self.lblLine3.setVisible(False)
        self.txtLine4.setVisible(False)
        self.lblLine4.setVisible(False)
        self.txtLine5.setVisible(False)
        self.lblLine5.setVisible(False)
        self.txtLine6.setVisible(False)
        self.lblLine6.setVisible(False)

    def show_textboxes(self, num_fields):
        """ Only show a certain number of text inputs """

        if num_fields >= 1:
            self.txtLine1.setEnabled(True)
            self.txtLine1.setVisible(True)
            self.lblLine1.setVisible(True)
        if num_fields >= 2:
            self.txtLine2.setEnabled(True)
            self.txtLine2.setVisible(True)
            self.lblLine2.setVisible(True)
        if num_fields >= 3:
            self.txtLine3.setEnabled(True)
            self.txtLine3.setVisible(True)
            self.lblLine3.setVisible(True)
        if num_fields >= 4:
            self.txtLine4.setEnabled(True)
            self.txtLine4.setVisible(True)
            self.lblLine4.setVisible(True)
        if num_fields >= 5:
            self.txtLine5.setEnabled(True)
            self.txtLine5.setVisible(True)
            self.lblLine5.setVisible(True)
        if num_fields >= 6:
            self.txtLine6.setEnabled(True)
            self.txtLine6.setVisible(True)
            self.lblLine6.setVisible(True)

    def display_svg(self):
        scene = QGraphicsScene(self)
        view = self.graphicsView
        svg = QtGui.QPixmap(self.filename)
        svg_scaled = svg.scaled(svg.width() / 4, svg.height() / 4, Qt.KeepAspectRatio)
        scene.addPixmap(svg_scaled)
        view.setScene(scene)
        view.show()

    def cmbTemplate_activated(self):
        # reconstruct the filename from the modified display name
        if self.cmbTemplate.currentIndex() > 0:
            # ignore the 'select a template entry'
            template = self.cmbTemplate.currentText()
            template_path = self.cmbTemplate.itemData(self.cmbTemplate.currentIndex())

            # Create temp version of SVG title
            self.filename = self.create_temp_title(template_path)

            # Load temp title
            self.load_svg_template()

            # Display tmp title
            self.display_svg()

    def create_temp_title(self, template_path):

        # Set temp file path
        self.filename = os.path.join(info.TITLE_PATH, "temp.svg")

        # Copy template to temp file
        shutil.copy(template_path, self.filename)

        # return temp path
        return self.filename

    def load_svg_template(self):
        """ Load an SVG title and init all textboxes and controls """

        # parse the svg object
        self.xmldoc = minidom.parse(self.filename)
        # get the text elements
        self.tspan_node = self.xmldoc.getElementsByTagName('tspan')
        self.text_fields = len(self.tspan_node)

        # Hide all text inputs
        self.hide_textboxes()
        # Show the correct number of text inputs
        self.show_textboxes(self.text_fields)

        # Get text nodes and rect nodes
        self.text_node = self.xmldoc.getElementsByTagName('text')
        self.rect_node = self.xmldoc.getElementsByTagName('rect')

        # Get text values
        title_text = []
        for i in range(0, self.text_fields):
            if len(self.tspan_node[i].childNodes) > 0:
                title_text.append(self.tspan_node[i].childNodes[0].data)

        # Set textbox values
        num_fields = len(title_text)
        if num_fields >= 1:
            self.txtLine1.setText("")
            self.txtLine1.setText(title_text[0])
        if num_fields >= 2:
            self.txtLine2.setText("")
            self.txtLine2.setText(title_text[1])
        if num_fields >= 3:
            self.txtLine3.setText("")
            self.txtLine3.setText(title_text[2])
        if num_fields >= 4:
            self.txtLine4.setText("")
            self.txtLine4.setText(title_text[3])
        if num_fields >= 5:
            self.txtLine5.setText("")
            self.txtLine5.setText(title_text[4])
        if num_fields >= 6:
            self.txtLine6.setText("")
            self.txtLine6.setText(title_text[5])

        # Update color buttons
        self.update_font_color_button()
        self.update_background_color_button()

        # Enable / Disable buttons based on # of text nodes
        if num_fields >= 1:
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
        # Get font from user
        font, ok = QFontDialog.getFont()

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

        # Get current project folder (if any)
        project_path = get_app().project.current_filepath
        default_folder = info.HOME_PATH
        if project_path:
            default_folder = os.path.dirname(project_path)

        # Init file path for new title
        title_path = os.path.join(default_folder, "%s.svg" % _("New Title"))

        # Get file path for SVG title
        file_path, file_type = QFileDialog.getSaveFileName(self, _("Save Title As..."), title_path, _("Scalable Vector Graphics (*.svg)"))

        if file_path:
            # Append .svg (if not already there)
            if not file_path.endswith("svg"):
                file_path = file_path + ".svg"

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
            msg.setText(app._tr("{} is not a valid video, audio, or image file.".format(filename)))
            msg.exec_()
            return False

    def btnAdvanced_clicked(self):
        _ = self.app._tr
        # use an external editor to edit the image
        try:
            prog = "inkscape"
            # check if inkscape is installed
            if subprocess.call('which ' + prog + ' 2>/dev/null', shell=True) == 0:
                # launch Inkscape
                # debug info
                log.info("Inkscape command: {} {} ".format(prog, self.filename))

                p = subprocess.Popen([prog, self.filename])

                # wait for process to finish (so we can update the preview)
                p.communicate()

                # update image preview
                self.load_svg_template()
                self.display_svg()
            else:
                msg = QMessageBox()
                msg.setText(_("There was an error trying to open {}.").format(prog.capitalize()))
                msg.exec_()

        except OSError:
            msg = QMessageBox()
            msg.setText(_("Please install {} to use this function").format(prog.capitalize()))
            msg.exec_()
