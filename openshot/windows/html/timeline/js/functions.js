//finds an element with a particular value in the json data
function findElement(arr, propName, propValue) {

  for (var i=0; i < arr.length; i++)
    if (arr[i][propName] == propValue)
      return arr[i];

}


//draws the audio wave on a clip
function drawAudio(scope, element){
    //show audio container
    element.find(".audio-container").show();
    
    //draw audio
    var audio_canvas = element.find(".audio");
    var ctx = audio_canvas[0].getContext('2d');
    //set the midpoint
    var mid_point = parseInt(audio_canvas.css("height")) / 2;
    var line_spot = 0;
    
    //draw midpoint line
    ctx.beginPath();
    ctx.lineWidth = .5;
    ctx.beginPath();
    ctx.moveTo(0, mid_point);
    ctx.lineTo(parseInt(audio_canvas.css("width")), mid_point);
    ctx.strokeStyle = "#fff";
    ctx.stroke();

    //for each point of audio data, draw a line
    for (var i = 0; i < scope.clip.audio_data.length; i++) {
        //increase the 'x' axis draw point
        line_spot += 1;
        ctx.beginPath();
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(line_spot, mid_point);
        var audio_point = scope.clip.audio_data[i];
        //set the point to draw to
        var draw_to = (audio_point * mid_point);
        //handle the 'draw to' point based on positive or negative audio point
        if (audio_point >= 0) draw_to = mid_point - draw_to;
        if (audio_point < 0) draw_to = mid_point + (draw_to * -1);
        //draw it
        ctx.lineTo(line_spot, draw_to);
        ctx.strokeStyle = "#FF6E97";
        ctx.stroke();
    }
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




