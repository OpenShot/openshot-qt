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

from PyQt5.QtWidgets import *
from PyQt5.QtGui import QIcon

from classes import info, ui_util
from classes.logger import log
from classes.query import Track
from classes.app import get_app
from windows.views.add_to_timeline_treeview import TimelineTreeView


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
        from random import shuffle

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


    def __init__(self, files=None, position=0.0):
        # Create dialog class
        QDialog.__init__(self)

        # Load UI from Designer
        ui_util.load_ui(self, self.ui_path)

        # Init UI
        ui_util.init_ui(self)

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
            self.cmbTrack.addItem(_('Track %s' % track.data['number']), track.data['id'])

        # Add all fade options
        self.cmbFade.addItem(_('None'), 0)
        self.cmbFade.addItem(_('Fade In'), 1)
        self.cmbFade.addItem(_('Fade Out'), 2)
        self.cmbFade.addItem(_('Fade In & Out'), 3)

        # Add all transitions
        transitions_dir = os.path.join(info.PATH, "transitions")
        common_dir = os.path.join(transitions_dir, "common")
        extra_dir = os.path.join(transitions_dir, "extra")
        transition_groups = [{"type": "common", "dir": common_dir, "files": os.listdir(common_dir)},
                             {"type": "extra", "dir": extra_dir, "files": os.listdir(extra_dir)}]

        self.cmbTransition.addItem(_('None'), None)
        self.cmbTransition.addItem(_('Random'), 'random')
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
                self.cmbTransition.addItem(QIcon(thumb_path), _(trans_name), filename)

        # Connections
        self.btnMoveUp.clicked.connect(self.btnMoveUpClicked)
        self.btnMoveDown.clicked.connect(self.btnMoveDownClicked)
        self.btnShuffle.clicked.connect(self.btnShuffleClicked)
        self.btnRemove.clicked.connect(self.btnRemoveClicked)
        self.btnBox.accepted.connect(self.accept)
        self.btnBox.rejected.connect(self.reject)