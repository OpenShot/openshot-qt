/**
 * @file
 * @brief Track directives (droppable functionality, etc...)
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


// Treats element as a track
// 1: allows clips, transitions, and effects to be dropped
App.directive('tlTrack', function($timeout) {
    return {
        // A = attribute, E = Element, C = Class and M = HTML Comment
        restrict:'A',
        link: function(scope, element, attrs) {
        	
			scope.$watch('project.layers', function (val) {
                if (val) {
                	$timeout(function(){
				        // Update track indexes if tracks change
                		scope.UpdateLayerIndex();
                		console.log('update track indexes...');
                	}, 0);
                		
                }
            });

        	//make it accept drops
        	element.droppable({
		        accept: ".droppable",
		       	drop:function(event,ui) {

		       		//with each dragged clip, find out which track they landed on
		       		$(".ui-selected").each(function() {
		       			var item = $(this);
						
		       			// Remove selected class
						if ($(".ui-selected").length > 1)
						{
							for (var clip_index = 0; clip_index < scope.project.clips.length; clip_index++)
								scope.project.clips[clip_index].selected = false;
							
						}
						
						// Determine type of item
						item_type = null;
						if (item.hasClass('clip'))
							item_type = 'clip';
						else if(item.hasClass('transition'))
							item_type = 'transition';
						else
							// Unknown drop type
							return;

		       			// get the item properties we need
		       			item_id = item.attr("id");
		       			item_num = item_id.substr(item_id.indexOf("_") + 1);
		       			item_middle = item.position().top + (item.height() / 2); // find middle of clip
		       			item_left = item.position().left + scroll_left_pixels;

						// make sure the item isn't dropped off too far to the left
						if (item_left < 0) item_left = 0;

		            	// get track the item was dropped on 
						drop_track_num = findTrackAtLocation(parseInt(item_middle));
		            	
		            	// if the droptrack was found, update the json
		            	if (drop_track_num != -1){ 

		            		// find the item in the json data
		            		item_data = null;
		            		if (item_type == 'clip')
		            			item_data = findElement(scope.project.clips, "id", item_num);
		            		else if (item_type == 'transition')
		            			item_data = findElement(scope.project.transitions, "id", item_num);

		            		// change the clip's track and position in the json data
		            		scope.$apply(function(){
		            			//set track
		            			item_data.layer = drop_track_num;
		            			item_data.position =  parseInt(item_left)/scope.pixelsPerSecond;
		            			
								// update clip in Qt (very important =)
		            			if (scope.Qt && item_type == 'clip')
		            				timeline.update_clip_data(JSON.stringify(item_data));
		            			else if (scope.Qt && item_type == 'transition')
		            				timeline.update_transition_data(JSON.stringify(item_data));
							});

		            	}
		            });
		            
		            // Re-sort clips
		            scope.SortItems();
		        }	
		    });
    	}    
    };
});