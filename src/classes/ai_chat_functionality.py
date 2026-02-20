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
import threading
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

from classes.logger import log


def _debug_log(location, message, data, hypothesis_id):
    # #region agent log
    try:
        import os
        _path = "/home/vboxuser/Projects/Flowcut/.cursor/debug.log"
        os.makedirs(os.path.dirname(_path), exist_ok=True)
        with open(_path, "a") as f:
            f.write(json.dumps({"location": location, "message": message, "data": data, "hypothesisId": hypothesis_id, "timestamp": time.time()}) + "\n")
    except Exception:
        pass
    # #endregion


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
    
    def __init__(self, session_id: str = "", model: str = "default", system_prompt: str = "",
                 title: str = "", parent_session_id: str = ""):
        """
        Initialize a chat session
        
        Args:
            session_id: Unique identifier for this session
            model: The AI model to use
            system_prompt: Initial system prompt for the conversation
            title: Display title for the tab UI
            parent_session_id: ID of the session this was carried-forward from (if any)
        """
        self.session_id = session_id
        self.model = model
        self.system_prompt = system_prompt
        self.title = title or "New Chat"
        self.parent_session_id = parent_session_id
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
            "title": self.title,
            "parent_session_id": self.parent_session_id,
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
            "You are an AI assistant for Flowcut. "
            "You help users with video editing, effects, transitions, and general editing tasks. "
            "Provide concise, practical advice for video editing workflows."
        )
    
    def _init_session(self):
        """Initialize a new chat session"""
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

        # #region agent log
        _debug_log("ai_chat_functionality.py:send_message", "send_message entered", {"user_input_len": len(user_input), "model_id": model_id or "(none)"}, "H2")
        # #endregion

        # Add user message to session
        self.current_session.add_message(MessageRole.USER, user_input, context)

        # Generate response from AI provider (agent + LLM)
        response = self._generate_response(user_input, model_id=model_id)
        # #region agent log
        _debug_log("ai_chat_functionality.py:send_message", "send_message returning", {"response_len": len(response) if response else 0}, "H2")
        # #endregion

        # Add assistant message to session
        self.current_session.add_message(MessageRole.ASSISTANT, response)

        return response

    def _generate_response(self, user_input: str, model_id: Optional[str] = None) -> str:
        """
        Generate a response using the LangChain agent and selected LLM, or media manager for media commands.
        Runs the agent in a worker thread; tools run on the Qt main thread.
        """
        # #region agent log
        _debug_log("ai_chat_functionality.py:_generate_response", "entry", {"user_input_preview": user_input[:60] if user_input else ""}, "H4")
        # #endregion

        # Check for product launch video requests FIRST (before media keywords)
        product_launch_keywords = ['product launch', 'launch video', 'promotional video',
                                   'showcase video', 'github video', 'repo video',
                                   'github.com/', 'create.*video.*github', 'video.*for.*repo']
        user_lower = user_input.lower()
        is_product_launch = any(keyword in user_lower for keyword in product_launch_keywords)

        # Check for GitHub URLs explicitly
        if not is_product_launch and ('github.com' in user_lower or 'github/' in user_lower):
            is_product_launch = 'video' in user_lower or 'launch' in user_lower or 'promotional' in user_lower

        # If it's a product launch request, skip media manager and go straight to root agent
        if is_product_launch:
            _debug_log("ai_chat_functionality.py:_generate_response", "product launch detected, routing to root agent", {}, "H4")
            # Skip media manager, fall through to LangChain agent below

        # Check if this is a media management command (from nilay branch)
        elif any(keyword in user_lower for keyword in ['analyze', 'search', 'find', 'collection', 'tag', 'face', 'statistics']):
            # #region agent log
            _debug_log("ai_chat_functionality.py:_generate_response", "taking media path", {}, "H4")
            # #endregion
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
        # #region agent log
        _debug_log("ai_chat_functionality.py:_generate_response", "taking LangChain path", {}, "H5")
        # #endregion
        import threading
        try:
            from classes.ai_agent_runner import run_agent, get_main_thread_runner, create_main_thread_runner
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
        # Use runner created on main thread (avoids deadlock when tools use BlockingQueuedConnection)
        # #region agent log
        _debug_log("ai_chat_functionality.py:_generate_response", "before get_main_thread_runner", {"thread_note": "current thread is worker sub_thread"}, "H3")
        # #endregion
        main_thread_runner = get_main_thread_runner()
        if main_thread_runner is None:
            try:
                main_thread_runner = create_main_thread_runner()
            except Exception as e:
                log.warning("Could not create main thread tool runner: %s", e)
                main_thread_runner = None
        # #region agent log
        _debug_log("ai_chat_functionality.py:_generate_response", "before run_agent (inner thread)", {"runner_ok": main_thread_runner is not None}, "H5")
        # #endregion
        try:
            from plan_graph import get_plan_builder
            get_plan_builder().start_plan(user_input)
        except Exception:
            pass
        result_holder = [None]
        def run():
            result_holder[0] = run_agent(resolved_model_id, messages, main_thread_runner)
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join()
        try:
            from plan_graph import get_plan_builder
            pb = get_plan_builder()
            pb.end_plan()
            from plan_graph import save_plan
            save_plan(pb)
        except Exception:
            pass
        # #region agent log
        _debug_log("ai_chat_functionality.py:_generate_response", "after run_agent join", {"has_result": result_holder[0] is not None}, "H5")
        # #endregion
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


