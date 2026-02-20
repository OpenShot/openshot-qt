# ✅ Manim Threading Fix - App No Longer Freezes

## Problem: App Becomes Unresponsive

When generating Manim videos, the entire app would freeze because:
1. LLM code generation (blocking, ~5-30 seconds)
2. Manim rendering (blocking, ~10-60 seconds per scene)
3. FFmpeg concatenation (blocking, ~5-10 seconds)

All of this happened **synchronously on the main thread**, freezing the Qt UI.

---

## Solution: Background Thread Processing

I've refactored the Manim generation to use **background threading**, similar to how music generation works.

### What Changed

**Before** (Synchronous - Freezes UI):
```python
def generate_manim_video_and_add_to_timeline(...):
    # Everything blocks the main thread
    code = llm.invoke(...)          # BLOCKS 5-30s
    render_scenes(...)              # BLOCKS 30-60s
    concatenate_videos(...)         # BLOCKS 5-10s
    add_to_timeline(...)
```

**After** (Asynchronous - UI Stays Responsive):
```python
class _ManimGenerationThread(QThread):
    def run(self):
        # All heavy work in background thread
        code = llm.invoke(...)
        render_scenes(...)
        concatenate_videos(...)
        # Signal when done

def generate_manim_video_and_add_to_timeline(...):
    thread = _ManimGenerationThread(...)
    thread.start()
    event_loop.exec_()  # Qt stays responsive
    # Add to timeline on main thread
```

---

## Key Features

### 1. Background Thread (`_ManimGenerationThread`)
- Extends `QThread` from PyQt5
- Runs all heavy processing in background
- Emits signals for progress updates
- Emits results when complete

### 2. Progress Updates
Real-time status bar messages:
- "Generating Manim code with AI..."
- "Rendering scene 1/3: Intro..."
- "Rendering scene 2/3: MainContent..."
- "Combining scenes..."

### 3. Non-Blocking Event Loop
Uses `QEventLoop` to:
- Keep Qt UI responsive
- Allow user to interact with app
- Show progress updates
- Wait for completion without freezing

### 4. Thread-Safe Communication
- **Thread → Main**: Via Qt signals (`finished_with_result`, `progress_update`)
- **Main → Thread**: Via thread initialization parameters
- **Main Thread Only**: File operations and timeline updates

---

## Code Structure

```python
# NEW: Background thread class
class _ManimGenerationThread(QThread):
    finished_with_result = pyqtSignal(list, str)  # paths, error
    progress_update = pyqtSignal(str)             # status message

    def run(self):
        # Generate code (background)
        # Render scenes (background)
        # Concatenate (background)
        # Emit result

# MODIFIED: Main function now uses thread
def generate_manim_video_and_add_to_timeline(...):
    # Create thread
    thread = _ManimGenerationThread(...)

    # Connect signals
    thread.finished_with_result.connect(on_done)
    thread.progress_update.connect(show_in_statusbar)

    # Start thread (non-blocking)
    thread.start()
    event_loop.exec_()

    # Add to project (main thread)
    app.window.files_model.add_files(paths)
    add_clip_to_timeline(...)
```

---

## Benefits

| Aspect | Before (Sync) | After (Async) |
|--------|---------------|---------------|
| **UI Responsiveness** | ❌ Frozen | ✅ Fully responsive |
| **Progress Updates** | ❌ None | ✅ Real-time status |
| **User Experience** | ❌ App appears hung | ✅ Professional feel |
| **Cancellation** | ❌ Impossible | ✅ Possible (future) |
| **Multi-tasking** | ❌ Blocked | ✅ Can do other work |

---

## Testing

### Before (Frozen UI):
1. Request Manim video
2. App freezes for 30-90 seconds
3. No feedback
4. User thinks app crashed
5. Finally completes

### After (Responsive UI):
1. Request Manim video
2. Status bar shows: "Generating Manim code with AI..."
3. App remains fully usable
4. Status updates: "Rendering scene 1/3..."
5. Status updates: "Rendering scene 2/3..."
6. Status updates: "Combining scenes..."
7. Completes with: "✅ Successfully rendered and added X clip(s)"

---

## Technical Details

### Thread Safety

**Safe (Background Thread):**
- LLM API calls
- File I/O (temp files)
- Subprocess execution (manim, ffmpeg)
- Code generation
- Video rendering

**Main Thread Only:**
- Qt UI updates
- Project file operations (`files_model.add_files`)
- Timeline modifications (`add_clip_to_timeline`)
- Query database operations (`File.get()`)

### Signal Flow

```
Background Thread          Signals              Main Thread
─────────────────         ─────────            ────────────
Generate code    ──────► progress_update  ──► Status bar
Render scene 1   ──────► progress_update  ──► Status bar
Render scene 2   ──────► progress_update  ──► Status bar
Combine videos   ──────► progress_update  ──► Status bar
Done!            ──────► finished_with     ──► Add to project
                         result                 Add to timeline
```

---

## Files Modified

**`src/classes/ai_manim_tools.py`**
- Added `_ManimGenerationThread` class (150+ lines)
- Modified `generate_manim_video_and_add_to_timeline()` to use thread
- Added Qt imports (`QThread`, `pyqtSignal`, `QEventLoop`)
- Added progress reporting
- Improved error handling

---

## Backward Compatibility

✅ **No breaking changes**
- Tool signature unchanged
- Return value format unchanged
- Works with existing agent code
- No changes needed in other files

---

## Future Enhancements (Optional)

1. **Cancel Button**: Allow user to cancel during rendering
2. **Progress Bar**: Show percentage instead of just status text
3. **Multiple Concurrent**: Allow multiple Manim generations simultaneously
4. **Preview Mode**: Show rendered scenes as they complete

---

## Summary

**Problem**: Manim generation blocked the main thread, freezing the entire app for 30-90 seconds.

**Solution**: Move all heavy processing to a background `QThread`, use Qt signals for progress updates, keep UI responsive.

**Result**: ✅ App stays responsive during Manim generation, professional user experience with real-time progress updates.

**Testing**: Try: "Create a manim video explaining the Pythagorean theorem" and notice the app remains fully usable during rendering!
