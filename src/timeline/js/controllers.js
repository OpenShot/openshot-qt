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
/*global App, timeline, bounding_box, setBoundingBox, moveBoundingBox, findElement*/
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
    playhead_position: 10, //position of play head
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
  $scope.playhead_height = 300;
  $scope.playheadTime = secondsToTime($scope.project.playhead_position, $scope.project.fps.num, $scope.project.fps.den);
  $scope.snapline_position = 0.0;
  $scope.snapline = false;
  $scope.enable_snapping = true;
  $scope.enable_razor = false;
  $scope.enable_playhead_follow = true;
  $scope.keyframe_prop_filter = "";
  $scope.debug = false;
  $scope.min_width = 1024;
  $scope.track_label = "Track %s";
  $scope.enable_sorting = true;
  $scope.ThumbServer = "http://127.0.0.1/";

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
    $scope.project.playhead_position = position_seconds;
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
    var absolute_seek_frames = clip_position_frames + parseInt(point);

    if ($scope.Qt) {
      timeline.SeekToKeyframe(absolute_seek_frames)
    }
  }

  // Get an array of keyframe points for the selected clips
  $scope.getKeyframes = function (object) {
    // List of keyframes
    var keyframes = {};

    var frames_per_second = $scope.project.fps.num / $scope.project.fps.den;
    var clip_start_x = Math.round(object.start * frames_per_second) + 1;
    var clip_end_x = Math.round(object.end * frames_per_second) + 1;

    // Loop through properties of an object (clip/transition), looking for keyframe points
    for (var child in object) {
      if (!object.hasOwnProperty(child)) {
        //The current property is not a direct property
        continue;
      }
      if ($scope.keyframe_prop_filter.length > 0 &&
        !child.toLowerCase().includes($scope.keyframe_prop_filter.toLowerCase())) {
        // Not the current filter property
        continue;
      }
      // Determine if this property is a Keyframe
      if (typeof object[child] === "object" && "Points" in object[child] && object[child].Points.length > 1) {
        for (var point = 0; point < object[child].Points.length; point++) {
          var co = object[child].Points[point].co;
          var interpolation = $scope.lookupInterpolation(object[child].Points[point].interpolation);
          if (co.X >= clip_start_x && co.X <= clip_end_x) {
            // Only add keyframe coordinates that are within the bounds of the clip
            keyframes[co.X] = interpolation;
          }
        }
      }
      // Determine if this property is a Color Keyframe
      if (typeof object[child] === "object" && "red" in object[child] && object[child]["red"].Points.length > 1) {
        for (var color_point = 0; color_point < object[child]["red"].Points.length; color_point++) {
          var color_co = object[child]["red"].Points[color_point].co;
          var color_interpolation = $scope.lookupInterpolation(object[child]["red"].Points[color_point].interpolation);
          if (color_co.X >= clip_start_x && color_co.X <= clip_end_x) {
            // Only add keyframe coordinates that are within the bounds of the clip
            keyframes[color_co.X] = color_interpolation;
          }
        }
      }
    }
    // Determine if this property contains effects (i.e. clips have their own effects)
    if ("effects" in object) {
      for (var effect in object["effects"]) {
        // Loop through properties of an effect, looking for keyframe points
        for (var effect_prop in object["effects"][effect]) {
          if (!object["effects"][effect].hasOwnProperty(effect_prop)) {
            //The current property is not a direct property
            continue;
          }
          if ($scope.keyframe_prop_filter.length > 0 &&
            !effect_prop.toLowerCase().includes($scope.keyframe_prop_filter.toLowerCase())) {
            // Not the current filter property
            continue;
          }
          // Determine if this property is a Keyframe
          if (typeof object["effects"][effect][effect_prop] === "object"
            && "Points" in object["effects"][effect][effect_prop] && object["effects"][effect][effect_prop].Points.length > 1) {
            for (var effect_point = 0; effect_point < object["effects"][effect][effect_prop].Points.length; effect_point++) {
              var effect_co = object["effects"][effect][effect_prop].Points[effect_point].co;
              var effect_interpolation = $scope.lookupInterpolation(object["effects"][effect][effect_prop].Points[effect_point].interpolation);
              if (effect_co.X >= clip_start_x && effect_co.X <= clip_end_x) {
                // Only add keyframe coordinates that are within the bounds of the clip
                keyframes[effect_co.X] = effect_interpolation;
              }
            }
          }
          // Determine if this property is a Color Keyframe
          if (typeof object["effects"][effect][effect_prop] === "object"
            && "red" in object["effects"][effect][effect_prop]
            && object["effects"][effect][effect_prop]["red"].Points.length > 1) {
            for (var effect_color_point = 0; effect_color_point < object["effects"][effect][effect_prop]["red"].Points.length; effect_color_point++) {
              var effect_color_co = object["effects"][effect][effect_prop]["red"].Points[effect_color_point].co;
              var effect_color_interpolation = $scope.lookupInterpolation(object["effects"][effect][effect_prop]["red"].Points[effect_color_point].interpolation);
              if (effect_color_co.X >= clip_start_x && effect_color_co.X <= clip_end_x) {
                // Only add keyframe coordinates that are within the bounds of the clip
                keyframes[effect_color_co.X] = effect_color_interpolation;
              }
            }
          }
        }
      }
    }

    // Return keyframe array
    return keyframes;
  };

  // Determine track top (in vertical pixels)
  $scope.getTrackTop = function (layer) {
    // Get scrollbar position
    var scrolling_tracks = $("#scrolling_tracks");
    var vert_scroll_offset = scrolling_tracks.scrollTop();

    // Find this tracks Y location
    var track_id = "div#track_" + layer;
    if ($(track_id).length) {
      return $(track_id).position().top + vert_scroll_offset;
    }
    else {
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

    // Calculate the position to scroll the timeline to to center on the requested time
    var pixelToCenterOn = parseFloat(centerTime) * $scope.pixelsPerSecond;
    var scrollPosition = Math.max(pixelToCenterOn - (scrollingTracksWidth / 2.0), 0);

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

  // Set the audio data for a clip
  $scope.setAudioData = function (clip_id, audio_data) {
    // Find matching clip
    for (var clip_index = 0; clip_index < $scope.project.clips.length; clip_index++) {
      if ($scope.project.clips[clip_index].id === clip_id) {
        // Set audio data
        $scope.$apply(function () {
          $scope.project.clips[clip_index].audio_data = audio_data;
          $scope.project.clips[clip_index].show_audio = true;
        });
        timeline.qt_log("DEBUG", "Audio data successful set on clip JSON");
        break;
      }

      // Draw audio data
      drawAudio($scope, clip_id);
    }
  };

  // Hide the audio waveform for a clip
  $scope.hideAudioData = function (clip_id) {
    // Find matching clip
    for (var clip_index = 0; clip_index < $scope.project.clips.length; clip_index++) {
      if ($scope.project.clips[clip_index].id === clip_id) {
        // Set audio data
        $scope.$apply(function () {
          $scope.project.clips[clip_index].show_audio = false;
          $scope.project.clips[clip_index].audio_data = [];
        });
        break;
      }
    }
  };

  // Redraw all audio waveforms on the timeline (if any)
  $scope.reDrawAllAudioData = function () {
    // Find matching clip
    for (var clip_index = 0; clip_index < $scope.project.clips.length; clip_index++) {
      if ("audio_data" in $scope.project.clips[clip_index] && $scope.project.clips[clip_index].audio_data.length > 0) {
        // Redraw audio data (since it has audio data)
        drawAudio($scope, $scope.project.clips[clip_index].id);
      }
    }
  };

  // Does clip have audio_data?
  $scope.hasAudioData = function (clip_id) {
    // Find matching clip
    for (var clip_index = 0; clip_index < $scope.project.clips.length; clip_index++) {
      if ($scope.project.clips[clip_index].id === clip_id && "audio_data" in $scope.project.clips[clip_index] && $scope.project.clips[clip_index].audio_data.length > 0) {
        return true;
      }
    }
    return false;
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
      if (enable_snapping) {
        $(".droppable").draggable("option", "snapTolerance", 20);
      }
      else {
        $(".droppable").draggable("option", "snapTolerance", 0);
      }
    });
  };

  // Change the razor mode
  $scope.setRazorMode = function (enable_razor) {
    $scope.$apply(function () {
      $scope.enable_razor = enable_razor;
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
      case "Object Detector":
        return "#636363";
      case "Parametric EQ":
        return "#708090";
      case "Pixelate":
        return	"#9fa131";
      case "Robotization":
        return "#CC5500";
      case "Saturation":
        return "#ff3d00";
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

      clip_json.position = clip_position;
      clip_json.layer = $scope.getTrackAtY(y).number;

      // Push new clip onto stack
      $scope.project.clips.push(clip_json);
    });
  };

  // Update cache json
  $scope.renderCache = function (cache_json) {
    // Push new clip onto stack
    $scope.project.progress = cache_json;

    //clear the canvas first
    var ruler = $("#progress");
    var ctx = ruler[0].getContext("2d");
    ctx.clearRect(0, 0, ruler.width(), ruler.height());

    // Determine fps & and get cached ranges
    var fps = $scope.project.fps.num / $scope.project.fps.den;
    var progress = $scope.project.progress.ranges;

    // Loop through each cached range of frames, and draw rect
    for (var p = 0; p < progress.length; p++) {
      //get the progress item details
      var start_second = parseFloat(progress[p]["start"]) / fps;
      var stop_second = parseFloat(progress[p]["end"]) / fps;

      //figure out the actual pixel position, constrained by max width
      var start_pixel = $scope.canvasMaxWidth(start_second * $scope.pixelsPerSecond);
      var stop_pixel = $scope.canvasMaxWidth(stop_second * $scope.pixelsPerSecond);
      var rect_length = stop_pixel - start_pixel;
      if (rect_length < 1) {
        break;
      }
      //get the element and draw the rects
      ctx.beginPath();
      ctx.rect(start_pixel, 0, rect_length, 5);
      ctx.fillStyle = "#4B92AD";
      ctx.fill();
    }
  };

  // Clear all selections
  $scope.clearAllSelections = function () {
    // Clear the selections on the main window
    $scope.selectTransition("", true);
    $scope.selectEffect("", true);

    // Update scope
    $scope.$apply(function () {
      for (var clip_index = 0; clip_index < $scope.project.clips.length; clip_index++) {
        $scope.project.clips[clip_index].selected = false;
      }
      for (var effect_index = 0; effect_index < $scope.project.effects.length; effect_index++) {
        $scope.project.effects[effect_index].selected = false;
      }
    });
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

  // Select clip in scope
  $scope.selectClip = function (clip_id, clear_selections, event) {
    // Trim clip_id
    var id = clip_id.replace("clip_", "");

    // Is CTRL pressed?
    var is_ctrl = event && event.ctrlKey;

    // Clear transitions selection if needed
    if (id !== "" && clear_selections && !is_ctrl) {
      $scope.selectTransition("", true);
    }
    // Call slice method and exit (don't actually select the clip)
    if (id !== "" && $scope.enable_razor && $scope.Qt && event) {
      var cursor_seconds = $scope.getJavaScriptPosition(event.clientX, null).position;
      timeline.RazorSliceAtCursor(id, "", cursor_seconds);

      // Don't actually select clip
      return;
    }

    // Update selection for clips
    for (var clip_index = 0; clip_index < $scope.project.clips.length; clip_index++) {
      if ($scope.project.clips[clip_index].id === id) {
        // Invert selection if CTRL is pressed and not forced add and already selected
        if (is_ctrl && clear_selections && ($scope.project.clips[clip_index].selected === true)) {
          $scope.project.clips[clip_index].selected = false;
          if ($scope.Qt) {
            timeline.removeSelection($scope.project.clips[clip_index].id, "clip");
          }
        }
        else {
          $scope.project.clips[clip_index].selected = true;
          if ($scope.Qt) {
            // Do not clear selection if CTRL is pressed
            if (is_ctrl) {
              timeline.addSelection(id, "clip", false);
            }
            else {
              timeline.addSelection(id, "clip", clear_selections);
            }
          }
        }
      }
      else if (clear_selections && !is_ctrl) {
        $scope.project.clips[clip_index].selected = false;
        if ($scope.Qt) {
          timeline.removeSelection($scope.project.clips[clip_index].id, "clip");
        }
      }
    }
  };

  // Select transition in scope
  $scope.selectTransition = function (tran_id, clear_selections, event) {
    // Trim tran_id
    var id = tran_id.replace("transition_", "");

    // Is CTRL pressed?
    var is_ctrl = event && event.ctrlKey;

    // Clear clips selection if needed
    if (id !== "" && clear_selections && !is_ctrl) {
      $scope.selectClip("", true);
    }
    // Call slice method and exit (don't actually select the transition)
    if (id !== "" && $scope.enable_razor && $scope.Qt && event) {
      var cursor_seconds = $scope.getJavaScriptPosition(event.clientX, null).position;
      timeline.RazorSliceAtCursor("", id, cursor_seconds);

      // Don't actually select transition
      return;
    }

    // Update selection for transitions
    for (var tran_index = 0; tran_index < $scope.project.effects.length; tran_index++) {
      if ($scope.project.effects[tran_index].id === id) {
        // Invert selection if CTRL is pressed and not forced add and already selected
        if (is_ctrl && clear_selections && ($scope.project.effects[tran_index].selected === true)) {
          $scope.project.effects[tran_index].selected = false;
          if ($scope.Qt) {
            timeline.removeSelection($scope.project.effects[tran_index].id, "transition");
          }
        }
        else {
          $scope.project.effects[tran_index].selected = true;
          if ($scope.Qt) {
            // Do not clear selection if CTRL is pressed
            if (is_ctrl) {
              timeline.addSelection(id, "transition", false);
            }
            else {
              timeline.addSelection(id, "transition", clear_selections);
            }
          }
        }
      }
      else if (clear_selections && !is_ctrl) {
        $scope.project.effects[tran_index].selected = false;
        if ($scope.Qt) {
          timeline.removeSelection($scope.project.effects[tran_index].id, "transition");
        }
      }
    }
  };

  // Format the thumbnail path: http://127.0.0.1:8081/thumbnails/FILE-ID/FRAME-NUMBER/
  /**
   * @return {string}
   * @return {string}
   */
  $scope.getThumbPath = function (clip) {
    var has_video = clip["reader"]["has_video"];
    var has_audio = clip["reader"]["has_audio"];
    if (!has_video && has_audio) {
      return "../images/AudioThumbnail.svg";
    }
    var file_fps = clip["reader"]["fps"]["num"] / clip["reader"]["fps"]["den"];
    return $scope.ThumbServer + clip.file_id + "/" + ((file_fps * clip.start) + 1) + "/";
  };

  // Select transition in scope
  $scope.selectEffect = function (effect_id) {
    if ($scope.Qt) {
      timeline.addSelection(effect_id, "effect", true);
    }
  };

  // Constrain canvas width values to under 32Kpixels
  $scope.canvasMaxWidth = function (desired_width) {
    return Math.min(32767, desired_width);
  };

// Find the furthest right edge on the timeline (and resize it if too small)
  $scope.resizeTimeline = function () {
    // Unselect all clips
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
        timeline.resizeTimeline(furthest_right_edge + 10);
        $scope.project.duration = furthest_right_edge + 10;
      }
    } else if ( $scope.project.duration - furthest_right_edge > 20) {
      if ($scope.Qt) {
        $scope.project.duration = furthest_right_edge;
        timeline.resizeTimeline(furthest_right_edge);
      }
    }
  };

