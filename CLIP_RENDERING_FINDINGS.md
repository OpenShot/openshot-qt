# Clip Rendering & Thumbnail Bug — Investigation Findings

## Problem Statement

When clips are added to the timeline (especially after AI tagging/indexing, or when dragged right), the **clip section size does not match the actual clip duration**, and **thumbnails are broken/wrong**.

---

## Investigation History

Multiple sessions investigated different theories. All were tested and either disproved or insufficient:

| Session | Theory | Result |
|---------|--------|--------|
| 1 | C++ reader contamination during drag | **Disproved** — readers are fine |
| 2 | Reader sanitization in clip.py | **No effect** |
| 3 | Drag preview architecture (ghost dicts vs real clips in base.py) | **Rewrote entirely** — did not fix the visual problem |
| 4 | Clip painter regressions in paint/clip.py | **Identified 10+ regressions** — wholesale copy from upstream compiled & launched but **still did not fix it visually** |

---

## Root Cause Analysis — What Was Found

### Comparison Method

Used upstream `openshot-qt` (branch `develop`) as reference, compared against `zenvi-core` (branch `harkit-new`). Full diff of `paint/clip.py` showed **220+ lines of differences** across the clip rendering pipeline.

### Key Differences Found in `paint/clip.py`

These are the concrete code differences between upstream openshot-qt and zenvi-core's clip painter at `src/windows/views/timeline_backend/paint/clip.py`:

#### 1. Missing `invalidate_clip_thumbnails` Method
- **Upstream**: Has a 43-line method for selective thumbnail cache invalidation
- **Zenvi-core**: Deleted entirely
- **Impact**: Stale thumbnails persist when they should be refreshed

#### 2. `_fill_clip_background` — Missing Rounded Corners & Overlay
- **Upstream**: Uses `_clip_fill_path` (QPainterPath with rounded corners), passes `segment_info` parameter, draws a top overlay gradient (`top_overlay` / `top_overlay2` from theme)
- **Zenvi-core**: Uses plain `fillRect`, no segment info, no rounded corners, no top overlay
- **Impact**: Clips render as flat rectangles without the polished upstream appearance

#### 3. CRITICAL — Thumbnail Slot Width Clamping
- **Upstream**: `thumb_w = max(min_width, thumb_w)` — keeps nominal width, allows slots to extend beyond clip boundary (painter clips them)
- **Zenvi-core**: `thumb_w = max(min_width, min(thumb_w, clip_width))` — clamps to clip_width
- **Impact**: Short clips get compressed thumbnail slots. During trimming, slot count oscillates as thumb_w keeps recalculating against shrinking clip_width

#### 4. CRITICAL — Missing Thumbnail Vertical Positioning
- **Upstream**: Nudges thumbnails down on taller tracks using `baseline_clip_height` logic to keep thumbnails vertically centered
- **Zenvi-core**: Deleted all vertical positioning logic
- **Impact**: Thumbnails float to top of tall tracks instead of centering

#### 5. CRITICAL — Slot Interval for "entire" Style
- **Upstream**: Uses `theme_thumb_w` (the nominal theme width) for slot interval calculation, adds frame-boundary snapping
- **Zenvi-core**: Uses the clamped `thumb_w` for interval
- **Impact**: Slot positions shift/oscillate during trimming operations because the interval depends on the current clip width

#### 6. CRITICAL — Missing Start-End Overlap Protection
- **Upstream**: Suppresses the end thumbnail slot when the clip is too short (prevents start and end thumbnails from overlapping)
- **Zenvi-core**: Always adds both start and end slots regardless of clip width
- **Impact**: On short clips, start and end thumbnails overlap each other

#### 7. CRITICAL — Simplified `sample_time` Logic
- **Upstream**: Has style-specific sampling — edge slots (start/end) use trim edges, "entire" style slots use the slot's start position
- **Zenvi-core**: Uses a clamped center calculation for all styles
- **Impact**: Thumbnails show wrong frames, especially during trim operations where edge frames jump

#### 8. Missing `_suspend_thumbnail_requests` Check
- **Upstream**: Checks `self.w._suspend_thumbnail_requests` before issuing new thumbnail fetches
- **Zenvi-core**: No such check
- **Impact**: Thumbnails continue being requested during operations that should pause them (drags, bulk operations), causing performance issues and visual glitches

#### 9. Border Pen Fallback
- **Upstream**: Uses the passed `pen` argument for border strokes (supports locked-track dimming)
- **Zenvi-core**: Always uses the standard pen, ignoring the passed argument
- **Impact**: Locked tracks don't get dimmed borders

#### 10. Missing Locked-Track Dimming
- **Upstream**: Calls `self.w._is_track_locked(track_num)` and applies `self.dimmed_pen` for locked tracks
- **Zenvi-core**: No locked-track awareness in the painter
- **Impact**: Minor visual difference (locked tracks look same as unlocked)

### Differences Found in `timeline.py` — `addClip` Method

#### 11. Reader Assignment
- **Upstream**: `new_clip["reader"] = file.data` — uses the file's data dict as the reader
- **Zenvi-core**: Keeps the native openshot.Clip reader object, only injects `media_type`
- **Impact**: Thumbnail system reads fps/duration from the reader dict. Wrong structure could cause wrong thumbnail frame calculations

#### 12. Missing `auto_transition` Support
- **Upstream**: `addClip` accepts `auto_transition=False` param, passes `_auto_transition` flag through to `update_clip_data`, which then calls `_find_missing_transition_details` + `add_missing_transition` to auto-create fade transitions when clips overlap
- **Zenvi-core**: No auto_transition parameter, no `_find_missing_transition_details` method
- **Impact**: Overlapping clips don't get automatic transitions

