/**
 * @file
 * @brief Playhead directives (dragging functionality, etc...)
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


// Handles the playhead dragging
var playhead_y_max = null;

/*global App*/
App.directive("tlPlayhead", function () {
  return {
    link: function (scope, element, attrs) {
      // get the default top position so we can lock it in place vertically
      playhead_y_max = element.position().top;

      element.on("mousedown", function (e) {
        // Set bounding box for the playhead
        setBoundingBox(scope, $(this), "playhead");
      });

      // Move playhead to new position (if it's not currently being animated)
      element.on("mousemove", function (e) {
        if (e.which === 1 && !scope.playhead_animating) { // left button
          // Calculate the playhead bounding box movement and apply snapping rules
          let cursor_position = e.pageX - $("#ruler").offset().left;
          let results = moveBoundingBox(scope, bounding_box.left, bounding_box.top,
            cursor_position - bounding_box.left, cursor_position - bounding_box.top,
            cursor_position, cursor_position, "playhead");

          // Only apply snapping when SHIFT is pressed
          let new_position = cursor_position;
          if (e.shiftKey) {
            new_position = results.position.left;
          }

          // Move playhead
          let playhead_seconds = new_position / scope.pixelsPerSecond;
          scope.movePlayhead(playhead_seconds);
          scope.previewFrame(playhead_seconds);
        }
      });

    }
  };
});
