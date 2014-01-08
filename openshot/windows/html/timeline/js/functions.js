//finds an element with a particular value in the json data
function findElement(arr, propName, propValue) {

  for (var i=0; i < arr.length; i++)
    if (arr[i][propName] == propValue)
      return arr[i];

}


function handleVisibleClipElements(scope, clip_number){

    //get the clip in the scope
    clip = findElement(scope.clips, "number", clip_number);
    element = $("#clip_"+clip_number);

    //check clip width to determine which elements can be shown
    var clip_width = element.width();
    var thumb_width = $(".thumb").outerWidth(true);
    var effects_width = element.find(".clip_effects").outerWidth(true); 
    var label_width = element.find(".clip_label").outerWidth(true);
    var menu_width = element.find(".clip_menu").outerWidth(true);   
    
    //set min widths
    var min_for_thumb_end = thumb_width * 2;
    var min_for_thumb_start = thumb_width;
    var min_for_menu = menu_width;
    var min_for_effects = menu_width + effects_width;
    var min_for_label = menu_width + effects_width + label_width;


    //show the images as audio is not shown
    if (!clip.show_audio){
        //show end clip?
        (clip_width <= min_for_thumb_end) ? element.find(".thumb-end").hide() : element.find(".thumb-end").show();
        
        //show start clip?
        (clip_width <= min_for_thumb_start) ? element.find(".thumb-start").hide() : element.find(".thumb-start").show();
        console.log("W: " + clip_width  + " --- CLIP" + clip.number + " : " + min_for_thumb_start);
        
    }

    //show label?
    (clip_width <= min_for_label) ? element.find(".clip_label").hide() : element.find(".clip_label").show();
    
    //show effects?
    (clip_width <= min_for_effects) ? element.find(".clip_effects").hide() : element.find(".clip_effects").show();

    //show menu?
    (clip_width <= min_for_menu) ? element.find(".clip_menu").hide() : element.find(".clip_menu").show();

    element.find(".clip_top").show();
    element.find(".thumb-container").show();
}

//draws the audio wave on a clip
function drawAudio(scope, clip_number){
    //get the clip in the scope
    clip = findElement(scope.clips, "number", clip_number);
    
    if (clip.show_audio){
        element = $("#clip_"+clip_number);

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
        for (var i = 0; i < clip.audio_data.length; i++) {
            //increase the 'x' axis draw point
            line_spot += 1;
            ctx.beginPath();
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(line_spot, mid_point);
            var audio_point = clip.audio_data[i];
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




