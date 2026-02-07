"""
Stub tools for voice overlays and music generation. To be wired to Azure tagging,
Eleven Labs/Coqui TTS, and music API or MusicGen when configured.
"""

from classes.logger import log


def tag_videos_via_azure(api_url: str = "", api_key: str = "") -> str:
    """Tag videos using the Azure tagging API. Not configured until API details are provided."""
    if not (api_url and api_key):
        return "Azure tagging API is not configured. Provide api_url and api_key in Preferences when available."
    return "Azure tagging not yet implemented. API URL and key will be used when the integration is added."


def generate_storyline_from_tags() -> str:
    """Generate a storyline script from tagged video metadata. Requires tags to be loaded first."""
    return "Storyline-from-tags is not yet implemented. Tag videos first (Azure API), then this will use the tags to generate a script."


def generate_voice_overlay(text: str, voice_id: str = "default") -> str:
    """Generate TTS audio from text (e.g. Eleven Labs or Coqui). Returns path to audio file or error."""
    if not (text or "").strip():
        return "Error: text is required for voice overlay."
    return (
        "Voice overlay is not yet configured. Add Eleven Labs or Coqui TTS API key in Preferences > AI (or similar) to enable."
    )


def generate_music(theme: str, duration_seconds: int = 60) -> str:
    """Generate background music for the given theme and duration. Returns path to audio file or error."""
    if not (theme or "").strip():
        return "Error: theme is required (e.g. 'upbeat', 'calm')."
    return (
        "Music generation is not yet configured. Use an open-source option (e.g. MusicGen) or add an API key in Preferences."
    )


def get_voice_music_tools_for_langchain():
    """Return a list of LangChain Tool objects for the Voice/Music agent (stubs)."""
    from langchain_core.tools import tool

    @tool
    def tag_videos_via_azure_tool(api_url: str = "", api_key: str = "") -> str:
        """Tag project videos using the Azure tagging API. Requires api_url and api_key (to be configured in Preferences)."""
        return tag_videos_via_azure(api_url=api_url, api_key=api_key)

    @tool
    def generate_storyline_from_tags_tool() -> str:
        """Generate a storyline/script from the current video tags. Use after tagging videos."""
        return generate_storyline_from_tags()

    @tool
    def generate_voice_overlay_tool(text: str, voice_id: str = "default") -> str:
        """Generate speech audio from text for voice-over. text: script to speak. voice_id: optional voice identifier."""
        return generate_voice_overlay(text=text, voice_id=voice_id)

    @tool
    def generate_music_tool(theme: str, duration_seconds: int = 60) -> str:
        """Generate background music. theme: e.g. 'upbeat', 'calm'. duration_seconds: length of the track."""
        return generate_music(theme=theme, duration_seconds=duration_seconds)

    return [
        tag_videos_via_azure_tool,
        generate_storyline_from_tags_tool,
        generate_voice_overlay_tool,
        generate_music_tool,
    ]
