
App.controller('TimelineCtrl',function($scope,$timeout) {



  $scope.project =
    {
      duration : 600, //length of project in seconds
      scale : 16.0, //seconds per tick
      tick_pixels : 100, //pixels between tick mark
      playhead_position : 123, //position of play head
      
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
	                 effects : [
	                           { effect : 'Old Movie',icon : 'om.png'},
	                           { effect : 'Blur', icon: 'blur.png'},
	                           { effect : 'Cartoon', icon: 'cartoon.png'}
	                           ],
	                 images : { start: 5, end: 10 },
	                 show_audio : true,
	                 audio_data : [.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3, ]
	                 //audio_data : [.0,.0,.1,.3,.5],
	               },
             ],
             
     layers : [
	               {number:4},
	               {number:3},
	               {number:2},               
	               {number:1},
	               {number:0}, 
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
  
 // Apply JSON diff from UpdateManager (this is how the user interface communicates changes
 // to the timeline. A change can be an insert, update, or delete. The change is passed in
 // as JSON, which represents the change.
 $scope.ApplyJsonDiff = function(jsonDiff){
	 
	 // Loop through each UpdateAction
	 for (action_number = 0; action_number < jsonDiff.length; action_number++) {
	 	
		 // Get the UpdateAction
		 var action = jsonDiff[action_number];
		 
		 // Iterate through the key levels (looking for a matching element in the $scope.project)
		 previous_object = null;
		 current_object = $scope.project;
		 for(var key_value in action.key) {

		 	// Check the key type
		 	if (key_value.constructor == String) {
		 		// Does the key value exist in scope
		 		if (key_value in current_object) {
		 			// Found a match, so set current level and previous level
		 			previous_object = current_object;
		 			current_object = current_object[key_value];
		 		}
		 		
		 	} else if (key_value.constructor == Object) {
		 		// Get the id from the object (if any)
		 		var id = null;
		 		if ("id" in key_value)
		 			id = key_value["id"];
		 			
		 		// Be sure the current_object is an Array
		 		if (current_object.constructor == Array) {
			 		// Filter the current_object for a specific id
			 		for(var child_object in current_object) {
	
			 		}
		 		}
		 	}
		 	
		 	
		 	
		 }
	 }
 };
 
 // Apply the an UpdateAction to a clip
 $scope.apply_json_to_clips = function(action) {
	 
	 // Find the object in the scope (if any)
	 var scope_object = null;
	 var scope_position = 0;
	 if (action.key.length > 1) {
		 // Get the id
		 var action_clip_id = action.key[1]['id'];
		 
		 // Loop through each clip (and find matching id)
		 for (z = 0; z < $scope.project.clips.length; z++) {
			 // Get clip
			 var clip = $scope.project.clips[z];
			 
			 // See if ids match
			 if (clip.id == action_clip_id) {
				 // Found a match, break loop
				 scope_object = clip;
				 scope_position = z;
				 break;
			 }
		 }
	 }
	 
	 switch (action.type) {
	 case "insert":
		 // Insert new clip
		 $scope.$apply(function(){
			 $scope.project.clips.push(action.value);
		 });
		 break;
		 
	 case "update":
		 // Update clip
		 $scope.$apply(function(){
			 // update matching properties
			 if (action.value.layer !== 'undefined')
				 scope_object.layer = action.value.layer;
			 if (action.value.position !== 'undefined')
				 scope_object.position = action.value.position;
			 if (action.value.start !== 'undefined')
				 scope_object.start = action.value.start;
			 if (action.value.end !== 'undefined')
				 scope_object.end = action.value.end;
			 if (action.value.duration !== 'undefined')
				 scope_object.duration = action.value.duration;
			 if (action.value.volume !== 'undefined')
				 scope_object.volume = action.value.volume;
			 if (action.value.reader !== 'undefined')
				 scope_object.reader = action.value.reader;
		 });
		 break;
		 
	 case "delete":
		 // Delete clip
		 $scope.$apply(function(){
			 $scope.project.clips.splice(scope_position, 1);
		 });
		 break;
	 }
	 
	 
 }
  
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