"""
 @file
 @brief This file contains the tutorial dialogs, which are used to explain certain features to new users
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

import functools

from PyQt5.QtCore import Qt, QPoint, QRectF, QEvent
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QLabel, QWidget, QDockWidget, QVBoxLayout, QHBoxLayout, QPushButton, QToolButton, QCheckBox

from classes.logger import log
from classes.settings import get_settings
from classes.app import get_app
from classes.metrics import *


class TutorialDialog(QWidget):
    """ A customized QWidget used to instruct a user how to use a certain feature """

    def paintEvent(self, event, *args):
        """ Custom paint event """
        # Paint custom frame image on QWidget
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        frameColor = QColor("#53a0ed")

        # Paint blue rounded rectangle
        path = QPainterPath()
        path.addRoundedRect(QRectF(31, 0, self.width()-31, self.height()), 10, 10)
        painter.setPen(Qt.NoPen)
        painter.fillPath(path, frameColor)
        painter.drawPath(path)

        # Paint gray rounded rectangle
        path = QPainterPath()
        path.addRoundedRect(QRectF(32, 1, self.width()-33, self.height()-2), 10, 10)
        painter.setPen(Qt.NoPen)
        painter.fillPath(path, self.palette().color(QPalette.Window))
        painter.drawPath(path)

        # Paint blue triangle (if needed)
        if self.arrow:
            arrow_height = 20
            path = QPainterPath()
            path.moveTo (0, 35)
            path.lineTo (31, 35 - arrow_height)
            path.lineTo (31, (35 - arrow_height) + (arrow_height * 2))
            path.lineTo (0, 35)
            painter.fillPath(path, frameColor)
            painter.drawPath(path)

    def checkbox_metrics_callback(self, state):
        """ Callback for error and anonymous usage checkbox"""
        s = get_settings()
        if state == Qt.Checked:
            # Enabling metrics sending
            s.set("send_metrics", True)

            # Opt-in for metrics tracking
            track_metric_screen("metrics-opt-in")
        else:
            # Opt-out for metrics tracking
            track_metric_screen("metrics-opt-out")

            # Disable metric sending
            s.set("send_metrics", False)

    def __init__(self, id, text, arrow, *args):
        # Invoke parent init
        QWidget.__init__(self, *args)

        # get translations
        app = get_app()
        _ = app._tr

        # Keep track of widget to position next to
        self.id = id
        self.arrow = arrow

        # Create vertical box
        vbox = QVBoxLayout()
        vbox.setContentsMargins(32,10,10,10)

        # Add label
        self.label = QLabel(self)
        self.label.setText(text)
        self.label.setTextFormat(Qt.RichText)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("margin-left: 20px;")
        vbox.addWidget(self.label)

        # Add error and anonymous metrics checkbox (for ID=0) tooltip
        # This is a bit of a hack, but since it's the only exception, it's
        # probably okay for now.
        if self.id == "0":
            # Get settings
            s = get_settings()

            # create spinner
            checkbox_metrics = QCheckBox()
            checkbox_metrics.setText(_("Yes, I would like to improve OpenShot!"))
            checkbox_metrics.setStyleSheet("margin-left: 25px; margin-bottom: 5px;")
            if s.get("send_metrics"):
                checkbox_metrics.setCheckState(Qt.Checked)
            else:
                checkbox_metrics.setCheckState(Qt.Unchecked)
            checkbox_metrics.stateChanged.connect(functools.partial(self.checkbox_metrics_callback))
            vbox.addWidget(checkbox_metrics)

        # Add button box
        hbox = QHBoxLayout()
        hbox.setContentsMargins(20,10,0,0)

        # Create buttons
        self.btn_close_tips = QPushButton(self)
        self.btn_close_tips.setText(_("Hide Tutorial"))
        self.btn_next_tip = QPushButton(self)
        self.btn_next_tip.setText(_("Next"))
        self.btn_next_tip.setStyleSheet("font-weight:bold;")
        hbox.addWidget(self.btn_close_tips)
        hbox.addWidget(self.btn_next_tip)
        vbox.addLayout(hbox)

        # Set layout
        self.setLayout(vbox)

        # Set size
        self.setMinimumWidth(350)
        self.setMinimumHeight(100)

        # Make transparent
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        #self.setWindowFlags(Qt.FramelessWindowHint)


class TutorialManager(object):
    """ Manage and present a list of tutorial dialogs """

    def process(self, parent_name=None):
        """ Process and show the first non-completed tutorial """

        # Do nothing if a tutorial is already visible
        if self.current_dialog:
            # XXX: Respond to possible dock floats/moves
            self.dock.raise_()
            self.re_position_dialog()
            return

        # Loop through and add each tutorial dialog
        for tutorial_details in self.tutorial_objects:
            # Get details
            tutorial_id = tutorial_details["id"]
            tutorial_object_id = tutorial_details["object_id"]
            tutorial_text = tutorial_details["text"]
            tutorial_x_offset = tutorial_details["x"]
            tutorial_y_offset = tutorial_details["y"]
            turorial_arrow = tutorial_details["arrow"]

            # Get QWidget
            tutorial_object = self.get_object(tutorial_object_id)

            # Skip completed tutorials (and invisible widgets)
            if tutorial_object.visibleRegion().isEmpty() or tutorial_id in self.tutorial_ids or not self.tutorial_enabled:
                continue

            # Create tutorial
            self.position_widget = tutorial_object
            self.x_offset = tutorial_x_offset
            self.y_offset = tutorial_y_offset
            tutorial_dialog = TutorialDialog(tutorial_id, tutorial_text, turorial_arrow)

            # Connect signals
            tutorial_dialog.btn_next_tip.clicked.connect(functools.partial(self.next_tip, tutorial_id))
            tutorial_dialog.btn_close_tips.clicked.connect(functools.partial(self.hide_tips, tutorial_id, True))

            # Insert into tutorial dock
            self.dock.setWidget(tutorial_dialog)
            self.current_dialog = tutorial_dialog

            # Show dialog
            self.dock.adjustSize()
            self.dock.setEnabled(True)
            self.re_position_dialog()
            #self.current_dialog.show()
            self.dock.show()
            break

    def get_object(self, object_id):
        """Get an object from the main window by object id"""
        if object_id == "filesTreeView":
            return self.win.filesTreeView
        elif object_id == "timeline":
            return self.win.timeline
        elif object_id == "dockVideoContents":
            return self.win.dockVideoContents
        elif object_id == "propertyTableView":
            return self.win.propertyTableView
        elif object_id == "transitionsTreeView":
            return self.win.transitionsTreeView
        elif object_id == "effectsTreeView":
            return self.win.effectsTreeView
        elif object_id == "export_button":
            # Find export toolbar button on main window
            export_button = None
            for toolbutton in self.win.toolBar.children():
                if type(toolbutton) == QToolButton and toolbutton.defaultAction() and toolbutton.defaultAction().objectName() == "actionExportVideo":
                    return toolbutton

    def next_tip(self, tid):
        """ Mark the current tip completed, and show the next one """
        # Hide matching tutorial
        self.hide_tips(tid)

        # Advance to the next one
        self.process()

    def hide_tips(self, tid, user_clicked=False):
        """ Hide the current tip, and don't show anymore """
        s = get_settings()

        # Loop through and find current tid
        for tutorial_object in self.tutorial_objects:
            # Get details
            tutorial_id = tutorial_object["id"]
            if tutorial_id == tid:
                # Hide dialog
                self.close_dialogs()
                # Update settings that this tutorial is completed
                if tid not in self.tutorial_ids:
                    self.tutorial_ids.append(str(tid))
                    s.set("tutorial_ids", ",".join(self.tutorial_ids))

        # Mark tutorial as completed (if settings)
        if user_clicked:
            # Disable all tutorials
            self.tutorial_enabled = False
            s.set("tutorial_enabled", False)

    def close_dialogs(self):
        """ Close any open tutorial dialogs """
        if self.current_dialog:
            self.dock.hide()
            self.dock.setEnabled(False)
            self.current_dialog = None

    def exit_manager(self):
        """ Disconnect from all signals, and shutdown tutorial manager """
        try:
            self.win.dockFiles.visibilityChanged.disconnect()
            self.win.dockTransitions.visibilityChanged.disconnect()
            self.win.dockEffects.visibilityChanged.disconnect()
            self.win.dockProperties.visibilityChanged.disconnect()
            self.win.dockVideo.visibilityChanged.disconnect()
        except:
            # Ignore errors from this
            pass

        # Close dialog window
        self.close_dialogs()

    def re_show_dialog(self):
        """ Re show an active dialog """
        if self.current_dialog:
            self.dock.raise_()
            self.dock.show()

    def re_position_dialog(self):
        """ Reposition a tutorial dialog next to another widget """
        if self.current_dialog:
            """ Move widget next to its position widget """
            x = self.position_widget.mapToGlobal(self.position_widget.pos()).x()
            y = self.position_widget.mapToGlobal(self.position_widget.pos()).y()
            self.dock.move(QPoint(x + self.x_offset, y + self.y_offset))

    def __init__(self, win):
        """ Constructor """
        self.win = win
        self.dock = win.dockTutorial
        self.current_dialog = None

        # get translations
        app = get_app()
        _ = app._tr

        # get settings
        s = get_settings()
        self.tutorial_enabled = s.get("tutorial_enabled")
        self.tutorial_ids = s.get("tutorial_ids").split(",")

        # Add all possible tutorials
        self.tutorial_objects = [    {"id":"0", "x":400, "y":0, "object_id":"filesTreeView", "text":_("<b>Welcome!</b> OpenShot Video Editor is an award-winning, open-source video editing application! This tutorial will walk you through the basics.<br><br>Would you like to automatically send errors and metrics to help improve OpenShot?"), "arrow":False},
                                     {"id":"1", "x":20, "y":0, "object_id":"filesTreeView", "text":_("<b>Project Files:</b> Get started with your project by adding video, audio, and image files here. Drag and drop files from your file system."), "arrow":True},
                                     {"id":"2", "x":200, "y":-15, "object_id":"timeline", "text":_("<b>Timeline:</b> Arrange your clips on the timeline here. Overlap clips to create automatic transitions. Access lots of fun presets and options by right-clicking on clips."), "arrow":True},
                                     {"id":"3", "x":150, "y":100, "object_id":"dockVideoContents", "text":_("<b>Video Preview:</b> Watch your timeline video preview here. Use the buttons (play, rewind, fast-forward) to control the video playback."), "arrow":True},
                                     {"id":"4", "x":20, "y":-35, "object_id":"propertyTableView", "text":_("<b>Properties:</b> View and change advanced properties of clips and effects here. Right-clicking on clips is usually faster than manually changing properties."), "arrow":True},
                                     {"id":"5", "x":20, "y":10, "object_id":"transitionsTreeView", "text":_("<b>Transitions:</b> Create a gradual fade from one clip to another. Drag and drop a transition onto the timeline and position it on top of a clip (usually at the beginning or ending)."), "arrow":True},
                                     {"id":"6", "x":20, "y":20, "object_id":"effectsTreeView", "text":_("<b>Effects:</b> Adjust brightness, contrast, saturation, and add exciting special effects. Drag and drop an effect onto the timeline and position it on top of a clip (or track)"), "arrow":True},
                                     {"id":"7", "x":-265, "y":-22, "object_id":"export_button", "text":_("<b>Export Video:</b> When you are ready to create your finished video, click this button to export your timeline as a single video file."), "arrow":True}
                                ]

        # Configure tutorial frame
        self.dock.setTitleBarWidget(QWidget()) # Prevents window decoration
        self.dock.setAttribute(Qt.WA_NoSystemBackground, True)
        self.dock.setAttribute(Qt.WA_TranslucentBackground, True)
        self.dock.setWindowFlags(Qt.FramelessWindowHint)
        self.dock.setFloating(True)


        # Connect to interface dock widgets
        self.win.dockFiles.visibilityChanged.connect(functools.partial(self.process, "dockFiles"))
        self.win.dockTransitions.visibilityChanged.connect(functools.partial(self.process, "dockTransitions"))
        self.win.dockEffects.visibilityChanged.connect(functools.partial(self.process, "dockEffects"))
        self.win.dockProperties.visibilityChanged.connect(functools.partial(self.process, "dockProperties"))
        self.win.dockVideo.visibilityChanged.connect(functools.partial(self.process, "dockVideo"))

        # Process tutorials (1 by 1)
        if self.tutorial_enabled:
            self.process()
