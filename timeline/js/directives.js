var dragging = false;
var previous_drag_position = null;

//variables for panning by middle click
var is_scrolling = false;
var starting_scrollbar = { x: 0, y: 0 };
var starting_mouse_position = { x: 0, y: 0 };



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
		       		//with each dragged clip, find out which track they landed on
		       		$(".ui-selected").each(function() {
		       			var clip = $(this);
						
						//remove selected class
						if (element.hasClass('ui-selected')){
			        		element.removeClass('ui-selected');
			        	}
			        	
		       			//get the clip properties we need
		       			clip_id = clip.attr("id");
						clip_num = clip_id.substr(clip_id.indexOf("_") + 1);
		            	clip_top = clip.css("top");
		            	clip_left = clip.css("left");
		            	
		            	//get track the clip was dropped on 
		            	drop_track_id = findTrackAtLocation(parseInt(clip_top));
		            	
		            	//if the droptrack was found, update the json
		            	if (drop_track_id != -1){ 
		            		//get track number from track.id
		            		drop_track_num = drop_track_id.substr(drop_track_id.indexOf("_") + 1);
		            		
		            		//find the clip in the json data
		            		elm = findElement(scope.clips, "number", clip_num);
		            		
		            		//change the clip's track in the json data
		            		scope.$apply(function(){
		            			elm.track = drop_track_num;
		            		});
		            	}
		            	
		            });

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
		scope: "@",
		link: function(scope, element, attrs){
			
			//handle resizability of clip
			element.resizable({ 
				handles: "e, w",
				maxWidth: scope.clip.duration * scope.pixelsPerSecond,
				start: function(e, ui) {
					dragging = true;
				},
				stop: function(e, ui) {
					dragging = false;
				},
				
			});
	
			//handle hover over on the clip
			element.hover(
	  			function () {
				  	if (!dragging)
				  	{
					  	element.addClass( "highlight_clip", 400, "easeInOutCubic" );
				  	}
			  	},
			  	function () {
				  	if (!dragging)
				  	{
					  	element.removeClass( "highlight_clip", 400, "easeInOutCubic" );
					}
			  	}
			);
			

			//handle draggability of clip
			element.draggable({
		        revert: true, //reverts back to original place if not dropped
		        snap: ".track", // snaps to a track
		        snapMode: "inner", 
		        snapTolerance: 40, 
		        stack: ".clip", 
		        start: function(event, ui) {
		        	dragging = true;
		        	if (!element.hasClass('ui-selected')){
		        		element.addClass('ui-selected');
		        	}
		        	
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


App.directive('tlScrollableTracks', function () {
	return {
		restrict: 'A',
		
		link: function (scope, element, attrs) {
			

			element.on('scroll', function () {
				$('#track_controls').scrollTop(element.scrollTop());
				$('#scrolling_ruler').scrollLeft(element.scrollLeft());
			});

			element.on('mousedown', function(e) {
				if (e.which == 2) { // middle button
					is_scrolling = true;
					starting_scrollbar = { x: element.scrollLeft(), y: element.scrollTop() }
					starting_mouse_position = { x: e.pageX, y: e.pageY }
				}
				return true;
			});

			element.on('mousemove', function(e){
				if (is_scrolling) {

					// Calculate difference from last position
					difference = { x: starting_mouse_position.x-e.pageX, y: starting_mouse_position.y-e.pageY}

					// Scroll the tracks div
					element.scrollLeft(starting_scrollbar.x + difference.x);
					element.scrollTop(starting_scrollbar.y + difference.y);
				}
				return true;
			});
			

		}
	};
})


App.directive('tlBody', function () {
	return {
		link: function (scope, element, attrs){

			element.on('mouseup', function(e){
				if (e.which == 2) // middle button
					is_scrolling = false;
				return true;
			});


		}
	};
});





App.directive('tlRuler', function ($timeout) {
	return {
		restrict: 'A',
		link: function (scope, element, attrs) {
			//use timeout to ensure that drawing on the canvas happens after the DOM is loaded
			scope.$watch('project.scale', function (val) {
                if (val){
                	 $timeout(function(){
						//get all scope variables we need for the ruler
						var scale = scope.project.scale;
						var tick_pixels = scope.project.tick_pixels;
						var each_tick = tick_pixels / 2;
						var pixel_length = scope.project.length * scope.pixelsPerSecond;


				    	//draw the ruler
				    	ctx = element[0].getContext('2d');
				    	num_ticks = pixel_length / 50;
						for (x=0;x<num_ticks+1;x++){
							ctx.lineWidth = 2;
							ctx.beginPath();
							if (x%2 == 0){
								line_top = 18;
								
								if (x != 0){
									//get time for this tick
									time = (scale * x) /2;

									time_text = secondsToTime(time)
									//write time
									ctx.fillStyle = "#fff";
									ctx.font = "bold 10px Arial";
									ctx.fillText(time_text, x*each_tick, 10);	
										
								}
								
							} else {
								line_top = 28;
							}
							
							ctx.moveTo(x*each_tick, 39);
							ctx.lineTo(x*each_tick, line_top);
							ctx.strokeStyle = "#fff";
							ctx.stroke();
							
						}
						
				    }, 0);   

                }
            });

		}
	};
})




// DEBUG STUFFS

App.directive('dbSlider', function () {
	return {
		restrict: 'A',
		link: function (scope, element, attrs) {
			element.slider({
			    value: 30,
			    step: 2,
			    min: 8,
			    max: 210,
			    slide: function(event, ui) {
			        $("#scaleVal").val(ui.value);
			        scope.$apply(function(){
			        	scope.project.scale = ui.value;
	            		scope.pixelsPerSecond =  parseFloat(scope.project.tick_pixels) / parseFloat(scope.project.scale);
	            	});

			    }
			});	
		}
	};
})