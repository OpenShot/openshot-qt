/**
 * @file
 * @brief Clip directives (draggable & resizable functionality)
 * @author Jonathan Thomas <jonathan@openshot.org>
 * @author Cody Parker <cody@yourcodepro.com>
 *
 * @section LICENSE
 *
 * Copyright (c) 2008-2018 OpenShot Studios, LLC
 * <http://www.openshotstudios.com/>. This file is part of
 * OpenShot Video Editor, an open-source project dedicated to
 * delivering high quality video editing and animation solutions to the
 * world. For more information visit <http://www.openshot.org/>.
 *
 * OpenShot Video Editor is free software: you can redistribute it
 * and/or modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation, either version 3 of the
 * License, or (at your option) any later version.
 *
 * OpenShot Video Editor is distributed in the hope that it will be
 * useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 */


/*global setSelections, setBoundingBox, moveBoundingBox, bounding_box, drawAudio, updateDraggables, snapToFPSGridTime */
// Init variables
var dragging = false;
var resize_disabled = false;
var previous_drag_position = null;
var start_clips = {};
var move_clips = {};
var track_container_height = -1;

// Treats element as a clip
// 1: can be dragged
// 2: can be resized
// 3: class change when hovered over
var dragLoc = null;

/*global App, timeline, moveBoundingBox*/
App.directive("tlClip", function ($timeout) {
  return {
    scope: "@",
    link: function (scope, element, attrs) {
      var timing_original_start = 0.0;
      var timing_original_end = 0.0;
      var timing_original_audio = null;
      var timing_original_duration = 0.0;

      function toNumber(value, fallback) {
        var parsed = parseFloat(value);
        return isNaN(parsed) ? fallback : parsed;
      }

      function resampleWaveform(data, originalDuration, newDuration) {
        if (!Array.isArray(data) || data.length === 0) {
          return null;
        }
        if (!isFinite(originalDuration) || !isFinite(newDuration) || originalDuration <= 0 || newDuration <= 0) {
          return null;
        }
        if (data.length === 1) {
          return [data[0]];
        }
        var newLength = Math.max(1, Math.round(data.length * (newDuration / originalDuration)));
        if (newLength === data.length) {
          return data.slice();
        }
        var result = new Array(newLength);
        var maxSourceIndex = data.length - 1;
        for (var i = 0; i < newLength; i++) {
          var t = newLength === 1 ? 0 : i / (newLength - 1);
          var sourcePos = t * maxSourceIndex;
          var idx0 = Math.floor(sourcePos);
          var idx1 = Math.min(maxSourceIndex, idx0 + 1);
          var frac = sourcePos - idx0;
          var value0 = data[idx0];
          var value1 = data[idx1];
          if (!isFinite(value0)) { value0 = 0; }
          if (!isFinite(value1)) { value1 = value0; }
          result[i] = value0 + (value1 - value0) * frac;
        }
        return result;
      }

      function snapTime(value) {
        if (typeof snapToFPSGridTime === "function") {
          return snapToFPSGridTime(scope, value);
        }
        return value;
      }

      function getTimePoints() {
        if (!scope.clip || !scope.clip.time) {
          return [];
        }
        var points = scope.clip.time.Points;
        return Array.isArray(points) ? points : [];
      }

      function hasTimeKeyframes() {
        return getTimePoints().length >= 2;
      }

      function isSingleImageClip() {
        if (!scope.clip) {
          return false;
        }
        if (scope.clip.has_single_image) {
          return true;
        }
        var mediaType = (scope.clip.media_type || "").toString().toLowerCase();
        if (mediaType === "image") {
          return true;
        }
        var reader = scope.clip.reader || {};
        if (reader.has_single_image) {
          return true;
        }
        var readerMediaType = (reader.media_type || "").toString().toLowerCase();
        return readerMediaType === "image";
      }

      /* The following functions are for displaying all keyframes during trimming/re-timing */
      function ensureKeyframePreviewContainer() {
        if (!scope.clip) {
          return null;
        }
        if (!scope.clip.ui) {
          scope.clip.ui = {};
        }
        var container = scope.clip.ui.keyframe_preview;
        if (!container || typeof container !== "object") {
          container = {};
          scope.clip.ui.keyframe_preview = container;
        }
        return container;
      }

      function scheduleKeyframePreviewDigest() {
        scope.$evalAsync(function () {
          scheduleKeyframePreviewRender();
        });
      }

      var keyframePreviewRaf = null;

      function resetKeyframePreviewState() {
        var preview = ensureKeyframePreviewContainer();
        if (!preview) {
          return;
        }
        var clipStart = snapTime(toNumber(scope.clip && scope.clip.start, 0));
        var clipEnd = snapTime(toNumber(scope.clip && scope.clip.end, clipStart));
        if (clipEnd < clipStart) {
          clipEnd = clipStart;
        }
        var duration = Math.max(clipEnd - clipStart, 0);
        preview.active = false;
        preview.mode = "";
        preview.originalStart = clipStart;
        preview.originalEnd = clipEnd;
        preview.originalDuration = duration;
        preview.displayStart = clipStart;
        preview.displayEnd = clipEnd;
        preview.displayDuration = duration;
        preview.projectedStart = clipStart;
        preview.projectedEnd = clipEnd;
        preview.pixelsPerSecond = scope.pixelsPerSecond;
      }

      function cancelKeyframePreviewRender() {
        if (keyframePreviewRaf === null) {
          return;
        }
        if (typeof window !== "undefined" && window.cancelAnimationFrame) {
          window.cancelAnimationFrame(keyframePreviewRaf);
        } else {
          clearTimeout(keyframePreviewRaf);
        }
        keyframePreviewRaf = null;
      }

      function scheduleKeyframePreviewRender() {
        if (keyframePreviewRaf !== null) {
          return;
        }
        var raf;
        if (typeof window !== "undefined" && window.requestAnimationFrame) {
          raf = window.requestAnimationFrame.bind(window);
        } else {
          raf = function (cb) {
            return setTimeout(cb, 16);
          };
        }
        keyframePreviewRaf = raf(function () {
          keyframePreviewRaf = null;
          renderKeyframePreview();
        });
      }

      // Position keyframes based on the current trim/retime preview window.
      function renderKeyframePreview() {
        if (!scope.clip || !scope.project) {
          return;
        }

        var preview = scope.clip.ui && scope.clip.ui.keyframe_preview ? scope.clip.ui.keyframe_preview : null;
        var points = element.find(".point");
        if (!points.length) {
          return;
        }

        if (!preview || !preview.active) {
          points.each(function () {
            var original = this.getAttribute("data-original-left");
            if (original !== null) {
              this.style.left = original;
              this.removeAttribute("data-original-left");
            }
          });
          return;
        }

        var pxPerSecond = toNumber(preview.pixelsPerSecond, toNumber(scope.pixelsPerSecond, 1));
        if (!isFinite(pxPerSecond) || pxPerSecond <= 0) {
          pxPerSecond = 1;
        }

        var fps_num = toNumber(scope.project.fps && scope.project.fps.num, 0);
        var fps_den = toNumber(scope.project.fps && scope.project.fps.den, 1);
        var frames_per_second = 0;
        if (fps_den !== 0) {
          frames_per_second = fps_num / fps_den;
        }
        if (!isFinite(frames_per_second) || frames_per_second <= 0) {
          frames_per_second = 1;
        }

        var clipStart = toNumber(scope.clip.start, 0);
        var displayStart = toNumber(preview.displayStart, clipStart);
        var displayEnd = toNumber(preview.displayEnd, displayStart);
        if (displayEnd < displayStart) {
          displayEnd = displayStart;
        }
        var displayDuration = Math.max(displayEnd - displayStart, 0);

        var originalStart = toNumber(preview.originalStart, clipStart);
        var originalEnd = toNumber(preview.originalEnd, originalStart);
        if (originalEnd < originalStart) {
          originalEnd = originalStart;
        }
        var originalDuration = Math.max(originalEnd - originalStart, 0);

        var hasRetimeMapping = preview.mode === "retime" && originalDuration > 0 && displayDuration > 0 && isFinite(originalDuration) && isFinite(displayDuration);

        points.each(function () {
          if (!this.hasAttribute("data-original-left")) { // capture original CSS once
            this.setAttribute("data-original-left", this.style.left || "");
          }

          var pointAttr = this.getAttribute("data-point");
          var frameValue = parseFloat(pointAttr);
          if (!isFinite(frameValue)) {
            return;
          }

          var frameSeconds = (frameValue - 1) / frames_per_second;
          if (!isFinite(frameSeconds)) {
            frameSeconds = 0;
          }

          var mappedSeconds = frameSeconds;
          if (hasRetimeMapping) { // stretch/scale keyframes in timing mode
            var normalized = (frameSeconds - originalStart) / originalDuration;
            if (!isFinite(normalized)) {
              normalized = 0;
            }
            mappedSeconds = displayStart + (normalized * displayDuration);
          }

          var relativeSeconds = mappedSeconds - displayStart;
          var newLeftPx = Math.round(relativeSeconds * pxPerSecond);
          this.style.left = newLeftPx + "px";
        });
      }

      function clearKeyframePreviewTransform() {
        cancelKeyframePreviewRender();
        element.find(".point").each(function () {
          if (this.hasAttribute("data-original-left")) {
            this.removeAttribute("data-original-left");
          }
        });
      }

      function startKeyframePreview(mode) {
        var container = ensureKeyframePreviewContainer();
        if (!container) {
          return;
        }

        var clipStart = snapTime(toNumber(scope.clip.start, 0));
        var clipEnd = snapTime(toNumber(scope.clip.end, clipStart));
        var originalStart = mode === "retime" ? snapTime(toNumber(timing_original_start, clipStart)) : clipStart;
        var originalEnd = mode === "retime" ? snapTime(toNumber(timing_original_end, clipEnd)) : clipEnd;

        container.active = true;
        container.mode = mode;
        container.originalStart = originalStart;
        container.originalEnd = originalEnd;
        container.originalDuration = Math.max(originalEnd - originalStart, 0);
        container.displayStart = clipStart;
        container.displayEnd = clipEnd;
        container.displayDuration = Math.max(container.displayEnd - container.displayStart, 0);
        if (mode === "trim") { // trim keeps absolute keyframe positions
          container.projectedStart = container.displayStart;
          container.projectedEnd = container.displayEnd;
        } else {
          container.projectedStart = container.originalStart;
          container.projectedEnd = container.originalEnd;
        }
        container.pixelsPerSecond = scope.pixelsPerSecond;
        scheduleKeyframePreviewDigest();
        renderKeyframePreview();
      }

      function updateKeyframePreview(displayStart, displayEnd) {
        var container = ensureKeyframePreviewContainer();
        if (!container || !container.active) {
          return;
        }

        var startSec = snapTime(toNumber(displayStart, container.displayStart));
        var endSec = snapTime(toNumber(displayEnd, startSec));
        if (endSec < startSec) {
          var temp = startSec;
          startSec = endSec;
          endSec = temp;
        }

        container.displayStart = startSec;
        container.displayEnd = endSec;
        container.displayDuration = Math.max(endSec - startSec, 0);

        if (container.mode === "trim") {
          container.projectedStart = container.displayStart;
          container.projectedEnd = container.displayEnd;
        } else {
          var originStart = toNumber(container.originalStart, startSec);
          var originEnd = toNumber(container.originalEnd, originStart);
          if (originEnd < originStart) {
            originEnd = originStart;
          }
          container.projectedStart = originStart;
          container.projectedEnd = originEnd;
        }

        container.pixelsPerSecond = scope.pixelsPerSecond;
        scheduleKeyframePreviewDigest();
        renderKeyframePreview();
      }

      function stopKeyframePreview() {
        var container = scope.clip && scope.clip.ui ? scope.clip.ui.keyframe_preview : null;
        if (container && container.active) {
          container.active = false;
        }
        scheduleKeyframePreviewDigest();
        clearKeyframePreviewTransform();
      }

      resetKeyframePreviewState();

      scope.$watch(function () {
        return scope.clip && scope.clip.id;
      }, function (newValue, oldValue) {
        if (!newValue || newValue === oldValue) {
          return;
        }
        resetKeyframePreviewState();
        clearKeyframePreviewTransform();
      });

      function getReaderDurationSeconds() {
        if (!scope.clip) {
          return 0;
        }
        var reader = scope.clip.reader || {};
        var duration = toNumber(reader.duration, NaN);
        if (!isNaN(duration) && duration > 0) {
          return duration;
        }
        var videoLength = toNumber(reader.video_length, NaN);
        var fps = reader.fps || {};
        var fpsNum = toNumber(fps.num, NaN);
        var fpsDen = toNumber(fps.den, NaN);
        if (!isNaN(videoLength) && !isNaN(fpsNum) && !isNaN(fpsDen) && fpsDen !== 0) {
          var fpsValue = fpsNum / fpsDen;
          if (fpsValue > 0) {
            return videoLength / fpsValue;
          }
        }
        var clipDuration = toNumber(scope.clip.duration, NaN);
        if (!isNaN(clipDuration) && clipDuration > 0) {
          return clipDuration;
        }
        var end = toNumber(scope.clip.end, 0);
        var start = toNumber(scope.clip.start, 0);
        return Math.max(end - start, 0);
      }

      function isResizeConstrained() {
        return !scope.enable_timing && !isSingleImageClip();
      }

      function getMaxDurationSeconds() {
        if (scope.enable_timing) {
          return null;
        }
        var retimed = getRetimedDurationSeconds();
        if (retimed !== null) {
          return retimed;
        }
        if (!isResizeConstrained()) {
          return null;
        }
        return getReaderDurationSeconds();
      }

      function getMaxClipEndSeconds() {
        var maxDuration = getMaxDurationSeconds();
        if (maxDuration === null || !isFinite(maxDuration)) {
          return null;
        }
        return toNumber(scope.clip.start, 0) + maxDuration;
      }

      function getRetimedDurationSeconds() {
        if (!hasTimeKeyframes()) {
          return null;
        }
        var points = getTimePoints();
        if (!points.length) {
          return null;
        }
        var fpsNum = toNumber(scope.project && scope.project.fps && scope.project.fps.num, NaN);
        var fpsDen = toNumber(scope.project && scope.project.fps && scope.project.fps.den, NaN);
        if (!isFinite(fpsNum) || !isFinite(fpsDen) || fpsDen === 0) {
          return null;
        }
        var fpsValue = fpsNum / fpsDen;
        if (!isFinite(fpsValue) || fpsValue <= 0) {
          return null;
        }
        var minFrame = Infinity;
        var maxFrame = -Infinity;
        points.forEach(function (point) {
          if (!point || !point.co) {
            return;
          }
          var frame = toNumber(point.co.X, NaN);
          if (isNaN(frame)) {
            return;
          }
          if (frame < minFrame) {
            minFrame = frame;
          }
          if (frame > maxFrame) {
            maxFrame = frame;
          }
        });
        if (!isFinite(minFrame) || !isFinite(maxFrame) || maxFrame <= minFrame) {
          return null;
        }
        var durationFrames = maxFrame - minFrame;
        if (!isFinite(durationFrames) || durationFrames <= 0) {
          return null;
        }
        return durationFrames / (fpsValue);
      }

      function getMaxResizeWidthPx() {
        var maxDuration = getMaxDurationSeconds();
        if (maxDuration === null || !isFinite(maxDuration)) {
          return null;
        }
        var startSec = toNumber(scope.clip.start, 0);
        var currentDuration = Math.max(0, toNumber(scope.clip.end, startSec) - startSec);
        var maxWidthSeconds = Math.max(maxDuration, currentDuration);
        return maxWidthSeconds * scope.pixelsPerSecond;
      }

      function updateMaxResizeWidth() {
        var maxWidth = getMaxResizeWidthPx();
        if (element.data("ui-resizable")) {
          element.resizable("option", "maxWidth", maxWidth);
        }
        return maxWidth;
      }

      //handle resizability of clip
      element.resizable({
        handles: "e, w",
        minWidth: 1,
        maxWidth: getMaxResizeWidthPx(),
        start: function (e, ui) {
          // Set selections
          setSelections(scope, element, $(this).attr("id"));

          // Set dragging mode
          scope.setDragging(true);
          resize_disabled = false;

          if (scope.enable_timing) {
            timing_original_start = scope.clip.start;
            timing_original_end = scope.clip.end;
            timing_original_duration = Math.max(timing_original_end - timing_original_start, 0);
            var existingAudio = scope.clip && scope.clip.ui && Array.isArray(scope.clip.ui.audio_data) ? scope.clip.ui.audio_data : null;
            timing_original_audio = existingAudio ? existingAudio.slice() : null;
          } else {
            timing_original_audio = null;
            timing_original_duration = 0.0;
          }

          // Set bounding box
          setBoundingBox(scope, $(this), "trimming");

          //determine which side is being changed
          var parentOffset = element.offset();
          var mouseLoc = e.pageX - parentOffset.left;
          if (mouseLoc < 5) {
            dragLoc = "left";
          }
          else {
            dragLoc = "right";
          }

          // Does this bounding box overlap a locked track?
          if (hasLockedTrack(scope, e.pageY, e.pageY)) {
            return !event; // yes, do nothing
          }

          // Does this bounding box overlap a locked track?
          var vert_scroll_offset = $("#scrolling_tracks").scrollTop();
          var track_top = (parseInt(element.position().top, 10) + parseInt(vert_scroll_offset, 10));
          var track_bottom = (parseInt(element.position().top, 10) + parseInt(element.height(), 10) + parseInt(vert_scroll_offset, 10));
          if (hasLockedTrack(scope, track_top, track_bottom)) {
            resize_disabled = true;
          }

          // Show hidden keyframes during resize
          startKeyframePreview(scope.enable_timing ? "retime" : "trim");
        },
        stop: function (e, ui) {
          scope.setDragging(false);

          // Stop showing hidden keyframes after drag is done
          stopKeyframePreview();

          // Calculate the pixel locations of the left and right side
          let original_left_edge = scope.clip.position * scope.pixelsPerSecond;
          let original_right_edge = original_left_edge + ((scope.clip.end - scope.clip.start) * scope.pixelsPerSecond);

          if (resize_disabled) {
            // disabled, do nothing
            resize_disabled = false;
            return;
          }

          // Calculate the clip bounding box movement and apply snapping rules
          let cursor_position = e.pageX - $("#ruler").offset().left;
          let results = moveBoundingBox(scope, bounding_box.left, bounding_box.top,
            cursor_position - bounding_box.left, cursor_position - bounding_box.top,
            cursor_position, cursor_position, "trimming")

          // Calculate delta from current mouse position
          let new_position_px = results.position.left;
          let delta_x = 0;
          if (dragLoc === "left") {
            delta_x = original_left_edge - new_position_px;
          } else if (dragLoc === "right") {
            delta_x = original_right_edge - new_position_px;
          }
          let delta_time = delta_x / scope.pixelsPerSecond;

          //change the clip end/start based on which side was dragged
          var new_position = scope.clip.position;
          var new_left = scope.clip.start;
          var new_right = scope.clip.end;

          var maxClipEndSeconds = getMaxClipEndSeconds();
          var singleImageClip = isSingleImageClip();
          var allowLeftOverflow = scope.enable_timing || singleImageClip;

          if (dragLoc === "left") {
            // changing the start of the clip
            var targetStart = new_left - delta_time;
            var overflow = 0;
            if (targetStart < 0) {
              overflow = -targetStart;
              targetStart = 0.0;
            }

            if (targetStart >= new_right) {
              // prevent resizing past right edge
              targetStart = new_right;
            } else {
              var positionShift = delta_time;
              if (overflow > 0 && !allowLeftOverflow) {
                // When overflow isn't allowed, clamp at the media's true start
                positionShift = scope.clip.start;
              }
              new_position -= positionShift;
            }

            new_left = targetStart;

            if (overflow > 0 && allowLeftOverflow) {
              // Extend duration when overflowing past the media's start
              new_right += overflow;
            }
          }
          else {
            // changing the end of the clips
            new_right -= delta_time;
            if (maxClipEndSeconds !== null && new_right > maxClipEndSeconds) {
              // prevent greater than duration
              new_right = maxClipEndSeconds;
            } else if (new_right < new_left) {
              // Prevent resizing past left edge
              new_right = new_left;
            }
          }

          // Hide snapline (if any)
          scope.hideSnapline();

          if (scope.enable_timing) {
            var duration_sec = snapToFPSGridTime(scope, new_right) - snapToFPSGridTime(scope, new_left);
            var position_sec = snapToFPSGridTime(scope, new_position);
            scope.$apply(function () {
              scope.clip.start = timing_original_start;
              scope.clip.end = snapToFPSGridTime(scope, timing_original_start + duration_sec);
              scope.clip.position = position_sec;
              scope.resizeTimeline();
            });
            if (scope.Qt) {
              timeline.RetimeClip(scope.clip.id, scope.clip.end, scope.clip.position);
            }
            if (timing_original_audio && timing_original_duration > 0) {
              var newDuration = Math.max(scope.clip.end - scope.clip.start, 0);
              var resampled = resampleWaveform(timing_original_audio, timing_original_duration, newDuration);
              if (resampled) {
                if (!scope.clip.ui) { scope.clip.ui = {}; }
                scope.clip.ui.audio_data = resampled;
                drawAudio(scope, scope.clip.id, {
                  clip: scope.clip,
                  pixelsPerSecond: scope.pixelsPerSecond
                });
              }
            }
            timing_original_audio = null;
            timing_original_duration = 0.0;
            updateMaxResizeWidth();
          } else {
            //apply the new start, end and length to the clip's scope
            scope.$apply(function () {
              if (scope.clip.end !== new_right) {
                scope.clip.end = snapToFPSGridTime(scope, new_right);
              }
              var snappedStart = snapToFPSGridTime(scope, new_left);
              var snappedPosition = snapToFPSGridTime(scope, new_position);
              if (scope.clip.start !== snappedStart) {
                scope.clip.start = snappedStart;
              }
              if (scope.clip.position !== snappedPosition) {
                scope.clip.position = snappedPosition;
              }
              scope.resizeTimeline();
            });

            // update clip in Qt (very important =)
            if (scope.Qt) {
              timeline.update_clip_data(JSON.stringify(scope.clip), true, true, false, null);
            }
            updateMaxResizeWidth();
          }

          //resize the audio canvas to match the new clip width
          if (scope.clip.ui && scope.clip.ui.audio_data) {
            // Redraw audio as the resize cleared the canvas
            drawAudio(scope, scope.clip.id, {
              clip: scope.clip,
              forceScale: false,
              pixelsPerSecond: scope.pixelsPerSecond
            });
          }
          dragLoc = null;
        },
        resize: function (e, ui) {
          // Calculate the pixel locations of the left and right side
          let original_left_edge = scope.clip.position * scope.pixelsPerSecond;
          let original_width = (scope.clip.end - scope.clip.start) * scope.pixelsPerSecond;
          let original_right_edge = original_left_edge + original_width;

          var singleImageClip = isSingleImageClip();
          var allowLeftOverflow = scope.enable_timing || singleImageClip;

          if (resize_disabled) {
            // disabled, keep the item the same size
            $(this).css({"left": original_left_edge + "px", "width": original_width + "px"});
            return;
          }

          // Calculate the clip bounding box movement and apply snapping rules
          let cursor_position = e.pageX - $("#ruler").offset().left;
          let results = moveBoundingBox(scope, bounding_box.left, bounding_box.top,
            cursor_position - bounding_box.left, cursor_position - bounding_box.top,
            cursor_position, cursor_position, "trimming");

          // Calculate delta from current mouse position
          let new_position = results.position.left;
          let delta_x = 0.0;
          if (dragLoc === "left") {
            delta_x = original_left_edge - new_position;
          } else if (dragLoc === "right") {
            delta_x = original_right_edge - new_position;
          }

          // Calculate the pixel locations of the left and right side
          var new_left = parseFloat(scope.clip.start * scope.pixelsPerSecond);
          var new_right = parseFloat(scope.clip.end * scope.pixelsPerSecond);

          var maxClipEndPx = getMaxClipEndSeconds();
          if (maxClipEndPx !== null) {
            maxClipEndPx *= scope.pixelsPerSecond;
          }

          if (dragLoc === "left") {
            if (allowLeftOverflow) {
              // Allow timing and single-image clips to extend beyond their media start
              var new_width_px = original_width + delta_x;
              if (new_width_px < 0) {
                new_width_px = 0;
              }
              ui.element.css("left", original_left_edge - delta_x);
              ui.element.width(new_width_px);
              new_left = Math.max((scope.clip.start * scope.pixelsPerSecond) - delta_x, 0.0);
              new_right = new_left + new_width_px;
            } else {
              // Adjust left side of clip
              if (new_left - delta_x > 0.0) {
                new_left -= delta_x;
              } else {
                // Don't allow less than 0.0 start
                let position_x = (scope.clip.position - scope.clip.start) * scope.pixelsPerSecond;
                delta_x = original_left_edge - position_x;
                new_left = 0.0;
              }

              // Position and size clip
              ui.element.css("left", original_left_edge - delta_x);
              ui.element.width(new_right - new_left);
            }
          }
          else {
            // Adjust right side of clip
            new_right -= delta_x;
            if (maxClipEndPx !== null && new_right > maxClipEndPx) {
              // change back to actual duration (for the preview below)
              new_right = maxClipEndPx;
            }
            ui.element.width(new_right - new_left);
          }

          // Preview frame during resize
          if (dragLoc === "left") {
            // Preview the left side of the clip
            scope.previewClipFrame(scope.clip.id, snapToFPSGridTime(scope, new_left / scope.pixelsPerSecond));
          }
          else {
            // Preview the right side of the clip
            scope.previewClipFrame(scope.clip.id, snapToFPSGridTime(scope, new_right / scope.pixelsPerSecond));
          }

          var previewStart = new_left / scope.pixelsPerSecond;
          var previewEnd = new_right / scope.pixelsPerSecond;
          updateKeyframePreview(previewStart, previewEnd);

          if (scope.clip.ui && scope.clip.ui.audio_data) {
            drawAudio(scope, scope.clip.id, {
              clip: scope.clip,
              start: previewStart,
              end: previewEnd,
              forceScale: scope.enable_timing,
              pixelsPerSecond: scope.pixelsPerSecond
            });
          }
        }
      });

      // Adjust max resize width when toggling timing mode
      scope.$watch("enable_timing", function () {
        updateMaxResizeWidth();
      });

      scope.$watch(function () {
        return scope.clip && scope.clip.start;
      }, function () {
        updateMaxResizeWidth();
      });

      scope.$watch(function () {
        return getTimePoints().length;
      }, function () {
        updateMaxResizeWidth();
      });

      scope.$watch(function () {
        return isSingleImageClip();
      }, function () {
        updateMaxResizeWidth();
      });

      scope.$on("$destroy", function () {
        stopKeyframePreview();
      });

      scope.$watch(function () {
        return scope.pixelsPerSecond;
      }, function (newValue, oldValue) {
        if (newValue === oldValue) {
          return;
        }
        var preview = scope.clip && scope.clip.ui ? scope.clip.ui.keyframe_preview : null;
        if (preview && preview.active) {
          clearKeyframePreviewTransform();
          scheduleKeyframePreviewDigest();
          renderKeyframePreview();
        }
        updateMaxResizeWidth();
      });

      updateMaxResizeWidth();

      //handle hover over on the clip
      element.hover(
        function () {
          if (!dragging) {
            element.addClass("highlight_clip", 200, "easeInOutCubic");
          }
        },
        function () {
          if (!dragging) {
            element.removeClass("highlight_clip", 200, "easeInOutCubic");
          }
        }
      );

      //handle draggability of clip
      element.draggable({
        snap: false,
        scroll: true,
        distance: 5,
        cancel: ".effect-container,.clip_menu,.point",
        start: function (event, ui) {
          // Set selections
          setSelections(scope, element, $(this).attr("id"));

          previous_drag_position = null;
          scope.setDragging(true);

          // Store initial cursor vs draggable offset
          var elementOffset = $(this).offset();
          var cursorOffset = {
              left: event.pageX - elementOffset.left,
              top: event.pageY - elementOffset.top
          };
          $(this).data("offset", cursorOffset);

          var scrolling_tracks = $("#scrolling_tracks");
          var vert_scroll_offset = scrolling_tracks.scrollTop();
          var horz_scroll_offset = scrolling_tracks.scrollLeft();
          track_container_height = getTrackContainerHeight();

          bounding_box = {};

          // Init all other selected clips (prepare to drag them)
          // This creates a bounding box which contains all selected clips
          $(".ui-selected, #" + $(this).attr("id")).each(function () {
            // Init all clips whether selected or not
            start_clips[$(this).attr("id")] = {
              "top": $(this).position().top + vert_scroll_offset,
              "left": $(this).position().left + horz_scroll_offset
            };
            move_clips[$(this).attr("id")] = {
              "top": $(this).position().top + vert_scroll_offset,
              "left": $(this).position().left + horz_scroll_offset
            };

            //send clip to bounding box builder
            setBoundingBox(scope, $(this));
          });

          // Does this bounding box overlap a locked track?
          if (hasLockedTrack(scope, bounding_box.top, bounding_box.bottom) || scope.enable_razor) {
            return !event; // yes, do nothing
          }
        },
        stop: function (event, ui) {
          // Hide snapline (if any)
          scope.hideSnapline();

          // Call the shared function for drag stop
          updateDraggables(scope, ui, "clip");

          // Clear previous drag position
          previous_drag_position = null;
        },
        drag: function (e, ui) {
          // Retrieve the initial cursor offset
          var initialOffset = $(this).data("offset");

          var previous_x = ui.originalPosition.left;
          var previous_y = ui.originalPosition.top;
          if (previous_drag_position !== null) {
            // if available, override with previous drag position
            previous_x = previous_drag_position.left;
            previous_y = previous_drag_position.top;
          }

          // set previous position (for next time around)
          previous_drag_position = ui.position;

          // Calculate amount to move clips
          var x_offset = ui.position.left - previous_x;
          var y_offset = ui.position.top - previous_y;

          // Move the bounding box and apply snapping rules
          var results = moveBoundingBox(scope, previous_x, previous_y, x_offset, y_offset, ui.position.left, ui.position.top, "clip", initialOffset);
          x_offset = results.x_offset;
          y_offset = results.y_offset;

          // Update ui object
          ui.position.left = results.position.left;
          ui.position.top = results.position.top;

          // Move all other selected clips with this one if we have more than one clip
          $(".ui-selected").each(function () {
            if (move_clips[$(this).attr("id")]) {
              let newY = move_clips[$(this).attr("id")]["top"] + y_offset;
              let newX = move_clips[$(this).attr("id")]["left"] + x_offset;
              //update the clip location in the array
              move_clips[$(this).attr("id")]["top"] = newY;
              move_clips[$(this).attr("id")]["left"] = newX;
              //change the element location
              $(this).css("left", newX);
              $(this).css("top", newY);
            }
          });
        }
      });
    }
  };
});

