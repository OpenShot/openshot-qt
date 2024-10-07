"""
 @file
 @brief This file loads the interactive HTML timeline
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Olivier Girard <eolinwen@gmail.com>

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

import json
import logging
import os
import time
import uuid
from functools import partial
from operator import itemgetter
from random import uniform

import openshot
from PyQt5.QtCore import pyqtSlot, Qt, QCoreApplication, QTimer, pyqtSignal, QPointF
from PyQt5.QtGui import QCursor, QKeySequence
from PyQt5.QtWidgets import QDialog

from classes import info, updates
from classes.app import get_app
from classes.effect_init import effect_options
from classes.logger import log
from classes.query import File, Clip, Transition, Track, Effect
from classes.clipboard import ClipboardManager
from classes.thumbnail import GetThumbPath
from classes.waveform import get_audio_data
from .timeline_backend.enums import (
    MenuFade, MenuRotate, MenuLayout, MenuAlign, MenuAnimate, MenuVolume,
    MenuTransform, MenuTime, MenuCopy, MenuSlice, MenuSplitAudio
)
from .timeline_backend.qwidget import TimelineWidget
from .menu import StyledContextMenu

# Constants used by this file
JS_SCOPE_SELECTOR = "$('body').scope()"
ViewClass = None

# Setup timeline
if info.WEB_BACKEND and info.WEB_BACKEND == "qwidget":
    ViewClass = TimelineWidget
elif info.WEB_BACKEND and info.WEB_BACKEND == "webkit":
    from .timeline_backend.webkit import TimelineWebKitView
    ViewClass = TimelineWebKitView
elif info.WEB_BACKEND and info.WEB_BACKEND == "webengine":
    from .timeline_backend.webengine import TimelineWebEngineView
    ViewClass = TimelineWebEngineView
else:
    try:
        from .timeline_backend.webengine import TimelineWebEngineView as ViewClass
    except ImportError as ex:
        try:
            from .timeline_backend.webkit import TimelineWebKitView as ViewClass
        except ImportError:
            log.error("Import failure loading WebKit backend", exc_info=1)
        finally:
            if not ViewClass:
                raise RuntimeError("Need PyQt5.QtWebEngine (or PyQt5.QtWebView on Win32)") from ex


class TimelineView(updates.UpdateInterface, ViewClass):
    """ A Web(Engine/Kit)View QWidget used to load the Timeline """

    # Path to html file
    html_path = os.path.join(info.PATH, 'timeline', 'index.html')

    # Create signal for adding waveforms to clips
    clipAudioDataReady = pyqtSignal(str, object, str)
    fileAudioDataReady = pyqtSignal(str, object, str)

    def connect_playback(self):
        """Connect playback signals to new experimental qwidget based timeline"""
        if ViewClass == TimelineWidget:
            # Propagate to timeline qwidget
            TimelineWidget.connect_playback(self)

    @pyqtSlot()
    def page_ready(self):
        """Document.Ready event has fired, and is initialized"""
        self.document_is_ready = True

    @pyqtSlot(result=str)
    def get_uuid(self):
        """Get a unique id (used for generating a transaction id for the undo/redo system)"""
        return str(uuid.uuid4())

    @pyqtSlot(result=str)
    def get_thumb_address(self):
        """Return the thumbnail HTTP server address"""
        thumb_server_details = self.window.http_server_thread.server_address
        while not thumb_server_details:
            log.info('No HTTP thumbnail server found yet... keep waiting...')
            time.sleep(0.25)
            thumb_server_details = self.window.http_server_thread.server_address

        thumb_address = "http://%s:%s/thumbnails/" % (thumb_server_details[0], thumb_server_details[1])
        return thumb_address

    # This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface)
    def changed(self, action):
        if ViewClass == TimelineWidget:
            # Propagate to timeline qwidget
            TimelineWidget.changed(self, action)

        try:
            # Duplicate UpdateAction, and remove unused action attribute (old_values)
            action = action.copy()
            action.old_values = {}
        except:
            log.error("Error duplicating UpdateAction", exc_info=1)
            return

        # Bail out if change unrelated to webview
        if action and len(action.key) >= 1 and action.key[0] not in ["clips", "effects", "duration", "layers", "markers"]:
            log.debug(f"Skipping unneeded webview update for '{action.key[0]}'")
            return

        # Send a JSON version of the UpdateAction to the timeline webview method: applyJsonDiff()
        if action.type == "load":
            # Set thumbnail server
            self.run_js(JS_SCOPE_SELECTOR + ".setThumbAddress('" + self.get_thumb_address() + "');")

            _ = get_app()._tr
            # Initialize translated track name
            self.run_js(JS_SCOPE_SELECTOR + ".setTrackLabel('" + _("Track %s") + "');")

            # Load entire project data
            self.run_js(JS_SCOPE_SELECTOR + ".loadJson(" + action.json() + ");")

        elif action.key[0] != "files":
            # Apply diff to part of project data
            self.run_js(JS_SCOPE_SELECTOR + ".applyJsonDiff([" + action.json() + "]);")

        # Reset the scale when loading new JSON
        if action.type == "load":
            # Set the scale again (to project setting)
            initial_scale = float(get_app().project.get("scale") or 15.0)
            self.window.sliderZoomWidget.setZoomFactor(initial_scale)

    def delete_invalid_timeline_item(self, item):
        """Delete an invalid timeline item (clip or transitions) if the basic
           data does not make sense - i.e. negative duration"""
        # Verify integrity of basic data
        if item.data["position"] < 0.0:
            item.data["position"] = 0.0
        if item.data["start"] < 0.0:
            item.data["start"] = 0.0
        if item.data["end"] < item.data["start"]:
            item.data["end"] = item.data["start"]
        if item.data["end"] - item.data["start"] <= 0.0:
            log.warning("Negative or zero duration is not possible, so deleting item instead: item_id: %s" % item.id)
            get_app().window.clearSelections()
            item.delete()
            return True
        return False

    @pyqtSlot(str, bool, bool, bool, str)
    def update_clip_data(self, clip_json, only_basic_props=True,
                         ignore_reader=False, ignore_refresh=False, transaction_id=None):
        """ Javascript callable function to update the project data when a clip changes.
        Create an updateAction and send it to the update manager.
        Transaction ID is for undo/redo grouping (if any) """

        # read clip json
        try:
            if not isinstance(clip_json, dict):
                clip_data = json.loads(clip_json)
            else:
                clip_data = clip_json
        except Exception:
            # Failed to parse json, do nothing
            log.warning('Failed to parse clip JSON data', exc_info=1)
            return

        # Search for matching clip in project data (if any)
        existing_clip = Clip.get(id=clip_data.get("id"))
        if not existing_clip:
            # Create a new clip (if not exists)
            log.debug("Create new clip object from clip_data: %s" % clip_data)
            existing_clip = Clip()

        # Update clip data
        existing_clip.data = clip_data

        # Remove unneeded properties (since they don't change here... this is a performance boost)
        if only_basic_props:
            existing_clip.data = {}
            existing_clip.data["id"] = clip_data["id"]
            existing_clip.data["layer"] = clip_data["layer"]
            existing_clip.data["position"] = clip_data["position"]
            existing_clip.data["start"] = clip_data["start"]
            existing_clip.data["end"] = clip_data["end"]

        # Delete invalid items (i.e. negative duration)
        if self.delete_invalid_timeline_item(existing_clip):
            return

        # Always remove the Reader attribute (since nothing updates it,
        # and we are wrapping clips in FrameMappers anyway)
        if ignore_reader and "reader" in existing_clip.data:
            existing_clip.data.pop("reader")

        # Set transaction id (if any)
        if transaction_id:
            get_app().updates.transaction_id = transaction_id

        # Save clip
        existing_clip.save()

        if transaction_id:
            get_app().updates.transaction_id = None

        # Notify UI to ignore OR not ignore updates
        self.window.IgnoreUpdates.emit(ignore_refresh)

    # Add missing transition
    @pyqtSlot(str)
    def add_missing_transition(self, transition_json):
        if not get_app().get_settings().get("automatic_transitions"):
            log.debug("Skipping auto transition (disabled in settings)")
            return

        transition_details = json.loads(transition_json)

        # Get FPS from project
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])

        # Open up QtImageReader for transition Image
        transition_reader = openshot.QtImageReader(
            os.path.join(info.PATH, "transitions", "common", "fade.svg"))

        # Generate transition object
        transition_object = openshot.Mask()

        # Set brightness and contrast, to correctly transition for overlapping clips
        brightness = transition_object.brightness
        brightness.AddPoint(1, 1.0, openshot.BEZIER)
        brightness.AddPoint(round(transition_details["end"] * fps_float) + 1, -1.0, openshot.BEZIER)
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
    @pyqtSlot(str, bool, bool, str)
    def update_transition_data(self, transition_json, only_basic_props=True, ignore_refresh=False, transaction_id=None):
        """ Create an updateAction and send it to the update manager.
            Transaction ID is for undo/redo grouping (if any) """

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
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        duration = existing_item.data["end"] - existing_item.data["start"]
        position = transition_data["position"]
        layer = transition_data["layer"]

        # Determine if transition is intersecting a clip
        # For example, the left side of a clip, or the right side, so we can determine
        # which direction the wipe should be moving in
        is_forward_direction = True
        diff_from_edge = 9999
        for intersecting_clip in Clip.filter(intersect=position, layer=layer):
            diff_from_start = abs(intersecting_clip.data.get("position", 0.0) - position)
            diff_from_end = abs((intersecting_clip.data.get("position", 0.0) + \
                                (intersecting_clip.data.get("end", 0.0) - intersecting_clip.data.get("start", 0.0))) \
                                - position)
            if diff_from_end <= 0.25:
                # Ignore when a transition is less than 1/2 second from the right edge of a clip
                continue
            smallest_diff = min(diff_from_start, diff_from_end)
            if smallest_diff < diff_from_edge:
                diff_from_edge = smallest_diff
                if diff_from_end < diff_from_start:
                    is_forward_direction = False
                else:
                    is_forward_direction = True
            log.debug(f'Intersecting Clip: pos:{intersecting_clip.data.get("position")}, '
                      f'from start: {diff_from_start}, from end: {diff_from_end}, '
                      f'is forward: {is_forward_direction}')
        log.debug(f"Is transition moving in a forward direction? {is_forward_direction}")

        # Determine existing brightness and contrast ranges (if any)
        brightness_range = []
        contrast_range = []
        if existing_item:
            for point in existing_item.data["brightness"].get("Points", []):
                point_value = float(point["co"]["Y"])
                brightness_range.append(point_value)
            for point in existing_item.data["contrast"].get("Points", []):
                point_value = float(point["co"]["Y"])
                contrast_range.append(point_value)
        if not brightness_range:
            brightness_range.extend([1, -1])
        if not contrast_range:
            contrast_range.extend([3])

        # Create new brightness Keyframes (using the previous value range)
        b = openshot.Keyframe()
        if is_forward_direction:
            b.AddPoint(1, sorted(brightness_range)[-1], openshot.BEZIER)
            b.AddPoint(round(duration * fps_float), sorted(brightness_range)[0], openshot.BEZIER)
        else:
            b.AddPoint(1, sorted(brightness_range)[0], openshot.BEZIER)
            b.AddPoint(round(duration * fps_float), sorted(brightness_range)[-1], openshot.BEZIER)
        brightness = json.loads(b.Json())

        # Create new contrast Keyframes (using the previous value range)
        c = openshot.Keyframe()
        if is_forward_direction:
            c.AddPoint(1, sorted(contrast_range)[-1], openshot.BEZIER)
            c.AddPoint(round(duration * fps_float), sorted(contrast_range)[0], openshot.BEZIER)
        else:
            c.AddPoint(1, sorted(contrast_range)[0], openshot.BEZIER)
            c.AddPoint(round(duration * fps_float), sorted(contrast_range)[-1], openshot.BEZIER)
        contrast = json.loads(c.Json())

        # Only include the basic properties (performance boost)
        if only_basic_props:
            existing_item.data = {}
            existing_item.data["id"] = transition_data["id"]
            existing_item.data["layer"] = transition_data["layer"]
            existing_item.data["position"] = transition_data["position"]
            existing_item.data["start"] = transition_data["start"]
            existing_item.data["end"] = transition_data["end"]
            existing_item.data["brightness"] = brightness
            existing_item.data["contrast"] = contrast

        # Delete invalid items (i.e. negative duration)
        if self.delete_invalid_timeline_item(existing_item):
            return

        # Set transaction id (if any)
        if transaction_id:
            get_app().updates.transaction_id = transaction_id

        # Save transition
        existing_item.save()

        if transaction_id:
            get_app().updates.transaction_id = None

        # Notify UI to ignore OR not ignore updates
        self.window.IgnoreUpdates.emit(ignore_refresh)

    # Prevent default context menu, and ignore, so that javascript can intercept
    def contextMenuEvent(self, event):
        event.ignore()

    # Javascript callable function to show clip or transition content menus, passing in type to show
    @pyqtSlot(float)
    def ShowPlayheadMenu(self, position=None):
        log.debug('ShowPlayheadMenu: %s' % position)

        # Get translation method
        _ = get_app()._tr

        # Get list of intercepting clips with position (if any)
        intersecting_clips = Clip.filter(intersect=position)
        intersecting_trans = Transition.filter(intersect=position)

        menu = StyledContextMenu(parent=self)
        if intersecting_clips or intersecting_trans:
            # Get list of clip ids
            clip_ids = [c.id for c in intersecting_clips]
            trans_ids = [t.id for t in intersecting_trans]

            # Add split clip menu
            Slice_Menu = StyledContextMenu(title=_("Slice All"), parent=self)
            Slice_Keep_Both = Slice_Menu.addAction(_("Keep Both Sides"))
            Slice_Keep_Both.setShortcuts(self.window.getShortcutByName("sliceAllKeepBothSides"))
            Slice_Keep_Both.triggered.connect(partial(
                self.Slice_Triggered, MenuSlice.KEEP_BOTH, clip_ids, trans_ids, position))
            Slice_Keep_Left = Slice_Menu.addAction(_("Keep Left Side"))
            Slice_Keep_Left.setShortcuts(self.window.getShortcutByName("sliceAllKeepLeftSide"))
            Slice_Keep_Left.triggered.connect(partial(
                self.Slice_Triggered, MenuSlice.KEEP_LEFT, clip_ids, trans_ids, position))
            Slice_Keep_Right = Slice_Menu.addAction(_("Keep Right Side"))
            Slice_Keep_Right.setShortcuts(self.window.getShortcutByName("sliceAllKeepRightSide"))
            Slice_Keep_Right.triggered.connect(partial(
                self.Slice_Triggered, MenuSlice.KEEP_RIGHT, clip_ids, trans_ids, position))
            menu.addMenu(Slice_Menu)

            # Add clear cache menu
            Cache_Menu = StyledContextMenu(title=_("Cache"), parent=self)
            Cache_Menu.addAction(self.window.actionClearAllCache)
            menu.addMenu(Cache_Menu)

            # Show context menu
            self.context_menu_cursor_position = QCursor.pos()
            return menu.popup(self.context_menu_cursor_position)

    @pyqtSlot(str)
    def ShowEffectMenu(self, effect_id=None):
        log.debug('ShowEffectMenu: %s' % effect_id)

        # Get translation method
        _ = get_app()._tr

        menu = StyledContextMenu(parent=self)

        # Only a single clip is selected (Show normal copy menus)
        Copy_Menu = StyledContextMenu(title=_("Copy"), parent=self)
        Copy_Effect = Copy_Menu.addAction(_("Effect"))
        Copy_Effect.setShortcuts(self.window.getShortcutByName("copyAll"))
        Copy_Effect.triggered.connect(partial(self.Copy_Triggered, MenuCopy.EFFECT, [], [], [effect_id]))
        menu.addMenu(Copy_Menu)

        # Properties
        menu.addAction(self.window.actionProperties)

        # Remove Effect Menu
        menu.addSeparator()
        menu.addAction(self.window.actionRemoveEffect)

        # Show context menu
        self.context_menu_cursor_position = QCursor.pos()
        return menu.popup(self.context_menu_cursor_position)

    @pyqtSlot(float, int)
    def ShowTimelineMenu(self, position, layer_number):
        log.debug('ShowTimelineMenu: position: %s, layer: %s' % (position, layer_number))

        # Get translation method
        _ = get_app()._tr

        # Initialize variables to track the found gap
        found_start = 0.0
        found_end = float('inf')
        found_gap = False

        # Get clipboard
        copied_object = ClipboardManager.from_mime(get_app().clipboard().mimeData())
        if copied_object:
            print(f"Copied object found: {type(copied_object).__name__}")

        # Determine if clipboard has FULL clip or transition data (or a list of multiple objects)
        has_clipboard = False
        if copied_object and isinstance(copied_object, Clip) and len(copied_object.data.keys()) > 20:
            has_clipboard = True
        elif copied_object and isinstance(copied_object, Transition) and len(copied_object.data.keys()) > 10:
            has_clipboard = True
        elif copied_object and isinstance(copied_object, list):
            has_clipboard = True

        # Combine and sort the clips and transitions by their position
        clips_and_transitions = sorted(
            Clip.filter(layer=layer_number) + Transition.filter(layer=layer_number),
            key=lambda c: c.data.get("position", 0.0)
        )

        # Loop through the combined and sorted list
        for clip in clips_and_transitions:
            left_edge = clip.data.get("position", 0.0)
            right_edge = left_edge + (clip.data.get("end", 0.0) - clip.data.get("start", 0.0))

            # Check if the current clip starts after the found_end, indicating a gap
            if left_edge > found_start and left_edge > position:
                found_end = left_edge
                found_gap = True
                break  # Found the first gap after the given position

            # Update the found_start to the end of the current clip
            found_start = max(found_start, right_edge)

        # Don't show context menu
        if not has_clipboard and not found_gap:
            return

        # Get track object (ignore locked tracks)
        track = Track.get(number=layer_number)
        if not track:
            return
        locked = track.data.get("lock", False)
        if locked:
            return

        # New context menu
        menu = StyledContextMenu(parent=self)

        if found_gap:
            # Add 'Remove Gap' Menu
            menu.addAction(self.window.actionRemoveGap)
            try:
                # Disconnect any previous connections
                self.window.actionRemoveGap.triggered.disconnect()
            except TypeError:
                pass  # No previous connections
            self.window.actionRemoveGap.triggered.connect(
                partial(self.RemoveGap_Triggered, found_start, found_end, int(layer_number))
            )
        if has_clipboard and found_gap:
            menu.addSeparator()
        if has_clipboard:
            # Add 'Paste' Menu
            Paste_Clip = menu.addAction(_("Paste"))
            Paste_Clip.setShortcuts(self.window.getShortcutByName("pasteAll"))
            Paste_Clip.triggered.connect(
                partial(self.Paste_Triggered, MenuCopy.PASTE, [], [])
            )

        # Show context menu
        self.context_menu_cursor_position = QCursor.pos()
        return menu.popup(self.context_menu_cursor_position)

    @pyqtSlot(str)
    def ShowClipMenu(self, clip_id=None):
        log.debug('ShowClipMenu: %s' % clip_id)

        # Get translation method
        _ = get_app()._tr

        # Get existing clip object
        clip = Clip.get(id=clip_id)
        if not clip:
            # Not a valid clip id
            return

        # Get list of selected clips
        clip_ids = self.window.selected_clips
        tran_ids = self.window.selected_transitions

        # Get framerate
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])

        # Get playhead position
        playhead_position = float(self.window.preview_thread.current_frame) / fps_float

        # Get clipboard
        copied_object = ClipboardManager.from_mime(get_app().clipboard().mimeData())
        if copied_object:
            print(f"Copied object found: {type(copied_object).__name__}")
        has_clipboard = False
        if copied_object and isinstance(copied_object, Clip):
            has_clipboard = True
        elif copied_object and isinstance(copied_object, Effect):
            has_clipboard = True

        # Create blank context menu
        menu = StyledContextMenu(parent=self)

        # Copy Menu
        if len(tran_ids) + len(clip_ids) > 1:
            # Show Copy All menu (clips and transitions are selected)
            Copy_All = menu.addAction(_("Copy"))
            Copy_All.setShortcuts(self.window.getShortcutByName("copyAll"))
            Copy_All.triggered.connect(self.window.copyAll)
            # Show Cut All menu
            Cut_All = menu.addAction(_("Cut"))
            Cut_All.setShortcuts(self.window.getShortcutByName("cutAll"))
            Cut_All.triggered.connect(self.window.cutAll)
        else:
            # Only a single clip is selected (Show normal copy menus)
            Copy_Menu = StyledContextMenu(title=_("Copy"), parent=self)
            Copy_Clip = Copy_Menu.addAction(_("Clip"))
            Copy_Clip.setShortcuts(self.window.getShortcutByName("copyAll"))
            Copy_Clip.triggered.connect(partial(self.Copy_Triggered, MenuCopy.CLIP, [clip_id], [], []))

            Keyframe_Menu = StyledContextMenu(title=_("Keyframes"), parent=self)
            Copy_Keyframes_All = Keyframe_Menu.addAction(_("All"))
            Copy_Keyframes_All.triggered.connect(partial(
                self.Copy_Triggered, MenuCopy.KEYFRAMES_ALL, [clip_id], [], []))
            Keyframe_Menu.addSeparator()
            Copy_Keyframes_Alpha = Keyframe_Menu.addAction(_("Alpha"))
            Copy_Keyframes_Alpha.triggered.connect(partial(
                self.Copy_Triggered, MenuCopy.KEYFRAMES_ALPHA, [clip_id], [], []))
            Copy_Keyframes_Scale = Keyframe_Menu.addAction(_("Scale"))
            Copy_Keyframes_Scale.triggered.connect(partial(
                self.Copy_Triggered, MenuCopy.KEYFRAMES_SCALE, [clip_id], [], []))
            Copy_Keyframes_Shear = Keyframe_Menu.addAction(_("Shear"))
            Copy_Keyframes_Shear.triggered.connect(partial(
                self.Copy_Triggered, MenuCopy.KEYFRAMES_SHEAR, [clip_id], [], []))
            Copy_Keyframes_Rotate = Keyframe_Menu.addAction(_("Rotation"))
            Copy_Keyframes_Rotate.triggered.connect(partial(
                self.Copy_Triggered, MenuCopy.KEYFRAMES_ROTATE, [clip_id], [], []))
            Copy_Keyframes_Locate = Keyframe_Menu.addAction(_("Location"))
            Copy_Keyframes_Locate.triggered.connect(partial(
                self.Copy_Triggered, MenuCopy.KEYFRAMES_LOCATION, [clip_id], [], []))
            Copy_Keyframes_Time = Keyframe_Menu.addAction(_("Time"))
            Copy_Keyframes_Time.triggered.connect(partial(
                self.Copy_Triggered, MenuCopy.KEYFRAMES_TIME, [clip_id], [], []))
            Copy_Keyframes_Volume = Keyframe_Menu.addAction(_("Volume"))
            Copy_Keyframes_Volume.triggered.connect(partial(
                self.Copy_Triggered, MenuCopy.KEYFRAMES_VOLUME, [clip_id], [], []))

            # Only add copy->effects and copy->keyframes if 1 clip is selected
            Copy_Effects = Copy_Menu.addAction(_("Effects"))
            Copy_Effects.triggered.connect(partial(
                self.Copy_Triggered, MenuCopy.ALL_EFFECTS, [clip_id], [], []))
            Copy_Menu.addMenu(Keyframe_Menu)
            menu.addMenu(Copy_Menu)

            # Show Cut menu
            Cut_All = menu.addAction(_("Cut"))
            Cut_All.setShortcuts(self.window.getShortcutByName("cutAll"))
            Cut_All.triggered.connect(self.window.cutAll)

        # Determine if the paste menu should be shown (for partial copied clip data)
        if has_clipboard:
            # Paste Menu (Only show if partial clipboard available)
            Paste_Clip = menu.addAction(_("Paste"))
            Paste_Clip.triggered.connect(partial(self.Paste_Triggered, MenuCopy.PASTE, clip_ids, []))

        menu.addSeparator()

        # Alignment Menu (if multiple selections)
        if len(clip_ids) > 1:
            Alignment_Menu = StyledContextMenu(title=_("Align"), parent=self)
            Align_Left = Alignment_Menu.addAction(_("Left"))
            Align_Left.triggered.connect(partial(self.Align_Triggered, MenuAlign.LEFT, clip_ids, tran_ids))
            Align_Right = Alignment_Menu.addAction(_("Right"))
            Align_Right.triggered.connect(partial(self.Align_Triggered, MenuAlign.RIGHT, clip_ids, tran_ids))

            # Add menu to parent
            menu.addMenu(Alignment_Menu)

        # Fade In Menu
        Fade_Menu = StyledContextMenu(title=_("Fade"), parent=self)
        Fade_None = Fade_Menu.addAction(_("No Fade"))
        Fade_None.triggered.connect(partial(self.Fade_Triggered, MenuFade.NONE, clip_ids))
        Fade_Menu.addSeparator()
        for position, position_label in [
            ("Start of Clip", _("Start of Clip")),
            ("End of Clip", _("End of Clip")),
            ("Entire Clip", _("Entire Clip"))
        ]:
            Position_Menu = StyledContextMenu(title=position_label, parent=self)

            if position == "Start of Clip":
                Fade_In_Fast = Position_Menu.addAction(_("Fade In (Fast)"))
                Fade_In_Fast.triggered.connect(partial(
                    self.Fade_Triggered, MenuFade.IN_FAST, clip_ids, position))
                Fade_In_Slow = Position_Menu.addAction(_("Fade In (Slow)"))
                Fade_In_Slow.triggered.connect(partial(
                    self.Fade_Triggered, MenuFade.IN_SLOW, clip_ids, position))

            elif position == "End of Clip":
                Fade_Out_Fast = Position_Menu.addAction(_("Fade Out (Fast)"))
                Fade_Out_Fast.triggered.connect(partial(
                    self.Fade_Triggered, MenuFade.OUT_FAST, clip_ids, position))
                Fade_Out_Slow = Position_Menu.addAction(_("Fade Out (Slow)"))
                Fade_Out_Slow.triggered.connect(partial(
                    self.Fade_Triggered, MenuFade.OUT_SLOW, clip_ids, position))

            else:
                Fade_In_Out_Fast = Position_Menu.addAction(_("Fade In and Out (Fast)"))
                Fade_In_Out_Fast.triggered.connect(partial(
                    self.Fade_Triggered, MenuFade.IN_OUT_FAST, clip_ids, position))
                Fade_In_Out_Slow = Position_Menu.addAction(_("Fade In and Out (Slow)"))
                Fade_In_Out_Slow.triggered.connect(partial(
                    self.Fade_Triggered, MenuFade.IN_OUT_SLOW, clip_ids, position))
                Position_Menu.addSeparator()
                Fade_In_Slow = Position_Menu.addAction(_("Fade In (Entire Clip)"))
                Fade_In_Slow.triggered.connect(partial(
                    self.Fade_Triggered, MenuFade.IN_SLOW, clip_ids, position))
                Fade_Out_Slow = Position_Menu.addAction(_("Fade Out (Entire Clip)"))
                Fade_Out_Slow.triggered.connect(partial(
                    self.Fade_Triggered, MenuFade.OUT_SLOW, clip_ids, position))

            Fade_Menu.addMenu(Position_Menu)
        menu.addMenu(Fade_Menu)

        # Animate Menu
        Animate_Menu = StyledContextMenu(title=_("Animate"), parent=self)
        Animate_None = Animate_Menu.addAction(_("No Animation"))
        Animate_None.triggered.connect(partial(self.Animate_Triggered, MenuAnimate.NONE, clip_ids))
        Animate_Menu.addSeparator()
        for position, position_label in [
            ("Start of Clip", _("Start of Clip")),
            ("End of Clip", _("End of Clip")),
            ("Entire Clip", _("Entire Clip"))
        ]:
            Position_Menu = StyledContextMenu(title=position_label, parent=self)

            # Scale
            Scale_Menu = StyledContextMenu(title=_("Zoom"), parent=self)
            Animate_In_50_100 = Scale_Menu.addAction(_("Zoom In (50% to 100%)"))
            Animate_In_50_100.triggered.connect(partial(
                self.Animate_Triggered, MenuAnimate.IN_50_100, clip_ids, position))
            Animate_In_75_100 = Scale_Menu.addAction(_("Zoom In (75% to 100%)"))
            Animate_In_75_100.triggered.connect(partial(
                self.Animate_Triggered, MenuAnimate.IN_75_100, clip_ids, position))
            Animate_In_100_150 = Scale_Menu.addAction(_("Zoom In (100% to 150%)"))
            Animate_In_100_150.triggered.connect(partial(
                self.Animate_Triggered, MenuAnimate.IN_100_150, clip_ids, position))
            Animate_Out_100_75 = Scale_Menu.addAction(_("Zoom Out (100% to 75%)"))
            Animate_Out_100_75.triggered.connect(partial(
                self.Animate_Triggered, MenuAnimate.OUT_100_75, clip_ids, position))
            Animate_Out_100_50 = Scale_Menu.addAction(_("Zoom Out (100% to 50%)"))
            Animate_Out_100_50.triggered.connect(partial(
                self.Animate_Triggered, MenuAnimate.OUT_100_50, clip_ids, position))
            Animate_Out_150_100 = Scale_Menu.addAction(_("Zoom Out (150% to 100%)"))
            Animate_Out_150_100.triggered.connect(partial(
                self.Animate_Triggered, MenuAnimate.OUT_150_100, clip_ids, position))
            Position_Menu.addMenu(Scale_Menu)

            # Center to Edge
            Center_Edge_Menu = StyledContextMenu(title=_("Center to Edge"), parent=self)
            Animate_Center_Top = Center_Edge_Menu.addAction(_("Center to Top"))
            Animate_Center_Top.triggered.connect(partial(
                self.Animate_Triggered, MenuAnimate.CENTER_TOP, clip_ids, position))
            Animate_Center_Left = Center_Edge_Menu.addAction(_("Center to Left"))
            Animate_Center_Left.triggered.connect(partial(
                self.Animate_Triggered, MenuAnimate.CENTER_LEFT, clip_ids, position))
            Animate_Center_Right = Center_Edge_Menu.addAction(_("Center to Right"))
            Animate_Center_Right.triggered.connect(partial(
                self.Animate_Triggered, MenuAnimate.CENTER_RIGHT, clip_ids, position))
            Animate_Center_Bottom = Center_Edge_Menu.addAction(_("Center to Bottom"))
            Animate_Center_Bottom.triggered.connect(partial(
                self.Animate_Triggered, MenuAnimate.CENTER_BOTTOM, clip_ids, position))
            Position_Menu.addMenu(Center_Edge_Menu)

            # Edge to Center
            Edge_Center_Menu = StyledContextMenu(title=_("Edge to Center"), parent=self)
            Animate_Top_Center = Edge_Center_Menu.addAction(_("Top to Center"))
            Animate_Top_Center.triggered.connect(partial(
                self.Animate_Triggered, MenuAnimate.TOP_CENTER, clip_ids, position))
            Animate_Left_Center = Edge_Center_Menu.addAction(_("Left to Center"))
            Animate_Left_Center.triggered.connect(partial(
                self.Animate_Triggered, MenuAnimate.LEFT_CENTER, clip_ids, position))
            Animate_Right_Center = Edge_Center_Menu.addAction(_("Right to Center"))
            Animate_Right_Center.triggered.connect(partial(
                self.Animate_Triggered, MenuAnimate.RIGHT_CENTER, clip_ids, position))
            Animate_Bottom_Center = Edge_Center_Menu.addAction(_("Bottom to Center"))
            Animate_Bottom_Center.triggered.connect(partial(
                self.Animate_Triggered, MenuAnimate.BOTTOM_CENTER, clip_ids, position))
            Position_Menu.addMenu(Edge_Center_Menu)

            # Edge to Edge
            Edge_Edge_Menu = StyledContextMenu(title=_("Edge to Edge"), parent=self)
            Animate_Top_Bottom = Edge_Edge_Menu.addAction(_("Top to Bottom"))
            Animate_Top_Bottom.triggered.connect(partial(
                self.Animate_Triggered, MenuAnimate.TOP_BOTTOM, clip_ids, position))
            Animate_Left_Right = Edge_Edge_Menu.addAction(_("Left to Right"))
            Animate_Left_Right.triggered.connect(partial(
                self.Animate_Triggered, MenuAnimate.LEFT_RIGHT, clip_ids, position))
            Animate_Right_Left = Edge_Edge_Menu.addAction(_("Right to Left"))
            Animate_Right_Left.triggered.connect(partial(
                self.Animate_Triggered, MenuAnimate.RIGHT_LEFT, clip_ids, position))
            Animate_Bottom_Top = Edge_Edge_Menu.addAction(_("Bottom to Top"))
            Animate_Bottom_Top.triggered.connect(partial(
                self.Animate_Triggered, MenuAnimate.BOTTOM_TOP, clip_ids, position))
            Position_Menu.addMenu(Edge_Edge_Menu)

            # Random Animation
            Position_Menu.addSeparator()
            Random = Position_Menu.addAction(_("Random"))
            Random.triggered.connect(partial(self.Animate_Triggered, MenuAnimate.RANDOM, clip_ids, position))

            # Add Sub-Menu's to Position menu
            Animate_Menu.addMenu(Position_Menu)

        # Add Each position menu
        menu.addMenu(Animate_Menu)

        # Rotate Menu
        Rotation_Menu = StyledContextMenu(title=_("Rotate"), parent=self)
        Rotation_None = Rotation_Menu.addAction(_("No Rotation"))
        Rotation_None.triggered.connect(partial(
            self.Rotate_Triggered, MenuRotate.NONE, clip_ids))
        Rotation_Menu.addSeparator()
        Rotation_90_Right = Rotation_Menu.addAction(_("Rotate 90 (Right)"))
        Rotation_90_Right.triggered.connect(partial(
            self.Rotate_Triggered, MenuRotate.RIGHT_90, clip_ids))
        Rotation_90_Left = Rotation_Menu.addAction(_("Rotate 90 (Left)"))
        Rotation_90_Left.triggered.connect(partial(
            self.Rotate_Triggered, MenuRotate.LEFT_90, clip_ids))
        Rotation_180_Flip = Rotation_Menu.addAction(_("Rotate 180 (Flip)"))
        Rotation_180_Flip.triggered.connect(partial(
            self.Rotate_Triggered, MenuRotate.FLIP_180, clip_ids))
        menu.addMenu(Rotation_Menu)

        # Layout Menu
        Layout_Menu = StyledContextMenu(title=_("Layout"), parent=self)
        Layout_None = Layout_Menu.addAction(_("Reset Layout"))
        Layout_None.triggered.connect(partial(
            self.Layout_Triggered, MenuLayout.NONE, clip_ids))
        Layout_Menu.addSeparator()
        Layout_Center = Layout_Menu.addAction(_("1/4 Size - Center"))
        Layout_Center.triggered.connect(partial(
            self.Layout_Triggered, MenuLayout.CENTER, clip_ids))
        Layout_Top_Left = Layout_Menu.addAction(_("1/4 Size - Top Left"))
        Layout_Top_Left.triggered.connect(partial(
            self.Layout_Triggered, MenuLayout.TOP_LEFT, clip_ids))
        Layout_Top_Right = Layout_Menu.addAction(_("1/4 Size - Top Right"))
        Layout_Top_Right.triggered.connect(partial(
            self.Layout_Triggered, MenuLayout.TOP_RIGHT, clip_ids))
        Layout_Bottom_Left = Layout_Menu.addAction(_("1/4 Size - Bottom Left"))
        Layout_Bottom_Left.triggered.connect(partial(
            self.Layout_Triggered, MenuLayout.BOTTOM_LEFT, clip_ids))
        Layout_Bottom_Right = Layout_Menu.addAction(_("1/4 Size - Bottom Right"))
        Layout_Bottom_Right.triggered.connect(partial(
            self.Layout_Triggered, MenuLayout.BOTTOM_RIGHT, clip_ids))
        Layout_Menu.addSeparator()
        Layout_Bottom_All_With_Aspect = Layout_Menu.addAction(_("Show All (Maintain Ratio)"))
        Layout_Bottom_All_With_Aspect.triggered.connect(partial(
            self.Layout_Triggered, MenuLayout.ALL_WITH_ASPECT, clip_ids))
        Layout_Bottom_All_Without_Aspect = Layout_Menu.addAction(_("Show All (Distort)"))
        Layout_Bottom_All_Without_Aspect.triggered.connect(partial(
            self.Layout_Triggered, MenuLayout.ALL_WITHOUT_ASPECT, clip_ids))
        menu.addMenu(Layout_Menu)

        # Time Menu
        Time_Menu = StyledContextMenu(title=_("Time"), parent=self)
        Time_None = Time_Menu.addAction(_("Reset Time"))
        Time_None.triggered.connect(partial(self.Time_Triggered, MenuTime.NONE, clip_ids, '1X'))
        Time_Menu.addSeparator()
        for speed, speed_values in [
            (_("Normal"), ['1X']),
            (_("Fast"), ['2X', '4X', '8X', '16X']),
            (_("Slow"), ['1/2X', '1/4X', '1/8X', '1/16X'])
        ]:
            Speed_Menu = StyledContextMenu(title=speed, parent=self)

            for direction, direction_value in [
                (_("Forward"), MenuTime.FORWARD),
                (_("Backward"), MenuTime.BACKWARD)
            ]:
                Direction_Menu = StyledContextMenu(title=direction, parent=self)

                for actual_speed in speed_values:
                    # Add menu option
                    Time_Option = Direction_Menu.addAction(_(actual_speed))
                    Time_Option.triggered.connect(
                        partial(self.Time_Triggered, direction_value, clip_ids, actual_speed))

                # Add menu to parent
                Speed_Menu.addMenu(Direction_Menu)
            # Add menu to parent
            Time_Menu.addMenu(Speed_Menu)

        # Add Freeze menu options
        Time_Menu.addSeparator()
        for freeze_type, trigger_type in [
            (_("Freeze"), MenuTime.FREEZE),
            (_("Freeze && Zoom"), MenuTime.FREEZE_ZOOM)
        ]:
            Freeze_Menu = StyledContextMenu(title=freeze_type, parent=self)

            for freeze_seconds in [2, 4, 6, 8, 10, 20, 30]:
                # Add menu option
                Time_Option = Freeze_Menu.addAction(_('{} seconds').format(freeze_seconds))
                Time_Option.triggered.connect(
                    partial(self.Time_Triggered, trigger_type, clip_ids, freeze_seconds, playhead_position))

            # Add menu to parent
            Time_Menu.addMenu(Freeze_Menu)

        # Add menu to parent
        menu.addMenu(Time_Menu)

        # Volume Menu
        Volume_Menu = StyledContextMenu(title=_("Volume"), parent=self)
        Volume_None = Volume_Menu.addAction(_("Reset Volume"))
        Volume_None.triggered.connect(partial(self.Volume_Triggered, MenuVolume.NONE, clip_ids))
        Volume_Menu.addSeparator()
        for position, position_label in [
            ("Start of Clip", _("Start of Clip")),
            ("End of Clip", _("End of Clip")),
            ("Entire Clip", _("Entire Clip"))
        ]:
            Position_Menu = StyledContextMenu(title=position_label, parent=self)

            if position == "Start of Clip":
                Fade_In_Fast = Position_Menu.addAction(_("Fade In (Fast)"))
                Fade_In_Fast.triggered.connect(partial(
                    self.Volume_Triggered, MenuVolume.FADE_IN_FAST, clip_ids, position))
                Fade_In_Slow = Position_Menu.addAction(_("Fade In (Slow)"))
                Fade_In_Slow.triggered.connect(partial(
                    self.Volume_Triggered, MenuVolume.FADE_IN_SLOW, clip_ids, position))

            elif position == "End of Clip":
                Fade_Out_Fast = Position_Menu.addAction(_("Fade Out (Fast)"))
                Fade_Out_Fast.triggered.connect(partial(
                    self.Volume_Triggered, MenuVolume.FADE_OUT_FAST, clip_ids, position))
                Fade_Out_Slow = Position_Menu.addAction(_("Fade Out (Slow)"))
                Fade_Out_Slow.triggered.connect(partial(
                    self.Volume_Triggered, MenuVolume.FADE_OUT_SLOW, clip_ids, position))

            else:
                Fade_In_Out_Fast = Position_Menu.addAction(_("Fade In and Out (Fast)"))
                Fade_In_Out_Fast.triggered.connect(partial(
                    self.Volume_Triggered, MenuVolume.FADE_IN_OUT_FAST, clip_ids, position))
                Fade_In_Out_Slow = Position_Menu.addAction(_("Fade In and Out (Slow)"))
                Fade_In_Out_Slow.triggered.connect(partial(
                    self.Volume_Triggered, MenuVolume.FADE_IN_OUT_SLOW, clip_ids, position))
                Position_Menu.addSeparator()
                Fade_In_Slow = Position_Menu.addAction(_("Fade In (Entire Clip)"))
                Fade_In_Slow.triggered.connect(partial(
                    self.Volume_Triggered, MenuVolume.FADE_IN_SLOW, clip_ids, position))
                Fade_Out_Slow = Position_Menu.addAction(_("Fade Out (Entire Clip)"))
                Fade_Out_Slow.triggered.connect(partial(
                    self.Volume_Triggered, MenuVolume.FADE_OUT_SLOW, clip_ids, position))

            # Add levels
            Position_Menu.addSeparator()

            # Volume levels menu optinos
            for level in reversed(range(0, 140, 10)):
                action = Position_Menu.addAction(_("Level {level}%").format(level=level))
                action.triggered.connect(partial(self.Volume_Triggered, MenuVolume.LEVEL, clip_ids, position, level))

            Volume_Menu.addMenu(Position_Menu)
        menu.addMenu(Volume_Menu)

        # Add separate audio menu
        Split_Audio_Channels_Menu = StyledContextMenu(title=_("Separate Audio"), parent=self)
        Split_Single_Clip = Split_Audio_Channels_Menu.addAction(_("Single Clip (all channels)"))
        Split_Single_Clip.triggered.connect(partial(
            self.Split_Audio_Triggered, MenuSplitAudio.SINGLE, clip_ids))
        Split_Multiple_Clips = Split_Audio_Channels_Menu.addAction(_("Multiple Clips (each channel)"))
        Split_Multiple_Clips.triggered.connect(partial(
            self.Split_Audio_Triggered, MenuSplitAudio.MULTIPLE, clip_ids))
        menu.addMenu(Split_Audio_Channels_Menu)

        # If Playhead overlapping clip
        if clip:
            start_of_clip = float(clip.data["start"])
            end_of_clip = float(clip.data["end"])
            position_of_clip = float(clip.data["position"])
            if (
                playhead_position >= position_of_clip
                and playhead_position <= (position_of_clip + (end_of_clip - start_of_clip))
            ):
                # Add split clip menu
                Slice_Menu = StyledContextMenu(title=_("Slice"), parent=self)
                Slice_Keep_Both = Slice_Menu.addAction(_("Keep Both Sides"))
                Slice_Keep_Both.triggered.connect(partial(
                    self.Slice_Triggered, MenuSlice.KEEP_BOTH, clip_ids, tran_ids, playhead_position))
                Slice_Keep_Left = Slice_Menu.addAction(_("Keep Left Side"))
                Slice_Keep_Left.triggered.connect(partial(
                    self.Slice_Triggered, MenuSlice.KEEP_LEFT, clip_ids, tran_ids, playhead_position))
                Slice_Keep_Right = Slice_Menu.addAction(_("Keep Right Side"))
                Slice_Keep_Right.triggered.connect(partial(
                    self.Slice_Triggered, MenuSlice.KEEP_RIGHT, clip_ids, tran_ids, playhead_position))

                # Add slice clip menu w/ Ripple
                Slice_Menu.addSeparator()
                Slice_Keep_Left = Slice_Menu.addAction(_("Keep Left Side (Ripple)"))
                Slice_Keep_Left.triggered.connect(partial(
                    self.Slice_Triggered, MenuSlice.KEEP_LEFT, clip_ids, tran_ids, playhead_position, True))
                Slice_Keep_Right = Slice_Menu.addAction(_("Keep Right Side (Ripple)"))
                Slice_Keep_Right.triggered.connect(partial(
                    self.Slice_Triggered, MenuSlice.KEEP_RIGHT, clip_ids, tran_ids, playhead_position, True))

                menu.addMenu(Slice_Menu)

        # Transform menu
        Transform_Action = self.window.actionTransform
        Transform_Action.triggered.connect(
            partial(self.Transform_Triggered, MenuTransform.DEFAULT, clip_ids))
        menu.addAction(Transform_Action)

        # Add clip display menu (waveform or thumbnail)
        menu.addSeparator()
        Waveform_Menu = StyledContextMenu(title=_("Display"), parent=self)
        ShowWaveform = Waveform_Menu.addAction(_("Show Waveform"))
        ShowWaveform.triggered.connect(partial(self.Show_Waveform_Triggered, clip_ids))
        HideWaveform = Waveform_Menu.addAction(_("Show Thumbnail"))
        HideWaveform.triggered.connect(partial(self.Hide_Waveform_Triggered, clip_ids))
        menu.addMenu(Waveform_Menu)

        # Properties
        menu.addAction(self.window.actionProperties)

        # Remove Clip Menu
        menu.addSeparator()
        menu.addAction(self.window.actionRemoveClip)

        # Show context menu
        self.context_menu_cursor_position = QCursor.pos()
        return menu.popup(self.context_menu_cursor_position)

    def Transform_Triggered(self, action, clip_ids):
        log.debug("Transform_Triggered")

        # Emit signal to transform this clip (for the 1st clip id)
        if clip_ids:
            # Transform first clip in list
            self.window.TransformSignal.emit(clip_ids[0])
        else:
            # Clear transform
            self.window.TransformSignal.emit("")

    def Show_Waveform_Triggered(self, clip_ids, transaction_id=None):
        """Show a waveform for all selected clips"""

        # Group clip IDs under each File ID
        # Data format:  { "fileID": ["ClipID-1", "ClipID-2", etc...]}
        files = {}
        for clip_id in clip_ids:
            # Get existing clip object
            clip = Clip.get(id=clip_id)
            file_id = clip.data.get("file_id")

            if file_id not in files:
                files[file_id] = []
            files[file_id].append(clip.data.get("id"))

        # Get audio data for all "selected" files/clips
        get_audio_data(files, transaction_id=transaction_id)

    def Hide_Waveform_Triggered(self, clip_ids):
        """Hide the waveform for the selected clip"""

        # Loop through each selected clip ID
        for clip_id in clip_ids:
            # Get existing clip object & clear audio_data
            clip = Clip.get(id=clip_id)
            clip.data = {"ui": {"audio_data": []}}
            clip.save()

    def fileAudioDataReady_Triggered(self, file_id, ui_data, tid):
        log.debug("fileAudioDataReady_Triggered received for file: %s" % file_id)

        # Transaction id to group all deletes together
        get_app().updates.transaction_id = tid

        get_app().window.actionClearWaveformData.setEnabled(True)
        file = File.get(id=file_id)
        if file:
            file.data = ui_data
            file.save()

        # Clear transaction id
        get_app().updates.transaction_id = None

    def clipAudioDataReady_Triggered(self, clip_id, ui_data, tid):
        # When audio data has been calculated, add it to a clip
        log.debug("clipAudioDataReady_Triggered received for clip: %s" % clip_id)

        # Transaction id to group all deletes together
        get_app().updates.transaction_id = tid

        get_app().window.actionClearWaveformData.setEnabled(True)
        clip = Clip.get(id=clip_id)
        if clip:
            clip.data = ui_data
            clip.save()

        # Clear transaction id
        get_app().updates.transaction_id = None

    def Thumbnail_Updated(self, clip_id, thumbnail_frame=1):
        """Callback when thumbnail needs to be updated"""
        clips = Clip.filter(id=clip_id)
        for clip in clips:
            # Force thumbnail image to be refreshed (for a particular frame #)
            GetThumbPath(clip.data.get("file_id"), thumbnail_frame, clear_cache=True)

            # Pass to javascript timeline (and render)
            self.run_js(JS_SCOPE_SELECTOR + ".updateThumbnail('" + clip_id + "');")

    def Split_Audio_Triggered(self, action, clip_ids):
        """Callback for split audio context menus"""
        log.debug("Split_Audio_Triggered")

        # Get translation method
        _ = get_app()._tr

        # Group transactions
        tid = self.get_uuid()
        get_app().updates.transaction_id = tid

        # Loop through each selected clip
        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)
            if not clip:
                # Invalid clip, skip to next item
                continue

            # Get # of tracks
            all_tracks = get_app().project.get("layers")

            # Clear audio override
            p = openshot.Point(1, -1.0, openshot.CONSTANT)  # Override has_audio keyframe to False
            p_object = json.loads(p.Json())
            clip.data["has_audio"] = {"Points": [p_object]}

            # Remove the ID property from the clip (so it becomes a new one)
            clip.id = None
            clip.type = 'insert'
            clip.data.pop('id')
            clip.key.pop(1)

            # Get title of clip
            clip_title = clip.data["title"]

            if action == MenuSplitAudio.SINGLE:
                # Clear channel filter on new clip
                p = openshot.Point(1, -1.0, openshot.CONSTANT)
                p_object = json.loads(p.Json())
                clip.data["channel_filter"] = {"Points": [p_object]}

                # Filter out video on the new clip
                p = openshot.Point(1, 0.0, openshot.CONSTANT)  # Override has_video keyframe to False
                p_object = json.loads(p.Json())
                clip.data["has_video"] = {"Points": [p_object]}
                # Also set scale to None
                # Workaround for https://github.com/OpenShot/openshot-qt/issues/2882
                clip.data["scale"] = openshot.SCALE_NONE

                # Get track below selected track (if any)
                next_track_number = clip.data['layer']
                found_track = False
                for track in reversed(sorted(all_tracks, key=itemgetter('number'))):
                    if found_track:
                        next_track_number = track.get("number")
                        break
                    if track.get("number") == clip.data['layer']:
                        found_track = True
                        continue

                # Adjust the layer, so this new audio clip doesn't overlap the parent
                clip.data['layer'] = next_track_number  # Add to layer below clip

                # Adjust the clip title
                channel_label = _("(all channels)")
                clip.data["title"] = clip_title + " " + channel_label
                # Save changes
                clip.save()

                # Generate waveform for new clip
                log.info("Generate waveform for split audio track clip id: %s" % clip.id)
                self.Show_Waveform_Triggered([clip.id], transaction_id=tid)

            if action == MenuSplitAudio.MULTIPLE:
                # Get # of channels on clip
                channels = int(clip.data["reader"]["channels"])

                # Loop through each channel
                separate_clip_ids = []
                for channel in range(0, channels):
                    log.debug("Adding clip for channel %s" % channel)

                    # Each clip is filtered to a different channel
                    p = openshot.Point(1, channel, openshot.CONSTANT)
                    p_object = json.loads(p.Json())
                    clip.data["channel_filter"] = {"Points": [p_object]}

                    # Filter out video on the new clip
                    p = openshot.Point(1, 0.0, openshot.CONSTANT)  # Override has_video keyframe to False
                    p_object = json.loads(p.Json())
                    clip.data["has_video"] = {"Points": [p_object]}
                    # Also set scale to None
                    # Workaround for https://github.com/OpenShot/openshot-qt/issues/2882
                    clip.data["scale"] = openshot.SCALE_NONE

                    # Get track below selected track (if any)
                    next_track_number = clip.data['layer']
                    found_track = False
                    for track in reversed(sorted(all_tracks, key=itemgetter('number'))):
                        if found_track:
                            next_track_number = track.get("number")
                            break
                        if track.get("number") == clip.data['layer']:
                            found_track = True
                            continue

                    # Adjust the layer, so this new audio clip doesn't overlap the parent
                    clip.data['layer'] = max(next_track_number, 0)  # Add to layer below clip

                    # Adjust the clip title
                    channel_label = _("(channel %s)") % (channel + 1)
                    clip.data["title"] = clip_title + " " + channel_label

                    # Save changes
                    clip.save()
                    separate_clip_ids.append(clip.id)

                    # Remove the ID property from the clip (so next time, it will create a new clip)
                    clip.id = None
                    clip.type = 'insert'
                    clip.data.pop('id')

                # Generate waveform for new clip
                log.info("Generate waveform for split audio track clip ids: %s" % str(separate_clip_ids))
                self.Show_Waveform_Triggered(separate_clip_ids, transaction_id=tid)

        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)
            if not clip:
                # Invalid clip, skip to next item
                continue

            # Filter out audio on the original clip
            p = openshot.Point(1, 0.0, openshot.CONSTANT)  # Override has_audio keyframe to False
            p_object = json.loads(p.Json())
            clip.data["has_audio"] = {"Points": [p_object]}

            # Save filter on original clip
            self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)
            clip.save()

        # Clear transaction
        get_app().updates.transaction_id = None

    def Layout_Triggered(self, action, clip_ids):
        """Callback for the layout context menus"""
        log.debug(action)

        # Loop through each selected clip
        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)
            if not clip:
                # Invalid clip, skip to next item
                continue

            new_gravity = openshot.GRAVITY_CENTER
            if action == MenuLayout.CENTER:
                new_gravity = openshot.GRAVITY_CENTER
            if action == MenuLayout.TOP_LEFT:
                new_gravity = openshot.GRAVITY_TOP_LEFT
            elif action == MenuLayout.TOP_RIGHT:
                new_gravity = openshot.GRAVITY_TOP_RIGHT
            elif action == MenuLayout.BOTTOM_LEFT:
                new_gravity = openshot.GRAVITY_BOTTOM_LEFT
            elif action == MenuLayout.BOTTOM_RIGHT:
                new_gravity = openshot.GRAVITY_BOTTOM_RIGHT

            if action == MenuLayout.NONE:
                # Reset scale mode
                clip.data["scale"] = openshot.SCALE_FIT
                clip.data["gravity"] = openshot.GRAVITY_CENTER

                # Clear scale keyframes
                p = openshot.Point(1, 1.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data["scale_x"] = {"Points": [p_object]}
                clip.data["scale_y"] = {"Points": [p_object]}

                # Clear location keyframes
                p = openshot.Point(1, 0.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data["location_x"] = {"Points": [p_object]}
                clip.data["location_y"] = {"Points": [p_object]}

            if action in [MenuLayout.CENTER,
                          MenuLayout.TOP_LEFT,
                          MenuLayout.TOP_RIGHT,
                          MenuLayout.BOTTOM_LEFT,
                          MenuLayout.BOTTOM_RIGHT]:
                # Reset scale mode
                clip.data["scale"] = openshot.SCALE_FIT
                clip.data["gravity"] = new_gravity

                # Add scale keyframes
                p = openshot.Point(1, 0.5, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data["scale_x"] = {"Points": [p_object]}
                clip.data["scale_y"] = {"Points": [p_object]}

                # Add location keyframes
                p = openshot.Point(1, 0.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data["location_x"] = {"Points": [p_object]}
                clip.data["location_y"] = {"Points": [p_object]}

            if action == MenuLayout.ALL_WITH_ASPECT:
                # Update all intersecting clips
                self.show_all_clips(clip, False)

            elif action == MenuLayout.ALL_WITHOUT_ASPECT:
                # Update all intersecting clips
                self.show_all_clips(clip, True)

            else:
                # Save changes
                self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)

    def Animate_Triggered(self, action, clip_ids, position="Entire Clip"):
        """Callback for the animate context menus"""
        log.debug(action)

        # Loop through each selected clip
        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)
            if not clip:
                # Invalid clip, skip to next item
                continue

            # Get framerate
            fps = get_app().project.get("fps")
            fps_float = float(fps["num"]) / float(fps["den"])

            # Get existing clip object
            start_of_clip = round(float(clip.data["start"]) * fps_float) + 1
            end_of_clip = round(float(clip.data["end"]) * fps_float) + 1

            # Determine the beginning and ending of this animation
            # ["Start of Clip", "End of Clip", "Entire Clip"]
            start_animation = start_of_clip
            end_animation = end_of_clip
            if position == "Start of Clip":
                start_animation = start_of_clip
                end_animation = min(start_of_clip + (1.0 * fps_float), end_of_clip)
            elif position == "End of Clip":
                start_animation = max(1.0, end_of_clip - (1.0 * fps_float))
                end_animation = end_of_clip

            if action == MenuAnimate.NONE:
                # Clear all keyframes
                default_zoom = openshot.Point(start_animation, 1.0, openshot.BEZIER)
                default_zoom_object = json.loads(default_zoom.Json())
                default_loc = openshot.Point(start_animation, 0.0, openshot.BEZIER)
                default_loc_object = json.loads(default_loc.Json())
                clip.data["gravity"] = openshot.GRAVITY_CENTER
                clip.data["scale_x"] = {"Points": [default_zoom_object]}
                clip.data["scale_y"] = {"Points": [default_zoom_object]}
                clip.data["location_x"] = {"Points": [default_loc_object]}
                clip.data["location_y"] = {"Points": [default_loc_object]}

            if action in [
                MenuAnimate.IN_50_100,
                MenuAnimate.IN_75_100,
                MenuAnimate.IN_100_150,
                MenuAnimate.OUT_100_75,
                MenuAnimate.OUT_100_50,
                MenuAnimate.OUT_150_100
            ]:
                # Scale animation
                start_scale = 1.0
                end_scale = 1.0
                if action == MenuAnimate.IN_50_100:
                    start_scale = 0.5
                elif action == MenuAnimate.IN_75_100:
                    start_scale = 0.75
                elif action == MenuAnimate.IN_100_150:
                    end_scale = 1.5
                elif action == MenuAnimate.OUT_100_75:
                    end_scale = 0.75
                elif action == MenuAnimate.OUT_100_50:
                    end_scale = 0.5
                elif action == MenuAnimate.OUT_150_100:
                    start_scale = 1.5

                # Add keyframes
                start = openshot.Point(start_animation, start_scale, openshot.BEZIER)
                start_object = json.loads(start.Json())
                end = openshot.Point(end_animation, end_scale, openshot.BEZIER)
                end_object = json.loads(end.Json())
                clip.data["gravity"] = openshot.GRAVITY_CENTER
                self.AddPoint(clip.data["scale_x"], start_object)
                self.AddPoint(clip.data["scale_x"], end_object)
                self.AddPoint(clip.data["scale_y"], start_object)
                self.AddPoint(clip.data["scale_y"], end_object)

            if action in [
                MenuAnimate.CENTER_TOP,
                MenuAnimate.CENTER_LEFT,
                MenuAnimate.CENTER_RIGHT,
                MenuAnimate.CENTER_BOTTOM,
                MenuAnimate.TOP_CENTER,
                MenuAnimate.LEFT_CENTER,
                MenuAnimate.RIGHT_CENTER,
                MenuAnimate.BOTTOM_CENTER,
                MenuAnimate.TOP_BOTTOM,
                MenuAnimate.LEFT_RIGHT,
                MenuAnimate.RIGHT_LEFT,
                MenuAnimate.BOTTOM_TOP
            ]:
                # Location animation
                animate_start_x = 0.0
                animate_end_x = 0.0
                animate_start_y = 0.0
                animate_end_y = 0.0
                # Center to edge...
                if action == MenuAnimate.CENTER_TOP:
                    animate_end_y = -1.0
                elif action == MenuAnimate.CENTER_LEFT:
                    animate_end_x = -1.0
                elif action == MenuAnimate.CENTER_RIGHT:
                    animate_end_x = 1.0
                elif action == MenuAnimate.CENTER_BOTTOM:
                    animate_end_y = 1.0

                # Edge to Center
                elif action == MenuAnimate.TOP_CENTER:
                    animate_start_y = -1.0
                elif action == MenuAnimate.LEFT_CENTER:
                    animate_start_x = -1.0
                elif action == MenuAnimate.RIGHT_CENTER:
                    animate_start_x = 1.0
                elif action == MenuAnimate.BOTTOM_CENTER:
                    animate_start_y = 1.0

                # Edge to Edge
                elif action == MenuAnimate.TOP_BOTTOM:
                    animate_start_y = -1.0
                    animate_end_y = 1.0
                elif action == MenuAnimate.LEFT_RIGHT:
                    animate_start_x = -1.0
                    animate_end_x = 1.0
                elif action == MenuAnimate.RIGHT_LEFT:
                    animate_start_x = 1.0
                    animate_end_x = -1.0
                elif action == MenuAnimate.BOTTOM_TOP:
                    animate_start_y = 1.0
                    animate_end_y = -1.0

                # Add keyframes
                start_x = openshot.Point(start_animation, animate_start_x, openshot.BEZIER)
                start_x_object = json.loads(start_x.Json())
                end_x = openshot.Point(end_animation, animate_end_x, openshot.BEZIER)
                end_x_object = json.loads(end_x.Json())
                start_y = openshot.Point(start_animation, animate_start_y, openshot.BEZIER)
                start_y_object = json.loads(start_y.Json())
                end_y = openshot.Point(end_animation, animate_end_y, openshot.BEZIER)
                end_y_object = json.loads(end_y.Json())
                clip.data["gravity"] = openshot.GRAVITY_CENTER
                self.AddPoint(clip.data["location_x"], start_x_object)
                self.AddPoint(clip.data["location_x"], end_x_object)
                self.AddPoint(clip.data["location_y"], start_y_object)
                self.AddPoint(clip.data["location_y"], end_y_object)

            if action == MenuAnimate.RANDOM:
                # Location animation
                animate_start_x = uniform(-0.5, 0.5)
                animate_end_x = uniform(-0.15, 0.15)
                animate_start_y = uniform(-0.5, 0.5)
                animate_end_y = uniform(-0.15, 0.15)

                # Scale animation
                start_scale = uniform(0.5, 1.5)
                end_scale = uniform(0.85, 1.15)

                # Add keyframes
                start = openshot.Point(start_animation, start_scale, openshot.BEZIER)
                start_object = json.loads(start.Json())
                end = openshot.Point(end_animation, end_scale, openshot.BEZIER)
                end_object = json.loads(end.Json())
                clip.data["gravity"] = openshot.GRAVITY_CENTER
                self.AddPoint(clip.data["scale_x"], start_object)
                self.AddPoint(clip.data["scale_x"], end_object)
                self.AddPoint(clip.data["scale_y"], start_object)
                self.AddPoint(clip.data["scale_y"], end_object)

                # Add keyframes
                start_x = openshot.Point(start_animation, animate_start_x, openshot.BEZIER)
                start_x_object = json.loads(start_x.Json())
                end_x = openshot.Point(end_animation, animate_end_x, openshot.BEZIER)
                end_x_object = json.loads(end_x.Json())
                start_y = openshot.Point(start_animation, animate_start_y, openshot.BEZIER)
                start_y_object = json.loads(start_y.Json())
                end_y = openshot.Point(end_animation, animate_end_y, openshot.BEZIER)
                end_y_object = json.loads(end_y.Json())
                clip.data["gravity"] = openshot.GRAVITY_CENTER
                self.AddPoint(clip.data["location_x"], start_x_object)
                self.AddPoint(clip.data["location_x"], end_x_object)
                self.AddPoint(clip.data["location_y"], start_y_object)
                self.AddPoint(clip.data["location_y"], end_y_object)

            # Save changes
            self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)

    def AddPoint(self, keyframe, new_point):
        """Add a Point to a Keyframe dict. Always remove existing points,
        if any collisions are found"""
        # Get all points that don't match new point coordinate
        cleaned_points = [
            point
            for point in keyframe["Points"]
            if point.get("co", {}).get("X") != new_point.get("co", {}).get("X")
        ]
        cleaned_points.append(new_point)

        # Replace points with new list
        keyframe["Points"] = cleaned_points


    def Copy_Triggered(self, action, clip_ids, tran_ids, effect_ids):
        """Callback for copy context menus"""
        log.debug(action)

        # Loop through selected clip objects
        copied_objects = []
        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)
            if not clip:
                # Invalid clip, skip to next item
                continue

            # Filter data copied (if needed)
            if action == MenuCopy.KEYFRAMES_ALL:
                clip.data = {'alpha': clip.data['alpha'],
                             'gravity': clip.data['gravity'],
                             'scale_x': clip.data['scale_x'],
                             'scale_y': clip.data['scale_y'],
                             'shear_x': clip.data['shear_x'],
                             'shear_y': clip.data['shear_y'],
                             'rotation': clip.data['rotation'],
                             'location_x': clip.data['location_x'],
                             'location_y': clip.data['location_y'],
                             'time': clip.data['time'],
                             'volume': clip.data['volume']}
            elif action == MenuCopy.KEYFRAMES_ALPHA:
                clip.data = {'alpha': clip.data['alpha']}
            elif action == MenuCopy.KEYFRAMES_SCALE:
                clip.data = {'gravity': clip.data['gravity'],
                             'scale_x': clip.data['scale_x'],
                             'scale_y': clip.data['scale_y']}
            elif action == MenuCopy.KEYFRAMES_SHEAR:
                clip.data = {'shear_x': clip.data['shear_x'],
                             'shear_y': clip.data['shear_y']}
            elif action == MenuCopy.KEYFRAMES_ROTATE:
                clip.data = {'gravity': clip.data['gravity'],
                             'rotation': clip.data['rotation']}
            elif action == MenuCopy.KEYFRAMES_LOCATION:
                clip.data = {'gravity': clip.data['gravity'],
                             'location_x': clip.data['location_x'],
                             'location_y': clip.data['location_y']}
            elif action == MenuCopy.KEYFRAMES_TIME:
                clip.data = {'time': clip.data['time']}
            elif action == MenuCopy.KEYFRAMES_VOLUME:
                clip.data = {'volume': clip.data['volume']}
            elif action == MenuCopy.ALL_EFFECTS:
                clip.data = {'effects': clip.data['effects']}

            # Append copied instance
            copied_objects.append(clip)

        # Loop through transition objects
        for tran_id in tran_ids:

            # Get existing transition object
            tran = Transition.get(id=tran_id)
            if not tran:
                # Invalid transition, skip to next item
                continue

            if action == MenuCopy.KEYFRAMES_ALL:
                tran.data = {'brightness': tran.data['brightness'],
                             'contrast': tran.data['contrast']}
            elif action == MenuCopy.KEYFRAMES_BRIGHTNESS:
                tran.data = {'brightness': tran.data['brightness']}
            elif action == MenuCopy.KEYFRAMES_CONTRAST:
                tran.data = {'contrast': tran.data['contrast']}

            # Append copied instance
            copied_objects.append(tran)

        # Loop through transition objects
        for effect_id in effect_ids:

            # Get existing transition object
            effect = Effect.get(id=effect_id)
            if not effect:
                # Invalid transition, skip to next item
                continue

            if action == MenuCopy.EFFECT:
                copied_objects.append(effect)

        # Copy instances to clipboard
        get_app().clipboard().setMimeData(ClipboardManager.to_mime(copied_objects))

    def RemoveGap_Triggered(self, found_start, found_end, layer_number):
        """Callback for removing gap context menus"""
        log.info(f"Removing gap from {found_start} to {found_end} on layer {layer_number}")

        # Start transaction
        tid = str(uuid.uuid4())
        get_app().updates.transaction_id = tid

        gap_size = found_end - found_start
        for clip in Clip.filter(layer=layer_number) + Transition.filter(layer=layer_number):
            if clip.data.get("position", 0.0) > found_start:
                clip.data["position"] -= gap_size
                clip.save()

        # Clear transaction id
        get_app().updates.transaction_id = None

    def RemoveAllGaps_Triggered(self, found_start, layer_number):
        """Callback for removing all gaps on a layer starting from the detected gap"""
        log.info(f"Removing all gaps on layer {layer_number} starting from {found_start}")

        # Start transaction
        tid = str(uuid.uuid4())
        get_app().updates.transaction_id = tid

        # Combine and sort the clips and transitions by their position
        clips_and_transitions = sorted(
            Clip.filter(layer=layer_number) + Transition.filter(layer=layer_number),
            key=lambda c: c.data.get("position", 0.0)
        )

        # Variable to track the end of the last clip/transition
        last_end = found_start

        # List to track modified clips for saving
        modified_clips = []

        # Iterate through the sorted list and remove gaps
        for clip in clips_and_transitions:
            left_edge = clip.data.get("position", 0.0)
            right_edge = left_edge + (clip.data.get("end", 0.0) - clip.data.get("start", 0.0))

            # Check if there is a gap between the end of the last clip/transition and the start of the current one
            if left_edge > last_end:
                gap_size = left_edge - last_end
                clip.data["position"] -= gap_size
                modified_clips.append(clip)
                log.info(f"Removing gap from {last_end} to {left_edge} on layer {layer_number}")
                last_end = right_edge - gap_size
            else:
                last_end = max(last_end, right_edge)

        # Save only the modified clips
        for clip in modified_clips:
            clip.save()

        # Clear transaction id
        get_app().updates.transaction_id = None

    def Paste_Triggered(self, action, clip_ids, tran_ids):
        """Callback for paste context menus"""
        log.debug(action)

        # Get global mouse position
        if self.context_menu_cursor_position:
            global_mouse_pos = self.context_menu_cursor_position
        else:
            global_mouse_pos = QCursor.pos()
        local_mouse_pos = self.mapFromGlobal(global_mouse_pos)

        # Callback function, to actually add the clip object
        def callback(self, clip_ids, tran_ids, callback_data):
            position = callback_data.get('position', 0.0)
            layer_id = callback_data.get('track', 0)

            # Start transaction
            tid = self.get_uuid()
            get_app().updates.transaction_id = tid

            # Get clipboard
            copied_object = ClipboardManager.from_mime(get_app().clipboard().mimeData())
            if not copied_object:
                get_app().updates.transaction_id = None
                return

            # Remove copied ids from targets
            if isinstance(copied_object, Clip):
                clip_ids = [id for id in clip_ids if id != copied_object.id]
            if isinstance(copied_object, Transition):
                tran_ids = [id for id in tran_ids if id != copied_object.id]

            # Adjust positions and layers for lists of objects
            def adjust_positions_and_layers(objects, position, layer_id):
                left_most_position = min(obj.data['position'] for obj in objects)
                top_most_layer = max(obj.data['layer'] for obj in objects)
                position_diff = position - left_most_position
                layer_diff = layer_id - top_most_layer if layer_id != -1 else 0

                for obj in objects:
                    obj.type = 'insert'
                    obj.data.pop('id', None)
                    obj.id = None
                    if 'effects' in obj.data:
                        obj.data['effects'] = [
                            {k: (get_app().project.generate_id() if k == 'id' else v) for k, v in effect.items()}
                            for effect in obj.data['effects']
                        ]
                    obj.data['position'] += position_diff
                    obj.data['layer'] += layer_diff
                    obj.save()

            # Apply clipboard data to target object, merging effects
            def apply_clipboard_data(target_obj, clipboard_data, excluded_keys=None):
                excluded_keys = excluded_keys or []
                for k, v in clipboard_data.items():
                    if k in excluded_keys:
                        continue
                    if k == 'effects' and isinstance(v, list):
                        existing_effects = target_obj.data.setdefault('effects', [])
                        effect_map = {effect['class_name']: effect for effect in existing_effects}

                        for effect in v:
                            effect_type = effect.get('class_name')
                            effect['id'] = get_app().project.generate_id()
                            if effect_type in effect_map:
                                effect_map[effect_type].update(effect)
                            else:
                                existing_effects.append(effect)

                        target_obj.data['effects'] = existing_effects
                    else:
                        target_obj.data[k] = v
                target_obj.save()

            # If a single clip/transition is copied with no target, add to a list (for inserting)
            if len(clip_ids + tran_ids) == 0 and \
                (isinstance(copied_object, Clip) or isinstance(copied_object, Transition)):
                copied_object = [copied_object]

            # Handle list of objects (adjust positions and layers)
            if isinstance(copied_object, list):
                adjust_positions_and_layers(copied_object, position, layer_id)

            # Handle individual objects (Clip, Transition, Effect)
            for clip_id in clip_ids:
                clip = Clip.get(id=clip_id)
                if clip and isinstance(copied_object, Clip):
                    apply_clipboard_data(clip, copied_object.data, excluded_keys=['id', 'position', 'layer', 'start', 'end'])
                if clip and isinstance(copied_object, Effect):
                    apply_clipboard_data(clip, {"effects": [copied_object.data]}, excluded_keys=['id'])

            for tran_id in tran_ids:
                tran = Transition.get(id=tran_id)
                if tran and isinstance(copied_object, Transition):
                    apply_clipboard_data(tran, copied_object.data, excluded_keys=['id', 'position', 'layer', 'start', 'end'])

            # End transaction
            get_app().updates.transaction_id = None

        # Find position from javascript
        self.run_js(JS_SCOPE_SELECTOR + ".getJavaScriptPosition({}, {});"
            .format(local_mouse_pos.x(), local_mouse_pos.y()), partial(callback, self, clip_ids, tran_ids))

    def Nudge_Triggered(self, action, clip_ids, tran_ids):
        """Callback for nudging clips/transitions by a specified number of frames."""
        # Determine the nudge duration in seconds based on the FPS
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        nudge_duration = float(action) / fps_float  # Nudge duration in seconds
        log.debug(f"Nudging by {nudge_duration} seconds")

        # Nudge all selected clips
        for clip_id in clip_ids:
            clip = Clip.get(id=clip_id)
            if not clip:
                continue

            # Apply the nudge and ensure the position doesn't go below 0
            new_position = max(clip.data['position'] + nudge_duration, 0.0)
            clip.data['position'] = new_position
            self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)

        # Nudge all selected transitions
        for tran_id in tran_ids:
            tran = Transition.get(id=tran_id)
            if not tran:
                continue

            # Apply the nudge and ensure the position doesn't go below 0
            new_position = max(tran.data['position'] + nudge_duration, 0.0)
            tran.data['position'] = new_position
            self.update_transition_data(tran.data, only_basic_props=False)

    def Align_Triggered(self, action, clip_ids, tran_ids):
        """Callback for alignment context menus"""
        log.debug(action)

        left_edge = -1.0
        right_edge = -1.0

        # Loop through each selected clip (find furthest left and right edge)
        for clip_id in clip_ids:
            # Get existing clip object
            clip = Clip.get(id=clip_id)
            if not clip:
                # Invalid clip, skip to next item
                continue

            position = float(clip.data["position"])
            start_of_clip = float(clip.data["start"])
            end_of_clip = float(clip.data["end"])

            if position < left_edge or left_edge == -1.0:
                left_edge = position
            if position + (end_of_clip - start_of_clip) > right_edge or right_edge == -1.0:
                right_edge = position + (end_of_clip - start_of_clip)

        # Loop through each selected transition (find furthest left and right edge)
        for tran_id in tran_ids:
            # Get existing transition object
            tran = Transition.get(id=tran_id)
            if not tran:
                # Invalid transition, skip to next item
                continue

            position = float(tran.data["position"])
            start_of_tran = float(tran.data["start"])
            end_of_tran = float(tran.data["end"])

            if position < left_edge or left_edge == -1.0:
                left_edge = position
            if position + (end_of_tran - start_of_tran) > right_edge or right_edge == -1.0:
                right_edge = position + (end_of_tran - start_of_tran)

        # Loop through each selected clip (update position to align clips)
        for clip_id in clip_ids:
            # Get existing clip object
            clip = Clip.get(id=clip_id)
            if not clip:
                # Invalid clip, skip to next item
                continue

            if action == MenuAlign.LEFT:
                clip.data['position'] = left_edge
            elif action == MenuAlign.RIGHT:
                position = float(clip.data["position"])
                start_of_clip = float(clip.data["start"])
                end_of_clip = float(clip.data["end"])
                right_clip_edge = position + (end_of_clip - start_of_clip)

                clip.data['position'] = position + (right_edge - right_clip_edge)

            # Save changes
            self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)

        # Loop through each selected transition (update position to align clips)
        for tran_id in tran_ids:
            # Get existing transition object
            tran = Transition.get(id=tran_id)
            if not tran:
                # Invalid transition, skip to next item
                continue

            if action == MenuAlign.LEFT:
                tran.data['position'] = left_edge
            elif action == MenuAlign.RIGHT:
                position = float(tran.data["position"])
                start_of_tran = float(tran.data["start"])
                end_of_tran = float(tran.data["end"])
                right_tran_edge = position + (end_of_tran - start_of_tran)

                tran.data['position'] = position + (right_edge - right_tran_edge)

            # Save changes
            self.update_transition_data(tran.data, only_basic_props=False)

    def Fade_Triggered(self, action, clip_ids, position="Entire Clip"):
        """Callback for fade context menus"""
        log.debug(action)

        # Get FPS from project
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])

        # Loop through each selected clip
        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)
            if not clip:
                # Invalid clip, skip to next item
                continue

            start_of_clip = round(float(clip.data["start"]) * fps_float) + 1
            end_of_clip = round(float(clip.data["end"]) * fps_float) + 1

            # Determine the beginning and ending of this animation
            # ["Start of Clip", "End of Clip", "Entire Clip"]
            start_animation = start_of_clip
            end_animation = end_of_clip
            if position == "Start of Clip" and action in [MenuFade.IN_FAST, MenuFade.OUT_FAST]:
                start_animation = start_of_clip
                end_animation = min(start_of_clip + (1.0 * fps_float), end_of_clip)
            elif position == "Start of Clip" and action in [MenuFade.IN_SLOW, MenuFade.OUT_SLOW]:
                start_animation = start_of_clip
                end_animation = min(start_of_clip + (3.0 * fps_float), end_of_clip)
            elif position == "End of Clip" and action in [MenuFade.IN_FAST, MenuFade.OUT_FAST]:
                start_animation = max(1.0, end_of_clip - (1.0 * fps_float))
                end_animation = end_of_clip
            elif position == "End of Clip" and action in [MenuFade.IN_SLOW, MenuFade.OUT_SLOW]:
                start_animation = max(1.0, end_of_clip - (3.0 * fps_float))
                end_animation = end_of_clip

            # Fade in and out (special case)
            if position == "Entire Clip" and action == MenuFade.IN_OUT_FAST:
                # Call this method for the start and end of the clip
                self.Fade_Triggered(MenuFade.IN_FAST, clip_ids, "Start of Clip")
                self.Fade_Triggered(MenuFade.OUT_FAST, clip_ids, "End of Clip")
                return
            if position == "Entire Clip" and action == MenuFade.IN_OUT_SLOW:
                # Call this method for the start and end of the clip
                self.Fade_Triggered(MenuFade.IN_SLOW, clip_ids, "Start of Clip")
                self.Fade_Triggered(MenuFade.OUT_SLOW, clip_ids, "End of Clip")
                return

            if action == MenuFade.NONE:
                # Clear all keyframes
                p = openshot.Point(1, 1.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data['alpha'] = {"Points": [p_object]}

            if action in [MenuFade.IN_FAST, MenuFade.IN_SLOW]:
                # Add keyframes
                start = openshot.Point(start_animation, 0.0, openshot.BEZIER)
                start_object = json.loads(start.Json())
                end = openshot.Point(end_animation, 1.0, openshot.BEZIER)
                end_object = json.loads(end.Json())
                self.AddPoint(clip.data['alpha'], start_object)
                self.AddPoint(clip.data['alpha'], end_object)

            if action in [MenuFade.OUT_FAST, MenuFade.OUT_SLOW]:
                # Add keyframes
                start = openshot.Point(start_animation, 1.0, openshot.BEZIER)
                start_object = json.loads(start.Json())
                end = openshot.Point(end_animation, 0.0, openshot.BEZIER)
                end_object = json.loads(end.Json())
                self.AddPoint(clip.data['alpha'], start_object)
                self.AddPoint(clip.data['alpha'], end_object)

            # Save changes
            self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)

    @pyqtSlot(str, str, float)
    def RazorSliceAtCursor(self, clip_id, trans_id, cursor_position):
        """Callback from javascript that the razor tool was clicked"""

        # Determine slice mode (keep both [default], keep left [shift], keep right [ctrl]
        slice_mode = MenuSlice.KEEP_BOTH
        if int(QCoreApplication.instance().keyboardModifiers() & Qt.ControlModifier) > 0:
            slice_mode = MenuSlice.KEEP_RIGHT
        elif int(QCoreApplication.instance().keyboardModifiers() & Qt.ShiftModifier) > 0:
            slice_mode = MenuSlice.KEEP_LEFT

        if clip_id:
            # Slice clip
            QTimer.singleShot(0, partial(self.Slice_Triggered, slice_mode, [clip_id], [], cursor_position))
        elif trans_id:
            # Slice transitions
            QTimer.singleShot(0, partial(self.Slice_Triggered, slice_mode, [], [trans_id], cursor_position))

    def Slice_Triggered(self, action, clip_ids, trans_ids, playhead_position=0, ripple=False):
        """Callback for slice context menus"""
        # Get FPS from project
        fps = get_app().project.get("fps")
        fps_num = float(fps["num"])
        fps_den = float(fps["den"])

        # Get locked tracks from project
        locked_layers = [t.get("number") for t in get_app().project.get("layers") if t.get("lock")]

        # Group transactions
        tid = self.get_uuid()
        get_app().updates.transaction_id = tid

        # Emit signal to ignore updates (start ignoring updates)
        get_app().window.IgnoreUpdates.emit(True)

        try:
            # Get the nearest starting frame position to the playhead (snap to frame boundaries)
            playhead_position = float(round((playhead_position * fps_num) / fps_den) * fps_den) / fps_num

            # Loop through each clip (using the list of ids)
            for clip_id in clip_ids:

                # Get existing clip object
                clip = Clip.get(id=clip_id)
                if not clip or clip.data.get("layer") in locked_layers:
                    continue

                original_position = float(clip.data["position"])  # Original position in timeline seconds
                start_of_clip = float(clip.data["start"])  # Trim start time in clip seconds
                end_of_clip = float(clip.data["end"])  # Trim end time in clip seconds
                original_duration = end_of_clip - start_of_clip  # Duration in media seconds

                if action == MenuSlice.KEEP_LEFT:
                    # Keep the left side of the clip, adjust the "end" of the clip
                    clip.data["end"] = start_of_clip + (playhead_position - original_position)

                    if ripple:
                        removed_duration = original_duration - (clip.data["end"] - start_of_clip)
                        self.ripple_delete_gap(playhead_position, clip.data["layer"], removed_duration)

                elif action == MenuSlice.KEEP_RIGHT:
                    # Keep the right side of the clip, adjust the "start" and "position"
                    new_start = start_of_clip + (playhead_position - original_position)
                    clip.data["position"] = playhead_position  # Set new timeline position
                    clip.data["start"] = new_start

                    if ripple:
                        removed_duration = original_duration - (end_of_clip - new_start)
                        clip.data["position"] = original_position  # Move right side back to original position
                        self.ripple_delete_gap(playhead_position, clip.data["layer"], removed_duration)

                elif action == MenuSlice.KEEP_BOTH:
                    # Update clip data for the left clip
                    clip.data["end"] = start_of_clip + (playhead_position - original_position)

                    # Split into two clips (left and right side)
                    right_clip = Clip.get(id=clip_id)
                    if not right_clip:
                        continue

                    # Create right side clip
                    right_clip.id = None
                    right_clip.type = 'insert'
                    right_clip.data.pop('id')
                    right_clip.key.pop(1)
                    right_clip.data["position"] = playhead_position
                    right_clip.data["start"] = clip.data["end"]
                    right_clip.save()

                # Save changes for the left or right slice
                self.update_clip_data(clip.data, only_basic_props=True, ignore_reader=True)

            # Redraw audio waveforms
            self.redraw_audio_timer.start()

            # Handle transitions (similar to clips)
            for trans_id in trans_ids:
                trans = Transition.get(id=trans_id)
                if not trans or trans.data.get("layer") in locked_layers:
                    continue

                original_position = float(trans.data["position"])  # Timeline position
                start_of_tran = float(trans.data["start"])  # Trim start time
                end_of_tran = float(trans.data["end"])  # Trim end time
                original_duration = end_of_tran - start_of_tran  # Original duration in seconds

                if action == MenuSlice.KEEP_LEFT:
                    # Keep the left side of the transition, adjust the "end"
                    trans.data["end"] = start_of_tran + (playhead_position - original_position)

                    if ripple:
                        removed_duration = original_duration - (trans.data["end"] - start_of_tran)
                        self.ripple_delete_gap(playhead_position, trans.data["layer"], removed_duration)

                elif action == MenuSlice.KEEP_RIGHT:
                    # Keep the right side of the transition
                    new_start = start_of_tran + (playhead_position - original_position)
                    trans.data["position"] = playhead_position
                    trans.data["start"] = new_start
                    if ripple:
                        removed_duration = original_duration - (end_of_tran - new_start)
                        trans.data["position"] = original_position
                        self.ripple_delete_gap(playhead_position, trans.data["layer"], removed_duration)

                elif action == MenuSlice.KEEP_BOTH:
                    # Update data for the left transition
                    trans.data["end"] = start_of_tran + (playhead_position - original_position)

                    # Split into two transitions (left and right side)
                    right_tran = Transition.get(id=trans_id)
                    if not right_tran:
                        continue

                    # Create right side transition
                    right_tran.id = None
                    right_tran.type = 'insert'
                    right_tran.data.pop('id')
                    right_tran.key.pop(1)
                    right_tran.data["position"] = playhead_position
                    right_tran.data["start"] = trans.data["end"]
                    right_tran.save()

                # Save changes for the left or right slice
                self.update_transition_data(trans.data, only_basic_props=False)
        finally:
            get_app().updates.transaction_id = None

            # Emit signal to resume updates (stop ignoring updates)
            get_app().window.IgnoreUpdates.emit(False)

    def ripple_delete_gap(self, ripple_start, layer, ripple_gap):
        """Remove the ripple gap and adjust subsequent items"""
        # Get all clips and transitions right of ripple_start in the given layer
        clips = [clip for clip in Clip.filter(layer=layer) if clip.data.get("position", 0.0) >= ripple_start]
        transitions = [tran for tran in Transition.filter(layer=layer) if tran.data.get("position", 0.0) >= ripple_start]

        # Adjust all subsequent items by the ripple gap
        for clip in clips:
            clip.data["position"] -= ripple_gap
            clip.save()

        for trans in transitions:
            trans.data["position"] -= ripple_gap
            trans.save()

    def Volume_Triggered(self, action, clip_ids, position="Entire Clip", level=1.0):
        """Callback for volume context menus"""
        log.debug(action)

        # Get FPS from project
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        clips_with_waveforms = []

        # Loop through each selected clip
        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)
            if not clip:
                # Invalid clip, skip to next item
                continue

            start_of_clip = round(float(clip.data["start"]) * fps_float) + 1
            end_of_clip = round(float(clip.data["end"]) * fps_float) + 1

            # Determine the beginning and ending of this animation
            # ["Start of Clip", "End of Clip", "Entire Clip"]
            start_animation = start_of_clip
            end_animation = end_of_clip
            if position == "Start of Clip" and action in [
                MenuVolume.FADE_IN_FAST,
                MenuVolume.FADE_OUT_FAST
            ]:
                start_animation = start_of_clip
                end_animation = min(start_of_clip + (1.0 * fps_float), end_of_clip)

            elif position == "Start of Clip" and action in [
                MenuVolume.FADE_IN_SLOW,
                MenuVolume.FADE_OUT_SLOW
            ]:
                start_animation = start_of_clip
                end_animation = min(start_of_clip + (3.0 * fps_float), end_of_clip)

            elif position == "End of Clip" and action in [
                MenuVolume.FADE_IN_FAST,
                MenuVolume.FADE_OUT_FAST
            ]:
                start_animation = max(1.0, end_of_clip - (1.0 * fps_float))
                end_animation = end_of_clip

            elif position == "End of Clip" and action in [
                MenuVolume.FADE_IN_SLOW,
                MenuVolume.FADE_OUT_SLOW
            ]:
                start_animation = max(1.0, end_of_clip - (3.0 * fps_float))
                end_animation = end_of_clip

            elif position == "Start of Clip":
                # Only used when setting levels (a single keyframe)
                start_animation = start_of_clip
                end_animation = start_of_clip

            elif position == "End of Clip":
                # Only used when setting levels (a single keyframe)
                start_animation = end_of_clip
                end_animation = end_of_clip

            # Fade in and out (special case)
            if position == "Entire Clip" and action == MenuVolume.FADE_IN_OUT_FAST:
                # Call this method for the start and end of the clip
                self.Volume_Triggered(MenuVolume.FADE_IN_FAST, clip_ids, "Start of Clip")
                self.Volume_Triggered(MenuVolume.FADE_OUT_FAST, clip_ids, "End of Clip")
                return
            if position == "Entire Clip" and action == MenuVolume.FADE_IN_OUT_SLOW:
                # Call this method for the start and end of the clip
                self.Volume_Triggered(MenuVolume.FADE_IN_SLOW, clip_ids, "Start of Clip")
                self.Volume_Triggered(MenuVolume.FADE_OUT_SLOW, clip_ids, "End of Clip")
                return

            if action == MenuVolume.NONE:
                # Clear all keyframes
                p = openshot.Point(1, 1.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data['volume'] = {"Points": [p_object]}

            if action in [
                MenuVolume.FADE_IN_FAST,
                MenuVolume.FADE_IN_SLOW
            ]:
                # Add keyframes
                start = openshot.Point(start_animation, 0.0, openshot.BEZIER)
                start_object = json.loads(start.Json())
                end = openshot.Point(end_animation, 1.0, openshot.BEZIER)
                end_object = json.loads(end.Json())
                self.AddPoint(clip.data['volume'], start_object)
                self.AddPoint(clip.data['volume'], end_object)

            if action in [
                MenuVolume.FADE_OUT_FAST,
                MenuVolume.FADE_OUT_SLOW
            ]:
                # Add keyframes
                start = openshot.Point(start_animation, 1.0, openshot.BEZIER)
                start_object = json.loads(start.Json())
                end = openshot.Point(end_animation, 0.0, openshot.BEZIER)
                end_object = json.loads(end.Json())
                self.AddPoint(clip.data['volume'], start_object)
                self.AddPoint(clip.data['volume'], end_object)

            if action == MenuVolume.LEVEL:
                # Add keyframes
                p = openshot.Point(start_animation, float(level) / 100.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                self.AddPoint(clip.data['volume'], p_object)

            # Save changes
            self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)

            # Add any clips with waveforms to a list
            if clip.data.get("ui", {}).get("audio_data", []):
                clips_with_waveforms.append(clip.id)

        # Update waveforms of all clips that have them
        self.Show_Waveform_Triggered(clips_with_waveforms)

    def Rotate_Triggered(self, action, clip_ids, position="Start of Clip"):
        """Callback for rotate context menus"""
        log.debug(action)

        # Loop through each selected clip
        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)
            if not clip:
                # Invalid clip, skip to next item
                continue

            if action == MenuRotate.NONE:
                # Clear all keyframes
                p = openshot.Point(1, 0.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data['rotation'] = {"Points": [p_object]}

            if action == MenuRotate.RIGHT_90:
                # Add keyframes
                p = openshot.Point(1, 90.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data['rotation'] = {"Points": [p_object]}

            if action == MenuRotate.LEFT_90:
                # Add keyframes
                p = openshot.Point(1, -90.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data['rotation'] = {"Points": [p_object]}

            if action == MenuRotate.FLIP_180:
                # Add keyframes
                p = openshot.Point(1, 180.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data['rotation'] = {"Points": [p_object]}

            # Save changes
            self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)

    def Time_Triggered(self, action, clip_ids, speed="1X", playhead_position=0.0):
        """Callback for time context menus"""
        log.debug(action)

        # Get FPS from project
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        clips_with_waveforms = []

        # Loop through each selected clip
        for clip_id in clip_ids:
            # Get existing clip object
            clip = Clip.get(id=clip_id)

            if not clip:
                # Invalid clip, skip to next item
                continue

            # Add any clips with waveforms to a list
            if clip.data.get("ui", {}).get("audio_data", []):
                clips_with_waveforms.append(clip.id)

            # Keep original 'end' and 'duration'
            if "original_data" not in clip.data:
                clip.data["original_data"] = {
                    "end": clip.data["end"],
                    "duration": clip.data["duration"],
                    "video_length": clip.data["reader"]["video_length"]
                }

            # Determine the beginning and ending of this animation
            start_animation = 1

            # Freeze or Speed?
            if action in [
                MenuTime.FREEZE,
                MenuTime.FREEZE_ZOOM
            ]:
                # Get freeze details
                freeze_seconds = float(speed)

                original_duration = clip.data["duration"]
                if "original_data" in clip.data:
                    original_duration = clip.data["original_data"]["duration"]

                log.info('Updating timing for clip ID {}, original duration: {}'
                         .format(clip.id, original_duration))
                log.debug(clip.data)

                # Extend end & duration (due to freeze)
                clip.data["end"] = float(clip.data["end"]) + freeze_seconds
                clip.data["duration"] = float(clip.data["duration"]) + freeze_seconds
                clip.data["reader"]["video_length"] = float(clip.data["reader"]["video_length"]) + freeze_seconds

                # Determine start frame from position
                start_animation_seconds = float(clip.data["start"]) + (playhead_position - float(clip.data["position"]))
                start_animation_frames = round(start_animation_seconds * fps_float) + 1
                start_animation_frames_value = start_animation_frames
                end_animation_seconds = start_animation_seconds + freeze_seconds
                end_animation_frames = round(end_animation_seconds * fps_float) + 1
                end_of_clip_seconds = float(clip.data["duration"])
                end_of_clip_frames = round((end_of_clip_seconds) * fps_float) + 1
                end_of_clip_frames_value = round((original_duration) * fps_float) + 1

                # Determine volume start and end
                start_volume_value = 1.0

                # Do we already have a time curve? Look up intersecting frame # from time curve
                if len(clip.data["time"]["Points"]) > 1:
                    # Delete last time point (which should be the end of the clip). We have a new end of the clip
                    # after inserting this freeze.
                    del clip.data["time"]["Points"][-1]

                    # Find actual clip object from libopenshot
                    c = self.window.timeline_sync.timeline.GetClip(clip_id)
                    if c:
                        # Look up correct position from time curve
                        start_animation_frames_value = c.time.GetLong(start_animation_frames)

                # Do we already have a volume curve? Look up intersecting frame # from volume curve
                if len(clip.data["volume"]["Points"]) > 1:
                    # Find actual clip object from libopenshot
                    c = self.window.timeline_sync.timeline.GetClip(clip_id)
                    if c:
                        # Look up correct volume from time curve
                        start_volume_value = c.volume.GetValue(start_animation_frames)

                # Create Time Freeze keyframe points
                p = openshot.Point(start_animation_frames, start_animation_frames_value, openshot.LINEAR)
                p_object = json.loads(p.Json())
                self.AddPoint(clip.data['time'], p_object)
                p1 = openshot.Point(end_animation_frames, start_animation_frames_value, openshot.LINEAR)
                p1_object = json.loads(p1.Json())
                self.AddPoint(clip.data['time'], p1_object)
                p2 = openshot.Point(end_of_clip_frames, end_of_clip_frames_value, openshot.LINEAR)
                p2_object = json.loads(p2.Json())
                self.AddPoint(clip.data['time'], p2_object)

                # Create Volume mute keyframe points (so the freeze is silent)
                p = openshot.Point(start_animation_frames - 1, start_volume_value, openshot.LINEAR)
                p_object = json.loads(p.Json())
                self.AddPoint(clip.data['volume'], p_object)
                p = openshot.Point(start_animation_frames, 0.0, openshot.LINEAR)
                p_object = json.loads(p.Json())
                self.AddPoint(clip.data['volume'], p_object)
                p2 = openshot.Point(end_animation_frames - 1, 0.0, openshot.LINEAR)
                p2_object = json.loads(p2.Json())
                self.AddPoint(clip.data['volume'], p2_object)
                p3 = openshot.Point(end_animation_frames, start_volume_value, openshot.LINEAR)
                p3_object = json.loads(p3.Json())
                self.AddPoint(clip.data['volume'], p3_object)

                # Create zoom keyframe points
                if action == MenuTime.FREEZE_ZOOM:
                    p = openshot.Point(start_animation_frames, 1.0, openshot.BEZIER)
                    p_object = json.loads(p.Json())
                    self.AddPoint(clip.data['scale_x'], p_object)
                    p = openshot.Point(start_animation_frames, 1.0, openshot.BEZIER)
                    p_object = json.loads(p.Json())
                    self.AddPoint(clip.data['scale_y'], p_object)

                    diff_halfed = (end_animation_frames - start_animation_frames) / 2.0
                    p1 = openshot.Point(start_animation_frames + diff_halfed, 1.05, openshot.BEZIER)
                    p1_object = json.loads(p1.Json())
                    self.AddPoint(clip.data['scale_x'], p1_object)
                    p1 = openshot.Point(start_animation_frames + diff_halfed, 1.05, openshot.BEZIER)
                    p1_object = json.loads(p1.Json())
                    self.AddPoint(clip.data['scale_y'], p1_object)

                    p1 = openshot.Point(end_animation_frames, 1.0, openshot.BEZIER)
                    p1_object = json.loads(p1.Json())
                    self.AddPoint(clip.data['scale_x'], p1_object)
                    p1 = openshot.Point(end_animation_frames, 1.0, openshot.BEZIER)
                    p1_object = json.loads(p1.Json())
                    self.AddPoint(clip.data['scale_y'], p1_object)

            else:

                # Calculate speed factor
                speed_label = speed.replace('X', '')
                speed_parts = speed_label.split('/')
                even_multiple = 1
                if len(speed_parts) == 2:
                    speed_factor = float(speed_parts[0]) / float(speed_parts[1])
                    even_multiple = int(speed_parts[1])
                else:
                    speed_factor = float(speed_label)
                    even_multiple = int(speed_factor)

                # Clear all keyframes
                p = openshot.Point(start_animation, 0.0, openshot.LINEAR)
                p_object = json.loads(p.Json())
                clip.data['time'] = {"Points": [p_object]}

                # Get the ending frame (do not round)
                end_of_clip = int(float(clip.data["end"]) * fps_float)

                # Determine the beginning and ending of this animation
                start_animation = round(float(clip.data["start"]) * fps_float) + 1
                duration_animation = self.round_to_multiple(end_of_clip - start_animation, even_multiple)
                end_animation = start_animation + duration_animation

                if action == MenuTime.FORWARD:
                    # Add keyframes
                    start = openshot.Point(start_animation, start_animation, openshot.LINEAR)
                    start_object = json.loads(start.Json())
                    clip.data['time'] = {"Points": [start_object]}
                    end = openshot.Point(
                        start_animation + (duration_animation / speed_factor), end_animation, openshot.LINEAR)
                    end_object = json.loads(end.Json())
                    self.AddPoint(clip.data['time'], end_object)

                    # Adjust end & duration
                    clip.data["end"] = (start_animation + (duration_animation / speed_factor)) / fps_float
                    clip.data["duration"] = self.round_to_multiple(clip.data["duration"] / speed_factor, even_multiple)
                    clip.data["reader"]["video_length"] = self.round_to_multiple(
                        float(clip.data["reader"]["video_length"]) / speed_factor, even_multiple)

                if action == MenuTime.BACKWARD:
                    # Add keyframes
                    start = openshot.Point(start_animation, end_animation, openshot.LINEAR)
                    start_object = json.loads(start.Json())
                    clip.data['time'] = {"Points": [start_object]}
                    end = openshot.Point(
                        start_animation + (duration_animation / speed_factor), start_animation, openshot.LINEAR)
                    end_object = json.loads(end.Json())
                    self.AddPoint(clip.data['time'], end_object)

                    # Adjust end & duration
                    clip.data["end"] = (start_animation + (duration_animation / speed_factor)) / fps_float
                    clip.data["duration"] = self.round_to_multiple(clip.data["duration"] / speed_factor, even_multiple)
                    clip.data["reader"]["video_length"] = self.round_to_multiple(
                        float(clip.data["reader"]["video_length"]) / speed_factor, even_multiple)

                if action == MenuTime.NONE and "original_data" in clip.data:
                    # Reset original end & duration (if available)
                    orig = clip.data.pop("original_data")
                    clip.data.update({
                        "end": orig["end"],
                        "duration": orig["duration"],
                    })
                    clip.data["reader"]["video_length"] = orig["video_length"]

            # Save changes
            self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)

        # Update waveforms of all clips that have them
        self.Show_Waveform_Triggered(clips_with_waveforms)

    def round_to_multiple(self, number, multiple):
        """Round this to the closest multiple of a given #"""
        return number - (number % multiple)

    def show_all_clips(self, clip, stretch=False):
        """ Show all clips at the same time (arranged col by col, row by row)  """
        from math import sqrt

        # Get list of nearby clips
        available_clips = []
        start_position = float(clip.data["position"])
        for c in Clip.filter():
            if (float(c.data["position"]) >= (start_position - 0.5)
               and float(c.data["position"]) <= (start_position + 0.5)):
                # add to list
                available_clips.append(c)

        # Get the number of rows
        number_of_clips = len(available_clips)
        number_of_rows = int(sqrt(number_of_clips))
        max_clips_on_row = float(number_of_clips) / float(number_of_rows)

        # Determine how many clips per row
        if max_clips_on_row > float(int(max_clips_on_row)):
            max_clips_on_row = int(max_clips_on_row + 1)
        else:
            max_clips_on_row = int(max_clips_on_row)

        # Calculate Height & Width
        height = 1.0 / float(number_of_rows)
        width = 1.0 / float(max_clips_on_row)

        clip_index = 0

        # Loop through each row of clips
        for row in range(0, number_of_rows):

            # Loop through clips on this row
            for col in range(0, max_clips_on_row):
                if clip_index >= number_of_clips:
                    continue

                # Calculate X & Y
                X = float(col) * width
                Y = float(row) * height

                # Modify clip layout settings
                selected_clip = available_clips[clip_index]
                selected_clip.data["gravity"] = openshot.GRAVITY_TOP_LEFT

                if stretch:
                    selected_clip.data["scale"] = openshot.SCALE_STRETCH
                else:
                    selected_clip.data["scale"] = openshot.SCALE_FIT

                # Set scale keyframes
                w = openshot.Point(1, width, openshot.BEZIER)
                w_object = json.loads(w.Json())
                selected_clip.data["scale_x"] = {"Points": [w_object]}
                h = openshot.Point(1, height, openshot.BEZIER)
                h_object = json.loads(h.Json())
                selected_clip.data["scale_y"] = {"Points": [h_object]}
                x_point = openshot.Point(1, X, openshot.BEZIER)
                x_object = json.loads(x_point.Json())
                selected_clip.data["location_x"] = {"Points": [x_object]}
                y_point = openshot.Point(1, Y, openshot.BEZIER)
                y_object = json.loads(y_point.Json())
                selected_clip.data["location_y"] = {"Points": [y_object]}

                log.info('Updating clip id: %s' % selected_clip.data["id"])
                log.info('width: %s, height: %s' % (width, height))

                # Increment Clip Index
                clip_index += 1

                # Save changes
                self.update_clip_data(selected_clip.data, only_basic_props=False, ignore_reader=True)

    def Reverse_Transition_Triggered(self, tran_ids):
        """Callback for reversing a transition"""
        log.info("Reverse_Transition_Triggered")

        # Loop through all selected transitions
        for tran_id in tran_ids:

            # Get existing clip object
            tran = Transition.get(id=tran_id)
            if not tran:
                # Invalid transition, skip to next item
                continue

            # Loop through brightness keyframes
            tran_data_copy = json.loads(json.dumps(tran.data))
            new_index = len(tran.data["brightness"]["Points"])
            for point in tran.data["brightness"]["Points"]:
                new_index -= 1
                tran_data_copy["brightness"]["Points"][new_index]["co"]["Y"] = point["co"]["Y"]
                if "handle_left" in point:
                    tran_data_copy["brightness"]["Points"][new_index]["handle_left"]["Y"] = point["handle_left"]["Y"]
                    tran_data_copy["brightness"]["Points"][new_index]["handle_right"]["Y"] = point["handle_right"]["Y"]

            # Save changes
            self.update_transition_data(tran_data_copy, only_basic_props=False)

    @pyqtSlot(str)
    def ShowTransitionMenu(self, tran_id=None):
        log.info('ShowTransitionMenu: %s' % tran_id)

        # Get translation method
        _ = get_app()._tr

        # Get existing transition object
        tran = Transition.get(id=tran_id)
        if not tran:
            # Not a valid transition id
            return

        # Get list of all selected transitions
        tran_ids = self.window.selected_transitions
        clip_ids = self.window.selected_clips

        # Get framerate
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])

        # Get playhead position
        playhead_position = float(self.window.preview_thread.current_frame) / fps_float

        # Get clipboard
        copied_object = ClipboardManager.from_mime(get_app().clipboard().mimeData())
        if copied_object:
            print(f"Copied object found: {type(copied_object).__name__}")
        has_clipboard = False
        if copied_object and isinstance(copied_object, Transition):
            has_clipboard = True

        menu = StyledContextMenu(parent=self)

        # Copy Menu
        if len(tran_ids) + len(clip_ids) > 1:
            # Show Copy All menu (clips and transitions are selected)
            Copy_All = menu.addAction(_("Copy"))
            Copy_All.setShortcuts(self.window.getShortcutByName("copyAll"))
            Copy_All.triggered.connect(self.window.copyAll)
            # Show Cut All menu
            Cut_All = menu.addAction(_("Cut"))
            Cut_All.setShortcuts(self.window.getShortcutByName("cutAll"))
            Cut_All.triggered.connect(self.window.cutAll)
        else:
            # Only a single transitions is selected (show normal transition copy menu)
            Copy_Menu = StyledContextMenu(title=_("Copy"), parent=self)
            Copy_Tran = Copy_Menu.addAction(_("Transition"))
            Copy_Tran.setShortcuts(self.window.getShortcutByName("copyAll"))
            Copy_Tran.triggered.connect(partial(self.Copy_Triggered, MenuCopy.TRANSITION, [], [tran_id], []))

            Keyframe_Menu = StyledContextMenu(title=_("Keyframes"), parent=self)
            Copy_Keyframes_All = Keyframe_Menu.addAction(_("All"))
            Copy_Keyframes_All.triggered.connect(partial(
                self.Copy_Triggered, MenuCopy.KEYFRAMES_ALL, [], [tran_id], []))
            Keyframe_Menu.addSeparator()
            Copy_Keyframes_Brightness = Keyframe_Menu.addAction(_("Brightness"))
            Copy_Keyframes_Brightness.triggered.connect(partial(
                self.Copy_Triggered, MenuCopy.KEYFRAMES_BRIGHTNESS, [], [tran_id], []))
            Copy_Keyframes_Scale = Keyframe_Menu.addAction(_("Contrast"))
            Copy_Keyframes_Scale.triggered.connect(partial(
                self.Copy_Triggered, MenuCopy.KEYFRAMES_CONTRAST, [], [tran_id], []))

            # Only show copy->keyframe if a single transitions is selected
            Copy_Menu.addMenu(Keyframe_Menu)
            menu.addMenu(Copy_Menu)

        # Show Cut menu
        Cut_All = menu.addAction(_("Cut"))
        Cut_All.setShortcuts(self.window.getShortcutByName("cutAll"))
        Cut_All.triggered.connect(self.window.cutAll)

        # Determine if the paste menu should be shown
        if has_clipboard:
            # Paste Menu (Only show when partial transition clipboard available)
            Paste_Tran = menu.addAction(_("Paste"))
            Paste_Tran.triggered.connect(partial(self.Paste_Triggered, MenuCopy.PASTE, [], tran_ids))

        menu.addSeparator()

        # Alignment Menu (if multiple selections)
        if len(clip_ids) > 1:
            Alignment_Menu = StyledContextMenu(title=_("Align"), parent=self)
            Align_Left = Alignment_Menu.addAction(_("Left"))
            Align_Left.triggered.connect(partial(self.Align_Triggered, MenuAlign.LEFT, clip_ids, tran_ids))
            Align_Right = Alignment_Menu.addAction(_("Right"))
            Align_Right.triggered.connect(partial(self.Align_Triggered, MenuAlign.RIGHT, clip_ids, tran_ids))

            # Add menu to parent
            menu.addMenu(Alignment_Menu)

        # If Playhead overlapping transition
        if tran:
            start_of_tran = float(tran.data["start"])
            end_of_tran = float(tran.data["end"])
            position_of_tran = float(tran.data["position"])
            if (playhead_position >= position_of_tran
               and playhead_position <= (position_of_tran + (end_of_tran - start_of_tran))):
                # Add split transition menu
                Slice_Menu = StyledContextMenu(title=_("Slice"), parent=self)
                Slice_Keep_Both = Slice_Menu.addAction(_("Keep Both Sides"))
                Slice_Keep_Both.triggered.connect(partial(
                    self.Slice_Triggered, MenuSlice.KEEP_BOTH, clip_ids, tran_ids, playhead_position))
                Slice_Keep_Left = Slice_Menu.addAction(_("Keep Left Side"))
                Slice_Keep_Left.triggered.connect(partial(
                    self.Slice_Triggered, MenuSlice.KEEP_LEFT, clip_ids, tran_ids, playhead_position))
                Slice_Keep_Right = Slice_Menu.addAction(_("Keep Right Side"))
                Slice_Keep_Right.triggered.connect(partial(
                    self.Slice_Triggered, MenuSlice.KEEP_RIGHT, clip_ids, tran_ids, playhead_position))

                # Add slice clip menu w/ Ripple
                Slice_Menu.addSeparator()
                Slice_Keep_Left = Slice_Menu.addAction(_("Keep Left Side (Ripple)"))
                Slice_Keep_Left.triggered.connect(partial(
                    self.Slice_Triggered, MenuSlice.KEEP_LEFT, clip_ids, tran_ids, playhead_position, True))
                Slice_Keep_Right = Slice_Menu.addAction(_("Keep Right Side (Ripple)"))
                Slice_Keep_Right.triggered.connect(partial(
                    self.Slice_Triggered, MenuSlice.KEEP_RIGHT, clip_ids, tran_ids, playhead_position, True))

                menu.addMenu(Slice_Menu)

        # Reverse Transition menu
        Reverse_Transition = menu.addAction(_("Reverse Transition"))
        Reverse_Transition.triggered.connect(partial(self.Reverse_Transition_Triggered, tran_ids))

        # Properties
        menu.addSeparator()
        menu.addAction(self.window.actionProperties)

        # Remove transition menu
        menu.addSeparator()
        menu.addAction(self.window.actionRemoveTransition)

        # Show context menu
        self.context_menu_cursor_position = QCursor.pos()
        return menu.popup(self.context_menu_cursor_position)

    @pyqtSlot(str)
    def ShowTrackMenu(self, layer_id=None):
        log.info('ShowTrackMenu: %s', layer_id)

        # Get translation method
        _ = get_app()._tr

        # Get track object
        track = Track.get(id=layer_id)
        if not track:
            return

        if layer_id not in self.window.selected_tracks:
            self.window.selected_tracks = [layer_id]

        # Find gaps on this track (if any)
        found_gap = False
        first_gap_start = 0.0
        layer_number = track.data.get("number", 0)

        # Combine and sort the clips and transitions by their position
        clips_and_transitions = sorted(
            Clip.filter(layer=layer_number) + Transition.filter(layer=layer_number),
            key=lambda c: c.data.get("position", 0.0)
        )

        # Variable to track the end of the last clip/transition
        last_end = 0.0

        # Loop through the combined and sorted list
        for clip in clips_and_transitions:
            left_edge = clip.data.get("position", 0.0)
            right_edge = left_edge + (clip.data.get("end", 0.0) - clip.data.get("start", 0.0))

            # Check if there is a gap between the end of the last clip/transition and the start of the current one
            if left_edge > last_end:
                found_gap = True
                first_gap_start = last_end
                break  # Stop once the first gap is found

            # Update the end of the last clip/transition
            last_end = max(last_end, right_edge)

        # Is track locked?
        locked = track.data.get("lock", False)

        menu = StyledContextMenu(parent=self)
        menu.addAction(self.window.actionAddTrackAbove)
        menu.addAction(self.window.actionAddTrackBelow)
        menu.addAction(self.window.actionRenameTrack)
        if found_gap:
            # Add 'Remove Gap' Menu
            log.info(f"Found gap at {first_gap_start}")
            menu.addAction(self.window.actionRemoveAllGaps)
            try:
                # Disconnect any previous connections
                self.window.actionRemoveAllGaps.triggered.disconnect()
            except TypeError:
                pass  # No previous connections
            self.window.actionRemoveAllGaps.triggered.connect(
                partial(self.RemoveAllGaps_Triggered, first_gap_start, int(layer_number))
            )
        if locked:
            menu.addAction(self.window.actionUnlockTrack)
            self.window.actionRemoveTrack.setEnabled(False)
        else:
            menu.addAction(self.window.actionLockTrack)
            self.window.actionRemoveTrack.setEnabled(True)
        menu.addSeparator()
        menu.addAction(self.window.actionRemoveTrack)

        # Show context menu
        self.context_menu_cursor_position = QCursor.pos()
        return menu.popup(self.context_menu_cursor_position)

    @pyqtSlot(str)
    def ShowMarkerMenu(self, marker_id=None):
        log.info('ShowMarkerMenu: %s' % marker_id)

        if marker_id not in self.window.selected_markers:
            self.window.selected_markers = [marker_id]

        menu = StyledContextMenu(parent=self)
        menu.addAction(self.window.actionRemoveMarker)

        # Show context menu
        self.context_menu_cursor_position = QCursor.pos()
        return menu.popup(self.context_menu_cursor_position)

    @pyqtSlot()
    def EnableCacheThread(self):
        log.debug('EnableCacheThread: Start caching frames on timeline')

        # Enable video caching
        openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = True

        # Refresh frame to ensure our last frame after scrubbing
        # is the final frame shown. Due to some unknown reason, this
        # is required for an accurate end to srubbing
        QTimer.singleShot(50, self.window.refreshFrameSignal.emit)

    @pyqtSlot()
    def DisableCacheThread(self):
        log.debug('DisableCacheThread: Stop caching frames on timeline')

        # Disable video caching
        openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = False

    @pyqtSlot(str, int)
    def PreviewClipFrame(self, clip_id, frame_number):

        # Get existing clip object
        clip = Clip.get(id=clip_id)
        if not clip:
            # Invalid clip
            return

        preview_path = clip.data['reader']['path']

        # Adjust frame # to valid range
        frame_number = max(frame_number, 1)
        frame_number = min(frame_number, int(clip.data['reader']['video_length']))

        # Load the clip into the Player (ignored if this has already happened)
        self.window.LoadFileSignal.emit(preview_path)
        self.window.SpeedSignal.emit(0)

        # Seek to frame
        self.window.SeekSignal.emit(frame_number)

    @pyqtSlot(int)
    def SeekToKeyframe(self, frame_number):
        """Seek to a specific frame when a keyframe point is clicked"""

        # Seek to frame
        self.window.SeekSignal.emit(frame_number)

    @pyqtSlot(int)
    def PlayheadMoved(self, position_frames):

        # Load the timeline into the Player (ignored if this has already happened)
        self.window.LoadFileSignal.emit('')

        if self.last_position_frames != position_frames:
            # Update time code (to prevent duplicate previews)
            self.last_position_frames = position_frames

            # Notify main window of current frame
            self.window.SeekSignal.emit(position_frames)

    @pyqtSlot(int)
    def movePlayhead(self, position_frames):
        """ Move the playhead since the position has changed inside OpenShot (probably due to the video player) """
        # Get access to timeline scope and set scale to zoom slider value (passed in)
        self.run_js(JS_SCOPE_SELECTOR + ".movePlayheadToFrame(%s);" % (str(position_frames)))

    @pyqtSlot()
    def centerOnPlayhead(self):
        """ Center the timeline on the current playhead position """
        # Execute JavaScript to center the timeline
        self.run_js(JS_SCOPE_SELECTOR + '.centerOnPlayhead();')

    @pyqtSlot(int)
    def SetSnappingMode(self, enable_snapping):
        """ Enable / Disable snapping mode """
        # Init snapping state (1 = snapping, 0 = no snapping)
        self.run_js(JS_SCOPE_SELECTOR + ".setSnappingMode(%s);" % int(enable_snapping))

    @pyqtSlot(int)
    def SetRazorMode(self, enable_razor):
        """ Enable / Disable razor mode """
        # Init razor state (1 = razor, 0 = no razor)
        self.run_js(JS_SCOPE_SELECTOR + ".setRazorMode(%s);" % int(enable_razor))

    @pyqtSlot(str)
    def SetPropertyFilter(self, property):
        """ Filter a specific property name """
        self.run_js(JS_SCOPE_SELECTOR + ".setPropertyFilter('%s');" % property)

    @pyqtSlot(int)
    def SetPlayheadFollow(self, enable_follow):
        """ Enable / Disable playhead follow on seek """
        self.run_js(JS_SCOPE_SELECTOR + ".setFollow({});".format(int(enable_follow)))

    @pyqtSlot(str, str, bool)
    def addSelection(self, item_id, item_type, clear_existing=False):
        """ Add the selected item to the current selection """
        self.window.SelectionAdded.emit(item_id, item_type, clear_existing)

    def addRippleSelection(self, item_id, item_type):
        if item_type == "clip":
            self.run_js(JS_SCOPE_SELECTOR + ".selectClipRipple('{}', false, null);".format(item_id))
        elif item_type == "transition":
            self.run_js(JS_SCOPE_SELECTOR + ".selectTransitionRipple('{}', false, null);".format(item_id))

    @pyqtSlot(str, str)
    def removeSelection(self, item_id, item_type):
        """ Remove the selected clip from the selection """
        self.window.SelectionRemoved.emit(item_id, item_type)

    @pyqtSlot(str, str)
    def qt_log(self, level="INFO", message=None):
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARN": logging.WARNING,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
            "FATAL": logging.FATAL,
            }
        if isinstance(level, str):
            level = levels.get(level, logging.INFO)
        self.log_fn(level, message)

    @pyqtSlot()
    def zoomIn(self):
        get_app().window.sliderZoomWidget.zoomIn()

    @pyqtSlot()
    def zoomOut(self):
        get_app().window.sliderZoomWidget.zoomOut()

    def update_scroll(self, newScroll):
        """Force a scroll event on the timeline (i.e. the zoom slider is moving, so we need to scroll the timeline)"""
        # Get access to timeline scope and set scale to new computed value
        self.run_js(JS_SCOPE_SELECTOR + ".setScroll(" + str(newScroll) + ");")

    # Handle changes to zoom level, update js
    def update_zoom(self, newScale):
        _ = get_app()._tr

        # Determine X coordinate of cursor (to center zoom on)
        cursor_y = self.mapFromGlobal(self.cursor().pos()).y()
        if cursor_y >= 0:
            cursor_x = self.mapFromGlobal(self.cursor().pos()).x()
        else:
            cursor_x = 0

        # Get access to timeline scope and set scale to new computed value
        self.run_js(JS_SCOPE_SELECTOR + ".setScale(" + str(newScale) + "," + str(cursor_x) + ");")

        # Start or restart timer to redraw audio
        self.redraw_audio_timer.start()

        # Only update scale if different
        current_scale = float(get_app().project.get("scale") or 15.0)

        # Save current zoom
        if newScale != current_scale:
            get_app().updates.ignore_history = True
            get_app().updates.update(["scale"], newScale)
            get_app().updates.ignore_history = False

    # An item is being dragged onto the timeline (mouse is entering the timeline now)
    def dragEnterEvent(self, event):
        # Wait cursor
        get_app().setOverrideCursor(QCursor(Qt.WaitCursor))

        # Clear previous selections
        self.ClearAllSelections()
        get_app().processEvents()

        # Initialize a list to hold file data (either from mime data or newly created files)
        data_list = []
        initial_pos = event.posF()

        # Get FPS and scaling information
        fps_float = float(get_app().project.get("fps")["num"]) / float(get_app().project.get("fps")["den"])
        snap_to_grid = lambda t: round(t * fps_float) / fps_float

        # Handle URL-based OS file drop
        if event.mimeData().hasUrls():
            self.item_type = "clip"
            urls = event.mimeData().urls()

            # Import list of files
            get_app().window.files_model.process_urls(urls, import_quietly=True, prevent_image_seq=True)

            # Get File objects and add JSON data
            for uri in urls:
                filepath = uri.toLocalFile()
                if not os.path.exists(filepath) or not os.path.isfile(filepath):
                    continue  # Skip invalid files

                # Create File object and get its JSON data
                for file in File.filter(path=filepath):
                    if file:
                        data_list.append(file.id)

        # Handle text-based mime data (clips or transitions)
        elif event.mimeData().html():
            self.item_type = event.mimeData().html()
            data_list = json.loads(event.mimeData().text())

            if not isinstance(data_list, list):
                data_list = [data_list]

        # If no valid item type, return
        if not self.item_type:
            return

        self.new_item = True
        self.item_ids = []

        # Restore cursor
        get_app().restoreOverrideCursor()

        # Nested callback to handle JavaScript position response
        def handle_js_position(pos, js_position_data):
            # Group drag/drop transactions
            tid = self.get_uuid()
            get_app().updates.transaction_id = tid

            js_position = snap_to_grid(js_position_data.get('position', 0.0))
            js_nearest_track = js_position_data.get('track', 0)

            pos.setX(js_position)

            # Create clips / transitions for each dragged data
            for index, drag_id in enumerate(data_list):
                ignore_refresh = False if index == len(data_list) - 1 else True
                new_item = None

                # Handle clip creation
                if self.item_type == "clip":
                    # Load file JSON and create the clip
                    new_item = self.addClip(drag_id, pos, js_nearest_track, ignore_refresh)

                # Handle transition creation
                elif self.item_type == "transition":
                    new_item = self.addTransition(drag_id, pos, js_nearest_track, ignore_refresh)

                # Adjust position for the next clip/transition
                if new_item:
                    pos += QPointF(new_item["end"] - new_item["start"], 0)

        # Get JS position and pass initial position to the callback
        self.run_js(JS_SCOPE_SELECTOR + ".getJavaScriptPosition({}, {});"
                    .format(initial_pos.x(), initial_pos.y()), partial(handle_js_position, initial_pos))

        # Accept the event
        event.accept()

    # Add Clip
    def addClip(self, file_id, position, track, ignore_refresh=False):
        # Retrieve File object by file_id
        file = File.get(id=file_id)
        if not file:
            return  # Skip if the file is not found

        # Get file name and path
        filename = os.path.basename(file.data["path"])
        file_path = file.absolute_path()

        # Get FPS and frame precision
        fps_float = float(get_app().project.get("fps")["num"]) / float(get_app().project.get("fps")["den"])
        snap_to_grid = lambda t: round(t * fps_float) / fps_float

        # Create a new Clip object with the file path
        c = openshot.Clip(file_path)

        # Convert the clip object to JSON and fill missing attributes
        new_clip = json.loads(c.Json())
        new_clip["file_id"] = file.id
        new_clip["title"] = file.data.get("name", filename)
        new_clip["reader"] = file.data

        # Skip clips that are missing a 'reader' attribute
        if not new_clip.get("reader"):
            return  # Skip this clip

        # Handle optional start and end times for the clip
        if 'start' in file.data:
            new_clip["start"] = snap_to_grid(file.data['start'])
        if 'end' in file.data:
            new_clip["end"] = snap_to_grid(file.data['end'])
        else:
            new_clip["end"] = snap_to_grid(new_clip["reader"]["duration"])

        # Use the passed position and track directly
        new_clip["position"] = position.x()
        new_clip["layer"] = track

        # Adjust the clip duration and set default values for images
        new_clip["duration"] = snap_to_grid(new_clip["reader"]["duration"])
        if file.data["media_type"] == "image":
            new_clip["end"] = snap_to_grid(get_app().get_settings().get("default-image-length"))

        # Add the clip to the timeline
        self.update_clip_data(new_clip, only_basic_props=False, ignore_refresh=ignore_refresh)

        # Track the added clip
        self.item_ids.append(new_clip.get('id'))

        # Trigger manual move event to initialize UI snapping
        self.run_js(JS_SCOPE_SELECTOR + ".startManualMove('{}', '{}');".format(self.item_type, json.dumps(self.item_ids)))
        return new_clip

    @pyqtSlot(list)
    def ScrollbarChanged(self, new_positions):
        """Timeline scrollbars changed"""
        get_app().window.TimelineScrolled.emit(new_positions)

    # Resize timeline
    @pyqtSlot(float)
    def resizeTimeline(self, new_duration):
        """Resize the duration of the timeline"""
        log.debug(f"Changing timeline to length: {new_duration}")
        get_app().updates.update_untracked(["duration"], new_duration)
        get_app().window.TimelineResize.emit()

    # Add Transition
    def addTransition(self, file_path, position, track, ignore_refresh=False):
        # Get FPS from project
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        snap_to_grid = lambda t: round(t * fps_float) / fps_float
        duration = snap_to_grid(get_app().get_settings().get("default-transition-length"))

        # Open up QtImageReader for transition Image
        transition_reader = openshot.QtImageReader(file_path)

        # Create Keyframes for brightness and contrast
        brightness = openshot.Keyframe()
        brightness.AddPoint(1, 1.0, openshot.BEZIER)
        brightness.AddPoint(round(duration * fps_float) + 1, -1.0, openshot.BEZIER)

        contrast = openshot.Keyframe(3.0)

        # Create transition dictionary
        transition_data = {
            "id": get_app().project.generate_id(),
            "layer": track,
            "title": "Transition",
            "type": "Mask",
            "position": snap_to_grid(position.x()),
            "start": 0,
            "end": duration,
            "brightness": json.loads(brightness.Json()),
            "contrast": json.loads(contrast.Json()),
            "reader": json.loads(transition_reader.Json()),
            "replace_image": False
        }

        # Send to update manager
        self.update_transition_data(transition_data, only_basic_props=False, ignore_refresh=ignore_refresh)

        # Track the added transition
        self.item_ids.append(transition_data.get('id'))

        # Init javascript bounding box (for snapping support)
        self.run_js(JS_SCOPE_SELECTOR + ".startManualMove('{}','{}');".format(self.item_type, json.dumps(self.item_ids)))
        return transition_data

    # Add Effect
    def addEffect(self, effect_names, event_position):

        # Callback function, to actually add the effect object
        def callback(self, effect_names, callback_data):
            js_position = callback_data.get('position', 0.0)
            js_nearest_track = callback_data.get('track', 0)

            # Get class name of effect
            name = effect_names[0]

            # Loop through clips on the closest layer
            possible_clips = Clip.filter(layer=js_nearest_track)
            for clip in possible_clips:
                if js_position == 0 or (
                    clip.data["position"]
                    <= js_position
                    <= clip.data["position"] + (clip.data["end"] - clip.data["start"])
                ):
                    log.info("Applying effect {} to clip ID {}".format(name, clip.id))
                    log.debug(clip)

                    # Handle custom effect dialogs
                    if name in effect_options:

                        # Get effect options
                        effect_params = effect_options.get(name)

                        # Show effect pre-processing window
                        from windows.process_effect import ProcessEffect

                        try:
                            win = ProcessEffect(clip.id, name, effect_params)

                        except ModuleNotFoundError as e:
                            print("[ERROR]: " + str(e))
                            return

                        print("Effect %s" % name)
                        print("Effect options: %s" % effect_options)

                        # Run the dialog event loop - blocking interaction on this window during this time
                        result = win.exec_()

                        if result == QDialog.Accepted:
                            log.info('Start processing')
                        else:
                            log.info('Cancel processing')
                            return

                        # Create Effect
                        effect = win.effect # effect.Id already set

                        if effect is None:
                            break
                    else:
                        # Create Effect
                        effect = openshot.EffectInfo().CreateEffect(name)

                        # Get Effect JSON
                        effect.Id(get_app().project.generate_id())

                    effect_json = json.loads(effect.Json())

                    # Append effect JSON to clip
                    clip.data["effects"].append(effect_json)

                    # Update clip data for project
                    self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)

        # Find position from javascript
        self.run_js(JS_SCOPE_SELECTOR + ".getJavaScriptPosition({}, {});"
            .format(event_position.x(), event_position.y()), partial(callback, self, effect_names))

    # Without defining this method, the 'copy' action doesn't show with cursor
    def dragMoveEvent(self, event):
        # Accept all move events
        event.accept()

        # Get cursor position
        pos = event.posF()

        # Move clip on timeline
        if self.item_type in ["clip", "transition"]:
            self.run_js(JS_SCOPE_SELECTOR + ".moveItem({}, {});".format(pos.x(), pos.y()))

    # Drop an item on the timeline
    def dropEvent(self, event):
        log.info("Dropping item on timeline - item_ids: %s, item_type: %s" % (self.item_ids, self.item_type))

        # Accept the event
        event.accept()

        if self.item_type == "effect":
            pos = event.posF()
            data = json.loads(event.mimeData().text())
            self.addEffect(data, pos)

        elif self.item_type in ["clip", "transition"] and self.item_ids:
            # Update most recent clip or transition
            self.run_js(JS_SCOPE_SELECTOR + ".updateRecentItemJSON('{}', '{}', '{}');"
                        .format(self.item_type, json.dumps(self.item_ids), get_app().updates.transaction_id))

        # Cleanup after drop
        self.new_item = False
        self.item_type = None
        self.item_ids = []
        get_app().updates.transaction_id = None

    def dragLeaveEvent(self, event):
        """A drag is in-progress and the user moves mouse outside of timeline"""
        log.debug('dragLeaveEvent - Undo drop')

        # Accept event
        event.accept()

        # Clear selected clips
        for item_id in self.item_ids:
            self.window.removeSelection(item_id, self.item_type)

            if self.item_type == "clip":
                # Delete dragging clip
                clips = Clip.filter(id=item_id)
                for c in clips:
                    c.delete()

            elif self.item_type == "transition":
                # Delete dragging transitions
                transitions = Transition.filter(id=item_id)
                for t in transitions:
                    t.delete()

        # Clear new clip
        self.new_item = False
        self.item_type = None
        self.item_ids = None

    def redraw_audio_onTimeout(self):
        """Timer is ready to redraw audio (if any)"""
        log.debug('redraw_audio_onTimeout')

        # Pass to javascript timeline (and render)
        self.run_js(JS_SCOPE_SELECTOR + ".reDrawAllAudioData();")

    def ClearAllSelections(self):
        """Clear all selections in JavaScript"""

        # Call javascript command
        self.run_js(JS_SCOPE_SELECTOR + ".clearAllSelections();")

    def SelectAll(self):
        """Select all clips and transitions in JavaScript"""

        # Call javascript command
        self.run_js(JS_SCOPE_SELECTOR + ".selectAll();")

    def render_cache_json(self):
        """Render the cached frames to the timeline (called every X seconds), and only if changed"""

        # Get final cache object from timeline
        try:
            if self.window.timeline_sync and self.window.timeline_sync.timeline:
                cache_object = self.window.timeline_sync.timeline.GetCache()
                if not cache_object:
                    return
                # Get the JSON from the cache object (i.e. which frames are cached)
                cache_json = cache_object.Json()
                cache_dict = json.loads(cache_json)
                cache_version = cache_dict["version"]

                if self.cache_renderer_version == cache_version:
                    # Nothing has changed, ignore
                    return
                # Cache has changed, re-render it
                self.cache_renderer_version = cache_version
                self.run_js(JS_SCOPE_SELECTOR + ".renderCache({});".format(cache_json))
        except Exception as ex:
            # Log the exception and ignore
            log.warning("Exception processing timeline cache: %s", ex)

    def handle_selection(self):
        # Force recalculation of clips and repaint
        self.run_js(JS_SCOPE_SELECTOR + ".refreshTimeline();")

    def __init__(self, window):
        super().__init__()
        self.setObjectName("TimelineView")

        app = get_app()
        self.window = window
        self.setAcceptDrops(True)
        self.last_position_frames = None
        self.context_menu_cursor_position = None

        # Get logger
        self.log_fn = log.log

        # Add self as listener to project data updates (used to update the timeline)
        app.updates.add_listener(self)

        # Connect zoom functionality
        window.TimelineZoom.connect(self.update_zoom)
        window.TimelineScroll.connect(self.update_scroll)
        window.TimelineCenter.connect(self.centerOnPlayhead)
        window.SetKeyframeFilter.connect(self.SetPropertyFilter)

        # Connect update thumbnail signal
        window.ThumbnailUpdated.connect(self.Thumbnail_Updated)

        # Init New clip
        self.new_item = False
        self.item_type = None
        self.item_ids = []

        # Delayed zoom audio redraw
        self.redraw_audio_timer = QTimer(self)
        self.redraw_audio_timer.setInterval(300)
        self.redraw_audio_timer.setSingleShot(True)
        self.redraw_audio_timer.timeout.connect(self.redraw_audio_onTimeout)

        # QTimer for cache rendering
        self.cache_renderer_version = None
        self.cache_renderer = QTimer(self)
        self.cache_renderer.setInterval(300)
        self.cache_renderer.timeout.connect(self.render_cache_json)

        # Connect shutdown signals
        app.aboutToQuit.connect(self.redraw_audio_timer.stop)
        app.aboutToQuit.connect(self.cache_renderer.stop)
        app.lastWindowClosed.connect(self.deleteLater)

        # Delay the start of cache rendering
        QTimer.singleShot(1500, self.cache_renderer.start)

        # connect signal to receive waveform data
        self.clipAudioDataReady.connect(self.clipAudioDataReady_Triggered)
        self.fileAudioDataReady.connect(self.fileAudioDataReady_Triggered)

        # Connect Selection signals
        self.window.SelectionChanged.connect(self.handle_selection)

