
App.controller('TimelineCtrl', function($scope,$timeout) {


  $scope.project =
    {
      length : 600, //length of project in seconds
      scale : 16.0, //seconds per tick
      tick_pixels : 100, //pixels between tick mark
      playhead_position : 123 //position of play head
    };
  

  $scope.progress = [
  
    [0, 30, 'rendering'],
    [40, 50, 'complete'],
    [100, 150, 'complete'],

  ];

   //clips json
  $scope.clips = [
    { 
      number : '1', 
      track : '1', 
      image : 'track1.png',
      locked : false,
      length : 32, //length in seconds
      duration : 32, //max length in seconds
      position : 0.0,
    },
    {
      number : '2', 
      track : '2', 
      image : 'track2.png',
      locked : false,
      length : 45,
      duration : 45,
      position : 0.0,
    },
    {
      number : '3', 
      track : '3', 
      image : 'track3.png',
      locked : false,
      length : 120,
      duration : 120,
      position : 32.0,
    },
  ];

  //tracks json
  $scope.tracks = [
    {number:'1'}, 
    {number:'2'},
    {number:'3'},
    {number:'4'},
    {number:'5'},
  ];

  

   $scope.pixelsPerSecond =  parseFloat($scope.project.tick_pixels) / parseFloat($scope.project.scale);
   $scope.playheadOffset = 0;
   $scope.playheadTime =  secondsToTime($scope.project.playhead_position);
   $scope.playlineLocation = 0;

  //filters clips by track
  $scope.filterByTrack = function (track) {
      return function (item) {
          if (item.track == track.number){
            return true; //belongs on this track 
          } else {
            return false; //does not belong on this track
          }
      };
  };



// ############# QT FUNCTIONS #################### //

//changes the scale resets the view
$scope.setScale = function(scaleVal){
      $scope.$apply(function(){
         $scope.project.scale = scaleVal;
         $scope.pixelsPerSecond =  parseFloat($scope.project.tick_pixels) / parseFloat($scope.project.scale);
     });
  };
// ############# END QT FUNCTIONS #################### //   



// ############ DEBUG STUFFS ################## //

  $scope.addClips = function(numClips) {
        startNum = $scope.clips.length + 1;
        for (x=1; x<=numClips; x++){
            $scope.clips.push({
              number: startNum.toString(),
              track : '4', 
              image : 'track1.png',
              locked : false,
              length : 10, //length in seconds
              duration : 10, //max length in seconds
              position : x*11,
          });
            startNum++;
        }
        

        $scope.numClips = "";

    };




});