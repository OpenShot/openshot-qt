/**
 * @file
 * @brief AngularJS App (initializes angular application)
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

// Initialize Angular application
/*global App, angular, timeline, init_mixin*/
const App = angular.module("openshot-timeline", ["ui.bootstrap", "ngAnimate"]);


// Wait for document ready event
$(document).ready(function () {

  const body_object = $("body");

  // Initialize Qt Mixin (WebEngine or WebKit)
  init_mixin();

  // Ensure caching thread is resumed on any mouse-up event during scrubbing
  $(document).on("mouseup", function () {
    if (body_object.scope().Qt) {
      timeline.EnableCacheThread();
    }
  });

  /// Capture window resize event, and resize scrollable track divs and playhead-line height
  (function () {
    const trackControls   = document.getElementById("track_controls");
    const scrollTracks    = document.getElementById("scrolling_tracks");
    const trackContainer  = document.getElementById("track-container");
    const playheadLine    = document.querySelector(".playhead-line");

    function syncAll() {
      // Resize both control and tracks container to fill window height
      if (trackControls && scrollTracks) {
        const offsetTop = trackControls.getBoundingClientRect().top;
        const newH = window.innerHeight - offsetTop;
        trackControls.style.height   = newH + "px";
        scrollTracks.style.height    = newH + "px";
      }
      // Adjust playhead-line height to match track stack
      if (trackContainer && playheadLine) {
        const h = trackContainer.getBoundingClientRect().height;
        playheadLine.style.height = h + "px";
      }
      // Adjust snapping-line height to match track stack
      const snappingLine = document.querySelector(".snapping-line");
      if (trackContainer && snappingLine) {
        const h = trackContainer.getBoundingClientRect().height;
        snappingLine.style.height = h + "px";
      }
    }

    // Re-sync on window resize
    window.addEventListener("resize", syncAll);

    // Observe structural changes in the track container
    if (window.ResizeObserver && trackContainer) {
      new ResizeObserver(syncAll).observe(trackContainer);
    } else if (trackContainer) {
      new MutationObserver(syncAll).observe(trackContainer, { childList: true });
    }

    // Observe Angular's style override on playhead-line
    if (window.MutationObserver && playheadLine) {
      new MutationObserver(syncAll).observe(playheadLine, { attributes: true, attributeFilter: ["style"] });
    }

    // Observe Angular's style override on snapping-line
    const snappingLine = document.querySelector(".snapping-line");
    if (window.MutationObserver && snappingLine) {
      new MutationObserver(syncAll).observe(snappingLine, { attributes: true, attributeFilter: ["style"] });
    }

    // Initial sync
    syncAll();
  })();
});
