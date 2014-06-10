/**
 * @file
 * @brief Misc Functions used by the OpenShot Timeline 
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


// Find a JSON element / object with a particular value in the json data
function findElement(arr, propName, propValue) {

  // Loop through array looking for a matching element
  for (var i=0; i < arr.length; i++)
    if (arr[i][propName] == propValue)
      return arr[i];

}

// Get the height of the track container (minus bottom margin of last track)
function getTrackContainerHeight() {
	
	var track_margin = 0;
	if ($(".track").length)
		if ($(".track").css("margin-bottom"))
			track_margin = parseInt($(".track").css("margin-bottom").replace("px",""));
	
	return $("#track-container").height() - track_margin;
}

// Hide and show various clip elements (based on width of clip)
function handleVisibleClipElements(scope, clip_id){

    // Get the clip in the scope
    clip = findElement(scope.project.clips, "id", clip_id);
    element = $("#clip_"+clip_id);

    // Check clip width to determine which elements can be shown
    var clip_width = element.width();
    var thumb_width = $(".thumb").outerWidth(true);
    var effects_width = element.find(".clip_effects").outerWidth(true); 
    var label_width = element.find(".clip_label").outerWidth(true);
    var menu_width = element.find(".clip_menu").outerWidth(true);   
    
    // Set min widths
    var min_for_thumb_end = thumb_width * 2;
    var min_for_thumb_start = thumb_width;
    var min_for_menu = menu_width;
    var min_for_effects = menu_width + effects_width;
    var min_for_label = menu_width + effects_width + label_width;


    // Show the images as audio is not shown
    if (!clip.show_audio){
        //show end clip?
        //(clip_width <= min_for_thumb_end) ? element.find(".thumb-end").hide() : element.find(".thumb-end").show();
        
        //show start clip?
        //(clip_width <= min_for_thumb_start) ? element.find(".thumb-start").hide() : element.find(".thumb-start").show();
        //console.log("W: " + clip_width  + " --- CLIP" + clip.id + " : " + min_for_thumb_start);
    }

    // Show label?
    (clip_width <= min_for_label) ? element.find(".clip_label").hide() : element.find(".clip_label").show();
    
    // Show effects?
    (clip_width <= min_for_effects) ? element.find(".clip_effects").hide() : element.find(".clip_effects").show();

    // Show menu?
    (clip_width <= min_for_menu) ? element.find(".clip_menu").hide() : element.find(".clip_menu").show();

    element.find(".clip_top").show();
    //element.find(".thumb-container").show();
}

// Draw the audio wave on a clip
function drawAudio(scope, clip_id){
    //get the clip in the scope
    clip = findElement(scope.project.clips, "id", clip_id);
    
    if (clip.show_audio){
        element = $("#clip_"+clip_id);

        //show audio container
        //element.find(".audio-container").show();
        
        //draw audio
        var audio_canvas = element.find(".audio");
        var ctx = audio_canvas[0].getContext('2d');
        //set the midpoint
        var mid_point = parseInt(audio_canvas.css("height")) / 2;
        var line_spot = 0;
        
        //draw midpoint line
        ctx.beginPath();
        ctx.lineWidth = .5;
        ctx.beginPath();
        ctx.moveTo(0, mid_point);
        ctx.lineTo(parseInt(audio_canvas.css("width")), mid_point);
        ctx.strokeStyle = "#fff";
        ctx.stroke();

        //for each point of audio data, draw a line
        for (var i = 0; i < clip.audio_data.length; i++) {
            //increase the 'x' axis draw point
            line_spot += 1;
            ctx.beginPath();
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(line_spot, mid_point);
            var audio_point = clip.audio_data[i];
            //set the point to draw to
            var draw_to = (audio_point * mid_point);
            //handle the 'draw to' point based on positive or negative audio point
            if (audio_point >= 0) draw_to = mid_point - draw_to;
            if (audio_point < 0) draw_to = mid_point + (draw_to * -1);
            //draw it
            ctx.lineTo(line_spot, draw_to);
            ctx.strokeStyle = "#FF6E97";
            ctx.stroke();
        }
    }
    
}

// Convert seconds into formatted time stamp
function secondsToTime(secs)
{
    var t = new Date(1970,0,1);
    t.setSeconds(secs);
    var s = t.toTimeString().substr(0,8);
    if(secs > 86399)
    	s = Math.floor((t - Date.parse("1/1/70")) / 3600000) + s.substr(2);
    return s;
}

// Find the closest track number (based on a Y coordinate)
function findTrackAtLocation(top){
	//default return value
	var retVal = "track_-1";
    
    //if the clip was dropped above the top track, return -1
    var track_count = $('.track').length;

	//loop all tracks
	$(".track").each(function(index, element) {
        var track = $(this);
	    
        //if clip top is less than 0, then set it to the first track
        if (index == 0 && top < 0) {
            retVal = track.attr("id");
            return false;
        }else{
            //otherwise, find the correct track
            track_top = track.position().top;
    	    track_bottom = track_top + track.outerHeight(true);
            if (top >= track_top && top <= track_bottom){
        		//found the track at this location
        		retVal = track.attr("id");
        		return false;
        	}
        }

        //if this is the last and no track was found, return the last track
        if (index == track_count - 1 && retVal == -1) {
            retVal = track.attr("id");
            return false;
        }
    });

    return parseInt(retVal.substr(retVal.indexOf("_") + 1));;
}


var bounding_box = Object();

// Build bounding box (since multiple items can be selected)
function setBoundingBox(item){
	var vert_scroll_offset = $("#scrolling_tracks").scrollTop();
	var horz_scroll_offset = $("#scrolling_tracks").scrollLeft();
	
    var item_bottom = item.position().top + item.height() + vert_scroll_offset;
    var item_top = item.position().top + vert_scroll_offset;
    var item_left = item.position().left + horz_scroll_offset;
    var item_right = item.position().left + horz_scroll_offset + item.width();

    if(jQuery.isEmptyObject(bounding_box)){
        bounding_box.left = item_left;
        bounding_box.top = item_top;
        bounding_box.bottom = item_bottom;
        bounding_box.right = item_right;
        bounding_box.height = item.height();
        bounding_box.width = item.width();
    }else{
        //compare and change if item is a better fit for bounding box edges
        if (item_top < bounding_box.top) bounding_box.top = item_top;
        if (item_left < bounding_box.left) bounding_box.left = item_left;
        if (item_bottom > bounding_box.bottom) bounding_box.bottom = item_bottom;
        if (item_right > bounding_box.right) bounding_box.right = item_right;
        
        // compare height and width of bounding box (take the largest number)
        var height = bounding_box.bottom - bounding_box.top;
        var width = bounding_box.right - bounding_box.left;
        if (height > bounding_box.height) bounding_box.height = height;
        if (width > bounding_box.width) bounding_box.width = width;
    }
}

// Move bounding box (apply snapping and constraints)
function moveBoundingBox(scope, element, previous_x, previous_y, x_offset, y_offset, ui) {
    
	// Check for shift key
	if (scope.shift_pressed) {
		// freeze X movement
		x_offset = 0;
		ui.position.left = previous_x;
	}

    // Update bounding box
    bounding_box.left += x_offset;
    bounding_box.right += x_offset;
    bounding_box.top += y_offset;
    bounding_box.bottom += y_offset;

    // Check overall timeline constraints (i.e don't let clips be dragged outside the timeline)
    if (bounding_box.left < 0) {
    	// Left border
    	x_offset -= bounding_box.left;
    	bounding_box.left = 0;
    	bounding_box.right = bounding_box.width;
		ui.position.left = previous_x + x_offset;
    }
    if (bounding_box.top < 0) {
    	// Top border
    	y_offset -= bounding_box.top;
    	bounding_box.top = 0;
    	bounding_box.bottom = bounding_box.height;
		ui.position.top = previous_y + y_offset;
    }
    if (bounding_box.bottom > track_container_height) {
    	// Bottom border
    	y_offset -= (bounding_box.bottom - track_container_height);
    	bounding_box.bottom = track_container_height;
    	bounding_box.top = bounding_box.bottom - bounding_box.height;
		ui.position.top = previous_y + y_offset;
    }
    
    // Find closest nearby object, if any (for snapping)
    var results = scope.GetNearbyPosition([bounding_box.left, bounding_box.right], 1.0);
    var nearby_offset = results[0] * scope.pixelsPerSecond;
    var snapline_position = results[1];

    if (snapline_position) {
    	snapped = true; 
    	
    	// Show snapping line
    	scope.ShowSnapline(snapline_position);

    	// Snap bounding box to this position
    	x_offset -= nearby_offset;
    	bounding_box.left -= nearby_offset;
    	bounding_box.right -= nearby_offset;
		ui.position.left -= nearby_offset;
		
    } else {
	    // Hide snapline
		scope.HideSnapline();
	}
    
    return { 'x_offset' : x_offset, 'y_offset' : y_offset };
}

