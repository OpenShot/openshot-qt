/**
 * @file
 * @brief AngularJS App (initializes angular application)
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

// Initialize Angular application
/*global App, angular, timeline, init_mixin*/
var App = angular.module("openshot-timeline", ["ui.bootstrap", "ngAnimate"]);
if (!window.hasOwnProperty("timeline")) {
  var timeline = null;
}

// Wait for document ready event
$(document).ready(function () {
  // Initialize Qt
  var have_qt = false;
  if(typeof window.timeline !== "undefined") {
    // WebKit
    timeline.qt_log("INFO", "WebKit Ready");
    angular.element(document).ready(function () {
      // Only enable Qt once Angular is initialized
      timeline.qt_log("INFO", "Angular Ready");
      $("body").scope().enableQt();
    });
  } else if (window.hasOwnProperty("qt")) {
    // WebEngine
    var channel = new QWebChannel(window.qt.webChannelTransport,
      function (channel) {
        window.timeline = channel.objects.timeline;
        window.timeline.qt_log("INFO", "WebEngine Ready");
        angular.element(document).ready(function () {
          // Only enable Qt once Angular is initialized
          window.timeline.qt_log("INFO", "Angular Ready");
          $("body").scope().enableQt();
        });
        timeline = window.timeline;
      });
  } else {
    // Dummy timeline which proxies all unknown properties as functions
    // that simply return true. (timeline.qt_log() logs to console.)
    const proxy_handler = {
      get: function(obj, prop) {
        if (prop in obj) {
          return obj[prop];
        }
        if (prop == "qt_log") {
          return function(level, args) {
            console.log(args);
          }
        }
        return function(args) {
          return true;
        };
      },
    }
    timeline = new Proxy({}, proxy_handler);
    timeline.fake = true;
    timeline.qt_log("INFO", "Dummy backend Ready");
    window.timeline = timeline;
    angular.element(document).ready(function () {
      // Log when Angular is initialized
      window.timeline.qt_log("INFO", "Angular Ready");
    });
  }

  /// Capture window resize event, and resize scrollable divs (i.e. track container)
  $(window).resize(function () {

    // Determine Y offset for track container div
    var track_controls = $("#track_controls");
    var track_offset = track_controls.offset().top;

    // Set the height of the scrollable divs. This resizes the tracks to fit the remaining
    // height of the web page. As the user changes the size of the web page, this will continue
    // to fire, and resize the child divs to fit.
    var new_track_height = $(this).height() - track_offset;

    track_controls.height(new_track_height);
    $("#scrolling_tracks").height(new_track_height);
    $("body").scope().playhead_height = $("#track-container").height();
    $(".playhead-line").height($("body").scope().playhead_height);
  });

  // Manually trigger the window resize code (to verify it runs at least once)
  $(window).trigger("resize");
});
