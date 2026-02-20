"""
OpenShot transitions tools for the LangChain transitions agent.
Provides access to all built-in OpenShot transitions (common and extra).
All tools assume they are run on the Qt main thread.
"""

import os
import json
from classes.logger import log
from classes import info


def _get_app():
    """Get app; must be called from main thread."""
    from classes.app import get_app
    return get_app()


def list_transitions(category: str = "all") -> str:
    """
    List all available transitions in OpenShot.

    Args:
        category: "all" (default), "common", or "extra"

    Returns:
        JSON list of transitions with their names, types, and file paths
    """
    try:
        transitions_dir = os.path.join(info.PATH, "transitions")
        common_dir = os.path.join(transitions_dir, "common")
        extra_dir = os.path.join(transitions_dir, "extra")

        transitions = []

        # Helper to process directory
        def process_dir(dir_path, category_name):
            if not os.path.exists(dir_path):
                return
            for filename in sorted(os.listdir(dir_path)):
                if filename.startswith(".") or "thumbs.db" in filename.lower():
                    continue
                path = os.path.join(dir_path, filename)
                file_base_name = os.path.splitext(filename)[0]
                trans_name = file_base_name.replace("_", " ").capitalize()
                transitions.append({
                    "name": trans_name,
                    "filename": filename,
                    "category": category_name,
                    "path": path
                })

        # Process based on category
        if category in ("all", "common"):
            process_dir(common_dir, "common")
        if category in ("all", "extra"):
            process_dir(extra_dir, "extra")

        if not transitions:
            return "No transitions found."

        return json.dumps({
            "total": len(transitions),
            "transitions": transitions[:50] if len(transitions) > 50 else transitions,
            "note": f"Showing first 50 of {len(transitions)} transitions. Use category='common' or 'extra' to filter." if len(transitions) > 50 else None
        }, indent=2)

    except Exception as e:
        log.error("list_transitions: %s", e, exc_info=True)
        return f"Error: {e}"


def search_transitions(query: str) -> str:
    """
    Search for transitions by name.

    Args:
        query: Search term (e.g., "fade", "wipe", "circle")

    Returns:
        JSON list of matching transitions
    """
    try:
        transitions_dir = os.path.join(info.PATH, "transitions")
        common_dir = os.path.join(transitions_dir, "common")
        extra_dir = os.path.join(transitions_dir, "extra")

        query_lower = query.lower()
        matches = []

        # Helper to search directory
        def search_dir(dir_path, category_name):
            if not os.path.exists(dir_path):
                return
            for filename in os.listdir(dir_path):
                if filename.startswith(".") or "thumbs.db" in filename.lower():
                    continue
                file_base_name = os.path.splitext(filename)[0]
                trans_name = file_base_name.replace("_", " ").capitalize()

                if query_lower in trans_name.lower() or query_lower in file_base_name.lower():
                    matches.append({
                        "name": trans_name,
                        "filename": filename,
                        "category": category_name,
                        "path": os.path.join(dir_path, filename)
                    })

        search_dir(common_dir, "common")
        search_dir(extra_dir, "extra")

        if not matches:
            return f"No transitions found matching '{query}'."

        return json.dumps({
            "query": query,
            "matches": len(matches),
            "transitions": matches
        }, indent=2)

    except Exception as e:
        log.error("search_transitions: %s", e, exc_info=True)
        return f"Error: {e}"


