var dragging = false;
var previous_drag_position = null;
var clip_tops = {};
var clip_lefts = {};
//variables for panning by middle click
var is_scrolling = false;
var starting_scrollbar = { x: 0, y: 0 };
var starting_mouse_position = { x: 0, y: 0 };



//treats element as a track
//1: allows clips to be dropped
App.directive('tlTrack', function($timeout) {
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
						
						if (clip.hasClass('ui-selected')){
			        		clip.removeClass('ui-selected');
			        	}
			        	
		       			//get the clip properties we need
		       			clip_id = clip.attr("id");
						clip_num = clip_id.substr(clip_id.indexOf("_") + 1);
						clip_top = clip.position().top;
						clip_left = clip.position().left;

		            	//get track the clip was dropped on 
		            	drop_track_id = findTrackAtLocation(parseInt(clip_top));
		            	
		            	//if the droptrack was found, update the json
		            	if (drop_track_id != -1){ 
		            		//get track number from track.id
		            		drop_track_num = drop_track_id.substr(drop_track_id.indexOf("_") + 1);
		            		
		            		//find the clip in the json data
		            		elm = findElement(scope.clips, "number", clip_num);
		            		
		            		clip_tops[clip_id] = clip.position().top;
							clip_lefts[clip_id] = clip.position().left;	

		            		//change the clip's track and position in the json data
		            		scope.$apply(function(){
		            			//set track
		            			elm.track = drop_track_num;
		            			elm.position =  parseInt(clip_left)/scope.pixelsPerSecond;
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

App.directive('tlClip', function($timeout){
	return {
		scope: "@",
		link: function(scope, element, attrs){
			$timeout(function(){
				clip_tops["clip_"+scope.clip.number] = element.position().top;
				clip_lefts["clip_"+scope.clip.number] = element.position().left;
				
			},0);

			//handle resizability of clip
			element.resizable({ 
				handles: "e, w",
				maxWidth: scope.clip.duration * scope.pixelsPerSecond,
				start: function(e, ui) {
					dragging = true;

				},
				stop: function(e, ui) {
					dragging = false;
					//determine resize deltas
					var delta_x = ui.size.width - ui.originalSize.width;
					console.log(delta_x);
					var dir = '';
					if (delta_x > 0) { 
				        dir += 'e';
				    } else if (delta_x < 0) { 
				        dir += 'w';
				    }
				    console.log(dir); 
				    console.log($(this).axis);
					scope.$apply(function(){
						//scope.playlineLocation = line_loc;
					});

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
		        //revert: true, //reverts back to original place if not dropped
		        snap: ".track", // snaps to a track
		        snapMode: "inner", 
		        snapTolerance: 40, 
		        stack: ".clip", 
		        containment:'#scrolling_tracks',
		        scroll: false,
		        revert: 'invalid',
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

	            	//update the dragged clip location in the location arrays
					clip_tops[element.attr('id')] = ui.position.top;
					clip_lefts[element.attr('id')] = ui.position.left;

					// Move all other selected clips with this one
	                $(".ui-selected").not($(this)).each(function(){
	                	var pos = $(this).position();
	                	var newY = clip_tops[$(this).attr('id')] + y_offset;
	                	var newX = clip_lefts[$(this).attr('id')] + x_offset;
	                	
	                	//update the clip location in the array
	                	clip_tops[$(this).attr('id')] = newY;
						clip_lefts[$(this).attr('id')] = newX;
						
						//change the element location
						$(this).css('left', newX);
				    	$(this).css('top', newY)
				    	
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



// This container allows for tracks to be scrolled (with synced ruler)
// and allows for panning of the timeline with the middle mouse button
App.directive('tlScrollableTracks', function () {
	return {
		restrict: 'A',
		
		link: function (scope, element, attrs) {
			
			//sync ruler to track scrolling
			element.on('scroll', function () {
				$('#track_controls').scrollTop(element.scrollTop());
				$('#scrolling_ruler').scrollLeft(element.scrollLeft());
				$('#progress_container').scrollLeft(element.scrollLeft());
				
				//set new playline location
				var line_loc = $(".playhead-top").offset().left + scope.playheadOffset;

				//make sure the playhead line stays with the playhead top
				scope.$apply(function(){
					scope.playlineLocation = line_loc;

				});
			});

			//handle panning when middle mouse is clicked
			element.on('mousedown', function(e) {
				if (e.which == 2) { // middle button
					is_scrolling = true;
					starting_scrollbar = { x: element.scrollLeft(), y: element.scrollTop() }
					starting_mouse_position = { x: e.pageX, y: e.pageY }
				}
				return true;
			});

			//pans the timeline on move
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

//the body of the app. allows for capture of released middle mouse button
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




//The HTML5 canvas ruler
App.directive('tlRuler', function ($timeout) {
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

			//watch the scale value so it will be able to draw the ruler after changes,
			//otherwise the canvas is just reset to blank
			scope.$watch('project.scale + markers', function (val) {
                if (val){
                	
	            	 $timeout(function(){
						//get all scope variables we need for the ruler
						var scale = scope.project.scale;
						var tick_pixels = scope.project.tick_pixels;
						var each_tick = tick_pixels / 2;
						var pixel_length = scope.project.length * scope.pixelsPerSecond;

				    	//draw the ruler
				    	var ctx = element[0].getContext('2d');
				    	//clear the canvas first
				    	ctx.clearRect(0, 0, element.width, element.height);
				    	//set number of ticks based 2 for each pixel_length
				    	num_ticks = pixel_length / 50;

				    	//loop em and draw em
						for (x=0;x<num_ticks+1;x++){
							ctx.lineWidth = 2;
							ctx.beginPath();

							//if it's even, make the line longer
							if (x%2 == 0){ 
								line_top = 18;
								//if it's not the first line, set the time text
								if (x != 0){
									//get time for this tick
									time = (scale * x) /2;
									time_text = secondsToTime(time)

									//write time on the canvas, centered above long tick
									ctx.fillStyle = "#fff";
									ctx.font = "bold 10px Arial";
									ctx.fillText(time_text, x*each_tick-22, 10);	
								}
							} else { 
								//shorter line
								line_top = 28;
							}
							
							ctx.moveTo(x*each_tick, 39);
							ctx.lineTo(x*each_tick, line_top);
							ctx.strokeStyle = "#fff";
							ctx.stroke();
						}

						//marker images
						$.each(scope.markers, function() {
							
							var img = new Image();
							img.src = "media/images/markers/"+this.icon;
							var img_loc = this.location * scope.pixelsPerSecond;
							img.onload = function() {
								ctx.drawImage(img, img_loc-img.width/2, 25);
							};
							
						});
						
				    }, 0);   

                }
            });

		}

		

	};
})


// Handles the HTML5 canvas progress bar
App.directive('tlProgress', function($timeout){
	return {
		link: function(scope, element, attrs){
			scope.$watch('progress + project.scale', function (val) {
                if (val) {
                	$timeout(function(){
				        var progress = scope.progress;
						for(p=0;p<progress.length;p++){
							
							//get the progress item details
							var start_second = progress[p][0];
							var stop_second = progress[p][1];
							var status = progress[p][2];
							
							//figure out the actual pixel position
							var start_pixel = start_second * scope.pixelsPerSecond;
							var stop_pixel = stop_second * scope.pixelsPerSecond;
							var rect_length = stop_pixel - start_pixel;
							
							//get the element and draw the rects
							var ctx = element[0].getContext('2d');
							ctx.beginPath();
						    ctx.rect(start_pixel, 0, rect_length, 5);
						   	//change style based on status
						   	if (status == 'complete'){
								ctx.fillStyle = 'green';
							}else{
								ctx.fillStyle = 'yellow'
							}
						   	ctx.fill();
						}
                	}, 0);
                		
                }
            });

			
		}
	}
});


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


App.directive('tlBackImg', function(){
    return {
    	link: function(scope, element, attrs){
	        var url = attrs.tlBackImg;
	        element.css({
	            'background-image': 'url(' + url +')',
	            'background-size' : 'cover'
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
});