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

/* global App, timeline, snapToFPSGridTime pixelToTime */
App.directive("tlTrack", function () {
    return {
        restrict: "A",
        link: function (scope, element) {
            var startX, startWidth, isResizing = false, newDuration, minimumWidth;

            // Function to calculate the furthest right edge of any clip
            var getFurthestRightEdge = function() {
                return scope.project.clips.reduce((max, clip) =>
                    Math.max(max, clip.position + (clip.end - clip.start)), 0);
            };

            // Delegate the mousedown event to the parent element for dynamically created resize-handle
            element.on("mousedown", ".track-resize-handle", function(event) {
                // Start resizing logic
                isResizing = true;
                startX = event.pageX;
                startWidth = element.width();

                // Calculate the minimum width based on the furthest right edge of clips
                minimumWidth = getFurthestRightEdge() * scope.pixelsPerSecond;

                // Attach document-wide mousemove and mouseup events
                $(document).on("mousemove", resizeTrack);
                $(document).on("mouseup", stopResizing);
                event.preventDefault();
            });

            // Function to handle resizing as mouse moves
            function resizeTrack(event) {
                if (!isResizing) return;

                // Calculate the new width (ensure it doesn't go below the minimum width)
                var newWidth = Math.max(startWidth + (event.pageX - startX), minimumWidth);

                // Update the track's new duration based on the resized width
                newDuration = snapToFPSGridTime(scope, pixelToTime(scope, newWidth));

                // Update the element's width dynamically
                element.width(newWidth);

                // Apply the new duration to the scope
                scope.$apply(function () {
                    scope.project.duration = newDuration;
                });
            }

            // Function to stop resizing when the mouse button is released
            function stopResizing() {
                if (!isResizing) {return;}
                isResizing = false;

                // Clean up the document-wide event listeners
                $(document).off("mousemove", resizeTrack);
                $(document).off("mouseup", stopResizing);

                // Finalize the new duration on the timeline (if valid)
                if (newDuration !== null) {
                    timeline.resizeTimeline(newDuration);
                }
            }
        }
    };
});
