/**
 * @file
 * @brief Track directives (droppable functionality, etc...)
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


// Treats element as a track
// 1: allows clips, transitions, and effects to be dropped
/*global App, timeline, findTrackAtLocation*/
App.directive("tlTrack", function ($timeout) {
  return {
    // A = attribute, E = Element, C = Class and M = HTML Comment
    restrict: "A",
    link: function (scope, element, attrs) {

      scope.$watch("project.layers.length", function (val) {
        if (val) {
          $timeout(function () {
            // Update track indexes if tracks change
            scope.updateLayerIndex();
            scope.playhead_height = $("#track-container").height();
            $(".playhead-line").height(scope.playhead_height);
          }, 0);

        }
      });

      //make it accept drops
      element.droppable({
        accept: ".droppable",
        drop: function (event, ui) {

          // Disabling sorting (until all the updates are completed)
          scope.enable_sorting = false;

          var scrolling_tracks = $("#scrolling_tracks");
          var vert_scroll_offset = scrolling_tracks.scrollTop();
          var horz_scroll_offset = scrolling_tracks.scrollLeft();

          // Get scrollbar offsets
          var scrolling_tracks_offset_top = scrolling_tracks.offset().top;

          // Keep track of each dropped clip (to check for missing transitions below, after they have been dropped)
          var dropped_clips = [];
          var position_diff = 0; // the time diff to apply to multiple selections (if any)
          var ui_selected = $(".ui-selected");
          var selected_item_count = ui_selected.length;

          // Get uuid to group all these updates as a single transaction
          var tid = timeline.get_uuid()

          // with each dragged clip, find out which track they landed on
          // Loop through each selected item, and remove the selection if multiple items are selected
          // If only 1 item is selected, leave it selected
          ui_selected.each(function (index) {
            var item = $(this);

            // Remove all selections
            if (ui_selected.length > 1) {
              for (var clip_index = 0; clip_index < scope.project.clips.length; clip_index++) {
                scope.project.clips[clip_index].selected = false;
                if (scope.Qt) {
                  timeline.removeSelection(scope.project.clips[clip_index].id.replace("clip_", ""), "clip");
                }
              }
              for (var tran_index = 0; tran_index < scope.project.effects.length; tran_index++) {
                scope.project.effects[tran_index].selected = false;
                if (scope.Qt) {
                  timeline.removeSelection(scope.project.effects[tran_index].id.replace("transition_", ""), "transition");
                }
              }
            }

            // Determine type of item
            var item_type = null;
            if (item.hasClass("clip")) {
              item_type = "clip";
            } else if (item.hasClass("transition")) {
              item_type = "transition";
            } else {
              // Unknown drop type
              return;
            }

            // get the item properties we need
            var item_id = item.attr("id");
            var item_num = item_id.substr(item_id.indexOf("_") + 1);
            var item_middle = item.position().top + (item.height() / 2); // find middle of clip
            var item_left = item.position().left;

            // Adjust top and left coordinates for scrollbars
            item_left = parseFloat(item_left + horz_scroll_offset);
            item_middle = parseFloat(item_middle - scrolling_tracks_offset_top + vert_scroll_offset);

            // make sure the item isn't dropped off too far to the left
            if (item_left < 0) {
              item_left = 0;
            }

            // get track the item was dropped on
            var drop_track_num = findTrackAtLocation(scope, parseInt(item_middle, 10));

            // if the droptrack was found, update the json
            if (drop_track_num !== -1) {

              // find the item in the json data
              item_data = null;
              if (item_type === "clip") {
                item_data = findElement(scope.project.clips, "id", item_num);
              } else if (item_type === "transition") {
                item_data = findElement(scope.project.effects, "id", item_num);
              }

              // set time diff (if not already determined)
              if (position_diff === 0.0) {
                // once calculated, we want to apply the exact same time diff to each clip/trans
                position_diff = (item_left / scope.pixelsPerSecond) - item_data.position;
              }

              // change the clip's track and position in the json data
              scope.$apply(function () {
                //set track
                item_data.layer = drop_track_num;
                item_data.position += position_diff;
                item_data.position = (Math.round((item_data.position * scope.project.fps.num) / scope.project.fps.den) * scope.project.fps.den ) / scope.project.fps.num;
              });

              // Resize timeline if it's too small to contain all clips
              scope.resizeTimeline();

              // Keep track of dropped clips (we'll check for missing transitions in a sec)
              dropped_clips.push(item_data);

              // Determine if this is the last iteration
              var needs_refresh = (index === selected_item_count - 1);

              // update clip in Qt (very important =)
              if (scope.Qt && item_type === "clip") {
                timeline.update_clip_data(JSON.stringify(item_data), true, true, !needs_refresh, tid);
              } else if (scope.Qt && item_type === "transition") {
                timeline.update_transition_data(JSON.stringify(item_data), true, !needs_refresh, tid);
              }


            }
          });

          // Add missing transitions (if any)
          if (dropped_clips.length === 1) {
            // Hack to only add missing transitions if a single clip is being dropped
            for (var clip_index = 0; clip_index < dropped_clips.length; clip_index++) {
              var item_data = dropped_clips[clip_index];

              // Check again for missing transitions
              var missing_transition_details = scope.getMissingTransitions(item_data);
              if (scope.Qt && missing_transition_details !== null) {
                timeline.add_missing_transition(JSON.stringify(missing_transition_details));
              }
            }
          }

          // Clear dropped clips
          dropped_clips = [];

          // Re-sort clips
          scope.enable_sorting = true;
          scope.sortItems();
        }
      });
    }
  };
});
