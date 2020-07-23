/**
 * @file
 * @brief Multiple-selection directive (JQueryUI Selectable)
 * @author Jonathan Thomas <jonathan@openshot.org>
 * @author Cody Parker <cody@yourcodepro.com>
 * @author FeRD (Frank Dana) <ferdnyc@gmail.com>
 *
 * @section LICENSE
 *
 * Copyright (c) 2008-2020 OpenShot Studios, LLC
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

/* global angular, timeline, findElement */

var App = angular.module("openshot-timeline");

// Handle multiple selections
App.directive("tlMultiSelectable", function () {
  return {
    link: function (scope, element, attrs) {
      element.selectable({
        filter: ".droppable",
        distance: 0,
        cancel: ".effect-container,.transition_menu,.clip_menu",
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
