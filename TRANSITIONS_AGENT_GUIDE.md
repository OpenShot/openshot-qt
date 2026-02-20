# Transitions Agent - Complete Guide

## Overview
The Transitions Agent provides AI-powered access to all 412+ OpenShot transitions, making it easy to add professional effects to your videos through natural language commands.

## Features
- **412+ Professional Transitions**: Access to all OpenShot transitions including:
  - **Common**: fade, circle in/out, wipe (4 directions)
  - **Extra**: 405 artistic transitions (ripples, blurs, blinds, boards, crosses, rays, and more)
- **Smart Search**: Find transitions by name or style
- **Automatic Application**: Apply transitions between clips or to single clips
- **Flexible Timing**: Customize transition duration and placement

## Architecture

### New Files Created
1. **`src/classes/ai_transitions_tools.py`**
   - Core transition functionality
   - Tools: list, search, add between clips, add to clip

2. **Updated `src/classes/ai_multi_agent/sub_agents.py`**
   - Added `run_transitions_agent()` function
   - Integrated with OpenShot tools for clip access

3. **Updated `src/classes/ai_multi_agent/root_agent.py`**
   - Added `invoke_transitions_agent` tool
   - Updated routing to include transitions

## Available Tools

### 1. list_transitions_tool
List all available transitions.
```python
Args:
  category: "all" (default), "common", or "extra"
Returns:
  JSON list of transitions with names, categories, and paths
```

### 2. search_transitions_tool
Search for transitions by name.
```python
Args:
  query: Search term (e.g., "fade", "wipe", "circle", "blur")
Returns:
  JSON list of matching transitions
```

### 3. add_transition_between_clips_tool
Add a transition effect between two clips.
```python
Args:
  clip1_id: ID of the first clip
  clip2_id: ID of the second clip
  transition_name: Name of transition
  duration: Duration in seconds (default: 1.0)
Returns:
  Success message with transition details
```

### 4. add_transition_to_clip_tool
Add a transition to a single clip (fade in/out).
```python
Args:
  clip_id: ID of the clip
  transition_name: Name of transition
  position: "start" (fade in) or "end" (fade out)
  duration: Duration in seconds (default: 1.0)
Returns:
  Success message with transition details
```

## Usage Examples

### Via Natural Language (Recommended)
The AI automatically routes to the transitions agent when you mention transitions:

```
"Add a fade transition between the first two clips"
"Add a wipe effect from left to right between clips"
"Put a fade in at the start of the first clip"
"Search for blur transitions and apply one between my clips"
"List all available transitions"
```

### Direct Agent Access (For Testing)
```python
from classes.ai_multi_agent.sub_agents import run_transitions_agent

result = run_transitions_agent(
    model_id="claude-sonnet-4-5",
    task_or_messages="Add a fade transition between clips",
    main_thread_runner=runner
)
```

### Tool Access (Low-Level)
```python
from classes.ai_transitions_tools import search_transitions, add_transition_between_clips

# Search for transitions
result = search_transitions("fade")

# Apply transition
result = add_transition_between_clips(
    clip1_id="abc123",
    clip2_id="def456",
    transition_name="fade",
    duration="1.5"
)
```

## Agent Workflow

1. **User Request**: "Add a fade between my clips"
2. **Root Agent**: Routes to transitions agent
3. **Transitions Agent**:
   - Lists clips using `list_clips_tool`
   - Searches for "fade" using `search_transitions_tool`
   - Applies transition using `add_transition_between_clips_tool`
4. **Response**: "Successfully added 'Fade' transition between clips."

## Common Transition Types

### Popular Effects
- **fade**: Classic fade in/out
- **wipe**: Directional wipes (left, right, top, bottom)
- **circle**: Circular in/out transitions
- **blur**: Blur-based transitions
- **ripple**: Water ripple effects
- **blinds**: Venetian blind effects
- **board**: Board/panel transitions
- **cross**: Cross-shaped transitions

### Tips
- Use **duration 0.5-1.0s** for quick cuts
- Use **duration 1.5-2.0s** for cinematic transitions
- Use **"fade"** for fade in/out on single clips
- Use **"wipe"** for dynamic scene changes
- Search before applying to explore options

## Integration

The transitions agent is fully integrated into Flowcut's multi-agent system:
- Accessible via root agent routing
- Works with plan-graph tracking
- Shares clip/timeline data with video agent
- Compatible with all existing features

## Verification

Run these commands to verify installation:

```bash
# Test imports
python3 -c "from classes.ai_transitions_tools import get_transitions_tools_for_langchain; print('✓ Transitions tools loaded')"

# List tools
python3 -c "
from classes.ai_transitions_tools import get_transitions_tools_for_langchain
tools = get_transitions_tools_for_langchain()
print(f'Found {len(tools)} tools:')
for tool in tools: print(f'  - {tool.name}')
"

# Test search
python3 -c "
from classes.ai_transitions_tools import search_transitions
import json
result = search_transitions('fade')
print(json.loads(result)['matches'], 'matches found')
"
```

## Troubleshooting

### "Transition not found"
- Use `search_transitions_tool` first to find exact names
- Try partial matches (e.g., "wipe" will find "wipe_left_to_right")

### "Clip not found"
- Use `list_clips_tool` to get valid clip IDs
- Clip IDs are UUIDs, not indices

### "Import errors"
- Ensure all files are in correct locations
- Restart application if modules were just added

## Future Enhancements
- Transition preview generation
- Automatic transition selection based on video content
- Custom transition duration per clip pair
- Bulk transition application
- Transition style recommendations
