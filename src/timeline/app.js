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


// Wait for document ready event
$(document).ready(function () {

  var body_object = $("body");

  // Initialize Qt Mixin (WebEngine or WebKit)
  init_mixin();

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
    body_object.scope().playhead_height = $("#track-container").height();
    $(".playhead-line").height(body_object.scope().playhead_height);
  });

  // Manually trigger the window resize code (to verify it runs at least once)
  $(window).trigger("resize");
});

/**
 * handle key events using the user's keyboard shortcut settings
 * settings made available in webview.py -> page_ready
 */
document.addEventListener('keydown', (e) => {

  if (!keyboard_shortcuts){
    keyboard_shortcuts = [];
    keyboard_shortcuts['selectAll'] = ['Ctrl', 'a'];
  }

  // Make a list of keys being pressed
  keys = [e.key]
  if (e.ctrlKey) keys.push('Ctrl');
  if (e.altKey) keys.push('Alt');
  if (e.shiftKey) keys.push('Shift');
    
  // Compare lists ignoring order
  function equivalentList(l1, l2) {
    function toLower(x) {
        if (typeof(x) == 'string')
            return x.toLowerCase();
        else
            return x;
    }
    l1 = l1.map(toLower)
    l2 = l2.map(toLower)
    while (l1.length > 0) {
        i = l2.indexOf(l1[0])
        if ( i == -1)
            return false;
        l1.shift();
        l2.splice(i,1);
    }
    if (l2.length > 0)
      // In the case that l2 is a superset of l1
      return false;
    return true;
  }

  selectAll = [...keyboard_shortcuts['selectAll']] // A copy that won't touch the original
  // TODO:
    // copy
    // paste
    // about
    // insert keyframe
  
  // selectAll
  if (equivalentList(keys, selectAll)) {
    $('body').scope().selectAll();
  }
});