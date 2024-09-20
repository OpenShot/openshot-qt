/**
 * @file
 * @brief Track directives (resizable functionality)
 * @author Jonathan Thomas <jonathan@openshot.org>
 *
 * @section LICENSE
 *
 * Copyright (c) 2008-2024 OpenShot Studios, LLC
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


App.directive('tlTrack', function () {
    return {
        restrict: 'A',
        link: function (scope, element, attrs) {
            var newDuration = null;  // Define the variable in a higher scope
            var minimumWidth = 0;    // Define the minimum width based on furthest right edge

            // Function to calculate the furthest right edge of any clip
            var getFurthestRightEdge = function() {
                var furthest_right_edge = 0;

                for (var clip_index = 0; clip_index < scope.project.clips.length; clip_index++) {
                    var clip = scope.project.clips[clip_index];
                    var right_edge = clip.position + (clip.end - clip.start);
                    if (right_edge > furthest_right_edge) {
                        furthest_right_edge = right_edge;
                    }
                }

                return furthest_right_edge;
            };

            // Make the track resizable using jQuery UI, but restrict resizing to the right side
            element.resizable({
                handles: 'e', // right edge
                minWidth: 0,  // Set minimum width (optional)
                distance: 5,  // threshold for resizing to avoid small movements

                // Event triggered when resizing starts
                start: function (event, ui) {
                    // Calculate the furthest right edge once, at the start of resizing
                    var furthestRightEdge = getFurthestRightEdge();
                    minimumWidth = furthestRightEdge * scope.pixelsPerSecond;
                },

                // Event triggered while resizing
                resize: function (event, ui) {
                    // Get the new width of the track in pixels
                    var newWidth = Math.max(ui.size.width, minimumWidth);

                    // Update the track duration based on the new constrained width and pixels per second
                    newDuration = snapToFPSGridTime(scope, pixelToTime(scope, newWidth));

                    // Apply the new duration to the scope
                    scope.$apply(function () {
                        scope.project.duration = newDuration;
                    });
                },

                // Event triggered when resizing ends (mouse released)
                stop: function (event, ui) {
                    // Use the newDuration variable defined in the resize event
                    if (newDuration !== null) {
                        timeline.resizeTimeline(newDuration);
                    }
                }
            });
        }
    };
});
