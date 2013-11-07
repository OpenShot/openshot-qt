
App.controller('TimelineCtrl', function($scope,$timeout) {


  $scope.project =
    {
      length : 600, //length of project in seconds
      scale : 16.0, //seconds per tick
      tick_pixels : 100, //pixels between tick mark
      play_head_position : 0.0 //position of play head
    };
  

  $scope.pixelsPerSecond =  parseFloat($scope.project.tick_pixels) / parseFloat($scope.project.scale);
  
  //clips json
  $scope.clips = [
    { 
      number : '1', 
      track : '1', 
      image : 'track1.png',
      locked : false,
      length : 32, //length in seconds
      position : 0.0,
    },
    {
      number : '2', 
      track : '2', 
      image : 'track2.png',
      locked : false,
      length : 45,
      position : 0.0,
    },
    {
      number : '3', 
      track : '3', 
      image : 'track3.png',
      locked : false,
      length : 120,
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


  //DEBUG STUFFS

  $scope.addClips = function(numClips) {
        startNum = $scope.clips.length + 1;
        for (x=1; x<=numClips; x++){
            $scope.clips.push({
              number: startNum.toString(),
              track : '4', 
              image : 'track1.png',
              locked : false,
          });
            startNum++;
        }
        
        $scope.numClips = "";

    };

$scope.scaleVal = $scope.project.scale;
  $scope.scaleChange = function() {
    console.log($scope.scaleVal);
    $scope.project.scale = parseFloat($scope.scaleVal);
  };


});