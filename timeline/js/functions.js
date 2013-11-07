//finds an element with a particular value in the json data
function findElement(arr, propName, propValue) {

  for (var i=0; i < arr.length; i++)
    if (arr[i][propName] == propValue)
      return arr[i];

}



function secondsToTime(secs)
{
    var t = new Date(1970,0,1);
    t.setSeconds(secs);
    var s = t.toTimeString().substr(0,8);
    if(secs > 86399)
    	s = Math.floor((t - Date.parse("1/1/70")) / 3600000) + s.substr(2);
    return s;
}

function findTrackAtLocation(top){
	//default return value
	var retVal = -1;

	//loop all tracks
	$(".track").each(function() {
		var track = $(this);
	    track_top = track.position().top;
	    track_bottom = track_top + track.outerHeight(true);
    	if (top >= track_top && top <= track_bottom){
    		//found the track at this location
    		retVal = track.attr("id");
    	}
    });
    return retVal;
}