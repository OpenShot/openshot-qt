/**
 * @file
 * @brief Misc Functions used by the OpenShot Timeline
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


// Find a JSON element / object with a particular value in the json data
function findElement(arr, propName, propValue) {
  // Loop through array looking for a matching element
  for (var i = 0; i < arr.length; i++) {
    if (arr[i][propName] === propValue) {
      return arr[i];
    }
  }

}

// Get the height of the track container (minus bottom margin of last track)
function getTrackContainerHeight() {

  var track_margin = 0;
  var track_object = $(".track");
  if (track_object.length) {
    if (track_object.css("margin-bottom")) {
      track_margin = parseInt(track_object.css("margin-bottom").replace("px", ""), 10);
    }
  }

  return $("#track-container").height() - track_margin;
}

// Draw the audio wave on a clip
function drawAudio(scope, clip_id) {
  //get the clip in the scope
  var clip = findElement(scope.project.clips, "id", clip_id);

  if (clip.show_audio) {
    var element = $("#clip_" + clip_id);

    // Determine start and stop samples
    var samples_per_second = 20;
    var block_width = 2; // 2 pixel wide blocks as smallest size
    var start_sample = Math.round(clip.start * samples_per_second);
    var end_sample = clip.end * samples_per_second;

    // Determine divisor for zoom scale
    var sample_divisor = samples_per_second / scope.pixelsPerSecond;

    //show audio container
    element.find(".audio-container").show();

    // Get audio canvas context
    var audio_canvas = element.find(".audio");
    var ctx = audio_canvas[0].getContext("2d", {alpha: false});

    // Clear canvas
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);

    var color = "#2a82da"; // rgb(42,130,218)
    var color_transp = "rgba(42,130,218,0.5)";

    ctx.strokeStyle = color;

    // Find the midpoint
    var mid_point = audio_canvas.height() - 8;
    var scale = mid_point;

    // Draw the mid-point line
    ctx.beginPath();
    ctx.lineWidth = 1;
    ctx.moveTo(0, mid_point);
    ctx.lineTo(audio_canvas.width(), mid_point);
    ctx.stroke();


    var sample = 0.0,
      // Variables for accumulation
      avg = 0.0,
      avg_cnt = 0,
      max = 0.0,
      last_x = 0;

    // Ensure that the waveform canvas doesn't exceed its max
    // dimensions, even if it means we can't draw the full audio.
    // (If we try to go over the max width, the whole canvas disappears)
    var final_sample = end_sample;
    var audio_width = (end_sample - start_sample) / sample_divisor;
    var usable_width = scope.canvasMaxWidth(audio_width);
    if (audio_width > usable_width) {
      // Just go as far as we can, then cut off the remaining waveform
      final_sample = (usable_width * sample_divisor) - 1;
    }

    // Go through all of the (reduced) samples
    // And whenever enough are "collected", draw a block
    for (var i = start_sample; i < final_sample; i++) {
      // Flip negative values up
      sample = Math.abs(clip.audio_data[i]);
      // X-Position of *next* sample
      var x = Math.floor((i + 1 - start_sample) / sample_divisor);

      avg += sample;
      avg_cnt++;
      max = Math.max(max, sample);

      if (x >= last_x + block_width || i === final_sample - 1) {
        // Block wide enough or last block -> draw it

        // Draw the slightly transparent max-bar
        ctx.fillStyle = color_transp;
        ctx.fillRect(last_x, mid_point, x - last_x, -(max * scale));

        // Draw the fully visible average-bar
        ctx.fillStyle = color;
        ctx.fillRect(last_x, mid_point, x - last_x, -(avg / avg_cnt * scale));

        // Reset all the variables for accumulation
        last_x = x;
        avg = 0;
        avg_cnt = 0;
        max = 0;
      }
    }
  }
}

function padNumber(value, pad_length) {
  return ("10000" + value).slice(-1 * pad_length);
}

// Convert seconds into formatted time stamp
function secondsToTime(secs, fps_num, fps_den) {
  // calculate time of playhead
  var milliseconds = secs * 1000;
  var sec = Math.floor(milliseconds / 1000);
  var milli = milliseconds % 1000;
  var min = Math.floor(sec / 60);
  sec = sec % 60;
  var hour = Math.floor(min / 60);
  min = min % 60;
  var day = Math.floor(hour / 24);
  hour = hour % 24;
  var week = Math.floor(day / 7);
  day = day % 7;

  var frame = Math.round((milli / 1000.0) * (fps_num / fps_den)) + 1;
  return {
    "week": padNumber(week, 2),
    "day": padNumber(day, 2),
    "hour": padNumber(hour, 2),
    "min": padNumber(min, 2),
    "sec": padNumber(sec, 2),
    "milli": padNumber(milli, 2),
    "frame": padNumber(frame, 2)
  };
}

// Find the closest track number (based on a Y coordinate)
function findTrackAtLocation(scope, top) {

  // Loop through each layer (looking for the closest track based on Y coordinate)
  var track_position = 0;
  var track_number = 0;
  for (var layer_index = scope.project.layers.length - 1; layer_index >= 0; layer_index--) {
    var layer = scope.project.layers[layer_index];

    // Compare position of track to Y param (of unlocked tracks)
    if (!layer.lock) {
      if ((top < layer.y && top > track_position) || track_position === 0) {
        // return first matching layer
        track_position = layer.y;
        track_number = layer.number;
      }
    }
  }

  return track_number;
}

// Find the closest track number (based on a Y coordinate)
function hasLockedTrack(scope, top, bottom) {

  // Loop through each layer (looking for the closest track based on Y coordinate)
  for (var layer_index = scope.project.layers.length - 1; layer_index >= 0; layer_index--) {
    var layer = scope.project.layers[layer_index];

    // Compare position of track to Y param
    if (layer.lock && layer.y >= top && layer.y <= bottom) {
      // Yes, found a locked track inside these coordinates
      return true;
    }
  }

  return false;
}

var bounding_box = Object();

// Build bounding box (since multiple items can be selected)
function setBoundingBox(scope, item) {
  var scrolling_tracks = $("#scrolling_tracks");
  var vert_scroll_offset = scrolling_tracks.scrollTop();
  var horz_scroll_offset = scrolling_tracks.scrollLeft();

  var item_bottom = item.position().top + item.height() + vert_scroll_offset;
  var item_top = item.position().top + vert_scroll_offset;
  var item_left = item.position().left + horz_scroll_offset;
  var item_right = item.position().left + horz_scroll_offset + item.width();

  if (jQuery.isEmptyObject(bounding_box)) {
    bounding_box.left = item_left;
    bounding_box.top = item_top;
    bounding_box.bottom = item_bottom;
    bounding_box.right = item_right;
    bounding_box.height = item.height();
    bounding_box.width = item.width();
  } else {
    //compare and change if item is a better fit for bounding box edges
    if (item_top < bounding_box.top) { bounding_box.top = item_top; }
    if (item_left < bounding_box.left) { bounding_box.left = item_left; }
    if (item_bottom > bounding_box.bottom) { bounding_box.bottom = item_bottom; }
    if (item_right > bounding_box.right) { bounding_box.right = item_right; }

    // compare height and width of bounding box (take the largest number)
    var height = bounding_box.bottom - bounding_box.top;
    var width = bounding_box.right - bounding_box.left;
    if (height > bounding_box.height) { bounding_box.height = height; }
    if (width > bounding_box.width) { bounding_box.width = width; }
  }

  // Get list of current selected ids (so we can ignore their snapping x coordinates)
  bounding_box.selected_ids = {};
  for (var clip_index = 0; clip_index < scope.project.clips.length; clip_index++) {
    if (scope.project.clips[clip_index].selected) {
      bounding_box.selected_ids[scope.project.clips[clip_index].id] = true;
    }
  }
  for (var effect_index = 0; effect_index < scope.project.effects.length; effect_index++) {
    if (scope.project.effects[effect_index].selected) {
      bounding_box.selected_ids[scope.project.effects[effect_index].id] = true;
    }
  }
}

// Move bounding box (apply snapping and constraints)
function moveBoundingBox(scope, previous_x, previous_y, x_offset, y_offset, left, top) {
  // Store result of snapping logic (left, top)
  var snapping_result = Object();
  snapping_result.left = left;
  snapping_result.top = top;

  // Check for shift key
  if (scope.shift_pressed) {
    // freeze X movement
    x_offset = 0;
    snapping_result.left = previous_x;
  }

  // Update bounding box
  bounding_box.left += x_offset;
  bounding_box.right += x_offset;
  bounding_box.top += y_offset;
  bounding_box.bottom += y_offset;

  // Check overall timeline constraints (i.e don't let clips be dragged outside the timeline)
  if (bounding_box.left < 0) {
    // Left border
    x_offset -= bounding_box.left;
    bounding_box.left = 0;
    bounding_box.right = bounding_box.width;
    snapping_result.left = previous_x + x_offset;
  }
  if (bounding_box.top < 0) {
    // Top border
    y_offset -= bounding_box.top;
    bounding_box.top = 0;
    bounding_box.bottom = bounding_box.height;
    snapping_result.top = previous_y + y_offset;
  }
  if (bounding_box.bottom > track_container_height) {
    // Bottom border
    y_offset -= (bounding_box.bottom - track_container_height);
    bounding_box.bottom = track_container_height;
    bounding_box.top = bounding_box.bottom - bounding_box.height;
    snapping_result.top = previous_y + y_offset;
  }

  // Find closest nearby object, if any (for snapping)
  var bounding_box_padding = 3; // not sure why this is needed, but it helps line everything up
  var results = scope.getNearbyPosition([bounding_box.left, bounding_box.right + bounding_box_padding], 10.0, bounding_box.selected_ids);
  var nearby_offset = results[0];
  var snapline_position = results[1];

  if (snapline_position) {
    // Show snapping line
    scope.showSnapline(snapline_position);

    if (scope.enable_snapping) {
      // Snap bounding box to this position
      x_offset -= nearby_offset;
      bounding_box.left -= nearby_offset;
      bounding_box.right -= nearby_offset;
      snapping_result.left -= nearby_offset;
    }

  } else {
    // Hide snapline
    scope.hideSnapline();
  }

  return {"position": snapping_result, "x_offset": x_offset, "y_offset": y_offset};
}
