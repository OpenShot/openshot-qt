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
    
    //if the clip was dropped above the top track, return -1
   

    var track_count = $('.track').length;

    
	//loop all tracks
	$(".track").each(function(index, element) {
        var track = $(this);
	    
        //if clip top is less than 0, then set it to the first track
        if (index == 0 && top < 0) {
            retVal = track.attr("id");
        }else{
            //otherwise, find the correct track
            track_top = track.position().top;
    	    track_bottom = track_top + track.outerHeight(true);
            if (top >= track_top && top <= track_bottom){
        		//found the track at this location
        		retVal = track.attr("id");
        	}
        }

        //if this is the last and no track was found, return the last track
        if (index == track_count - 1 && retVal == -1) {
            retVal = track.attr("id");
        }
    });

    return retVal;
}