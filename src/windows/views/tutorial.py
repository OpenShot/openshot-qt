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

from PyQt5.QtCore import Qt, QPoint, QRectF
from PyQt5.QtGui import (
    QColor, QPalette, QPen, QPainter, QPainterPath, QKeySequence,
)
from PyQt5.QtWidgets import (
    QAction, QLabel, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QToolButton, QCheckBox,
)
from classes.logger import log
from classes.app import get_app
from classes.metrics import track_metric_screen
from classes import sentry


class TutorialDialog(QWidget):
    """ A customized QWidget used to instruct a user how to use a certain feature """

    def paintEvent(self, event, *args):
        """ Custom paint event """
        # Paint custom frame image on QWidget
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        frameColor = QColor("#53a0ed")

        painter.setPen(QPen(frameColor, 2))
        painter.setBrush(self.palette().color(QPalette.Window))
        painter.drawRoundedRect(
            QRectF(31, 0,
                   self.width() - 31,
                   self.height()
                   ),
            10, 10)

        # Paint blue triangle (if needed)
        if self.arrow:
            arrow_height = 20
            path = QPainterPath()
            path.moveTo(0, 35)
            path.lineTo(31, 35 - arrow_height)
            path.lineTo(
                31, int((35 - arrow_height) + (arrow_height * 2)))
            path.lineTo(0, 35)
            painter.fillPath(path, frameColor)

    def checkbox_metrics_callback(self, state):
        """ Callback for error and anonymous usage checkbox"""
        s = get_app().get_settings()
        if state == Qt.Checked:
            # Enabling metrics sending
            s.set("send_metrics", True)
            sentry.init_tracing()

            # Opt-in for metrics tracking
            track_metric_screen("metrics-opt-in")
        else:
            # Opt-out for metrics tracking
            track_metric_screen("metrics-opt-out")
            sentry.disable_tracing()

            # Disable metric sending
            s.set("send_metrics", False)

    def mouseReleaseEvent(self, event):
        """Process click events on tutorial. Especially useful when tutorial messages are partially
        obscured or offscreen (i.e. on small screens). Just click any part of the tutorial, and it will
        move on to the next one."""
        self.manager.next_tip(self.widget_id)

    def __init__(self, widget_id, text, arrow, manager, *args):
        # Invoke parent init
        QWidget.__init__(self, *args)

        # get translations
        app = get_app()
        _ = app._tr

        # Keep track of widget to position next to
        self.widget_id = widget_id
        self.arrow = arrow
        self.manager = manager

        # Create vertical box
        vbox = QVBoxLayout()
        vbox.setContentsMargins(32, 10, 10, 10)

        # Add label
        self.label = QLabel(self)
        self.label.setText(text)
        self.label.setTextFormat(Qt.RichText)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("margin-left: 20px;")
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents)
        vbox.addWidget(self.label)

        # Add error and anonymous metrics checkbox (for ID=0) tooltip
        # This is a bit of a hack, but since it's the only exception, it's
        # probably okay for now.
        if self.widget_id == "0":
            # Get settings
            s = get_app().get_settings()

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
        hbox.setContentsMargins(20, 10, 0, 0)

        # Close action
        self.close_action = QAction(_("Hide Tutorial"), self)
        self.close_action.setShortcut(QKeySequence(Qt.Key_Escape))
        self.close_action.setShortcutContext(Qt.ApplicationShortcut)

        # Create buttons
        self.btn_close_tips = QPushButton(self)
        self.btn_close_tips.setText(_("Hide Tutorial"))
        self.btn_close_tips.addAction(self.close_action)

        self.btn_next_tip = QPushButton(self)
        self.btn_next_tip.setText(_("Next"))
        self.btn_next_tip.setStyleSheet("font-weight:bold;")

        hbox.addWidget(self.btn_close_tips)
        hbox.addWidget(self.btn_next_tip)
        vbox.addLayout(hbox)

        # Set layout, cursor, and size
        self.setLayout(vbox)
        self.setCursor(Qt.ArrowCursor)
        self.setMinimumWidth(350)
        self.setMinimumHeight(100)
        self.setFocusPolicy(Qt.ClickFocus)

        # Make transparent
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        # Connect close action signal
        self.close_action.triggered.connect(
            functools.partial(self.manager.hide_tips, self.widget_id, True))


