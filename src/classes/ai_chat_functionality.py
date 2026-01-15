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
    
    def send_message(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Send a message and get a response
        
        Args:
            user_input: The user's message
            context: Optional context to attach to the message
        
        Returns:
            The AI assistant's response
        """
        if not self.current_session:
            self._init_session()
        
        # Add user message to session
        self.current_session.add_message(MessageRole.USER, user_input, context)
        
        # Generate response from AI provider
        response = self._generate_response(user_input)
        
        # Add assistant message to session
        self.current_session.add_message(MessageRole.ASSISTANT, response)
        
        return response
    
    def _generate_response(self, user_input: str) -> str:
        """
        Generate a response from the AI provider
        
        Args:
            user_input: The user's message
        
        Returns:
            The AI's response
        """
        # This is a placeholder. In a real implementation, you would:
        # 1. Call an actual AI API (OpenAI, Anthropic, local LLM, etc.)
        # 2. Pass the conversation history
        # 3. Return the generated response
        
        # For now, return a placeholder response
        log.debug(f"Generating response for: {user_input}")
        
        # Placeholder implementation - can be extended with real AI integration
        response = (
            f"I understand you're asking about video editing. "
            f"This is a placeholder response. "
            f"To use real AI responses, configure an AI provider in the preferences."
        )
        
        return response
    
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
