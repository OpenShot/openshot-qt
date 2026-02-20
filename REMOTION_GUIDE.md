# Remotion Video Generation Guide for Flowcut

This guide explains how to set up, configure, and use Remotion for video generation in Flowcut.

## Overview

Flowcut now supports two video generation services:
- **Runware (Vidu)**: Cloud-based AI video generation
- **Remotion**: Programmatic video generation with React

This integration allows you to generate videos from text prompts using either service directly from the Flowcut chatbot and timeline.

---

## Prerequisites

Before using Remotion in Flowcut, ensure you have:

1. **Remotion API Server Running**
   - The Remotion API server must be running locally or on a remote server
   - Default URL: `http://localhost:4500/api/v1`

2. **Remotion API Key**
   - Obtain an API key from your Remotion API server
   - This is used to authenticate requests

3. **Python Dependencies**
   - `requests` library (should already be installed with Flowcut)

---

## Setup Instructions

### Quick Setup for Local Development

If you have the Remotion server in `../remotion` (already configured):

```bash
# The server should already be running. If not:
cd ../remotion
npm start

# In a new terminal, configure Flowcut:
cd core
python3 setup_local_remotion.py
```

**Then in Flowcut Preferences:**
- **Video Generation Service**: `Remotion`
- **Remotion API Key**: `dev-key-change-me`
- **Remotion API Base URL**: `http://127.0.0.1:4500/api/v1`

### Step 1: Start Remotion API Server

The Remotion server should already be running. To verify:

```bash
curl http://127.0.0.1:4500/api/v1/health
# Should return: {"status":"healthy",...}
```

If not running, start it:

```bash
cd ../remotion
npm install  # First time only
npm start
```

The server runs on `http://127.0.0.1:4500` by default with API key `dev-key-change-me`.

### Step 2: Configure Flowcut

1. **Quick Setup Script** (Recommended)
   ```bash
   python3 setup_local_remotion.py
   ```
   Follow the instructions displayed.

2. **Manual Setup**
   - Launch Flowcut
   - Go to `Edit > Preferences` (or `Preferences` menu on macOS)
   - Click on the `AI` category in the left sidebar
   - **Video Generation Service**: Select `Remotion` from the dropdown
   - **Remotion API Key**: Enter `dev-key-change-me` (local dev key)
   - **Remotion API Base URL**: Enter `http://127.0.0.1:4500/api/v1`
   - Click `OK` to save

### Step 3: Test It!

```bash
# Test from command line
python3 test_local_remotion.py

# Or test in Flowcut:
# 1. Open AI Chat
# 2. Type: "Generate a video showing a modern office"
# 3. Watch it render and add to timeline!
```

---

## Available Templates

The local Remotion server includes these templates:

- **product-launch** (default) - Versatile template for general content
- **globe-travel** - Travel and location-based videos
- **code-showcase** - Technical/coding content
- **desktop-app-demo** - Software demonstrations

The integration automatically uses `product-launch` as it works well for most prompts.

## Using Remotion in Flowcut

### Method 1: Chatbot Commands

Open the AI chat panel and use natural language commands:

```
Generate a video showing a modern tech startup office
```

```
Create a 5-second video of a sunset over mountains
```

```
Make a video with text "Welcome to Flowcut" and add it to the timeline
```

The chatbot will:
1. Send your prompt to the Remotion API
2. Wait for video generation to complete
3. Download the generated video
4. Add it to your timeline automatically

### Method 2: Timeline Integration

In a future update, Remotion generation will be directly integrated into the timeline context menu.

---

## How It Works

### Architecture

```
Flowcut Chatbot
    ↓
AI Agent Runner
    ↓
generate_video_and_add_to_timeline()
    ↓
_RemotionGenerationThread (Worker Thread)
    ↓
remotion_client.py (API Client)
    ↓
Remotion API Server
    ↓
Video Rendered & Downloaded
    ↓
Added to Flowcut Timeline
```

### Workflow Details

1. **User Request**: User asks the chatbot to generate a video
2. **Service Selection**: Flowcut checks the `video-generation-service` setting
3. **API Call**: If Remotion is selected:
   - Creates a `_RemotionGenerationThread` worker
   - Calls `render_from_repo()` with the prompt
   - Uses a default Remotion template (configurable)
4. **Polling**: Thread polls the Remotion API for job status
5. **Download**: Once complete, downloads the video file
6. **Timeline Integration**: Adds the video to the Flowcut project and timeline

---

## API Configuration

### Remotion Client Functions

The Remotion integration uses two main API functions:

#### 1. `render_from_repo()`

Generates video from a GitHub repository template:

```python
result = render_from_repo(
    api_key="your-api-key",
    repo_url="https://github.com/remotion-dev/template-still",
    template="default",
    user_input="Your prompt here",
    codec="h264",
    base_url="http://localhost:4500/api/v1",
    timeout_seconds=300,
    poll_callback=progress_callback
)
```

**Parameters:**
- `api_key`: Your Remotion API key
- `repo_url`: GitHub repo with Remotion template
- `template`: Template name to use
- `user_input`: Custom user prompt/text
- `codec`: Video codec (h264, h265, vp8, vp9)
- `base_url`: API endpoint URL
- `timeout_seconds`: Max wait time for render
- `poll_callback`: Optional progress callback function

