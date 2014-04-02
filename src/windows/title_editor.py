""" 
 @file
 @brief This file loads the title editor dialog (i.e SVG creator)
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Andy Finch <andy@openshot.org>
 
 @section LICENSE
 
 Copyright (c) 2008-2014 OpenShot Studios, LLC
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

import sys, os, fnmatch
from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import *
from PyQt5 import uic, QtSvg, QtGui
from PyQt5.QtWebKitWidgets import QWebView
from classes import info, ui_util, settings, qt_types, updates
from classes.logger import log
from classes.app import get_app
import functools, subprocess
from xml.dom import minidom
import openshot


class TitleEditor(QDialog):
	""" Title Editor Dialog """

	# Path to ui file
	ui_path = os.path.join(info.PATH, 'windows', 'ui', 'title-editor.ui')

	def __init__(self):

		#Create dialog class
		QDialog.__init__(self)

		self.app = get_app()

		# Get translation object
		_ = self.app._tr

		#Load UI from designer
		ui_util.load_ui(self, self.ui_path)

		#Init UI
		ui_util.init_ui(self)

		self.project = self.app.project

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

		#initially hide the text input fields,
		#they are set to show later, depending on what template is selected
		self.txtLine2.setVisible(False)
		self.lblLine2.setVisible(False)
		self.txtLine3.setVisible(False)
		self.lblLine3.setVisible(False)
		self.txtLine4.setVisible(False)
		self.lblLine4.setVisible(False)

		#load the template files
		self.cmbTemplate.addItem("<Select a template>")
		self.template_dir = os.path.join(info.PATH, 'titles')
		for file in sorted(os.listdir(self.template_dir)):
			#pretty up the filename for display purposes
			if fnmatch.fnmatch(file, '*.svg'):
				(fileName, fileExtension) = os.path.splitext(file)
			self.cmbTemplate.addItem(fileName.replace("_", " "))


		#set event handlers
		self.txtName.textChanged.connect(functools.partial(self.txtName_changed))
		self.btnCreateNew.clicked.connect(functools.partial(self.btnCreateNew_clicked))
		self.cmbTemplate.activated.connect(functools.partial(self.cmbTemplate_activated))
		self.btnFontColor.clicked.connect(functools.partial(self.btnFontColor_clicked))
		self.btnBackgroundColor.clicked.connect(functools.partial(self.btnBackgroundColor_clicked))
		self.btnFont.clicked.connect(functools.partial(self.btnFont_clicked))
		self.btnApplyText.clicked.connect(functools.partial(self.btnApplyText_clicked))
		self.btnAdvanced.clicked.connect(functools.partial(self.btnAdvanced_clicked))


	def display_svg(self, filename):
		scene = QGraphicsScene(self)
		view = self.graphicsView
		svg = QtGui.QPixmap(filename)
		svg_scaled = svg.scaled(svg.width() / 4, svg.height() / 4, Qt.KeepAspectRatio)
		scene.addPixmap(svg_scaled)
		view.setScene(scene)
		view.show()

	def cmbTemplate_activated(self):
		#reconstruct the filename from the modified display name
		if self.cmbTemplate.currentIndex() > 0:
			#ignore the 'select a template entry
			template = self.cmbTemplate.currentText()
			self.template_name = template.replace(" ", "_") + ".svg"
			self.display_svg(os.path.join(info.PATH, 'titles', self.template_name))
			self.txtLine2.setVisible(False)
			self.lblLine2.setVisible(False)
			self.txtLine3.setVisible(False)
			self.lblLine3.setVisible(False)
			self.txtLine4.setVisible(False)
			self.lblLine4.setVisible(False)


	def txtName_changed(self):
		if self.btnCreateNew.isEnabled() == False:
			self.btnCreateNew.setEnabled(True)


	def btnCreateNew_clicked(self):
		#project = self.app.project
		#project_params = {}

		#project_params["current_filepath"] = project.get(["current_filepath"])
		base_path = info.THUMBNAIL_PATH
		self.filename = os.path.join(base_path, self.txtName.text() + ".svg")

		self.load_svg_template(self.template_name)

		self.update_font_color_button()
		self.update_background_color_button()

		#write the new file
		self.writeToFile(self.xmldoc)
		self.txtLine1.setEnabled(True)
		self.txtLine2.setEnabled(True)
		self.btnFont.setEnabled(True)
		self.btnFontColor.setEnabled(True)
		self.btnBackgroundColor.setEnabled(True)
		self.btnAdvanced.setEnabled(True)

		if self.noTitles == True:
			self.btnFont.setEnabled(False)
			self.btnFontColor.setEnabled(False)


	def load_svg_template(self, filename):
		self.svgname = os.path.join(self.template_dir, filename)
		#parse the svg object
		self.xmldoc = minidom.parse(self.svgname)
		#get the text elements
		self.tspan_node = self.xmldoc.getElementsByTagName('tspan')
		self.text_fields = len(self.tspan_node)

		if self.text_fields == 0:
			self.txtLine1.setVisible(False)
			self.lblLine1.setVisible(False)
			self.txtLine2.setVisible(False)
			self.lblLine2.setVisible(False)
			self.noTitles = True
		else:
			self.noTitles = False

		self.text_node = self.xmldoc.getElementsByTagName('text')
		#get the rect element
		self.rect_node = self.xmldoc.getElementsByTagName('rect')

		#populate the text boxes
		title_text = []
		for i in range(0, self.text_fields):
			if len(self.tspan_node[i].childNodes) > 0:
				title_text.append(self.tspan_node[i].childNodes[0].data)

		num_fields = len(title_text)
		#we'll assume there will always be 1 field
		self.txtLine1.setText(title_text[0])
		if num_fields == 2 or num_fields == 3 or num_fields == 4:
			self.txtLine2.setText(title_text[1])
			self.txtLine2.setVisible(True)
			self.lblLine2.setVisible(True)
		if num_fields == 3 or num_fields == 4:
			self.txtLine3.setText(title_text[2])
			self.txtLine3.setEnabled(True)
			self.txtLine3.setVisible(True)
			self.lblLine3.setVisible(True)
		if num_fields == 4:
			self.txtLine4.setEnabled(True)
			self.txtLine4.setText(title_text[3])
			self.txtLine4.setVisible(True)
			self.lblLine4.setVisible(True)



	def writeToFile(self, xmldoc):
		'''writes a new svg file containing the user edited data'''

		if not self.filename.endswith("svg"):
			self.filename = self.filename + ".svg"
		try:
			#TODO: check if file exists
			file = open(self.filename, "wb")  #wb needed for windows support
			file.write(bytes(xmldoc.toxml(), 'UTF-8'))
			file.close()
		except IOError as inst:
			#messagebox.show(_("OpenShot Error"), _("Unexpected Error '%s' while writing to '%s'." % (inst, self.filename)))
			pass


	def btnFontColor_clicked(self):
		col = QColorDialog.getColor(Qt.white,
            self,
            "Select Colour...",
            QColorDialog.DontUseNativeDialog|QColorDialog.ShowAlphaChannel)

		if col.isValid():
			self.btnFontColor.setStyleSheet("background-color: %s" % col.name())
			self.set_font_color_elements(col.name(), col.alphaF())


	def btnBackgroundColor_clicked(self):
		col = QColorDialog.getColor(Qt.white,
            self,
            "Select Colour...",
            QColorDialog.DontUseNativeDialog|QColorDialog.ShowAlphaChannel)

		if col.isValid():
			self.btnBackgroundColor.setStyleSheet("background-color: %s" % col.name())
			self.set_bg_style(col.name(), col.alphaF())


	def btnFont_clicked(self):
		font, ok = QFontDialog.getFont()
		if ok:
			fontinfo = QtGui.QFontInfo(font)
			self.font_family = fontinfo.family()
			self.font_style = fontinfo.styleName()
			self.font_weight = fontinfo.weight()
			self.set_font_style()


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

			#set the style elements for the main text node
			s = text_child.attributes["style"].value
			#split the text node so we can access each part
			ar = s.split(";")
			#we need to find each element that we are changing, shouldn't assume
			#they are in the same position in any given template.

			#ignoring font-weight, as not sure what it represents in Qt.
			fs = self.find_in_list(ar, "font-style:")
			ff = self.find_in_list(ar, "font-family:")
			ar[fs] = "font-style:" + self.font_style
			ar[ff] = "font-family:" + self.font_family
			#rejoin the modified parts
			t = ";"
			self.title_style_string = t.join(ar)

			#set the text node
			text_child.setAttribute("style", self.title_style_string)

			# Loop through each TSPAN
		for tspan_child in self.tspan_node:

			#set the style elements for the main text node
			s = tspan_child.attributes["style"].value
			#split the text node so we can access each part
			ar = s.split(";")
			#we need to find each element that we are changing, shouldn't assume
			#they are in the same position in any given template.

			#ignoring font-weight, as not sure what it represents in Qt.
			fs = self.find_in_list(ar, "font-style:")
			ff = self.find_in_list(ar, "font-family:")
			ar[fs] = "font-style:" + self.font_style
			ar[ff] = "font-family:" + self.font_family
			#rejoin the modified parts
			t = ";"
			self.title_style_string = t.join(ar)

			#set the text node
			tspan_child.setAttribute("style", self.title_style_string)


		#write the file and preview the image
		self.writeToFile(self.xmldoc)
		self.display_svg(self.filename)

	def set_bg_style(self, color, alpha):
		'''sets the background color'''

		if self.rect_node:
			#split the node so we can access each part
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

			#rejoin the modifed parts
			t = ";"
			self.bg_style_string = t.join(ar)
			#set the node in the xml doc
			self.rect_node[0].setAttribute("style", self.bg_style_string)

			self.writeToFile(self.xmldoc)
			self.display_svg(self.filename)

	def set_font_color_elements(self, color, alpha):

		# Loop through each TEXT element
		for text_child in self.text_node:

			# SET TEXT PROPERTIES
			s = text_child.attributes["style"].value
			#split the text node so we can access each part
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
				#split the text node so we can access each part
				ar = s.split(";")
				fill = self.find_in_list(ar, "fill:")
				if fill == None:
					ar.append("fill:" + color)
				else:
					ar[fill] = "fill:" + color
				t = ";"
				tspan_child.setAttribute("style", t.join(ar))


		#write the file and preview the image
		self.writeToFile(self.xmldoc)
		self.display_svg(self.filename)

	def btnApplyText_clicked(self):
				#
		# replace textnode (if any)
		text_list = []
		text_list.append(self.txtLine1.text())
		text_list.append(self.txtLine2.text())
		text_list.append(self.txtLine3.text())
		text_list.append(self.txtLine4.text())
		for i in range(0, self.text_fields):
			if len(self.tspan_node[i].childNodes) > 0 and i <= (len(text_list) - 1):
				new_text_node = self.xmldoc.createTextNode(text_list[i])
				old_text_node = self.tspan_node[i].childNodes[0]
				self.tspan_node[i].removeChild(old_text_node)
				# add new text node
				self.tspan_node[i].appendChild(new_text_node)
		self.writeToFile(self.xmldoc)
		self.display_svg(self.filename)

	def accept(self):
		#TODO add the file to the project
		pass

	def btnAdvanced_clicked(self):
		_ = self.app._tr
		#use an external editor to edit the image
		try:
			prog = "inkscape"
			#check if inkscape is installed
			if subprocess.call('which ' + prog + ' 2>/dev/null', shell=True) == 0:
				# launch Inkscape
				# debug info
				log.info("Inkscape command: {} {} ".format(prog, self.filename))

				p=subprocess.Popen([prog, self.filename])

				# wait for process to finish (so we can update the preview)
				p.communicate()

				# update image preview
				self.display_svg(self.filename)
			else:
				msg = QMessageBox()
				msg.setText(_("There was an error trying to open {}.").format(prog.capitalize()))
				msg.exec_()

		except OSError:
			msg = QMessageBox()
			msg.setText(_("Please install {} to use this function").format(prog.capitalize()))
			msg.exec_()