class TutorialManager(object):
    """ Manage and present a list of tutorial dialogs """

    def process(self, parent_name=None):
        """ Process and show the first non-completed tutorial """

        # If a tutorial is already visible, just update it
        if self.current_dialog:
            # Respond to possible dock floats/moves
            self.dock.raise_()
            self.re_position_dialog()
            return

        # Loop through and add each tutorial dialog
        for tutorial_details in self.tutorial_objects:
            # Get details
            tutorial_id = tutorial_details["id"]

            # Get QWidget
            tutorial_object = self.get_object(tutorial_details["object_id"])

            # Skip completed tutorials (and invisible widgets)
            if not self.tutorial_enabled or tutorial_id in self.tutorial_ids or tutorial_object.visibleRegion().isEmpty():
                continue

            # Create tutorial
            self.position_widget = tutorial_object
            self.offset = QPoint(
                int(tutorial_details["x"]),
                int(tutorial_details["y"]))
            tutorial_dialog = TutorialDialog(tutorial_id, tutorial_details["text"], tutorial_details["arrow"], self)

            # Connect signals
            tutorial_dialog.btn_next_tip.clicked.connect(functools.partial(self.next_tip, tutorial_id))
            tutorial_dialog.btn_close_tips.clicked.connect(functools.partial(self.hide_tips, tutorial_id, True))

            # Get previous dock contents
            old_widget = self.dock.widget()

            # Insert into tutorial dock
            self.dock.setWidget(tutorial_dialog)
            self.current_dialog = tutorial_dialog

            # Show dialog
            self.dock.adjustSize()
            self.dock.setEnabled(True)
            self.re_position_dialog()
            self.dock.show()

            # Delete old widget
            if old_widget:
                old_widget.close()

            break

    def get_object(self, object_id):
        """Get an object from the main window by object id"""
        if object_id == "filesView":
            return self.win.filesView
        elif object_id == "timeline":
            return self.win.timeline
        elif object_id == "dockVideo":
            return self.win.dockVideo
        elif object_id == "propertyTableView":
            return self.win.propertyTableView
        elif object_id == "transitionsView":
            return self.win.transitionsView
        elif object_id == "effectsView":
            return self.win.effectsView
        elif object_id == "emojisView":
            return self.win.emojiListView
        elif object_id == "actionPlay":
            # Find play/pause button on transport controls toolbar
            for w in self.win.actionPlay.associatedWidgets():
                if isinstance(w, QToolButton):
                    return w
        elif object_id == "export_button":
            # Find export toolbar button on main window
            for w in self.win.actionExportVideo.associatedWidgets():
                if isinstance(w, QToolButton):
                    return w

    def next_tip(self, tid):
        """ Mark the current tip completed, and show the next one """
        # Hide matching tutorial
        self.hide_tips(tid)

        # Advance to the next one
        self.process()

    def hide_tips(self, tid, user_clicked=False):
        """ Hide the current tip, and don't show anymore """
        s = get_app().get_settings()

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

        # Forgot current tutorial
        self.current_dialog = None

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
        except Exception:
            log.debug('Failed to properly disconnect from dock signals', exc_info=1)

        # Close dialog window
        self.close_dialogs()

    def re_show_dialog(self):
        """ Re show an active dialog """
        if self.current_dialog:
            self.dock.raise_()
            self.dock.show()

    def hide_dialog(self):
        """ Hide an active dialog """
        if self.current_dialog:
            self.dock.hide()

    def re_position_dialog(self):
        """ Reposition a tutorial dialog next to another widget """
        if self.current_dialog:
            # Check if target is visible
            if self.position_widget.isHidden():
                self.hide_dialog()
                return

            # Locate tutorial popup relative to its "target" widget
            pos_rect = self.position_widget.rect()

            # Start with a 1/4-size offset rectangle, so the tutorial dialog
            # floats a bit, then apply any custom offset defined for this popup.
            pos_rect.setSize(pos_rect.size() / 4)
            pos_rect.translate(self.offset)
            # Map the new rectangle's bottom-right corner to global coords
            position = self.position_widget.mapToGlobal(pos_rect.bottomRight())

            # Move tutorial widget to the correct position
            self.dock.move(position)
            self.re_show_dialog()

    def __init__(self, win):
        """ Constructor """
        self.win = win
        self.dock = win.dockTutorial
        self.current_dialog = None

        # get translations
        app = get_app()
        _ = app._tr

        # get settings
        s = app.get_settings()
        self.tutorial_enabled = s.get("tutorial_enabled")
        self.tutorial_ids = s.get("tutorial_ids").split(",")

        # Add all possible tutorials
        self.tutorial_objects = [
            {"id": "0",
             "x": 0,
             "y": 0,
             "object_id": "dockVideo",
             "text": _("<b>Welcome!</b> OpenShot Video Editor is an award-winning, open-source video editing application! This tutorial will walk you through the basics.<br><br>Would you like to automatically send errors and metrics to help improve OpenShot?"),
             "arrow": False
             },
            {"id": "1",
             "x": 0,
             "y": 0,
             "object_id": "filesView",
             "text": _("<b>Project Files:</b> Get started with your project by adding video, audio, and image files here. Drag and drop files from your file system."),
             "arrow": True
             },
            {"id": "2",
             "x": 0,
             "y": 0,
             "object_id": "timeline",
             "text": _("<b>Timeline:</b> Arrange your clips on the timeline here. Overlap clips to create automatic transitions. Access lots of fun presets and options by right-clicking on clips."),
             "arrow": True
             },
            {"id": "3",
             "x": 10,
             "y": -27,
             "object_id": "actionPlay",
             "text": _("<b>Video Preview:</b> Watch your timeline video preview here. Use the buttons (play, rewind, fast-forward) to control the video playback."),
             "arrow": True},
            {"id": "4",
             "x": 0,
             "y": 0,
             "object_id": "propertyTableView",
             "text": _("<b>Properties:</b> View and change advanced properties of clips and effects here. Right-clicking on clips is usually faster than manually changing properties."),
             "arrow": True
             },
            {"id": "5",
             "x": 0,
             "y": 0,
             "object_id": "transitionsView",
             "text": _("<b>Transitions:</b> Create a gradual fade from one clip to another. Drag and drop a transition onto the timeline and position it on top of a clip (usually at the beginning or ending)."),
             "arrow": True
             },
            {"id": "6",
             "x": 0,
             "y": 0,
             "object_id": "effectsView",
             "text": _("<b>Effects:</b> Adjust brightness, contrast, saturation, and add exciting special effects. Drag and drop an effect onto the timeline and position it on top of a clip (or track)"),
             "arrow": True
             },
            {"id": "8",
             "x": 0,
             "y": 0,
             "object_id": "emojisView",
             "text": _("<b>Emojis:</b> Add exciting and colorful emojis to your project! Drag and drop an emoji onto the timeline. The emoji will become a new Clip when dropped on the Timeline."),
             "arrow": True
             },
            {"id": "7",
             "x": 10,
             "y": -27,
             "object_id": "export_button",
             "text": _("<b>Export Video:</b> When you are ready to create your finished video, click this button to export your timeline as a single video file."),
             "arrow": True
             }
        ]

        # Configure tutorial frame
        self.dock.setTitleBarWidget(QWidget())  # Prevents window decoration
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
        self.win.dockEmojis.visibilityChanged.connect(functools.partial(self.process, "dockEmojis"))

        # Process tutorials (1 by 1)
        if self.tutorial_enabled:
            self.process()
