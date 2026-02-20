# Product Launch Video Agent - Implementation Guide

## Overview

The **Product Launch Agent** automatically creates compelling product launch videos for GitHub repositories using animated visualizations. It combines GitHub API data extraction with Manim's programmatic animation capabilities to generate professional videos that are automatically added to your timeline.

## Features

✅ **GitHub Integration** - Fetches repository data, stats, and README content
✅ **Programmatic Animations** - Uses Manim to create beautiful, code-based animations (Remotion-style)
✅ **Multi-Scene Videos** - Automatically generates and combines multiple scenes
✅ **Auto-Timeline Integration** - Videos appear on timeline immediately after generation
✅ **Thread-Safe** - Runs on worker thread, UI stays responsive

## How It Works

### 1. User Input
User provides a GitHub repository URL (any format):
- `https://github.com/facebook/react`
- `github.com/facebook/react`
- `facebook/react`

### 2. Data Extraction
The agent fetches:
- Repository metadata (name, description, stars, forks, language)
- README content
- Topics/tags
- Homepage URL

### 3. Video Generation
Creates an animated video with 4 scenes:

#### **Intro Scene**
- Animated repo name with gradient colors
- Description text
- GitHub URL
- Smooth fade animations

#### **Stats Scene**
- Animated counters for stars ⭐
- Fork count 🔀
- Primary programming language 💻
- Staggered entrance animations

#### **Features Scene** (if features detected)
- Key features extracted from README
- Bullet-point list with smooth animations
- Sequential reveal

#### **Outro Scene**
- Call-to-action: "Check it out!"
- GitHub URL
- Homepage (if available)
- Fade out

### 4. Timeline Integration
- All scenes are rendered separately
- Combined into a single MP4 file
- Automatically added to the timeline
- Ready for further editing or export

## Architecture

### New Files Created

```
/src/classes/
├── github_client.py              # GitHub API client
├── ai_product_launch_tools.py    # LangChain tools for product launch
└── ai_multi_agent/
    └── sub_agents.py              # Added run_product_launch_agent()
```

### Modified Files

```
/src/classes/
├── ai_agent_runner.py            # Registered product launch tools
└── ai_multi_agent/
    └── root_agent.py              # Added invoke_product_launch_agent
```

### Integration Points

1. **GitHub Client** (`github_client.py`)
   - REST API client using `requests` library
   - Thread-safe, no Qt dependencies
   - Error handling with structured exceptions
   - URL parsing for flexible input formats

2. **Product Launch Tools** (`ai_product_launch_tools.py`)
   - `fetch_github_repo_data(repo_url)` - Fetches and returns JSON data
   - `generate_product_launch_video(repo_data_json)` - Generates and renders video
   - Uses existing Manim rendering pipeline
   - Automatic timeline integration

3. **Product Launch Agent** (`sub_agents.py`)
   - Specialized system prompt for product launch videos
   - Workflow: Fetch data → Generate video → Confirm
   - Uses both GitHub and Manim tools

4. **Root Agent** (`root_agent.py`)
   - Routes product launch requests to specialized agent
   - Accessible via `invoke_product_launch_agent` tool

## Usage

### Via Chat Interface

```
User: "Create a product launch video for https://github.com/facebook/react"

Agent Response:
1. ✅ Fetched GitHub data for facebook/react (242K stars)
2. ✅ Generated Manim scenes (IntroScene, StatsScene, FeaturesScene, OutroScene)
3. ✅ Rendered and combined 4 scenes
4. ✅ Added product launch video to timeline!
```

### Via Code

```python
from classes.ai_multi_agent import sub_agents
from classes.ai_agent_runner import get_main_thread_runner

# Run product launch agent
result = sub_agents.run_product_launch_agent(
    model_id="claude-sonnet-4.5",
    task_or_messages="Create a launch video for facebook/react",
    main_thread_runner=get_main_thread_runner()
)

print(result)  # Success message with details
```

## Test Suite

Run comprehensive tests:

```bash
cd /home/lol/project/core
python3 test_product_launch_agent.py
```

### Test Coverage

✅ **Test 1: GitHub Client**
- URL parsing (multiple formats)
- Repo info fetching
- README extraction

✅ **Test 2: Product Launch Tools**
- Tool registration
- GitHub data extraction
- Manim code generation

✅ **Test 3: Agent Registration**
- Sub-agent import
- Root agent integration
- Tool runner registration

