# AI Chat UI - User Guide

## Overview

The video editor includes an AI Assistant dock widget for chat interactions. The UI is integrated as a dockable panel similar to other editor panels.

## How to Access

1. Run the application:
   ```
   bash run-zenvi-core.sh
   ```

2. Open the AI Assistant:
   - Click on the View menu
   - Select Docks
   - Click on AI Assistant

3. The chat panel will appear as a dockable widget that can be moved and resized like other panels.

## Using the Chat

- Type your message in the input field at the bottom
- Press Enter to send the message
- Press Shift+Enter to create a new line without sending
- Click Clear to reset the chat conversation
- Select a different model from the Model dropdown

## Window Behavior

The chat window state is saved with your application preferences:

- If you close the application with the chat window open, the chat window will appear when you start the application again.
- If you close the chat window (by clicking the X button on the dock) before closing the application, the chat window will not appear on the next startup.

To toggle the chat visibility, use View > Docks > AI Assistant at any time.

## Files

- src/windows/ai_chat_ui.py - Chat interface implementation
- src/classes/ai_chat_functionality.py - Chat backend and message handling

## Notes

- Currently returns placeholder responses
- Designed for future AI provider integration (OpenAI, Anthropic, local LLM, etc.)
- No API keys or external services required for the UI
