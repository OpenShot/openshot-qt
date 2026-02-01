GEN_AI_SYSTEM = "gcp.gemini"

# Mapping of tool attributes to their descriptions
# These are all tools that are available in the Google GenAI API
TOOL_ATTRIBUTES_MAP = {
    "google_search_retrieval": "Google Search retrieval tool",
    "google_search": "Google Search tool",
    "retrieval": "Retrieval tool",
    "enterprise_web_search": "Enterprise web search tool",
    "google_maps": "Google Maps tool",
    "code_execution": "Code execution tool",
    "computer_use": "Computer use tool",
}

IDENTIFIER = "google_genai"
ORIGIN = f"auto.ai.{IDENTIFIER}"
