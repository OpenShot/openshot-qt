.. _keyboard_shortcut_ref:

Keyboard Shortcuts
==================
Find shortcuts by task below, or jump to the full reference. These are the
default assignments; customize them in :guilabel:`Edit → Preferences → Keyboard`
(:guilabel:`OpenShot Video Editor → Preferences` on macOS). See
:ref:`preferences_keyboard_ref` for details.

On macOS, use Command for shortcuts shown with Ctrl.

.. contents:: On this page
   :local:
   :depth: 2

.. _timeline_keyboard_ref:

Using the timeline with a keyboard
----------------------------------
Focus the timeline before selecting, moving, or trimming clips and transitions with these shortcuts.

Moving between panels
~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 60 40

   * - Action
     - Shortcut
   * - Focus Project Files
     - :kbd:`Shift+1`
   * - Focus the timeline
     - :kbd:`Shift+3`
   * - Focus Transitions
     - :kbd:`Shift+7`
   * - Focus Effects
     - :kbd:`Shift+8`
   * - Focus Emojis
     - :kbd:`Shift+9`
   * - Move to the next / previous control
     - :kbd:`Tab` / :kbd:`Shift+Tab`
   * - Focus the next / previous dock tab title without selecting it
     - :kbd:`Tab` / :kbd:`Shift+Tab`
   * - Move focus between dock tab titles
     - :kbd:`Left` / :kbd:`Right` while a title has focus
   * - Activate the focused dock tab and enter its first control
     - :kbd:`Space` or :kbd:`Enter`
   * - Browse Project Files, transitions, effects, or emojis
     - Arrow keys while the list has focus

Each grouped dock title is a separate Tab stop. Its normal focus style marks the
focused title (an underline in Cosmic Dusk);
moving focus does not change the selected dock. Activate a title to switch docks
and focus its first control. Clicking a dock tab also focuses its first control,
even if that tab is already selected. Only the active dock's visible controls participate
in the Tab sequence; hidden dock controls are skipped.

When focus is inside a dock, the underline stays beneath its active tab. When
you Tab between titles, the underline follows the focused title. The timeline itself is one
Tab stop; Tab does not visit each clip or transition.

The timeline's ruler and track headers, including their labels, dim when
unfocused. The clip area stays the same. In Cosmic Dusk, a blue underline marks
the focused dock's title text or active tab, and buttons show a blue focus
border. The untitled timeline dock has no underline.

Adding and applying assets
~~~~~~~~~~~~~~~~~~~~~~~~~~
The panel shortcuts above open the dock and focus its asset list directly.
Use the arrow keys to choose an asset, then :kbd:`Ctrl+Enter` to add or apply it.
Your existing browser selection is preserved; if nothing is selected, focusing
the browser selects its current item or the first available item.

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Panel / action
     - Shortcut
     - Result
   * - Project Files: add selected files
     - :kbd:`Ctrl+Enter`
     - Place files sequentially at the playhead, in browser order, on the target track.
   * - Effects: apply selected effects
     - :kbd:`Ctrl+Enter`
     - Apply to the selected timeline clips. Browsing effects keeps that clip selection.
   * - Transitions: add selected transitions
     - :kbd:`Ctrl+Enter`
     - Place at the playhead on the target track, using the default transition length.
   * - Emojis: add selected emoji
     - :kbd:`Ctrl+Enter`
     - Place at the playhead on the target track, using the default image length.
   * - Open the Add to Timeline dialog for selected files
     - :kbd:`Ctrl+Alt+A`
     - Choose placement and other options before adding the files.

The target is the selected timeline item's track, or the remembered track if
nothing is selected. With neither available, OpenShot uses the highest unlocked
track. The target track label appears **bold** while browsing assets. To change
it, select an item on the desired track or clear the timeline selection and click
the desired track before returning to the browser. A locked target blocks the
operation; effects also require selected clips on unlocked tracks.

Adding at the playhead uses normal OpenShot placement: it does not make room by
shifting later clips or overwrite their content. As with dragging a single clip,
an overlap can create an automatic transition. The playhead stays in place and
focus stays in the browser, so you can continue choosing assets. Press
:kbd:`Shift+3` to edit the newly added timeline items.