// Handle clip effects
App.directive("tlClipEffects", function () {
  return {
    link: function (scope, element, attrs) {

    }
  };
});

// Handle multiple selections
App.directive("tlMultiSelectable", function () {
  return {
    link: function (scope, element, attrs) {
      element.selectable({
        filter: ".droppable",
        distance: 0,
        cancel: ".effect-container,.transition_menu,.clip_menu,.point,.track-resize-handle",
        selected: function (event, ui) {
          // Identify the selected ID and TYPE
          var id = ui.selected.id;
          var type = "";
          var item = null;

          if (id.match("^clip_")) {
            id = id.replace("clip_", "");
            type = "clip";
            item = findElement(scope.project.clips, "id", id);
          }
          else if (id.match("^transition_")) {
            id = id.replace("transition_", "");
            type = "transition";
            item = findElement(scope.project.effects, "id", id);
          }

          if (scope.Qt) {
            timeline.addSelection(id, type, false);
            // Clear effect selections (if any)
            timeline.addSelection("", "effect", true);
          }

          // Update item state
          item.selected = true;
        },
        unselected: function (event, ui) {
          // Identify the selected ID and TYPE
          var id = ui.unselected.id;
          var type = "";
          var item = null;

          if (id.match("^clip_")) {
            id = id.replace("clip_", "");
            type = "clip";
            item = findElement(scope.project.clips, "id", id);
          }
          else if (id.match("^transition_")) {
            id = id.replace("transition_", "");
            type = "transition";
            item = findElement(scope.project.effects, "id", id);
          }

          if (scope.Qt) {
            timeline.removeSelection(id, type);
          }
          // Update item state
          item.selected = false;
        },
        stop: function (event, ui) {
          // Check if any clips or transitions are selected
          var anySelected =
            scope.project.clips.some(function(c) { return c.selected; }) ||
            scope.project.effects.some(function(t) { return t.selected; });

          if (!anySelected) {
            // If nothing is selected, clear all effect selections
            scope.$apply(function() {
              scope.selectEffect("", true);
            });
          } else {
            // Otherwise, just update UI as normal
            scope.$apply();
          }
        }
      });
    }
  };
});

// Handle audio waveform drawing (when a tl-audio directive is found)
App.directive("tlAudio",  function ($timeout) {
  return {
    link: function (scope, element, attrs) {
      $timeout(function () {
        // Use timeout to wait until after the DOM is manipulated
        let clip_id = attrs.id.replace("audio_clip_", "");
        drawAudio(scope, clip_id);
      }, 0);
    }
  };
});
