/**
 * @file
 * @brief Clip directives (draggable & resizable functionality) 
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


// Init variables
var dragging = false;
var resize_disabled = false;
var previous_drag_position = null;
var start_clips = {};
var move_clips = {};
var out_of_bounds = false;
var track_container_height = -1;

// Treats element as a clip
// 1: can be dragged
// 2: can be resized
// 3: class change when hovered over
var dragLoc = null;

App.directive('tlClip', function($timeout){
	return {
		scope: "@",
		link: function(scope, element, attrs){

			//handle resizability of clip
			element.resizable({ 
				handles: "e, w",
				minWidth: 1,
				maxWidth: scope.clip.length * scope.pixelsPerSecond,
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

					// Does this bounding box overlap a locked track?
					if (hasLockedTrack(scope, e.pageY, e.pageY))
						return !event; // yes, do nothing

					// Does this bounding box overlap a locked track?
					var vert_scroll_offset = $("#scrolling_tracks").scrollTop();
					var track_top = (parseInt(element.position().top) + parseInt(vert_scroll_offset));
					var track_bottom = (parseInt(element.position().top) + parseInt(element.height()) + parseInt(vert_scroll_offset));
					if (hasLockedTrack(scope, track_top, track_bottom))
						resize_disabled = true;

					// Hide keyframe points
					element.find('.point_icon').fadeOut('fast');
					element.find('.audio-container').fadeOut('fast');

				},
				stop: function(e, ui) {
					dragging = false;

					if (resize_disabled) {
						// disabled, do nothing
						resize_disabled = false;
						return;
					}

					// Hide keyframe points
					if (dragLoc == 'right') {
						// Make the keyframe points visible again
						element.find('.point_icon').show();
						element.find('.audio-container').show();
					}

					//get amount changed in width
					var delta_x = ui.originalSize.width - ui.size.width;
					var delta_time = delta_x/scope.pixelsPerSecond;

					//change the clip end/start based on which side was dragged
					new_position = scope.clip.position;
					new_left = scope.clip.start;
					new_right = scope.clip.end;

					if (dragLoc == 'left'){
						// changing the start of the clip
						new_left += delta_time;
						if (new_left < 0) {
							// prevent less than zero
							new_left = 0.0;
							new_position -= scope.clip.start
						} else {
							new_position += delta_time
						}
					} else {
						// changing the end of the clips
						new_right -= delta_time;
						if (new_right > scope.clip.duration)
						    // prevent greater than duration
							new_right = scope.clip.duration;
					}

					//apply the new start, end and length to the clip's scope
					scope.$apply(function(){

						// Get the nearest starting frame position to the clip position (this helps to prevent cutting
						// in-between frames, and thus less likely to repeat or skip a frame).
						new_position = (Math.round((new_position * scope.project.fps.num) / scope.project.fps.den ) * scope.project.fps.den ) / scope.project.fps.num;
						new_right = (Math.round((new_right * scope.project.fps.num) / scope.project.fps.den ) * scope.project.fps.den ) / scope.project.fps.num;
						new_left = (Math.round((new_left * scope.project.fps.num) / scope.project.fps.den ) * scope.project.fps.den ) / scope.project.fps.num;

						if (scope.clip.end != new_right){
							scope.clip.end = new_right;
						}
						if (scope.clip.start != new_left){
							scope.clip.start = new_left;
							scope.clip.position = new_position;
						}

					// Resize timeline if it's too small to contain all clips
					scope.ResizeTimeline();

						// update clip in Qt (very important =)
            			if (scope.Qt)
            				timeline.update_clip_data(JSON.stringify(scope.clip));

					});

					//resize the audio canvas to match the new clip width
					if (scope.clip.show_audio){
						element.find(".audio-container").show();
						//redraw audio as the resize cleared the canvas
						drawAudio(scope, scope.clip.id);
					}

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
					var delta_x = parseFloat(ui.originalSize.width) - ui.size.width;
					var delta_time = delta_x / scope.pixelsPerSecond;

					// change the clip end/start based on which side was dragged
					new_left = scope.clip.start;
					new_right = scope.clip.end;

					if (dragLoc == 'left'){
						// changing the start of the clip
						new_left += delta_time;
						if (new_left < 0) {
							ui.element.width(ui.size.width + (new_left * scope.pixelsPerSecond));
							ui.element.css("left", ui.position.left - (new_left * scope.pixelsPerSecond));
						} else {
							ui.element.width(ui.size.width);
						}
					} else {
						// changing the end of the clips
						new_right -= delta_time;
						if (new_right > scope.clip.duration) {
							new_right = scope.clip.duration - new_right; // difference from duration
							ui.element.width(ui.size.width + (new_right * scope.pixelsPerSecond));

							// change back to actual duration (for the preview below)
							new_right = scope.clip.duration;
						} else {
							ui.element.width(ui.size.width);
						}
					}


					// Preview frame during resize
					if (dragLoc == 'left'){
						// Preview the left side of the clip
						scope.PreviewClipFrame(scope.clip.id, new_left);
					} else {
						// Preview the right side of the clip
						scope.PreviewClipFrame(scope.clip.id, new_right);
					}

				},

			});
	
			//handle hover over on the clip
			element.hover(
	  			function () {
				  	if (!dragging)
				  	{
					  	element.addClass( "highlight_clip", 200, "easeInOutCubic" );
				  	}
			  	},
			  	function () {
				  	if (!dragging)
				  	{
					  	element.removeClass( "highlight_clip", 200, "easeInOutCubic" );
					}
			  	}
			);

			//handle draggability of clip
			element.draggable({
		        snap: ".track", // snaps to a track
		        snapMode: "inner", 
		        snapTolerance: 20,
		        scroll: true,
				cancel: '.effect-container,.clip_menu',
		        start: function(event, ui) {
		        	previous_drag_position = null;
		        	dragging = true;
		        	if (!element.hasClass('ui-selected')) 
		        	{
		        		// Clear previous selections?
		        		var clear_selections = false;
		        		if ($(".ui-selected").length > 0)
		        			clear_selections = true;
		        		
		        		// SelectClip, SelectTransition
		        		var id = $(this).attr("id");
		        		if (element.hasClass('clip')) {
							// Select this clip, unselect all others
		        			scope.SelectTransition("", clear_selections);
		        			scope.SelectClip(id, clear_selections);
		        			
		        		} else if (element.hasClass('transition')) {
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

		        	// Init all other selected clips (prepare to drag them)
		        	$(".ui-selected").each(function(){
		        		start_clips[$(this).attr('id')] = {"top": $(this).position().top + vert_scroll_offset,
                                						   "left": $(this).position().left + horz_scroll_offset};
                        move_clips[$(this).attr('id')] = {"top": $(this).position().top + vert_scroll_offset,
                               							  "left": $(this).position().left + horz_scroll_offset};

                        //send clip to bounding box builder
                        setBoundingBox($(this));
                    });
					
					// Does this bounding box overlap a locked track?
					if (hasLockedTrack(scope, bounding_box.top, bounding_box.bottom) || scope.enable_razor)
						return !event; // yes, do nothing
		        	
		        },
                stop: function(event, ui) {

					// Ignore clip-menu click
					$( event.toElement ).one('.clip_menu', function(e){ e.stopImmediatePropagation(); } );

                	// Hide snapline (if any)
                	scope.HideSnapline();

                	// Clear previous drag position
					previous_drag_position = null;
					dragging = false;

				},
                drag: function(e, ui) {
                	var previous_x = ui.originalPosition.left;
					var previous_y = ui.originalPosition.top;
					if (previous_drag_position != null)
					{
						// if available, override with previous drag position
						previous_x = previous_drag_position.left;
						previous_y = previous_drag_position.top;
					}

					// set previous position (for next time around)
					previous_drag_position = ui.position;

	            	// Calculate amount to move clips
	            	var x_offset = ui.position.left - previous_x;
	            	var y_offset = ui.position.top - previous_y;

					// Move the bounding box and apply snapping rules
					results = moveBoundingBox(scope, previous_x, previous_y, x_offset, y_offset, ui.position.left, ui.position.top);
					x_offset = results.x_offset;
					y_offset = results.y_offset;

					// Update ui object
					ui.position.left = results.position.left;
					ui.position.top = results.position.top;

    				// Move all other selected clips with this one
	                $(".ui-selected").each(function(){
	                	var newY = move_clips[$(this).attr('id')]["top"] + y_offset;
                        var newX = move_clips[$(this).attr('id')]["left"] + x_offset;

						//update the clip location in the array
	                	move_clips[$(this).attr('id')]['top'] = newY;
                        move_clips[$(this).attr('id')]['left'] = newX;

						//change the element location
						$(this).css('left', newX);
				    	$(this).css('top', newY);

				    });

                },
                revert: function(valid) {
                    if(!valid) {
                        //the drop spot was invalid, so we're going to move all clips to their original position
                        $(".ui-selected").each(function(){
                        	var oldY = start_clips[$(this).attr('id')]['top'];
                        	var oldX = start_clips[$(this).attr('id')]['left'];

                        	$(this).css('left', oldX);
				    		$(this).css('top', oldY);
                        });
                    }
                }
		      });


		}
	};
});

// Handle clip effects
App.directive('tlClipEffects', function(){
	return{
		link: function(scope, element, attrs){

		}
	};
});

// Handle multiple selections
App.directive('tlMultiSelectable', function(){
	return {
		link: function(scope, element, attrs){
			element.selectable({
				filter: '.droppable',
				distance: 0,
				cancel: '.effect-container,.transition_menu,.clip_menu',
				selected: function( event, ui ) {

					// Identify the selected ID and TYPE
					var id = ui.selected.id;
					var type = "";
					var item = null;
					
					if (id.match("^clip_")) {
						id = id.replace("clip_", "");
						type = "clip";
						item = findElement(scope.project.clips, "id", id);
					} else if (id.match("^transition_")) {
						id = id.replace("transition_", "");
						type = "transition";
						item = findElement(scope.project.effects, "id", id);
					}
					
					if (scope.Qt)
					{
						timeline.addSelection(id, type, false);

						// Clear effect selections (if any)
						timeline.addSelection("", "effect", true);
					}

					// Update item state
					item.selected = true;
				},
				unselected: function( event, ui ) {

					// Identify the selected ID and TYPE
					var id = ui.unselected.id;
					var type = "";
					var item = null;
					
					if (id.match("^clip_")) {
						id = id.replace("clip_", "");
						type = "clip";
						item = findElement(scope.project.clips, "id", id);
					} else if (id.match("^transition_")) {
						id = id.replace("transition_", "");
						type = "transition";
						item = findElement(scope.project.effects, "id", id);
					}
					
					if (scope.Qt)
						timeline.removeSelection(id, type);

					// Update item state
					item.selected = false;
				},
				stop: function(event, ui) {
					// This is called one time after all the selecting/unselecting is done
					// Large amounts of selected item data could have changed, so
					// let's force the UI to update
					scope.$apply();
				}
			});
		}
	};
});





