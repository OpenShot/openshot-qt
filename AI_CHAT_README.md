# AI Chat - User Guide

## Overview

The video editor includes an AI Assistant dock widget that uses real LLMs (OpenAI, Anthropic, Ollama) via LangChain. The assistant can query project state and perform editing actions (list files, add track, play, undo, export, etc.) through tools that run on the main thread.

## How to Access

1. Run the application:
   ```
   ./run.sh
   ```
   (or `run-flowcut-core.sh` if you use that launcher)

2. Open the Flowcut Assistant:
   - Click on the **View** menu
   - Select **Docks**
   - Click on **Flowcut Assistant**

3. The chat panel appears as a dockable widget that can be moved and resized.

## Configuration

1. Open **Edit > Preferences** and go to the **AI** tab.
2. Set at least one provider:
   - **OpenAI API Key** – for OpenAI models (e.g. GPT-4o mini)
   - **Anthropic API Key** – for Anthropic models (e.g. Claude 3.5 Sonnet)
   - **Ollama Base URL** – for local Ollama (default: http://localhost:11434)
3. Optionally set **AI Default Model** (e.g. `openai/gpt-4o-mini`).
4. The **Model** dropdown in the Flowcut Assistant lists only models whose provider is configured (e.g. models appear when the corresponding API key is set).

## Using the Chat

- Type your message in the input field at the bottom.
- Press **Enter** to send; **Shift+Enter** for a new line.
- Use the **Model** dropdown to choose which LLM to use for this chat.
- Click **Clear** to reset the conversation.
- The assistant can use tools to query the project (list files, clips, layers, markers, project info) and to perform actions (play, undo, redo, add track, add marker, export video, import files, save/open project, zoom, etc.). Ask in natural language (e.g. “List my files”, “Add a track”, “Undo”).

## Window Behavior

The chat window state is saved with your application preferences:

- If you close the application with the chat window open, the chat window will appear when you start again.
- If you close the chat window (X on the dock) before closing the application, it will not appear on the next startup.

Toggle visibility via **View > Docks > AI Assistant**.

## Architecture

- **UI:** `src/windows/ai_chat_ui.py` – dock, model combo, send/clear.
- **Session:** `src/classes/ai_chat_functionality.py` – `AIChat`, `send_message()`, `_generate_response()`.
- **LLM registry:** `src/classes/ai_llm_registry.py` – `get_model()`, `list_models()`, `get_default_model_id()`.
- **Providers:** `src/classes/ai_providers/` – OpenAI, Anthropic, Ollama (build LangChain ChatModels from settings).
- **Tools:** `src/classes/ai_openshot_tools.py` – Flowcut tools (project state and actions) for the agent.
- **Agent runner:** `src/classes/ai_agent_runner.py` – builds agent with selected LLM and tools, runs in a worker thread, dispatches tool execution to the Qt main thread.

## Dependencies

- `langchain-core`, `langchain`, `langchain-openai`, `langchain-anthropic`, `langchain-community`, `langchain-ollama` (see `requirements-noqt.txt` or `requirements.txt`).

## Safety

- Tool inputs are validated; errors are returned as strings to the agent.
- API keys are stored in user settings (Preferences > AI) and are not logged.
- Do not share your settings file; it may contain API keys.
