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
var App = angular.module('openshot-timeline', ['ui.bootstrap','ngAnimate']);


// Wait for document ready event
 $( document ).ready(function() {

	/// Capture window resize event, and resize scrollable divs (i.e. track container)
	$( window ).resize(function() {

		// Determine Y offset for track container div
		var track_offset = $("#track_controls").offset().top;

		// Set the height of the scrollable divs. This resizes the tracks to fit the remaining
		// height of the web page. As the user changes the size of the web page, this will continue
		// to fire, and resize the child divs to fit.
		var new_track_height = $(this).height() - track_offset;

		$("#track_controls").height(new_track_height);
		$("#scrolling_tracks").height(new_track_height);
		$('body').scope().playhead_height = $("#track-container").height();
		$(".playhead-line").height($('body').scope().playhead_height);
	});

	// Check for Qt Integration
	if(typeof timeline !== 'undefined') {
		timeline.qt_log("Qt Found!");
		$('body').scope().EnableQt();
		timeline.page_ready();
		$('body').scope().SetThumbAddress(timeline.get_thumb_address());
	}

	// Manually trigger the window resize code (to verify it runs at least once)
	$(window).trigger('resize');

	// Bind to keydown event (to detect SHIFT)
	$( "body" ).keydown(function(event) {
	  if (event.which===16)
    	$('body').scope().shift_pressed = true;
	});
	$( "body" ).keyup(function(event) {
	  if ($('body').scope().shift_pressed)
	  	$('body').scope().shift_pressed = false;
	});
});

