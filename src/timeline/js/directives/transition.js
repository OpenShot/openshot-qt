/**
 * @file
 * @brief Transition directives (draggable & resizable functionality)
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


// Init Variables
var dragging = false;
var resize_disabled = false;
var previous_drag_position = null;
var start_transitions = {};
var move_transitions = {};
var out_of_bounds = false;
var track_container_height = -1;

// Treats element as a transition
// 1: can be dragged
// 2: can be resized
// 3: class change when hovered over
var dragLoc = null;

App.directive('tlTransition', function() {
	return {
		scope: "@",
		link: function(scope, element, attrs) {

			//handle resizability of transition
			element.resizable({ 
				handles: "e, w",
				minWidth: 1,
				start: function(e, ui) {
					dragging = true;
					resize_disabled = false;
					
					//determine which side is being changed
					var parentOffset = element.offset(); 
					var mouseLoc = e.pageX - parentOffset.left;
					if (mouseLoc < 5) {
						dragLoc = 'left';
					} 
					else {
						dragLoc = 'right';
					}

					// Does this bounding box overlap a locked track?
					var vert_scroll_offset = $("#scrolling_tracks").scrollTop();
					var track_top = (parseInt(element.position().top) + parseInt(vert_scroll_offset));
					var track_bottom = (parseInt(element.position().top) + parseInt(element.height()) + parseInt(vert_scroll_offset));
					if (hasLockedTrack(scope, track_top, track_bottom)) {
						resize_disabled = true;
					}

					// Hide keyframe points
					element.find('.point_icon').hide();
				},
				stop: function(e, ui) {
					dragging = false;

					if (resize_disabled) {
						// disabled, do nothing
						resize_disabled = false;
						return;
					}

					// Make the keyframe points visible again
					element.find('.point_icon').show()

					//get amount changed in width
					var delta_x = ui.originalSize.width - ui.size.width;
					var delta_time = delta_x/scope.pixelsPerSecond;

					//change the transition end/start based on which side was dragged
					new_left = scope.transition.position;
					new_right = (scope.transition.end - scope.transition.start);

					if (dragLoc == 'left') {
						//changing the start of the transition
						new_left += delta_time;
						if (new_left < 0) {
							new_left = 0; // prevent less than zero
						}
					} 
					else {
						new_right -= delta_time;
					}

					//apply the new start, end and length to the transition's scope
					scope.$apply(function() {

						// Get the nearest starting frame position to the transition position (this helps to prevent cutting
						// in-between frames, and thus less likely to repeat or skip a frame).
						new_position = (Math.round((new_position * scope.project.fps.num) / scope.project.fps.den ) * scope.project.fps.den ) / scope.project.fps.num;
						new_right = (Math.round((new_right * scope.project.fps.num) / scope.project.fps.den ) * scope.project.fps.den ) / scope.project.fps.num;
						new_left = (Math.round((new_left * scope.project.fps.num) / scope.project.fps.den ) * scope.project.fps.den ) / scope.project.fps.num;

						if (dragLoc == 'right') {
							scope.transition.end = new_right;
						}
						if (dragLoc == 'left') {
							scope.transition.position = new_left;
							scope.transition.end -= delta_time;
						}
						
						// update transition in Qt (very important =)
            			if (scope.Qt) {
            				timeline.update_transition_data(JSON.stringify(scope.transition));
            			}
					});
				
					dragLoc = null;
				},
				resize: function(e, ui) {

					if (resize_disabled) {
						// disabled, keep the item the same size
						$(this).css(ui.originalPosition);
						$(this).width(ui.originalSize.width);
						return;
					}
					
					// get amount changed in width
					var delta_x = ui.originalSize.width - ui.size.width;
					var delta_time = Math.round(delta_x/scope.pixelsPerSecond);

					// change the transition end/start based on which side was dragged
					new_left = scope.transition.position;
					new_right = (scope.transition.end - scope.transition.start);

					if (dragLoc == 'left') {
						// changing the start of the transition
						new_left += delta_time;
						if (new_left < 0) { 
							ui.element.width(ui.size.width + (new_left * scope.pixelsPerSecond));
							ui.element.css("left", ui.position.left - (new_left * scope.pixelsPerSecond));
						} 
						else {
							ui.element.width(ui.size.width);
						}
					} 
					else {
						// changing the end of the transitions
						new_right -= delta_time;
						ui.element.width(ui.size.width);
					}
				}
			});
	
			//handle hover over on the transition
			element.hover(
	  			function () {
				  	if (!dragging)
				  	{
					  	element.addClass( "highlight_transition", 200, "easeInOutCubic" );
				  	}
			  	},
			  	function () {
				  	if (!dragging)
				  	{
					  	element.removeClass( "highlight_transition", 200, "easeInOutCubic" );
					}
			  	}
			);
			
			//handle draggability of transition
			element.draggable({
		        snap: ".track", // snaps to a track
		        snapMode: "inner", 
		        snapTolerance: 20,
		        scroll: true,
		        revert: 'invalid',
				cancel : '.transition_menu',
		        start: function(event, ui) {
		        	previous_drag_position = null;
		        	dragging = true;
		        	if (!element.hasClass('ui-selected')) {
		        		// Clear previous selections?
		        		var clear_selections = false;
		        		if ($(".ui-selected").length > 0) {
		        			clear_selections = true;
		        		}
		        		
		        		// SelectClip, SelectTransition
		        		var id = $(this).attr("id");
		        		if (element.hasClass('clip')) {
							// Select this clip, unselect all others
		        			scope.SelectTransition("", clear_selections);
		        			scope.SelectClip(id, clear_selections);
		        			
		        		} 
		        		else if (element.hasClass('transition')) {
							// Select this transition, unselect all others
		        			scope.SelectClip("", clear_selections);
		        			scope.SelectTransition(id, clear_selections);
		        		}
					}
					
				 	// Apply scope up to this point
				 	scope.$apply(function(){});
		        	
	            	var vert_scroll_offset = $("#scrolling_tracks").scrollTop();
	            	var horz_scroll_offset = $("#scrolling_tracks").scrollLeft();
	            	track_container_height = getTrackContainerHeight();

                    bounding_box = {};

		        	// Init all other selected transitions (prepare to drag them)
		        	$(".ui-selected").each(function() {
		        		start_transitions[$(this).attr('id')] = {
		        			"top": $(this).position().top + vert_scroll_offset,
                            "left": $(this).position().left + horz_scroll_offset
                        };
                        move_transitions[$(this).attr('id')] = {
                        	"top": $(this).position().top + vert_scroll_offset,
                            "left": $(this).position().left + horz_scroll_offset
                        };

                        //send transition to bounding box builder
                        setBoundingBox($(this));
                    });

					// Does this bounding box overlap a locked track?
					if (hasLockedTrack(scope, bounding_box.top, bounding_box.bottom) || scope.enable_razor) {
						return !event; // yes, do nothing
					}
		        },
                stop: function(event, ui) {
					// Ignore transition-menu click
					$( event.toElement ).one('.transition_menu', function(e) { 
							e.stopImmediatePropagation(); 
						}
					);
                	
                	// Hide snapline (if any)
                	scope.HideSnapline();
                	
                	// Clear previous drag position
					previous_drag_position = null;
					dragging = false;
				},
                drag: function(e, ui) {
                	var previous_x = ui.originalPosition.left;
					var previous_y = ui.originalPosition.top;
					if (previous_drag_position != null) {
						// if available, override with previous drag position
						previous_x = previous_drag_position.left;
						previous_y = previous_drag_position.top;
					}

					// set previous position (for next time around)
					previous_drag_position = ui.position;

	            	// Calculate amount to move transitions
	            	var x_offset = ui.position.left - previous_x;
	            	var y_offset = ui.position.top - previous_y;

					// Move the bounding box and apply snapping rules
					results = moveBoundingBox(scope, previous_x, previous_y, x_offset, y_offset, ui.position.left, ui.position.top);
					x_offset = results.x_offset;
					y_offset = results.y_offset;

					// Update ui object
					ui.position.left = results.position.left;
					ui.position.top = results.position.top;

    				// Move all other selected transitions with this one
	                $(".ui-selected").each(function() {
	                	var pos = $(this).position();
	                	var newY = move_transitions[$(this).attr('id')]["top"] + y_offset;
                        var newX = move_transitions[$(this).attr('id')]["left"] + x_offset;

						//update the transition location in the array
	                	move_transitions[$(this).attr('id')]['top'] = newY;
                        move_transitions[$(this).attr('id')]['left'] = newX;

						//change the element location
						$(this).css('left', newX);
				    	$(this).css('top', newY);
				    });
                },
                revert: function(valid) {
                    if(!valid) {
                        //the drop spot was invalid, so we're going to move all transitions to their original position
                        $(".ui-selected").each(function() {
                        	var oldY = start_transitions[$(this).attr('id')]['top'];
                        	var oldX = start_transitions[$(this).attr('id')]['left'];

                        	$(this).css('left', oldX);
				    		$(this).css('top', oldY);
                        });
                    }
                }
		      });
		}
	};
});