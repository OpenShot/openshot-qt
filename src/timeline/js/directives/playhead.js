
// Handles the playhead dragging 
var playhead_y_max = null;
var playhead_x_min = null;

App.directive('tlPlayhead', function(){
	return {
		link: function(scope, element, attrs) {
			//get the default top position so we can lock it in place vertically
			playhead_y_max = element.position().top;

			//get the size of the playhead and line so we can determine the offset 
			//value which will put the line on the zero
			var playhead_top_w = parseInt($(".playhead-top").css("width"));
			var playhead_line_w = parseInt($(".playhead-line").css("width"));
			var playhead_0_offset = 0 - ((playhead_top_w/2) - (playhead_line_w/2));
			
			//with the offset, get the mininum left (x) the playhead can slide
			playhead_x_min = playhead_0_offset;
			//set it in the scope for future reference
			scope.playheadOffset = playhead_0_offset;

			//set as draggable
			element.draggable({
				containment:'#scrolling_ruler',
		        scroll: false,
		        
		        start: function(event, ui) {
		        	
		        },
	            stop: function(event, ui) {
	            	
				},
	            drag: function(e, ui) {
	            	//force playhead to stay where it's supposed to
	             	ui.position.top = playhead_y_max;
	             	if (ui.position.left < playhead_x_min) ui.position.left = playhead_x_min;
	             	
	             	//update the playhead position in the json data
	             	scope.$apply(function(){
	             		//set position of playhead
	             		playhead_seconds = (ui.position.left - scope.playheadOffset) / scope.pixelsPerSecond;
	             		scope.project.playhead_position = playhead_seconds;
	             		scope.playheadTime = secondsToTime(playhead_seconds);
	             		scope.playlineLocation = ui.offset.left + scope.playheadOffset;
	             	});


		        },
		    });
		}
	};
});



App.directive('tlPlayline', function($timeout){
	return {

		link: function(scope, element, attrs) {
			//set the playhead line to the top
			var playhead_top_h = parseInt($(".playhead-top").css("height"));
			var bottom_of_playhead = $(".playhead-top").offset().top + playhead_top_h;
			element.css('top', bottom_of_playhead);

			//set playline initial spot
			$timeout(function(){
				scope.playlineLocation = $(".playhead-top").offset().left - scope.playheadOffset;
			}, 0);

			//watch playlineLocation and the project scale to move the line as needed
			scope.$watch('playlineLocation + project.scale', function (val) {
                if (val) {
                	$timeout(function(){
	                	//now set it in the correct "left" position, under the playhead top
						var playline_left = $(".playhead-top").offset().left - scope.playheadOffset;
						element.css('left', playline_left);
                		
                		if (playline_left < $('#scrolling_ruler').position().left){
							//hide the line
							element.hide();
						}else{
							//show the line
							element.show();
						}

                	}, 0);
                		
                }
            });

		}
	};
});


//The HTML5 canvas ruler
App.directive('tlPlayheadbox', function ($timeout) {
	return {
		restrict: 'A',
		link: function (scope, element, attrs) {
			//on click of the ruler canvas, jump playhead to the clicked spot
			element.on('mousedown', function(e){
				var playhead_seconds = (e.pageX - element.offset().left) / scope.pixelsPerSecond;
				scope.$apply(function(){
					scope.project.playhead_position = playhead_seconds;
					scope.playheadTime = secondsToTime(playhead_seconds);
					//use timeout to ensure that the playhead has moved before setting the line location off of it
					$timeout(function(){
						scope.playlineLocation = $(".playhead-top").offset().left + scope.playheadOffset;
					},0);
				});
			});
			
			element.on('mousemove', function(e){
				if (e.which == 1) { // left button
					var playhead_seconds = (e.pageX - element.offset().left) / scope.pixelsPerSecond;
					scope.$apply(function(){
						scope.project.playhead_position = playhead_seconds;
						scope.playheadTime = secondsToTime(playhead_seconds);
						//use timeout to ensure that the playhead has moved before setting the line location off of it
						$timeout(function(){
							scope.playlineLocation = $(".playhead-top").offset().left + scope.playheadOffset;
						},0);
					});
				}
			});
		}
	};
});