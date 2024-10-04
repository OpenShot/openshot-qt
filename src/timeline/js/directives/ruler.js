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


/*global App, timeline, secondsToTime, setSelections, setBoundingBox, moveBoundingBox, bounding_box */
// Variables for panning by middle click
var is_scrolling = false;
var starting_scrollbar = {x: 0, y: 0};
var starting_mouse_position = {x: 0, y: 0};

// Variables for scrolling control
var scroll_left_pixels = 0;


// This container allows for tracks to be scrolled (with synced ruler)
// and allows for panning of the timeline with the middle mouse button
App.directive("tlScrollableTracks", function () {
  return {
    restrict: "A",
    link: function (scope, element, attrs) {

      /**
       * if ctrl is held, scroll in or out.
       * Implimentation copied from zoomSlider zoomIn zoomOut
       */
      element.on("wheel",function (e) {
        if (e.ctrlKey) {
          e.preventDefault(); // Don't scroll like a browser
          var delta = e.originalEvent.deltaY * (e.shiftKey ? -1 : 1);
          if (delta > 0) { // Scroll down: Zoom out
            /*global timeline*/
            timeline.zoomOut();
          } else { // Scroll Up: Zoom in
            /*global timeline*/
            timeline.zoomIn();
          }
        }
        else if (e.shiftKey) {
          e.preventDefault();
          let current_scroll = $("#scrolling_tracks").scrollLeft();
          $("#scrolling_tracks").scrollLeft(current_scroll + e.originalEvent.deltaY);
        }
      });

      // Sync ruler to track scrolling
      element.on("scroll", function () {
        var scrollLeft = element.scrollLeft();
        var timelineWidth = scope.getTimelineWidth(0); // Full width of the timeline
        var maxScrollLeft = timelineWidth - element.width(); // Max horizontal scroll

        // Clamp to right edge
        element.scrollLeft(Math.min(scrollLeft, maxScrollLeft));

        // Sync the ruler and other components
        $("#track_controls").scrollTop(element.scrollTop());
        $("#scrolling_ruler, #progress_container").scrollLeft(scrollLeft);

        // Send scrollbar position to Qt if available
        if (scope.Qt) {
          // Create variables first and pass them as arguments
          var leftScrollbarEdge = scrollLeft / timelineWidth; // Use the full timeline width
          var rightScrollbarEdge = (scrollLeft + element.width()) / timelineWidth; // Use the full timeline width

          // Pass the variables as a JavaScript array (interpreted as a PyQt list)
          timeline.ScrollbarChanged([leftScrollbarEdge, rightScrollbarEdge, timelineWidth, element.width()]);
        }

        // Update scrollLeft in scope
        scope.$apply(() => scope.scrollLeft = scrollLeft);
      });

      // Pans the timeline (on middle mouse click and drag)
      element.on("mousemove", function (e) {
        if (is_scrolling) {
          var difference = {x: starting_mouse_position.x - e.pageX, y: starting_mouse_position.y - e.pageY};
          var newPos = {
            x: Math.max(0, Math.min(starting_scrollbar.x + difference.x, scope.getTimelineWidth(0) - element.width())),
            y: Math.max(0, Math.min(starting_scrollbar.y + difference.y, $("#scrolling_tracks")[0].scrollHeight - element.height()))
          };

          // Scroll the tracks div
          element.scrollLeft(newPos.x).scrollTop(newPos.y);
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
      var isDragging = false;

      // Start dragging when mousedown on the ruler
      element.on("mousedown", function (e) {
        // Set bounding box for the playhead position
        setBoundingBox(scope, $("#playhead"), "playhead");
        isDragging = true;

        if (scope.Qt) {
            // Disable caching thread during scrubbing
            timeline.DisableCacheThread();
        }

        // Get playhead position
        var playhead_left = e.pageX - element.offset().left;
        var playhead_seconds = snapToFPSGridTime(scope, pixelToTime(scope, playhead_left));
        playhead_seconds = Math.min(Math.max(0.0, playhead_seconds), scope.project.duration);
        var playhead_snapped_target = playhead_seconds * scope.pixelsPerSecond;

        // Immediately preview frame (don't wait for animated playhead)
        scope.previewFrame(playhead_seconds);

        if (playhead_seconds == scope.project.playhead_position) {
          // No animation (playhead didn't move)
          return;
        }

        // Animate to new position (and then update scope)
        scope.playhead_animating = true;
        $(".playhead-line").animate({left: playhead_snapped_target}, 150);
        $(".playhead-top").animate({left: playhead_snapped_target}, 150, function () {
          // Update playhead
          scope.movePlayhead(playhead_seconds);

          // Animation complete.
          scope.$apply(function () {
            scope.playhead_animating = false;
          });
        });
      });

      // Global mousemove listener
      $(document).on("mousemove", function (e) {
        if (isDragging && e.which === 1 && !scope.playhead_animating && !scope.getDragging()) { // left button is held
          // Calculate the playhead bounding box movement
          let cursor_position = e.pageX - $("#ruler").offset().left;
          let new_position = cursor_position;
          if (e.shiftKey) {
            // Only apply playhead snapping when SHIFT is pressed
            let results = moveBoundingBox(scope, bounding_box.left, bounding_box.top,
              cursor_position - bounding_box.left, cursor_position - bounding_box.top,
              cursor_position, cursor_position, "playhead");

            // Update position to snapping position
            new_position = results.position.left;
          }

          // Move playhead
          let playhead_seconds = new_position / scope.pixelsPerSecond;
          playhead_seconds = Math.min(Math.max(0.0, playhead_seconds), scope.project.duration);
          scope.movePlayhead(playhead_seconds);
          scope.previewFrame(playhead_seconds);
        }
      });

      // Global mouseup listener to stop dragging
      $(document).on("mouseup", function (e) {
        if (isDragging) {
          isDragging = false;

          if (scope.Qt) {
            // Enable caching thread after scrubbing
            timeline.EnableCacheThread();
          }
        }
      });

      /**
       * Draw frame precision alternating banding on each track (when zoomed in)
       */
      function updateTrackBackground() {
          const fps = scope.project.fps.num / scope.project.fps.den;
          const pixelsPerFrame = scope.pixelsPerSecond / fps;
          const fpt = framesPerTick(scope.pixelsPerSecond, scope.project.fps.num, scope.project.fps.den);

          // Calculate the time start and end positions
          let timeStart = scope.scrollLeft / scope.pixelsPerSecond;
          let timeEnd = (scope.scrollLeft + $("body").width()) / scope.pixelsPerSecond;

          // Align the start time based on frames per tick
          timeStart -= fpt > fps ? (timeStart % (fpt / Math.round(fps))) : (timeStart % 2);
          timeEnd -= timeEnd % 1 - 1;

          const startFrame = timeStart * Math.round(fps);
          const endFrame = timeEnd * Math.round(fps);

          if (fpt <= 2.0) {
              $('.track').each(function() {
                  const $bandingContainer = $(this).find('.banding-overlay').empty();
                  const trackHeight = $(this).innerHeight();
                  let frame = startFrame;
                  let isDarkBand = true;

                  while (frame <= endFrame) {
                      const pos = (frame / fps) * scope.pixelsPerSecond;

                      if (fpt === 1.0) {
                          // When fpt == 1, alternate entire ticks as dark or transparent
                          if (isDarkBand) {
                              $bandingContainer.append($('<div></div>').css({
                                  'position': 'absolute',
                                  'left': `${pos}px`,
                                  'width': `${pixelsPerFrame}px`,  // Full frame width for one frame
                                  'height': '100%',
                                  'background-color': 'rgba(0, 0, 0, 0.1)'
                              }));
                          }
                          isDarkBand = !isDarkBand;  // Alternate bands
                      } else if (fpt === 2.0) {
                          // When fpt == 2, create two alternating dark bands per tick
                          const bandWidth = pixelsPerFrame * fpt;
                          $bandingContainer.append($('<div></div>').css({
                              'position': 'absolute',
                              'left': `${pos}px`,
                              'width': `${bandWidth / 2}px`,  // Dark band width is half of the tick
                              'height': '100%',
                              'background-color': 'rgba(0, 0, 0, 0.1)'
                          }));
                      }
                      frame += fpt;  // Move to the next frame
                  }

                  // Set container CSS for banding overlay
                  $bandingContainer.css({
                      'position': 'absolute',
                      'top': '0',
                      'left': '0',
                      'height': `${trackHeight}px`,
                      'width': '100%',
                      'z-index': '1',
                      'pointer-events': 'none'
                  });
              });
          } else {
              // Clear bands when not zoomed in enough
              $('.track').find('.banding-overlay').empty();
          }
      }

      /**
       * Draw times on the ruler
       * Always starts on a second
       * Draws to the right edge of the screen
       */
      function drawTimes() {
        // Delete old tick marks
        ruler = $('#ruler');
        $("#ruler span").remove();

        let startPos = scope.scrollLeft;
        let endPos = scope.scrollLeft + $("body").width();
        let fpt = framesPerTick(scope.pixelsPerSecond, scope.project.fps.num ,scope.project.fps.den);
        let fps = scope.project.fps.num / scope.project.fps.den;
        let time = [ startPos / scope.pixelsPerSecond, endPos / scope.pixelsPerSecond];

        if (fpt > fps) {
          // Make sure seconds don't change when scrolling right and left
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
          let tickSpan = $('<span style="left:'+pos+'px;"></span>');
          tickSpan.addClass("tick_mark");

          if ((frame) % (fpt * 2) === 0) {
            // Alternating long marks with times marked
            let timeSpan = $('<span style="left:'+pos+'px;"></span>');
            timeSpan.addClass("ruler_time");
            let timeText = secondsToTime(t, scope.project.fps.num, scope.project.fps.den);
            timeSpan[0].innerText = timeText['hour'] + ':' +
              timeText['min'] + ':' +
              timeText['sec'];
            if (fpt < Math.round(fps)) {
              timeSpan[0].innerText += ',' + timeText['frame'];
            }
            tickSpan[0].style['height'] = '20px';
            ruler.append(timeSpan);
          }
          ruler.append(tickSpan);
          frame += fpt;
        }

        // Add alternating banding to indicate frame boundaries (when zoomed in)
        updateTrackBackground();
      }

      scope.$watch("project.scale + project.duration + scrollLeft + element.width()", function (val) {
        $timeout(function () {
          drawTimes();
          return;
        } , 0);
      });

    }

  };
});
