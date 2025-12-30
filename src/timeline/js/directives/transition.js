/**
 * @file
 * @brief Transition directives (draggable & resizable functionality)
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


/*global setSelections, setBoundingBox, moveBoundingBox, bounding_box, updateDraggables, snapToFPSGridTime */
// Init Variables
var resize_disabled = false;
var previous_drag_position = null;
var start_transitions = {};
var move_transitions = {};
var track_container_height = -1;

// Treats element as a transition
// 1: can be dragged
// 2: can be resized
// 3: class change when hovered over
var dragLoc = null;

/*global App, timeline, hasLockedTrack, moveBoundingBox */
App.directive("tlTransition", function () {
  return {
    scope: "@",
    link: function (scope, element, attrs) {

      var transitionKeyframePreview = {
        active: false,
        originalWidth: 0
      };

      function ensureTransitionPreviewContainer() {
        if (!scope.transition) {
          return null;
        }
        if (!scope.transition.ui) {
          scope.transition.ui = {};
        }
        var container = scope.transition.ui.keyframe_preview;
        if (!container || typeof container !== "object") {
          container = {};
          scope.transition.ui.keyframe_preview = container;
        }
        return container;
      }

      function setTransitionPreviewActive(active) {
        scope.$evalAsync(function () {
          var container = ensureTransitionPreviewContainer();
          if (!container) {
            return;
          }
          container.active = active;
          container.displayStart = scope.transition.start;
          container.displayEnd = scope.transition.end;
          container.pixelsPerSecond = scope.pixelsPerSecond;
        });
      }

      function startTransitionKeyframePreview() {
        var points = element.find(".point");
        if (!points.length) {
          transitionKeyframePreview.active = false;
          transitionKeyframePreview.originalWidth = 0;
          return;
        }

        var width = element.width();
        if (!width || width <= 0) {
          transitionKeyframePreview.active = false;
          transitionKeyframePreview.originalWidth = 0;
          return;
        }

        transitionKeyframePreview.originalWidth = width;
        transitionKeyframePreview.active = true;

        setTransitionPreviewActive(true);

        points.each(function () {
          if (!this.hasAttribute("data-original-left")) {
            var leftValue = this.style.left;
            var numericLeft = parseFloat(leftValue);
            if (!isNaN(numericLeft)) {
              this.setAttribute("data-original-left", numericLeft);
            } else {
              this.setAttribute("data-original-left", 0);
            }
          }
        });
      }

      function updateTransitionKeyframePreview(widthPx) {
        if (!transitionKeyframePreview.active) {
          return;
        }

        var width = widthPx;
        if (typeof width !== "number" || !isFinite(width)) {
          width = element.width();
        }

        if (!width || width < 0) {
          width = 0;
        }

        var originalWidth = transitionKeyframePreview.originalWidth;
        if (!originalWidth || originalWidth <= 0) {
          return;
        }

        var scale = width / originalWidth;

        element.find(".point").each(function () {
          var originalLeft = parseFloat(this.getAttribute("data-original-left"));
          if (isNaN(originalLeft)) {
            originalLeft = parseFloat(this.style.left) || 0;
            this.setAttribute("data-original-left", originalLeft);
          }
          var scaledLeft = originalLeft * scale;
          if (!isFinite(scaledLeft)) {
            scaledLeft = 0;
          }
          if (scaledLeft < 0) {
            scaledLeft = 0;
          }
          if (scaledLeft > width) {
            scaledLeft = width;
          }
          this.style.left = scaledLeft + "px";
        });
      }

      function stopTransitionKeyframePreview() {
        setTransitionPreviewActive(false);

        if (!transitionKeyframePreview.active) {
          return;
        }

        element.find(".point").each(function () {
          if (this.hasAttribute("data-original-left")) {
            this.removeAttribute("data-original-left");
          }
        });

        transitionKeyframePreview.active = false;
        transitionKeyframePreview.originalWidth = 0;
      }

      //handle resizability of transition
      element.resizable({
        handles: "e, w",
        minWidth: 1,
        start: function (e, ui) {
          // Set selections
          setSelections(scope, element, $(this).attr("id"));

          // Set dragging mode
          scope.setDragging(true);
          resize_disabled = false;

          // Set bounding box
          setBoundingBox(scope, $(this), "trimming");

          //determine which side is being changed
          var parentOffset = element.offset();
          var mouseLoc = e.pageX - parentOffset.left;
          if (mouseLoc < 5) {
            dragLoc = "left";
          } else {
            dragLoc = "right";
          }

          // Does this bounding box overlap a locked track?
          var vert_scroll_offset = $("#scrolling_tracks").scrollTop();
          var track_top = (parseInt(element.position().top, 10) + parseInt(vert_scroll_offset, 10));
          var track_bottom = (parseInt(element.position().top, 10) + parseInt(element.height(), 10) + parseInt(vert_scroll_offset, 10));
          if (hasLockedTrack(scope, track_top, track_bottom)) {
            resize_disabled = true;
          }

          startTransitionKeyframePreview();

        },
        stop: function (e, ui) {
          scope.setDragging(false);

          stopTransitionKeyframePreview();

          // Calculate the pixel locations of the left and right side
          let original_left_edge = scope.transition.position * scope.pixelsPerSecond;
          let original_width = (scope.transition.end - scope.transition.start) * scope.pixelsPerSecond;
          let original_right_edge = original_left_edge + original_width;

          if (resize_disabled) {
            // disabled, do nothing
            resize_disabled = false;
            return;
          }

          // Calculate the bounding box movement and apply snapping rules
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

          //change the end/start based on which side was dragged
          var new_position = scope.transition.position;
          var new_right = scope.transition.end;

          if (dragLoc === "left") {
            // changing the start
            new_position -= delta_time;
            new_right += delta_time;
          } else {
            new_right -= delta_time;
          }

          // Hide snapline (if any)
          scope.hideSnapline();

          //apply the new start, end and length to the transition's scope
          var snappedPosition = typeof snapToFPSGridTime === "function" ? snapToFPSGridTime(scope, new_position) : new_position;
          var snappedEnd = typeof snapToFPSGridTime === "function" ? snapToFPSGridTime(scope, new_right) : new_right;

          scope.$apply(function () {
            if (dragLoc === "right") {
              scope.transition.end = snappedEnd;
            }
            if (dragLoc === "left") {
              scope.transition.position = snappedPosition;
              scope.transition.start = 0.0;
              scope.transition.end = snappedEnd;
            }
          });

          // update transition in Qt (very important =)
          if (scope.Qt) {
            timeline.update_transition_data(JSON.stringify(scope.transition), true, false, null);
          }

          dragLoc = null;

        },
        resize: function (e, ui) {
          // Calculate the pixel locations of the left and right side
          let original_left_edge = scope.transition.position * scope.pixelsPerSecond;
          let original_width = (scope.transition.end - scope.transition.start) * scope.pixelsPerSecond;
          let original_right_edge = original_left_edge + original_width;

          if (resize_disabled) {
            // disabled, keep the item the same size
            $(this).css({"left": original_left_edge + "px", "width": original_width + "px"});
            return;
          }

          // Calculate the transition bounding box movement and apply snapping rules
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
          var new_left = parseFloat(scope.transition.start * scope.pixelsPerSecond);
          var new_right = parseFloat(scope.transition.end * scope.pixelsPerSecond);

          if (dragLoc === "left") {
            // Adjust left side of transition
            ui.element.css("left", ui.originalPosition.left - delta_x);
            ui.element.width(new_right - (new_left - delta_x));
          }
          else {
            // Adjust right side of transition
            new_right -= delta_x;
            ui.element.width((new_right - new_left));
          }

          updateTransitionKeyframePreview(ui.element.width());

        }

      });

      //handle hover over on the transition
      element.hover(
        function () {
          if (!scope.getDragging()) {
            element.addClass("highlight_transition", 200, "easeInOutCubic");
          }
        },
        function () {
          if (!scope.getDragging()) {
            element.removeClass("highlight_transition", 200, "easeInOutCubic");
          }
        }
      );


      //handle draggability of transition
      element.draggable({
        snap: false,
        scroll: true,
        distance: 5,
        cancel: ".transition_menu, .point",
        start: function (event, ui) {
          // Set selections
          setSelections(scope, element, $(this).attr("id"));

          // Set dragging mode
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

          // Init all other selected transitions (prepare to drag them)
          // This creates a bounding box which contains all selections
          $(".ui-selected, #" + $(this).attr("id")).each(function () {
            start_transitions[$(this).attr("id")] = {
              "top": $(this).position().top + vert_scroll_offset,
              "left": $(this).position().left + horz_scroll_offset
            };
            move_transitions[$(this).attr("id")] = {
              "top": $(this).position().top + vert_scroll_offset,
              "left": $(this).position().left + horz_scroll_offset
            };
            //send transition to bounding box builder
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
          updateDraggables(scope, ui, "transition");

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

          // Calculate amount to move transitions
          var x_offset = ui.position.left - previous_x;
          var y_offset = ui.position.top - previous_y;

          // Move the bounding box and apply snapping rules
          var results = moveBoundingBox(scope, previous_x, previous_y, x_offset, y_offset, ui.position.left, ui.position.top, "clip", initialOffset);
          x_offset = results.x_offset;
          y_offset = results.y_offset;

          // Update ui object
          ui.position.left = results.position.left;
          ui.position.top = results.position.top;

          // Move all other selected transitions with this one
          $(".ui-selected").each(function () {
            if (move_transitions[$(this).attr("id")]) {
              let newY = move_transitions[$(this).attr("id")]["top"] + y_offset;
              let newX = move_transitions[$(this).attr("id")]["left"] + x_offset;
              // Update the transition location in the array
              move_transitions[$(this).attr("id")]["top"] = newY;
              move_transitions[$(this).attr("id")]["left"] = newX;
              // Change the element location
              $(this).css("left", newX);
              $(this).css("top", newY);
            }
          });

        }
      });

      scope.$on("$destroy", function () {
        stopTransitionKeyframePreview();
      });


    }
  };
});
