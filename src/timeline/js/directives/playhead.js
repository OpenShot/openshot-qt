
// Handles the playhead dragging 
var playhead_y_max = null;
var playhead_x_min = null;

App.directive('tlPlayhead', function(){
	return {
		link: function(scope, element, attrs) {
			// get the default top position so we can lock it in place vertically
			playhead_y_max = element.position().top;

			// get the size of the playhead and line so we can determine the offset 
			var playhead_top_w = parseInt($(".playhead-top").css("width")) - 8.0; // I'm not sure why I need to remove another 8 pixels here
			scope.playheadOffset = 0.0 - (playhead_top_w / 2.0);

			//set as draggable
			element.draggable({
				//containment:'#scrolling_ruler',
		        scroll: false,
		        
		        start: function(event, ui) {
		        	
		        },
	            stop: function(event, ui) {
	            	
				},
	            drag: function(e, ui) {
	            	//force playhead to stay where it's supposed to
	             	ui.position.top = playhead_y_max;
	             	if (ui.position.left < scope.playheadOffset) ui.position.left = scope.playheadOffset;

	             	//update the playhead position in the json data
	             	scope.$apply(function(){
	             		//set position of playhead
	             		playhead_seconds = (ui.position.left - scope.playheadOffset) / scope.pixelsPerSecond;
	             		scope.project.playhead_position = playhead_seconds;
	             		scope.playheadTime = secondsToTime(playhead_seconds);
	             	});


		        },
		    });
		}
	};
});


