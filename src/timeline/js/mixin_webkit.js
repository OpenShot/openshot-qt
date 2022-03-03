/**
 * @file
 * @brief JavaScript file to initialize QtWebKit JS mixin
 * @author Jonathan Thomas <jonathan@openshot.org>
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

/*global timeline, qt, angular*/

function init_mixin() {

  // Only enable Qt once Angular as initialized
  angular.element(document).ready(function () {
    if (typeof timeline !== "undefined") {
      timeline.qt_log("INFO", "Qt Ready");
      $("body").scope().enableQt();
      $("body").addClass("webkit");
    }
    timeline.qt_log("INFO", "Angular Ready");
  });

}
