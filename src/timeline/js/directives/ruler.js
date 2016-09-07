/**
 * @file
 * @brief Ruler directives (dragging playhead functionality, progress bars, tick marks, etc...)
 * @author Jonathan Thomas <jonathan@openshot.org>
 * @author Cody Parker <cody@yourcodepro.com>
 *
 * @section LICENSE
 *
 * Copyright (c) 2008-2014 OpenShot Studios, LLC
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


// Variables for panning by middle click
var is_scrolling = false;
var starting_scrollbar = { x: 0, y: 0 };
var starting_mouse_position = { x: 0, y: 0 };

// Variables for scrolling control
var scroll_left_pixels = 0;


// This container allows for tracks to be scrolled (with synced ruler)
// and allows for panning of the timeline with the middle mouse button
App.directive('tlScrollableTracks', function () {
	return {
		restrict: 'A',

		link: function (scope, element, attrs) {

			// Sync ruler to track scrolling
			element.on('scroll', function () {
				//set amount scrolled
				scroll_left_pixels = element.scrollLeft();

				$('#track_controls').scrollTop(element.scrollTop());
				$('#scrolling_ruler').scrollLeft(element.scrollLeft());
				$('#progress_container').scrollLeft(element.scrollLeft());
			});

			// Initialize panning when middle mouse is clicked
			element.on('mousedown', function(e) {
				if (e.which == 2) { // middle button
					e.preventDefault();
					is_scrolling = true;
					starting_scrollbar = { x: element.scrollLeft(), y: element.scrollTop() };
					starting_mouse_position = { x: e.pageX, y: e.pageY };
					element.addClass('drag_cursor');
				}
			});

			// Pans the timeline (on middle mouse clip and drag)
			element.on('mousemove', function(e){
				if (is_scrolling) {
					// Calculate difference from last position
					difference = { x: starting_mouse_position.x-e.pageX, y: starting_mouse_position.y-e.pageY};

					// Scroll the tracks div
					element.scrollLeft(starting_scrollbar.x + difference.x);
					element.scrollTop(starting_scrollbar.y + difference.y);
				}
			});

			// Remove move cursor (i.e. dragging has stopped)
			element.on('mouseup', function(e) {
				element.removeClass('drag_cursor');
			});


		}
	};
});

// Track scrolling mode on body tag... allows for capture of released middle mouse button
App.directive('tlBody', function () {
	return {
		link: function (scope, element, attrs){

			element.on('mouseup', function(e){
				if (e.which == 2) // middle button
					is_scrolling = false;
			});


		}
	};
});


// The HTML5 canvas ruler
App.directive('tlRuler', function ($timeout) {
	return {
		restrict: 'A',
		link: function (scope, element, attrs) {
			//on click of the ruler canvas, jump playhead to the clicked spot
			element.on('mousedown', function(e){
				// Get playhead position
				var playhead_left = e.pageX - element.offset().left;
				var playhead_seconds = playhead_left / scope.pixelsPerSecond;

				// Immediately preview frame (don't wait for animated playhead)
				scope.PreviewFrame(playhead_seconds);

				// Animate to new position (and then update scope)
				scope.playhead_animating = true;
				$(".playhead-line").animate({left: playhead_left + scope.playheadOffset }, 200);
				$(".playhead-top").animate({left: playhead_left + scope.playheadOffset }, 200, function() {
					// Update playhead
					scope.MovePlayhead(playhead_seconds);

					// Animation complete.
					scope.$apply(function(){
						scope.playhead_animating = false;
					});
				});

			});

			// Move playhead to new position (if it's not currently being animated)
			element.on('mousemove', function(e){
				if (e.which == 1 && !scope.playhead_animating) { // left button
					var playhead_seconds = (e.pageX - element.offset().left) / scope.pixelsPerSecond;
					// Update playhead
					scope.MovePlayhead(playhead_seconds);
					scope.PreviewFrame(playhead_seconds);
				}
			});

			//watch the scale value so it will be able to draw the ruler after changes,
			//otherwise the canvas is just reset to blank
			scope.$watch('project.scale + markers.length + project.duration', function (val) {
             if (val){

	            	 $timeout(function(){
						//get all scope variables we need for the ruler
						var scale = scope.project.scale;
						var tick_pixels = scope.project.tick_pixels;
						var each_tick = tick_pixels / 2;
						var pixel_length = scope.GetTimelineWidth(1024);

				    	//draw the ruler
				    	var ctx = element[0].getContext('2d');
				    	//clear the canvas first
				    	ctx.clearRect(0, 0, element.width(), element.height());
				    	//set number of ticks based 2 for each pixel_length
				    	num_ticks = pixel_length / 50;

						ctx.lineWidth = 1;
						ctx.strokeStyle = "#c8c8c8";
						ctx.lineCap = "round";

				    	//loop em and draw em
						for (x=0;x<num_ticks+1;x++){
							ctx.beginPath();

							//if it's even, make the line longer
							if (x%2 == 0){
								line_top = 18;
								//if it's not the first line, set the time text
								if (x != 0){
									//get time for this tick
									time = (scale * x) /2;
									time_text = secondsToTime(time, scope.project.fps.num, scope.project.fps.den);

									//write time on the canvas, centered above long tick
									ctx.fillStyle = "#c8c8c8";
									ctx.font = "0.9em";
									ctx.fillText(time_text["hour"] +":"+ time_text["min"] +":"+ time_text["sec"], x*each_tick-22, 11);
								}
							} else {
								//shorter line
								line_top = 28;
							}

							ctx.moveTo(x*each_tick, 39);
							ctx.lineTo(x*each_tick, line_top);
							ctx.stroke();
						}
				    }, 0);

             }
         });

		}

	};
});


// The HTML5 canvas ruler
App.directive('tlRulertime', function () {
	return {
		restrict: 'A',
		link: function (scope, element, attrs) {
			//on click of the ruler canvas, jump playhead to the clicked spot
			element.on('mousedown', function(e){
				var playhead_seconds = 0.0;
				// Update playhead
				scope.MovePlayhead(playhead_seconds);
				scope.PreviewFrame(playhead_seconds);

			});

			// Move playhead to new position (if it's not currently being animated)
			element.on('mousemove', function(e){
				if (e.which == 1 && !scope.playhead_animating) { // left button
					var playhead_seconds = 0.0;
					// Update playhead
					scope.MovePlayhead(playhead_seconds);
					scope.PreviewFrame(playhead_seconds);
				}
			});


		}
	};
});



// Handles the HTML5 canvas progress bar
App.directive('tlProgress', function($timeout){
	return {
		link: function(scope, element, attrs){
			scope.$watch('project.progress.version + project.scale', function (val) {
             if (val) {
             	$timeout(function(){
					//clear the canvas first
					var ctx = element[0].getContext('2d');
					ctx.clearRect(0, 0, element.width(), element.height());

					// Determine fps & and get cached ranges
					var fps = scope.project.fps.num / scope.project.fps.den;
					var progress = scope.project.progress.ranges;

					// Loop through each cached range of frames, and draw rect
					for(p=0;p<progress.length;p++){

						//get the progress item details
						var start_second = parseFloat(progress[p]["start"]) / fps;
						var stop_second = parseFloat(progress[p]["end"]) / fps;

						//figure out the actual pixel position
						var start_pixel = start_second * scope.pixelsPerSecond;
						var stop_pixel = stop_second * scope.pixelsPerSecond;
						var rect_length = stop_pixel - start_pixel;

						//get the element and draw the rects
						ctx.beginPath();
						ctx.rect(start_pixel, 0, rect_length, 5);
						ctx.fillStyle = '#4B92AD';
						ctx.fill();
					}

             	}, 0);

             }
         });


		}
	};
});