# ---------------------------------------------------------------------------
# Multi-session manager
# ---------------------------------------------------------------------------

class ChatSessionManager:
    """
    Manages multiple AIChat sessions for the tab-based chat UI.

    Thread-safe: all mutations are protected by a lock so the worker pool
    can call ``get_session()`` / ``send_message()`` from any thread.
    """

    def __init__(self):
        self._sessions: Dict[str, AIChat] = {}
        self._active_session_id: Optional[str] = None
        self._lock = threading.Lock()
        # Titles assigned to sessions by the preamble-summary logic
        self._titles: Dict[str, str] = {}

    # -- CRUD ---------------------------------------------------------------

    def create_session(self, model_id: str = "") -> str:
        """Create a new chat session, make it active, and return its session ID."""
        chat = AIChat(model=model_id or "default")
        sid = chat.current_session.session_id
        with self._lock:
            self._sessions[sid] = chat
            self._active_session_id = sid
        log.info("ChatSessionManager: created session %s (model=%s)", sid, model_id)
        return sid

    def get_session(self, session_id: str) -> Optional[AIChat]:
        """Return the AIChat for *session_id*, or None."""
        with self._lock:
            return self._sessions.get(session_id)

    def get_active_session(self) -> Optional[AIChat]:
        """Return the currently-active AIChat."""
        with self._lock:
            if self._active_session_id:
                return self._sessions.get(self._active_session_id)
        return None

    @property
    def active_session_id(self) -> Optional[str]:
        with self._lock:
            return self._active_session_id

    def switch_session(self, session_id: str) -> bool:
        """Set *session_id* as the active session. Returns False if not found."""
        with self._lock:
            if session_id not in self._sessions:
                return False
            self._active_session_id = session_id
        return True

    def close_session(self, session_id: str) -> Optional[str]:
        """
        Remove a session. If it was the active session, activate another one
        (or create a fresh one if none remain). Returns the new active session ID.
        """
        with self._lock:
            self._sessions.pop(session_id, None)
            self._titles.pop(session_id, None)
            if self._active_session_id == session_id:
                if self._sessions:
                    self._active_session_id = next(iter(self._sessions))
                else:
                    self._active_session_id = None
        # If nothing left, create a fresh session
        if self._active_session_id is None:
            return self.create_session()
        return self._active_session_id

    def set_title(self, session_id: str, title: str):
        """Set a display title for a session (called after preamble summary)."""
        with self._lock:
            self._titles[session_id] = title
            chat = self._sessions.get(session_id)
            if chat and chat.current_session:
                chat.current_session.title = title

    # -- Listing ------------------------------------------------------------

    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        Return a list of dicts describing each session, suitable for the
        tab-bar UI. Includes context-usage fraction.
        """
        from classes.ai_context_tracker import get_usage_info
        result = []
        with self._lock:
            for sid, chat in self._sessions.items():
                sess = chat.current_session
                if not sess:
                    continue
                model_id = sess.model if sess.model != "default" else "openai/gpt-4o-mini"
                usage = get_usage_info(model_id, sess.get_conversation_history())
                result.append({
                    "id": sid,
                    "title": self._titles.get(sid) or sess.title or "New Chat",
                    "model": sess.model,
                    "message_count": len(sess.messages),
                    "context_used": usage["used"],
                    "context_total": usage["total"],
                    "context_fraction": usage["fraction"],
                    "active": sid == self._active_session_id,
                })
        return result

    # -- Carry-forward ------------------------------------------------------

    def carry_forward(self, session_id: str, model_id: str = "") -> Optional[str]:
        """
        Summarize the conversation in *session_id*, create a new session
        that starts with the summary as system context, and return its ID.
        Returns None on failure.
        """
        chat = self.get_session(session_id)
        if not chat or not chat.current_session:
            return None

        messages = chat.current_session.get_conversation_history()
        resolved_model = model_id or chat.current_session.model
        if resolved_model == "default":
            try:
                from classes.ai_llm_registry import get_default_model_id
                resolved_model = get_default_model_id()
            except Exception:
                resolved_model = "openai/gpt-4o-mini"

        summary = self._summarize_conversation(resolved_model, messages)
        if not summary:
            summary = "(Previous conversation context could not be summarized.)"

        old_title = self._titles.get(session_id, chat.current_session.title)

        # Create new session with summary injected as system context
        new_chat = AIChat(model=resolved_model)
        new_sid = new_chat.current_session.session_id
        new_chat.current_session.parent_session_id = session_id
        new_chat.current_session.title = old_title + " (cont.)" if old_title else "Continued Chat"
        # Inject summary as a system message
        new_chat.current_session.add_message(
            MessageRole.SYSTEM,
            "The following is a summary of the prior conversation:\n\n" + summary
        )

        with self._lock:
            self._sessions[new_sid] = new_chat
            self._titles[new_sid] = new_chat.current_session.title
            self._active_session_id = new_sid

        log.info("ChatSessionManager: carried forward %s -> %s", session_id, new_sid)
        return new_sid

    @staticmethod
    def _summarize_conversation(model_id: str, messages: List[Dict[str, Any]]) -> str:
        """Use the LLM to produce a concise summary of the conversation."""
        try:
            from classes.ai_llm_registry import get_model
            from langchain_core.messages import SystemMessage, HumanMessage
        except ImportError:
            return ""
        llm = get_model(model_id)
        if not llm:
            return ""
        # Build a text transcript
        lines = []
        for m in messages:
            role = m.get("role", "unknown")
            content = m.get("content", "")
            if isinstance(content, list):
                content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
            if role == "system":
                continue
            lines.append(f"{role}: {content}")
        transcript = "\n".join(lines)
        system = (
            "Summarize the following conversation concisely. "
            "Preserve key decisions, context, and any pending tasks or questions. "
            "Reply with only the summary, no preamble."
        )
        try:
            response = llm.invoke([SystemMessage(content=system), HumanMessage(content=transcript)])
            out = (response.content if hasattr(response, "content") else str(response)).strip()
            return out[:4000] if out else ""
        except Exception as exc:
            log.warning("carry_forward summarization failed: %s", exc)
            return ""

    # -- Convenience --------------------------------------------------------

    def ensure_session(self, model_id: str = "") -> str:
        """If no sessions exist, create one and return its ID."""
        with self._lock:
            if self._sessions:
                return self._active_session_id or next(iter(self._sessions))
        return self.create_session(model_id)
