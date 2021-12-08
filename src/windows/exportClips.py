from PyQt5.QtWidgets import QPushButton, QDialog, QDialogButtonBox
from PyQt5.QtCore import Qt
from classes.filePicker import filePicker
from classes import ui_util
from classes import info
from classes.app import get_app
from classes.logger import log
import os

_ = get_app()._tr


def export_name(clip):
    # Name clips with a suffix of their start and end time.
    # strip clip names of any characters not legal in file names
    name = clip.data.get("name")
    name += f" [{format(clip.data.get('start'), '.2f')} to {format(clip.data.get('end'), '.2f')}]"
    # if a file, not a clip:
    # append [ 0.00 to {flile length} ]
    return name

def setupWriter(clip, writer):
    import openshot
    export_type = "Video & Audio"
    # Set video options
    if export_type in [_("Video & Audio"), _("Video Only"), _("Image Sequence")]:
        writer.SetVideoOptions(True,
                               "libx264",
                               openshot.Fraction(clip.data.get("fps").get("num"),
                                                 clip.data.get("fps").get("den")),
                               clip.data.get("width"),
                               clip.data.get("height"),
                               openshot.Fraction(clip.data.get("pixel_ratio").get("num"),
                                                 clip.data.get("pixel_ratio").get("den")),
                               False,
                               False,
                               22
                               )
        # Set audio options
    if export_type in [_("Video & Audio"), _("Audio Only")]:
        writer.SetAudioOptions(True,
                               clip.data.get("acodec", "aac"),
                               clip.data.get("sample_rate"),
                               clip.data.get("channels"),
                               clip.data.get("channel_layout"),
                               clip.data.get("audio_bit_rate"))

class clipExportWindow(QDialog):
    """A popup to export clips as mp4 files
    in a folder of the user's choosing"""
    fp: filePicker
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'exportClips.ui')

    def __init__(self, export_clips_arg, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ui_util.load_ui(self, self.ui_path)
        ui_util.init_ui
        self.export_clips = export_clips_arg
        self._create_widgets()

    def _create_widgets(self):
        self.fp = filePicker(folder_only=True, export_clips=self.export_clips)
        self.export_button = QPushButton(_("Export"))
        self.export_button.clicked.connect(self._export_pressed)
        self.close_button = QPushButton(_("Close"))
        self.close_button.clicked.connect(self.done)
        self.cancel_button = QPushButton(_("Cancel"))
        self.cancel_button.clicked.connect(self._cancel_button_cicked)

        from PyQt5.QtGui import QPalette
        p = QPalette()
        p.setColor(QPalette.Highlight, Qt.green)

        self.buttonBox.addButton(self.export_button, QDialogButtonBox.ActionRole)
        self.buttonBox.addButton(self.cancel_button, QDialogButtonBox.ActionRole)
        self.buttonBox.addButton(QDialogButtonBox.Close).clicked.connect(lambda: self.done(0))
        self.FilePickerArea.addWidget(self.fp)
        self.progressExportVideo.setValue(0)

    def setPath(self, p: str):
        self.fp.setPath(p)

    def _cancel_button_cicked(self):
        self.exporting = False

    def _update_progress_bar(self, count: int, total: int):
        d = count - total
        if -2 <= d and 2 >= d:
            self.progressExportVideo.setValue(100)
            return
        self.progressExportVideo.setValue((count/total) * 100)

    def _export_pressed(self):
        if ( not self.export_clips ):
            return
        import openshot, os
        def framesInClip(cl):
            fps = cl.data.get("fps").get("num") / cl.data.get("fps").get("den")
            seconds = cl.data.get('end') - cl.data.get('start')
            return seconds * fps + 1

        # Total number of frames
        totalFrames, currentFrame = 0, 0
        self.exporting=True
        self.buttonBox.button(QDialogButtonBox.Close).setEnabled(False)
        get_app().processEvents()
        for c in self.export_clips:
            totalFrames += framesInClip(c)

        for c in self.export_clips:
            file_path = c.data.get("path")
            extension = "mp4"
            project_folder = self.fp.getPath()
            export_path = os.path.join(project_folder, f"{export_name(c)}.{extension}")
            # TODO: If that path exists, don't export over-top of it
            # TODO: If it's a file, just copy it to the destination folder
            w = openshot.FFmpegWriter(export_path)

            setupWriter(c, w)
            w.PrepareStreams()
            w.Open()

            start_time = c.data.get("start")
            end_time = c.data.get("end")
            fps = c.data.get("fps").get("num") / c.data.get("fps").get("den")
            start_frame, end_frame = int(start_time * fps), int(end_time*fps)

            # Or a file reader, and do the math for the first/last frame
            clip_reader = openshot.Clip(file_path)
            clip_reader.Open()

            log.info(f"Starting to write frames to {export_path}")
            for frame in range(start_frame+1, end_frame+1):
                w.WriteFrame(clip_reader.GetFrame(frame))
                if frame % 5 == 0:
                    self._update_progress_bar(currentFrame, totalFrames)
                    get_app().processEvents()
                currentFrame += 1
                if not self.exporting:
                    break
            self._update_progress_bar(currentFrame, totalFrames)
            clip_reader.Close()
            w.Close()
            log.info("Finished Exporting Clip: %s" % export_path)
        self.export_button.hide()
        self.cancel_button.hide()
        self.buttonBox.button(QDialogButtonBox.Close).setEnabled(True)
