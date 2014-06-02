
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
		        accept: ".droppable",
		       	drop:function(event,ui) {

		       		//with each dragged clip, find out which track they landed on
		       		$(".ui-selected").each(function() {
		       			var item = $(this);
						
		       			// Remove selected class
						if (item.hasClass('ui-selected'))
							item.removeClass('ui-selected');
						
						// Determine type of item
						item_type = null;
						if (item.hasClass('clip'))
							item_type = 'clip';
						else if(item.hasClass('transition'))
							item_type = 'transition';
						else
							// Unknown drop type
							return;

		       			// get the item properties we need
		       			item_id = item.attr("id");
		       			item_num = item_id.substr(item_id.indexOf("_") + 1);
		       			item_middle = item.position().top + (item.height() / 2); // find middle of clip
		       			item_left = item.position().left + scroll_left_pixels;

						// make sure the item isn't dropped off too far to the left
						if (item_left < 0) item_left = 0;

		            	// get track the item was dropped on 
						drop_track_num = findTrackAtLocation(parseInt(item_middle));
		            	
		            	// if the droptrack was found, update the json
		            	if (drop_track_num != -1){ 

		            		// find the item in the json data
		            		item_data = null;
		            		if (item_type == 'clip')
		            			item_data = findElement(scope.project.clips, "id", item_num);
		            		else if (item_type == 'transition')
		            			item_data = findElement(scope.project.transitions, "id", item_num);

		            		// change the clip's track and position in the json data
		            		scope.$apply(function(){
		            			//set track
		            			item_data.layer = drop_track_num;
		            			item_data.position =  parseInt(item_left)/scope.pixelsPerSecond;
		            			
								// update clip in Qt (very important =)
		            			if (scope.Qt && item_type == 'clip')
		            				timeline.update_clip_data(JSON.stringify(item_data));
		            			else if (scope.Qt && item_type == 'transition')
		            				timeline.update_transition_data(JSON.stringify(item_data));
							});

		            	}
		            });

		        }	
		    });
    	}    
    };
});