### Differences Found in `base.py` — Drag Preview Architecture

#### 13. Drag Preview: Real Clips vs Ghost Dicts
- **Upstream**: During drag-from-files-panel, creates lightweight **ghost dictionaries** (never added to the openshot timeline) and paints them with `_paint_drag_preview` using simple rectangles
- **Zenvi-core**: Creates **real openshot.Clip objects** during drag preview, which get added to the timeline and can contaminate state
- **Impact**: Was investigated and rewritten in session 3, but the rewrite alone didn't fix the visual issues

---

## Dependencies Required by Upstream `paint/clip.py`

When copying the upstream clip painter, these supporting changes are needed:

### In `paint/base.py`
```python
# Add to imports
from PyQt5.QtGui import QColor, QPen

# Add methods to BasePainter class
@staticmethod
def dimmed_color(color, amount=0.6, desaturate=0.5):
    """Return a dimmed, desaturated variant of the given QColor."""
    h, s, l, a = color.getHslF()
    s = max(0.0, s * (1.0 - desaturate))
    l = l * amount
    c = QColor()
    c.setHslF(h, s, l, a)
    return c

def dimmed_pen(self, pen, amount=0.6, desaturate=0.5):
    """Return a copy of *pen* with a dimmed colour."""
    p = QPen(pen)
    p.setColor(self.dimmed_color(pen.color(), amount, desaturate))
    return p
```

### In `theme.py` — `ClipTheme` Class
```python
# Add to ClipTheme dataclass fields
top_overlay: QColor = QColor()
top_overlay2: QColor = QColor()
```

And add theme loading for CSS selector `.clip_top`:
```python
# After thumb_height loading, add:
_apply_gradient_with_fallback(
    ".clip_top", "background",
    lambda g: (
        setattr(self.clip, "top_overlay", g.stops[0].color if g.stops else QColor()),
        setattr(self.clip, "top_overlay2", g.stops[-1].color if len(g.stops) > 1 else QColor()),
    ),
    lambda: None,
)
```

### In `qwidget/track.py`
```python
# Add method to the track widget class
def _is_track_locked(self, track_num):
    """Return True if the given track number is locked."""
    for track in self.window.timeline.timeline.Tracks():
        if track.number() == track_num:
            return track.lock
    return False
```

---

## What Was Tried and Failed

### Attempt: Copy Upstream `paint/clip.py` Wholesale + All Dependencies
- Copied upstream `paint/clip.py` (1569 lines) over zenvi-core's version (1397 lines)
- Added `dimmed_color`/`dimmed_pen` to `paint/base.py`
- Added `top_overlay`/`top_overlay2` to `theme.py` + CSS loading
- Added `_is_track_locked` to `track.py`
- Fixed `addClip` reader to `file.data`
- Added `auto_transition` + `_find_missing_transition_details` to `timeline.py`
- **Result**: All files compiled, app launched with no errors, but **visual problem persisted**

---

## What Has NOT Been Investigated

These areas may contain the actual root cause:

1. **The CSS/theme files themselves** — Do zenvi-core's stylesheets define clip dimensions differently? Is `thumb_height`, `clip_height`, or track spacing different?

2. **The geometry module** (`timeline_backend/geometry/`) — This module calculates pixel positions from time values. If the pixels-per-second scale or track height calculations differ, clips would render at wrong sizes regardless of painter code.

3. **The `file.data` structure** — Does zenvi-core's File model produce different data than upstream? If `fps`, `duration`, `width`, `height` are wrong in `file.data`, thumbnails would be calculated against wrong values.

4. **The QWidget track layout** — Track height, spacing, and how clips are positioned within tracks. The issue might be in how the QWidget lays out clip rectangles, not in how they're painted.

5. **JavaScript/WebEngine timeline** — If zenvi-core has a hybrid JS+QWidget timeline, the JS side might be setting clip properties that conflict with the QWidget painter.

6. **The thumbnail cache/worker** — The thumbnail fetching system itself. Even with correct slot positions, if the worker returns wrong-sized or wrong-frame thumbnails, they'll look broken.

7. **Clip data flow from AI tagging** — The AI tagging/indexing pipeline may be modifying clip data in ways that affect rendering (e.g., changing start/end/position values, or adding metadata that interferes with the rendering pipeline).

8. **The actual openshot timeline object state** — Using `timeline.Json()` to dump the actual clip positions/durations and comparing against what's visually rendered would reveal if the issue is in data vs rendering.

---

## Recommended Next Steps

1. **Debug with print statements**: Add logging to `_fill_clip_background` and `_get_thumbnail_slots` to print the actual pixel rectangles being drawn, and compare against expected values.

2. **Dump timeline JSON**: After adding a clip, call `self.window.timeline.timeline.Json()` and inspect the clip's `position`, `start`, `end`, `layer` values — verify they match what was intended.

3. **Compare geometry module**: Diff `zenvi-core/src/windows/views/timeline_backend/geometry/` against `openshot-qt/src/windows/views/timeline_backend/geometry/` to find any scale/position calculation differences.

4. **Compare theme/CSS**: Diff the stylesheet files to check if track heights, clip heights, or thumbnail sizes are defined differently.

5. **Test with a simple clip**: Create a minimal test — one 10-second video clip, add to timeline, screenshot — to isolate whether the bug is clip-type-specific or universal.
