"""
 @file
 @brief This file contains the preview thread, used for displaying previews of the timeline
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

import time
import threading
import math
import json
import traceback

from qt_api import QObject, QThread, QTimer, pyqtSlot, pyqtSignal, QCoreApplication
from qt_api import QMessageBox
from qt_api import unwrapinstance, wrapinstance, _is_android_runtime
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes.app import get_app
from classes.logger import log
from classes.updates import UpdateInterface
from windows.scope_panel import build_vectorscope_image, normalize_vectorscope_display


class PreviewParent(QObject, UpdateInterface):
    """ Class which communicates with the PlayerWorker Class (running on a separate thread) """

    def changed(self, action):
        """ This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface) """

        # Ignore changes that don't affect libopenshot
        if action and len(action.key) >= 1 and action.key[0].lower() in ["files", "history", "markers", "layers", "scale", "profile", "sample_rate", "export_settings"]:
            return

        if not getattr(self, "_use_timeline_sync_max", True):
            return

        try:
            # Keep track of max timeline frame # on any updates to the timeline.
            self.timeline_max_length = max(1, int(get_app().window.timeline_sync.GetLastFrame() or 1))
            log.debug(f"Max timeline length/frames detected: {self.timeline_max_length}")
        except Exception as e:
            log.info("Error calculating max timeline length on PreviewParent: %s. %s" % (e, action.json(is_array=True)))

    # Signal when the frame position changes in the preview player
    def onPositionChanged(self, current_frame):
        timeline_last_frame = max(1, int(getattr(self, "timeline_max_length", 1) or 1))
        self.parent.movePlayhead(max(1, int(current_frame)))

        # Check if we are at the end of the timeline
        if self.worker.player.Mode() == openshot.PLAYBACK_PLAY:
            loop_preview = bool(getattr(self.parent, "loop_playback", False))
            if self.worker.player.Speed() > 0.0 and current_frame >= timeline_last_frame:
                if loop_preview:
                    # Loop preview playback back to the beginning.
                    self.worker.Seek(1)
                else:
                    # Yes, pause the video
                    self.parent.PauseSignal.emit()
                    # If the player got past the end of the project, go back.
                    self.worker.Seek(timeline_last_frame)
            if self.worker.player.Speed() < 0.0 and current_frame <= 1:
                if loop_preview:
                    # Loop rewind to the end frame.
                    self.worker.Seek(timeline_last_frame)
                else:
                    # If rewinding, and the player got past the first frame,
                    # pause and go to frame 1
                    self.parent.PauseSignal.emit()
                    self.worker.Seek(1)

    @pyqtSlot(int)
    @pyqtSlot(int, bool)
    def QueueSeek(self, frame, start_preroll=True):
        """Queue latest seek request for worker loop (non-blocking)."""
        self.worker.queue_seek(frame, start_preroll)

    # Signal when the playback mode changes in the preview player (i.e PLAY, PAUSE, STOP)
    def onModeChanged(self, current_mode):
        try:
            if current_mode == openshot.PLAYBACK_PLAY:
                self.parent.SetPlayheadFollow(False)
            else:
                self.parent.SetPlayheadFollow(True)
        except AttributeError:
            # Parent object doesn't need the playhead follow code
            pass

    # Signal when the playback encounters an error
    def onError(self, error):
        # Get translation object
        _ = get_app()._tr

        # Only JUCE audio errors bubble up here now
        QMessageBox.warning(self.parent, _("Audio Error"), _("Please fix the following error and restart OpenShot\n%s") % error)

    def Stop(self, wait_for_thread=True):
        """Disconnect preview parent from update manager and stop worker thread"""
        get_app().updates.disconnect_listener(self)

        # Stop preview thread
        self.worker.Stop()
        self.worker.kill()
        if self.background.isRunning():
            log.info("Stopping preview thread (running=%s)", self.background.isRunning())
        self.background.quit()
        if wait_for_thread:
            if not self.background.wait(5000):
                log.warning("Preview thread did not stop within 5 seconds")

    @pyqtSlot(object, object)
    def Init(self, parent, timeline, video_widget, max_length=1):
        # Important vars
        self.parent = parent
        self.timeline = timeline
        try:
            max_len = max(1, int(max_length))
        except (TypeError, ValueError):
            max_len = 1

        # Dialog previews (Split File / Region) pass their own max_length and
        # should not be clamped by the main timeline's last frame.
        self._use_timeline_sync_max = max_len <= 1
        if self._use_timeline_sync_max and getattr(get_app().window, "timeline_sync", None):
            self.timeline_max_length = max(1, int(get_app().window.timeline_sync.GetLastFrame() or 1))
        else:
            self.timeline_max_length = max_len

        # Background Worker Thread (for preview video process)
        self.background = QThread(self)
        self.background.setObjectName("preview_background")
        self.worker = PlayerWorker()  # no parent!

        # Init worker variables
        self.worker.Init(parent, timeline, video_widget)

        # Hook up signals to Background Worker
        self.worker.position_changed.connect(self.onPositionChanged)
        self.worker.mode_changed.connect(self.onModeChanged)
        if hasattr(self.parent, "_preview_ready"):
            self.worker.ready.connect(self.parent._preview_ready)
        if hasattr(self.parent, "_preview_mode_changed"):
            self.worker.mode_changed.connect(self.parent._preview_mode_changed)
        self.background.started.connect(self.worker.Start)
        self.worker.finished.connect(self.background.quit)
        self.worker.error_found.connect(self.onError)

        # Connect preview thread to main UI signals
        self.parent.previewFrameSignal.connect(self.worker.previewFrame)
        self.parent.refreshFrameSignal.connect(self.worker.refreshFrame)
        self.parent.LoadFileSignal.connect(self.worker.LoadFile)
        if hasattr(self.parent, "LoadFilePreviewSignal"):
            self.parent.LoadFilePreviewSignal.connect(self.worker.LoadFilePreview)
        self.parent.PlaySignal.connect(self.worker.Play)
        self.parent.PauseSignal.connect(self.worker.Pause)
        self.parent.SeekSignal.connect(self.QueueSeek)
        self.parent.LoadTimelineAndSeekSignal.connect(self.worker.LoadTimelineAndSeek)
        self.parent.SpeedSignal.connect(self.worker.Speed)
        self.parent.StopSignal.connect(self.worker.Stop)
        if hasattr(self.parent, "RunScopeSignal"):
            self.parent.RunScopeSignal.connect(self.worker.queue_scope_analysis)
            self.worker.scope_ready.connect(self.parent._on_scope_ready)

        # Move Worker to new thread, and Start
        self.worker.moveToThread(self.background)
        self.background.start()

        # Add preview parent as listener for updates
        get_app().updates.add_listener(self)


class PlayerWorker(QObject):
    """ QT Player Worker Object (to preview video on a separate thread) """

    position_changed = pyqtSignal(int)
    mode_changed = pyqtSignal(object)
    error_found = pyqtSignal(object)
    ready = pyqtSignal()
    finished = pyqtSignal()
    scope_ready = pyqtSignal(int, dict, dict)

    @pyqtSlot(object, object)
    def Init(self, parent, timeline, videoPreview):
        self.parent = parent
        self.timeline = timeline
        self.videoPreview = videoPreview
        self.clip_path = None
        self.clip_reader = None
        self.original_speed = 0
        self.original_position = 0
        self.previous_clips = []
        self.previous_clip_readers = []
        self.is_running = True
        self.number = None
        self.current_frame = None
        self.current_mode = None
        self.reader_mode = "timeline"
        self.preview_stretch = False
        self._seek_lock = threading.Lock()
        self._pending_seek = None
        self._last_queued_seek_request = None
        self._last_applied_seek_request = None
        self._last_applied_seek_time = 0.0
        self._scope_lock = threading.Lock()
        self._pending_scope_request = None
        self._scope_analysis_active = False

        # Create QtPlayer class from libopenshot
        self.player = openshot.QtPlayer()

    def CheckAudioDevice(self):
        """Check if any audio devices initialization errors, default sample rate, and current open audio device"""
        s = get_app().get_settings()
        project = get_app().project

        def update_project_sample_rate_without_dirty(value):
            """Normalize startup audio settings without changing project dirty state."""
            previous_dirty = project.has_unsaved_changes
            get_app().updates.update_untracked(["sample_rate"], value)
            project.has_unsaved_changes = previous_dirty

        # Check audio init error
        audio_error = self.player.GetError()
        if audio_error:
            log.warning('Audio initialization error: %s', audio_error)
            self.error_found.emit(audio_error)

        # Check active sample rate from audio device
        # Parse string as float ("48000.0" -> 48000   OR   NaN)
        detected_sample_rate = float(self.player.GetDefaultSampleRate())
        if detected_sample_rate and not math.isnan(detected_sample_rate) and detected_sample_rate > 0.0:
            # Convert float to Integer
            detected_sample_rate_int = round(detected_sample_rate)

            settings_sample_rate = int(s.get("default-samplerate") or 48000)
            if detected_sample_rate_int != settings_sample_rate:
                log.warning("Your sample rate (%d) does not match OpenShot (%d). "
                            "Adjusting your 'Preferences->Preview->Default Sample Rate to match your "
                            "system rate: %d." % (detected_sample_rate_int,
                                                  settings_sample_rate,
                                                  detected_sample_rate_int))

                # Update default sample rate in settings
                s.set("default-samplerate", detected_sample_rate_int)

                # Update current project's sample rate, so we don't have some crazy
                # audio drift due to mis-matching sample rates
                update_project_sample_rate_without_dirty(detected_sample_rate_int)

        # Convert float 'settings' sample rate to Integer, if detected
        if type(s.get("default-samplerate")) == float:
            if detected_sample_rate_int is None:
                detected_sample_rate_int = round(s.get("default-samplerate"))
            s.set("default-samplerate", detected_sample_rate_int)

        # Convert float 'project' sample rate to Integer, if detected
        if type(project.get("sample_rate")) == float:
            update_project_sample_rate_without_dirty(round(project.get("sample_rate")))

        # Check active audio device name and type from audio device
        active_audio_device = self.player.GetCurrentAudioDevice()
        audio_device_value = f"{active_audio_device.get_name()}||{active_audio_device.get_type()}"
        if s.get("playback-audio-device") != audio_device_value:
            log.warning("Your active audio device (%s) does not match OpenShot (%s). "
                        "Adjusting your 'Preferences->Playback->Audio Device' to match your "
                        "active audio device: %s" % (audio_device_value,
                                                     s.get("playback-audio-device"),
                                                     audio_device_value))
            s.set("playback-audio-device", audio_device_value)

            # Set libopenshot settings
            lib_settings = openshot.Settings.Instance()
            lib_settings.PLAYBACK_AUDIO_DEVICE_NAME = active_audio_device.get_name()
            lib_settings.PLAYBACK_AUDIO_DEVICE_TYPE = active_audio_device.get_type()

    @pyqtSlot()
    def Start(self):
        """ This method starts the video player """
        log.info("QThread Start Method Invoked")

        # Init new player
        self.initPlayer()

        # Connect player to timeline reader
        self.player.Reader(self.timeline)
        self.player.Play()
        self.player.Pause()
        self.ready.emit()

        # Check for any Player initialization errors (only JUCE errors bubble up here now)
        # But slightly delay, to allow for correct audio thread initialization with the
        # correct number of channels and sample rate
        QTimer.singleShot(1000, self.CheckAudioDevice)

        # Main loop, waiting for frames to process
        while self.is_running:
            seek_request = self._take_pending_seek()
            if seek_request is not None:
                seek_frame, start_preroll = seek_request
                self._apply_seek(seek_frame, start_preroll)

            # Emit position changed signal (if needed)
            if self.current_frame != self.player.Position():
                self.current_frame = self.player.Position()

                if not self.clip_path:
                    # Emit position of overall timeline (don't emit this for clip previews)
                    self.position_changed.emit(self.current_frame)

                    # TODO: Remove this hack and really determine what's blocking the main thread
                    # Try and keep things responsive
                    QCoreApplication.processEvents()

            # Emit mode changed signal (if needed)
            if self.player.Mode() != self.current_mode:
                self.current_mode = self.player.Mode()
                self.mode_changed.emit(self.current_mode)

            # wait for a small delay
            time.sleep(0.005)
            QCoreApplication.processEvents()

        self.finished.emit()
        log.debug('exiting playback thread')

    @pyqtSlot()
    def initPlayer(self):
        log.debug("initPlayer")

        # Get the address of the player's renderer (a QObject that emits signals when frames are ready)
        self.renderer_address = self.player.GetRendererQObject()
        self.renderer = None

        if _is_android_runtime():
            # Pass widget directly; C++ delivers frames via QMetaObject::invokeMethod.
            self.player.SetQWidget(self.videoPreview)
        else:
            # Pass raw pointer; connect C++ present() signal to Python slot.
            self.player.SetQWidget(unwrapinstance(self.videoPreview))
            self.renderer = wrapinstance(self.renderer_address, QObject)
            if self.renderer is not None:
                self.videoPreview.connectSignals(self.renderer)

    def kill(self):
        """ Kill this thread """
        self.is_running = False

    def previewFrame(self, number):
        """ Preview a certain frame """
        # Mark frame number for processing
        self.Seek(number)

    def refreshFrame(self):
        """ Refresh a certain frame """
        # Selection/UI refresh signals can arrive during active playback.
        # Avoid seeking while playing, which can perturb frame progression.
        if self.player.Mode() == openshot.PLAYBACK_PLAY and self.player.Speed() != 0.0:
            return

        # Always load back in the timeline reader
        self.parent.LoadFileSignal.emit('')

        # A refresh must not replace a user seek which the worker has not
        # applied yet (for example, the final seek after a keyframe drag).
        # Check and enqueue under the same lock as user seek requests.
        if not self.parent.initialized:
            return
        with self._seek_lock:
            if self._pending_seek is not None:
                return
            # Refreshes should not trigger preroll/cache invalidation behavior.
            request = (max(1, int(self.player.Position())), False)
            self._last_queued_seek_request = request
            self._pending_seek = request

    @pyqtSlot(int, bool, bool, bool, bool, object, object, object)
    def queue_scope_analysis(self, frame_number, need_waveform, need_histogram, need_vectorscope, need_audio, scope_region, waveform_render, vectorscope_render):
        with self._scope_lock:
            self._pending_scope_request = (
                frame_number, need_waveform, need_histogram, need_vectorscope,
                need_audio, scope_region, waveform_render, vectorscope_render,
            )
            if self._scope_analysis_active:
                return
            self._scope_analysis_active = True

        while True:
            with self._scope_lock:
                request = self._pending_scope_request
                self._pending_scope_request = None
            if not request:
                with self._scope_lock:
                    self._scope_analysis_active = False
                return
            self.run_scope_analysis(*request)

    def run_scope_analysis(self, frame_number, need_waveform, need_histogram, need_vectorscope, need_audio, scope_region, waveform_render, vectorscope_render):
        """Compute FrameScope data on the worker thread and emit scope_ready.

        Running here keeps scope analysis work off the UI thread.

        Channel key contract: libopenshot frames are stored as
        QImage::Format_RGBA8888_Premultiplied ([R=0, G=1, B=2, A=3]).
        FrameScope exposes per-channel data under the keys "red", "green",
        and "blue" matching that order. scope_panel.py reads those same keys.
        """
        timeline = getattr(getattr(get_app().window, "timeline_sync", None), "timeline", None)
        if not timeline:
            self.scope_ready.emit(frame_number, {}, {})
            return
        video, audio = {}, {}
        try:
            need_video = bool(need_waveform or need_histogram or need_vectorscope)
            frame = timeline.GetFrame(frame_number)
            scope = openshot.FrameScope()
            if need_waveform:
                waveform_settings = waveform_render if isinstance(waveform_render, dict) else {}
                try:
                    scope.SetWaveformColumns(max(32, int(waveform_settings.get("columns", 256) or 256)))
                except Exception as ex:
                    log.debug("Unable to set waveform column count: %s", ex)
            if need_vectorscope:
                is_playing = False
                try:
                    is_playing = self.player.Mode() == openshot.PLAYBACK_PLAY
                except Exception:
                    is_playing = self.current_mode == openshot.PLAYBACK_PLAY
                if is_playing:
                    playback_size = 96 if not (need_waveform or need_histogram) else 128
                    scope.SetVectorscopeSize(playback_size)
                else:
                    scope.SetVectorscopeSize(256)
            if need_video and isinstance(scope_region, dict):
                scope.SetVideoRegionNormalized(
                    float(scope_region.get("x", 0.0)),
                    float(scope_region.get("y", 0.0)),
                    float(scope_region.get("width", 0.0)),
                    float(scope_region.get("height", 0.0)),
                )
            scope.SetFrame(frame)
            if need_video:
                if scope.HasVideo():
                    video = {"present": True}
                    if need_waveform:
                        video["waveform"] = {
                            "columns": scope.GetWaveformColumns(),
                            "bins":    scope.GetWaveformBins(),
                            "luma":    list(scope.GetVideoWaveformLuma()),
                            "red":     list(scope.GetVideoWaveformRed()),
                            "green":   list(scope.GetVideoWaveformGreen()),
                            "blue":    list(scope.GetVideoWaveformBlue()),
                        }
                    if need_histogram:
                        video["histogram"] = {
                            "luma":  list(scope.GetVideoHistogramLuma()),
                            "red":   list(scope.GetVideoHistogramRed()),
                            "green": list(scope.GetVideoHistogramGreen()),
                            "blue":  list(scope.GetVideoHistogramBlue()),
                        }
                    if need_vectorscope:
                        render_settings = vectorscope_render if isinstance(vectorscope_render, dict) else {}
                        display = normalize_vectorscope_display(render_settings.get("display", "colorized"))
                        zoom_factor = {"100": 1.0, "200": 2.0, "400": 4.0}.get(
                            str(render_settings.get("zoom", "100")), 1.0)
                        vectorscope = {
                            "size": scope.GetVectorscopeSize(),
                            "density": [],
                        }
                        try:
                            vectorscope["density"] = list(scope.GetVideoVectorscope())
                        except Exception:
                            try:
                                root = json.loads(scope.Json())
                                vectorscope = root.get("video", {}).get("vectorscope", vectorscope)
                            except Exception as ex:
                                log.debug("Unable to read vectorscope data from scope JSON: %s", ex)
                        try:
                            vectorscope["image"] = build_vectorscope_image(
                                vectorscope.get("density", []),
                                int(vectorscope.get("size", 256) or 256),
                                zoom_factor,
                                display,
                            )
                        except Exception as ex:
                            log.debug("Unable to build vectorscope image: %s", ex)
                        video["vectorscope"] = vectorscope
                    video["summary"] = {
                        "avg_luma":           scope.GetVideoAverageLuma(),
                        "clipped_shadows":    scope.GetVideoClippedShadows(),
                        "clipped_highlights": scope.GetVideoClippedHighlights(),
                    }
                else:
                    video = {"present": False}
            if need_audio:
                if scope.HasAudio():
                    channels = scope.GetAudioChannels()
                    audio = {
                        "present":  True,
                        "channels": channels,
                        "summary": {
                            "peak":            list(scope.GetAudioPeakLevels()),
                            "rms":             list(scope.GetAudioRmsLevels()),
                            "clipped_samples": list(scope.GetAudioClippedSamples()),
                        },
                        "waveform": {
                            "min": [list(scope.GetAudioWaveformMin(ch)) for ch in range(channels)],
                            "max": [list(scope.GetAudioWaveformMax(ch)) for ch in range(channels)],
                        },
                    }
                else:
                    audio = {"present": False}
        except Exception:
            log.error("Scope analysis failed for frame %s\n%s", frame_number, traceback.format_exc())
        self.scope_ready.emit(frame_number, video, audio)

    def LoadFile(self, path=None):
        """ Load a media file into the video player """
        self.LoadFilePreview(path, False)

    @pyqtSlot(str, bool)
    def LoadFilePreview(self, path=None, stretch=False):
        """Load a media file into the video player with optional stretch scaling."""
        # Check to see if this path is already loaded
        if path == self.clip_path:
            if self.reader_mode == "clip" and self.preview_stretch == bool(stretch):
                return
            if self.clip_reader:
                self.original_position = self.player.Position()
                self.player.Reader(self.clip_reader)
                self.reader_mode = "clip"
                self.preview_stretch = bool(stretch)
                self.Seek(1)
            return
        if not path and not self.clip_path and self.reader_mode == "timeline":
            return

        log.info("LoadFile %s" % path)

        # Determine the current frame of the timeline (when switching to a clip)
        seek_position = 1
        if path and not self.clip_path:
            # Track the current frame
            self.original_position = self.player.Position()

        # If blank path, switch back to self.timeline reader
        if not path:
            # Return to self.timeline reader
            log.debug("Set timeline reader again in player: %s" % self.timeline)
            self.player.Reader(self.timeline)
            self.reader_mode = "timeline"
            self.preview_stretch = False

            # Clear clip reader reference
            self.clip_reader = None
            self.clip_path = None

            # Switch back to last timeline position
            seek_position = self.original_position
        else:
            # Create new timeline reader (to preview selected clip)
            project = get_app().project

            # Get some settings from the project
            fps = project.get("fps")
            width = int(project.get("width"))
            height = int(project.get("height"))
            sample_rate = int(project.get("sample_rate"))
            channels = int(project.get("channels"))
            channel_layout = int(project.get("channel_layout"))
            timeline_sync = getattr(get_app().window, "timeline_sync", None)
            preview_width = getattr(getattr(timeline_sync, "timeline", None), "preview_width", 0)
            preview_height = getattr(getattr(timeline_sync, "timeline", None), "preview_height", 0)

            # Create an instance of a libopenshot Timeline object
            self.clip_reader = openshot.Timeline(width, height,
                                                 openshot.Fraction(fps["num"], fps["den"]),
                                                 sample_rate, channels, channel_layout)
            self.clip_reader.info.channel_layout = channel_layout
            self.clip_reader.info.has_audio = True
            self.clip_reader.info.has_video = True
            self.clip_reader.info.video_length = 999999
            self.clip_reader.info.duration = 999999
            self.clip_reader.info.sample_rate = sample_rate
            self.clip_reader.info.channels = channels
            if preview_width and preview_height:
                self.clip_reader.SetMaxSize(int(preview_width), int(preview_height))

            try:
                # Add clip for current preview file
                new_clip = openshot.Clip(path)
                try:
                    if new_clip.Reader().info.has_video:
                        self.clip_reader.info.has_audio = False
                        new_clip.Reader().info.has_audio = False
                except Exception:
                    log.debug("Failed to check has_video on clip reader for %s", path)
                if stretch:
                    new_clip.scale = openshot.SCALE_STRETCH
                    new_clip.gravity = openshot.GRAVITY_CENTER
                self.clip_reader.AddClip(new_clip)
            except:
                log.warning('Failed to load media file into video player: %s' % path)

            # Assign new clip_reader
            self.clip_path = path
            self.reader_mode = "clip"
            self.preview_stretch = bool(stretch)

            # Keep track of previous clip readers (so we can Close it later)
            self.previous_clips.append(new_clip)
            self.previous_clip_readers.append(self.clip_reader)

            # Open and set reader
            self.clip_reader.Open()
            self.player.Reader(self.clip_reader)

        # Close and destroy old clip readers (leaving the 3 most recent)
        while len(self.previous_clip_readers) > 3:
            log.debug('Removing old clips from preview: %s' % self.previous_clip_readers[0])
            previous_clip = self.previous_clips.pop(0)
            previous_clip.Close()
            previous_reader = self.previous_clip_readers.pop(0)
            previous_reader.Close()

        # Seek to frame 1, and resume speed
        if not path:
            QTimer.singleShot(0, lambda: self.Seek(seek_position))
        else:
            self.Seek(seek_position)

    def Play(self):
        """ Start playing the video player """

        # Start playback
        if self.parent.initialized:
            pending = self._take_pending_seek()
            if pending is not None:
                seek_frame, start_preroll = pending
                self._apply_seek(seek_frame, start_preroll)
            self.player.Play()

    def Pause(self):
        """ Pause the video player """

        # Pause playback
        if self.parent.initialized:
            self.player.Pause()

    def Stop(self):
        """ Stop the video player and terminate the playback threads """

        # Stop playback
        if getattr(self, "player", None):
            self.player.Stop()

    def queue_seek(self, number, start_preroll=True):
        """Queue latest seek request (latest-wins, thread-safe)."""
        if not self.parent.initialized:
            return
        frame = max(1, int(number))
        seek_request = (frame, bool(start_preroll))

        now = time.monotonic()

        # Drop immediate duplicate seeks (same frame + preroll) that can be
        # generated by UI signal fan-out during scrubbing/commit boundaries.
        if (
            self._last_applied_seek_request == seek_request
            and (now - self._last_applied_seek_time) < 0.03
        ):
            return
        with self._seek_lock:
            if self._last_queued_seek_request == seek_request:
                return
            self._last_queued_seek_request = seek_request
            self._pending_seek = seek_request

    def _take_pending_seek(self):
        with self._seek_lock:
            seek_request = self._pending_seek
            self._pending_seek = None
            if seek_request is not None:
                # Reset dedup key once the queued seek is consumed so future
                # refreshes at the same frame can trigger another render.
                self._last_queued_seek_request = None
            return seek_request

    def _apply_seek(self, frame, start_preroll):
        try:
            self.player.Seek(frame, start_preroll)
        except TypeError:
            # Backward compatibility with older libopenshot builds exposing
            # only Seek(frame).
            self.player.Seek(frame)
        self._last_applied_seek_request = (int(max(1, frame)), bool(start_preroll))
        self._last_applied_seek_time = time.monotonic()
        # Force the main loop to publish a fresh position_changed event after
        # each seek so timeline playheads stay in sync with queued seeks.
        self.current_frame = None

    @pyqtSlot(int)
    @pyqtSlot(int, bool)
    def Seek(self, number, start_preroll=True):
        """Seek to a specific frame (queued for worker loop application)."""
        self.queue_seek(number, start_preroll)

    @pyqtSlot(int)
    def LoadTimelineAndSeek(self, frame):
        frame = max(1, int(frame))
        self.original_position = frame
        if self.timeline:
            self.player.Reader(self.timeline)
            self.reader_mode = "timeline"
            self.clip_reader = None
            self.clip_path = None
        self.Seek(frame)

    def Speed(self, new_speed):
        """ Set the speed of the video player """

        # Set speed
        if self.parent.initialized and self.player.Speed() != new_speed:
            self.player.Speed(new_speed)
