/**
 * @file
 * @brief Transition directives (draggable & resizable functionality)
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


// Init Variables
var dragging = false;
var previous_drag_position = null;
var start_transitions = {};
var move_transitions = {};
var out_of_bounds = false;
var track_container_height = -1;

// Variables for resizing transitions
var last_resizable = { left: 0, width: 0 };

// Treats element as a transition
// 1: can be dragged
// 2: can be resized
// 3: class change when hovered over
var dragLog = null;

App.directive('tlTransition', function(){
	return {
		scope: "@",
		link: function(scope, element, attrs){

			//handle resizability of transition
			element.resizable({ 
				handles: "e, w",
				start: function(e, ui) {
					dragging = true;
					
					//determine which side is being changed
					var parentOffset = element.offset(); 
					var mouseLoc = e.pageX - parentOffset.left;
					if (mouseLoc < 5) {
						dragLoc = 'left';
					} else {
						dragLoc = 'right';
					}

				},
				stop: function(e, ui) {
					dragging = false;
					//get amount changed in width
					var delta_x = ui.originalSize.width - last_resizable.width;
					var delta_time = Math.round(delta_x/scope.pixelsPerSecond);

					//change the transition end/start based on which side was dragged
					new_left = scope.transition.position;
					new_right = scope.transition.duration;

					if (dragLoc == 'left'){
						//changing the start of the transition
						new_left += delta_time;
						if (new_left < 0) new_left = 0; // prevent less than zero
					} else {
						new_right -= delta_time;
					}

					//apply the new start, end and length to the transition's scope
					scope.$apply(function(){
	
						if (dragLoc == 'right'){
							scope.transition.duration = new_right;
						}
						if (dragLoc == 'left'){
							scope.transition.position = new_left;
							scope.transition.duration -= delta_time;
						}
						
						// update transition in Qt (very important =)
            			if (scope.Qt)
            				timeline.update_transition_data(JSON.stringify(scope.transition));

					});
				
					dragLoc = null;

				},
				resize: function(e, ui) {
					
					// get amount changed in width
					var delta_x = ui.originalSize.width - ui.size.width;
					var delta_time = Math.round(delta_x/scope.pixelsPerSecond);

					// change the transition end/start based on which side was dragged
					new_left = scope.transition.position;
					new_right = scope.transition.duration;

					if (dragLoc == 'left'){
						// changing the start of the transition
						new_left += delta_time;
						if (new_left < 0) { 
							ui.element.width(last_resizable.width + (new_left * scope.pixelsPerSecond));
							ui.element.css("left", last_resizable.left - (new_left * scope.pixelsPerSecond));
						}
						console.log("new_left" + new_left);
					} else {
						// changing the end of the transitions
						new_right -= delta_time;
					}

					// Set last_resizable
					last_resizable.left = ui.position.left;
					last_resizable.width = ui.size.width;

				},

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
		        stack: ".droppable", 
		        scroll: true,
		        revert: 'invalid',
		        start: function(event, ui) {
		        	previous_drag_position = null;
		        	dragging = true;
		        	if (!element.hasClass('ui-selected')){
		        		element.addClass('ui-selected');
		        	}
		        	
	            	var vert_scroll_offset = $("#scrolling_tracks").scrollTop();
	            	var horz_scroll_offset = $("#scrolling_tracks").scrollLeft();
	            	track_container_height = getTrackContainerHeight();

                    bounding_box = {};

		        	// Init all other selected transitions (prepare to drag them)
		        	$(".ui-selected").each(function(){
		        		start_transitions[$(this).attr('id')] = {"top": $(this).position().top + vert_scroll_offset,
                                						   "left": $(this).position().left + horz_scroll_offset};
                        move_transitions[$(this).attr('id')] = {"top": $(this).position().top + vert_scroll_offset,
                               							  "left": $(this).position().left + horz_scroll_offset};

                        //send transition to bounding box builder
                        setBoundingBox($(this));
                    });
		        	
		        },
                stop: function(event, ui) {
                	// Clear previous drag position
					previous_drag_position = null;
					dragging = false;

				},
                drag: function(e, ui) {
                	var previous_x = ui.originalPosition.left;
					var previous_y = ui.originalPosition.top;
					if (previous_drag_position)
					{
						// if available, override with previous drag position
						previous_x = previous_drag_position.left;
						previous_y = previous_drag_position.top;
					}

					// set previous position (for next time around)
					previous_drag_position = ui.position;

	            	// Calculate amount to move transitions
	            	var x_offset = ui.position.left - previous_x;
	            	var y_offset = ui.position.top - previous_y;
	            	
					// Check for shift key
					if (scope.shift_pressed) {
						// freeze X movement
						x_offset = 0;
						ui.position.left = previous_x;
					}

                    //update the dragged transition location in the location arrays
					move_transitions[element.attr('id')] = {"top": ui.position.top,
                                                      "left": ui.position.left};

                    //update box
                    bounding_box.left += x_offset;
                    bounding_box.right += x_offset;
                    bounding_box.top += y_offset;
                    bounding_box.bottom += y_offset;
                    
                    if (bounding_box.left < 0) {
                    	x_offset -= bounding_box.left;
                    	bounding_box.left = 0;
                		ui.position.left = previous_x + x_offset;
                		move_transitions[element.attr('id')]["left"] = ui.position.left;
                    }
                    if (bounding_box.top < 0) {
                    	y_offset -= bounding_box.top;
                    	bounding_box.top = 0;
                    	bounding_box.bottom = bounding_box.height;
                		ui.position.top = previous_y + y_offset;
                		move_transitions[element.attr('id')]["top"] = ui.position.top;
                    }
                    if (bounding_box.bottom > track_container_height) {
                    	y_offset -= (bounding_box.bottom - track_container_height);
                    	bounding_box.bottom = track_container_height;
                    	bounding_box.top = bounding_box.bottom - bounding_box.height;
                		ui.position.top = previous_y + y_offset;
                		move_transitions[element.attr('id')]["top"] = ui.position.top;
                    }
                    	
    				// Move all other selected transitions with this one
	                $(".ui-selected").not($(this)).each(function(){
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
                        $(".ui-selected").each(function(){
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

//Handle multiple selections
App.directive('tlMultiSelectable', function(){
	return {
		link: function(scope, element, attrs){
			element.selectable({
				filter: '.droppable',
			});
		}
	};
});





