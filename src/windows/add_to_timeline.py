"""
 @file
 @brief This file loads the Addtotimeline dialog (i.e add several clips in the timeline)
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <olivier@openshot.org>

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

import os, math
from operator import itemgetter
from random import shuffle, randint, uniform

from PyQt5.QtWidgets import *
from PyQt5.QtGui import QIcon

from classes import settings
from classes import info, ui_util
from classes.logger import log
from classes.query import Track, Clip, Transition
from classes.app import get_app
from classes.metrics import *
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

        selected_index = None
        if self.treeFiles.selected:
            selected_index = self.treeFiles.selected.row()

        # Ignore if empty files
        if not files or selected_index == None:
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

        selected_index = None
        if self.treeFiles.selected:
            selected_index = self.treeFiles.selected.row()

        # Ignore if empty files
        if not files or selected_index == None:
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

        selected_index = None
        if self.treeFiles.selected:
            selected_index = self.treeFiles.selected.row()

        # Ignore if empty files
        if not files or selected_index == None:
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

        # Update total
        self.updateTotal()

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
        image_length = self.txtImageLength.value()
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

            # Skip any clips that are missing a 'reader' attribute
            # TODO: Determine why this even happens, as it shouldn't be possible
            if not new_clip.get("reader"):
                continue  # Skip to next file

            # Overwrite frame rate (incase the user changed it in the File Properties)
            file_properties_fps = float(file.data["fps"]["num"]) / float(file.data["fps"]["den"])
            file_fps = float(new_clip["reader"]["fps"]["num"]) / float(new_clip["reader"]["fps"]["den"])
            fps_diff = file_fps / file_properties_fps
            new_clip["reader"]["fps"]["num"] = file.data["fps"]["num"]
            new_clip["reader"]["fps"]["den"] = file.data["fps"]["den"]
            # Scale duration / length / and end properties
            new_clip["reader"]["duration"] *= fps_diff
            new_clip["end"] *= fps_diff
            new_clip["duration"] *= fps_diff

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
                end_time = image_length
                new_clip["end"] = end_time

            # Adjust Fade of Clips (if no transition is chosen)
            if not transition_path:
                if fade_value != None:
                    # Overlap this clip with the previous one (if any)
                    position = max(start_position, new_clip["position"] - fade_length)
                    new_clip["position"] = position

                if fade_value == 'Fade In' or fade_value == 'Fade In & Out':
                    start = openshot.Point(round(start_time * fps_float) + 1, 0.0, openshot.BEZIER)
                    start_object = json.loads(start.Json())
                    end = openshot.Point(min(round((start_time + fade_length) * fps_float) + 1, round(end_time * fps_float) + 1), 1.0, openshot.BEZIER)
                    end_object = json.loads(end.Json())
                    new_clip['alpha']["Points"].append(start_object)
                    new_clip['alpha']["Points"].append(end_object)

                if fade_value == 'Fade Out' or fade_value == 'Fade In & Out':
                    start = openshot.Point(max(round((end_time * fps_float) + 1) - (round(fade_length * fps_float) + 1), round(start_time * fps_float) + 1), 1.0, openshot.BEZIER)
                    start_object = json.loads(start.Json())
                    end = openshot.Point(round(end_time * fps_float) + 1, 0.0, openshot.BEZIER)
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
                start = openshot.Point(round(start_time * fps_float) + 1, start_scale, openshot.BEZIER)
                start_object = json.loads(start.Json())
                end = openshot.Point(round(end_time * fps_float) + 1, end_scale, openshot.BEZIER)
                end_object = json.loads(end.Json())
                new_clip["gravity"] = openshot.GRAVITY_CENTER
                new_clip["scale_x"]["Points"].append(start_object)
                new_clip["scale_x"]["Points"].append(end_object)
                new_clip["scale_y"]["Points"].append(start_object)
                new_clip["scale_y"]["Points"].append(end_object)

                # Add keyframes
                start_x = openshot.Point(round(start_time * fps_float) + 1, animate_start_x, openshot.BEZIER)
                start_x_object = json.loads(start_x.Json())
                end_x = openshot.Point(round(end_time * fps_float) + 1, animate_end_x, openshot.BEZIER)
                end_x_object = json.loads(end_x.Json())
                start_y = openshot.Point(round(start_time * fps_float) + 1, animate_start_y, openshot.BEZIER)
                start_y_object = json.loads(start_y.Json())
                end_y = openshot.Point(round(end_time * fps_float) + 1, animate_end_y, openshot.BEZIER)
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
                brightness.AddPoint(round(min(transition_length, end_time - start_time) * fps_float) + 1, -1.0, openshot.BEZIER)
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

    def ImageLengthChanged(self, value):
        """Handle callback for image length being changed"""
        self.updateTotal()

    def updateTotal(self):
        """Calculate the total length of what's about to be added to the timeline"""
        fade_value = self.cmbFade.currentData()
        fade_length = self.txtFadeLength.value()
        transition_path = self.cmbTransition.currentData()
        transition_length = self.txtTransitionLength.value()

        total = 0.0
        for file in self.treeFiles.timeline_model.files:
            # Adjust clip duration, start, and end
            duration = file.data["duration"]
            if file.data["media_type"] == "image":
                duration = self.txtImageLength.value()

            if total != 0.0:
                # Don't subtract time from initial clip
                if not transition_path:
                    # No transitions
                    if fade_value != None:
                        # Fade clip - subtract the fade length
                        duration -= fade_length
                else:
                    # Transition
                    duration -= transition_length

            # Append duration to total
            total += duration

        # Get frames per second
        fps = get_app().project.get(["fps"])

        # Update label
        total_parts = self.secondsToTime(total, fps["num"], fps["den"])
        timestamp = "%s:%s:%s:%s" % (total_parts["hour"], total_parts["min"], total_parts["sec"], total_parts["frame"])
        self.lblTotalLengthValue.setText(timestamp)

    def padNumber(self, value, pad_length):
        format_mask = '%%0%sd' % pad_length
        return format_mask % value

    def secondsToTime(self, secs, fps_num, fps_den):
        # calculate time of playhead
        milliseconds = secs * 1000
        sec = math.floor(milliseconds/1000)
        milli = milliseconds % 1000
        min = math.floor(sec/60)
        sec = sec % 60
        hour = math.floor(min/60)
        min = min % 60
        day = math.floor(hour/24)
        hour = hour % 24
        week = math.floor(day/7)
        day = day % 7

        frame = round((milli / 1000.0) * (fps_num / fps_den)) + 1
        return { "week":self.padNumber(week,2), "day":self.padNumber(day,2), "hour":self.padNumber(hour,2), "min":self.padNumber(min,2), "sec":self.padNumber(sec,2), "milli":self.padNumber(milli,2), "frame":self.padNumber(frame,2) };

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

        # Track metrics
        track_metric_screen("add-to-timeline-screen")

        # Add custom treeview to window
        self.treeFiles = TimelineTreeView(self)
        self.vboxTreeParent.insertWidget(0, self.treeFiles)

        # Update data in model
        self.treeFiles.timeline_model.update_model(files)

        # Refresh view
        self.treeFiles.refresh_view()

        # Init start position
        self.txtStartTime.setValue(position)

        # Init default image length
        self.txtImageLength.setValue(self.settings.get("default-image-length"))
        self.txtImageLength.valueChanged.connect(self.updateTotal)
        self.cmbTransition.currentIndexChanged.connect(self.updateTotal)
        self.cmbFade.currentIndexChanged.connect(self.updateTotal)
        self.txtFadeLength.valueChanged.connect(self.updateTotal)
        self.txtTransitionLength.valueChanged.connect(self.updateTotal)

        # Find display track number
        all_tracks = get_app().project.get(["layers"])
        display_count = len(all_tracks)
        for track in reversed(sorted(all_tracks, key=itemgetter('number'))):
            # Add to dropdown
            track_name = track.get('label') or _("Track %s") % display_count
            self.cmbTrack.addItem(track_name, track.get('number'))
            display_count -= 1

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

                # split the name into parts (looking for a number)
                suffix_number = None
                name_parts = fileBaseName.split("_")
                if name_parts[-1].isdigit():
                    suffix_number = name_parts[-1]

                # get name of transition
                trans_name = fileBaseName.replace("_", " ").capitalize()

                # replace suffix number with placeholder (if any)
                if suffix_number:
                    trans_name = trans_name.replace(suffix_number, "%s")
                    trans_name = _(trans_name) % suffix_number
                else:
                    trans_name = _(trans_name)

                # Check for thumbnail path (in build-in cache)
                thumb_path = os.path.join(info.IMAGES_PATH, "cache",  "{}.png".format(fileBaseName))

                # Check built-in cache (if not found)
                if not os.path.exists(thumb_path):
                    # Check user folder cache
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

        # Update total
        self.updateTotal()
