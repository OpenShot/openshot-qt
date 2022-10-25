"""
 @file export_clips.py
 @brief Behavior for the export clips dialog.
 @details
 Takes an array of file objects

 Allow the user to select a directory to export to.
 Then export any clips and files to that directory

 To save time, (and preserve video quality)
 Any files should only be copied
 If a clip name already exists, skip that clip.
 @author Jackson Godwin <jackson@openshot.org>

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
from PyQt5.QtWidgets import QPushButton, QDialog, QDialogButtonBox, QLabel, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt
from classes import ui_util
from classes import info
from classes.app import get_app
from classes.logger import log
import openshot, os, re, shutil


_ = get_app()._tr

def makeLegalFileName(s: str):
    # Regex taken from django's slugify function
    # https://github.com/django/django/blob/main/django/utils/text.py
    s = re.sub(r'[^\w\s-]', '', s.lower())
    return s.strip() #clean leading or trailing spaces

def copyFileToFolder(f , destination_folder: str):
    """Takes a file object, gives it a suffix, and copies it"""
    new_file_path = nameOfExport(f)
    if os.path.exists(new_file_path):
        return
    log.info(f"copying {f.data.get('path')} to {os.path.join( destination_folder, new_file_path )}")
    shutil.copy(f.data.get("path"), os.path.join( destination_folder, new_file_path ))

def notClip(file_obj):
    return not isClip(file_obj)

def isClip(file_object) -> bool:
    if "start" in file_object.data\
       and "end" in file_object.data:
        return True
    return False

def nameOfExport(file_obj) -> str:
    if isClip(file_obj):
        backup_name = os.path.splitext(file_obj.data.get("path", "openshot_clip"))[0]
        name = file_obj.data.get("name", backup_name)
        name = makeLegalFileName(name)
        name += f" [{format(file_obj.data.get('start'), '.2f')} - {format(file_obj.data.get('end'), '.2f')}]"
        # When we support audio-only exports
        # ext = "mp4" if file_obj.data.get("has_video") else "mp3"
        name += ".mp4"
        return name
    else:
        name, ext = os.path.splitext(os.path.split(file_obj.data.get("path"))[1])
        name = makeLegalFileName(name)
        fps = file_obj.data.get("fps")
        fps = int(fps.get("num")) / int(fps.get("den"))
        length_in_seconds = int(file_obj.data.get("video_length",0)) / fps
        suffix = f"[0.00 - {format(length_in_seconds, '.2f')}]"
        return f"{name} {suffix}{ext}"

def framesInClip(cl):
    fps = cl.data.get("fps").get("num") / cl.data.get("fps").get("den")
    seconds = cl.data.get('end') - cl.data.get('start')
    return seconds * fps + 1

def startAndEndFrames(clip):
    timeToFrame = lambda t, fps: round((t * fps) + 1)
    fps = clip.data.get("fps").get("num") / clip.data.get("fps").get("den")
    start_time = clip.data.get("start")
    end_time = clip.data.get("end")
    return (timeToFrame(start_time, fps), timeToFrame(end_time, fps))

def setupWriter(clip, writer):
    # TODO: allow for audio clips
    # Set video options
    pr = clip.data.get("pixel_ratio", {"num": 1, "den": 1})
    pixel_ratio = openshot.Fraction(pr.get("num"), pr.get("den"))
    fps = clip.data.get("fps", {"num": 30, "den": 1})
    frames_per_second = openshot.Fraction(fps.get("num",1), fps.get("den",1))

    writer.SetVideoOptions(True,
                           "libx264",
                           frames_per_second,
                           clip.data.get("width", 1280),
                           clip.data.get("height", 720),
                           pixel_ratio,
                           False,
                           False,
                           22)
    writer.PrepareStreams()
    # Set audio options
    writer.SetAudioOptions(True,
                           "aac",
                           clip.data.get("sample_rate", 48000),
                           clip.data.get("channels", 2),
                           clip.data.get("channel_layout", 3),
                           clip.data.get("audio_bit_rate", 192000) )
    writer.PrepareStreams()
    writer.Open()

class clipExportWindow(QDialog):
    """A popup to export clips as mp4 files
    in a folder of the user's choosing"""
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'export-clips.ui')

    exporting = False # Changes whether cancel button closes,
        # or waits for export to close the writers
    canceled = False

    def __init__(self, export_clips_arg, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ui_util.load_ui(self, self.ui_path)
        ui_util.init_ui
        self.file_objs = export_clips_arg
        self._getDestination()
        self._createWidgets()

    def _getDestination(self):
        settings = get_app().get_settings()
        fd = QFileDialog()
        fd.setOption(QFileDialog.ShowDirsOnly)
        fd.setDirectory(
            settings.getDefaultPath(settings.actionType.EXPORT)
        )
        chosen_destination = fd.getExistingDirectory()

        # if dialog is canceled, use default path
        if chosen_destination:
            self.export_destination = chosen_destination
            settings.setDefaultPath(settings.actionType.EXPORT, self.export_destination)
        else:
            self.export_destination = settings.getDefaultPath(settings.actionType.EXPORT)

    def _createWidgets(self):
        self.FilePickerArea.addWidget(QLabel(_("Export To %s") % self.export_destination))
        self.export_button = QPushButton(_("Export"))
        self.export_button.clicked.connect(self._exportPressed)
        self.done_button = QPushButton(_("Done"))
        self.done_button.clicked.connect(self.done)
        self.cancel_button = QPushButton(_("Cancel"))
        self.cancel_button.clicked.connect(self._cancelButtonClicked)

        # Make progress bar look like the one in the export dialog
        from PyQt5.QtGui import QPalette
        p = QPalette()
        p.setColor(QPalette.Highlight, Qt.green)
        self.progressExportVideo.setPalette(p)

        self.buttonBox.addButton(self.cancel_button, QDialogButtonBox.ActionRole)
        self.buttonBox.addButton(self.export_button, QDialogButtonBox.ActionRole)
        self.buttonBox.addButton(self.done_button, QDialogButtonBox.ActionRole)
        self.done_button.setHidden(True)
        self.progressExportVideo.setValue(0)

    def _cancelButtonClicked(self):
        if self.exporting:
            self.canceled = True
        else:
            self.done(0)

    def _exportPressed(self):
        clips = list(filter(isClip, self.file_objs))
        files = list(filter(notClip, self.file_objs))
        # Total number of frames
        self._updateDialogExportStarting()
        total_frames, frames_written = 0, 0
        for c in clips:
            total_frames += framesInClip(c)
        for f in files:
            total_frames += int(f.data.get("video_length",0))
        for f in files:
            copyFileToFolder(f, self.export_destination)
            frames_written+=int(f.data.get("video_length",0))
        for c in clips:
            export_path = os.path.join(self.export_destination, f"{nameOfExport(c)}")
            if(os.path.exists(export_path)):
                log.info("Export path exists. Skipping render")
                frames_written += framesInClip(c)
                self._updateProgressBar(frames_written, total_frames)
                get_app().processEvents()
                continue
            w = openshot.FFmpegWriter(export_path)
            try:
                setupWriter(c, w)
            except Exception as ex:
                log.error("Error Exporting Clip: "+str(ex))
                QMessageBox.warning(self, _("Error Exporting Clip"),
                                    _("The following error occurred while exporting this clip: \n%s") % str(ex))
                log.info("Removing this clip from total_frames")
                total_frames -= int(framesInClip(c))
                if os.path.exists(export_path):
                    log.info("Removing incomplete file %s" % export_path)
                    os.remove(export_path)
                continue

            start_frame, end_frame = startAndEndFrames(c)

            clip_reader = openshot.Clip(c.data.get("path"))
            clip_reader.Open()

            log.info(f"Starting to write frames to {export_path}")
            for frame in range(start_frame, end_frame):
                w.WriteFrame(clip_reader.GetFrame(frame))
                if frame % 5 == 0:
                    self._updateProgressBar(frames_written, total_frames)
                    get_app().processEvents()
                frames_written += 1
                if self.canceled:
                    log.info("Export Canceled. Deleting partial export")
                    os.remove(export_path)
                    break
            clip_reader.Close()
            w.Close()
            if self.canceled:
                log.info("Reader and Writer closed. Exiting Dialog")
                self.done(0)
                break
            log.info("Finished Exporting Clip: %s" % export_path)
        log.info("Finished exporting")
        self._updateProgressBar(frames_written, total_frames)
        self._updateDialogExportFinished()

    def _updateProgressBar(self, count: int, total: int):
        if total==0:
            log.info("Total:frames is 0")
            # Only reason this should happen is if the only clip
            # Has an error.
                # I consider error'ed clips "done" so the user doesn't
                # mistakenly wait on a progress bar.
            self.progressExportVideo.setValue(100)
            return # Prevent division by zero
        d = count - total
        if -2 <= d and 2 >= d:
            # If within 2 frames of complete, show 100 percent.
            self.progressExportVideo.setValue(100)
            return
        self.progressExportVideo.setValue(round((count/total) * 100))

    def _updateDialogExportFinished(self):
        self.progressExportVideo.setValue(100)
        self.setWindowTitle(_("Done"))
        self.cancel_button.hide()
        self.done_button.setHidden(False)
        self.done_button.setFocus()
        self.exporting=False
        log.info("Finished exporting")

    def _updateDialogExportStarting(self):
        self.exporting=True
        self.export_button.hide()
        self.setWindowTitle(_("Exporting"))
