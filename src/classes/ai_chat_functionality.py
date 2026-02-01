"""
 @file
 @brief This file contains the AI chat functionality for OpenShot
 @author OpenShot Development Team

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
"""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

from classes.logger import log


class MessageRole(Enum):
    """Enum for message roles in the chat"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage:
    """Represents a single message in the chat"""
    
    def __init__(self, role: MessageRole, content: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize a chat message
        
        Args:
            role: The role of the message sender (user, assistant, or system)
            content: The content of the message
            context: Optional context data attached to the message
        """
        self.role = role
        self.content = content
        self.context = context or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        return {
            "role": self.role.value,
            "content": self.content,
            "context": self.context,
            "timestamp": self.timestamp.isoformat()
        }


class ChatSession:
    """Manages a single chat session with conversation history"""
    
    def __init__(self, session_id: str = "", model: str = "default", system_prompt: str = ""):
        """
        Initialize a chat session
        
        Args:
            session_id: Unique identifier for this session
            model: The AI model to use
            system_prompt: Initial system prompt for the conversation
        """
        self.session_id = session_id
        self.model = model
        self.system_prompt = system_prompt
        self.messages: List[ChatMessage] = []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.context_data = {}  # Store context information
        
        # Add system message if provided
        if system_prompt:
            self.add_message(MessageRole.SYSTEM, system_prompt)
    
    def add_message(self, role: MessageRole, content: str, context: Optional[Dict[str, Any]] = None) -> ChatMessage:
        """
        Add a message to the session
        
        Args:
            role: The role of the message sender
            content: The message content
            context: Optional context data
        
        Returns:
            The created ChatMessage object
        """
        message = ChatMessage(role, content, context)
        self.messages.append(message)
        self.updated_at = datetime.now()
        log.debug(f"Chat message added: {role.value} - {content[:50]}...")
        return message
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        Get the conversation history as a list of dictionaries
        
        Returns:
            List of message dictionaries
        """
        return [msg.to_dict() for msg in self.messages]
    
    def get_user_messages(self) -> List[ChatMessage]:
        """Get all user messages from the session"""
        return [msg for msg in self.messages if msg.role == MessageRole.USER]
    
    def get_assistant_messages(self) -> List[ChatMessage]:
        """Get all assistant messages from the session"""
        return [msg for msg in self.messages if msg.role == MessageRole.ASSISTANT]
    
    def clear_messages(self):
        """Clear all messages from the session (except system messages)"""
        system_msgs = [msg for msg in self.messages if msg.role == MessageRole.SYSTEM]
        self.messages = system_msgs
        self.updated_at = datetime.now()
    
    def attach_context(self, context_key: str, context_value: Any):
        """
        Attach context information to the session
        
        Args:
            context_key: Key for the context data
            context_value: The context data value
        """
        self.context_data[context_key] = context_value
        log.debug(f"Context attached: {context_key}")
    
    def get_context(self, context_key: str) -> Optional[Any]:
        """
        Get context information from the session
        
        Args:
            context_key: Key for the context data
        
        Returns:
            The context value or None if not found
        """
        return self.context_data.get(context_key)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary"""
        return {
            "session_id": self.session_id,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "messages": self.get_conversation_history(),
            "context_data": self.context_data,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class AIChat:
    """Main AI Chat manager - handles a single session"""
    
    def __init__(self, model: str = "default", system_prompt: str = ""):
        """
        Initialize the AI Chat manager
        
        Args:
            model: The AI model to use
            system_prompt: System prompt for the conversation
        """
        self.model = model
        self.system_prompt = system_prompt or self._get_default_system_prompt()
        self.current_session: Optional[ChatSession] = None
        self.ai_provider = None
        
        # Initialize the session
        self._init_session()
    
    def _get_default_system_prompt(self) -> str:
        """Get default system prompt for video editing context"""
        return (
            "You are an AI assistant for OpenShot Video Editor. "
            "You help users with video editing, effects, transitions, and general editing tasks. "
            "Provide concise, practical advice for video editing workflows."
        )
    
    def _init_session(self):
        """Initialize a new chat session"""
        import uuid
        session_id = str(uuid.uuid4())
        self.current_session = ChatSession(
            session_id=session_id,
            model=self.model,
            system_prompt=self.system_prompt
        )
        log.info(f"AI Chat session initialized: {session_id}")
    
    def send_message(self, user_input: str, context: Optional[Dict[str, Any]] = None,
                     model_id: Optional[str] = None) -> str:
        """
        Send a message and get a response.

        Args:
            user_input: The user's message
            context: Optional context to attach to the message
            model_id: Optional model id from registry (e.g. openai/gpt-4o-mini). Uses default if not set.

        Returns:
            The AI assistant's response
        """
        if not self.current_session:
            self._init_session()

        # Add user message to session
        self.current_session.add_message(MessageRole.USER, user_input, context)

        # Generate response from AI provider (agent + LLM)
        response = self._generate_response(user_input, model_id=model_id)

        # Add assistant message to session
        self.current_session.add_message(MessageRole.ASSISTANT, response)

        return response

    def _generate_response(self, user_input: str, model_id: Optional[str] = None) -> str:
        """
        Generate a response using the LangChain agent and selected LLM, or media manager for media commands.
        Runs the agent in a worker thread; tools run on the Qt main thread.
        """
        # Check if this is a media management command (from nilay branch)
        media_keywords = ['analyze', 'search', 'find', 'collection', 'tag', 'face', 'statistics']
        if any(keyword in user_input.lower() for keyword in media_keywords):
            try:
                import asyncio
                from classes.ai_media_manager import get_ai_media_manager
                manager = get_ai_media_manager()
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(manager.process_command(user_input))
                loop.close()
                if result.get('success'):
                    response = result.get('message', 'Command executed successfully')
                    if result.get('action') == 'search' and result.get('results'):
                        response += "\n\nTop results:"
                        for file_id, score in result['results'][:5]:
                            from classes.query import File
                            file_obj = File.get(id=file_id)
                            if file_obj:
                                import os
                                filename = os.path.basename(file_obj.data.get('path', ''))
                                response += f"\n- {filename} (relevance: {score:.2f})"
                    elif result.get('action') == 'statistics':
                        stats = result.get('stats', {})
                        response += "\n\nStatistics:"
                        if 'tags' in stats:
                            response += f"\n- Total tags: {stats['tags'].get('total_tags', 0)}"
                        if 'faces' in stats:
                            response += f"\n- People recognized: {stats['faces'].get('total_people', 0)}"
                        if 'collections' in stats:
                            response += f"\n- Collections: {stats['collections'].get('total', 0)}"
                    return response
                else:
                    return result.get('message', 'Command failed')
            except ImportError:
                pass
            except Exception as e:
                log.error("Media management command failed: %s", e)
                return "Failed to execute media command: %s" % (e,)

        # LangChain agent (HEAD)
        import threading
        try:
            from classes.ai_agent_runner import run_agent, create_main_thread_runner
            from classes.ai_llm_registry import get_default_model_id
        except ImportError as e:
            log.warning("AI agent runner not available: %s", e)
            return (
                "AI agent is not available. Install langchain and langchain-openai (or other providers), "
                "then configure an API key in Preferences > AI."
            )
        resolved_model_id = model_id or get_default_model_id()
        messages = self.current_session.get_conversation_history() if self.current_session else []
        if not messages or messages[-1].get("role") != "user" or messages[-1].get("content") != user_input:
            messages = list(messages) + [{"role": "user", "content": user_input}]
        try:
            main_thread_runner = create_main_thread_runner()
        except Exception as e:
            log.warning("Could not create main thread tool runner: %s", e)
            main_thread_runner = None
        result_holder = [None]
        def run():
            result_holder[0] = run_agent(resolved_model_id, messages, main_thread_runner)
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join()
        return result_holder[0] or "Error: No response from agent."
    
    def attach_context_data(self, context_key: str, context_value: Any):
        """
        Attach context data to the current session
        
        Args:
            context_key: Key for the context
            context_value: The context value
        """
        if not self.current_session:
            self._init_session()
        
        self.current_session.attach_context(context_key, context_value)
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        Get the conversation history
        
        Returns:
            List of messages in the current session
        """
        if not self.current_session:
            return []
        
        return self.current_session.get_conversation_history()
    
    def clear_session(self):
        """Clear the current session and start a new one"""
        self._init_session()
        log.info("Chat session cleared and reset")
    
    def export_session(self) -> str:
        """
        Export the current session as JSON
        
        Returns:
            JSON string of the session data
        """
        if not self.current_session:
            return "{}"
        
        return json.dumps(self.current_session.to_dict(), indent=2, default=str)
    
    def get_session_info(self) -> Dict[str, Any]:
        """
        Get information about the current session
        
        Returns:
            Dictionary with session information
        """
        if not self.current_session:
            return {}
        
        return {
            "session_id": self.current_session.session_id,
            "model": self.current_session.model,
            "message_count": len(self.current_session.messages),
            "user_messages": len(self.current_session.get_user_messages()),
            "assistant_messages": len(self.current_session.get_assistant_messages()),
            "created_at": self.current_session.created_at.isoformat(),
            "updated_at": self.current_session.updated_at.isoformat(),
            "context_keys": list(self.current_session.context_data.keys())
        }