#### 2. `render_from_sonar()`

Generates video from Perplexity Sonar research data:

```python
result = render_from_sonar(
    api_key="your-api-key",
    query="Research question",
    sonar_data={
        "content": "Research content...",
        "citations": [...],
        "images": [...],
        "relatedQuestions": [...]
    },
    visualization_style="research-summary",
    duration=10,
    base_url="http://localhost:4500/api/v1"
)
```

**Parameters:**
- `api_key`: Your Remotion API key
- `query`: Research query/question
- `sonar_data`: Perplexity Sonar API response data
- `visualization_style`: "research-summary", "data-cards", or "timeline"
- `duration`: Video duration in seconds
- `base_url`: API endpoint URL

---

## Troubleshooting

### Issue: "Remotion is not configured"

**Solution:**
- Open Preferences > AI
- Enter your Remotion API key
- Verify the base URL is correct
- Click OK to save

### Issue: App becomes unresponsive

**Cause:** This was the original issue - prompts were routing to Runware instead of Remotion.

**Solution:**
- Ensure you're on the latest version (after the fix commit)
- Verify "Video Generation Service" is set to "Remotion" in preferences
- The fix routes requests correctly and uses a worker thread to prevent UI freezing

### Issue: "Network error: Connection refused"

**Solution:**
- Ensure the Remotion API server is running
- Check the server URL in preferences
- Verify firewall/network settings allow localhost connections
- Test the server: `curl http://localhost:4500/api/v1/health`

### Issue: "Authentication failed. Check your API key"

**Solution:**
- Verify your API key is correct
- Check for extra spaces or characters
- Re-enter the API key in preferences

### Issue: "Render timeout after 300s"

**Solution:**
- Your video is taking too long to render
- Check Remotion server logs for errors
- Consider reducing video duration
- Check server resources (CPU/memory)

### Issue: Generated video not appearing on timeline

**Solution:**
- Check Flowcut's project files directory
- Look in system temp folder: `/tmp/flowcut_generated_*.mp4`
- Verify disk space is available
- Check Flowcut logs for file import errors

---

## Advanced Configuration

### Custom Remotion Templates

To use custom Remotion templates:

1. Modify `_RemotionGenerationThread.run()` in `src/classes/ai_openshot_tools.py`
2. Change the `repo_url` parameter to your template repository
3. Update the `template` parameter as needed

Example:

```python
result = render_from_repo(
    api_key=self._api_key,
    repo_url="https://github.com/your-org/custom-template",
    template="my-template",
    user_input=self._prompt,
    # ... other parameters
)
```

### Remote Remotion Server

To use a remote Remotion server:

1. Open Preferences > AI
2. Update **Remotion API Base URL** to your remote server:
   - Example: `https://remotion.yourdomain.com/api/v1`
3. Ensure the server is accessible from your network
4. Update firewall rules if needed

### Progress Callbacks

Progress updates are displayed in the Flowcut status bar during generation. To customize:

1. Edit the `on_progress` callback in `_RemotionGenerationThread.run()`
2. Emit custom signals or update UI elements as needed

---

## Code Reference

### Key Files

- **`src/classes/video_generation/remotion_client.py`**: API client for Remotion
- **`src/classes/video_generation/remotion_worker.py`**: QThread worker for Remotion
- **`src/classes/ai_openshot_tools.py`**: Integration with Flowcut tools (line ~625-695)
- **`src/settings/_default.settings`**: Configuration settings (line ~1610-1640)

### Example: Manual API Call

You can test the Remotion API directly from Python:

```python
from classes.video_generation.remotion_client import render_from_repo

result = render_from_repo(
    api_key="your-api-key-here",
    repo_url="https://github.com/remotion-dev/template-still",
    template="default",
    user_input="Hello from Flowcut!",
    base_url="http://localhost:4500/api/v1"
)

print("Video URL:", result['videoUrl'])
print("Download URL:", result['downloadUrl'])
print("Job ID:", result['jobId'])
```

---

## Switching Between Services

You can easily switch between Runware and Remotion:

1. Open Preferences > AI
2. Change **Video Generation Service** dropdown:
   - Select `Runware (Vidu)` for Runware
   - Select `Remotion` for Remotion
3. Ensure the appropriate API key is configured
4. Click OK to save

No restart required - changes take effect immediately.

---

## Future Enhancements

Planned features for Remotion integration:

- [ ] Sonar research data visualization (already coded, needs UI integration)
- [ ] Custom template selector in UI
- [ ] Batch video generation
- [ ] Timeline right-click "Generate with Remotion"
- [ ] Progress bar for long renders
- [ ] Template marketplace integration
- [ ] Render queue management
- [ ] Local Remotion rendering (without API server)

---

## Support

If you encounter issues:

1. Check Flowcut logs: View > Console/Logs
2. Check Remotion server logs
3. Test API directly with `curl`:
   ```bash
   curl -X POST http://localhost:4500/api/v1/render/repo \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"repoUrl":"https://github.com/remotion-dev/template-still","template":"default","userInput":"Test"}'
   ```
4. Report issues on the Flowcut GitHub repository

---

## Credits

- Remotion integration developed with Claude Sonnet 4.5
- Original Remotion framework by Jonny Burger
- Flowcut video editor by the Flowcut team

---

**Last Updated:** February 15, 2026
