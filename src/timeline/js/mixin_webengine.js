/**
 * @file
 * @brief JavaScript file to initialize QtWebEngine JS mixin
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

/*global timeline, angular, QWebChannel*/
var timeline = null;

function init_mixin() {

  // Check for Qt Integration
  var channel = new QWebChannel(qt.webChannelTransport, function (channel) {
    timeline = channel.objects.timeline;
    timeline.qt_log("INFO", "Qt Ready");

    // Only enable Qt once Angular as initialized
    angular.element(document).ready(function () {
      timeline.qt_log("INFO", "Angular Ready");
      $("body").scope().enableQt();
      $("body").addClass("webengine");
    });

  });

}
