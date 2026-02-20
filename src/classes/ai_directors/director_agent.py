"""
Director Agent

Represents a director that analyzes video projects and provides critiques.
Directors are meta-agents that use read-only analysis tools and don't
execute changes directly.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DirectorPersonality:
    """Defines director's analysis approach and style."""
    system_prompt: str
    analysis_focus: List[str]  # ["pacing", "audio", "visual", "story", "retention"]
    critique_style: str  # "constructive", "aggressive", "technical", "artistic"
    expertise_areas: List[str]  # ["retention", "aesthetics", "storytelling", "technical"]


@dataclass
class DirectorTraining:
    """Training data for director's decision-making."""
    type: str  # "examples", "videos", "guidelines"
    data: Dict[str, Any]


@dataclass
class DirectorMetadata:
    """Director metadata."""
    id: str
    name: str
    version: str
    author: str
    description: str
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class DirectorAnalysis:
    """Result of a director's analysis."""
    director_id: str
    director_name: str
    analysis_text: str
    issues_found: List[Dict[str, Any]]  # [{type, severity, description, suggestion}]
    strengths: List[str]
    overall_score: float  # 0.0-10.0
    recommendations: List[str]
    confidence: float  # 0.0-1.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class DirectorResponse:
    """Response to peer directors' analyses during debate."""
    director_id: str
    director_name: str
    round_number: int
    agreements: List[str]  # Points agreed with other directors
    disagreements: List[str]  # Points disagreed with other directors
    new_insights: List[str]  # New points raised
    revised_recommendations: List[str]  # Updated recommendations based on debate


