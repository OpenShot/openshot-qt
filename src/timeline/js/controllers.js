/**
 * @file
 * @brief The AngularJS controller used by the OpenShot Timeline 
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


// Initialize the main controller module 
App.controller('TimelineCtrl',function($scope) {

	// DEMO DATA (used when debugging outside of Qt using Chrome)
	$scope.project =
    {
	  fps: {
		    num : 24,
		    den : 1
		   },
      duration : 300,				//length of project in seconds
      scale : 16.0,				//seconds per tick
      tick_pixels : 100,		//pixels between tick mark
      playhead_position : 10,	//position of play head
      clips : [
	               { 
	                 id : '1', 
	                 layer : 1, 
	                 image : './media/images/thumbnail.png',
	                 locked : false,
	                 duration : 32, //max length in seconds
	                 start : 0,
	                 end : 32,
	                 position : 0.0,
	                 title : 'Clip U2V5ENELDY',
	                 effects : [
	                           { type : 'Saturation', icon : 'bw.png'},
	                           { type : 'ChromaKey',icon : 'om.png'},
	                           { type : 'Negate',icon : 'neg.png'},
	                           { type : 'Blur', icon: 'blur.png'},
	                           { type : 'Brightness', icon: 'cartoon.png'}
	                           ],
	                 images :  {start: 1, end: 4},
	                 show_audio : false,

					 alpha: {
					    Points: [
					      {
					        "interpolation": 2,
					        "co": {
					          "Y": 0,
					          "X": 0
					        }
					      },
					      {
					        "interpolation": 1,
					        "co": {
					          "Y": 0,
					          "X": 250
					        }
					      },
					      {
					        "interpolation": 1,
					        "co": {
					          "Y": 1,
					          "X": 500
					        }
					      }
						]
					},
					location_x: { Points: [] },
					location_y: { Points: [] },
					scale_x: { Points: [] },
					scale_y: { Points: [] },
					rotation: { Points: [] },
					time: { Points: [] },
					volume: { Points: [] }
	                 
	               },
	               {
	                 id : '2', 
	                 layer : 2, 
	                 image : './media/images/thumbnail.png',
	                 locked : false,
	                 duration : 45,
	                 start : 0,
	                 end : 45,
	                 position : 0.0,
	                 title : 'Clip B',
	                 effects : [],
	                 images : {start: 3, end: 7},
	                 show_audio : false,
	                 alpha: { Points: [] },
	                 location_x: { Points: [] },
					 location_y: { Points: [] },
					 scale_x: { Points: [] },
					 scale_y: { Points: [] },
					 rotation: { Points: [] },
					 time: { Points: [] },
					 volume: { Points: [] }
	               },
	               {
	                 id : '3', 
	                 layer : 3, 
	                 image : './media/images/thumbnail.png',
	                 locked : false,
	                 duration : 120,
	                 start : 0,
	                 end : 120,
	                 position : 32.0,
	                 title : 'Clip C',
	                 effects : [
	                           { type : 'Deinterlace',icon : 'om.png'},
	                           { type : 'Blur', icon: 'blur.png'},
	                           { type : 'Mask', icon: 'cartoon.png'}
	                           ],
	                 images : { start: 5, end: 10 },
	                 show_audio : false,
	                 audio_data : [.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3, ],
	                 alpha: { Points: [] },
	                 location_x: { Points: [] },
					 location_y: { Points: [] },
					 scale_x: { Points: [] },
					 scale_y: { Points: [] },
					 rotation: { Points: [] },
					 time: { Points: [] },
					 volume: { Points: [] }
	               },
             ],
             
	  effects : [
	                	{
	   	                 id : '5', 
		                 layer : 4, 
		                 title : 'Transition',
		                 position : 20.0,
		                 start : 0,
		                 end : 30
	                	},
	                	{
	   	                 id : '6', 
		                 layer : 3, 
		                 title : 'Transition',
		                 position : 137.5,
		                 start : 0,
		                 end : 30
	                	}
                    
                    ],
             
	  layers : [
	  				{id: 'L0', number:0, y:0, label: ''},
					{id: 'L1', number:1, y:0, label: ''},
					{id: 'L2', number:2, y:0, label: ''},
					{id: 'L3', number:3, y:0, label: ''},
					{id: 'L4', number:4, y:0, label: ''}
	  				
             ],
             
	  markers : [
	                {
	                  id : 'M1',
	                  position : 16,
	                  icon : 'yellow.png'
	                },
	                {
	                  id : 'M2',
	                  position: 120,
	                  icon : 'green.png'
	                },
	                {
	                  id : 'M3',
	                  position: 300,
	                  icon : 'red.png'
	                },
	                {
	                  id : 'M4',
	                  position: 10,
	                  icon : 'purple.png'
	                },
              ],
              
	  progress : [
	                  [0, 30, 'rendering'],
	                  [40, 50, 'complete'],
	                  [100, 150, 'complete'],
                  ]
    };
  
  // Additional variables used to control the rendering of HTML
  $scope.pixelsPerSecond =  parseFloat($scope.project.tick_pixels) / parseFloat($scope.project.scale);
  $scope.playheadOffset = 0;
  $scope.keyframePointOffset = 3;
  $scope.playhead_animating = false;
  $scope.playhead_height = 300;
  $scope.playheadTime =  secondsToTime($scope.project.playhead_position, $scope.project.fps.num, $scope.project.fps.den);
  $scope.shift_pressed = false;
  $scope.snapline_position = 0.0;
  $scope.snapline = false;
  $scope.enable_snapping = true;
  $scope.debug = false;
  $scope.min_width = 1024;
  
  // Method to set if Qt is detected (which clears demo data)
  $scope.Qt = false;
  $scope.EnableQt = function() { 
	  	$scope.Qt = true;
	  	$scope.project.clips = [];
	  	$scope.project.markers = [];
	  	$scope.project.effects = [];
	  	$scope.project.progress = [];
	  	timeline.qt_log("$scope.Qt = true;"); 
  };

  // Move the playhead to a specific time
  $scope.MovePlayhead = function(position_seconds) {
	  // Update internal scope (in seconds)
	  $scope.$apply(function(){
		  $scope.project.playhead_position = position_seconds;
		  $scope.playheadTime = secondsToTime(position_seconds, $scope.project.fps.num, $scope.project.fps.den);
	  });
  };
  
  // Move the playhead to a specific frame
  $scope.MovePlayheadToFrame = function(position_frames) {
	  // Don't move the playhead if it's currently animating
	  if ($scope.playhead_animating)
	  		return;
	  
	  // Determine seconds
	  var frames_per_second = $scope.project.fps.num / $scope.project.fps.den;
	  var position_seconds = ((position_frames - 1) / frames_per_second);
	  
	  // Update internal scope (in seconds)
	  $scope.MovePlayhead(position_seconds);
  };

  // Move the playhead to a specific time
  $scope.PreviewFrame = function(position_seconds) {
	  // Determine frame
	  var frames_per_second = $scope.project.fps.num / $scope.project.fps.den;
	  var frame = (position_seconds * frames_per_second) + 1;
	  
	  // Update GUI with position (to the preview can be updated)
	  if ($scope.Qt)
		  timeline.PlayheadMoved(position_seconds, frame, secondsToTime(position_seconds, $scope.project.fps.num, $scope.project.fps.den));
  };


  // Move the playhead to a specific time
  $scope.PreviewClipFrame = function(clip_id, position_seconds) {
	  // Determine frame
	  var frames_per_second = $scope.project.fps.num / $scope.project.fps.den;
	  var frame = (position_seconds * frames_per_second) + 1;

	  // Update GUI with position (to the preview can be updated)
	  if ($scope.Qt)
		  timeline.PreviewClipFrame(clip_id, frame);
  };

  // Get an array of keyframe points for the selected clips
  $scope.getKeyframes = function(object){
  	// List of keyframes
  	keyframes = {};

    var frames_per_second = $scope.project.fps.num / $scope.project.fps.den;
    var clip_start_x = Math.round(object.start * frames_per_second) + 1.0;
    var clip_end_x = Math.round(object.end * frames_per_second) + 1.0;

 	// Loop through properties of an object (clip/transition), looking for keyframe points
	for (child in object) {
	    if (!object.hasOwnProperty(child)) {
	        //The current property is not a direct property of p
	        continue;
	    }

	    // Determine if this property is a Keyframe
	 	if (typeof object[child] == "object" && "Points" in object[child])
			for (var point = 0; point < object[child].Points.length; point++) {
				var co = object[child].Points[point].co;
				if (co.X >= clip_start_x && co.X <= clip_end_x)
					// Only add keyframe coordinates that are within the bounds of the clip
					keyframes[co.X] = co.Y;
			}
	}
	
	// Return keyframe array
	return keyframes;
  };
  
  
  // Determine track top (in vertical pixels)
  $scope.getTrackTop = function(layer){
	  // Get scrollbar position
	  var vert_scroll_offset = $("#scrolling_tracks").scrollTop();
	  var horz_scroll_offset = $("#scrolling_tracks").scrollLeft();

	  // Find this tracks Y location
	  var track_id = "div#track_" + layer;
	  if ($(track_id).length)
		  return $(track_id).position().top + vert_scroll_offset;
	  else
		  return 0;
  };


// ############# QT FUNCTIONS #################### //

 // Change the scale and apply to scope
 $scope.setScale = function(scaleVal){
      $scope.$apply(function(){
         $scope.project.scale = scaleVal;
         $scope.pixelsPerSecond =  parseFloat($scope.project.tick_pixels) / parseFloat($scope.project.scale);
     });
 };

 // Change the snapping mode
 $scope.SetSnappingMode = function(enable_snapping){
      $scope.$apply(function(){
         $scope.enable_snapping = enable_snapping;
		 if (enable_snapping)
		 	$(".droppable").draggable("option", "snapTolerance", 20);
		 else
		 	$(".droppable").draggable("option", "snapTolerance", 0);
     });
 };

 // Get the color of an effect
 $scope.GetEffectColor = function(effect_type){
	switch (effect_type)
	{
		case "Blur":
			return "#0095bf";
		case "Brightness":
			return "#5500ff";
		case "ChromaKey":
			return "#00ad2d";
		case "Deinterlace":
			return "#006001";
		case "Mask":
			return "#cb0091";
		case "Negate":
			return "#ff9700";
		case "Saturation":
			return "#ff3d00";
	}

	 return "rgba(54, 25, 25, .2)";
 };

 // Add a new clip to the timeline
 $scope.AddClip = function(x, y, clip_json){
	 $scope.$apply(function(){
		 
		 // Convert x and y into timeline vars
		 var scrolling_tracks_offset = $("#scrolling_tracks").offset().left;
		 var clip_position = parseFloat(x - scrolling_tracks_offset) / parseFloat($scope.pixelsPerSecond);
		 clip_json.position = clip_position;
		 clip_json.layer = $scope.GetTrackAtY(y).number;
		 
		 // Push new clip onto stack
		 $scope.project.clips.push(clip_json);

	 });
 };
 
 // Select clip in scope
 $scope.SelectClip = function(clip_id, clear_selections) {
 	// Trim clip_id
 	var id = clip_id.replace("clip_", "");

	// Clear transitions also (if needed)
	if (id != "" && clear_selections)
		$scope.SelectTransition("", true);
 	
 	// Unselect all clips
	for (var clip_index = 0; clip_index < $scope.project.clips.length; clip_index++)
		if ($scope.project.clips[clip_index].id == id) {
			$scope.project.clips[clip_index].selected = true;
			if ($scope.Qt)
	 			timeline.addSelection(id, "clip");
		}
		else if (clear_selections) {
			$scope.project.clips[clip_index].selected = false;
			if ($scope.Qt)
	 			timeline.removeSelection($scope.project.clips[clip_index].id, "clip");
		}
 };
 
  // Select transition in scope
 $scope.SelectTransition = function(tran_id, clear_selections) {
 	// Trim tran_id
 	var id = tran_id.replace("transition_", "");

	// Clear clips also (if needed)
	if (id != "" && clear_selections)
		$scope.SelectClip("", true);
 	
 	// Unselect all transitions
	for (var tran_index = 0; tran_index < $scope.project.effects.length; tran_index++)
		if ($scope.project.effects[tran_index].id == id) {
			$scope.project.effects[tran_index].selected = true;
		 	if ($scope.Qt)
			 	timeline.addSelection(id, "transition");
		}
		else if (clear_selections) {
			$scope.project.effects[tran_index].selected = false;
		 	if ($scope.Qt)
			 	timeline.removeSelection($scope.project.effects[tran_index].id, "transition");
		}
 };

  // Format the thumbnail path
 $scope.FormatThumbPath = function(image_url) {
 	if (image_url.charAt(0) == ".")
		return image_url;
	else
		return "file:///" + image_url;
 };

  // Select transition in scope
 $scope.SelectEffect = function(effect_id) {
 	if ($scope.Qt) {
	 	timeline.qt_log("$scope.SelectEffect");
	 	timeline.addSelection(effect_id, "effect", true);
 	}
 };

// Find the furthest right edge on the timeline (and resize it if too small)
 $scope.ResizeTimeline = function() {

 	// Unselect all clips
	var furthest_right_edge = 0;
	for (var clip_index = 0; clip_index < $scope.project.clips.length; clip_index++)
	{
		var clip = $scope.project.clips[clip_index];
		var right_edge = clip.position + (clip.end - clip.start);
		if (right_edge > furthest_right_edge)
			furthest_right_edge = right_edge;
	}

	// Resize timeline
	if (furthest_right_edge > $scope.project.duration)
		if ($scope.Qt) {
			timeline.resizeTimeline(furthest_right_edge + 10)
			$scope.project.duration = furthest_right_edge + 10;
		}
 };
 
 // Show clip context menu
 $scope.ShowClipMenu = function(clip_id) {
 	if ($scope.Qt) {
	 	timeline.qt_log("$scope.ShowClipMenu");
	 	timeline.ShowClipMenu(clip_id);
 	}
 };

 // Show clip context menu
 $scope.ShowEffectMenu = function(effect_id) {
 	if ($scope.Qt) {
	 	timeline.qt_log("$scope.ShowEffectMenu");
	 	timeline.ShowEffectMenu(effect_id);
 	}
 };
 
 // Show transition context menu
 $scope.ShowTransitionMenu = function(tran_id) {
 	if ($scope.Qt) {
	 	timeline.qt_log("$scope.ShowTransitionMenu");
	 	timeline.ShowTransitionMenu(tran_id);
 	}
 };
 
 // Show track context menu
 $scope.ShowTrackMenu = function(layer_id) {
 	if ($scope.Qt) {
	 	timeline.qt_log("$scope.ShowTrackMenu");
	 	timeline.ShowTrackMenu(layer_id);
 	}
 };

 // Show marker context menu
 $scope.ShowMarkerMenu = function(marker_id) {
 	if ($scope.Qt) {
	 	timeline.qt_log("$scope.ShowMarkerMenu");
	 	timeline.ShowMarkerMenu(marker_id);
 	}
 };
 
  // Show playhead context menu
 $scope.ShowPlayheadMenu = function(position) {
 	if ($scope.Qt) {
	 	timeline.qt_log("$scope.ShowPlayheadMenu");
	 	timeline.ShowPlayheadMenu(position);
	 }
 };

 // Get the name of the track
 $scope.GetTrackName = function(layer_label, layer_number){
	// Determine custom label or default track name
	if (layer_label.length > 0)
		return layer_label;
	else
		return "Track " + layer_number;
 };

 // Get the width of the timeline in pixels
 $scope.GetTimelineWidth = function(min_value){
	// Adjust for minimim length
	return Math.max(min_value, $scope.project.duration * $scope.pixelsPerSecond);
 };

 
 // Get Position of item (used by Qt)
 $scope.GetJavaScriptPosition = function(x){
	// Adjust for scrollbar position
	var horz_scroll_offset = $("#scrolling_tracks").scrollLeft();
	var scrolling_tracks_offset_left = $("#scrolling_tracks").offset().left;
	x += horz_scroll_offset;

	 // Convert x into position in seconds
	 var clip_position = parseFloat(x - scrolling_tracks_offset_left) / parseFloat($scope.pixelsPerSecond);
	 if (clip_position < 0)
		 clip_position = 0;
	 
	 // Return position in seconds
	 return clip_position;
 };
 
 // Get Track number of item (used by Qt)
 $scope.GetJavaScriptTrack = function(y){
	// Adjust for scrollbar position
  	var vert_scroll_offset = $("#scrolling_tracks").scrollTop();
	y += vert_scroll_offset;

	// Return number of track
	var track_number = parseInt($scope.GetTrackAtY(y).number);
	return track_number;
 };
 
 // Get JSON of most recent item (used by Qt)
 $scope.UpdateRecentItemJSON = function(item_type) {

		// update clip in Qt (very important =)
		if (item_type == 'clip') {
			var item_data = $scope.project.clips[$scope.project.clips.length - 1];
			timeline.update_clip_data(JSON.stringify(item_data));
		}
		else if (item_type == 'transition') {
			var item_data = $scope.project.effects[$scope.project.effects.length - 1];
			timeline.update_transition_data(JSON.stringify(item_data));
		}

	    // Resize timeline if it's too small to contain all clips
	    $scope.ResizeTimeline();
		 	
 };
 
 // Move a new clip to the timeline
 $scope.MoveItem = function(x, y, item_type){
	 $scope.$apply(function(){
		 
     	var vert_scroll_offset = $("#scrolling_tracks").scrollTop();
    	var horz_scroll_offset = $("#scrolling_tracks").scrollLeft();
    	x += horz_scroll_offset;
    	y += vert_scroll_offset;
		 
		 // Convert x and y into timeline vars
		 var scrolling_tracks_offset_left = $("#scrolling_tracks").offset().left;
		 var scrolling_tracks_offset_top = $("#scrolling_tracks").offset().top;
		 var clip_position = parseFloat(x - scrolling_tracks_offset_left) / parseFloat($scope.pixelsPerSecond);
		 if (clip_position < 0)
			 clip_position = 0;

		 // Update clip position & layer (based on x,y)
		 if (item_type == "clip") {
			 // move clip
			 $scope.project.clips[$scope.project.clips.length - 1].position = clip_position;
			 $scope.project.clips[$scope.project.clips.length - 1].layer = $scope.GetTrackAtY(y - scrolling_tracks_offset_top).number;

			 // hide and show elements of the clip (based on size)
			 handleVisibleClipElements($scope, $scope.project.clips[$scope.project.clips.length - 1].id);
		 
		 } else if (item_type == "transition") {
			 // move transition
			 $scope.project.effects[$scope.project.effects.length - 1].position = clip_position;
			 $scope.project.effects[$scope.project.effects.length - 1].layer = $scope.GetTrackAtY(y - scrolling_tracks_offset_top).number;
		 }

	 });
 };
 
 // Update X,Y indexes of tracks / layers (anytime the project.layers scope changes)
 $scope.UpdateLayerIndex = function(){
	 $scope.$apply(function(){
		 
		 // Loop through each layer
		for (var layer_index = 0; layer_index < $scope.project.layers.length; layer_index++) {
			var layer = $scope.project.layers[layer_index];
			
			// Find element on screen (bound to this layer)
			var layer_elem = $("#track_" + layer.number);
			if (layer_elem) {
				// Update the top offset
				layer.y = layer_elem.offset().top;
			}
		}
		
	 });
 };
 
 // Sort clips and transitions by position
 $scope.SortItems = function(){
	 console.log('Sorting clips and transitions');
	 $scope.$apply(function(){
	 	
		 // Sort by position second
		 $scope.project.clips = $scope.project.clips.sort(function(a,b) {
			    if ( a.position < b.position )
			        return -1;
			    if ( a.position > b.position )
			        return 1;
			    return 0;
		  });
	 
	});
	// Print clips 
	//for (var index = 0; index < $scope.project.clips.length; index++) {
	//	var clip = $scope.project.clips[index];
	//	console.log('clip layer: ' + clip.layer + ', position: ' + clip.position);
	//}
 };
 
 // Find overlapping clips
 $scope.GetMissingTransitions = function(original_clip) {

 	var transition_size = null;
 	
 	// Get clip that matches this id
 	var original_left = original_clip.position;
 	var original_right = original_clip.position + (original_clip.end - original_clip.start);
	
	// Search through all other clips on this track, and look for overlapping ones
	for (var index = 0; index < $scope.project.clips.length; index++) {
		var clip = $scope.project.clips[index];

		// skip clips that are not on the same layer
		if (original_clip.layer != clip.layer)
			continue;
		
		// is clip overlapping
		var clip_left = clip.position;
		var clip_right = clip.position + (clip.end - clip.start);
		
		if (original_left < clip_right && original_left > clip_left)
			transition_size = { "position" : original_left, "layer" : clip.layer, "start" : 0, "end" : (clip_right - original_left) };
		else if (original_right > clip_left && original_right < clip_right)
			transition_size = { "position" : clip_left, "layer" : clip.layer, "start" : 0, "end" : (original_right - clip_left) };

		if (transition_size != null && transition_size.end >= 0.5)
			// Found a possible missing transition
			break;
		else if (transition_size != null && transition_size.end < 0.5)
			// Too small to be a missing transitions, clear and continue looking
			transition_size = null;

	}

	// Search through all existing transitions, and don't overlap an existing one
	if (transition_size != null)
		for (var tran_index = 0; tran_index < $scope.project.effects.length; tran_index++) {
			var tran = $scope.project.effects[tran_index];

			// skip transitions that are not on the same layer
			if (tran.layer != transition_size.layer)
				continue;

			var tran_left = tran.position;
			var tran_right = tran.position + (tran.end - tran.start);

			var new_tran_left = transition_size.position;
			var new_tran_right = transition_size.position + (transition_size.end - transition_size.start);

			var TOLERANCE = 0.01;
			// Check for overlapping transitions
			if (Math.abs(tran_left - new_tran_left) < TOLERANCE || Math.abs(tran_right - new_tran_right) < TOLERANCE) {
				transition_size = null; // this transition already exists
				break;
			}
		}

 	return transition_size;
 };
 
 // Search through clips and transitions to find the closest element within a given threashold
 $scope.GetNearbyPosition = function(pixel_positions, threashold, ignore_ids){
	// init some vars
	var smallest_diff = 900.0;
	var smallest_abs_diff = 900.0;
	var snapping_position = 0.0;
	var diffs = [];
	
	// Loop through each pixel position (supports multiple positions: i.e. left and right side of bounding box)
	for (var pos_index = 0; pos_index < pixel_positions.length; pos_index++) {
		var pixel_position = pixel_positions[pos_index];
		var position = pixel_position / $scope.pixelsPerSecond;
		 
		// Add clip positions to array
		for (var index = 0; index < $scope.project.clips.length; index++) {
			var clip = $scope.project.clips[index];

			// exit out if this item is in ignore_ids
			if (ignore_ids.hasOwnProperty(clip.id))
				continue;
			
			diffs.push({'diff' : position - clip.position, 'position' : clip.position}, // left side of clip
			           {'diff' : position - (clip.position + (clip.end - clip.start)), 'position' : clip.position + (clip.end - clip.start)}); // right side of clip
		}
		
		// Add transition positions to array
		for (var index = 0; index < $scope.project.effects.length; index++) {
			var transition = $scope.project.effects[index];

			// exit out if this item is in ignore_ids
			if (ignore_ids.hasOwnProperty(transition.id))
				continue;
			
			diffs.push({'diff' : position - transition.position, 'position' : transition.position}, // left side of transition
			           {'diff' : position - (transition.position + (transition.end - transition.start)), 'position' : transition.position + (transition.end - transition.start)}); // right side of transition
		}

		// Add marker positions to array
		for (var index = 0; index < $scope.project.markers.length; index++) {
			var marker = $scope.project.markers[index];

			diffs.push({'diff' : position - marker.position, 'position' : marker.position}, // left side of marker
			           {'diff' : position - (marker.position + (marker.end - marker.start)), 'position' : marker.position + (marker.end - marker.start)}); // right side of marker
		}

		// Add playhead position to array
		var playhead_diff = position - $scope.project.playhead_position;
		diffs.push({'diff' : playhead_diff, 'position' : $scope.project.playhead_position });
		
		// Loop through diffs (and find the smallest one)
		for (var diff_index = 0; diff_index < diffs.length; diff_index++) {
			var diff = diffs[diff_index].diff;
			var position = diffs[diff_index].position;
			var abs_diff = Math.abs(diff);
			
			// Check if this clip is nearby
			if (abs_diff < smallest_abs_diff && abs_diff <= threashold) {
				// This one is smaller
				smallest_diff = diff;
				smallest_abs_diff = abs_diff;
				snapping_position = position;
			}
		}
	}
	
	// no nearby found?
	if (smallest_diff == 900.0)
		smallest_diff = 0.0;
	
	// Return closest nearby position
	return [smallest_diff, snapping_position];
 };
 
  // Show the nearby snapping line
 $scope.ShowSnapline = function(position){
	 $scope.$apply(function(){
		$scope.snapline_position = position;
		$scope.snapline = true; 
	 });
 };
 
 // Hide the nearby snapping line
 $scope.HideSnapline = function(){
	 $scope.$apply(function(){
		$scope.snapline = false; 
	 });
 };
 
 // Find a track JSON object at a given y coordinate (if any)
 $scope.GetTrackAtY = function(y){

		// Loop through each layer (looking for the closest track based on Y coordinate)
		for (var layer_index = $scope.project.layers.length - 1; layer_index >= 0 ; layer_index--) {
			var layer = $scope.project.layers[layer_index];

			// Compare position of track to Y param
			if (layer.y > y)
				// return first matching layer
				return layer;
		}

		// no layer found (return top layer... if any)
		if ($scope.project.layers.length > 0)
			return $scope.project.layers[0];
		else
			return null;
 };
 
 // Apply JSON diff from UpdateManager (this is how the user interface communicates changes
 // to the timeline. A change can be an insert, update, or delete. The change is passed in
 // as JSON, which represents the change.
 $scope.ApplyJsonDiff = function(jsonDiff){

	 // Loop through each UpdateAction
	for (var action_index = 0; action_index < jsonDiff.length; action_index++) {
		var action = jsonDiff[action_index];
	 	
		 // Iterate through the key levels (looking for a matching element in the $scope.project)
		 var previous_object = null;
		 var current_object = $scope.project;
		 var current_position = 0;
		 var current_key = "";
		 for (var key_index = 0; key_index < action.key.length; key_index++) {
		 	var key_value = action.key[key_index];

		 	// Check the key type
		 	if (key_value.constructor == String) {
		 		// Does the key value exist in scope
		 		if (!current_object.hasOwnProperty(key_value))
		 			// No match, bail out
		 			return false;
		 		
	 			// set current level and previous level
	 			previous_object = current_object;
	 			current_object = current_object[key_value];
	 			current_key = key_value;
		 		
		 	} else if (key_value.constructor == Object) {
		 		// Get the id from the object (if any)
		 		var id = null;
		 		if ("id" in key_value)
		 			id = key_value["id"];
		 			
		 		// Be sure the current_object is an Array
		 		if (current_object.constructor == Array) {
			 		// Filter the current_object for a specific id
			 		current_position = 0;
			 		for (var child_index = 0; child_index < current_object.length; child_index++) {
			 			var child_object = current_object[child_index];
			 		
						// Find matching child
						if (child_object.hasOwnProperty("id") && child_object.id == id) {
				 			// set current level and previous level
				 			previous_object = current_object;
				 			current_object = child_object;
				 			break; // found child, stop looping
				 		}
				 		
				 		// increment index
				 		current_position++;
			 		}
		 		}
		 	}
		}

	 	// Now that we have a matching object in the $scope.project...
	 	if (current_object){ 
	 		// INSERT OBJECT
		 	if (action.type == "insert") {

		 		// Insert action's value into current_object
		 		if (current_object.constructor == Array)
		 			// push new element into array
		 			$scope.$apply(function(){
		 				current_object.push(action.value);
		 			});
		 		else {
			 		// replace the entire value
			 		if (previous_object.constructor == Array) {
			 			// replace entire value in OBJECT
			 			$scope.$apply(function(){
			 				previous_object[current_position] = action.value;
			 			});
			 			
			 		} else if (previous_object.constructor == Object) {
			 			// replace entire value in OBJECT
			 			$scope.$apply(function(){
			 				previous_object[current_key] = action.value;
			 			});
			 		}
		 		}
		 		
		 	} else if (action.type == "update") {
				// UPDATE OBJECT
				// Update: If action and current object are Objects
				if (current_object.constructor == Object && action.value.constructor == Object) {
					for (var update_key in action.value)
						if (update_key in current_object)
						// Only copy over keys that exist in both action and current_object
						$scope.$apply(function () {
							current_object[update_key] = action.value[update_key];
						});
				}
			 	else {
			 		// replace the entire value
			 		if (previous_object.constructor == Array) {
			 			// replace entire value in OBJECT
			 			$scope.$apply(function(){
			 				previous_object[current_position] = action.value;
			 			});
			 			
			 		} else if (previous_object.constructor == Object) {
			 			// replace entire value in OBJECT
			 			$scope.$apply(function(){
			 				previous_object[current_key] = action.value;
			 			});
			 		}
			 	}

		 		
		 	} else if (action.type == "delete") {
		 		// DELETE OBJECT
		 		// delete current object from it's parent (previous object)
		 		$scope.$apply(function(){
		 			previous_object.splice(current_position, 1);
		 		});
		 	}

		    // Resize timeline if it's too small to contain all clips
		    $scope.ResizeTimeline();
		 	
		    // Re-sort clips and transitions array
		    scope.SortItems();

	 	}
	}	
	 
	// return true
	return true;
 };
 
 
 // Load entire project data JSON from UpdateManager (i.e. user opened an existing project)
 $scope.LoadJson = function(EntireProjectJson){
 	
	 $scope.$apply(function(){
 		// Update the entire JSON object for the entire timeline
 		$scope.project = EntireProjectJson.value;
 		
 		// Un-select any selected items
 		$scope.SelectClip("", true);
	 });

	// Re-index Layer Y values
	$scope.UpdateLayerIndex();
	 
	 // return true
	 return true;
 };
  
// ############# END QT FUNCTIONS #################### //   



// ############ DEBUG STUFFS ################## //
 
 $scope.ToggleDebug = function() {
	 if ($scope.debug == true)
		 $scope.debug = false;
	 else
		 $scope.debug = true;
 };

  // Debug method to add clips to the $scope
  $scope.addClips = function(numClips) {
        startNum = $scope.project.clips.length + 1;
	  	positionNum = 0;
        for (var x = 0; x < parseInt(numClips); x++) {
           $scope.project.clips.push({
	                 id : x.toString(),
	                 layer : 0,
	                 image : './media/images/thumbnail.png',
	                 locked : false,
	                 duration : 5,
	                 start : 0,
	                 end : 5,
	                 position : positionNum,
	                 title : 'Clip B',
	                 effects : [],
	                 images : {start: 3, end: 7},
	                 show_audio : false,
	                 alpha: { Points: [] },
	                 location_x: { Points: [] },
					 location_y: { Points: [] },
					 scale_x: { Points: [] },
					 scale_y: { Points: [] },
					 rotation: { Points: [] },
					 time: { Points: [] },
					 volume: { Points: [] }
	               });
            startNum++;
			positionNum+=5;
        };
      
        $scope.numClips = "";

    };

  // Debug method to add effects to a clip's $scope
  $scope.addEffect = function(clipNum){
	    //find the clip in the json data
	    elm = findElement($scope.project.clips, "number", clipNum);
	    elm.effects.push({
	       effect : 'Old Movie',
	       icon : 'om.png'
	    });
	    $scope.clipNum = "";
                    
  };

  // Debug method to add a marker to the $scope
  $scope.addMarker = function(markLoc){
        $scope.project.markers.push({
          location: parseInt(markLoc),
          icon: 'blue.png'
        });
        $scope.markLoc = "";
  };

  // Debug method to change a clip's image
  $scope.changeImage = function(startImage){
      console.log(startImage);
        $scope.project.clips[2].images.start=startImage;
        $scope.startImage = "";
  };

});