def add_transition_between_clips(clip1_id: str, clip2_id: str, transition_name: str, duration: str = "1.0") -> str:
    """
    Add a transition effect between two clips on the timeline.

    Args:
        clip1_id: ID of the first clip
        clip2_id: ID of the second clip
        transition_name: Name of transition (use search_transitions to find available ones)
        duration: Duration of transition in seconds (default: 1.0)

    Returns:
        Success message with transition details
    """
    try:
        from classes.query import Clip, Transition
        from classes.updates import transaction
        import uuid

        app = _get_app()

        # Get the two clips
        clip1 = Clip.get(id=clip1_id)
        clip2 = Clip.get(id=clip2_id)

        if not clip1:
            return f"Error: Clip with id '{clip1_id}' not found."
        if not clip2:
            return f"Error: Clip with id '{clip2_id}' not found."

        # Find the transition file
        transitions_dir = os.path.join(info.PATH, "transitions")
        transition_path = None

        # Normalize transition name for matching
        search_name = transition_name.lower().replace(" ", "_")

        for category in ["common", "extra"]:
            category_dir = os.path.join(transitions_dir, category)
            if os.path.exists(category_dir):
                for filename in os.listdir(category_dir):
                    file_base = os.path.splitext(filename)[0]
                    if search_name in file_base.lower() or file_base.lower() in search_name:
                        transition_path = os.path.join(category_dir, filename)
                        break
            if transition_path:
                break

        if not transition_path:
            return f"Error: Transition '{transition_name}' not found. Use search_transitions_tool to find available transitions."

        # Get positions
        clip1_end = clip1.data.get("position", 0) + (clip1.data.get("end", 0) - clip1.data.get("start", 0))
        clip2_start = clip2.data.get("position", 0)

        # Calculate transition position (overlap the clips)
        try:
            duration_float = float(duration)
        except ValueError:
            duration_float = 1.0

        # Position transition at the boundary
        trans_position = max(clip1_end - duration_float / 2, 0)

        # Determine which clip is on higher layer
        layer1 = clip1.data.get("layer", 0)
        layer2 = clip2.data.get("layer", 0)

        # Create transition data
        transition_data = {
            "id": str(uuid.uuid4()),
            "layer": max(layer1, layer2),
            "position": trans_position,
            "start": 0,
            "end": duration_float,
            "brightness": 1.0,
            "contrast": 3.0,
            "reader": {
                "acodec": "",
                "audio_bit_rate": 0,
                "audio_stream_index": -1,
                "audio_timebase": {"den": 1, "num": 1},
                "channel_layout": 4,
                "channels": 0,
                "display_ratio": {"den": 1, "num": 1},
                "duration": duration_float,
                "file_size": "0",
                "fps": {"den": 1, "num": 30},
                "has_audio": False,
                "has_single_image": True,
                "has_video": True,
                "height": 1080,
                "interlaced_frame": False,
                "metadata": {},
                "path": transition_path,
                "pixel_ratio": {"den": 1, "num": 1},
                "sample_rate": 0,
                "top_field_first": True,
                "type": "QtImageReader",
                "vcodec": "",
                "video_bit_rate": 0,
                "video_length": "0",
                "video_stream_index": -1,
                "video_timebase": {"den": 30, "num": 1},
                "width": 1920
            },
            "replace_image": False,
            "type": "Mask",
            "title": os.path.splitext(os.path.basename(transition_path))[0]
        }

        # Add transition to project
        with transaction():
            app.updates.insert_transition(transition_data)

        return (
            f"Successfully added '{transition_name}' transition between clips.\n"
            f"Transition ID: {transition_data['id']}\n"
            f"Duration: {duration_float}s\n"
            f"Position: {trans_position}s\n"
            f"Layer: {transition_data['layer']}"
        )

    except Exception as e:
        log.error("add_transition_between_clips: %s", e, exc_info=True)
        return f"Error: {e}"