class Director:
    """
    Represents a director agent that analyzes video projects.

    Directors use read-only tools to analyze projects and provide
    critiques from their unique perspective (YouTube, GenZ, Cinematic, etc.)
    """

    def __init__(
        self,
        metadata: DirectorMetadata,
        personality: DirectorPersonality,
        training: Optional[DirectorTraining] = None,
        settings: Optional[Dict[str, Any]] = None,
    ):
        self.metadata = metadata
        self.personality = personality
        self.training = training
        self.settings = settings or {}
        self.analysis_history: List[DirectorAnalysis] = []

    @property
    def id(self) -> str:
        """Get director ID."""
        return self.metadata.id

    @property
    def name(self) -> str:
        """Get director name."""
        return self.metadata.name

    def get_system_prompt(self) -> str:
        """
        Build complete system prompt for this director.

        Combines personality, expertise, and critique style.
        """
        focus_str = ", ".join(self.personality.analysis_focus)
        expertise_str = ", ".join(self.personality.expertise_areas)

        prompt = f"""{self.personality.system_prompt}

Your name is {self.name} and you are a {self.metadata.description}.

Analysis Focus: {focus_str}
Expertise Areas: {expertise_str}
Critique Style: {self.personality.critique_style}

When analyzing videos:
1. Focus on your areas of expertise
2. Provide specific, actionable feedback
3. Use a {self.personality.critique_style} tone
4. Support critiques with reasoning
5. Consider the target audience and platform

Provide analysis in this format:
- Overall Assessment: Brief summary (1-2 sentences)
- Strengths: What works well (2-3 points)
- Issues: Problems found with severity and specific timestamps/locations
- Recommendations: Specific, actionable improvements
- Confidence: How confident you are in your analysis (0.0-1.0)
"""
        return prompt

    def analyze_project(self, model_id: str, analysis_tools: List, main_thread_runner) -> DirectorAnalysis:
        """
        Analyze project using available tools and LLM.

        Args:
            model_id: LLM model to use
            analysis_tools: Tools available for analysis (from director_tools.py)
            main_thread_runner: Tool runner for executing analysis tools

        Returns:
            DirectorAnalysis with findings
        """
        from classes.logger import log
        from classes.ai_agent_runner import run_agent_with_tools
        from langchain_core.messages import HumanMessage

        try:
            # Build analysis prompt
            analysis_prompt = f"""Analyze the current video project and provide detailed feedback.

Task: Analyze the video project from your perspective as {self.name}.

IMPORTANT: You have analysis tools available. IMMEDIATELY use ALL of these tools to analyze the project:
- get_project_metadata_tool: Get project metadata
- analyze_timeline_structure_tool: Analyze timeline structure
- analyze_pacing_tool: Analyze pacing
- analyze_audio_levels_tool: Analyze audio
- analyze_transitions_tool: Analyze transitions
- analyze_clip_content_tool: Analyze clip content
- analyze_music_sync_tool: Analyze music sync

DO NOT ask the user to specify files. The tools analyze the entire project automatically.

After gathering data from ALL tools:
1. Focus on your areas of expertise: {', '.join(self.personality.expertise_areas)}
2. Provide specific, actionable feedback
3. Structure your response as:
   - Overall Assessment (1-2 sentences)
   - Strengths (2-3 bullet points)
   - Issues Found (list with severity: high/medium/low)
   - Recommendations (specific, actionable improvements)
   - Confidence (0.0-1.0 in your analysis)

Be thorough but concise. Focus on what matters most for the target audience."""

            messages = [HumanMessage(content=analysis_prompt)]

            # Run agent with analysis tools
            log.info(f"{self.name}: Starting analysis...")
            response = run_agent_with_tools(
                model_id=model_id,
                messages=messages,
                tools=analysis_tools,
                main_thread_runner=main_thread_runner,
                system_prompt=self.get_system_prompt(),
                max_iterations=10,
            )

            # Parse response into DirectorAnalysis
            # For now, store full response as analysis_text
            # TODO: Parse structured fields (issues, strengths, etc.)
            analysis = DirectorAnalysis(
                director_id=self.id,
                director_name=self.name,
                analysis_text=response,
                issues_found=[],  # TODO: Parse from response
                strengths=[],  # TODO: Parse from response
                overall_score=7.5,  # TODO: Parse from response
                recommendations=[],  # TODO: Parse from response
                confidence=0.8,
            )

            log.info(f"{self.name}: Analysis complete")
            return analysis

        except Exception as e:
            log.error(f"{self.name}: Analysis failed: {e}", exc_info=True)
            return DirectorAnalysis(
                director_id=self.id,
                director_name=self.name,
                analysis_text=f"Analysis failed: {e}",
                issues_found=[],
                strengths=[],
                overall_score=0.0,
                recommendations=[],
                confidence=0.0,
            )

    def critique_peer_analysis(
        self,
        model_id: str,
        peer_analyses: List[DirectorAnalysis],
        round_number: int,
    ) -> DirectorResponse:
        """
        Respond to other directors' analyses during debate.

        Args:
            model_id: LLM model to use
            peer_analyses: Analyses from other directors
            round_number: Current debate round

        Returns:
            DirectorResponse with reactions to peer feedback
        """
        from classes.logger import log
        from classes.ai_llm_registry import get_model
        from langchain_core.messages import SystemMessage, HumanMessage

        try:
            # Build debate prompt with peer analyses
            peer_summaries = []
            for analysis in peer_analyses:
                if analysis.director_id != self.id:
                    peer_summaries.append(f"**{analysis.director_name}:**\n{analysis.analysis_text[:500]}...")

            debate_prompt = f"""Round {round_number} of director debate.

You are {self.name}. You've seen analyses from other directors. Respond with:

1. **Agreements**: Points where you agree with other directors
2. **Disagreements**: Points where you respectfully disagree (with reasoning)
3. **New Insights**: Additional observations based on the discussion
4. **Revised Recommendations**: Updated suggestions considering all perspectives

Other Directors' Analyses:
{chr(10).join(peer_summaries)}

Provide a thoughtful response that advances the discussion toward consensus."""

            llm = get_model(model_id)
            messages = [
                SystemMessage(content=self.get_system_prompt()),
                HumanMessage(content=debate_prompt),
            ]

            response = llm.invoke(messages)
            response_text = response.content if hasattr(response, 'content') else str(response)

            # Parse response
            # TODO: Structure parsing for agreements, disagreements, etc.
            return DirectorResponse(
                director_id=self.id,
                director_name=self.name,
                round_number=round_number,
                agreements=[],  # TODO: Parse
                disagreements=[],  # TODO: Parse
                new_insights=[],  # TODO: Parse
                revised_recommendations=[],  # TODO: Parse
            )

        except Exception as e:
            log.error(f"{self.name}: Debate response failed: {e}", exc_info=True)
            return DirectorResponse(
                director_id=self.id,
                director_name=self.name,
                round_number=round_number,
                agreements=[],
                disagreements=[],
                new_insights=[],
                revised_recommendations=[],
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization (.director file format)."""
        return {
            "id": self.metadata.id,
            "name": self.metadata.name,
            "version": self.metadata.version,
            "author": self.metadata.author,
            "description": self.metadata.description,
            "tags": self.metadata.tags,
            "created_at": self.metadata.created_at,
            "updated_at": self.metadata.updated_at,
            "personality": {
                "system_prompt": self.personality.system_prompt,
                "analysis_focus": self.personality.analysis_focus,
                "critique_style": self.personality.critique_style,
                "expertise_areas": self.personality.expertise_areas,
            },
            "training": {
                "type": self.training.type,
                "data": self.training.data,
            } if self.training else None,
            "settings": self.settings,
        }
