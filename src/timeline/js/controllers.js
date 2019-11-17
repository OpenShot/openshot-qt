/**
 * @file
 * @brief The AngularJS controller used by the OpenShot Timeline
 * @author Jonathan Thomas <jonathan@openshot.org>
 * @author Cody Parker <cody@yourcodepro.com>
 *
 * @section LICENSE
 *
 * Copyright (c) 2008-2018 OpenShot Studios, LLC
 * <http://www.openshotstudios.com/>. This file is part of
 * OpenShot Video Editor, an open-source project dedicated to
 * delivering high quality video editing and animation solutions to the
 * world. For more information visit <http://www.openshot.org/>.
 *
 * OpenShot Video Editor is free software: you can redistribute it
 * and/or modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation, either version 3 of the
 * License, or (at your option) any later version.
 *
 * OpenShot Video Editor is distributed in the hope that it will be
 * useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 */


// Initialize the main controller module
App.controller('TimelineCtrl',function($scope) {

	// DEMO DATA (used when debugging outside of Qt using Chrome)
	$scope.project = {
		fps: {
			num : 24,
			den : 1
		},
      	duration : 300, //length of project in seconds
      	scale : 16.0, //seconds per tick
      	tick_pixels : 100, //pixels between tick mark
      	playhead_position : 10, //position of play head
      	clips : [],
		  	// [
	          //      {
	          //        id : '1',
	          //        layer : 1,
	          //        image : './media/images/thumbnail.png',
	          //        locked : false,
	          //        duration : 32, //max length in seconds
	          //        start : 0,
	          //        end : 32,
	          //        position : 0.0,
	          //        title : 'Clip U2V5ENELDY',
	          //        effects : [
	          //                  { type : 'Saturation', icon : 'bw.png'},
	          //                  { type : 'ChromaKey',icon : 'om.png'},
	          //                  { type : 'Negate',icon : 'neg.png'},
	          //                  { type : 'Blur', icon: 'blur.png'},
	          //                  { type : 'Brightness', icon: 'cartoon.png'}
	          //                  ],
	          //        images :  {start: 1, end: 4},
	          //        show_audio : false,
             //
				// 	 alpha: {
				// 	    Points: [
				// 	      {
				// 	        "interpolation": 2,
				// 	        "co": {
				// 	          "Y": 0,
				// 	          "X": 0
				// 	        }
				// 	      },
				// 	      {
				// 	        "interpolation": 1,
				// 	        "co": {
				// 	          "Y": 0,
				// 	          "X": 250
				// 	        }
				// 	      },
				// 	      {
				// 	        "interpolation": 1,
				// 	        "co": {
				// 	          "Y": 1,
				// 	          "X": 500
				// 	        }
				// 	      }
				// 		]
				// 	},
				// 	location_x: { Points: [] },
				// 	location_y: { Points: [] },
				// 	scale_x: { Points: [] },
				// 	scale_y: { Points: [] },
				// 	rotation: { Points: [] },
				// 	time: { Points: [] },
				// 	volume: { Points: [] }
	          //
	          //      },
	          //      {
	          //        id : '2',
	          //        layer : 2,
	          //        image : './media/images/thumbnail.png',
	          //        locked : false,
	          //        duration : 45,
	          //        start : 0,
	          //        end : 45,
	          //        position : 0.0,
	          //        title : 'Clip B',
	          //        effects : [],
	          //        images : {start: 3, end: 7},
	          //        show_audio : false,
	          //        alpha: { Points: [] },
	          //        location_x: { Points: [] },
				// 	 location_y: { Points: [] },
				// 	 scale_x: { Points: [] },
				// 	 scale_y: { Points: [] },
				// 	 rotation: { Points: [] },
				// 	 time: { Points: [] },
				// 	 volume: { Points: [] }
	          //      },
	          //      {
	          //        id : '3',
	          //        layer : 3,
	          //        image : './media/images/thumbnail.png',
	          //        locked : false,
	          //        duration : 120,
	          //        start : 0,
	          //        end : 120,
	          //        position : 32.0,
	          //        title : 'Clip C',
	          //        effects : [
	          //                  { type : 'Deinterlace',icon : 'om.png'},
	          //                  { type : 'Blur', icon: 'blur.png'},
	          //                  { type : 'Mask', icon: 'cartoon.png'}
	          //                  ],
	          //        images : { start: 5, end: 10 },
	          //        show_audio : false,
	          //        audio_data : [.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3,.5, .6, .7, .7, .6, .5, .4, .1, 0, -0.1, -0.3, -0.6, -0.6, -0.3, -0.1, 0, .2, .3, ],
	          //        alpha: { Points: [] },
	          //        location_x: { Points: [] },
				// 	 location_y: { Points: [] },
				// 	 scale_x: { Points: [] },
				// 	 scale_y: { Points: [] },
				// 	 rotation: { Points: [] },
				// 	 time: { Points: [] },
				// 	 volume: { Points: [] }
	          //      },
             // ],
  		effects : [],
		  		// [
	               //  	{
	   	        //          id : '5',
		           //       layer : 4,
		           //       title : 'Transition',
		           //       position : 20.0,
		           //       start : 0,
		           //       end : 30
	               //  	},
	               //  	{
	   	        //          id : '6',
		           //       layer : 3,
		           //       title : 'Transition',
		           //       position : 137.5,
		           //       start : 0,
		           //       end : 30
	               //  	},
	               //  	{
	   	        //          id : '7',
		           //       layer : 2,
		           //       title : 'Transition',
		           //       position : 30.5,
		           //       start : 0,
		           //       end : 30
	               //  	}
                   //
                   //  ],
	  	layers : [
  				{id: 'L0', number:0, y:0, label: '', lock: false},
				{id: 'L1', number:1, y:0, label: '', lock: false},
				{id: 'L2', number:2, y:0, label: '', lock: false},
				{id: 'L3', number:3, y:0, label: '', lock: false},
				{id: 'L4', number:4, y:0, label: '', lock: false}
             ],
	  	markers : [],
              // [
	           //      {
	           //        id : 'M1',
	           //        position : 16,
	           //        icon : 'yellow.png'
	           //      },
	           //      {
	           //        id : 'M2',
	           //        position: 120,
	           //        icon : 'green.png'
	           //      },
	           //      {
	           //        id : 'M3',
	           //        position: 300,
	           //        icon : 'red.png'
	           //      },
	           //      {
	           //        id : 'M4',
	           //        position: 10,
	           //        icon : 'purple.png'
	           //      },
              // ],
	  	progress : {}
	  			// {
				//    max_bytes : "0",
				//    ranges : [
				// 	  {
				// 		 end : "30",
				// 		 start : "0"
				// 	  },
				// 	  {
				// 		 end : "40",
				// 		 start : "50"
				// 	  },
				// 	  {
				// 		 end : "100",
				// 		 start : "150"
				// 	  }
				//    ],
				//    version : "2"
				// }
    };
  
  // Additional variables used to control the rendering of HTML
  $scope.pixelsPerSecond =  parseFloat($scope.project.tick_pixels) / parseFloat($scope.project.scale);
  $scope.playheadOffset = 0;
  $scope.playhead_animating = false;
  $scope.playhead_height = 300;
  $scope.playheadTime =  secondsToTime($scope.project.playhead_position, $scope.project.fps.num, $scope.project.fps.den);
  $scope.shift_pressed = false;
  $scope.snapline_position = 0.0;
  $scope.snapline = false;
  $scope.enable_snapping = true;
  $scope.enable_razor = false;
  $scope.enable_playhead_follow = true;
  $scope.debug = false;
  $scope.min_width = 1024;
  $scope.track_label = "Track %s";
  $scope.enable_sorting = true;
  $scope.ThumbServer = "http://127.0.0.1/";

  // Method to set if Qt is detected (which clears demo data)
  $scope.Qt = false;
  $scope.EnableQt = function() {
	  	$scope.Qt = true;
	  	timeline.qt_log("$scope.Qt = true;");
  };

  $scope.SetThumbAddress = function(url) {
	  	$scope.ThumbServer = url;
	  	timeline.qt_log("SetThumbAddress: " + url);
  };

  // Move the playhead to a specific time
  $scope.MovePlayhead = function(position_seconds) {
	  // Update internal scope (in seconds)
	  $scope.project.playhead_position = position_seconds;
	  $scope.playheadTime = secondsToTime(position_seconds, $scope.project.fps.num, $scope.project.fps.den);

	  // Use JQuery to move playhead (for performance reasons) - scope.apply is too expensive here
	  $(".playhead-top").css("left", (($scope.project.playhead_position * $scope.pixelsPerSecond) + $scope.playheadOffset) + "px");
	  $(".playhead-line").css("left", (($scope.project.playhead_position * $scope.pixelsPerSecond) + $scope.playheadOffset) + "px");
	  $("#ruler_time").text($scope.playheadTime.hour + ":" + $scope.playheadTime.min + ":" + $scope.playheadTime.sec + ":" + $scope.playheadTime.frame);
  };
  
  // Move the playhead to a specific frame
  $scope.MovePlayheadToFrame = function(position_frames) {
	  // Don't move the playhead if it's currently animating
	  if ($scope.playhead_animating) {
			return;
	  }
	  
	  // Determine seconds
	  var frames_per_second = $scope.project.fps.num / $scope.project.fps.den;
	  var position_seconds = ((position_frames - 1) / frames_per_second);
	  
	  // Center on the playhead if it has moved out of view and the timeline should follow it
	  if ($scope.enable_playhead_follow && !$scope.isTimeVisible(position_seconds)) {
	    $scope.centerOnTime(position_seconds);
	  }
      
	  // Update internal scope (in seconds)
	  $scope.MovePlayhead(position_seconds);
  };

  // Move the playhead to a specific time
  $scope.PreviewFrame = function(position_seconds) {
	  // Determine frame
	  var frames_per_second = $scope.project.fps.num / $scope.project.fps.den;
	  var frame = Math.round(position_seconds * frames_per_second) + 1;

	  // Update GUI with position (so the preview can be updated)
	  if ($scope.Qt) {
		  timeline.PlayheadMoved(frame);
	  }
  };

  // Move the playhead to a specific time
  $scope.PreviewClipFrame = function(clip_id, position_seconds) {
	  // Get the nearest starting frame position to the playhead (this helps to prevent cutting
	  // in-between frames, and thus less likely to repeat or skip a frame).
  	  // Determine frame
  	  position_seconds_rounded = (Math.round((position_seconds * $scope.project.fps.num) / $scope.project.fps.den ) * $scope.project.fps.den ) / $scope.project.fps.num;
	  var frames_per_second = $scope.project.fps.num / $scope.project.fps.den;
	  var frame = Math.round(position_seconds_rounded * frames_per_second) + 1;

	  // Update GUI with position (so the preview can be updated)
	  if ($scope.Qt) {
		  timeline.PreviewClipFrame(clip_id, frame);
	  }
  };

  // Get an array of keyframe points for the selected clips
  $scope.getKeyframes = function(object) {
  	// List of keyframes
  	keyframes = {};

    var frames_per_second = $scope.project.fps.num / $scope.project.fps.den;
    var clip_start_x = Math.round(object.start * frames_per_second) + 1;
    var clip_end_x = Math.round(object.end * frames_per_second) + 1;

 	// Loop through properties of an object (clip/transition), looking for keyframe points
	for (child in object) {
	    if (!object.hasOwnProperty(child)) {
	        //The current property is not a direct property of p
	        continue;
	    }
	    // Determine if this property is a Keyframe
	 	if (typeof object[child] == "object" && "Points" in object[child]) {
			for (const point of object[child].Points) {
				if (point.co.X >= clip_start_x && point.co.X <= clip_end_x)
					// Only add keyframe coordinates that are within the bounds of the clip
					keyframes[point.co.X] = point.co.Y;
			}
		}
	    // Determine if this property is a Color Keyframe
	 	if (typeof object[child] == "object" && "red" in object[child]) {
			for (const point of object[child]["red"].Points) {
				if (point.co.X >= clip_start_x && point.co.X <= clip_end_x)
					// Only add keyframe coordinates that are within the bounds of the clip
					keyframes[point.co.X] = point.co.Y;
			}
		}
	}
	// Determine if this property contains effects (i.e. clips have their own effects)
	if ("effects" in object) {
		for (effect in object["effects"]) {
			// Loop through properties of an effect, looking for keyframe points
			for (child in object["effects"][effect]) {
				if (!object["effects"][effect].hasOwnProperty(child)) {
					//The current property is not a direct property of p
					continue;
				}
				// Determine if this property is a Keyframe
				if (typeof object["effects"][effect][child] == "object" && "Points" in object["effects"][effect][child]) {
					for (const point of object["effects"][effect][child].Points) {
						if (point.co.X >= clip_start_x && point.co.X <= clip_end_x)
							// Only add keyframe coordinates that are within the bounds of the clip
							keyframes[point.co.X] = point.co.Y;
					}
				}
				// Determine if this property is a Color Keyframe
				if (typeof object["effects"][effect][child] == "object" && "red" in object["effects"][effect][child]) {
					for (const point of object["effects"][effect][child]["red"].Points) {
						if (point.co.X >= clip_start_x && point.co.X <= clip_end_x)
							// Only add keyframe coordinates that are within the bounds of the clip
							keyframes[point.co.X] = point.co.Y;
					}
				}
			}
		}
	}
	// Return keyframe array
	return keyframes;
  };

  // Determine track top (in vertical pixels)
  $scope.getTrackTop = function(layer) {
	  // Get scrollbar position
	  var vert_scroll_offset = $("#scrolling_tracks").scrollTop();
	  var horz_scroll_offset = $("#scrolling_tracks").scrollLeft();

	  // Find this tracks Y location
	  var track_id = "div#track_" + layer;
	  if ($(track_id).length) {
		  return $(track_id).position().top + vert_scroll_offset;
	  }
	  else {
		  return 0;
	  }
  };

  // Determine whether a given timeline time index is scrolled into view
  $scope.isTimeVisible = function(time_pos) {
    // Get scrollbar positions
    var horz_scroll_offset = $("#scrolling_tracks").scrollLeft();
    var canvas_width = $("#scrolling_tracks").width();

    // Compute pixel location of time index
    var time_x = (time_pos * $scope.pixelsPerSecond) - horz_scroll_offset;
    if (time_x > 0 && time_x < canvas_width ) {
        return true;
    } else {
        return false;
    }
  };

  // Determine whether the playhead is within the visible timeline section
  $scope.isPlayheadVisible = function() {
    return $scope.isTimeVisible($scope.project.playhead_position);
  };

// ############# QT FUNCTIONS #################### //

 // Change the scale and apply to scope
 $scope.setScale = function(scaleVal, cursor_x) {
	  // Get scrollbar positions
	  var horz_scroll_offset = $("#scrolling_tracks").scrollLeft();
	  var track_labels_width = $("#track_controls").width();

	  // Determine actual x coordinate (over timeline)
      var center_x = Math.max(cursor_x - track_labels_width, 0);
      if (cursor_x === 0) {
		center_x = 0;
      }

      // Determine time of cursor position
      var cursor_time = parseFloat(center_x + horz_scroll_offset) / $scope.pixelsPerSecond;

      $scope.$apply(function() {
         $scope.project.scale = parseFloat(scaleVal);
         $scope.pixelsPerSecond = parseFloat($scope.project.tick_pixels) / parseFloat($scope.project.scale);
      });

	 // Scroll back to correct cursor time (minus the difference of the cursor location)
	 var new_cursor_x = Math.round((cursor_time * $scope.pixelsPerSecond) - center_x);
	 $("#scrolling_tracks").scrollLeft(new_cursor_x);
 };
 
 // Center the timeline on a given time position
 $scope.centerOnTime = function(centerTime) {
    // Get the width of the timeline
    var scrollingTracksWidth = $("#scrolling_tracks").width();
    
    // Calculate the position to scroll the timeline to to center on the requested time
    var pixelToCenterOn = parseFloat(centerTime) * $scope.pixelsPerSecond;
    var scrollPosition = Math.max(pixelToCenterOn - (scrollingTracksWidth / 2.0), 0);
    
    // Scroll the timeline using JQuery
    $("#scrolling_tracks").scrollLeft(Math.floor(scrollPosition + 0.5));
 };

  // Center the timeline on the current playhead position
  $scope.centerOnPlayhead = function() {
    $scope.centerOnTime($scope.project.playhead_position);
  };

 // Update thumbnail for clip
 $scope.updateThumbnail = function(clip_id) {
 	// Find matching clip, update thumbnail to same path (to force reload)
	var existing_thumb_path = $("#clip_" + clip_id + " .thumb").attr("src");
	timeline.qt_log(existing_thumb_path);
	$("#clip_" + clip_id + " .thumb").attr("src", existing_thumb_path);
 };

 // Set the audio data for a clip
 $scope.setAudioData = function(clip_id, audio_data) {
 	// Find matching clip
	for (const clip of $scope.project.clips) {
		if (clip.id == clip_id) {
			// Set audio data
			$scope.$apply(function(){
				clip.audio_data = audio_data;
				clip.show_audio = true;
			});
			timeline.qt_log("Audio data successful set on clip JSON");
			break;
		}

	 // Draw audio data
	 drawAudio($scope, clip_id);
	}
 };

 // Hide the audio waveform for a clip
 $scope.hideAudioData = function(clip_id, audio_data) {
 	// Find matching clip
	for (const clip of $scope.project.clips) {
		if (clip.id == clip_id) {
			// Set audio data
			$scope.$apply(function(){
				clip.show_audio = false;
				clip.audio_data = [];
			});
			break;
		}
	}
 };

 // Redraw all audio waveforms on the timeline (if any)
 $scope.reDrawAllAudioData = function() {
 	// Find matching clip
	for (const clip of $scope.project.clips) {
		if ("audio_data" in clip && clip.audio_data.length > 0) {
			// Redraw audio data (since it has audio data)
			drawAudio($scope, clip.id);
		}
	}
 };

 // Does clip have audio_data?
 $scope.hasAudioData = function(clip_id) {
 	// Find matching clip
	for (const clip of $scope.project.clips) {
		if (clip.id == clip_id && "audio_data" in clip && clip.audio_data.length > 0) {
			return true;
			break;
		}
	}
	return false;
 };

 // Change the snapping mode
 $scope.SetSnappingMode = function(enable_snapping) {
      $scope.$apply(function() {
         $scope.enable_snapping = enable_snapping;
		 if (enable_snapping) {
		 	$(".droppable").draggable("option", "snapTolerance", 20);
		 }
		 else {
		 	$(".droppable").draggable("option", "snapTolerance", 0);
		 }
     });
 };

 // Change the razor mode
 $scope.SetRazorMode = function(enable_razor) {
      $scope.$apply(function() {
         $scope.enable_razor = enable_razor;
     });
 };

 // Change playhead follow mode
 $scope.SetFollow = function(enable_follow) {
    $scope.$apply(function() {
        $scope.enable_playhead_follow = enable_follow;
    });
 };

 // Get the color of an effect
 $scope.GetEffectColor = function(effect_type) {
	switch (effect_type) {
		case "Blur":
			return "#0095bf";
		case "Brightness":
			return "#5500ff";
		case "ChromaKey":
			return "#00ad2d";
		case "Deinterlace":
			return "#006001";
		case "Mask":
			return "#cb0091";
		case "Negate":
			return "#ff9700";
		case "Saturation":
			return "#ff3d00";
		default:
			return "#000000";
	}
 };

 // Add a new clip to the timeline
 $scope.AddClip = function(x, y, clip_json) {
	 $scope.$apply(function() {
		 // Convert x and y into timeline vars
		 var scrolling_tracks_offset = $("#scrolling_tracks").offset().left;
		 var clip_position = parseFloat(x - scrolling_tracks_offset) / parseFloat($scope.pixelsPerSecond);

         // Get the nearest starting frame position to the clip position (this helps to prevent cutting
         // in-between frames, and thus less likely to repeat or skip a frame).
         clip_position = (Math.round((clip_position * $scope.project.fps.num) / $scope.project.fps.den ) * $scope.project.fps.den ) / $scope.project.fps.num;

		 clip_json.position = clip_position;
		 clip_json.layer = $scope.GetTrackAtY(y).number;
		 
		 // Push new clip onto stack
		 $scope.project.clips.push(clip_json);
	 });
 };
	
 // Update cache json
 $scope.RenderCache = function(cache_json) {
	 // Push new clip onto stack
	 $scope.project.progress = cache_json;
	 
	//clear the canvas first
	var ruler = $("#progress");
	var ctx = ruler[0].getContext('2d');
	ctx.clearRect(0, 0, ruler.width(), ruler.height());

	// Determine fps & and get cached ranges
	var fps = $scope.project.fps.num / $scope.project.fps.den;
	var progress = $scope.project.progress.ranges;

	// Loop through each cached range of frames, and draw rect
	for(p=0;p<progress.length;p++) {
		//get the progress item details
		var start_second = parseFloat(progress[p]["start"]) / fps;
		var stop_second = parseFloat(progress[p]["end"]) / fps;

		//figure out the actual pixel position
		var start_pixel = start_second * $scope.pixelsPerSecond;
		var stop_pixel = stop_second * $scope.pixelsPerSecond;
		var rect_length = stop_pixel - start_pixel;

		//get the element and draw the rects
		ctx.beginPath();
		ctx.rect(start_pixel, 0, rect_length, 5);
		ctx.fillStyle = '#4B92AD';
		ctx.fill();
	}
 };

 // Clear all selections
 $scope.ClearAllSelections = function() {
	// Clear the selections on the main window
	$scope.SelectTransition("", true);
	$scope.SelectEffect("", true);

	// Update scope
	$scope.$apply(function() {
		for (const clip of $scope.project.clips) {
			clip.selected = false;
		}
		for (const effect of $scope.project.effects) {
			effect.selected = false;
		}
	});
 };
 
 // Select all clips and transitions
 $scope.SelectAll = function() {
	 $scope.$apply(function() {
		 // Select all clips
		 for (const clip of $scope.project.clips) {
			 clip.selected = true;
			 timeline.addSelection(clip.id, "clip", false);
		 }
		 // Select all transitions
		 for (const effect of $scope.project.effects) {
			 effect.selected = true;
			 timeline.addSelection(effect.id, "transition", false);
		 }
	 });
 };
	
 // Select clip in scope
 $scope.SelectClip = function(clip_id, clear_selections, event) {
 	// Trim clip_id
 	var id = clip_id.replace("clip_", "");

	// Clear transitions also (if needed)
	if (id != "" && clear_selections) {
		$scope.SelectTransition("", clear_selections);
		$scope.SelectEffect("", clear_selections);
	}
	// Call slice method and exit (don't actually select the clip)
	if (id != "" && $scope.enable_razor) {
        if ($scope.Qt) {
			cursor_seconds = $scope.GetJavaScriptPosition(event.clientX);
            timeline.RazorSliceAtCursor(id, "", cursor_seconds);
        }
		// Don't actually select clip
        return;
    }
	// Is CTRL pressed?
	is_ctrl = false;
	if (event && event.ctrlKey) {
		is_ctrl = true;
	}
 	
 	// Unselect all clips
	for (const clip of $scope.project.clips) {
		if (clip.id == id) {
			clip.selected = true;
			if ($scope.Qt) {
				timeline.addSelection(id, "clip", clear_selections);
			}
		}
		else if (clear_selections && !is_ctrl) {
			clip.selected = false;
			if ($scope.Qt) {
	 			timeline.removeSelection(clip.id, "clip");
			}
		}
	}
 };
 
  // Select transition in scope
 $scope.SelectTransition = function(tran_id, clear_selections, event) {
 	// Trim tran_id
 	var id = tran_id.replace("transition_", "");

	// Clear clips also (if needed)
	if (id != "" && clear_selections) {
		$scope.SelectClip("", true);
		$scope.SelectEffect("", true);
	}
	// Call slice method and exit (don't actually select the transition)
	if (id != "" && $scope.enable_razor) {
        if ($scope.Qt) {
			cursor_seconds = $scope.GetJavaScriptPosition(event.clientX)
            timeline.RazorSliceAtCursor("", id, cursor_seconds)
        }
		// Don't actually select transition
        return;
    }

	// Is CTRL pressed?
	is_ctrl = false;
	if (event && event.ctrlKey) {
		is_ctrl = true;
	}

 	// Unselect all transitions
	for (const tran of $scope.project.effects) {
		if (tran.id == id) {
			tran.selected = true;
		 	if ($scope.Qt)
				timeline.addSelection(id, "transition", clear_selections);
		}
		else if (clear_selections && !is_ctrl) {
			tran.selected = false;
		 	if ($scope.Qt)
			 	timeline.removeSelection(tran.id, "transition");
		}
	}
 };

  // Format the thumbnail path: http://127.0.0.1:8081/thumbnails/FILE-ID/FRAME-NUMBER/
 $scope.GetThumbPath = function(clip) {
 	var file_fps = clip["reader"]["fps"]["num"] / clip["reader"]["fps"]["den"];
 	return $scope.ThumbServer + clip.file_id + "/" + ((file_fps * clip.start) + 1) + "/";
 };

  // Select transition in scope
 $scope.SelectEffect = function(effect_id) {
 	if ($scope.Qt) {
	 	timeline.addSelection(effect_id, "effect", true);
 	}
 };

// Find the furthest right edge on the timeline (and resize it if too small)
 $scope.ResizeTimeline = function() {
 	// Unselect all clips
	var furthest_right_edge = 0;
	for (const clip of $scope.project.clips) {
		var right_edge = clip.position + (clip.end - clip.start);
		if (right_edge > furthest_right_edge)
			furthest_right_edge = right_edge;
	}
	// Resize timeline
	if (furthest_right_edge > $scope.project.duration) {
		if ($scope.Qt) {
			timeline.resizeTimeline(furthest_right_edge + 10)
			$scope.project.duration = furthest_right_edge + 10;
		}
	}
 };
 
// Show clip context menu
$scope.ShowClipMenu = function(clip_id, event) {
 	if ($scope.Qt && !$scope.enable_razor) {
	 	timeline.qt_log("$scope.ShowClipMenu");
	 	$scope.SelectClip(clip_id, false, event);
	 	timeline.ShowClipMenu(clip_id);
 	}
};

// Show clip context menu
$scope.ShowEffectMenu = function(effect_id) {
 	if ($scope.Qt && !$scope.enable_razor) {
	 	timeline.qt_log("$scope.ShowEffectMenu");
	 	timeline.ShowEffectMenu(effect_id);
 	}
};

// Show transition context menu
$scope.ShowTransitionMenu = function(tran_id, event) {
 	if ($scope.Qt && !$scope.enable_razor) {
	 	timeline.qt_log("$scope.ShowTransitionMenu");
	 	$scope.SelectTransition(tran_id, false, event);
	 	timeline.ShowTransitionMenu(tran_id);
 	}
};

// Show track context menu
$scope.ShowTrackMenu = function(layer_id) {
 	if ($scope.Qt && !$scope.enable_razor) {
	 	timeline.qt_log("$scope.ShowTrackMenu");
	 	timeline.ShowTrackMenu(layer_id);
 	}
};

// Show marker context menu
$scope.ShowMarkerMenu = function(marker_id) {
 	if ($scope.Qt && !$scope.enable_razor) {
	 	timeline.qt_log("$scope.ShowMarkerMenu");
	 	timeline.ShowMarkerMenu(marker_id);
 	}
};

  // Show playhead context menu
$scope.ShowPlayheadMenu = function(position) {
 	if ($scope.Qt && !$scope.enable_razor) {
	 	timeline.qt_log("$scope.ShowPlayheadMenu");
	 	timeline.ShowPlayheadMenu(position);
	 }
};

  // Show timeline context menu
$scope.ShowTimelineMenu = function(e, layer_number) {
 	if ($scope.Qt && !$scope.enable_razor) {
	 	timeline.ShowTimelineMenu($scope.GetJavaScriptPosition(e.pageX), layer_number);
	 }
};

 // Get the name of the track
 $scope.GetTrackName = function(layer_label, layer_number) {
	// Determine custom label or default track name
	if (layer_label && layer_label.length > 0) {
		return layer_label;
	}
	else {
		return $scope.track_label.replace('%s', layer_number.toString());
	}
 };

$scope.SetTrackLabel = function (label) {
	$scope.track_label = label;
};

 // Get the width of the timeline in pixels
 $scope.GetTimelineWidth = function(min_value) {
	// Adjust for minimim length
	return Math.max(min_value, $scope.project.duration * $scope.pixelsPerSecond);
 };

 
 // Get Position of item (used by Qt)
 $scope.GetJavaScriptPosition = function(x) {
	// Adjust for scrollbar position
	var horz_scroll_offset = $("#scrolling_tracks").scrollLeft();
	var scrolling_tracks_offset_left = $("#scrolling_tracks").offset().left;
	x += horz_scroll_offset;

	 // Convert x into position in seconds
	 var clip_position = parseFloat(x - scrolling_tracks_offset_left) / parseFloat($scope.pixelsPerSecond);
	 if (clip_position < 0) {
		 clip_position = 0;
	 }
	 
	 // Return position in seconds
	 return clip_position;
 };
 
 // Get Track number of item (used by Qt)
 $scope.GetJavaScriptTrack = function(y) {
	// Adjust for scrollbar position
	var scrolling_tracks_offset_top = $("#scrolling_tracks").offset().top;
  	var vert_scroll_offset = $("#scrolling_tracks").scrollTop();
	y += vert_scroll_offset;

	// Return number of track
	var track_number = parseInt($scope.GetTrackAtY(y - scrolling_tracks_offset_top).number);
	return track_number;
 };
 
 // Get JSON of most recent item (used by Qt)
 $scope.UpdateRecentItemJSON = function(item_type, item_id) {

	// Find item in JSON
	var item_object = null;
	if (item_type == 'clip') {
		item_object = findElement($scope.project.clips, "id", item_id);
	}
	else if (item_type == 'transition') {
		item_object = findElement($scope.project.effects, "id", item_id);
	}
	else {
		// Bail out if no id found
		return;
	}
	// Get position of item
	var scrolling_tracks_offset_top = $("#scrolling_tracks").offset().top;
	var clip_position = parseFloat(bounding_box.left) / parseFloat($scope.pixelsPerSecond);
	var layer_num = $scope.GetTrackAtY(bounding_box.track_position - scrolling_tracks_offset_top).number;

	// update scope with final position of items
	$scope.$apply(function() {
		// update item
		item_object.position = clip_position;
		item_object.layer = layer_num;
	});

	// update clip in Qt (very important =)
	if (item_type == 'clip') {
		timeline.update_clip_data(JSON.stringify(item_object), true, true, false);
	}
	else if (item_type == 'transition') {
		timeline.update_transition_data(JSON.stringify(item_object), true, false);
	}

	// Resize timeline if it's too small to contain all clips
	$scope.ResizeTimeline();

	// Hide snapline (if any)
	$scope.HideSnapline();

	// Check again for missing transitions
	missing_transition_details = $scope.GetMissingTransitions(item_object);
	if ($scope.Qt && missing_transition_details != null) {
		timeline.add_missing_transition(JSON.stringify(missing_transition_details));
	}
	// Remove manual move stylesheet
	bounding_box.element.removeClass("manual-move");

	// Remove CSS class (after the drag)
	bounding_box = {};
 };
	
 // Init bounding boxes for manual move
 $scope.StartManualMove = function(item_type, item_id) {
	 // Select the item
	 $scope.$apply(function() {
		 if (item_type == 'clip') {
			 $scope.SelectClip(item_id, true);
		 }
		 else if (item_type == 'transition') {
			 $scope.SelectTransition(item_id, true);
		 }
	 });

 	// Select new clip object (and unselect others)
	// This needs to be done inline due to async issues with the
	// above calls to SelectClip/SelectTransition
	for (const clip of $scope.project.clips) {
		if (clip.id == item_id) {
			clip.selected = true;
		} else {
			clip.selected = false;
		}
	}

	// Select new transition object (and unselect others)
	for (const tran of $scope.project.effects) {
		if (tran.id == item_id) {
			tran.selected = true;
		} else {
			tran.selected = false;
		}
	}

	 // JQuery selector for element (clip or transition)
	 var element_id = "#" + item_type + "_" + item_id;

	 // Init bounding box
	 bounding_box = {};
	 setBoundingBox($scope, $(element_id));

	 // Init some variables to track the changing position
	 bounding_box.previous_x = bounding_box.left;
	 bounding_box.previous_y = bounding_box.top;
	 bounding_box.offset_x = 0;
	 bounding_box.offset_y = 0;
	 bounding_box.element = $(element_id);
	 bounding_box.track_position = 0;

	 // Set z-order to be above other clips/transitions
	 if (item_type != "os_drop") {
	 	bounding_box.element.addClass("manual-move");
	 }
 };
 
 // Move a new clip to the timeline
 $scope.MoveItem = function(x, y, item_type) {

	var vert_scroll_offset = $("#scrolling_tracks").scrollTop();
	var horz_scroll_offset = $("#scrolling_tracks").scrollLeft();
	x += horz_scroll_offset;
	y += vert_scroll_offset;

	// Convert x and y into timeline vars
	var scrolling_tracks_offset_left = $("#scrolling_tracks").offset().left;
	var scrolling_tracks_offset_top = $("#scrolling_tracks").offset().top;

	// Calculate the x,y of cursor
	var left = parseFloat(x - scrolling_tracks_offset_left);
	var top = parseFloat(y - scrolling_tracks_offset_top);

	// Calculate amount to move transitions
	var x_offset = left - bounding_box.previous_x;
	var y_offset = top - bounding_box.previous_y;

	// Move the bounding box and apply snapping rules
	results = moveBoundingBox($scope, bounding_box.previous_x, bounding_box.previous_y, x_offset, y_offset, left, top);

	// Track previous values
	bounding_box.previous_x = results.position.left;
	bounding_box.previous_y = results.position.top;

	var clip_position = parseFloat(results.position.left) / parseFloat($scope.pixelsPerSecond);
	if (clip_position < 0) {
		clip_position = 0;
	}
	// Loop through each layer (looking for the closest track based on Y coordinate)
	bounding_box.track_position = 0;
	for (const layer of $scope.project.layers) {
		// Compare position of track to Y param (for unlocked tracks)
		if (!layer.lock) {
			if ((top < layer.y && top > bounding_box.track_position) || bounding_box.track_position === 0) {
				// return first matching layer
				bounding_box.track_position = layer.y;
			}
		}
	}
	//change the element location
	bounding_box.element.css('left', results.position.left);
	bounding_box.element.css('top', bounding_box.track_position - scrolling_tracks_offset_top);
 };
 
 // Update X,Y indexes of tracks / layers (anytime the project.layers scope changes)
 $scope.UpdateLayerIndex = function(){

	 if ($scope.Qt) {
		 timeline.qt_log('UpdateLayerIndex');
	 }

	var vert_scroll_offset = $("#scrolling_tracks").scrollTop();
	var horz_scroll_offset = $("#scrolling_tracks").scrollLeft();

	// Get scrollbar offsets
	var scrolling_tracks_offset_left = $("#scrolling_tracks").offset().left;
	var scrolling_tracks_offset_top = $("#scrolling_tracks").offset().top;

	 $scope.$apply(function() {
		 // Loop through each layer
		for (const layer of $scope.project.layers) {
			// Find element on screen (bound to this layer)
			var layer_elem = $("#track_" + layer.number);
			if (layer_elem) {
				// Update the top offset
				layer.y = layer_elem.offset().top + vert_scroll_offset;
			}
		}
		// Update playhead height
		$scope.playhead_height = $("#track-container").height();
		$(".playhead-line").height($scope.playhead_height);
	 });
 };

 // Sort clips and transitions by position
 $scope.SortItems = function() {
	if (!$scope.enable_sorting) {
		 // Sorting is disabled, do nothing
		 return;
	}

	if ($scope.Qt) {
		 timeline.qt_log('SortItems');

		 $scope.$evalAsync(function() {
			 // Sort by position second
			 $scope.project.clips = $scope.project.clips.sort(function(a,b) {
				    if ( a.position < b.position ) {
				        return -1;
				    }
				    if ( a.position > b.position ) {
				        return 1;
				    }
				    return 0;
			  });
			 // Sort transitions by position second
			 $scope.project.effects = $scope.project.effects.sort(function(a,b) {
				    if ( a.position < b.position ) {
				        return -1;
				    }
				    if ( a.position > b.position ) {
				        return 1;
				    }
				    return 0;
			  });
			 // Sort tracks by position second
			 $scope.project.layers = $scope.project.layers.sort(function(a,b) {
				    if ( a.number < b.number ) {
				        return -1;
				    }
				    if ( a.number > b.number ) {
				        return 1;
				    }
				    return 0;
			  });
		});
	}
 };
 
 // Find overlapping clips
 $scope.GetMissingTransitions = function(original_clip) {

 	var transition_size = null;
 	
 	// Get clip that matches this id
 	var original_left = original_clip.position;
 	var original_right = original_clip.position + (original_clip.end - original_clip.start);
	
	// Search through all other clips on this track, and look for overlapping ones
	for (const clip of $scope.project.clips) {
		// skip clips that are not on the same layer
		if (original_clip.layer != clip.layer) {
			continue;
		}
		
		// is clip overlapping
		var clip_left = clip.position;
		var clip_right = clip.position + (clip.end - clip.start);
		
		if (original_left < clip_right && original_left > clip_left) {
			transition_size = { "position" : original_left, "layer" : clip.layer, "start" : 0, "end" : (clip_right - original_left) };
		}
		else if (original_right > clip_left && original_right < clip_right) {
			transition_size = { "position" : clip_left, "layer" : clip.layer, "start" : 0, "end" : (original_right - clip_left) };
		}

		if (transition_size != null && transition_size.end >= 0.5) {
			// Found a possible missing transition
			break;
		}
		else if (transition_size != null && transition_size.end < 0.5) {
			// Too small to be a missing transitions, clear and continue looking
			transition_size = null;
		}
	}
	// Search through all existing transitions, and don't overlap an existing one
	if (transition_size != null) {
		for (const tran of $scope.project.effects) {
			// skip transitions that are not on the same layer
			if (tran.layer != transition_size.layer) {
				continue;
			}

			var tran_left = tran.position;
			var tran_right = tran.position + (tran.end - tran.start);

			var new_tran_left = transition_size.position;
			var new_tran_right = transition_size.position + (transition_size.end - transition_size.start);

			var TOLERANCE = 0.01;
			// Check for overlapping transitions
			if (Math.abs(tran_left - new_tran_left) < TOLERANCE || Math.abs(tran_right - new_tran_right) < TOLERANCE) {
				transition_size = null; // this transition already exists
				break;
			}
		}
	}

 	return transition_size;
 };
 
 // Search through clips and transitions to find the closest element within a given threshold
 $scope.GetNearbyPosition = function(pixel_positions, threshold, ignore_ids) {
	// init some vars
	var smallest_diff = 900.0;
	var smallest_abs_diff = 900.0;
	var snapping_position = 0.0;
	var diffs = [];

	// Loop through each pixel position (supports multiple positions: i.e. left and right side of bounding box)
	for (const position of pixel_positions) {
		// Add clip positions to array
		for (const clip of $scope.project.clips) {
			var clip_left_position = clip.position * $scope.pixelsPerSecond;
			var clip_right_position = (clip.position + (clip.end - clip.start)) * $scope.pixelsPerSecond;

			// exit out if this item is in ignore_ids
			if (ignore_ids.hasOwnProperty(clip.id)) {
				continue;
			}
			
			diffs.push({'diff' : position - clip_left_position, 'position' : clip_left_position}, // left side of clip
			           {'diff' : position - clip_right_position, 'position' : clip_right_position}); // right side of clip
		}
		
		// Add transition positions to array
		for (const transition of $scope.project.effects) {
			var tran_left_position = transition.position * $scope.pixelsPerSecond;
			var tran_right_position = (transition.position + (transition.end - transition.start)) * $scope.pixelsPerSecond;


			// exit out if this item is in ignore_ids
			if (ignore_ids.hasOwnProperty(transition.id)) {
				continue;
			}

			diffs.push({'diff' : position - tran_left_position, 'position' : tran_left_position}, // left side of transition
			           {'diff' : position - tran_right_position, 'position' : tran_right_position}); // right side of transition
		}

		// Add marker positions to array
		for (const marker of $scope.project.markers) {
			var marker_position = marker.position * $scope.pixelsPerSecond;

			diffs.push({'diff' : position - marker_position, 'position' : marker_position}, // left side of marker
			           {'diff' : position - marker_position, 'position' : marker_position}); // right side of marker
		}

		// Add playhead position to array
		var playhead_pixel_position = $scope.project.playhead_position * $scope.pixelsPerSecond;
		var playhead_diff = position - playhead_pixel_position;
		diffs.push({'diff' : playhead_diff, 'position' : playhead_pixel_position });

		// Loop through diffs (and find the smallest one)
		for (const each_diff of diffs) {
			var diff = each_diff.diff;
			var diff_position = each_diff.position;
			var abs_diff = Math.abs(diff);

			// Check if this clip is nearby
			if (abs_diff < smallest_abs_diff && abs_diff <= threshold) {
				// This one is smaller
				smallest_diff = diff;
				smallest_abs_diff = abs_diff;
				snapping_position = diff_position;
			}
		}
	}
	
	// no nearby found?
	if (smallest_diff === 900.0) {
		smallest_diff = 0.0;
	}
	
	// Return closest nearby position
	return [smallest_diff, snapping_position];
 };
 
  // Show the nearby snapping line
 $scope.ShowSnapline = function(position) {
	 if (position != $scope.snapline_position || !$scope.snapline) {
		 // Only update if value has changed
		 $scope.$apply(function() {
			$scope.snapline_position = position;
			$scope.snapline = true;
		 });
	 }
 };
 
 // Hide the nearby snapping line
 $scope.HideSnapline = function() {
	 if ($scope.snapline) {
		 // Only hide if not already hidden
		 $scope.$apply(function() {
			$scope.snapline = false;
		 });
	 }
 };
 
 // Find a track JSON object at a given y coordinate (if any)
 $scope.GetTrackAtY = function(y) {
		// Loop through each layer (looking for the closest track based on Y coordinate)
		for (var layer_index = $scope.project.layers.length - 1; layer_index >= 0 ; layer_index--) {
			var layer = $scope.project.layers[layer_index];

			// Compare position of track to Y param and return first matching layer
			if (layer.y > y) {
				return layer;
			}
		}

		// no layer found (return top layer... if any)
		if ($scope.project.layers.length > 0) {
			return $scope.project.layers[0];
		}
		else {
			return null;
		}
 };

 // Determine which CSS classes are used on a track
 $scope.GetTrackStyle = function(lock) {
	if (lock) {
		return "track track_disabled";
	}
 	else {
		return "track";
 	}
 };

 // Determine which CSS classes are used on a clip
 $scope.getClipStyle = function(clip) {

	style = "";
	if (clip.selected) {
		style += "ui-selected ";
	}
	if ($scope.enable_razor) {
		style += "razor_cursor ";
	}

 	return style;
 };

 // Determine which CSS classes are used on a clip label
 $scope.getClipLabelStyle = function(clip) {
	style = "";
	if ($scope.enable_razor) {
		style += "razor_cursor";
	}
 	return style;
 };

 // Apply JSON diff from UpdateManager (this is how the user interface communicates changes
 // to the timeline. A change can be an insert, update, or delete. The change is passed in
 // as JSON, which represents the change.
 $scope.ApplyJsonDiff = function(jsonDiff) {

	 // Loop through each UpdateAction
	for (const action of jsonDiff) {
		 // Iterate through the key levels (looking for a matching element in the $scope.project)
		 var previous_object = null;
		 var current_object = $scope.project;
		 var current_position = 0;
		 var current_key = "";
		 for (var key_index = 0; key_index < action.key.length; key_index++) {
		 	var key_value = action.key[key_index];

		 	// Check the key type
		 	if (key_value.constructor == String) {
		 		// Does the key value exist in scope?, No match, bail out
		 		if (!current_object.hasOwnProperty(key_value)) {
		 			return false;
		 		}
	 			// set current level and previous level
	 			previous_object = current_object;
	 			current_object = current_object[key_value];
	 			current_key = key_value;
		 		
		 	}
		 	else if (key_value.constructor == Object) {
		 		// Get the id from the object (if any)
		 		var id = null;
		 		if ("id" in key_value) {
		 			id = key_value["id"];
		 		}
		 		// Be sure the current_object is an Array
		 		if (current_object.constructor == Array) {
			 		// Filter the current_object for a specific id
			 		current_position = 0;
			 		for (var child_index = 0; child_index < current_object.length; child_index++) {
			 			var child_object = current_object[child_index];
			 		
						// Find matching child
						if (child_object.hasOwnProperty("id") && child_object.id == id) {
				 			// set current level and previous level
				 			previous_object = current_object;
				 			current_object = child_object;
				 			break; // found child, stop looping
				 		}
				 		// increment index
				 		current_position++;
			 		}
		 		}
		 	}
		}

        // Now that we have a matching object in the $scope.project...
        if (current_object) {
            // INSERT OBJECT
            if (action.type == "insert") {
                // Insert action's value into current_object
                if (current_object.constructor == Array) {
                    // push new element into array
                    current_object.push(action.value);
                }
                else {
                    // replace the entire value
                    if (previous_object.constructor == Array) {
                        // replace entire value in OBJECT
                        previous_object[current_position] = action.value;
                    }
                    else if (previous_object.constructor == Object) {
                        // replace entire value in OBJECT
                        previous_object[current_key] = action.value;
                    }
                }
            }
            else if (action.type == "update") {
                // UPDATE OBJECT
                // Update: If action and current object are Objects
                if (current_object.constructor == Object && action.value.constructor == Object) {
                    for (var update_key in action.value) {
                        if (update_key in current_object)
                        // Only copy over keys that exist in both action and current_object
                        current_object[update_key] = action.value[update_key];
                    }
                }
                else {
                    // replace the entire value
                    if (previous_object.constructor == Array) {
                        // replace entire value in OBJECT
                        previous_object[current_position] = action.value;
                    }
                    else if (previous_object.constructor == Object) {
                        // replace entire value in OBJECT
                        previous_object[current_key] = action.value;
                    }
                }
            }
            else if (action.type == "delete") {
                // DELETE OBJECT
                // delete current object from it's parent (previous object)
                previous_object.splice(current_position, 1);
            }
            // Resize timeline if it's too small to contain all clips
            $scope.ResizeTimeline();

            // Re-sort clips and transitions array
            $scope.SortItems();

            // Re-index Layer Y values
            $scope.UpdateLayerIndex();
        }
		$scope.$digest();
	}
	// return true
	return true;
 };
 
 // Load entire project data JSON from UpdateManager (i.e. user opened an existing project)
 $scope.LoadJson = function(EntireProjectJson) {
 	
	 $scope.$apply(function() {
 		// Update the entire JSON object for the entire timeline
 		$scope.project = EntireProjectJson.value;
 		// Un-select any selected items
 		$scope.SelectClip("", true);
	 });

     // Re-sort clips and transitions array
     $scope.SortItems();

	 // Re-index Layer Y values
	 $scope.UpdateLayerIndex();

	 // Scroll to top/left when loading a project
	 $("#scrolling_tracks").animate({
		scrollTop: 0,
		scrollLeft: 0
	 }, 'slow');

     // Update playhead position and time readout
     $scope.MovePlayhead($scope.project.playhead_position)

	 // return true
	 return true;
 };

// ############# END QT FUNCTIONS #################### //



// ############ DEBUG STUFFS ################## //

 $scope.ToggleDebug = function() {
	 if ($scope.debug === true) {
		 $scope.debug = false;
	 }
	 else {
		 $scope.debug = true;
	 }
 };

  // Debug method to add clips to the $scope
  $scope.addClips = function(numClips) {
        startNum = $scope.project.clips.length + 1;
	  	positionNum = 0;
        for (var x = 0; x < parseInt(numClips); x++) {
           $scope.project.clips.push({
	                 id : x.toString(),
	                 layer : 0,
	                 image : './media/images/thumbnail.png',
	                 locked : false,
	                 duration : 50,
	                 start : 0,
	                 end : 50,
	                 position : positionNum,
	                 title : 'Clip B',
	                 effects : [],
	                 images : {start: 3, end: 7},
	                 show_audio : false,
	                 alpha: { Points: [] },
	                 location_x: { Points: [] },
					 location_y: { Points: [] },
					 scale_x: { Points: [] },
					 scale_y: { Points: [] },
					 rotation: { Points: [] },
					 time: { Points: [] },
					 volume: { Points: [] }
	               });
            startNum++;
			positionNum+=50;
        };
        $scope.numClips = "";
    };

  // Debug method to add effects to a clip's $scope
  $scope.addEffect = function(clipNum) {
	    //find the clip in the json data
	    elm = findElement($scope.project.clips, "id", clipNum);
	    elm.effects.push({
	       effect : 'Old Movie',
	       icon : 'om.png'
	    });
	    $scope.clipNum = "";
  };

  // Debug method to add a marker to the $scope
  $scope.addMarker = function(markLoc) {
        $scope.project.markers.push({
          position: parseInt(markLoc),
          icon: 'blue.png'
        });
        $scope.markLoc = "";
  };

  // Debug method to change a clip's image
  $scope.changeImage = function(startImage) {
        $scope.project.clips[2].images.start = startImage;
        $scope.startImage = "";
  };

});
