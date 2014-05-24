// Angular app init
var App = angular.module('openshot-timeline', ['ui.bootstrap']);


// Window resize code
 $( document ).ready(function() {
 
	/// Capture window resize event, and resize scrollable divs (i.e. track container)
	$( window ).resize(function() {
	
		// Determine Y offset for track container div
		var track_offset = $("#track_controls").offset().top;
		var playhead_line_offset = $(".playhead-line").offset().top;
	  
		// Set the height of the scrollable divs. This resizes the tracks to fit the remaining
		// height of the web page. As the user changes the size of the web page, this will continue
		// to fire, and resize the child divs to fit.
		var new_track_height = $(this).height() - track_offset;
		var new_playhead_line_height = $(this).height() - playhead_line_offset;
		
		$("#track_controls").height(new_track_height);
		$("#scrolling_tracks").height(new_track_height);
		$(".playhead-line").height(new_playhead_line_height);
	});
	
	// Check for Qt Integration
	if(typeof timeline != 'undefined') {
		timeline.qt_log("Qt Found!");
		$('body').scope().EnableQt()
	} else {
		console.log("Qt NOT Found!");
	}
});

// Init window resize
$(window).trigger('resize');
