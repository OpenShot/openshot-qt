
App.controller('TimelineCtrl',function($scope,$timeout) {



  $scope.project =
    {
      duration : 600, //length of project in seconds
      scale : 16.0, //seconds per tick
      tick_pixels : 100, //pixels between tick mark
      playhead_position : 123, //position of play head
      
      clips : [
	               { 
	                 number : '1', 
	                 layer : '1', 
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
	                 number : '2', 
	                 layer : '2', 
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
	                 number : '3', 
	                 layer : '3', 
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
	               {number:'4'},
	               {number:'3'},
	               {number:'2'},               
	               {number:'1'},
	               {number:'0'}, 
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
     
	 
	 
	 $scope.$apply(function(){
         $scope.project.scale = scaleVal;
         $scope.pixelsPerSecond =  parseFloat($scope.project.tick_pixels) / parseFloat($scope.project.scale);
     });
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