⚠ **Test 4: Manim Availability**
- Checks if Manim is installed
- Required for video rendering

## Dependencies

All dependencies are already configured in `requirements.txt`:

```
# Core dependencies (already installed)
requests
langchain-core>=0.3
langchain>=0.3

# Manim (optional, see requirements-manim.txt)
# pip install manim
```

## Example Output

For `https://github.com/facebook/react`:

**Generated Video Structure:**
```
[0:00-0:04] Intro Scene
  - "React" title with gradient animation
  - "The library for web and native user interfaces"
  - "github.com/facebook/react"

[0:04-0:10] Stats Scene
  - ⭐ 243K Stars
  - 🔀 45K Forks
  - 💻 JavaScript

[0:10-0:16] Features Scene
  - Declarative
  - Component-Based
  - Learn Once, Write Anywhere

[0:16-0:20] Outro Scene
  - "Check it out!"
  - "github.com/facebook/react"
  - "react.dev"
```

**Timeline Result:**
- Single MP4 clip added to timeline
- Duration: ~20 seconds
- Ready for export or further editing

## Customization

### Modify Scene Templates

Edit `ai_product_launch_tools.py` → `generate_product_launch_manim_code()`:

```python
# Change intro animation style
title.set_color_by_gradient(BLUE, PURPLE)  # Customize colors

# Adjust scene timing
self.wait(2)  # Change wait duration

# Add new scenes
class CustomScene(Scene):
    def construct(self):
        # Your custom animation
        pass
```

### Extend GitHub Data Extraction

Edit `github_client.py`:

```python
def get_repo_contributors(owner, repo):
    """Fetch top contributors."""
    url = f"{DEFAULT_GITHUB_API}/repos/{owner}/{repo}/contributors"
    # ... implementation
```

### Add New Video Styles

Create style presets in `ai_product_launch_tools.py`:

```python
def generate_minimal_style(repo_data):
    # Minimalist design

def generate_vibrant_style(repo_data):
    # Bold, colorful design
```

## Troubleshooting

### Issue: "Manim is not installed"

**Solution:**
```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get install -y libcairo2-dev libpango1.0-dev pkg-config

# Install Manim
pip install manim

# Or use requirements file
pip install -r requirements-manim.txt
```

### Issue: "GitHub API rate limit exceeded"

**Solution:**
1. Generate a GitHub Personal Access Token (PAT)
2. Add token to Preferences > AI (if supported)
3. Or modify `github_client.py` to use token:
   ```python
   repo_info = get_repo_info("owner", "repo", token="ghp_your_token")
   ```

### Issue: "Video not appearing on timeline"

**Diagnosis:**
- Check if Manim rendering succeeded (console logs)
- Verify file was added to project files
- Check timeline has available tracks

**Solution:**
```python
# Manual file addition
from classes.app import get_app
app = get_app()
app.window.files_model.add_files(["/path/to/video.mp4"])
```

### Issue: "Scenes failed to render"

**Diagnosis:**
- Check Manim version compatibility
- Review generated Python code for syntax errors
- Check system dependencies (Cairo, Pango)

**Solution:**
```bash
# Test Manim manually
manim --version
manim -ql test_scene.py TestScene
```

## Performance

- **GitHub API fetch:** ~1-2 seconds
- **Manim code generation:** <1 second
- **Scene rendering:** ~10-30 seconds (depends on scene complexity and quality)
- **Video concatenation:** ~2-5 seconds
- **Total time:** ~15-40 seconds per video

## Roadmap

Future enhancements:
- [ ] Multiple video style presets (minimal, vibrant, corporate)
- [ ] Customizable scene order and duration
- [ ] Support for other Git hosting services (GitLab, Bitbucket)
- [ ] AI-powered feature extraction from README
- [ ] Background music integration
- [ ] Voice-over narration option
- [ ] Transition effects between scenes
- [ ] Social media optimized formats (9:16 for TikTok/Instagram)

## Credits

- **OpenShot** - Video editing engine
- **Manim Community** - Animation framework
- **GitHub API** - Repository data
- **LangChain** - Agent orchestration
- **Anthropic Claude** - LLM backend

## Support

For issues or feature requests:
1. Check this guide and troubleshooting section
2. Review test results: `python3 test_product_launch_agent.py`
3. Check logs in console for detailed error messages
4. Verify dependencies are installed

---

**Built with ❤️ for the Flowcut community**
