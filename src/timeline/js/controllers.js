
App.controller('TimelineCtrl',function($scope,$timeout) {

  $scope.project =
    {
      duration : 600, //length of project in seconds
      scale : 16.0, //seconds per tick
      tick_pixels : 100, //pixels between tick mark
      playhead_position : 123, //position of play head
      
      clips : [],
      clips_hide : [
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
	                 //audio_data : [.0,.0,.1,.3,.5],
	               },
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
  

  //tracked vars
  $scope.pixelsPerSecond =  parseFloat($scope.project.tick_pixels) / parseFloat($scope.project.scale);
  $scope.playheadOffset = 0;
  $scope.playheadTime =  secondsToTime($scope.project.playhead_position);
  $scope.playlineLocation = 0;
  $scope.Qt = true;
  $scope.EnableQt = function() { $scope.Qt = true; };
  
  //filters clips by layer
  $scope.filterByLayer = function (layer) {
      return function (item) {
          if (item.layer == layer.number){
            return true; //belongs on this layer 
          } else {
            return false; //does not belong on this layer
          }
      };
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
 
  // Show playhead context menu
 $scope.ShowPlayheadMenu = function(position) {
 	if ($scope.Qt) {
	 	timeline.qt_log("$scope.ShowPlayheadMenu");
	 	timeline.ShowPlayheadMenu(position);
	 }
 };
 
 // Move a new clip to the timeline
 $scope.MoveClip = function(x, y){
	 $scope.$apply(function(){
		 
		 // Convert x and y into timeline vars
		 var scrolling_tracks_offset_left = $("#scrolling_tracks").offset().left;
		 var scrolling_tracks_offset_top = $("#scrolling_tracks").offset().top;
		 var clip_position = parseFloat(x - scrolling_tracks_offset_left) / parseFloat($scope.pixelsPerSecond);
		 if (clip_position < 0)
			 clip_position = 0;
		 
		 // Update clip position & layer (based on x,y)
		 $scope.project.clips[$scope.project.clips.length - 1].position = clip_position;
		 $scope.project.clips[$scope.project.clips.length - 1].layer = $scope.GetTrackAtY(y - scrolling_tracks_offset_top).number;

		 // hide and show elements of the clip (based on size)
		 handleVisibleClipElements($scope, $scope.project.clips[$scope.project.clips.length - 1].id);
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
  
 // Find a track at a given y coordinate (if any)
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


$scope.addEffect = function(clipNum){
    //find the clip in the json data
    elm = findElement($scope.project.clips, "number", clipNum);
    elm.effects.push({
       effect : 'Old Movie',
       icon : 'om.png'
    });
    $scope.clipNum = "";
                    
}

  $scope.addMarker = function(markLoc){
        $scope.project.markers.push({
          location: parseInt(markLoc),
          icon: 'blue.png'
        });
        $scope.markLoc = "";
  };


  $scope.changeImage = function(startImage){
      console.log(startImage);
        $scope.project.clips[2].images.start=startImage;
        $scope.startImage = "";
  };

});