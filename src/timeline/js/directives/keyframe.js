/**
 * @file
 * @brief Keyframe directive (draggable keyframes on the timeline)
 */

/*global App, findElement, uuidv4, snapToFPSGridTime, pixelToTime, timeline, angular, document*/
App.directive("tlKeyframe", function () {
  return {
    link: function (scope, element, attrs) {
      var obj, objType = attrs.objectType, objId = attrs.objectId;
      var fps = scope.project.fps.num / scope.project.fps.den;
      var transactionId = null;
      var currentFrame = parseInt(attrs.point, 10);

      // Track the candidate new frame while dragging (no model writes until stop)
      var pendingFrame = currentFrame;

      function toNumber(value, fallback) {
        var parsed = parseFloat(value);
        return isNaN(parsed) ? fallback : parsed;
      }

      function locateObject() {
        if (objType === "clip") {
          obj = findElement(scope.project.clips, "id", objId);
        } else {
          obj = findElement(scope.project.effects, "id", objId);
        }
      }

      function getBounds(object) {
        if (!object) { return null; }
        var start = toNumber(object.start, 0);
        var end = toNumber(object.end, NaN);
        if (isNaN(end)) {
          var duration = toNumber(object.duration, NaN);
          if (!isNaN(duration)) end = start + duration;
          else end = start;
        }
        start = snapToFPSGridTime(scope, start);
        end   = snapToFPSGridTime(scope, end);
        if (end < start) { var t = start; start = end; end = t; }
        return { start: start, end: end };
      }

      // Right edge must be exclusive: last valid time is end - (1/fps)
      function exclusiveMaxSec(bounds) {
        return bounds.end - (1 / fps);
      }

      // Clamp to [start, end-1/fps], snap to grid, clamp again (prevents landing past last frame)
      function snapClampExclusive(secs, bounds) {
        if (secs < bounds.start) secs = bounds.start;
        var maxSec = exclusiveMaxSec(bounds);
        if (secs > maxSec) secs = maxSec;
        secs = snapToFPSGridTime(scope, secs);
        if (secs > maxSec) secs = maxSec;  // guard post-snap
        if (secs < bounds.start) secs = bounds.start;
        return secs;
      }

      function secondsToPixels(object, seconds) {
        var start = toNumber(object.start, 0);
        return (seconds - start) * scope.pixelsPerSecond;
      }

      // Convert seconds -> frame index; end is inclusive at floor(end*fps)
      function secondsToFrame(secs, bounds) {
        var startFrame = Math.floor(bounds.start * fps) + 1;
        var endFrame   = Math.floor(bounds.end   * fps);
        var f = Math.floor(secs * fps) + 1; // aligned by snapClampExclusive
        if (f < startFrame) f = startFrame;
        if (f > endFrame)   f = endFrame;
        return f;
      }

      function pushKeyframeChange(copy, ignoreRefresh) {
        var json = JSON.stringify(copy);
        if (objType === "clip") {
          timeline.update_clip_data(
            json, false /*allow keyframes*/, true /*force JSON diff*/, ignoreRefresh, transactionId
          );
        } else {
          timeline.update_transition_data(
            json, false, ignoreRefresh, transactionId
          );
        }
      }

      var draggingKeyframe = false;

      function enterDragMode() {
        if (draggingKeyframe) return;
        draggingKeyframe = true;
        element.addClass("point-dragging");
        if (document && document.body) {
          document.body.classList.add("keyframe-dragging");
        }
      }

      function exitDragMode() {
        if (!draggingKeyframe) return;
        draggingKeyframe = false;
        element.removeClass("point-dragging");
        if (document && document.body) {
          document.body.classList.remove("keyframe-dragging");
          document.body.style.cursor = "";
        }
      }

      function restoreUserSelect() {
        if (document && document.body) {
          document.body.style.userSelect = "";
          document.body.style.webkitUserSelect = "";
        }
      }

      // Prevent parent selectable/drag handlers from interfering
      element.on("mousedown", function (e) {
        e.stopPropagation();
      });

      element.draggable({
        axis: "x",
        distance: 1,
        scroll: true,
        cursor: "ew-resize",
        start: function () {
          scope.setDragging(true);
          enterDragMode();
          transactionId = uuidv4();
          currentFrame = parseInt(attrs.point, 10);
          pendingFrame = currentFrame;
          locateObject();
          if (scope.Qt) {
            timeline.StartKeyframeDrag(objType, objId, transactionId);
          }
          try { window.getSelection() && window.getSelection().removeAllRanges(); } catch (_) {}
          if (document && document.body) {
            document.body.style.userSelect = "none";
            document.body.style.webkitUserSelect = "none";
          }
        },
        drag: function (e, ui) {
          locateObject();
          if (!obj || typeof obj.start === "undefined") return;

          var left   = ui.position.left;
          var start  = toNumber(obj.start, 0);
          var bounds = getBounds(obj);

          // propose secs from pixels, then snap&clamp with end-exclusive rule
          var secs = pixelToTime(scope, left) + start;
          secs = snapClampExclusive(secs, bounds);

          // keep helper aligned to snapped time
          left = secondsToPixels(obj, secs);
          ui.position.left = left;
          if (ui.helper) ui.helper.css("left", left + "px");

          // candidate frame (snapped, end-exclusive safe)
          var newFrame = secondsToFrame(secs, bounds);
          pendingFrame = newFrame;

          // visual preview only
          var position = toNumber(obj.position, 0);
          scope.$evalAsync(function () {
            scope.previewFrame(position + pixelToTime(scope, left));
          });
        },
        stop: function (e, ui) {
          scope.setDragging(false);
          exitDragMode();
          locateObject();
          if (!obj || typeof obj.start === "undefined") {
            restoreUserSelect();
            return;
          }

          var left   = ui.position.left;
          var start  = toNumber(obj.start, 0);
          var bounds = getBounds(obj);

          // final secs with snap + end-exclusive clamp
          var secs = pixelToTime(scope, left) + start;
          secs = snapClampExclusive(secs, bounds);

          // enforce visual sync to snapped pos
          left = secondsToPixels(obj, secs);
          ui.position.left = left;
          if (ui.helper) ui.helper.css("left", left + "px");
          element.css("left", left + "px");

          var newFrame = secondsToFrame(secs, bounds);

          if (newFrame !== currentFrame) {
            var copy = angular.copy(obj);
            scope.moveKeyframes(copy, currentFrame, newFrame);
            pushKeyframeChange(copy, false); // commit once
            currentFrame = newFrame;
          }

          if (scope.Qt) {
            timeline.FinalizeKeyframeDrag(objType, objId);
          }

          restoreUserSelect();
        }
      });

      scope.$on("$destroy", function () {
        exitDragMode();
        restoreUserSelect();
      });
    }
  };
});
