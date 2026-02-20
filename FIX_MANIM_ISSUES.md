# Fixing Manim and WebEngine Issues

## Issue 1: Manim Installation Failed ❌

### Problem
Manim installation failed due to missing system dependencies:
```
fatal error: cairo.h: No such file or directory
```

### Solution: Install System Dependencies

**Step 1: Install required packages**
```bash
sudo apt-get update
sudo apt-get install -y \
    libcairo2-dev \
    libpango1.0-dev \
    ffmpeg \
    pkg-config \
    python3-dev \
    texlive-latex-base \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-latex-extra
```

**Step 2: Install Manim in virtual environment**
```bash
cd /home/vboxuser/Projects/Flowcut
source .venv/bin/activate
pip install manim
```

**Step 3: Verify installation**
```bash
manim --version
```

You should see output like: `Manim Community v0.19.1`

---

## Issue 2: WebEngine GPU Error 🖥️

### Problem
```
ERROR:command_buffer_proxy_impl.cc(141)] ContextResult::kTransientFailure:
Failed to send GpuChannelMsg_CreateCommandBuffer.
```

This is a Qt WebEngine GPU acceleration issue, common in virtual machines or systems without proper GPU access.

### Solution: Disable GPU Acceleration for WebEngine

**Option A: Environment Variable (Recommended)**

Add to your launch script or `.bashrc`:
```bash
export QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu --no-sandbox --disable-software-rasterizer"
```

Then run Flowcut:
```bash
cd /home/vboxuser/Projects/Flowcut
source .venv/bin/activate
export QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu --no-sandbox --disable-software-rasterizer"
python src/launch.py
```

**Option B: Modify Launch Script**

Create a wrapper script `/home/vboxuser/Projects/Flowcut/run_flowcut.sh`:

```bash
#!/bin/bash
cd /home/vboxuser/Projects/Flowcut
source .venv/bin/activate
export QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu --no-sandbox --disable-software-rasterizer"
python src/launch.py
```

Make it executable:
```bash
chmod +x run_flowcut.sh
./run_flowcut.sh
```

**Option C: System-Wide Setting**

Add to `~/.bashrc` or `~/.profile`:
```bash
export QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu --no-sandbox --disable-software-rasterizer"
```

Then restart your terminal.

---

## Testing Manim After Installation

Once both issues are fixed, test Manim generation:

1. **Launch Flowcut** with GPU acceleration disabled
2. **Open AI Chat** window
3. **Try a Manim request**:
   - "Create a manim video explaining the Pythagorean theorem"
   - "Generate an educational animation about the second law of thermodynamics"

### Expected Behavior:
✅ Agent immediately calls `generate_manim_video_tool`
✅ Code is generated automatically
✅ Multiple scenes are rendered
✅ Videos are added to timeline
✅ No more "Would you like me to provide the code?" messages
✅ No GPU errors in console

---

## Alternative: Use CPU-Only Rendering

If you can't install the full LaTeX stack (it's large ~1GB), Manim will still work but without fancy mathematical typesetting:

```bash
# Minimal installation (without LaTeX)
sudo apt-get install libcairo2-dev libpango1.0-dev ffmpeg pkg-config python3-dev
pip install manim
```

Mathematical formulas will use simpler text rendering instead of LaTeX.

---

## Troubleshooting

### Manim Still Fails?
Check Manim logs:
```bash
source .venv/bin/activate
manim --version  # Should show version
manim example_scenes.py SquareToCircle  # Test render
```

### WebEngine Still Shows GPU Errors?
1. Verify environment variable is set:
   ```bash
   echo $QTWEBENGINE_CHROMIUM_FLAGS
   ```

2. Check Qt version:
   ```bash
   python -c "from PyQt5.QtCore import QT_VERSION_STR; print(QT_VERSION_STR)"
   ```

3. Try with software rendering:
   ```bash
   export QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu --no-sandbox --disable-software-rasterizer --in-process-gpu"
   ```

### Still Having Issues?
Check the full logs:
```bash
cd /home/vboxuser/Projects/Flowcut
source .venv/bin/activate
python src/launch.py 2>&1 | tee flowcut.log
```

Then search the log for errors.

---

## Summary

**Two separate issues:**

1. **Manim not installed** → Install system dependencies + pip install manim
2. **WebEngine GPU error** → Disable GPU acceleration with environment variable

Both are now fixed! 🎉
