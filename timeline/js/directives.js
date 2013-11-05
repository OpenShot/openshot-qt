var dragging = false;
var previous_drag_position = null;


//finds an element with a particular value in the json data
function findElement(arr, propName, propValue) {

  for (var i=0; i < arr.length; i++)
    if (arr[i][propName] == propValue)
      return arr[i];

}

function findTrackAtLocation(top, left){
	//get all tracks
	tracks = $(".track");
	for (x=0;x<=tracks.length-1;x++){
    	track = tracks[x];
    	track_rect = track.getBoundingClientRect();
    	console.log("looking for top: " + top);
    	console.log("tracktop: " + track_rect.top);
    	console.log("trackbottom: " + track_rect.bottom);
    	if (top <= track_rect.top && top >= track_rect.bottom){
    		return track;
    	}
    }
    return null;
}


//holds the data index of an element
App.directive('tlIndex', function () {
        return {
             link:function (scope, elm, attrs) {}
     };
}); 


//treats element as a track
//1: allows clips to be dropped
App.directive('tlTrack', function() {
    return {
        // A = attribute, E = Element, C = Class and M = HTML Comment
        restrict:'A',
        link: function(scope, element, attrs) {

        	//make it accept drops
        	element.droppable({
		        accept: ".clip",
		       	drop:function(event,ui) {
		       		//handle all dragged clips
		       		all_dragged =  $(".ui-selected");
		       		for (x=0;x<=all_dragged.length-1;x++){
		            	clip = angular.element(all_dragged[x]);
		            	clip_top = clip.css("top");
		            	clip_left = clip.css("left");
		            	drop_track = findTrackAtLocation(parseInt(clip_top));
		            	console.log(drop_track);
		            }

		        	//dragged = angular.element(ui.draggable);
		        	//console.log(dragged);
		        	//dropped = angular.element(this);
		        	// Move clip to new track parent
					//clip_id = dragged.attr("id");
					//clip_num = clip_id.substr(clip_id.indexOf("_") + 1);
					//elm = findElement(scope.clips, "number", clip_num);
					//scope.$apply(function(){
			        //   elm.track = attrs.tlIndex;
			      	//});
	
		        }	
		    });
    	}    
    }
});



//treats element as a clip
//1: can be dragged
//2: can be resized
//3: class change when hovered over
App.directive('tlClip', function(){
	return {
		link: function(scope, element, attrs){
			
			//handle hover over on the clip
			element.hover(
	  			function () {
				  	if (!dragging)
				  	{
					  	$(this).addClass( "highlight_clip", 400, "easeInOutCubic" );
				  	}
			  	},
			  	function () {
				  	if (!dragging)
				  	{
					  	$(this).removeClass( "highlight_clip", 400, "easeInOutCubic" );
					}
			  	}
			);
			
			//handle resizability of clip
			element.resizable({ handles: "e, w",
				start: function(e, ui) {
					dragging = true;
				},
				stop: function(e, ui) {
					dragging = false;
				}
			});

			//handle draggability of clip
			element.draggable({
		        revert: true, //reverts back to original place if not dropped
		        snap: ".track", // snaps to a track
		        snapMode: "inner", 
		        snapTolerance: 40, 
		        stack: ".clip", 
		        start: function(event, ui) {
		        	dragging = true;
		        },
                stop: function(event, ui) {
                	// Clear previous drag position
					previous_drag_position = null;
					dragging = false;
				},
                drag: function(e, ui) {
					// Determine the amount moved since the previous event
					var previous_x = ui.originalPosition.left;
					var previous_y = ui.originalPosition.top;
					if (previous_drag_position)
					{
						// if available, override with previous drag position
						previous_x = previous_drag_position.left;
						previous_y = previous_drag_position.top;
					}
					// set previous position (for next time round)
					previous_drag_position = ui.position;

		        	// Calculate amount to move clips
		        	var x_offset = ui.position.left - previous_x;
		        	var y_offset = ui.position.top - previous_y;

					// Move all other selected clips with this one
		            $(".ui-selected").not($(this)).each(function(){
		            	var pos = $(this).position();
				        $(this).css('left', pos.left + x_offset);
				        $(this).css('top', pos.top + y_offset);
				    });
		        },
		      });


		}
	}
});



App.directive('tlMultiSelectable', function(){
	return {
		link: function(scope, element, attrs){
			element.selectable({
				filter: '.clip',
			});
		}
	}
});


App.directive('tlScrollableTracks', [function () {
	return {
		restrict: 'A',
		
		link: function (scope, element, attrs) {
			element.on('scroll', function () {
				$('#track_controls').scrollTop(element.scrollTop());
				$('#scrolling_ruler').scrollLeft(element.scrollLeft());
			});
		}
	};
}])


App.directive('tlTrackControls', [function () {
	return {
		link: function (scope, element, attrs) {
			
		}
	};
}])
