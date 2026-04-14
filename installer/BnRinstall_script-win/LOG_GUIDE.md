# Log Guide and Step-by-Step Walkthrough

This project lives or dies on whether the log tells the truth. The installer is strongest when the summary, artifacts, and runtime log all agree.

## A successful OpenShot runtime log means this

If you see a log like the one below, that means the build made it through the expensive parts and OpenShot actually launched.

```text
Loaded modules from: C:\OpenShotBuild\openshot-qt\src
INFO app: OpenShot (version 3.5.1)
INFO app: libopenshot version: 0.7.0
INFO ui_util: Initializing UI for MainWindow
INFO preview_thread: QThread Start Method Invoked
INFO app: OpenShot's session ended
```

That is not a fake pass. That is a real launch.

## Walkthrough of the successful runtime sequence

### `Loaded modules from: C:\OpenShotBuild\openshot-qt\src`
The launcher found the OpenShot Python application source tree and added it to the module search path.

### `INFO app: Starting new session`
OpenShot booted into a fresh app session. You are past the launcher and into the application.

### `INFO app: OpenShot (version 3.5.1)`
The Python app started and is reporting its own version. That means the top-level OpenShot app code is alive.

### `INFO app: libopenshot version: 0.7.0`
The Python app was able to talk to the native `libopenshot` binding. This is one of the biggest milestones in the whole build.

### `INFO app: python version: ... / qt5 version: ... / pyqt5 version: ...`
These lines tell you the active runtime stack. They are useful when you need to compare a working box with a failing one.

### `INFO project_data: Setting profile to HD 720p 30 fps`
Default project data loaded correctly.

### `INFO language: ...`
Language detection ran. Usually harmless and informational.

### `INFO logger_libopenshot: Connecting to libopenshot with debug port: 5556`
The Python side connected to the native logging/debug interface.

### `INFO ui_util: Initializing UI for MainWindow`
The actual desktop UI is being assembled. This is the line that tells you the app made it past imports and into real GUI startup.

### `INFO thumbnail: Starting thumbnail server listening on ...`
Background support services are starting. Normal.

### `WARNING updates: Cannot add existing listener ...`
This is noisy, but not fatal. It means a listener registration was attempted twice.

### `INFO sentry: Sentry initialized ...`
Error reporting initialized successfully. Nice to have, not required for a launch.

### `INFO generation_service: ComfyUI check failed at http://127.0.0.1:8188 ...`
This is also not a launch blocker. It just means a local ComfyUI service was not running.

### `INFO main_window: InitCacheSettings` and cache lines
The app is configuring preview/cache behavior. This is normal startup work.

### `INFO preview_thread: QThread Start Method Invoked`
The preview/render thread came online.

### `INFO main_window: Cleared temporary files: ...`
The app cleaned its temp folders. Good housekeeping, not a warning.

### `INFO theme: Setting Fusion dark palette`
The UI theme loaded.

### `INFO main_window: recover_backup`
The app checked for recovery state/backups.

### `INFO video_widget: ...`
The preview widget initialized and knows its aspect ratio.

### `INFO timeline: Adjusting max size of preview image ...`
Timeline preview resources are live.

### Shutdown block

```text
INFO main_window: ---------------- Shutting down -----------------
INFO thumbnail: Shutting down thumbnail server
INFO logger_libopenshot: Shutting down libopenshot logger
INFO preview_thread: Stopping preview thread
INFO app: OpenShot's session ended
```

This is a clean shutdown sequence. It means the app did not just vanish; it exited and tore down its background pieces deliberately.

## Installer stage summary walkthrough

The installer summary is the other half of the truth.

### `PASS Prerequisites`
Windows support, admin/elevation path, WinGet, Git, and MSYS2 are ready.

### `PASS Dependencies`
The script updated MSYS2 metadata, read the live UCRT64 package list, and resolved/install the package capabilities it needed.

### `PASS Repositories`
The OpenShot source repositories are present.

### `PASS Build libopenshot-audio`
The audio layer built and installed.

### `PASS Build libopenshot`
The native video/binding layer built and the source-build import probe worked.

### `PASS Prepare openshot-qt`
The runtime bootstrap files were created and the launcher smoke test succeeded.

### `PASS Verification`
The build artifacts and launch route looked good enough to treat the run as ready.

## Fastest way to use the log when something breaks

1. Read the stage summary first.
2. Read the artifacts block next.
3. Open `openshot-installer.log`.
4. Search for the first red/FAIL line, not the last dramatic line.
5. Compare against the successful runtime flow above.

The first meaningful deviation is usually where the real problem starts.


See also: RELEASE_GUIDE.md for the public-release checklist and final QA pass.