// Show clip context menu
  $scope.showClipMenu = function (clip_id, event) {
    if ($scope.Qt && !$scope.enable_razor) {
      timeline.qt_log("DEBUG", "$scope.showClipMenu");
      $scope.selectClip(clip_id, false, event);
      timeline.ShowClipMenu(clip_id);
    }
  };

// Show clip context menu
  $scope.showEffectMenu = function (effect_id) {
    if ($scope.Qt && !$scope.enable_razor) {
      timeline.qt_log("DEBUG", "$scope.showEffectMenu");
      timeline.ShowEffectMenu(effect_id);
    }
  };

// Show transition context menu
  $scope.showTransitionMenu = function (tran_id, event) {
    if ($scope.Qt && !$scope.enable_razor) {
      timeline.qt_log("DEBUG", "$scope.showTransitionMenu");
      $scope.selectTransition(tran_id, false, event);
      timeline.ShowTransitionMenu(tran_id);
    }
  };

// Show track context menu
  $scope.showTrackMenu = function (layer_id) {
    if ($scope.Qt && !$scope.enable_razor) {
      timeline.qt_log("DEBUG", "$scope.showTrackMenu");
      timeline.ShowTrackMenu(layer_id);
    }
  };

// Show marker context menu
  $scope.showMarkerMenu = function (marker_id) {
    if ($scope.Qt && !$scope.enable_razor) {
      timeline.qt_log("DEBUG", "$scope.showMarkerMenu");
      timeline.ShowMarkerMenu(marker_id);
    }
  };

  // Show playhead context menu
  $scope.showPlayheadMenu = function (position) {
    if ($scope.Qt && !$scope.enable_razor) {
      timeline.qt_log("DEBUG", "$scope.showPlayheadMenu");
      timeline.ShowPlayheadMenu(position);
    }
  };

  // Show timeline context menu
  $scope.showTimelineMenu = function (e, layer_number) {
    if ($scope.Qt && !$scope.enable_razor) {
      timeline.ShowTimelineMenu($scope.getJavaScriptPosition(e.pageX, null).position, layer_number);
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
    var clip_position = parseFloat(x - scrolling_tracks_offset_left) / parseFloat($scope.pixelsPerSecond);
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
    y += scrolling_tracks.scrollTop();

    // Return number of track
    return parseInt($scope.getTrackAtY(y - scrolling_tracks_offset_top).number, 10);
  };

  // Get JSON of most recent item (used by Qt)
  $scope.updateRecentItemJSON = function (item_type, item_id) {

    // Find item in JSON
    var item_object = null;
    if (item_type === "clip") {
      item_object = findElement($scope.project.clips, "id", item_id);
    }
    else if (item_type === "transition") {
      item_object = findElement($scope.project.effects, "id", item_id);
    }
    else {
      // Bail out if no id found
      return;
    }
    // Get position of item
    var scrolling_tracks_offset_top = $("#scrolling_tracks").offset().top;
    var clip_position = parseFloat(bounding_box.left) / parseFloat($scope.pixelsPerSecond);
    var layer_num = $scope.getTrackAtY(bounding_box.track_position - scrolling_tracks_offset_top).number;

    // update scope with final position of items
    $scope.$apply(function () {
      // update item
      item_object.position = clip_position;
      item_object.layer = layer_num;
    });

    // update clip in Qt (very important =)
    if (item_type === "clip") {
      timeline.update_clip_data(JSON.stringify(item_object), true, true, false);
    }
    else if (item_type === "transition") {
      timeline.update_transition_data(JSON.stringify(item_object), true, false);
    }

    // Resize timeline if it's too small to contain all clips
    $scope.resizeTimeline();

    // Hide snapline (if any)
    $scope.hideSnapline();

    // Check again for missing transitions
    var missing_transition_details = $scope.getMissingTransitions(item_object);
    if ($scope.Qt && missing_transition_details !== null) {
      timeline.add_missing_transition(JSON.stringify(missing_transition_details));
    }
    // Remove manual move stylesheet
    if (bounding_box.element) {
      bounding_box.element.removeClass("manual-move");
    }

    // Remove CSS class (after the drag)
    bounding_box = {};
  };

  // Init bounding boxes for manual move
  $scope.startManualMove = function (item_type, item_id) {
    // Select the item
    $scope.$apply(function () {
      if (item_type === "clip") {
        $scope.selectClip(item_id, true);
      }
      else if (item_type === "transition") {
        $scope.selectTransition(item_id, true);
      }
    });

    // Select new clip object (and unselect others)
    // This needs to be done inline due to async issues with the
    // above calls to selectClip/selectTransition
    for (var clip_index = 0; clip_index < $scope.project.clips.length; clip_index++) {
      $scope.project.clips[clip_index].selected = $scope.project.clips[clip_index].id === item_id;
    }

    // Select new transition object (and unselect others)
    for (var tran_index = 0; tran_index < $scope.project.effects.length; tran_index++) {
      $scope.project.effects[tran_index].selected = $scope.project.effects[tran_index].id === item_id;
    }

    // JQuery selector for element (clip or transition)
    var element_id = "#" + item_type + "_" + item_id;

    // Init bounding box
    bounding_box = {};
    setBoundingBox($scope, $(element_id));

    // Init some variables to track the changing position
    bounding_box.previous_x = bounding_box.left;
    bounding_box.previous_y = bounding_box.top;
    bounding_box.offset_x = 0;
    bounding_box.offset_y = 0;
    bounding_box.element = $(element_id);
    bounding_box.track_position = 0;

    // Set z-order to be above other clips/transitions
    if (item_type !== "os_drop" && bounding_box.element) {
      bounding_box.element.addClass("manual-move");
    }
  };

  // Move a new clip to the timeline
  $scope.moveItem = function (x, y, item_type) {
    var scrolling_tracks = $("#scrolling_tracks");
    x += scrolling_tracks.scrollLeft();
    y += scrolling_tracks.scrollTop();

    // Convert x and y into timeline vars
    var scrolling_tracks_offset_left = scrolling_tracks.offset().left;
    var scrolling_tracks_offset_top = scrolling_tracks.offset().top;

    // Calculate the x,y of cursor
    var left = parseFloat(x - scrolling_tracks_offset_left);
    var top = parseFloat(y - scrolling_tracks_offset_top);

    // Calculate amount to move transitions
    var x_offset = left - bounding_box.previous_x;
    var y_offset = top - bounding_box.previous_y;

    // Move the bounding box and apply snapping rules
    var results = moveBoundingBox($scope, bounding_box.previous_x, bounding_box.previous_y, x_offset, y_offset, left, top);

    // Track previous values
    bounding_box.previous_x = results.position.left;
    bounding_box.previous_y = results.position.top;

    // Loop through each layer (looking for the closest track based on Y coordinate)
    bounding_box.track_position = 0;
    for (var layer_index = $scope.project.layers.length - 1; layer_index >= 0; layer_index--) {
      var layer = $scope.project.layers[layer_index];

      // Compare position of track to Y param (for unlocked tracks)
      if (!layer.lock) {
        if ((top < layer.y && top > bounding_box.track_position) || bounding_box.track_position === 0) {
          // return first matching layer
          bounding_box.track_position = layer.y;
        }
      }
    }
    //change the element location
    if (bounding_box.element) {
      bounding_box.element.css("left", results.position.left);
      bounding_box.element.css("top", bounding_box.track_position - scrolling_tracks_offset_top);
    }
  };

  // Update X,Y indexes of tracks / layers (anytime the project.layers scope changes)
  $scope.updateLayerIndex = function () {

    if ($scope.Qt) {
      timeline.qt_log("DEBUG", "updateLayerIndex");
    }

    var scrolling_tracks = $("#scrolling_tracks");
    var vert_scroll_offset = scrolling_tracks.scrollTop();

    // Loop through each layer
    for (var layer_index = 0; layer_index < $scope.project.layers.length; layer_index++) {
      var layer = $scope.project.layers[layer_index];

      // Find element on screen (bound to this layer)
      var layer_elem = $("#track_" + layer.number);
      if (layer_elem.offset()) {
        // Update the top offset
        layer.y = layer_elem.offset().top + vert_scroll_offset;
      }
    }
    // Update playhead height
    $scope.playhead_height = $("#track-container").height();
    $(".playhead-line").height($scope.playhead_height);
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
        // Sort by position second
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
  $scope.getNearbyPosition = function (pixel_positions, threshold, ignore_ids={}) {
    // init some vars
    var smallest_diff = 900.0;
    var smallest_abs_diff = 900.0;
    var snapping_position = 0.0;
    var diffs = [];

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

  // Find a track JSON object at a given y coordinate (if any)
  /**
   * @return {object}
   */
  $scope.getTrackAtY = function (y) {
    // Loop through each layer (looking for the closest track based on Y coordinate)
    for (var layer_index = $scope.project.layers.length - 1; layer_index >= 0; layer_index--) {
      var layer = $scope.project.layers[layer_index];

      // Compare position of track to Y param and return first matching layer
      if (layer.y > y) {
        return layer;
      }
    }

    // no layer found (return top layer... if any)
    if ($scope.project.layers.length > 0) {
      return $scope.project.layers[0];
    }
    else {
      return null;
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

  $scope.markerPath = function(marker) {
    var dir = "media/images/markers";
    var marker_file;
    if(marker.hasOwnProperty("vector")) {
      marker_file = `${marker.vector}.svg`;
    } else if(marker.icon === "blue.png") {
      marker_file = "blue.svg";
    } else {
      marker_file = marker.icon;
    }
    return `${dir}/${marker_file}`;
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
          // Does the key value exist in scope?, No match, bail out
          if (!current_object.hasOwnProperty(key_value)) {
            return false;
          }
          // set current level and previous level
          previous_object = current_object;
          current_object = current_object[key_value];
          current_key = key_value;

        }
        else if (key_value.constructor === Object) {
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
          }
          else {
            // replace the entire value
            if (previous_object.constructor === Array) {
              // replace entire value in OBJECT
              previous_object[current_position] = action.value;
            }
            else if (previous_object.constructor === Object) {
              // replace entire value in OBJECT
              previous_object[current_key] = action.value;
            }
          }
        }
        else if (action.type === "update") {
          // UPDATE OBJECT
          // Update: If action and current object are Objects
          if (current_object.constructor === Object && action.value.constructor === Object) {
            for (var update_key in action.value) {
              if (update_key in current_object) {
                // Only copy over keys that exist in both action and current_object
                current_object[update_key] = action.value[update_key];
              }
            }
          }
          else {
            // replace the entire value
            if (previous_object.constructor === Array) {
              // replace entire value in OBJECT
              previous_object[current_position] = action.value;
            }
            else if (previous_object.constructor === Object) {
              // replace entire value in OBJECT
              previous_object[current_key] = action.value;
            }
          }
        }
        else if (action.type === "delete") {
          // DELETE OBJECT
          // delete current object from it's parent (previous object)
          previous_object.splice(current_position, 1);
        }
        // Resize timeline if it's too small to contain all clips
        $scope.resizeTimeline();

        // Re-sort clips and transitions array
        $scope.sortItems();

        // Re-index Layer Y values
        $scope.updateLayerIndex();
      }
    }
    // return true
    return true;
  };

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

    // Update playhead position and time readout
    $scope.movePlayhead($scope.project.playhead_position);

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