def add_transition_to_clip(clip_id: str, transition_name: str, position: str = "start", duration: str = "1.0") -> str:
    """
    Add a transition effect to a single clip (fade in/out effect).

    Args:
        clip_id: ID of the clip
        transition_name: Name of transition (e.g., "fade", "wipe")
        position: "start" (fade in) or "end" (fade out)
        duration: Duration of transition in seconds (default: 1.0)

    Returns:
        Success message with transition details
    """
    try:
        from classes.query import Clip, Transition
        from classes.updates import transaction
        import uuid

        app = _get_app()

        # Get the clip
        clip = Clip.get(id=clip_id)
        if not clip:
            return f"Error: Clip with id '{clip_id}' not found."

        # Find the transition file
        transitions_dir = os.path.join(info.PATH, "transitions")
        transition_path = None

        # Normalize transition name for matching
        search_name = transition_name.lower().replace(" ", "_")

        for category in ["common", "extra"]:
            category_dir = os.path.join(transitions_dir, category)
            if os.path.exists(category_dir):
                for filename in os.listdir(category_dir):
                    file_base = os.path.splitext(filename)[0]
                    if search_name in file_base.lower() or file_base.lower() in search_name:
                        transition_path = os.path.join(category_dir, filename)
                        break
            if transition_path:
                break

        if not transition_path:
            return f"Error: Transition '{transition_name}' not found. Use search_transitions_tool to find available transitions."

        # Get clip timing
        clip_position = clip.data.get("position", 0)
        clip_start = clip.data.get("start", 0)
        clip_end = clip.data.get("end", 0)
        clip_duration = clip_end - clip_start
        clip_layer = clip.data.get("layer", 0)

        try:
            duration_float = float(duration)
        except ValueError:
            duration_float = 1.0

        # Calculate transition position
        if position.lower() == "start":
            trans_position = clip_position
        else:  # end
            trans_position = clip_position + clip_duration - duration_float

        # Create transition data
        transition_data = {
            "id": str(uuid.uuid4()),
            "layer": clip_layer,
            "position": trans_position,
            "start": 0,
            "end": duration_float,
            "brightness": 1.0,
            "contrast": 3.0,
            "reader": {
                "acodec": "",
                "audio_bit_rate": 0,
                "audio_stream_index": -1,
                "audio_timebase": {"den": 1, "num": 1},
                "channel_layout": 4,
                "channels": 0,
                "display_ratio": {"den": 1, "num": 1},
                "duration": duration_float,
                "file_size": "0",
                "fps": {"den": 1, "num": 30},
                "has_audio": False,
                "has_single_image": True,
                "has_video": True,
                "height": 1080,
                "interlaced_frame": False,
                "metadata": {},
                "path": transition_path,
                "pixel_ratio": {"den": 1, "num": 1},
                "sample_rate": 0,
                "top_field_first": True,
                "type": "QtImageReader",
                "vcodec": "",
                "video_bit_rate": 0,
                "video_length": "0",
                "video_stream_index": -1,
                "video_timebase": {"den": 30, "num": 1},
                "width": 1920
            },
            "replace_image": False,
            "type": "Mask",
            "title": os.path.splitext(os.path.basename(transition_path))[0]
        }

        # Add transition to project
        with transaction():
            app.updates.insert_transition(transition_data)

        return (
            f"Successfully added '{transition_name}' transition to clip at {position}.\n"
            f"Transition ID: {transition_data['id']}\n"
            f"Duration: {duration_float}s\n"
            f"Position: {trans_position}s"
        )

    except Exception as e:
        log.error("add_transition_to_clip: %s", e, exc_info=True)
        return f"Error: {e}"


def get_transitions_tools_for_langchain():
    """Return LangChain tool wrappers for all transitions tools."""
    from langchain_core.tools import tool

    @tool
    def list_transitions_tool(category: str = "all") -> str:
        """List all available transitions. Args: category ("all", "common", or "extra"). Returns JSON list of transitions."""
        return list_transitions(category=category)

    @tool
    def search_transitions_tool(query: str) -> str:
        """Search for transitions by name. Args: query (search term like "fade", "wipe", "circle"). Returns matching transitions."""
        return search_transitions(query=query)

    @tool
    def add_transition_between_clips_tool(clip1_id: str, clip2_id: str, transition_name: str, duration: str = "1.0") -> str:
        """Add a transition between two clips. Args: clip1_id (first clip ID), clip2_id (second clip ID), transition_name (transition name from search), duration (seconds, default 1.0). Use list_clips_tool to get clip IDs first."""
        return add_transition_between_clips(clip1_id=clip1_id, clip2_id=clip2_id, transition_name=transition_name, duration=duration)

    @tool
    def add_transition_to_clip_tool(clip_id: str, transition_name: str, position: str = "start", duration: str = "1.0") -> str:
        """Add a transition to a single clip (fade in/out). Args: clip_id (clip ID), transition_name (transition name), position ("start" or "end"), duration (seconds, default 1.0)."""
        return add_transition_to_clip(clip_id=clip_id, transition_name=transition_name, position=position, duration=duration)

    return [
        list_transitions_tool,
        search_transitions_tool,
        add_transition_between_clips_tool,
        add_transition_to_clip_tool,
    ]