For example: :kbd:`Shift+1` → arrow keys → :kbd:`Ctrl+Enter` → :kbd:`Shift+3`.
The add/apply shortcut works in the asset list, not while typing in a filter or
renaming an item.

Moving the playhead
~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 60 40

   * - Action
     - Shortcut
   * - Step backward / forward one frame
     - :kbd:`Left` / :kbd:`Right`
   * - Step backward / forward five frames
     - :kbd:`Shift+Left` / :kbd:`Shift+Right`
   * - Go to the previous / next edit
     - :kbd:`Up` / :kbd:`Down`
   * - Jump to the start / end
     - :kbd:`Home` / :kbd:`End`
   * - Center the timeline on the playhead
     - :kbd:`Shift+C`
   * - Play / pause
     - :kbd:`Space`
   * - Play in reverse
     - :kbd:`J`
   * - Stop playback
     - :kbd:`K`
   * - Play forward
     - :kbd:`L`

Edit navigation uses the selected item's track, or the last clicked track if
nothing is selected. With no active track, it starts on the highest track
containing a clip or transition at the playhead, or the highest populated track in a gap.

Selecting clips and transitions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
These shortcuts select both clips and transitions. Selection brings an item into view without changing the zoom or playhead.

.. list-table::
   :header-rows: 1
   :widths: 60 40

   * - Action
     - Shortcut
   * - Select the previous / next item
     - :kbd:`Ctrl+Left` / :kbd:`Ctrl+Right`
   * - Select an item above / below
     - :kbd:`Ctrl+Up` / :kbd:`Ctrl+Down`
   * - Extend selection to the previous / next item
     - :kbd:`Ctrl+Shift+Left` / :kbd:`Ctrl+Shift+Right`
   * - Cycle through items under the playhead
     - :kbd:`D`
   * - Extend selection through items under the playhead
     - :kbd:`Ctrl+Shift+D`
   * - Select all / clear selection
     - :kbd:`Ctrl+A` / :kbd:`Ctrl+Shift+A`

**Left/right** follows the current track first. When no item remains in that
direction, it continues to the closest item start on another track.

**Up/down** looks above or below the selected item, preferring items that overlap
it in time. The nearest overlapping track wins. If nothing overlaps, the smallest
horizontal gap wins, then the nearest track. Ties on a track favor the closest
item center. Empty tracks and unrelated items farther to the side do not block
navigation. With no selection, the playhead supplies the starting position.

**Selection at the playhead** cycles from the highest track to the lowest, then
wraps to the top. Moving the playhead restarts the cycle. If no item is under it,
the selection stays unchanged. Extending selection keeps items already selected.

.. _moving-and-trimming-clips:

Moving clips and transitions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
These shortcuts move the selected clips and transitions when no trim edge is selected.

.. list-table::
   :header-rows: 1
   :widths: 60 40

   * - Action
     - Shortcut
   * - Move left / right one frame
     - :kbd:`,` / :kbd:`.`
   * - Move left / right five frames
     - :kbd:`Shift+,` / :kbd:`Shift+.`
   * - Move up / down one track
     - :kbd:`Alt+Up` / :kbd:`Alt+Down`

Track moves keep the selection's timing and can use empty tracks. A locked track
or the edge of the track list blocks the whole track move.

Trimming clips and transitions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Select a clip or transition, choose its left or right edge, then adjust that edge.

.. list-table::
   :header-rows: 1
   :widths: 60 40

   * - Action
     - Shortcut
   * - Select the left trim edge
     - :kbd:`[`
   * - Select the right trim edge
     - :kbd:`]`
   * - Move the selected edge left / right one frame
     - :kbd:`,` / :kbd:`.`
   * - Move the selected edge left / right five frames
     - :kbd:`Shift+,` / :kbd:`Shift+.`
   * - Leave trim mode and restore the timeline preview
     - :kbd:`Esc`

The selected edge has a fading highlight. Video Preview shows the first included
frame for the left edge or the last included frame for the right edge, updating
after each trim without moving the playhead. For transitions, the preview shows
the transition mask. Trims respect the available source
media and do not ripple other clips.

After leaving trim mode, comma/period move whole clips and transitions again.

Coming from another editor?
---------------------------
Compare a few everyday editing tasks with shortcuts you may already know.

