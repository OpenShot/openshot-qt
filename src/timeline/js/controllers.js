/**
 * @file
 * @brief The AngularJS controller used by the OpenShot Timeline
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


// Initialize the main controller module
/*global App, timeline, bounding_box, setBoundingBox, moveBoundingBox, findElement, findTrackAtLocation, snapToFPSGridTime, pixelToTime*/
App.controller("TimelineCtrl", function ($scope) {

  // DEMO DATA (used when debugging outside of Qt using Chrome)
  $scope.project = {
    fps: {
      num: 24,
      den: 1
    },
    duration: 300, //length of project in seconds
    scale: 16.0, //seconds per tick
    tick_pixels: 100, //pixels between tick mark
    playhead_position: 0.0, //position of play head
    clips: [],
    effects: [],
    layers: [
      {id: "L0", number: 0, y: 0, label: "", lock: false},
      {id: "L1", number: 1, y: 0, label: "", lock: false},
      {id: "L2", number: 2, y: 0, label: "", lock: false},
      {id: "L3", number: 3, y: 0, label: "", lock: false},
      {id: "L4", number: 4, y: 0, label: "", lock: false}
    ],
    markers: [],
    progress: {}
  };

  // Additional variables used to control the rendering of HTML
  $scope.pixelsPerSecond = parseFloat($scope.project.tick_pixels) / parseFloat($scope.project.scale);
  $scope.playhead_animating = false;
  $scope.playheadTime = secondsToTime($scope.project.playhead_position, $scope.project.fps.num, $scope.project.fps.den);
  $scope.snapline_position = 0.0;
  $scope.snapline = false;
  $scope.enable_snapping = true;
  $scope.enable_razor = false;
  $scope.enable_timing = false;
  $scope.enable_playhead_follow = true;
  $scope.keyframe_prop_filter = "";
  $scope.debug = false;
  $scope.min_width = 1024;
  $scope.track_label = "Track %s";
  $scope.enable_sorting = true;
  $scope.ThumbServer = "http://127.0.0.1/";
  $scope.ThemeCSS = "";
  $scope.dragging = false;

  $scope.keyframeIconPaths = {};
  var keyframeSvgTemplates = {};
  var keyframeCache = new WeakMap();

  function loadKeyframeIcons() {
    var ready = true;
    ["bezier", "linear", "constant"].forEach(function(type) {
      var el = document.createElement("div");
      el.className = "point_" + type;
      document.body.appendChild(el);
      var url = getComputedStyle(el).getPropertyValue("background-image")
        .replace(/url\((['"]?)(.*?)\1\)/, "$2");
      document.body.removeChild(el);

      if (!url || url === "none") {
        ready = false;
        return;
      }

      $scope.keyframeIconPaths[type] = url;

      var xhr = new XMLHttpRequest();
      xhr.onreadystatechange = function() {
        if (xhr.readyState === 4 && (xhr.status === 200 || xhr.status === 0)) {
          keyframeSvgTemplates[type] = xhr.responseText;
        }
      };
      xhr.open("GET", url, true);
      xhr.send();
    });

    if (!ready) {
      // CSS not ready yet, try again once the page has loaded
      window.addEventListener("load", loadKeyframeIcons, { once: true });
      return;
    }

    // Remove default background images now that we have their paths
    var style = document.createElement("style");
    style.textContent = ".point_bezier,.point_linear,.point_constant{background-image:none;}";
    document.head.appendChild(style);
  }

  function coloredIcon(interpolation, color) {
    var tpl = keyframeSvgTemplates[interpolation];
    if (!tpl) {return $scope.keyframeIconPaths[interpolation];}
    var svg = tpl.replace(/fill="[^"]*"/g, "fill=\"" + color + "\"");
    return "data:image/svg+xml;utf8," + encodeURIComponent(svg);
  }

  // Load keyframe icons after all styles have finished loading
  window.addEventListener("load", loadKeyframeIcons);

  // Method to set if Qt is detected (which clears demo data
  // and updates the document_is_ready variable in openshot-qt)
  $scope.Qt = false;
  $scope.enableQt = function () {
    $scope.Qt = true;
    timeline.qt_log("DEBUG", "$scope.Qt = true;");
    timeline.page_ready();
  };

  $scope.setThumbAddress = function (url) {
    $scope.ThumbServer = url;
    timeline.qt_log("DEBUG", "setThumbAddress: " + url);
  };

  // Move the playhead to a specific time
  $scope.movePlayhead = function (position_seconds) {
    // Update internal scope (in seconds)
    $scope.project.playhead_position = snapToFPSGridTime($scope, position_seconds);
    $scope.playheadTime = secondsToTime(position_seconds, $scope.project.fps.num, $scope.project.fps.den);

    // Use JQuery to move playhead (for performance reasons) - scope.apply is too expensive here
    $(".playhead-top").css("left", ($scope.project.playhead_position * $scope.pixelsPerSecond) + "px");
    $(".playhead-line").css("left", ($scope.project.playhead_position * $scope.pixelsPerSecond) + "px");
    $("#ruler_time").text($scope.playheadTime.hour + ":" + $scope.playheadTime.min + ":" + $scope.playheadTime.sec + "," + $scope.playheadTime.frame);
  };

  // Move the playhead to a specific frame
  $scope.movePlayheadToFrame = function (position_frames) {
    // Don't move the playhead if it's currently animating
    if ($scope.playhead_animating) {
      return;
    }

    // Determine seconds
    var frames_per_second = $scope.project.fps.num / $scope.project.fps.den;
    var position_seconds = ((position_frames - 1) / frames_per_second);

    // Update internal scope (in seconds)
    $scope.movePlayhead(position_seconds);
  };

  // Move the playhead to a specific time
  $scope.previewFrame = function (position_seconds) {
    // Determine frame
    var frames_per_second = $scope.project.fps.num / $scope.project.fps.den;
    var frame = Math.round(position_seconds * frames_per_second) + 1;

    // Update GUI with position (so the preview can be updated)
    if ($scope.Qt) {
      timeline.PlayheadMoved(frame);
    }
  };

  // Move the playhead to a specific time
  $scope.previewClipFrame = function (clip_id, position_seconds) {
    // Get the nearest starting frame position to the playhead (this helps to prevent cutting
    // in-between frames, and thus less likely to repeat or skip a frame).
    // Determine frame
    var position_seconds_rounded = (Math.round((position_seconds * $scope.project.fps.num) / $scope.project.fps.den) * $scope.project.fps.den ) / $scope.project.fps.num;
    var frames_per_second = $scope.project.fps.num / $scope.project.fps.den;
    var frame = Math.round(position_seconds_rounded * frames_per_second) + 1;

    // Update GUI with position (so the preview can be updated)
    if ($scope.Qt) {
      timeline.PreviewClipFrame(clip_id, frame);
    }
  };

  // Get keyframe interpolation type
  $scope.lookupInterpolation = function(interpolation_number) {
    if (parseInt(interpolation_number) === 0) {
      return "bezier";
    } else if (parseInt(interpolation_number) === 1) {
      return "linear";
    } else {
      return "constant";
    }
  }

  // Seek to keyframe
  $scope.selectPoint = function(object, point) {
    var frames_per_second = $scope.project.fps.num / $scope.project.fps.den;
    var clip_position_frames = object.position * frames_per_second;
    var absolute_seek_frames = clip_position_frames + parseInt(point) - (object.start * frames_per_second);

    if ($scope.Qt) {
      timeline.SeekToKeyframe(absolute_seek_frames)
    }
  }

  $scope.hasSelectedEffect = function (clip) {
    if (!clip || !clip.effects) {return false;}
    for (var i = 0; i < clip.effects.length; i++) {
      if (clip.effects[i].selected) {return true;}
    }
    return false;
  };

  $scope.getKeyframes = function (object) {
    var frames_per_second = $scope.project.fps.num / $scope.project.fps.den;

    function toNumber(value, fallback) {
      var num = parseFloat(value);
      return isNaN(num) ? fallback : num;
    }

    var clip_start_sec = toNumber(object.start, 0);
    var clip_end_sec = toNumber(object.end, clip_start_sec);
    if (clip_end_sec < clip_start_sec) {
      clip_end_sec = clip_start_sec;
    }

    var object_type = object.hasOwnProperty("file_id") ? "clip" : "transition";

    var effect_selected = false;
    var effect_key = "";
    if ("effects" in object) {
      effect_selected = object.effects.some(function(e) { return e.selected; });
      effect_key = object.effects.map(function(e) {
        return e.id + (e.selected ? "1" : "0");
      }).join(",");
    }

    var preview = null;
    if (object && object.ui && object.ui.keyframe_preview && object.ui.keyframe_preview.active) {
      preview = object.ui.keyframe_preview;
    }

    var previewSignature = "none";
    if (preview) {
      var previewMode = preview.mode || "";
      var displayStart = toNumber(preview.displayStart, clip_start_sec);
      var displayEnd = toNumber(preview.displayEnd, clip_end_sec);
      var originalStart = toNumber(preview.originalStart, clip_start_sec);
      var originalEnd = toNumber(preview.originalEnd, clip_end_sec);
      previewSignature = [previewMode, displayStart.toFixed(4), displayEnd.toFixed(4), originalStart.toFixed(4), originalEnd.toFixed(4)].join("|");
    }

    var cacheKey = object.selected + "|" + effect_key + "|" + $scope.keyframe_prop_filter + "|" + previewSignature;
    var cached = keyframeCache.get(object);

    var previewActive = !!(preview && preview.active);

    if (object_type !== "transition" && !object.selected && !effect_selected && !previewActive) {
      if (cached && cached.key === cacheKey) {
        return cached.value;
      }
      keyframeCache.set(object, {key: cacheKey, value: {}});
      return {};
    }

    var keyframes = {};
    // Include every keyframe while previewing trims/retimes so the UI can dim out-of-range ones.
    var includeAllKeyframes = !!preview;
    var EPSILON = 0.000001;
    var frameTolerance = EPSILON;
    if (frames_per_second && isFinite(frames_per_second) && frames_per_second > 0) {
      frameTolerance = Math.max(frameTolerance, 0.5 / frames_per_second);
    }

    var previewDisplayStart = preview ? toNumber(preview.displayStart, clip_start_sec) : clip_start_sec;
    var previewDisplayEnd = preview ? toNumber(preview.displayEnd, clip_end_sec) : clip_end_sec;
    if (previewDisplayEnd < previewDisplayStart) {
      var tmp = previewDisplayStart;
      previewDisplayStart = previewDisplayEnd;
      previewDisplayEnd = tmp;
    }

    var previewProjectedStart = preview ? toNumber(preview.projectedStart, clip_start_sec) : clip_start_sec;
    var previewProjectedEnd = preview ? toNumber(preview.projectedEnd, clip_end_sec) : clip_end_sec;
    if (previewProjectedEnd < previewProjectedStart) {
      previewProjectedEnd = previewProjectedStart;
    }

    var displayDuration = Math.max(previewDisplayEnd - previewDisplayStart, 0);
    var projectedDuration = Math.max(previewProjectedEnd - previewProjectedStart, 0);

    function mapSecondsToDisplay(seconds) {
      if (!preview || preview.mode !== "retime") {
        return seconds;
      }
      if (!(projectedDuration > 0) || !(displayDuration > 0)) {
        return previewDisplayStart;
      }
      var normalized = (seconds - previewProjectedStart) / projectedDuration;
      if (!isFinite(normalized)) {
        normalized = 0;
      }
      var mapped = previewDisplayStart + (normalized * displayDuration);
      return mapped;
    }

    function isInside(seconds, start, end) {
      return seconds >= start - frameTolerance && seconds <= end + frameTolerance;
    }

    function isInsideClip(seconds) {
      return isInside(seconds, clip_start_sec, clip_end_sec);
    }

    function isInsidePreview(seconds) {
      if (!preview) {
        return isInsideClip(seconds);
      }
      if (preview.mode === "retime") {
        var mappedSeconds = mapSecondsToDisplay(seconds);
        return isInside(mappedSeconds, previewDisplayStart, previewDisplayEnd);
      }
      return isInside(seconds, previewDisplayStart, previewDisplayEnd);
    }

    function storeKeyframe(frame, data) {
      var existing = keyframes[frame];
      if (!existing || (data.selected && !existing.selected)) {
        keyframes[frame] = data;
      }
    }

    for (var child in object) {
      if (!object.hasOwnProperty(child)) {continue;}
      if ($scope.keyframe_prop_filter.length > 0 &&
          !child.toLowerCase().includes($scope.keyframe_prop_filter.toLowerCase())) {
        continue;
      }
      if (typeof object[child] === "object" && object[child].Points && object[child].Points.length > 1) {
        for (var point = 0; point < object[child].Points.length; point++) {
          var co = object[child].Points[point].co;
          var interpolation = $scope.lookupInterpolation(object[child].Points[point].interpolation);
          var keyframeSeconds = (co.X - 1) / frames_per_second;
          var withinClip = isInsideClip(keyframeSeconds);
          if (includeAllKeyframes || withinClip) {
            var insidePreview = isInsidePreview(keyframeSeconds);
            var baseSelected = object_type === "transition" ? true : object.selected && !effect_selected;
            storeKeyframe(co.X, {
              interpolation: interpolation,
              selected: baseSelected && insidePreview,
              type: object_type,
              owner: object.id,
              insidePreview: insidePreview,
              baseSelected: baseSelected
            });
            cacheKey += ";c" + co.X + ":" + interpolation;
          }
        }
      }
      if (typeof object[child] === "object" && object[child].red && object[child].red.Points.length > 1) {
        for (var color_point = 0; color_point < object[child].red.Points.length; color_point++) {
          var color_co = object[child].red.Points[color_point].co;
          var color_interpolation = $scope.lookupInterpolation(object[child].red.Points[color_point].interpolation);
          var colorSeconds = (color_co.X - 1) / frames_per_second;
          var colorWithinClip = isInsideClip(colorSeconds);
          if (includeAllKeyframes || colorWithinClip) {
            var colorInsidePreview = isInsidePreview(colorSeconds);
            var colorBaseSelected = object_type === "transition" ? true : object.selected && !effect_selected;
            storeKeyframe(color_co.X, {
              interpolation: color_interpolation,
              selected: colorBaseSelected && colorInsidePreview,
              type: object_type,
              owner: object.id,
              insidePreview: colorInsidePreview,
              baseSelected: colorBaseSelected
            });
            cacheKey += ";cr" + color_co.X + ":" + color_interpolation;
          }
        }
      }
    }

    if ("effects" in object) {
      for (var e in object.effects) {
        var eff = object.effects[e];
        var eff_color = $scope.getEffectColor(eff.type);
        for (var prop in eff) {
          if (!eff.hasOwnProperty(prop)) {continue;}
          if ($scope.keyframe_prop_filter.length > 0 &&
              !prop.toLowerCase().includes($scope.keyframe_prop_filter.toLowerCase())) {
            continue;
          }
          if (typeof eff[prop] === "object" && eff[prop].Points && eff[prop].Points.length > 1) {
            for (var ep = 0; ep < eff[prop].Points.length; ep++) {
              var eco = eff[prop].Points[ep].co;
              var einterp = $scope.lookupInterpolation(eff[prop].Points[ep].interpolation);
              var eframe = eco.X;
              var effectSeconds = (eframe - 1) / frames_per_second;
              var effectWithinClip = isInsideClip(effectSeconds);
              if (includeAllKeyframes || effectWithinClip) {
                var effectInsidePreview = isInsidePreview(effectSeconds);
                var icon = coloredIcon(einterp, eff_color);
                var effectSelected = !!eff.selected;
                storeKeyframe(eframe, {
                  interpolation: einterp,
                  icon: icon,
                  selected: effectSelected && effectInsidePreview,
                  type: "effect",
                  owner: eff.id,
                  insidePreview: effectInsidePreview,
                  baseSelected: effectSelected
                });
                cacheKey += ";e" + eff.id + ":" + eframe + ":" + einterp;
              }
            }
          }
          if (typeof eff[prop] === "object" && eff[prop].red && eff[prop].red.Points.length > 1) {
            for (var ecp = 0; ecp < eff[prop].red.Points.length; ecp++) {
              var ecc = eff[prop].red.Points[ecp].co;
              var ecinterp = $scope.lookupInterpolation(eff[prop].red.Points[ecp].interpolation);
              var ecframe = ecc.X;
              var colorEffectSeconds = (ecframe - 1) / frames_per_second;
              var colorEffectWithinClip = isInsideClip(colorEffectSeconds);
              if (includeAllKeyframes || colorEffectWithinClip) {
                var colorEffectInsidePreview = isInsidePreview(colorEffectSeconds);
                var color_icon = coloredIcon(ecinterp, eff_color);
                var colorEffectSelected = !!eff.selected;
                storeKeyframe(ecframe, {
                  interpolation: ecinterp,
                  icon: color_icon,
                  selected: colorEffectSelected && colorEffectInsidePreview,
                  type: "effect",
                  owner: eff.id,
                  insidePreview: colorEffectInsidePreview,
                  baseSelected: colorEffectSelected
                });
                cacheKey += ";ec" + eff.id + ":" + ecframe + ":" + ecinterp;
              }
            }
          }
        }
      }
    }

    cached = keyframeCache.get(object);
    if (cached && cached.key === cacheKey) {
      return cached.value;
    }
    keyframeCache.set(object, {key: cacheKey, value: keyframes});
    return keyframes;
  };

  $scope.clickKeyframe = function(value, parent, point, event) {
    if (event && event.stopPropagation) {
      event.stopPropagation();
    }
    if (value.type === "clip") {
      $scope.selectClip(parent.id, true, event);
    } else if (value.type === "effect") {
      $scope.selectEffect(value.owner, true, event);
    } else if (value.type === "transition") {
      $scope.selectTransition(parent.id, true, event);
    }
    $scope.selectPoint(parent, point);
  };

  // Move all keyframes located at old_frame to new_frame within an object
  $scope.moveKeyframes = function(object, old_frame, new_frame) {
    function update(obj) {
      if (!obj || typeof obj !== "object") return;

      if (Array.isArray(obj)) {
        obj.forEach(update);
        return;
      }

      if (obj.Points && Array.isArray(obj.Points)) {
        obj.Points.forEach(function(p) {
          if (p.co && p.co.X === old_frame) {
            p.co.X = new_frame;
          }
        });
      }

      if (obj.red && obj.red.Points) {
        ["red", "green", "blue"].forEach(function(color) {
          obj[color].Points.forEach(function(p) {
            if (p.co && p.co.X === old_frame) {
              p.co.X = new_frame;
            }
          });
        });
      }

      for (var k in obj) {
        if (obj.hasOwnProperty(k) && typeof obj[k] === "object") {
          update(obj[k]);
        }
      }
    }

    update(object);
  };

  // Determine track top (in vertical pixels)
  $scope.getTrackTop = function (layer) {
    // Get scrollbar position
    var scrolling_tracks = $("#scrolling_tracks");
    var vert_scroll_offset = scrolling_tracks.scrollTop();

    // Find this tracks Y location
    var track_id = "div#track_" + layer;
    if ($(track_id).length) {
      var trackElement = $(track_id);
      var topPosition = trackElement.position().top;
      var marginTop = parseInt(trackElement.css("margin-top"), 10);

      // Include the margin in the position calculation
      return topPosition + vert_scroll_offset + marginTop;
    } else {
      return 0;
    }
  };

  // Determine whether a given timeline time index is scrolled into view
  $scope.isTimeVisible = function (time_pos) {
    // Get scrollbar positions
    var scrolling_tracks = $("#scrolling_tracks");
    var horz_scroll_offset = scrolling_tracks.scrollLeft();
    var canvas_width = scrolling_tracks.width();

    // Compute pixel location of time index
    var time_x = (time_pos * $scope.pixelsPerSecond) - horz_scroll_offset;
    return time_x > 0 && time_x < canvas_width;
  };

  // Determine whether the playhead is within the visible timeline section
  $scope.isPlayheadVisible = function () {
    return $scope.isTimeVisible($scope.project.playhead_position);
  };

// ############# QT FUNCTIONS #################### //

  // Change the scale and apply to scope
  $scope.setScale = function (scaleVal, cursor_x) {
    // Get scrollbar positions
    var scrolling_tracks = $("#scrolling_tracks");
    var horz_scroll_offset = scrolling_tracks.scrollLeft();
    var track_labels_width = $("#track_controls").width();
    var center_x = 0;
    var cursor_time = 0;

    // Determine actual x coordinate (over timeline)
    if (cursor_x > 0) {
      center_x = Math.max(cursor_x - track_labels_width, 0);
      // Determine time of cursor position
      cursor_time = parseFloat(center_x + horz_scroll_offset) / $scope.pixelsPerSecond;
    } else if ($scope.isPlayheadVisible()) {
      // Zoom on playhead if visible
      cursor_time = $scope.project.playhead_position;
      center_x = (cursor_time * $scope.pixelsPerSecond) - horz_scroll_offset;
    } else {
      // Fall back to centering on left edge of canvas
      cursor_time = parseFloat(horz_scroll_offset) / $scope.pixelsPerSecond;
    }

    $scope.$apply(function () {
      $scope.project.scale = parseFloat(scaleVal);
      $scope.pixelsPerSecond = parseFloat($scope.project.tick_pixels) / parseFloat($scope.project.scale);
    });

    // Scroll back to correct cursor time (minus the difference of the cursor location)
    var new_cursor_x = Math.max(0, Math.round((cursor_time * $scope.pixelsPerSecond) - center_x));
    scrolling_tracks.scrollLeft(new_cursor_x + 1); // force scroll event
    scrolling_tracks.scrollLeft(new_cursor_x);
  };

  // Change the scale and apply to scope
  $scope.setScroll = function (normalizedScrollValue) {
    var timeline_length = $scope.getTimelineWidth(0);
    var scrolling_tracks = $("#scrolling_tracks");
    var horz_scroll_offset = normalizedScrollValue * timeline_length;
    scrolling_tracks.scrollLeft(horz_scroll_offset);
  };

  // Scroll the timeline horizontally of a certain amount
  $scope.scrollLeft = function (scroll_value) {
    var scrolling_tracks = $("#scrolling_tracks");
    var horz_scroll_offset = scrolling_tracks.scrollLeft();
    scrolling_tracks.scrollLeft(horz_scroll_offset + scroll_value);
  };

  // Center the timeline on a given time position
  $scope.centerOnTime = function (centerTime) {
    // Get the width of the timeline
    var scrolling_tracks = $("#scrolling_tracks");
    var scrollingTracksWidth = scrolling_tracks.width();

    // Get the total width of the timeline (the entire scrollable content width)
    var totalTimelineWidth = $scope.getTimelineWidth(0);

    // Calculate the position to scroll the timeline to center on the requested time
    var pixelToCenterOn = parseFloat(centerTime) * $scope.pixelsPerSecond;
    var scrollPosition = Math.max(pixelToCenterOn - (scrollingTracksWidth / 2.0), 0);

    // Condition: Check if we are zoomed into the very right edge of the timeline
    if (scrollPosition + scrollingTracksWidth >= totalTimelineWidth) {
        // We are near the right edge, so align the right edge with the right of the screen
        scrollPosition = totalTimelineWidth - scrollingTracksWidth;
    }

    // Scroll the timeline using JQuery
    scrolling_tracks.scrollLeft(Math.floor(scrollPosition + 0.5));
  };

  // Center the timeline on the current playhead position
  $scope.centerOnPlayhead = function () {
    $scope.centerOnTime($scope.project.playhead_position);
  };

  // Update thumbnail for clip
  $scope.updateThumbnail = function (clip_id) {
    // Find matching clip, update thumbnail to same path (to force reload)
    var clip_selector = $("#clip_" + clip_id + " .thumb");
    var existing_thumb_path = clip_selector.attr("src");
    var thumb_url_parts = existing_thumb_path.split("?");
    if (thumb_url_parts.length > 1) {
      // Trim off any previous cache buster
      existing_thumb_path = thumb_url_parts[0];
    }

    // Append cache buster, since QtWebEngine seems to aggressively cache images
    existing_thumb_path += "?" + Math.random();

    timeline.qt_log("DEBUG", existing_thumb_path);
    clip_selector.attr("src", existing_thumb_path);
  };

  // Redraw all audio waveforms on the timeline (for example, if the screen is resized)
  $scope.reDrawAllAudioData = function () {
    // Loop through all clips (and look for audio data)
    for (var clip_index = 0; clip_index < $scope.project.clips.length; clip_index++) {
      var clip_ui = $scope.project.clips[clip_index].ui;
      var audio_data = clip_ui ? clip_ui.audio_data : null;
      if (Array.isArray(audio_data) && audio_data.length > 1) {
        // Redraw audio data
        drawAudio($scope, $scope.project.clips[clip_index].id);
      }
    }
  };

  $scope.setPropertyFilter = function (property) {
    $scope.$apply(function () {
      $scope.keyframe_prop_filter = property;
    });
  };

  // Change the snapping mode
  $scope.setSnappingMode = function (enable_snapping) {
    $scope.$apply(function () {
      $scope.enable_snapping = enable_snapping;
    });
  };

  // Change the razor mode
  $scope.setRazorMode = function (enable_razor) {
    $scope.$apply(function () {
      $scope.enable_razor = enable_razor;
    });
  };

  // Change the timing mode
  $scope.setTimingMode = function (enable_timing) {
    $scope.$apply(function () {
      $scope.enable_timing = enable_timing;
    });
  };

  // Change playhead follow mode
  $scope.setFollow = function (enable_follow) {
    $scope.$apply(function () {
      $scope.enable_playhead_follow = enable_follow;
    });
  };

  // Get the color of an effect
  $scope.getEffectColor = function (effect_type) {
    switch (effect_type) {
      case "AnalogTape":
        return "#907600";
      case "Bars":
        return "#4d7bff";
      case "Blur":
        return "#0095bf";
      case "Brightness":
        return "#5500ff";
      case "Caption":
        return "#5e7911";
      case "ChromaKey":
        return "#00ad2d";
      case "Color Shift":
        return "#b39373";
      case "Compressor":
        return "#A52A2A";
      case "Crop":
        return "#7b3f00";
      case "Deinterlace":
        return "#006001";
      case "Delay":
        return "#ff4dd4";
      case "Distortion":
        return "#7393B3";
      case "Echo":
        return "#5C4033";
      case "Expander":
        return "#C4A484";
      case "Hue":
        return "#2d7b6b";
      case "Mask":
        return "#cb0091";
      case "Negate":
        return "#ff9700";
      case "Noise":
        return "#a9a9a9";
      case "ObjectDetection":
        return "#636363";
      case "Parametric EQ":
        return "#708090";
      case "Pixelate":
        return	"#9fa131";
      case "Robotization":
        return "#CC5500";
      case "Saturation":
        return "#ff3d00";
      case "Sharpen":
        return "#49759c";
      case "ColorMap":
        return "#4d945d";
      case "LensFlare":
        return "#7c29d1";
      case "Normalize":
        return "#607d3b";
      case "Outline":
        return "#be6d33";
      case "SphericalProjection":
        return "#b886ea";
      case "Shift":
        return "#8d7960";
      case "Stabilizer":
        return "#9F2B68";
      case "Tracker":
        return "#DE3163";
      case "Wave":
        return "#FF00Ff";
      case "Whisperization":
        return "#93914a";
      default:
        return "#000000";
    }
  };

  // Add a new clip to the timeline
  $scope.addClip = function (x, y, clip_json) {
    $scope.$apply(function () {
      // Convert x and y into timeline vars
      var scrolling_tracks_offset = $("#scrolling_tracks").offset().left;
      var clip_position = parseFloat(x - scrolling_tracks_offset) / parseFloat($scope.pixelsPerSecond);

      // Get the nearest starting frame position to the clip position (this helps to prevent cutting
      // in-between frames, and thus less likely to repeat or skip a frame).
      clip_position = (Math.round((clip_position * $scope.project.fps.num) / $scope.project.fps.den) * $scope.project.fps.den ) / $scope.project.fps.num;

      // Get the nearest track
      var nearest_track = findTrackAtLocation($scope, y);
      if (nearest_track !== null) {
        // Set clip properties and add clip
        clip_json.position = clip_position;
        clip_json.layer = nearest_track.number;

        // Push new clip onto stack
        $scope.project.clips.push(clip_json);
      }
    });
  };

  // Update cache json
  $scope.renderCache = function (cache_json) {
    $scope.project.progress = cache_json;

    //clear the canvas first
    var ruler = $("#progress");
    var ctx = ruler[0].getContext("2d");
    ctx.clearRect(0, 0, ruler.width(), ruler.height());

    // Determine fps & and get cached ranges
    var fps = $scope.project.fps.num / $scope.project.fps.den;
    if ($scope.project.progress && $scope.project.progress.hasOwnProperty('ranges')) {
        // Loop through each cached range of frames, and draw rect
        let progress = $scope.project.progress.ranges;
        for (var p = 0; p < progress.length; p++) {
          //get the progress item details
          var start_second = parseFloat(progress[p]["start"]) / fps;
          var stop_second = parseFloat(progress[p]["end"]) / fps;

          //figure out the actual pixel position, constrained by max width
          var start_pixel = $scope.canvasMaxWidth(start_second * $scope.pixelsPerSecond);
          var stop_pixel = $scope.canvasMaxWidth(stop_second * $scope.pixelsPerSecond);
          var rect_length = stop_pixel - start_pixel;
          if (rect_length < 1) {
            continue;
          }
          //get the element and draw the rects
          ctx.beginPath();
          ctx.rect(start_pixel, 0, rect_length, 5);
          ctx.fillStyle = "#4B92AD";
          ctx.fill();
        }
    }
  };

  // Clear all selections
  $scope.clearAllSelections = function () {
    // Clear the selections on the main window
    $scope.selectClip("", true);
    $scope.selectTransition("", true);
    $scope.selectEffect("", true);

    // Update scope
    $scope.$apply();
  };

  // Select all clips and transitions
  $scope.selectAll = function () {
    $scope.$apply(function () {
      // Select all clips
      for (var clip_index = 0; clip_index < $scope.project.clips.length; clip_index++) {
        $scope.project.clips[clip_index].selected = true;
        timeline.addSelection($scope.project.clips[clip_index].id, "clip", false);
      }
      // Select all transitions
      for (var effect_index = 0; effect_index < $scope.project.effects.length; effect_index++) {
        $scope.project.effects[effect_index].selected = true;
        timeline.addSelection($scope.project.effects[effect_index].id, "transition", false);
      }
    });
  };

  // Initialize last selected item
  $scope.lastSelectedItem = null;

$scope.selectItem = function (item_id, item_type, clear_selections, event, force_ripple) {
    if ($scope.dragging) {
        timeline.qt_log("DEBUG", "Skip selection due to dragging...");
        return;
    }

    // Trim item_id
    var id = (item_id || "").replace(`${item_type}_`, "");

    // Check for modifier keys
    var is_ctrl = event && event.ctrlKey;
    var is_shift = event && event.shiftKey;
    var is_alt = event && event.altKey;
    var parent_clip = null;

    // If no ID is provided (id == ""), unselect all items of this type
    if (id === "") {
        if (clear_selections) {
            if (item_type === "clip") {
                $scope.project.clips.forEach(function (clip) {
                    clip.selected = false;
                    if ($scope.Qt) { timeline.removeSelection(clip.id, "clip"); }
                });
            } else if (item_type === "transition") {
                $scope.project.effects.forEach(function (tran) {
                    tran.selected = false;
                    if ($scope.Qt) { timeline.removeSelection(tran.id, "transition"); }
                });
            } else if (item_type === "effect") {
                // Clear both global effects and all clip effects!
                $scope.project.effects.forEach(function (eff) {
                    eff.selected = false;
                    if ($scope.Qt) { timeline.removeSelection(eff.id, "effect"); }
                });
                $scope.project.clips.forEach(function (clip) {
                    if (clip.effects) {
                        clip.effects.forEach(function (eff) {
                            eff.selected = false;
                            if ($scope.Qt) { timeline.removeSelection(eff.id, "effect"); }
                        });
                    }
                });
            }
        }
        return; // Exit after clearing all selections
    }

    // Razor mode check
    if ($scope.enable_razor && $scope.Qt && typeof event !== 'undefined') {
        var cursor_seconds = $scope.getJavaScriptPosition(event.clientX, null).position;
        timeline.RazorSliceAtCursor(
            item_type === "clip" ? id : "",
            item_type === "transition" ? id : "",
            cursor_seconds
        );
        return; // Don't select if razor mode is enabled
    }

    // Handle ripple selection (ALT key) for both clips and transitions
    if (is_alt || force_ripple) {
        var selected_item = null;
        if (item_type === "clip") {
            selected_item = $scope.project.clips.find((item) => item.id === id);
        } else if (item_type === "transition") {
            selected_item = $scope.project.effects.find((item) => item.id === id);
        } else if (item_type === "effect") {
            // Try global effects first, then all clip effects
            selected_item = $scope.project.effects.find((item) => item.id === id);
            if (!selected_item) {
                for (let j = 0; j < $scope.project.clips.length; j++) {
                    let clipItem = $scope.project.clips[j];
                    if (clipItem.effects) {
                        let effItem = clipItem.effects.find((e) => e.id === id);
                        if (effItem) {
                            selected_item = effItem;
                            break;
                        }
                    }
                }
            }
        }

        if (selected_item && (item_type === "clip" || item_type === "transition")) {
            var selected_layer = selected_item.layer;
            var selected_position = selected_item.position;

            // Select all clips and transitions to the right on the same layer
            $scope.project.clips.forEach(function (clip) {
                if (clip.layer === selected_layer && clip.position >= selected_position) {
                    clip.selected = true;
                    if ($scope.Qt) { timeline.addSelection(clip.id, "clip", false); }
                }
            });
            $scope.project.effects.forEach(function (transition) {
                if (transition.layer === selected_layer && transition.position >= selected_position) {
                    transition.selected = true;
                    if ($scope.Qt) { timeline.addSelection(transition.id, "transition", false); }
                }
            });
        }

        // If CTRL is not pressed, clear previous selections (unless clear_selections is false)
        if (clear_selections && !is_ctrl) {
            $scope.project.clips.forEach(function (clip) {
                if (!clip.selected) {
                    if ($scope.Qt) { timeline.removeSelection(clip.id, "clip"); }
                }
                if (clip.effects) {
                    clip.effects.forEach(function (eff) {
                        if (!eff.selected && $scope.Qt) { timeline.removeSelection(eff.id, "effect"); }
                    });
                }
            });
            $scope.project.effects.forEach(function (transition) {
                if (!transition.selected) {
                    if ($scope.Qt) { timeline.removeSelection(transition.id, "transition"); }
                }
            });
        }

        // Do not update lastSelectedItem when ALT is pressed
        return;
    }

    // Handle SHIFT + Click selection (for both clips and transitions)
    if (is_shift && $scope.lastSelectedItem && (item_type === "clip" || item_type === "transition")) {
        // If CTRL is not pressed, clear previous selections (unless clear_selections is false)
        if (clear_selections && !is_ctrl) {
            $scope.project.clips.forEach(function (clip) {
                clip.selected = false;
                if (clip.effects) {
                    clip.effects.forEach(function (eff) {
                        eff.selected = false;
                        if ($scope.Qt) { timeline.removeSelection(eff.id, "effect"); }
                    });
                }
                if ($scope.Qt) { timeline.removeSelection(clip.id, "clip"); }
            });
            $scope.project.effects.forEach(function (transition) {
                transition.selected = false;
                if ($scope.Qt) { timeline.removeSelection(transition.id, "transition"); }
            });
        }

        // Get the selected item
        var selectedItem = (item_type === "clip" ? $scope.project.clips : $scope.project.effects).find((item) => item.id === id);

        if (selectedItem && $scope.lastSelectedItem) {
            // Get the start (left edge) and end (right edge) of both selected items
            var selectedItemStart = selectedItem.position;
            var selectedItemEnd = selectedItem.position + (selectedItem.end - selectedItem.start);
            var lastSelectedItemStart = $scope.lastSelectedItem.position;
            var lastSelectedItemEnd = $scope.lastSelectedItem.position + ($scope.lastSelectedItem.end - $scope.lastSelectedItem.start);

            // Calculate the proper selection range based on the leftmost and rightmost edges
            var minPosition = Math.min(selectedItemStart, lastSelectedItemStart);
            var maxPosition = Math.max(selectedItemEnd, lastSelectedItemEnd);
            var minLayer = Math.min($scope.lastSelectedItem.layer, selectedItem.layer);
            var maxLayer = Math.max($scope.lastSelectedItem.layer, selectedItem.layer);

            // Select all clips and transitions that fall completely within the range
            $scope.project.clips.forEach(function (clip) {
                var clipEnd = clip.position + (clip.end - clip.start);
                if (clip.position >= minPosition && clipEnd <= maxPosition &&
                    clip.layer >= minLayer && clip.layer <= maxLayer) {
                    clip.selected = true;
                    if ($scope.Qt) { timeline.addSelection(clip.id, "clip", false); }
                }
            });

            $scope.project.effects.forEach(function (transition) {
                var transitionEnd = transition.position + (transition.end - transition.start);
                if (transition.position >= minPosition && transitionEnd <= maxPosition &&
                    transition.layer >= minLayer && transition.layer <= maxLayer) {
                    transition.selected = true;
                    if ($scope.Qt) { timeline.addSelection(transition.id, "transition", false); }
                }
            });
        }
    } else {
        // Clear selections if necessary (and not CTRL)
        if (clear_selections && !is_ctrl) {
            $scope.project.clips.forEach(function (clip) {
                clip.selected = false;
                if (clip.effects) {
                    clip.effects.forEach(function (eff) {
                        eff.selected = false;
                        if ($scope.Qt) { timeline.removeSelection(eff.id, "effect"); }
                    });
                }
                if ($scope.Qt) { timeline.removeSelection(clip.id, "clip"); }
            });
            $scope.project.effects.forEach(function (transition) {
                transition.selected = false;
                if ($scope.Qt) { timeline.removeSelection(transition.id, "transition"); }
            });
            $scope.project.effects.forEach(function (eff) {
                eff.selected = false;
                if ($scope.Qt) { timeline.removeSelection(eff.id, "effect"); }
            });
        }

        // Update selection for the clicked item (clip, transition, or effect)
        var item = null;
        if (item_type === "clip") {
            item = $scope.project.clips.find((item) => item.id === id);
        } else if (item_type === "transition") {
            item = $scope.project.effects.find((item) => item.id === id);
        } else if (item_type === "effect") {
            // Try global effect first
            item = $scope.project.effects.find((item) => item.id === id);
            // If not found, try to find in all clips and keep track of parent clip
            if (!item) {
                for (let j = 0; j < $scope.project.clips.length; j++) {
                    let clipItem = $scope.project.clips[j];
                    if (clipItem.effects) {
                        let effItem = clipItem.effects.find((e) => e.id === id);
                        if (effItem) {
                            item = effItem;
                            parent_clip = clipItem;
                            break;
                        }
                    }
                }
            }
        }
        if (item) {
            // Invert selection if CTRL is pressed and item is already selected
            if (is_ctrl && clear_selections && item.selected) {
                item.selected = false;
                if ($scope.Qt) { timeline.removeSelection(item.id, item_type); }
            } else {
                item.selected = true;
                if ($scope.Qt) { timeline.addSelection(item.id, item_type, false); }
            }
        }
    }

    // Update last selected item (do not update if ALT is pressed)
    if (!is_alt) {
        var last = null;
        if (item_type === "clip") {
            last = $scope.project.clips.find((item) => item.id === id);
        } else if (item_type === "transition") {
            last = $scope.project.effects.find((item) => item.id === id);
        } else if (item_type === "effect") {
            // Try global effect first
            last = $scope.project.effects.find((item) => item.id === id);
            if (!last) {
                for (let j = 0; j < $scope.project.clips.length; j++) {
                    let clipItem = $scope.project.clips[j];
                    if (clipItem.effects) {
                        let effItem = clipItem.effects.find((e) => e.id === id);
                        if (effItem) {
                            last = effItem;
                            break;
                        }
                    }
                }
            }
        }
        $scope.lastSelectedItem = last;
    }
};

  // Wrapper for ripple selecting clips
  $scope.selectClipRipple = function (clip_id, clear_selections, event) {
    $scope.selectItem(clip_id, "clip", clear_selections, event, true);
  };

  // Wrapper for ripple selecting transitions
  $scope.selectTransitionRipple = function (tran_id, clear_selections, event) {
    $scope.selectItem(tran_id, "transition", clear_selections, event, true);
  };

  // Wrapper for selecting clips
  $scope.selectClip = function (clip_id, clear_selections, event) {
    $scope.selectItem(clip_id, "clip", clear_selections, event, false);
  };

  // Wrapper for selecting transitions
  $scope.selectTransition = function (tran_id, clear_selections, event) {
    $scope.selectItem(tran_id, "transition", clear_selections, event, false);
  };

  // Wrapper for selecting effects (clip effects or global effects)
  $scope.selectEffect = function (effect_id, clear_selections, event) {
      $scope.selectItem(effect_id, "effect", clear_selections, event, false);
  };

  // Format the thumbnail path: http://127.0.0.1:8081/thumbnails/FILE-ID/FRAME-NUMBER/
  /**
   * @return {string}
   */
  $scope.getThumbPath = function (clip) {
    if (!clip || !clip.reader) {
      return "../images/NotFound.svg";
    }

    var has_video = clip["reader"]["has_video"];
    var has_audio = clip["reader"]["has_audio"];
    if (!has_video && has_audio) {
      return "../images/AudioThumbnail.svg";
    }
    var file_fps = clip["reader"]["fps"]["num"] / clip["reader"]["fps"]["den"];
    return $scope.ThumbServer + clip.file_id + "/" + ((file_fps * clip.start) + 1) + "/";
  };

  // Constrain canvas width values to under 32Kpixels
  $scope.canvasMaxWidth = function (desired_width) {
    return Math.min(32767, desired_width);
  };

// Find the furthest right edge on the timeline (and resize it if too small or too large)
  $scope.resizeTimeline = function () {
    let max_timeline_padding = 20;
    let min_timeline_padding = 10;
    let min_timeline_length = 300; // Length of the default OpenShot project
    // Find latest end of a clip
    var furthest_right_edge = 0;
    for (var clip_index = 0; clip_index < $scope.project.clips.length; clip_index++) {
      var clip = $scope.project.clips[clip_index];
      var right_edge = clip.position + (clip.end - clip.start);
      if (right_edge > furthest_right_edge) {
        furthest_right_edge = right_edge;
      }
    }
    // Resize timeline
    if (furthest_right_edge > $scope.project.duration) {
      if ($scope.Qt) {
        let new_timeline_length = Math.max(min_timeline_length, furthest_right_edge + min_timeline_padding);
        timeline.resizeTimeline(new_timeline_length);
        // Apply the new duration to the scope
        $scope.$apply(function () {
            $scope.project.duration = new_timeline_length;
        });
      }
    }
  };

// Show clip context menu
  $scope.showClipMenu = function (clip_id, event) {
    if ($scope.Qt && !$scope.enable_razor) {
      setTimeout(function() {
        timeline.qt_log("DEBUG", "$scope.showClipMenu");

        // Get data
        var id = clip_id.replace("clip_", "");
        var clip = findElement($scope.project.clips, "id", id);
        var is_ctrl = event && event.ctrlKey;

        // Select clip and show menu
        if (is_ctrl || clip.selected) {
          $scope.selectClip(clip_id, false);
        } else {
          $scope.selectClip(clip_id, true);
        }
        timeline.ShowClipMenu(clip_id);
      });
    }
  };

// Show clip context menu
  $scope.showEffectMenu = function (effect_id, event) {
    if ($scope.Qt && !$scope.enable_razor) {
      setTimeout(function() {
        timeline.qt_log("DEBUG", "$scope.showEffectMenu");
        var is_ctrl = event && event.ctrlKey;
        if (is_ctrl) {
            // clear effects first
            $scope.selectEffect(effect_id, true, event);
        } else {
            // don't clear effects first
            $scope.selectEffect(effect_id, false, event);
        }
        timeline.ShowEffectMenu(effect_id);
      });
    }
  };

// Show transition context menu
  $scope.showTransitionMenu = function (tran_id, event) {
    if ($scope.Qt && !$scope.enable_razor) {
      setTimeout(function() {
        timeline.qt_log("DEBUG", "$scope.showTransitionMenu");
        // Get data
        var id = tran_id.replace("transition_", "");
        var tran = findElement($scope.project.effects, "id", id);
        var is_ctrl = event && event.ctrlKey;

        // Select clip and show menu
        if (is_ctrl || tran.selected) {
          $scope.selectTransition(tran_id, false);
        } else {
          $scope.selectTransition(tran_id, true);
        }
        timeline.ShowTransitionMenu(tran_id);
      });
    }
  };

// Show track context menu
  $scope.showTrackMenu = function (layer_id) {
    if ($scope.Qt && !$scope.enable_razor) {
      setTimeout(function() {
        timeline.qt_log("DEBUG", "$scope.showTrackMenu");
        timeline.ShowTrackMenu(layer_id);
      });
    }
  };

// Show marker context menu
  $scope.showMarkerMenu = function (marker_id) {
    if ($scope.Qt && !$scope.enable_razor) {
      setTimeout(function() {
        timeline.qt_log("DEBUG", "$scope.showMarkerMenu");
        timeline.ShowMarkerMenu(marker_id);
      });
    }
  };

// Show marker context menu
  $scope.selectMarker = function (marker) {
    var frames_per_second = $scope.project.fps.num / $scope.project.fps.den;
    var marker_position_frames = Math.round(marker.position * frames_per_second) + 1;

    if ($scope.Qt) {
      timeline.SeekToKeyframe(marker_position_frames);
    }
  };

  // Show playhead context menu
  $scope.showPlayheadMenu = function (position) {
    if ($scope.Qt && !$scope.enable_razor) {
      setTimeout(function() {
        timeline.qt_log("DEBUG", "$scope.showPlayheadMenu");
        timeline.ShowPlayheadMenu(position);
      });
    }
  };

  // Show timeline context menu
  $scope.showTimelineMenu = function (e, layer_number) {
    if ($scope.Qt && !$scope.enable_razor) {
      setTimeout(function() {
        timeline.ShowTimelineMenu($scope.getJavaScriptPosition(e.pageX, null).position, layer_number);
      });
    }
  };

  // Get the name of the track
  /**
   * @return {string}
   */
  $scope.getTrackName = function (layer_label, layer_number) {
    // Determine custom label or default track name
    if (layer_label && layer_label.length > 0) {
      return layer_label;
    }
    else {
      return $scope.track_label.replace("%s", layer_number.toString());
    }
  };

  $scope.setTrackLabel = function (label) {
    $scope.track_label = label;
  };

  // Get the width of the timeline in pixels
  /**
   * @return {number}
   */
  $scope.getTimelineWidth = function (min_value) {
    // Adjust for minimim length
    return Math.max(min_value, $scope.project.duration * $scope.pixelsPerSecond);
  };

  // Seek to the beginning of the timeline
  $scope.rulerTimeClick = function () {
      $scope.movePlayhead(0.0);
      $scope.previewFrame(0.0);

      // Force a scroll event (from 1 to 0, to send the geometry to zoom slider)
      $("#scrolling_tracks").scrollLeft(1);

      // Scroll to top/left when loading a project
      $("#scrolling_tracks").animate({
        scrollTop: 0,
        scrollLeft: 0
      }, "slow");
  };

  // Get Position of item (used by Qt), both the position and track number.
  /**
   * @return {object}
   */
  $scope.getJavaScriptPosition = function (x, y) {
    // Adjust for scrollbar position
    var scrolling_tracks = $("#scrolling_tracks");
    var horz_scroll_offset = scrolling_tracks.scrollLeft();
    var scrolling_tracks_offset_left = scrolling_tracks.offset().left;
    x += horz_scroll_offset;

    // Convert x into position in seconds
    var clip_position = snapToFPSGridTime($scope, pixelToTime($scope, parseFloat(x - scrolling_tracks_offset_left)));
    if (clip_position < 0) {
      clip_position = 0;
    }

    // Get track at y position (if y passed in)
    var track = 0;
    if (y) {
      track = $scope.getJavaScriptTrack(y);
    }

    // Return position in seconds
    return { "position": clip_position, "track": track };
  };

  // Get Track number of item (used by Qt)
  $scope.getJavaScriptTrack = function (y) {
    // Adjust for scrollbar position
    var scrolling_tracks = $("#scrolling_tracks");
    var scrolling_tracks_offset_top = scrolling_tracks.offset().top;
    y += scrolling_tracks.scrollTop() - scrolling_tracks_offset_top;

      // Get the nearest track
      var nearest_track = findTrackAtLocation($scope, y);
      if (nearest_track !== null) {
        return nearest_track.number;
      } else {
        return 0;
      }
  };

// Get JSON of most recent items (used by Qt)
$scope.updateRecentItemJSON = function (item_type, item_ids, tid) {
  // Ensure item_ids is an array for consistency
  item_ids = JSON.parse(item_ids);

  // Iterate through each item_id
  item_ids.forEach(function (item_id) {
    // Find item in JSON
    var item_object = null;
    if (item_type === "clip") {
      item_object = findElement($scope.project.clips, "id", item_id);
    } else if (item_type === "transition") {
      item_object = findElement($scope.project.effects, "id", item_id);
    } else {
      // Bail out if no item_type matches
      return;
    }

    // Get recent move data
    var element_id = item_type + "_" + item_id;
    var top = 0;
    var left = 0;

    // Safely read the stored move data, or fall back to DOM values
    if (
      bounding_box.move_clips &&
      Object.prototype.hasOwnProperty.call(bounding_box.move_clips, element_id)
    ) {
      top = bounding_box.move_clips[element_id].top;
      left = bounding_box.move_clips[element_id].left;
    } else {
      var elem = $("#" + element_id);
      if (elem.length) {
        var scrolling_tracks = $("#scrolling_tracks");
        top = elem.position().top + scrolling_tracks.scrollTop();
        left = elem.position().left + scrolling_tracks.scrollLeft();
      }
    }

    // Get position of item (snapped to FPS grid)
    var clip_position = snapToFPSGridTime($scope, pixelToTime($scope, parseFloat(left)));

    // Get the nearest track
    var layer_num = 0;
    var nearest_track = findTrackAtLocation($scope, top);
    if (nearest_track !== null) {
      layer_num = nearest_track.number;
    }

    // Update scope with final position of the item
    $scope.$apply(function () {
      // Update item with new position and layer
      item_object.position = clip_position;
      item_object.layer = layer_num;
    });

    // Update clip or transition in Qt (very important)
    if (item_type === "clip") {
      timeline.update_clip_data(JSON.stringify(item_object), true, true, false, tid);
    } else if (item_type === "transition") {
      timeline.update_transition_data(JSON.stringify(item_object), true, false, tid);
    }

    // Resize timeline if it's too small to contain all clips
    $scope.resizeTimeline();

    // Hide snapline (if any)
    $scope.hideSnapline();

    // Check again for missing transitions
    var missing_transition_details = $scope.getMissingTransitions(item_object);
    if ($scope.Qt && missing_transition_details !== null && item_ids.length === 1) {
      timeline.add_missing_transition(JSON.stringify(missing_transition_details));
    }
  });

  // Remove manual move stylesheet
  if (bounding_box.elements) {
    bounding_box.elements.each(function () {
      $(this).removeClass("manual-move");
    });
  }

  // Reset bounding box
  bounding_box = {};
};

// Init bounding boxes for manual move
$scope.startManualMove = function (item_type, item_ids) {
  // Ensure item_ids is an array for consistency
  item_ids = JSON.parse(item_ids);

  // Select new objects
  $scope.$apply(function () {
    for (var clip_index = 0; clip_index < $scope.project.clips.length; clip_index++) {
      $scope.project.clips[clip_index].selected = item_ids.includes($scope.project.clips[clip_index].id);
      if ($scope.project.clips[clip_index].selected) {
        $scope.selectClip($scope.project.clips[clip_index].id, false);
      }
    }

    // Select new transition objects (and unselect others)
    for (var tran_index = 0; tran_index < $scope.project.effects.length; tran_index++) {
      $scope.project.effects[tran_index].selected = item_ids.includes($scope.project.effects[tran_index].id);
      if ($scope.project.effects[tran_index].selected) {
        $scope.selectTransition($scope.project.effects[tran_index].id, false);
      }
    }
  });

  // Helper to initialize bounding box once DOM elements exist
  function initBoundingBox(attempt) {
    attempt = attempt || 0;

    var selectedClips = $(".ui-selected");

    // If the DOM hasn't finished updating, retry a few times
    if (selectedClips.length < item_ids.length && attempt < 10) {
      setTimeout(function() { initBoundingBox(attempt + 1); }, 10);
      return;
    }

    // Prepare to store clip positions
    var scrolling_tracks = $("#scrolling_tracks");
    var vert_scroll_offset = scrolling_tracks.scrollTop();
    var horz_scroll_offset = scrolling_tracks.scrollLeft();

    // Init bounding box
    bounding_box = {};

    // Set bounding box that contains all selected clips/transitions
    selectedClips.each(function () {
      setBoundingBox($scope, $(this));
    });

    // Initialize start_clips and move_clips properties
    bounding_box.start_clips = {};
    bounding_box.move_clips = {};

    // Iterate again to set start_clips and move_clips properties
    selectedClips.each(function () {
      var element_id = $(this).attr("id");
      bounding_box.start_clips[element_id] = {
        "top": $(this).position().top + vert_scroll_offset,
        "left": $(this).position().left + horz_scroll_offset
      };
      bounding_box.move_clips[element_id] = {
        "top": $(this).position().top + vert_scroll_offset,
        "left": $(this).position().left + horz_scroll_offset
      };
    });

    // Set some additional properties
    bounding_box.previous_x = bounding_box.left;
    bounding_box.previous_y = bounding_box.top;
    bounding_box.offset_x = 0;
    bounding_box.offset_y = 0;
    bounding_box.elements = selectedClips;
    bounding_box.track_position = 0;

    // Set z-order to be above other clips/transitions
    selectedClips.each(function () {
      $(this).addClass("manual-move");
    });
  }

  // Delay to allow the DOM to update before trying to init bounding box
  setTimeout(function() { initBoundingBox(0); }, 0);
};

$scope.moveItem = function (x, y) {
  // Adjust x and y to account for the scroll position
  var scrolling_tracks = $("#scrolling_tracks");
  x += scrolling_tracks.scrollLeft();
  y += scrolling_tracks.scrollTop();

  // Calculate relative x and y within the scrolling_tracks container
  var left = x - scrolling_tracks.offset().left;
  var top = y - scrolling_tracks.offset().top;

  // Calculate movement offsets
  var x_offset = left - bounding_box.previous_x;
  var y_offset = top - bounding_box.previous_y;

  // Move the bounding box with snapping rules applied
  var results = moveBoundingBox($scope, bounding_box.previous_x, bounding_box.previous_y, x_offset, y_offset, left, top);

  // Update previous position to the new one
  bounding_box.previous_x = results.position.left;
  bounding_box.previous_y = results.position.top;

  // protect against empty .first()
  if (!bounding_box.elements || !bounding_box.elements.length) return;
  const $first = bounding_box.elements.first();
  if (!$first.length) return;
  const firstId = $first.attr("id");
  const firstStart = bounding_box.start_clips[firstId];
  if (!firstStart) return;

  // Apply snapping results to the first clip and calculate the delta for the remaining clips
  const delta_x = results.position.left - firstStart.left;
  const delta_y = results.position.top - firstStart.top;

  // Update the position of each selected element by applying the delta
  if (bounding_box.elements) {
    bounding_box.elements.each(function () {
      var element_id = $(this).attr("id");
      // Apply x_offset and y_offset to the starting position of each selected clip
      var new_left = bounding_box.start_clips[element_id].left + delta_x;
      var new_top = bounding_box.start_clips[element_id].top + delta_y;
      bounding_box.move_clips[element_id]["top"] = new_top;
      bounding_box.move_clips[element_id]["left"] = new_left;
      // Set the new position for the element
      $(this).css("left", new_left + "px");
      $(this).css("top", new_top + "px");
    });
  }
};

$scope.updateLayerIndex = function () {
  var scrolling_tracks = $("#scrolling_tracks");
  var scrolling_tracks_offset = scrolling_tracks.offset().top;

  // Loop through each layer
  for (var layer_index = 0; layer_index < $scope.project.layers.length; layer_index++) {
    var layer = $scope.project.layers[layer_index];

    // Find track element on screen (bound to this layer)
    var layer_elem = $("#track_" + layer.number);
    if (layer_elem.length) {
      // Update the top offset relative to the scrolling_tracks
      layer.y = layer_elem.offset().top - scrolling_tracks_offset + scrolling_tracks.scrollTop();
      layer.height = layer_elem.outerHeight();
    }
  }
};

  // Sort clips and transitions by position
  $scope.sortItems = function () {
    if (!$scope.enable_sorting) {
      // Sorting is disabled, do nothing
      return;
    }

    if ($scope.Qt) {
      timeline.qt_log("DEBUG", "sortItems");

      $scope.$evalAsync(function () {
        // Ensure clip list is always an array
        if (!Array.isArray($scope.project.clips)) {
          $scope.project.clips = Object.values($scope.project.clips || {});
        }
        // Sort clips by position
        $scope.project.clips = $scope.project.clips.sort(function (a, b) {
          if (a.position < b.position) {
            return -1;
          }
          if (a.position > b.position) {
            return 1;
          }
          return 0;
        });
        // Sort transitions by position second
        $scope.project.effects = $scope.project.effects.sort(function (a, b) {
          if (a.position < b.position) {
            return -1;
          }
          if (a.position > b.position) {
            return 1;
          }
          return 0;
        });
        // Sort tracks by position second
        $scope.project.layers = $scope.project.layers.sort(function (a, b) {
          if (a.number < b.number) {
            return -1;
          }
          if (a.number > b.number) {
            return 1;
          }
          return 0;
        });
      });
    }
  };

  // Find overlapping clips
  $scope.getMissingTransitions = function (original_clip) {

    var transition_size = null;

    // Get clip that matches this id
    var original_left = original_clip.position;
    var original_right = original_clip.position + (original_clip.end - original_clip.start);

    // Search through all other clips on this track, and look for overlapping ones
    for (var index = 0; index < $scope.project.clips.length; index++) {
      var clip = $scope.project.clips[index];

      // skip clips that are not on the same layer
      if (original_clip.layer !== clip.layer) {
        continue;
      }

      // is clip overlapping
      var clip_left = clip.position;
      var clip_right = clip.position + (clip.end - clip.start);

      if (original_left < clip_right && original_left > clip_left) {
        transition_size = {
          "position": original_left,
          "layer": clip.layer,
          "start": 0,
          "end": (clip_right - original_left)
        };
      }
      else if (original_right > clip_left && original_right < clip_right) {
        transition_size = {"position": clip_left, "layer": clip.layer, "start": 0, "end": (original_right - clip_left)};
      }

      if (transition_size !== null && transition_size.end >= 0.5) {
        // Found a possible missing transition
        break;
      }
      else if (transition_size !== null && transition_size.end < 0.5) {
        // Too small to be a missing transitions, clear and continue looking
        transition_size = null;
      }
    }
    // Search through all existing transitions, and don't overlap an existing one
    if (transition_size !== null) {
      for (var tran_index = 0; tran_index < $scope.project.effects.length; tran_index++) {
        var tran = $scope.project.effects[tran_index];

        // skip transitions that are not on the same layer
        if (tran.layer !== transition_size.layer) {
          continue;
        }

        var tran_left = tran.position;
        var tran_right = tran.position + (tran.end - tran.start);

        var new_tran_left = transition_size.position;
        var new_tran_right = transition_size.position + (transition_size.end - transition_size.start);

        var TOLERANCE = 0.01;
        // Check for overlapping transitions
        if (Math.abs(tran_left - new_tran_left) < TOLERANCE || Math.abs(tran_right - new_tran_right) < TOLERANCE) {
          transition_size = null; // this transition already exists
          break;
        }
      }
    }

    return transition_size;
  };

  // Search through clips and transitions to find the closest element within a given threshold
  $scope.getNearbyPosition = function (pixel_positions, threshold, ignore_ids={}, options={}) {
    // init some vars
    var smallest_diff = 900.0;
    var smallest_abs_diff = 900.0;
    var snapping_position = 0.0;
    var diffs = [];
    var keyframeTargets = [];

    var includeKeyframeSnaps = !!(options && options.includeKeyframes);

    function toNumber(value, fallback) {
      var num = parseFloat(value);
      return isNaN(num) ? fallback : num;
    }

    var frames_per_second = 0;
    if ($scope.project && $scope.project.fps) {
      var fps_num = toNumber($scope.project.fps.num, NaN);
      var fps_den = toNumber($scope.project.fps.den, NaN);
      if (isFinite(fps_num) && isFinite(fps_den) && fps_den !== 0) {
        frames_per_second = fps_num / fps_den;
      }
    }

    if (includeKeyframeSnaps && frames_per_second > 0) {
      function collectKeyframes(object) {
        if (!object) {
          return;
        }
        var entries = $scope.getKeyframes(object);
        for (var frame in entries) {
          if (!Object.prototype.hasOwnProperty.call(entries, frame)) {
            continue;
          }
          var frameNumber = parseFloat(frame);
          if (!isFinite(frameNumber)) {
            continue;
          }
          var keySeconds = (frameNumber - 1) / frames_per_second;
          var startSec = toNumber(object.start, 0);
          var positionSec = toNumber(object.position, 0);
          var timelineSeconds = positionSec + (keySeconds - startSec);
          if (!isFinite(timelineSeconds)) {
            continue;
          }
          var pixelPosition = timelineSeconds * $scope.pixelsPerSecond;
          if (!isFinite(pixelPosition)) {
            continue;
          }
          keyframeTargets.push({ position: pixelPosition });
        }
      }

      for (var clipIndex = 0; clipIndex < $scope.project.clips.length; clipIndex++) {
        var clip = $scope.project.clips[clipIndex];
        if (!clip || !(clip.selected || $scope.hasSelectedEffect(clip))) {
          continue;
        }
        collectKeyframes(clip);
      }

      for (var transitionIndex = 0; transitionIndex < $scope.project.effects.length; transitionIndex++) {
        var transition = $scope.project.effects[transitionIndex];
        if (!transition || !transition.selected) {
          continue;
        }
        collectKeyframes(transition);
      }
    }

    // Loop through each pixel position (supports multiple positions: i.e. left and right side of bounding box)
    for (var pos_index = 0; pos_index < pixel_positions.length; pos_index++) {
      var position = pixel_positions[pos_index];

      // Add clip positions to array
      for (var index = 0; index < $scope.project.clips.length; index++) {
        var clip = $scope.project.clips[index];
        var clip_left_position = clip.position * $scope.pixelsPerSecond;
        var clip_right_position = (clip.position + (clip.end - clip.start)) * $scope.pixelsPerSecond;

        // exit out if this item is in ignore_ids
        if (ignore_ids.hasOwnProperty(clip.id)) {
          continue;
        }

        // left side of clip
        let left_edge_diff = position - clip_left_position;
        if (Math.abs(left_edge_diff) <= threshold) {
          diffs.push({"diff": left_edge_diff, "position": clip_left_position, "id": clip.id, "side": "left"});
        }

        // right side of clip
        let right_edge_diff = position - clip_right_position;
        if (Math.abs(right_edge_diff) <= threshold) {
          diffs.push({"diff": right_edge_diff, "position": clip_right_position, "id": clip.id, "side": "right"});
        }

      }

      // Add transition positions to array
      for (var index = 0; index < $scope.project.effects.length; index++) {
        var transition = $scope.project.effects[index];
        var tran_left_position = transition.position * $scope.pixelsPerSecond;
        var tran_right_position = (transition.position + (transition.end - transition.start)) * $scope.pixelsPerSecond;


        // exit out if this item is in ignore_ids
        if (ignore_ids.hasOwnProperty(transition.id)) {
          continue;
        }

        // left side of transition
        let left_edge_diff = position - tran_left_position;
        if (Math.abs(left_edge_diff) <= threshold) {
          diffs.push({"diff": left_edge_diff, "position": tran_left_position});
        }

        // right side of transition
        let right_edge_diff = position - tran_right_position;
        if (Math.abs(right_edge_diff) <= threshold) {
          diffs.push({"diff": right_edge_diff, "position": tran_right_position});
        }

      }

      // Add marker positions to array
      for (var index = 0; index < $scope.project.markers.length; index++) {
        var marker = $scope.project.markers[index];
        var marker_position = marker.position * $scope.pixelsPerSecond;

        // marker position
        let left_edge_diff = position - marker_position;
        if (Math.abs(left_edge_diff) <= threshold) {
          diffs.push({"diff": left_edge_diff, "position": marker_position});
        }
      }

      // Add playhead position to array
      var playhead_pixel_position = $scope.project.playhead_position * $scope.pixelsPerSecond;
      var playhead_diff = position - playhead_pixel_position;
      if (!ignore_ids.hasOwnProperty("ruler") && !ignore_ids.hasOwnProperty("playhead")) {
        if (Math.abs(playhead_diff) <= threshold) {
          diffs.push({"diff": playhead_diff, "position": playhead_pixel_position});
        }
      }

      // Add end of timeline position
      var end_of_track = $scope.project.duration * $scope.pixelsPerSecond;
      var end_of_track_diff = position - end_of_track;
      diffs.push({"diff": end_of_track_diff, "position": end_of_track});

      if (includeKeyframeSnaps) {
        // Add visible keyframe positions
        for (var keyIndex = 0; keyIndex < keyframeTargets.length; keyIndex++) {
          var keyTarget = keyframeTargets[keyIndex];
          var keyDiff = position - keyTarget.position;
          if (Math.abs(keyDiff) <= threshold) {
            diffs.push({"diff": keyDiff, "position": keyTarget.position});
          }
        }
      }

      // Loop through diffs (and find the smallest one)
      for (var diff_index = 0; diff_index < diffs.length; diff_index++) {
        var diff = diffs[diff_index].diff;
        var diff_position = diffs[diff_index].position;
        var abs_diff = Math.abs(diff);

        // Check if this clip is nearby
        if (abs_diff < smallest_abs_diff && abs_diff <= threshold && diff_position) {
          // This one is smaller
          smallest_diff = diff;
          smallest_abs_diff = abs_diff;
          snapping_position = diff_position;
        }
      }
    }

    // no nearby found?
    if (smallest_diff === 900.0) {
      smallest_diff = 0.0;
    }

    // Return closest nearby position
    return [smallest_diff, snapping_position];
  };

  // Show the nearby snapping line
  $scope.showSnapline = function (position) {
    if (position !== $scope.snapline_position || !$scope.snapline) {
      // Only update if value has changed
      $scope.$apply(function () {
        $scope.snapline_position = position;
        $scope.snapline = true;
      });
    }
  };

  // Hide the nearby snapping line
  $scope.hideSnapline = function () {
    if ($scope.snapline) {
      // Only hide if not already hidden
      $scope.$apply(function () {
        $scope.snapline = false;
      });
    }
  };

  // Determine which CSS classes are used on a track
  /**
   * @return {string}
   * @return {string}
   */
  $scope.getTrackStyle = function (lock) {
    if (lock) {
      return "track track_disabled";
    }
    else {
      return "track";
    }
  };

  $scope.setDragging = function(value) {
    $scope.dragging = value;
  };

  $scope.getDragging = function() {
    return $scope.dragging;
  };

  // Set the CSS theme for this timeline dynamically
  $scope.setTheme = function (css) {
    $scope.$apply(function () {
      $scope.ThemeCSS = css;
    });

    // Update track Y coordinates after theme is applied
    setTimeout(function() {
      $scope.$apply(function () {
        $scope.updateLayerIndex();
      });
      loadKeyframeIcons();
    }, 0);
  }

  // Determine which CSS classes are used on a clip
  $scope.getClipStyle = function (clip) {

    var style = "";
    if (clip.selected) {
      style += "ui-selected ";
    }
    if ($scope.enable_razor) {
      style += "razor_cursor ";
    }

    return style;
  };

  // Determine which CSS classes are used on a clip label
  $scope.getClipLabelStyle = function (clip) {
    var style = "";
    if ($scope.enable_razor) {
      style += "razor_cursor";
    }
    return style;
  };

  // Determine which z-index to assign for a clip / transition.
  // Selected items z-index should be larger than unselected items.
  // The index is passed in, and represents the current position
  // in the render loop (1, 2, 3, etc...)
  $scope.getZindex = function (item, starting_index, index) {
    let unselected_zindex = starting_index;
    let selected_zindex = starting_index + 1000;

    if (item.selected) {
      return selected_zindex + index;
    } else {
      return unselected_zindex + index;
    }
  };

  // Apply JSON diff from UpdateManager (this is how the user interface communicates changes
  // to the timeline. A change can be an insert, update, or delete. The change is passed in
  // as JSON, which represents the change.
  /**
   * @return {boolean}
   * @return {boolean}
   */
  $scope.applyJsonDiff = function (jsonDiff) {
    // Loop through each UpdateAction
    for (var action_index = 0; action_index < jsonDiff.length; action_index++) {
      var action = jsonDiff[action_index];

      // Iterate through the key levels (looking for a matching element in the $scope.project)
      var previous_object = null;
      var current_object = $scope.project;
      var current_position = 0;
      var current_key = "";
      for (var key_index = 0; key_index < action.key.length; key_index++) {
        var key_value = action.key[key_index];

        // Check the key type
        if (key_value.constructor === String) {
          // Does the key value exist in scope?, No match, skip this action
          if (!current_object.hasOwnProperty(key_value)) {
            continue;
          }
          // set current level and previous level
          previous_object = current_object;
          current_object = current_object[key_value];
          current_key = key_value;

        } else if (key_value.constructor === Object) {
          // Get the id from the object (if any)
          var id = null;
          if ("id" in key_value) {
            id = key_value["id"];
          }
          // Be sure the current_object is an Array
          if (current_object.constructor === Array) {
            // Filter the current_object for a specific id
            current_position = 0;
            for (var child_index = 0; child_index < current_object.length; child_index++) {
              var child_object = current_object[child_index];

              // Find matching child
              if (child_object.hasOwnProperty("id") && child_object.id === id) {
                // set current level and previous level
                previous_object = current_object;
                current_object = child_object;
                break; // found child, stop looping
              }
              // increment index
              current_position++;
            }
          }
        }
      }

      // Now that we have a matching object in the $scope.project...
      if (current_object) {
        // INSERT OBJECT
        if (action.type === "insert") {
          // Insert action's value into current_object
          if (current_object.constructor === Array) {
            // push new element into array
            current_object.push(action.value);
          } else {
            // replace the entire value
            if (previous_object.constructor === Array) {
              // replace entire value in OBJECT
              previous_object[current_position] = action.value;
            } else if (previous_object.constructor === Object) {
              // replace entire value in OBJECT
              previous_object[current_key] = action.value;
            }
          }
        } else if (action.type === "update") {
          // UPDATE OBJECT
          // Update: If action and current object are Objects
          if (current_object.constructor === Object && action.value.constructor === Object) {
            for (var update_key in action.value) {
              if (action.value.hasOwnProperty(update_key)) {
                current_object[update_key] = action.value[update_key];
              }
            }
          } else {
            // replace the entire value
            if (previous_object.constructor === Array) {
              // replace entire value in OBJECT
              previous_object[current_position] = action.value;
            } else if (previous_object.constructor === Object) {
              // replace entire value in OBJECT
              previous_object[current_key] = action.value;
            }
          }
        } else if (action.type === "delete") {
          // DELETE OBJECT
          // delete current object from its parent (previous object)
          if (previous_object.constructor === Array) {
            previous_object.splice(current_position, 1);
          } else if (previous_object.constructor === Object) {
            delete previous_object[current_key];
          }
        }

        // Re-sort clips and transitions array
        $scope.sortItems();

        // Re-index Layer Y values after DOM has been updated
        setTimeout(function() {
          $scope.$apply(function () {
            $scope.updateLayerIndex();
          });
        }, 0);
      }
    }

    // return true
    return true;
  };

  // Force Angular to refresh (i.e. when selections change outside)
  $scope.refreshTimeline = function () {
    $scope.$apply();
  }

  // Load entire project data JSON from UpdateManager (i.e. user opened an existing project)
  /**
   * @return {boolean}
   */
  $scope.loadJson = function (EntireProjectJson) {

    $scope.$apply(function () {
      // Update the entire JSON object for the entire timeline
      $scope.project = EntireProjectJson.value;
      // Un-select any selected items
      $scope.selectClip("", true);
    });

    // Re-sort clips and transitions array
    $scope.sortItems();

    // Re-index Layer Y values
    $scope.updateLayerIndex();

    // Force a scroll event (from 1 to 0, to send the geometry to zoom slider)
    $("#scrolling_tracks").scrollLeft(1);

    // Scroll to top/left when loading a project
    $("#scrolling_tracks").animate({
      scrollTop: 0,
      scrollLeft: 0
    }, "slow");

    // Update playhead position and time readout (reset to zero)
    $scope.movePlayhead(0.0);

    // Force ruler to redraw
    $scope.project.scale += 1/100000

    // Apply all changes
    $scope.$apply();

    // return true
    return true;
  };

// ############# END QT FUNCTIONS #################### //


// ############ DEBUG STUFFS ################## //

  $scope.toggleDebug = function () {
    $scope.debug = $scope.debug !== true;
  };

  // Debug method to add clips to the $scope
  $scope.addClips = function (numClips) {
    var startNum = $scope.project.clips.length + 1;
    var positionNum = 0;
    for (var x = 0; x < parseInt(numClips, 10); x++) {
      $scope.project.clips.push({
        id: x.toString(),
        layer: 0,
        image: "./media/images/thumbnail.png",
        locked: false,
        duration: 50,
        start: 0,
        end: 50,
        position: positionNum,
        title: "Clip B",
        effects: [],
        images: {start: 3, end: 7},
        show_audio: false,
        alpha: {Points: []},
        location_x: {Points: [
				  {co: {X: 1.0, Y: -0.5}, interpolation: 0},
          {co: {X: 30.0, Y: -0.4}, interpolation: 1},
          {co: {X: 100.0, Y: -0.4}, interpolation: 2}
        ]},
        location_y: {Points: []},
        scale_x: {Points: []},
        scale_y: {Points: []},
        rotation: {Points: []},
        time: {Points: []},
        volume: {Points: []},
        reader: { has_video: false, has_audio: true }
      });
      startNum++;
      positionNum += 50;
    }
    $scope.numClips = "";
  };

  // Debug method to add effects to a clip's $scope
  $scope.addEffect = function (clipNum) {
    //find the clip in the json data
    var elm = findElement($scope.project.clips, "id", clipNum);
    elm.effects.push({
      effect: "Old Movie",
      icon: "om.png"
    });
    $scope.clipNum = "";
  };

  // Debug method to add a marker to the $scope
  $scope.addMarker = function (markLoc) {
    $scope.project.markers.push({
      position: parseInt(markLoc, 10),
      icon: "blue.png",
      vector: "blue"
    });
    $scope.markLoc = "";
  };

  // Debug method to change a clip's image
  $scope.changeImage = function (startImage) {
    $scope.project.clips[2].images.start = startImage;
    $scope.startImage = "";
  };

});
