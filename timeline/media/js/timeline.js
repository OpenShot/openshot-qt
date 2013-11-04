$(document).ready(function() {

	
	// Sync scrollbars
	$('#scrolling_tracks').on('scroll', function () {
    	$('#track_controls').scrollTop($(this).scrollTop());
	});
	var scrolling_tracks = $("#scrolling_tracks");
	var scrolling_ruler = $("#scrolling_ruler");
	
	scrolling_tracks.scroll(function () { 
		scrolling_ruler.scrollLeft($(this).scrollLeft());
	});

	// Make all clips draggable
	// var previous_drag_position = null;
	// var dragging = false;
	// $(".clip").draggable({ snap: ".track", snapMode: "inner", snapTolerance: 40, stack: ".clip",
	// 	start: function(e, ui) {
	// 		dragging = true;
	// 	},
 //        drag: function(e, ui) {
	// 		// Determine the amount moved since the previous event
	// 		var previous_x = ui.originalPosition.left;
	// 		var previous_y = ui.originalPosition.top;
	// 		if (previous_drag_position)
	// 		{
	// 			// if available, override with previous drag position
	// 			previous_x = previous_drag_position.left;
	// 			previous_y = previous_drag_position.top;
	// 		}
	// 		// set previous position (for next time round)
	// 		previous_drag_position = ui.position;

 //        	// Calculate amount to move clips
 //        	var x_offset = ui.position.left - previous_x;
 //        	var y_offset = ui.position.top - previous_y;

	// 		// Move all other selected clips with this one
 //            $(".ui-selected").not($(this)).each(function(){
 //            	var pos = $(this).position();
	// 	        $(this).css('left', pos.left + x_offset);
	// 	        $(this).css('top', pos.top + y_offset);
	// 	    });
 //        },
	// 		stop: function(e, ui) {
	// 			// Clear previous drag position
	// 			previous_drag_position = null;
	// 			dragging = false;
	// 			//console.log(ui);
				
	// 			// Loop through all clips on this track, and find one that is close
 //            //$(this).parent().children().not($(this)).each(function(){
 //            //	var pos = $(this).position();
	// 	    //})
	// 		}
	// });
	// $(".clip").resizable({ handles: "e, w",
	// 	start: function(e, ui) {
	// 		dragging = true;
	// 	},
	// 	stop: function(e, ui) {
	// 		dragging = false;
	// 	}
 //    });
    
	// $("#click_trap").selectable({
	// 	filter: '.clip',
	// });
	
	// $(".track").droppable({
	// 	drop: function(ev, ui) {
	// 		// Move clip to new track parent
	// 	    $(ui.draggable).detach().appendTo(this);
	// 	}
	// });
	
	// // Hover event on clip
	// $(".clip").hover(
	//   function () {
	// 	  	if (!dragging)
	// 	  	{
	// 		  	$(this).addClass( "highlight_clip", 400, "easeInOutCubic" );
	// 	  	}
	//   },
	//   function () {
	// 	  	if (!dragging)
	// 	  	{
	// 		  	$(this).removeClass( "highlight_clip", 400, "easeInOutCubic" );
	// 		}
	//   }
	// );

});