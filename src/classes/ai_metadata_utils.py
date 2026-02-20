"""
Utility functions for handling AI metadata on clips, especially for sub-clipping operations.
"""

from typing import Dict, Any, List


def adjust_scene_descriptions_for_subclip(
    ai_metadata: Dict[str, Any],
    start_time: float,
    end_time: float
) -> Dict[str, Any]:
    """
    Adjust scene descriptions in ai_metadata for a sub-clip.
    
    Args:
        ai_metadata: Original AI metadata dictionary
        start_time: Start time of the sub-clip in seconds
        end_time: End time of the sub-clip in seconds
    
    Returns:
        New ai_metadata dictionary with adjusted scene descriptions
    """
    if not ai_metadata or not ai_metadata.get('analyzed'):
        return ai_metadata
    
    scene_descriptions = ai_metadata.get('scene_descriptions', [])
    
    if not scene_descriptions:
        return ai_metadata
    
    # Filter scene descriptions that fall within the sub-clip time range
    filtered_scenes = []
    for scene in scene_descriptions:
        scene_time = scene.get('time', 0)
        # Check if scene time falls within the sub-clip range
        if start_time <= scene_time <= end_time:
            # Adjust time to be relative to the new clip's start
            adjusted_scene = {
                'time': scene_time - start_time,
                'description': scene.get('description', '')
            }
            filtered_scenes.append(adjusted_scene)
    
    # Create new ai_metadata for the sub-clip
    new_metadata = {
        'analyzed': True,
        'analysis_version': ai_metadata.get('analysis_version', '2.0'),
        'analysis_date': ai_metadata.get('analysis_date', ''),
        'provider': ai_metadata.get('provider', 'gemini'),
        'scene_descriptions': filtered_scenes,
        'tags': {
            'objects': [],
            'scenes': [],
            'activities': [],
            'mood': [],
            'quality': {}
        },
        'faces': [],
        'colors': {},
        'audio_analysis': {},
        'description': ' '.join([s['description'] for s in filtered_scenes]),
        'confidence': ai_metadata.get('confidence', 0.0)
    }
    
    return new_metadata


def get_scene_descriptions_formatted(ai_metadata: Dict[str, Any]) -> List[str]:
    """
    Get scene descriptions formatted as human-readable strings with timestamps.
    
    Args:
        ai_metadata: AI metadata dictionary
    
    Returns:
        List of formatted strings like "[0:05] A person walking down the street"
    """
    if not ai_metadata or not ai_metadata.get('analyzed'):
        return []
    
    scene_descriptions = ai_metadata.get('scene_descriptions', [])
    formatted = []
    
    for scene in scene_descriptions:
        time_sec = scene.get('time', 0)
        description = scene.get('description', '')
        
        # Format time as MM:SS
        minutes = int(time_sec // 60)
        seconds = int(time_sec % 60)
        time_str = f"{minutes}:{seconds:02d}"
        
        formatted.append(f"[{time_str}] {description}")
    
    return formatted