The table shows OpenShot's Windows/Linux defaults, Adobe Premiere Pro and
DaVinci Resolve Windows defaults, and Final Cut Pro Mac defaults. On macOS,
OpenShot uses Command for shortcuts shown with Ctrl. Shortcuts in other editors
can vary with the version, keyboard layout, selected preset, and active panel.
Similar shortcuts can also behave differently on stacked or connected clips.

.. list-table:: Everyday editing shortcuts
   :header-rows: 1
   :widths: 24 19 19 19 19

   * - Task
     - OpenShot
     - Premiere Pro
     - DaVinci Resolve
     - Final Cut Pro
   * - Play / pause
     - Space
     - Space
     - Space
     - Space
   * - Reverse / stop / forward
     - J / K / L
     - J / K / L
     - J / K / L
     - J / K / L
   * - Previous / next frame
     - Left / Right
     - Left / Right
     - Left / Right
     - Left / Right
   * - Previous / next edit
     - Up / Down (active track)
     - Up / Down
     - Up / Down
     - Up / Down
   * - Focus media browser / project assets
     - Shift+1
     - Shift+1 (Project panel)
     - Not listed here
     - Cmd+1 (Browser)
   * - Focus timeline
     - Shift+3
     - Shift+3
     - Not listed here
     - Cmd+2
   * - Add source media at the playhead
     - Ctrl+Enter (place on target track)
     - Comma (insert); period (overwrite)
     - F9 (insert); F10 (overwrite)
     - W (insert); D (overwrite); Q (connect)
   * - Select previous / next clip
     - Ctrl+Left / Right
     - Ctrl+Up / Down
     - Ctrl+Left / Right
     - Cmd+Left / Right (same role; also moves playhead)
   * - Select clip above / below
     - Ctrl+Up / Down
     - No default listed here
     - Ctrl+Up / Down
     - Cmd+Up / Down
   * - Move selection up / down
     - Alt+Up / Down
     - Alt+Up / Down
     - Alt+Up / Down
     - Option+Up / Down (connected clips)
   * - Nudge left / right one frame
     - Comma / period
     - Alt+Left / Right
     - Comma / period
     - Comma / period
   * - Nudge by several frames
     - Shift+comma / period (5)
     - Alt+Shift+Left / Right (5)
     - Shift+comma / period (configurable; default 5)
     - Shift+comma / period (10)
   * - Select at playhead
     - D (cycles through stacked clips)
     - D
     - Shift+V (nearest clip/gap)
     - X selects a range; C selects under the pointer
   * - Split at playhead
     - Ctrl+K (selected clips)
     - Ctrl+K (targeted tracks)
     - Ctrl+B
     - Cmd+B
   * - Undo
     - Ctrl+Z
     - Ctrl+Z
     - Ctrl+Z
     - Cmd+Z
   * - Save project
     - Ctrl+S
     - Ctrl+S
     - Ctrl+S
     - Saves automatically

For complete shortcut lists and customization options, see the
`Premiere Pro keyboard reference <https://helpx.adobe.com/premiere/desktop/get-started/keyboard-shortcuts/default-keyboard-shortcuts.html>`_,
`DaVinci Resolve training guides <https://www.blackmagicdesign.com/products/davinciresolve/training>`_,
and `Final Cut Pro keyboard reference <https://support.apple.com/guide/final-cut-pro/ver90ba5929/mac>`_.



Mouse shortcuts
---------------
These gestures complement the keyboard shortcuts. In Project Files' Details
view, double-click the thumbnail column for the file actions below.

.. list-table::
   :header-rows: 1
   :widths: 35 35 30

   * - Action
     - Mouse gesture
     - Keyboard alternative
   * - Preview a file in Project Files
     - Double-click the file
     - :kbd:`Alt+P`
   * - Open file properties in Project Files
     - :kbd:`Ctrl` + double-click the file
     - :kbd:`Alt+I`
   * - Split a file in Project Files
     - :kbd:`Shift` + double-click the file
     - :kbd:`Alt+S`
   * - Select an item and everything to its right on the same track
     - :kbd:`Alt` + click the clip or transition
     - :kbd:`Alt+A` with an item selected
   * - Open properties for a timeline clip or transition
     - Double-click the item
     - :kbd:`U`
   * - Fit the whole timeline in view
     - Double-click the zoom slider
     - :kbd:`\\` or :kbd:`Shift+\\`

