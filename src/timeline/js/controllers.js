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
      duration : 600,			//length of project in seconds
      scale : 16.0,				//seconds per tick
      tick_pixels : 100,		//pixels between tick mark
      playhead_position : 10,	//position of play head
      clips : [
	               { 
	                 id : '1', 
	                 layer : 1, 
	                 image : 'track1.png',
	                 locked : false,
	                 duration : 32, //max length in seconds
	                 start : 0,
	                 end : 32,
	                 position : 0.0,
	                 title : 'Clip U2V5ENELDY',
	                 effects : [
	                           { effect : 'Black and White', icon : 'bw.png'},
	                           { effect : 'Old Movie',icon : 'om.png'},
	                           { effect : 'Negative',icon : 'neg.png'},
	                           { effect : 'Blur', icon: 'blur.png'},
	                           { effect : 'Cartoon', icon: 'cartoon.png'}
	                           ],
	                 images :  {start: 1, end: 4},
	                 show_audio : false,
	
	               },
	               {
	                 id : '2', 
	                 layer : 2, 
	                 image : 'track2.png',
	                 locked : false,
	                 duration : 45,
	                 start : 0,
	                 end : 45,
	                 position : 0.0,
	                 title : 'Clip B',
	                 effects : [],
	                 images : {start: 3, end: 7},
	                 show_audio : false,
	               },
	               {
	                 id : '3', 
	                 layer : 3, 
	                 image : 'track3.png',
	                 locked : false,
	                 duration : 120,
	                 start : 0,
	                 end : 120,
	                 position : 32.0,
	                 title : 'Clip C',
	                 effects : [
	                           { effect : 'Old Movie',icon : 'om.png'},
	                           { effect : 'Blur', icon: 'blur.png'},
	                           { effect : 'Cartoon', icon: 'cartoon.png'}
	                           ],
	                 images : { start: 5, end: 10 },
	                 show_audio : false,
	                 audio_data : [.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3, ]
	               },
             ],
             
	  transitions : [
	                	{
	   	                 id : '5', 
		                 layer : 4, 
		                 title : 'Transition',
		                 position : 20.0,
		                 duration : 30
	                	},
	                	{
	   	                 id : '6', 
		                 layer : 3, 
		                 title : 'Transition',
		                 position : 137.5,
		                 duration : 30
	                	}
                    
                    ],
             
	  layers : [
	               {number:4, y:0},
	               {number:3, y:0},
	               {number:2, y:0},               
	               {number:1, y:0},
	               {number:0, y:0}, 
             ],
             
	  markers : [
	                {
	                  location : 16,
	                  icon : 'yellow.png'
	                },
	                {
	                  location: 120,
	                  icon : 'green.png'
	                },
	                {
	                  location: 300,
	                  icon : 'red.png'
	                },
	                {
	                  location: 10,
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
  $scope.playhead_animating = false;
  $scope.playhead_height = 300;
  $scope.playheadTime =  secondsToTime($scope.project.playhead_position);
  $scope.shift_pressed = false;
  $scope.snapline_position = 0.0;
  $scope.snapline = false;
  
  // Method to set if Qt is detected (which clears demo data)
  $scope.Qt = false;
  $scope.EnableQt = function() { 
	  	$scope.Qt = true;
	  	$scope.project.clips = [];
	  	$scope.project.transitions = [];
	  	timeline.qt_log("$scope.Qt = true;"); 
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
 
 // Show clip context menu
 $scope.ShowClipMenu = function(clip_id) {
 	if ($scope.Qt) {
	 	timeline.qt_log("$scope.ShowClipMenu");
	 	timeline.ShowClipMenu(clip_id);
 	}
 };
 
 // Show transition context menu
 $scope.ShowTransitionMenu = function(tran_id) {
 	if ($scope.Qt) {
	 	timeline.qt_log("$scope.ShowTransitionMenu");
	 	timeline.ShowTransitionMenu(tran_id);
 	}
 };
 
  // Show playhead context menu
 $scope.ShowPlayheadMenu = function(position) {
 	if ($scope.Qt) {
	 	timeline.qt_log("$scope.ShowPlayheadMenu");
	 	timeline.ShowPlayheadMenu(position);
	 }
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
	 	timeline.qt_log(item_type);
	 	
		// update clip in Qt (very important =)
		if (item_type == 'clip') {
			var item_data = $scope.project.clips[$scope.project.clips.length - 1];
			timeline.update_clip_data(JSON.stringify(item_data));
		}
		else if (item_type == 'transition') {
			var item_data = $scope.project.transitions[$scope.project.transitions.length - 1];
			timeline.update_transition_data(JSON.stringify(item_data));
		}
 }
 
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
			 $scope.project.transitions[$scope.project.transitions.length - 1].position = clip_position;
			 $scope.project.transitions[$scope.project.transitions.length - 1].layer = $scope.GetTrackAtY(y - scrolling_tracks_offset_top).number;
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
	 
	 // Sort by position second
	 $scope.project.clips = $scope.project.clips.sort(function(a,b) {
		    if ( a.position < b.position )
		        return -1;
		    if ( a.position > b.position )
		        return 1;
		    return 0;
	  });
	 
	// Print clips 
	//for (var index = 0; index < $scope.project.clips.length; index++) {
	//	var clip = $scope.project.clips[index];
	//	console.log('clip layer: ' + clip.layer + ', position: ' + clip.position);
	//}
 };
 
 // Search through clips and transitions to find the closest element within a given threashold
 $scope.GetNearbyPosition = function(pixel_position, threashold){
	var position = pixel_position / $scope.pixelsPerSecond;
	var smallest_diff = 900.0;
	var smallest_abs_diff = 900.0;
	var snapping_position = 0.0;
	var end_padding = $scope.project.fps.den / $scope.project.fps.num; // add a frame onto the end of clips
	var diffs = [];
	 
	// Add clip position to array
	for (var index = 0; index < $scope.project.clips.length; index++) {
		var clip = $scope.project.clips[index];
		diffs.push({'diff' : position - clip.position, 'position' : clip.position}, // left side of clip
		           {'diff' : position - (clip.position + (clip.end - clip.start) + end_padding), 'position' : clip.position + (clip.end - clip.start) + end_padding}); // right side of clip
	}
	
	// Add transition position to array
	for (var index = 0; index < $scope.project.transitions.length; index++) {
		var transition = $scope.project.transitions[index];
		diffs.push({'diff' : position - transition.position, 'position' : transition.position}, // left side of transition
		           {'diff' : position - (transition.position + transition.duration + end_padding), 'position' : transition.position + transition.duration + end_padding}); // right side of transition
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
		 $scope.snapline_position = -1;
		$scope.snapline = false; 
	 });
 };
 
 // Find a track JSON object at a given y coordinate (if any)
 $scope.GetTrackAtY = function(y){

		// Loop through each layer (looking for the closest track based on Y coordinate)
		for (var layer_index = 0; layer_index < $scope.project.layers.length; layer_index++) {
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
		 		$scope.$apply(function(){
		 		// Insert action's value into current_object
		 		if (current_object.constructor == Array)
		 			// push new element into array
		 			current_object.push(action.value);
		 		else {
			 		// replace the entire value
			 		if (previous_object.constructor == Array) {
			 			// replace entire value in OBJECT
			 			previous_object[current_position] = action.value;
			 			
			 		} else if (previous_object.constructor == Object) {
			 			// replace entire value in OBJECT
			 			previous_object[current_key] = action.value;
			 		}
		 		}
		 		});
		 		
		 	} else if (action.type == "update") {
		 		$scope.$apply(function(){
		 		// UPDATE OBJECT
		 		// Update: If action and current object are Objects
		 		if (current_object.constructor == Object && action.value.constructor == Object)
			 		for (var update_key in action.value)
			 			if (update_key in current_object)
			 				// Only copy over keys that exist in both action and current_object
			 				current_object[update_key] = action.value[update_key];
			 	else {
			 		// replace the entire value
			 		if (previous_object.constructor == Array) {
			 			// replace entire value in OBJECT
			 			previous_object[current_position] = action.value;
			 			
			 		} else if (previous_object.constructor == Object) {
			 			// replace entire value in OBJECT
			 			previous_object[current_key] = action.value;
			 		}
			 	}
			 	});
			 		
		 		
		 	} else if (action.type == "delete") {
		 		// DELETE OBJECT
		 		// delete current object from it's parent (previous object)
		 		$scope.$apply(function(){
		 			previous_object.splice(current_position, 1);
		 		});
		 	}
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
	 });
	 
	 // return true
	 return true;
 };
 
  
// ############# END QT FUNCTIONS #################### //   



// ############ DEBUG STUFFS ################## //

  // Debug method to add clips to the $scope
  $scope.addClips = function(numClips) {
        startNum = $scope.project.clips.length + 1;
        $.each(numClips, function() {
           $scope.project.clips.push({
              number: startNum.toString(),
              track : '4', 
              image : 'track1.png',
              locked : false,
              length : 10, //length in seconds
              duration : 10, //max length in seconds
              position : x*11,
            });
            startNum++;
        });
      
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
                    
  }

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