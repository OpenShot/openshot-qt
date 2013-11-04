
App.controller('TimelineCtrl', function($scope) {
  
  //clips json
  $scope.clips = [
    { 
      number : '1', 
      track : '1', 
      image : 'track1.png',
      locked : false,
    },
    {
      number : '2', 
      track : '2', 
      image : 'track2.png',
      locked : false,
    },
    {
      number : '3', 
      track : '3', 
      image : 'track3.png',
      locked : false,
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

});