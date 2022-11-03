/**
 * @file
 * @brief Misc directives (right click handling, debug functions, etc...)
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


// Handle right-click context menus
/*global App*/
App.directive("ngRightClick", function ($parse) {
  return function (scope, element, attrs) {
    var fn = $parse(attrs.ngRightClick);
    element.bind("contextmenu", function (event) {
      event.preventDefault();
      fn(scope, {$event: event});
    });
  };
});


// Debug directive (for binding a timeline scale slider)
App.directive("dbSlider", function () {
  return {
    restrict: "A",
    link: function (scope, element) {
      element.slider({
        value: 30,
        step: 1,
        min: 1,
        max: 210,
        slide: function (event, ui) {
          $("#scaleVal").val(ui.value);
          scope.$apply(function () {
            scope.project.scale = ui.value;
            scope.pixelsPerSecond = parseFloat(scope.project.tick_pixels) / parseFloat(scope.project.scale);
          });

        }
      });
    }
  };
});
