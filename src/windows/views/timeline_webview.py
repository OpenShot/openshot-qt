""" 
 @file
 @brief This file loads the interactive HTML timeline
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <eolinwen@gmail.com>
 
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

import os

from PyQt5.QtCore import QFileInfo, pyqtSlot, QUrl, Qt, QCoreApplication
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWebKitWidgets import QWebView
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes.query import Transition
from classes.logger import log
from classes.app import get_app
from classes import info, updates
from classes import settings
from classes.query import File, Clip

try:
    import json
except ImportError:
    import simplejson as json

JS_SCOPE_SELECTOR = "$('body').scope()"


class TimelineWebView(QWebView, updates.UpdateInterface):
    """ A WebView QWidget used to load the Timeline """

    # Path to html file
    html_path = os.path.join(info.PATH, 'timeline', 'index.html')

    def eval_js(self, code):
        return self.page().mainFrame().evaluateJavaScript(code)

    # This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface)
    def changed(self, action):

        # Send a JSON version of the UpdateAction to the timeline webview method: ApplyJsonDiff()
        if action.type == "load":
            # Load entire project data
            code = JS_SCOPE_SELECTOR + ".LoadJson(" + action.json() + ");"
        else:
            # Apply diff to part of project data
            code = JS_SCOPE_SELECTOR + ".ApplyJsonDiff([" + action.json() + "]);"
        self.eval_js(code)

    # Javascript callable function to update the project data when a clip changes
    @pyqtSlot(str)
    def update_clip_data(self, clip_json, only_basic_props=True):
        """ Create an updateAction and send it to the update manager """

        # read clip json
        if not isinstance(clip_json, dict):
            clip_data = json.loads(clip_json)
        else:
            clip_data = clip_json

        # Search for matching clip in project data (if any)
        existing_clip = Clip.get(id=clip_data["id"])
        if not existing_clip:
            # Create a new clip (if not exists)
            existing_clip = Clip()
        existing_clip.data = clip_data

        # Remove unneeded properties (since they don't change here... this is a performance boost)
        if only_basic_props:
            existing_clip.data = {}
            existing_clip.data["id"] = clip_data["id"]
            existing_clip.data["layer"] = clip_data["layer"]
            existing_clip.data["position"] = clip_data["position"]
            existing_clip.data["start"] = clip_data["start"]
            existing_clip.data["end"] = clip_data["end"]

        # Save clip
        existing_clip.save()

    # Add missing transition
    @pyqtSlot(str)
    def add_missing_transition(self, transition_json):

        transition_details = json.loads(transition_json)

        # Get FPS from project
        fps = get_app().project.get(["fps"])
        fps_float = float(fps["num"]) / float(fps["den"])

        # Open up QtImageReader for transition Image
        transition_reader = openshot.QtImageReader(
            os.path.join(info.PATH, "transitions", "extra", "wipe_diagonal_2.png"))

        # Generate transition object
        transition_object = openshot.Mask()

        # Set brightness and contrast, to correctly transition for overlapping clips
        brightness = transition_object.brightness
        brightness.AddPoint(1, 1.0, openshot.BEZIER)
        brightness.AddPoint((transition_details["end"]) * fps_float, -1.0, openshot.BEZIER)
        contrast = openshot.Keyframe(3.0)

        # Create transition dictionary
        transitions_data = {
            "id": get_app().project.generate_id(),
            "layer": transition_details["layer"],
            "title": "Transition",
            "type": "Mask",
            "position": transition_details["position"],
            "start": transition_details["start"],
            "end": transition_details["end"],
            "brightness": json.loads(brightness.Json()),
            "contrast": json.loads(contrast.Json()),
            "reader": json.loads(transition_reader.Json()),
            "replace_image": False
        }

        # Send to update manager
        self.update_transition_data(transitions_data, only_basic_props=False)

    # Javascript callable function to update the project data when a transition changes
    @pyqtSlot(str)
    def update_transition_data(self, transition_json, only_basic_props=True):
        """ Create an updateAction and send it to the update manager """

        # read clip json
        if not isinstance(transition_json, dict):
            transition_data = json.loads(transition_json)
        else:
            transition_data = transition_json

        # Search for matching clip in project data (if any)
        existing_item = Transition.get(id=transition_data["id"])
        if not existing_item:
            # Create a new clip (if not exists)
            existing_item = Transition()
        existing_item.data = transition_data


        # Get FPS from project
        fps = get_app().project.get(["fps"])
        fps_float = float(fps["num"]) / float(fps["den"])

        # Update the brightness and contrast keyframes to match the duration of the transition
        duration = existing_item.data["end"] - existing_item.data["start"]
        brightness = openshot.Keyframe()
        brightness.AddPoint(1, 1.0, openshot.BEZIER)
        brightness.AddPoint(duration * fps_float, -1.0, openshot.BEZIER)

        # Only include the basic properties (performance boost)
        if only_basic_props:
            existing_item.data = {}
            existing_item.data["id"] = transition_data["id"]
            existing_item.data["layer"] = transition_data["layer"]
            existing_item.data["position"] = transition_data["position"]
            existing_item.data["start"] = transition_data["start"]
            existing_item.data["end"] = transition_data["end"]
            existing_item.data["brightness"] = json.loads(brightness.Json())

        # Save transition
        existing_item.save()

    # Prevent default context menu, and ignore, so that javascript can intercept
    def contextMenuEvent(self, event):
        event.ignore()

    # Javascript callable function to show clip or transition content menus, passing in type to show
    @pyqtSlot(str)
    def ShowPlayheadMenu(self, position=None):
        log.info('ShowPlayheadMenu: %s' % position)

        menu = QMenu(self)
        if type == "clip":
            menu.addAction(self.window.actionRemoveClip)
        elif type == "transition":
            menu.addAction(self.window.actionRemoveTransition)
            # return menu.popup(QCursor.pos())

    @pyqtSlot(str)
    def ShowEffectMenu(self, effect_id=None):
        log.info('ShowEffectMenu: %s' % effect_id)

        # Set the selected clip (if needed)
        if effect_id not in self.window.selected_effects:
            self.window.addSelection(effect_id, 'effect')

        menu = QMenu(self)
        menu.addAction(self.window.actionRemoveEffect)
        return menu.popup(QCursor.pos())

    @pyqtSlot(str)
    def ShowClipMenu(self, clip_id=None):
        log.info('ShowClipMenu: %s' % clip_id)

        # Set the selected clip (if needed)
        if clip_id not in self.window.selected_clips:
            self.window.addSelection(clip_id, 'clip')

        menu = QMenu(self)
        menu.addAction(self.window.actionRemoveClip)
        return menu.popup(QCursor.pos())

    @pyqtSlot(str)
    def ShowTransitionMenu(self, tran_id=None):
        log.info('ShowTransitionMenu: %s' % tran_id)

        # Set the selected transition (if needed)
        if tran_id not in self.window.selected_transitions:
            self.window.addSelection(tran_id, 'transition')

        menu = QMenu(self)
        menu.addAction(self.window.actionRemoveTransition)
        return menu.popup(QCursor.pos())

    @pyqtSlot(str)
    def ShowTrackMenu(self, layer_id=None):
        log.info('ShowTrackMenu: %s' % layer_id)

        if layer_id not in self.window.selected_tracks:
            self.window.selected_tracks = [layer_id]

        menu = QMenu(self)
        menu.addAction(self.window.actionAddTrackAbove)
        menu.addAction(self.window.actionAddTrackBelow)
        menu.addSeparator()
        menu.addAction(self.window.actionRemoveTrack)
        return menu.popup(QCursor.pos())

    @pyqtSlot(str)
    def ShowMarkerMenu(self, marker_id=None):
        log.info('ShowMarkerMenu: %s' % marker_id)

        if marker_id not in self.window.selected_markers:
            self.window.selected_markers = [marker_id]

        menu = QMenu(self)
        menu.addAction(self.window.actionRemoveMarker)
        return menu.popup(QCursor.pos())

    @pyqtSlot(float, int, str)
    def PlayheadMoved(self, position_seconds, position_frames, time_code):
        log.info("PlayheadMoved - position_seconds: %s, position_frames: %s, time_code: %s" % (position_seconds, position_frames, time_code))

        if self.last_position_frames != position_frames:
            # Update time code (to prevent duplicate previews)
            self.last_position_frames = position_frames

            # Notify main window of current frame
            self.window.previewFrame(position_seconds, position_frames, time_code)

    @pyqtSlot(int)
    def movePlayhead(self, position_frames):
        """ Move the playhead since the position has changed inside OpenShot (probably due to the video player) """

        # Get access to timeline scope and set scale to zoom slider value (passed in)
        code = JS_SCOPE_SELECTOR + ".MovePlayheadToFrame(" + str(position_frames) + ");"
        self.eval_js(code)

    @pyqtSlot(int)
    def SetSnappingMode(self, enable_snapping):
        """ Enable / Disable snapping mode """

        # Init snapping state (1 = snapping, 0 = no snapping)
        self.eval_js(JS_SCOPE_SELECTOR + ".SetSnappingMode(%s);" % int(enable_snapping))

    @pyqtSlot(str, str)
    def addSelection(self, item_id, item_type):
        """ Add the selected item to the current selection """

        # Add to main window
        self.window.addSelection(item_id, item_type)

    @pyqtSlot(str, str)
    def removeSelection(self, item_id, item_type):
        """ Remove the selected clip from the selection """

        # Remove from main window
        self.window.removeSelection(item_id, item_type)

    @pyqtSlot(str)
    def qt_log(self, message=None):
        log.info(message)

    # Handle changes to zoom level, update js
    def update_zoom(self, newValue):
        _ = get_app()._tr
        self.window.zoomScaleLabel.setText(_("{} seconds").format(newValue))
        # Get access to timeline scope and set scale to zoom slider value (passed in)
        cmd = JS_SCOPE_SELECTOR + ".setScale(" + str(newValue) + ");"
        self.page().mainFrame().evaluateJavaScript(cmd)

    # Capture wheel event to alter zoom slider control
    def wheelEvent(self, event):
        if int(QCoreApplication.instance().keyboardModifiers() & Qt.ControlModifier) > 0:
            # For each 120 (standard scroll unit) adjust the zoom slider
            tick_scale = 120
            steps = int(event.angleDelta().y() / tick_scale)
            self.window.sliderZoom.setValue(self.window.sliderZoom.value() - self.window.sliderZoom.pageStep() * steps)
        # Otherwise pass on to implement default functionality (scroll in QWebView)
        else:
            # self.show_context_menu('clip') #Test of spontaneous context menu creation
            super(type(self), self).wheelEvent(event)

    def setup_js_data(self):
        # Export self as a javascript object in webview
        self.page().mainFrame().addToJavaScriptWindowObject('timeline', self)
        self.page().mainFrame().addToJavaScriptWindowObject('mainWindow', self.window)

        # Initialize snapping mode
        self.SetSnappingMode(self.window.actionSnappingTool.isChecked())

    def dragEnterEvent(self, event):

        # If a plain text drag accept
        if not self.new_item and not event.mimeData().hasUrls() and event.mimeData().hasText():
            # get type of dropped data
            self.item_type = event.mimeData().html()

            # Track that a new item is being 'added'
            self.new_item = True

            # Get the mime data (i.e. list of files, list of transitions, etc...)
            data = json.loads(event.mimeData().text())
            pos = event.posF()

            # create the item
            if self.item_type == "clip":
                self.addClip(data, pos)
            elif self.item_type == "transition":
                self.addTransition(data, pos)

        # accept all events, even if a new clip is not being added
        event.accept()

    # Add Clip
    def addClip(self, data, position):

        # Get app object
        app = get_app()

        # Search for matching file in project data (if any)
        file_id = data[0]
        file = File.get(id=file_id)

        if (file.data["media_type"] == "video" or file.data["media_type"] == "image"):
            # Determine thumb path
            thumb_path = os.path.join(info.THUMBNAIL_PATH, "%s.png" % file.data["id"])
        else:
            # Audio file
            thumb_path = os.path.join(info.PATH, "images", "AudioThumbnail.png")

        # Get file name
        path, filename = os.path.split(file.data["path"])

        # Convert path to the correct relative path (based on this folder)
        file_path = file.absolute_path()

        # Create clip object for this file
        c = openshot.Clip(file_path)

        # Append missing attributes to Clip JSON
        new_clip = json.loads(c.Json())
        new_clip["file_id"] = file.id
        new_clip["title"] = filename
        new_clip["image"] = thumb_path

        # Find the closest track (from javascript)
        top_layer = int(self.eval_js(JS_SCOPE_SELECTOR + ".GetJavaScriptTrack(" + str(position.y()) + ");"))
        new_clip["layer"] = top_layer

        # Find position from javascript
        js_position = self.eval_js(JS_SCOPE_SELECTOR + ".GetJavaScriptPosition(" + str(position.x()) + ");")
        new_clip["position"] = js_position

        # Adjust clip duration, start, and end
        new_clip["duration"] = new_clip["reader"]["duration"]
        if file.data["media_type"] != "image":
            new_clip["end"] = new_clip["reader"]["duration"]
        else:
            new_clip["end"] = self.settings.get("default-image-length")  # default to 8 seconds

        # Add clip to timeline
        self.update_clip_data(new_clip, only_basic_props=False)

    # Add Transition
    def addTransition(self, file_ids, position):
        log.info("addTransition...")

        # Find the closest track (from javascript)
        top_layer = int(self.eval_js(JS_SCOPE_SELECTOR + ".GetJavaScriptTrack(" + str(position.y()) + ");"))

        # Find position from javascript
        js_position = self.eval_js(JS_SCOPE_SELECTOR + ".GetJavaScriptPosition(" + str(position.x()) + ");")

        # Get FPS from project
        fps = get_app().project.get(["fps"])
        fps_float = float(fps["num"]) / float(fps["den"])

        # Open up QtImageReader for transition Image
        transition_reader = openshot.QtImageReader(file_ids[0])

        brightness = openshot.Keyframe()
        brightness.AddPoint(1, 1.0, openshot.BEZIER)
        brightness.AddPoint(10 * fps_float, -1.0, openshot.BEZIER)
        contrast = openshot.Keyframe(3.0)

        # Create transition dictionary
        transitions_data = {
            "id": get_app().project.generate_id(),
            "layer": top_layer,
            "title": "Transition",
            "type": "Mask",
            "position": js_position,
            "start": 0,
            "end": 10,
            "brightness": json.loads(brightness.Json()),
            "contrast": json.loads(contrast.Json()),
            "reader": json.loads(transition_reader.Json()),
            "replace_image": False
        }

        # Send to update manager
        self.update_transition_data(transitions_data, only_basic_props=False)

    # Add Effect
    def addEffect(self, effect_names, position):
        log.info("addEffect...")
        # Get name of effect
        name = effect_names[0]

        # Find the closest track (from javascript)
        closest_track_num = int(self.eval_js(JS_SCOPE_SELECTOR + ".GetJavaScriptTrack(" + str(position.y()) + ");"))
        closest_layer = closest_track_num + 1  # convert track number to layer position

        # Find position from javascript
        js_position = self.eval_js(JS_SCOPE_SELECTOR + ".GetJavaScriptPosition(" + str(position.x()) + ");")

        # Loop through clips on the closest layer
        possible_clips = Clip.filter(layer=closest_layer)
        for clip in possible_clips:
            if js_position == 0 or (clip.data["position"] <= js_position <= clip.data["position"] + (
                        clip.data["end"] - clip.data["start"])):
                log.info("Applying effect to clip")
                log.info(clip)

                # Create Effect
                effect = None
                if name == "blur":
                    effect = openshot.Blur()
                elif name == "brightness":
                    effect = openshot.Brightness()
                elif name == "chromakey":
                    effect = openshot.ChromaKey()
                elif name == "deinterlace":
                    effect = openshot.Deinterlace()
                elif name == "mask":
                    effect = openshot.Mask()
                elif name == "negate":
                    effect = openshot.Negate()
                elif name == "saturation":
                    effect = openshot.Saturation()

                # Get Effect JSON
                effect.Id(get_app().project.generate_id())
                effect_json = json.loads(effect.Json())

                # Append effect JSON to clip
                clip.data["effects"].append(effect_json)

                # Update clip data for project
                self.update_clip_data(clip.data, only_basic_props=False)

    # Without defining this method, the 'copy' action doesn't show with cursor
    def dragMoveEvent(self, event):

        # Get cursor position
        pos = event.posF()

        # Move clip on timeline
        code = ""
        if self.item_type == "clip":
            code = JS_SCOPE_SELECTOR + ".MoveItem(" + str(pos.x()) + ", " + str(pos.y()) + ", 'clip');"
        elif self.item_type == "transition":
            code = JS_SCOPE_SELECTOR + ".MoveItem(" + str(pos.x()) + ", " + str(pos.y()) + ", 'transition');"
        self.eval_js(code)

        if code:
            event.accept()

    def dropEvent(self, event):
        log.info('Dropping {} in timeline.'.format(event.mimeData().text()))
        event.accept()

        data = json.loads(event.mimeData().text())
        pos = event.posF()

        # Update project data with final position of item
        if self.item_type == "clip":
            # Update most recent clip
            self.eval_js(JS_SCOPE_SELECTOR + ".UpdateRecentItemJSON('clip');")

        elif self.item_type == "transition":
            # Update most recent transition
            self.eval_js(JS_SCOPE_SELECTOR + ".UpdateRecentItemJSON('transition');")

        elif self.item_type == "effect":
            # Add effect only on drop
            self.addEffect(data, pos)

        # Clear new clip
        self.new_item = False
        self.item_type = None

    def __init__(self, window):
        QWebView.__init__(self)
        self.window = window
        self.setAcceptDrops(True)
        self.last_position_frames = None

        # Get settings
        self.settings = settings.get_settings()

        # Add self as listener to project data updates (used to update the timeline)
        get_app().updates.add_listener(self)

        # set url from configuration (QUrl takes absolute paths for file system paths, create from QFileInfo)
        self.setUrl(QUrl.fromLocalFile(QFileInfo(self.html_path).absoluteFilePath()))

        # Connect signal of javascript initialization to our javascript reference init function
        self.page().mainFrame().javaScriptWindowObjectCleared.connect(self.setup_js_data)

        # Connect zoom functionality
        window.sliderZoom.valueChanged.connect(self.update_zoom)

        # Init New clip
        self.new_item = False
        self.item_type = None
