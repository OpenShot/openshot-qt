"""
Tool Registry for Directors

Provides a catalog of available tools with signatures for LLM plan generation.
Maps vision analysis scores to executable tool parameters.
"""

from typing import Dict, Any
from classes.logger import log


class ToolRegistry:
    """Registry of executable tools available to directors"""

    @staticmethod
    def get_tool_catalog() -> str:
        """
        Returns formatted tool catalog for LLM consumption.

        This catalog describes available tools that directors can use
        in their generated plans, including parameter ranges and types.
        """
        return """
AVAILABLE TOOLS FOR PLAN EXECUTION:

VIDEO AGENT TOOLS:
------------------
add_effect(clip_id: str, effect_type: str, **parameters)
  Description: Add visual effect to a clip
  Types: brightness_contrast, color_correction, saturation, blur
  Parameters:
    - brightness: float (0.5-2.0, default 1.0) - brightness multiplier
    - contrast: float (0.5-2.0, default 1.0) - contrast multiplier
    - saturation: float (0.0-2.0, default 1.0) - color saturation
  Example: add_effect("clip_002", "brightness_contrast", brightness=1.15, contrast=1.05)

adjust_audio(clip_id: str, volume: float, fade_in: float = 0.0, fade_out: float = 0.0)
  Description: Adjust audio levels and fades for a clip
  Parameters:
    - volume: float (0.0-2.0, default 1.0) - volume multiplier
    - fade_in: float (seconds) - fade in duration
    - fade_out: float (seconds) - fade out duration
  Example: adjust_audio("clip_003", volume=0.8, fade_in=0.5)

split_clip(clip_id: str, split_time: float)
  Description: Split a clip into two clips at specified time
  Parameters:
    - split_time: float (seconds from clip start)
  Example: split_clip("clip_001", split_time=5.5)

add_transition(clip1_id: str, clip2_id: str, transition_name: str, duration: float)
  Description: Add transition effect between two adjacent clips
  Parameters:
    - transition_name: str - one of: fade, dissolve, wipe_left, wipe_right, circle_in, circle_out
    - duration: float (0.5-3.0 typical, in seconds)
  Example: add_transition("clip_001", "clip_002", "fade", duration=1.0)

remove_clip(clip_id: str)
  Description: Remove a clip from the timeline
  Example: remove_clip("clip_005")

reorder_clip(clip_id: str, new_position: float, new_layer: int)
  Description: Move a clip to a new position and/or layer
  Parameters:
    - new_position: float (seconds on timeline)
    - new_layer: int (track number, 1000000-5000000)
  Example: reorder_clip("clip_003", new_position=10.5, new_layer=2000000)

TRANSITIONS AGENT TOOLS:
-----------------------
search_transitions(query: str) -> List[transition_name]
  Description: Search available transitions by keyword
  Example: search_transitions("fade")

add_transition_between_clips(clip1_id: str, clip2_id: str, transition_name: str, duration: float)
  Description: Apply professional transition between clips
  Parameters: Same as add_transition above, but with 412+ available transitions
  Example: add_transition_between_clips("clip_001", "clip_002", "ripple", duration=1.5)

TTS AGENT TOOLS:
---------------
generate_tts(text: str, voice: str, position: float, track: int)
  Description: Generate text-to-speech audio and add to timeline
  Parameters:
    - text: str - text to speak
    - voice: str - one of: alloy (neutral), echo (male), fable (expressive),
             onyx (deep male), nova (female), shimmer (soft female)
    - position: float (seconds on timeline, use 0.0 for playhead)
    - track: int (audio track number)
  Example: generate_tts("Welcome to the video", "alloy", position=0.0, track=3000000)

MUSIC AGENT TOOLS:
-----------------
generate_music(prompt: str, tags: List[str], position: float, track: int)
  Description: Generate background music using Suno and add to timeline
  Parameters:
    - prompt: str - description of desired music
    - tags: List[str] - style tags like: upbeat, cinematic, calm, energetic,
            dramatic, happy, sad, electronic, acoustic, instrumental
    - position: float (seconds on timeline)
    - track: int (audio track number)
  Example: generate_music("Upbeat background music", ["upbeat", "electronic"], position=0.0, track=3000000)

PARAMETER CALCULATION FROM VISION ANALYSIS:
------------------------------------------
When vision analysis provides scores (0.0-1.0), calculate tool parameters:
- Lighting score < 0.7 → brightness adjustment: 1.0 + (0.7 - score) * 0.5
  Example: score 0.65 → brightness 1.15
- Low contrast → contrast adjustment: 1.0 + (0.7 - score) * 0.3
- Low saturation → saturation adjustment: 1.0 + (0.7 - score) * 0.2

Always reference vision scores in your rationale when using them.
"""

    @staticmethod
    def map_vision_score_to_params(score: float, param_type: str) -> float:
        """
        Convert vision analysis score to tool parameter value.

        Args:
            score: Vision analysis score (0.0-1.0)
            param_type: Parameter type to calculate ('brightness', 'contrast', 'saturation')

        Returns:
            Calculated parameter value suitable for the tool
        """
        if param_type == "brightness":
            # Lower lighting scores need more brightness
            # Score 0.65 → brightness 1.15 (increase by 15%)
            # Score 0.50 → brightness 1.20 (increase by 20%)
            if score < 0.7:
                adjustment = (0.7 - score) * 0.5
                return round(1.0 + adjustment, 2)
            return 1.0

        elif param_type == "contrast":
            # Lower scores need more contrast
            if score < 0.7:
                adjustment = (0.7 - score) * 0.3
                return round(1.0 + adjustment, 2)
            return 1.0

        elif param_type == "saturation":
            # Lower saturation scores need more saturation
            if score < 0.7:
                adjustment = (0.7 - score) * 0.2
                return round(1.0 + adjustment, 2)
            return 1.0

        else:
            log.warning(f"Unknown param_type: {param_type}")
            return 1.0

    @staticmethod
    def calculate_effect_params_from_vision(vision_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate effect parameters from vision analysis data.

        Args:
            vision_data: Vision analysis dictionary with composition and quality scores

        Returns:
            Dictionary of effect parameters
        """
        params = {}

        # Extract vision analysis scores
        vision_analysis = vision_data.get('vision_analysis', {})
        composition = vision_analysis.get('composition', {})

        lighting_score = composition.get('lighting_score', 1.0)
        framing_score = composition.get('framing_score', 1.0)
        color_harmony = composition.get('color_harmony_score', 1.0)

        # Calculate adjustments
        if lighting_score < 0.7:
            params['brightness'] = ToolRegistry.map_vision_score_to_params(lighting_score, 'brightness')
            params['contrast'] = ToolRegistry.map_vision_score_to_params(lighting_score, 'contrast')

        if color_harmony < 0.7:
            params['saturation'] = ToolRegistry.map_vision_score_to_params(color_harmony, 'saturation')

        return params

    @staticmethod
    def format_tool_call(tool_name: str, tool_args: Dict[str, Any]) -> str:
        """
        Format a tool call for display/logging.

        Args:
            tool_name: Name of the tool
            tool_args: Tool arguments

        Returns:
            Formatted string representation
        """
        args_str = ", ".join(f"{k}={repr(v)}" for k, v in tool_args.items())
        return f"{tool_name}({args_str})"


# Global instance
_tool_registry = None

def get_tool_registry() -> ToolRegistry:
    """Get global tool registry instance"""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry
