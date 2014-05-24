
//treats element as a track
//1: allows clips to be dropped
App.directive('tlTrack', function($timeout) {
    return {
        // A = attribute, E = Element, C = Class and M = HTML Comment
        restrict:'A',
        link: function(scope, element, attrs) {
        	
			scope.$watch('project.layers', function (val) {
                if (val) {
                	$timeout(function(){
				        // Update track indexes if tracks change
                		scope.UpdateLayerIndex();
                		console.log('update track indexes...');
                	}, 0);
                		
                }
            });

        	//make it accept drops
        	element.droppable({
		        accept: ".clip",
		       	drop:function(event,ui) {

		       		//with each dragged clip, find out which track they landed on
		       		$(".ui-selected").each(function() {
		       			var clip = $(this);
						
						if (clip.hasClass('ui-selected'))
			        		clip.removeClass('ui-selected');

		       			//get the clip properties we need
		       			clip_id = clip.attr("id");
						clip_num = clip_id.substr(clip_id.indexOf("_") + 1);
						clip_middle = clip.position().top + (clip.height() / 2); // find middle of clip
						clip_left = clip.position().left + scroll_left_pixels;

						//make sure the clip isn't dropped off too far to the left
						if (clip_left < 0) clip_left = 0;

		            	//get track the clip was dropped on 
		            	drop_track_id = findTrackAtLocation(parseInt(clip_middle));
		            	
		            	//if the droptrack was found, update the json
		            	if (drop_track_id != -1){ 
		            		//get track id from track.id
		            		drop_track_num = parseInt(drop_track_id.substr(drop_track_id.indexOf("_") + 1));
		            		
		            		//find the clip in the json data
		            		clip_data = findElement(scope.project.clips, "id", clip_num);

		            		//change the clip's track and position in the json data
		            		scope.$apply(function(){
		            			//set track
		            			clip_data.layer = drop_track_num;
		            			clip_data.position =  parseInt(clip_left)/scope.pixelsPerSecond;
		            			
								// update clip in Qt (very important =)
		            			if (scope.Qt)
		            				timeline.update_clip_data(JSON.stringify(clip_data));
							});

		            	}
		            });

		        }	
		    });
    	}    
    };
});