Full shortcut reference
-----------------------
These are the default shortcuts, including view shortcuts supplied by the menus. Your assignments in Preferences
may differ. On macOS, Command is used for shortcuts shown with Ctrl.

.. list-table:: Default keyboard shortcuts
   :header-rows: 1
   :widths: 44 28 28

   * - Action
     - Primary shortcut
     - Alternatives
   * - About OpenShot
     - :kbd:`Ctrl+H`
     -
   * - Add Marker
     - :kbd:`M`
     -
   * - Add or Apply Selected Asset
     - :kbd:`Ctrl+Enter`
     -
   * - Add to Timeline
     - :kbd:`Ctrl+Alt+A`
     -
   * - Add Track
     - :kbd:`Ctrl+Y`
     -
   * - Animated Title
     - :kbd:`Ctrl+Shift+T`
     -
   * - Ask a Question...
     - :kbd:`F4`
     -
   * - Center on Playhead
     - :kbd:`Shift+C`
     -
   * - Choose Profile
     - :kbd:`Ctrl+Alt+P`
     -
   * - Clear All Cache
     - :kbd:`Ctrl+Shift+ESC`
     -
   * - Clear History
     - :kbd:`Ctrl+Shift+H`
     -
   * - Clear Waveform Display Data
     - :kbd:`Ctrl+Shift+W`
     -
   * - Color View
     - :kbd:`Alt+Shift+2`
     -
   * - Copy
     - :kbd:`Ctrl+C`
     -
   * - Cut
     - :kbd:`Ctrl+X`
     -
   * - Delete Item
     - :kbd:`Delete`
     - :kbd:`Backspace`
   * - Delete Item (Ripple)
     - :kbd:`Shift+Delete`
     -
   * - Delete Optimized Videos
     - :kbd:`Ctrl+Shift+O`
     -
   * - Details View
     - :kbd:`Ctrl+Page Up`
     -
   * - Donate
     - :kbd:`F7`
     -
   * - Duplicate
     - :kbd:`Ctrl+Shift+/`
     -
   * - Edit Title
     - :kbd:`Alt+T`
     -
   * - Export Files
     - :kbd:`Ctrl+Shift+E`
     -
   * - Export Video
     - :kbd:`Ctrl+E`
     - :kbd:`Ctrl+M`
   * - Extend Selection at Playhead
     - :kbd:`Ctrl+Shift+D`
     -
   * - Extend Selection to Next Item
     - :kbd:`Ctrl+Shift+Right`
     -
   * - Extend Selection to Previous Item
     - :kbd:`Ctrl+Shift+Left`
     -
   * - Fast Forward
     - :kbd:`L`
     -
   * - File Properties
     - :kbd:`Alt+I`
     -
   * - Focus Effects
     - :kbd:`Shift+8`
     -
   * - Focus Emojis
     - :kbd:`Shift+9`
     -
   * - Focus Project Files
     - :kbd:`Shift+1`
     -
   * - Focus Timeline
     - :kbd:`Shift+3`
     -
   * - Focus Transitions
     - :kbd:`Shift+7`
     -
   * - Fullscreen
     - :kbd:`F11`
     -
   * - Import Files...
     - :kbd:`Ctrl+I`
     -
   * - Insert Keyframe
     - :kbd:`Alt+Shift+K`
     -
   * - Join our Community...
     - :kbd:`F5`
     -
   * - Jump To End
     - :kbd:`End`
     -
   * - Jump To Start
     - :kbd:`Home`
     -
   * - Launch Tutorial
     - :kbd:`F2`
     -
   * - Move Selection Down One Track
     - :kbd:`Alt+Down`
     -
   * - Move Selection Up One Track
     - :kbd:`Alt+Up`
     -
   * - New Project
     - :kbd:`Ctrl+N`
     -
   * - Next Edit Point
     - :kbd:`Down`
     -
   * - Next Five Frames
     - :kbd:`Shift+Right`
     -
   * - Next Frame
     - :kbd:`Right`
     -
   * - Next Marker
     - :kbd:`Shift+M`
     - :kbd:`Alt+Right`
   * - Nudge left (1 Frame)
     - :kbd:`,`
     -
   * - Nudge left (5 Frames)
     - :kbd:`Shift+,`
     -
   * - Nudge right (1 Frame)
     - :kbd:`.`
     -
   * - Nudge right (5 Frames)
     - :kbd:`Shift+.`
     -
   * - Open Help Contents
     - :kbd:`F1`
     -
   * - Open Project...
     - :kbd:`Ctrl+O`
     -
   * - Paste
     - :kbd:`Ctrl+V`
     -
   * - Play/Pause Toggle
     - :kbd:`Space`
     -
   * - Preferences
     - :kbd:`Ctrl+P`
     -
   * - Preview File
     - :kbd:`Alt+P`
     -
   * - Previous Edit Point
     - :kbd:`Up`
     -
   * - Previous Five Frames
     - :kbd:`Shift+Left`
     -
   * - Previous Frame
     - :kbd:`Left`
     -
   * - Previous Marker
     - :kbd:`Ctrl+Shift+M`
     - :kbd:`Alt+Left`
   * - Properties
     - :kbd:`U`
     -
   * - Quit
     - :kbd:`Ctrl+Q`
     -
   * - Razor Toggle
     - :kbd:`C`
     - :kbd:`B` or :kbd:`R`
   * - Recording View
     - :kbd:`Alt+Shift+3`
     -
   * - Redo
     - :kbd:`Ctrl+Shift+Z`
     -
   * - Report a Bug...
     - :kbd:`F3`
     -
   * - Rewind
     - :kbd:`J`
     -
   * - Save Current Frame
     - :kbd:`Shift+E`
     -
   * - Save Project
     - :kbd:`Ctrl+S`
     -
   * - Save Project As...
     - :kbd:`Ctrl+Shift+S`
     -
   * - Select All
     - :kbd:`Ctrl+A`
     -
   * - Select Item Above
     - :kbd:`Ctrl+Up`
     -
   * - Select Item at Playhead
     - :kbd:`D`
     -
   * - Select Item Below
     - :kbd:`Ctrl+Down`
     -
   * - Select Item (Ripple)
     - :kbd:`Alt+A`
     -
   * - Select Left Item Edge
     - :kbd:`[`
     -
   * - Select Next Item
     - :kbd:`Ctrl+Right`
     -
   * - Select None
     - :kbd:`Ctrl+Shift+A`
     -
   * - Select Previous Item
     - :kbd:`Ctrl+Left`
     -
   * - Select Right Item Edge
     - :kbd:`]`
     -
   * - Share Feedback...
     - :kbd:`F8`
     -
   * - Simple View
     - :kbd:`Alt+Shift+0`
     -
   * - Slice All: Keep Both Sides
     - :kbd:`Ctrl+Shift+K`
     -
   * - Slice All: Keep Left Side
     - :kbd:`Ctrl+Shift+J`
     -
   * - Slice All: Keep Right Side
     - :kbd:`Ctrl+Shift+L`
     -
   * - Slice Selected: Keep Both Sides
     - :kbd:`Ctrl+K`
     -
   * - Slice Selected: Keep Left (Ripple)
     - :kbd:`W`
     -
   * - Slice Selected: Keep Left Side
     - :kbd:`Ctrl+J`
     -
   * - Slice Selected: Keep Right (Ripple)
     - :kbd:`Q`
     -
   * - Slice Selected: Keep Right Side
     - :kbd:`Ctrl+L`
     -
   * - Snapping Toggle
     - :kbd:`S`
     -
   * - Split File
     - :kbd:`Alt+S`
     -
   * - Stop Playback
     - :kbd:`K`
     -
   * - Thumbnail View
     - :kbd:`Ctrl+Page Down`
     -
   * - Timing Toggle
     - :kbd:`T`
     -
   * - Title
     - :kbd:`Ctrl+T`
     -
   * - Translate this Application...
     - :kbd:`F6`
     -
   * - Undo
     - :kbd:`Ctrl+Z`
     -
   * - Update Available
     - :kbd:`F9`
     -
   * - View Toolbar
     - :kbd:`Ctrl+Shift+B`
     -
   * - Zoom In
     - :kbd:`=`
     - :kbd:`Ctrl+=`
   * - Zoom Out
     - :kbd:`-`
     - :kbd:`Ctrl+-`
   * - Zoom to Timeline
     - :kbd:`\\`
     - :kbd:`Shift+\\`
