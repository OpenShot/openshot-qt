/**
 * @file
 * @brief Ruler directives (dragging playhead functionality, progress bars, tick marks, etc...)
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


/*global setSelections, setBoundingBox, moveBoundingBox, bounding_box */
// Variables for panning by middle click
var is_scrolling = false;
var starting_scrollbar = {x: 0, y: 0};
var starting_mouse_position = {x: 0, y: 0};

// Variables for scrolling control
var scroll_left_pixels = 0;


// This container allows for tracks to be scrolled (with synced ruler)
// and allows for panning of the timeline with the middle mouse button
/*global App, secondsToTime*/
App.directive("tlScrollableTracks", function () {
  return {
    restrict: "A",
    link: function (scope, element, attrs) {

      // Sync ruler to track scrolling
      element.on("scroll", function () {
        //set amount scrolled
        scroll_left_pixels = element.scrollLeft();

        $("#track_controls").scrollTop(element.scrollTop());
        $("#scrolling_ruler").scrollLeft(element.scrollLeft());
        $("#progress_container").scrollLeft(element.scrollLeft());

        scope.$apply( () => {
          scope.scrollLeft = element[0].scrollLeft;
        })

        // Send scrollbar position to Qt
        if (scope.Qt) {
           // Calculate scrollbar positions (left and right edge of scrollbar)
           var timeline_length = scope.getTimelineWidth(0);
           var left_scrollbar_edge = scroll_left_pixels / timeline_length;
           var right_scrollbar_edge = (scroll_left_pixels + element.width()) / timeline_length;

           // Send normalized scrollbar positions to Qt
           timeline.ScrollbarChanged([left_scrollbar_edge, right_scrollbar_edge, timeline_length, element.width()]);
        }

        scope.$apply( () => {
          scope.scrollLeft = element[0].scrollLeft;
        })

      });

      // Pans the timeline (on middle mouse clip and drag)
      element.on("mousemove", function (e) {
        if (is_scrolling) {
          // Calculate difference from last position
          var difference = {x: starting_mouse_position.x - e.pageX, y: starting_mouse_position.y - e.pageY};
          var newPos = { x: starting_scrollbar.x + difference.x, y: starting_scrollbar.y + difference.y};

          // Scroll the tracks div
          element.scrollLeft(newPos.x);
          element.scrollTop(newPos.y);
        }
      });

      // Remove move cursor (i.e. dragging has stopped)
      element.on("mouseup", function (e) {
        element.removeClass("drag_cursor");
      });

    }
  };
});

// Track scrolling mode on body tag... allows for capture of released middle mouse button
App.directive("tlBody", function () {
  return {
    link: function (scope, element, attrs) {

      element.on("mouseup", function (e) {
        if (e.which === 2) { // middle button
          is_scrolling = false;
          element.removeClass("drag_cursor");
        }
      });

      // Stop scrolling if mouse leaves timeline
      element.on("mouseleave", function (e) {
        is_scrolling = false;
        element.removeClass("drag_cursor");
      })

      // Initialize panning when middle mouse is clicked
      element.on("mousedown", function (e) {
        if (e.which === 2) { // middle button
          e.preventDefault();
          is_scrolling = true;
          starting_scrollbar = {x: $("#scrolling_tracks").scrollLeft(), y: $("#scrolling_tracks").scrollTop()};
          starting_mouse_position = {x: e.pageX, y: e.pageY};
          element.addClass("drag_cursor");
        }
      });

    }
  };
});


// The HTML5 canvas ruler
App.directive("tlRuler", function ($timeout) {
  return {
    restrict: "A",
    link: function (scope, element, attrs) {
      //on click of the ruler canvas, jump playhead to the clicked spot
      element.on("mousedown", function (e) {
        // Get playhead position
        var playhead_left = e.pageX - element.offset().left;
        var playhead_seconds = playhead_left / scope.pixelsPerSecond;

        // Immediately preview frame (don't wait for animated playhead)
        scope.previewFrame(playhead_seconds);

        // Animate to new position (and then update scope)
        scope.playhead_animating = true;
        $(".playhead-line").animate({left: playhead_left}, 200);
        $(".playhead-top").animate({left: playhead_left}, 200, function () {
          // Update playhead
          scope.movePlayhead(playhead_seconds);

          // Animation complete.
          scope.$apply(function () {
            scope.playhead_animating = false;
          });
        });
      });

      element.on("mousedown", function (e) {
        // Set bounding box for the playhead position
        setBoundingBox(scope, $(this), "playhead");
      });

      // Move playhead to new position (if it's not currently being animated)
      element.on("mousemove", function (e) {
        if (e.which === 1 && !scope.playhead_animating) { // left button
          // Calculate the playhead bounding box movement
          let cursor_position = e.pageX - $("#ruler").offset().left;
          let new_position = cursor_position;
          if (e.shiftKey) {
            // Only apply playhead shapping when SHIFT is pressed
            let results = moveBoundingBox(scope, bounding_box.left, bounding_box.top,
              cursor_position - bounding_box.left, cursor_position - bounding_box.top,
              cursor_position, cursor_position, "playhead");

            // Update position to snapping position
            new_position = results.position.left;
          }

          // Move playhead
          let playhead_seconds = new_position / scope.pixelsPerSecond;
          scope.movePlayhead(playhead_seconds);
          scope.previewFrame(playhead_seconds);
        }
      });

      // Frames per tick. Stored to prevent calculating if possible
      let fpt;
      let fps;

      /**
       * Draw times on the ruler
       * Always starts on a second
       * Draws to the right edge of the screen
       */
      function drawTimes() {
        // Delete old tick marks
        let ruler = $("#ruler");
        $("#ruler span").remove();

        let startPos = scope.scrollLeft;
        let endPos = scope.scrollLeft + $("body").width();
        fpt = framesPerTick(scope.pixelsPerSecond, scope.project.fps.num ,scope.project.fps.den);
        fps = scope.project.fps.num / scope.project.fps.den;
        let time = [ startPos / scope.pixelsPerSecond, endPos / scope.pixelsPerSecond];

        if (fpt > fps) {
          // Make sure seconds don't change when scrolling right and left
          // console.log("F/F:" + fpt / Math.round(fps));
          time[0] -= time[0]%(fpt/Math.round(fps));
        }
        else {
          time[0] -= time[0]%2;
        }
        time[1] -= time[1]%1 - 1;

        let startFrame = time[0] * Math.round(fps);
        let endFrame = time[1] * Math.round(fps);

        let frame = startFrame;
        while ( frame <= endFrame){
          let t = frame / fps;
          let pos = t * scope.pixelsPerSecond;
          let tickSpan = $('<span style="left:' + pos + 'px;"></span>');
          tickSpan.addClass("tick_mark");

          let timeSpan = $('<span style="left:' + pos + 'px;"></span>');
          if ((frame) % (fpt * 2) === 0) {
            // Alternating long marks with times marked
            timeSpan.addClass("ruler_time");
            let timeText = secondsToTime(t, scope.project.fps.num, scope.project.fps.den);
            timeSpan[0].innerText = timeText['hour'] + ':' +
              timeText['min'] + ':' +
              timeText['sec'];
            if (fpt < Math.round(fps)) {
              timeSpan[0].innerText += ',' + timeText['frame'];
            }
            tickSpan[0].style['height'] = '20px';
          }
          ruler.append(timeSpan);
          ruler.append(tickSpan);

          frame += fpt;
        }
        return;
      };

      scope.$watch("project.scale + project.duration + scrollLeft", function (val) {
        if (val) {
          $timeout(function () {
            drawTimes();
            return;
          } , 0);
        }
      });

    }

  };
});
