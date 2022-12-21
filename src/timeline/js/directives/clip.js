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


/*global setSelections, setBoundingBox, moveBoundingBox, bounding_box, drawAudio */
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

      //handle resizability of clip
      element.resizable({
        handles: "e, w",
        minWidth: 1,
        maxWidth: scope.clip.length * scope.pixelsPerSecond,
        start: function (e, ui) {
          dragging = true;

          // Set selections
          setSelections(scope, element, $(this).attr("id"));

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

          // Hide keyframe points
          element.find(".point").fadeOut(100);
          element.find(".audio-container").fadeOut(100);

        },
        stop: function (e, ui) {
          dragging = false;

          // Show keyframe points
          element.find(".point").fadeIn(100);
          element.find(".audio-container").fadeIn(100);

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

          if (dragLoc === "left") {
            // changing the start of the clip
            new_left -= delta_time;
            if (new_left < 0) {
              // prevent less than zero
              new_left = 0.0;
              new_position -= scope.clip.start;
            } else if (new_left >= new_right) {
              // prevent resizing past right edge
              new_left = new_right;
            } else {
              new_position -= delta_time;
            }
          }
          else {
            // changing the end of the clips
            new_right -= delta_time;
            if (new_right > scope.clip.duration) {
              // prevent greater than duration
              new_right = scope.clip.duration;
            } else if (new_right < new_left) {
              // Prevent resizing past left edge
              new_right = new_left;
            }
          }

          // Hide snapline (if any)
          scope.hideSnapline();

          //apply the new start, end and length to the clip's scope
          scope.$apply(function () {
            // Apply clip scope changes
            if (scope.clip.end !== new_right) {
              scope.clip.end = new_right;
            }
            if (scope.clip.start !== new_left) {
              scope.clip.start = new_left;
              scope.clip.position = new_position;
            }
            // Resize timeline if it's too small to contain all clips
            scope.resizeTimeline();
          });

          // update clip in Qt (very important =)
          if (scope.Qt) {
            timeline.update_clip_data(JSON.stringify(scope.clip), true, true, false, null);
          }

          //resize the audio canvas to match the new clip width
          if (scope.clip.ui && scope.clip.ui.audio_data) {
            //redraw audio as the resize cleared the canvas
            drawAudio(scope, scope.clip.id);
          }
          dragLoc = null;
        },
        resize: function (e, ui) {
          element.find(".point").fadeOut(100);
          element.find(".audio-container").fadeOut(100);

          // Calculate the pixel locations of the left and right side
          let original_left_edge = scope.clip.position * scope.pixelsPerSecond;
          let original_width = (scope.clip.end - scope.clip.start) * scope.pixelsPerSecond;
          let original_right_edge = original_left_edge + original_width;

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

          if (dragLoc === "left") {
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
          else {
            // Adjust right side of clip
            new_right -= delta_x;
            let duration_pixels = scope.clip.duration * scope.pixelsPerSecond;
            if (new_right > duration_pixels) {
              // change back to actual duration (for the preview below)
              new_right = duration_pixels;
            }
            ui.element.width(new_right - new_left);
          }

          // Preview frame during resize
          if (dragLoc === "left") {
            // Preview the left side of the clip
            scope.previewClipFrame(scope.clip.id, new_left / scope.pixelsPerSecond);
          }
          else {
            // Preview the right side of the clip
            scope.previewClipFrame(scope.clip.id, new_right / scope.pixelsPerSecond);
          }
        }
      });

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
        snap: ".track", // snaps to a track
        snapMode: "inner",
        snapTolerance: 20,
        scroll: true,
        cancel: ".effect-container,.clip_menu,.point",
        start: function (event, ui) {
          previous_drag_position = null;
          dragging = true;

          // Set selections
          setSelections(scope, element, $(this).attr("id"));

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

          // Clear previous drag position
          previous_drag_position = null;
          dragging = false;
        },
        drag: function (e, ui) {
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
          var results = moveBoundingBox(scope, previous_x, previous_y, x_offset, y_offset, ui.position.left, ui.position.top);
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
        },
        revert: function (valid) {
          if (!valid) {
            //the drop spot was invalid, so we're going to move all clips to their original position
            $(".ui-selected").each(function () {
              var oldY = start_clips[$(this).attr("id")]["top"];
              var oldX = start_clips[$(this).attr("id")]["left"];

              $(this).css("left", oldX);
              $(this).css("top", oldY);
            });
          }
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
        cancel: ".effect-container,.transition_menu,.clip_menu,.point",
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
          // This is called one time after all the selecting/unselecting is done
          // Large amounts of selected item data could have changed, so
          // let's force the UI to update
          scope.$apply();
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
