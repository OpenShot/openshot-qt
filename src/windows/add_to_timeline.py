"""
 @file
 @brief This file loads the Addtotimeline dialog (i.e add several clips in the timeline)
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <olivier@openshot.org>

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
from random import shuffle, randint, uniform

from PyQt5.QtWidgets import *
from PyQt5.QtGui import QIcon

from classes import settings
from classes import info, ui_util
from classes.logger import log
from classes.query import Track, Clip, Transition
from classes.app import get_app
from windows.views.add_to_timeline_treeview import TimelineTreeView

import openshot

try:
    import json
except ImportError:
    import simplejson as json


class AddToTimeline(QDialog):
    """ Add To timeline Dialog """

    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'add-to-timeline.ui')

    def btnMoveUpClicked(self, event):
        """Callback for move up button click"""
        log.info("btnMoveUpClicked")

        # Get selected file
        files = self.treeFiles.timeline_model.files
        selected_index = self.treeFiles.selected.row()

        # Ignore if empty files
        if not files:
            return

        # New index
        new_index = max(selected_index - 1, 0)
        log.info(new_index)

        # Remove item and move it
        files.insert(new_index, files.pop(selected_index))

        # Refresh tree
        self.treeFiles.refresh_view()

        # Select new position
        idx = self.treeFiles.timeline_model.model.index(new_index, 0)
        self.treeFiles.setCurrentIndex(idx)

    def btnMoveDownClicked(self, event):
        """Callback for move up button click"""
        log.info("btnMoveDownClicked")

        # Get selected file
        files = self.treeFiles.timeline_model.files
        selected_index = self.treeFiles.selected.row()

        # Ignore if empty files
        if not files:
            return

        # New index
        new_index = min(selected_index + 1, len(files) - 1)
        log.info(new_index)

        # Remove item and move it
        files.insert(new_index, files.pop(selected_index))

        # Refresh tree
        self.treeFiles.refresh_view()

        # Select new position
        idx = self.treeFiles.timeline_model.model.index(new_index, 0)
        self.treeFiles.setCurrentIndex(idx)

    def btnShuffleClicked(self, event):
        """Callback for move up button click"""
        log.info("btnShuffleClicked")

        # Shuffle files
        files = shuffle(self.treeFiles.timeline_model.files)

        # Refresh tree
        self.treeFiles.refresh_view()

    def btnRemoveClicked(self, event):
        """Callback for move up button click"""
        log.info("btnRemoveClicked")

        # Get selected file
        files = self.treeFiles.timeline_model.files
        selected_index = self.treeFiles.selected.row()

        # Ignore if empty files
        if not files:
            return

        # Remove item
        files.pop(selected_index)

        # Refresh tree
        self.treeFiles.refresh_view()

        # Select next item (if any)
        new_index = max(len(files) - 1, 0)

        # Select new position
        idx = self.treeFiles.timeline_model.model.index(new_index, 0)
        self.treeFiles.setCurrentIndex(idx)

    def accept(self):
        """ Ok button clicked """
        log.info('accept')

        # Get settings from form
        start_position = self.txtStartTime.value()
        track_num = self.cmbTrack.currentData()
        fade_value = self.cmbFade.currentData()
        fade_length = self.txtFadeLength.value()
        transition_path = self.cmbTransition.currentData()
        transition_length = self.txtTransitionLength.value()
        zoom_value = self.cmbZoom.currentData()

        # Init position
        position = start_position

        random_transition = False
        if transition_path == "random":
            random_transition = True

        # Get frames per second
        fps = get_app().project.get(["fps"])
        fps_float = float(fps["num"]) / float(fps["den"])

        # Loop through each file (in the current order)
        for file in self.treeFiles.timeline_model.files:
            # Create a clip
            clip = Clip()
            clip.data = {}

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
            new_clip["position"] = position
            new_clip["layer"] = track_num
            new_clip["file_id"] = file.id
            new_clip["title"] = filename
            new_clip["image"] = thumb_path

            # Check for optional start and end attributes
            start_time = 0
            end_time = new_clip["reader"]["duration"]

            if 'start' in file.data.keys():
                start_time = file.data['start']
                new_clip["start"] = start_time
            if 'end' in file.data.keys():
                end_time = file.data['end']
                new_clip["end"] = end_time

            # Adjust clip duration, start, and end
            new_clip["duration"] = new_clip["reader"]["duration"]
            if file.data["media_type"] == "image":
                end_time = self.settings.get("default-image-length")  # default to 8 seconds
                new_clip["end"] = end_time

            # Adjust Fade of Clips (if no transition is chosen)
            if not transition_path:
                if fade_value != None:
                    # Overlap this clip with the previous one (if any)
                    position = max(start_position, new_clip["position"] - fade_length)
                    new_clip["position"] = position

                if fade_value == 'Fade In' or fade_value == 'Fade In & Out':
                    start = openshot.Point((start_time * fps_float) + 1, 1.0, openshot.BEZIER)
                    start_object = json.loads(start.Json())
                    end = openshot.Point(min((start_time + fade_length) * fps_float, end_time * fps_float), 0.0, openshot.BEZIER)
                    end_object = json.loads(end.Json())
                    new_clip['alpha']["Points"].append(start_object)
                    new_clip['alpha']["Points"].append(end_object)

                if fade_value == 'Fade Out' or fade_value == 'Fade In & Out':
                    start = openshot.Point(max((end_time * fps_float) - (fade_length * fps_float), start_time * fps_float), 0.0, openshot.BEZIER)
                    start_object = json.loads(start.Json())
                    end = openshot.Point(end_time * fps_float, 1.0, openshot.BEZIER)
                    end_object = json.loads(end.Json())
                    new_clip['alpha']["Points"].append(start_object)
                    new_clip['alpha']["Points"].append(end_object)

            # Adjust zoom amount
            if zoom_value != None:
                # Location animation
                if zoom_value == "Random":
                    animate_start_x = uniform(-0.5, 0.5)
                    animate_end_x = uniform(-0.15, 0.15)
                    animate_start_y = uniform(-0.5, 0.5)
                    animate_end_y = uniform(-0.15, 0.15)

                    # Scale animation
                    start_scale = uniform(0.5, 1.5)
                    end_scale = uniform(0.85, 1.15)

                elif zoom_value == "Zoom In":
                    animate_start_x = 0.0
                    animate_end_x = 0.0
                    animate_start_y = 0.0
                    animate_end_y = 0.0

                    # Scale animation
                    start_scale = 1.0
                    end_scale = 1.25

                elif zoom_value == "Zoom Out":
                    animate_start_x = 0.0
                    animate_end_x = 0.0
                    animate_start_y = 0.0
                    animate_end_y = 0.0

                    # Scale animation
                    start_scale = 1.25
                    end_scale = 1.0

                # Add keyframes
                start = openshot.Point((start_time * fps_float) + 1, start_scale, openshot.BEZIER)
                start_object = json.loads(start.Json())
                end = openshot.Point(end_time * fps_float, end_scale, openshot.BEZIER)
                end_object = json.loads(end.Json())
                new_clip["gravity"] = openshot.GRAVITY_CENTER
                new_clip["scale_x"]["Points"].append(start_object)
                new_clip["scale_x"]["Points"].append(end_object)
                new_clip["scale_y"]["Points"].append(start_object)
                new_clip["scale_y"]["Points"].append(end_object)

                # Add keyframes
                start_x = openshot.Point((start_time * fps_float) + 1, animate_start_x, openshot.BEZIER)
                start_x_object = json.loads(start_x.Json())
                end_x = openshot.Point(end_time * fps_float, animate_end_x, openshot.BEZIER)
                end_x_object = json.loads(end_x.Json())
                start_y = openshot.Point((start_time * fps_float) + 1, animate_start_y, openshot.BEZIER)
                start_y_object = json.loads(start_y.Json())
                end_y = openshot.Point(end_time * fps_float, animate_end_y, openshot.BEZIER)
                end_y_object = json.loads(end_y.Json())
                new_clip["gravity"] = openshot.GRAVITY_CENTER
                new_clip["location_x"]["Points"].append(start_x_object)
                new_clip["location_x"]["Points"].append(end_x_object)
                new_clip["location_y"]["Points"].append(start_y_object)
                new_clip["location_y"]["Points"].append(end_y_object)

            if transition_path:
                # Add transition for this clip (if any)
                # Open up QtImageReader for transition Image
                if random_transition:
                    random_index = randint(0, len(self.transitions))
                    transition_path = self.transitions[random_index]

                # Get reader for transition
                transition_reader = openshot.QtImageReader(transition_path)

                brightness = openshot.Keyframe()
                brightness.AddPoint(1, 1.0, openshot.BEZIER)
                brightness.AddPoint(min(transition_length, end_time - start_time) * fps_float, -1.0, openshot.BEZIER)
                contrast = openshot.Keyframe(3.0)

                # Create transition dictionary
                transitions_data = {
                    "layer": track_num,
                    "title": "Transition",
                    "type": "Mask",
                    "start": 0,
                    "end": min(transition_length, end_time - start_time),
                    "brightness": json.loads(brightness.Json()),
                    "contrast": json.loads(contrast.Json()),
                    "reader": json.loads(transition_reader.Json()),
                    "replace_image": False
                }

                # Overlap this clip with the previous one (if any)
                position = max(start_position, position - transition_length)
                transitions_data["position"] = position
                new_clip["position"] = position

                # Create transition
                tran = Transition()
                tran.data = transitions_data
                tran.save()


            # Save Clip
            clip.data = new_clip
            clip.save()

            # Increment position by length of clip
            position += (end_time - start_time)


        # Accept dialog
        super(AddToTimeline, self).accept()

    def reject(self):
        """ Cancel button clicked """
        log.info('reject')

        # Accept dialog
        super(AddToTimeline, self).reject()

    def __init__(self, files=None, position=0.0):
        # Create dialog class
        QDialog.__init__(self)

        # Load UI from Designer
        ui_util.load_ui(self, self.ui_path)

        # Init UI
        ui_util.init_ui(self)

        # Get settings
        self.settings = settings.get_settings()

        # Get translation object
        self.app = get_app()
        _ = self.app._tr

        # Add custom treeview to window
        self.treeFiles = TimelineTreeView(self)
        self.vboxTreeParent.insertWidget(0, self.treeFiles)

        # Update data in model
        self.treeFiles.timeline_model.update_model(files)

        # Refresh view
        self.treeFiles.refresh_view()

        # Init start position
        self.txtStartTime.setValue(position)

        # Add all tracks to dropdown
        tracks = Track.filter()
        for track in reversed(tracks):
            # Add to dropdown
            self.cmbTrack.addItem(_('Track %s' % track.data['number']), track.data['number'])

        # Add all fade options
        self.cmbFade.addItem(_('None'), None)
        self.cmbFade.addItem(_('Fade In'), 'Fade In')
        self.cmbFade.addItem(_('Fade Out'), 'Fade Out')
        self.cmbFade.addItem(_('Fade In & Out'), 'Fade In & Out')

        # Add all zoom options
        self.cmbZoom.addItem(_('None'), None)
        self.cmbZoom.addItem(_('Random'), 'Random')
        self.cmbZoom.addItem(_('Zoom In'), 'Zoom In')
        self.cmbZoom.addItem(_('Zoom Out'), 'Zoom Out')

        # Add all transitions
        transitions_dir = os.path.join(info.PATH, "transitions")
        common_dir = os.path.join(transitions_dir, "common")
        extra_dir = os.path.join(transitions_dir, "extra")
        transition_groups = [{"type": "common", "dir": common_dir, "files": os.listdir(common_dir)},
                             {"type": "extra", "dir": extra_dir, "files": os.listdir(extra_dir)}]

        self.cmbTransition.addItem(_('None'), None)
        self.cmbTransition.addItem(_('Random'), 'random')
        self.transitions = []
        for group in transition_groups:
            type = group["type"]
            dir = group["dir"]
            files = group["files"]

            for filename in sorted(files):
                path = os.path.join(dir, filename)
                (fileBaseName, fileExtension) = os.path.splitext(filename)

                # Skip hidden files (such as .DS_Store, etc...)
                if filename[0] == "." or "thumbs.db" in filename.lower():
                    continue

                # get name of transition
                trans_name = fileBaseName.replace("_", " ").capitalize()

                # Generate thumbnail for file (if needed)
                thumb_path = os.path.join(info.CACHE_PATH, "{}.png".format(fileBaseName))

                # Add item
                self.transitions.append(path)
                self.cmbTransition.addItem(QIcon(thumb_path), _(trans_name), path)

        # Connections
        self.btnMoveUp.clicked.connect(self.btnMoveUpClicked)
        self.btnMoveDown.clicked.connect(self.btnMoveDownClicked)
        self.btnShuffle.clicked.connect(self.btnShuffleClicked)
        self.btnRemove.clicked.connect(self.btnRemoveClicked)
        self.btnBox.accepted.connect(self.accept)
        self.btnBox.rejected.connect(self.reject)