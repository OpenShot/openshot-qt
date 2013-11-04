var dragging = false;
var previous_drag_position = null;


//finds an element with a particular value in the json data
function findElement(arr, propName, propValue) {

  for (var i=0; i < arr.length; i++)
    if (arr[i][propName] == propValue)
      return arr[i];

}


//allows an element to be draggable
App.directive('tlDraggable', function() {
	return {
        // A = attribute, E = Element, C = Class and M = HTML Comment
        restrict:'A',
        link: function(scope, element, attrs) {
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

//allows an element to accept drops
App.directive('tlDroppable', function() {
    return {
        // A = attribute, E = Element, C = Class and M = HTML Comment
        restrict:'A',
        link: function(scope, element, attrs) {
        	element.droppable({
		        accept: ".clip",
		       	drop:function(event,ui) {
		        	dragged = angular.element(ui.draggable);
		        	dropped = angular.element(this);
		        	// Move clip to new track parent
					clip_id = dragged.attr("id");
					clip_num = clip_id.substr(clip_id.indexOf("_") + 1);
					elm = findElement(scope.clips, "number", clip_num);
					scope.$apply(function(){
			           elm.track = attrs.tlIndex;
			      	});

        			
		        }	
		    });
    	}    
    }
});

//holds the data index of an element
App.directive('tlIndex', function () {
        return {
             link:function (scope, elm, attrs) {}
     };
}); 