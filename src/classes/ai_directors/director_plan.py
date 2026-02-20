"""
Director Plan Data Structures

Defines the plan format that directors produce after analysis and debate.
Plans contain ordered execution steps with dependencies, confidence scores,
alternatives, and debate transcripts.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict


class PlanStepType(Enum):
    """Types of plan steps that can be executed."""
    EDIT_TIMELINE = "edit_timeline"
    ADD_TRANSITION = "add_transition"
    ADJUST_AUDIO = "adjust_audio"
    ADD_EFFECT = "add_effect"
    GENERATE_CONTENT = "generate_content"
    SPLIT_CLIP = "split_clip"
    REORDER_CLIPS = "reorder_clips"
    ADD_MUSIC = "add_music"
    ADD_VOICE = "add_voice"
    REMOVE_CLIP = "remove_clip"


@dataclass
class PlanStep:
    """Single step in execution plan."""
    step_id: str
    type: PlanStepType
    description: str
    agent: str  # "video", "manim", "voice", "music"
    tool_name: str
    tool_args: Dict[str, Any]
    rationale: str
    confidence: float  # 0.0-1.0
    dependencies: List[str] = field(default_factory=list)  # step_ids that must run first
    estimated_duration: float = 0.0  # seconds
    director_notes: Dict[str, str] = field(default_factory=dict)  # director_id -> note

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "step_id": self.step_id,
            "type": self.type.value,
            "description": self.description,
            "agent": self.agent,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "dependencies": self.dependencies,
            "estimated_duration": self.estimated_duration,
            "director_notes": self.director_notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlanStep':
        """Create from dictionary."""
        data_copy = data.copy()
        data_copy['type'] = PlanStepType(data_copy['type'])
        return cls(**data_copy)


@dataclass
class PlanAlternative:
    """Alternative approach for a step or set of steps."""
    alternative_id: str
    replaces_step_ids: List[str]  # Steps this alternative replaces
    description: str
    steps: List[PlanStep]
    pros: List[str]
    cons: List[str]
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alternative_id": self.alternative_id,
            "replaces_step_ids": self.replaces_step_ids,
            "description": self.description,
            "steps": [step.to_dict() for step in self.steps],
            "pros": self.pros,
            "cons": self.cons,
            "confidence": self.confidence,
        }


@dataclass
class DebateMessage:
    """Single message in director debate."""
    director_id: str
    director_name: str
    round_number: int
    message_type: str  # "analysis", "critique", "agreement", "proposal", "synthesis"
    content: str
    references: List[str] = field(default_factory=list)  # director_ids being responded to
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class DirectorPlan:
    """
    Complete execution plan from directors.

    Contains ordered steps, alternatives, confidence scores,
    and full debate transcript.
    """

    def __init__(
        self,
        title: str = "",
        summary: str = "",
        created_by: Optional[List[str]] = None,
    ):
        self.plan_id = str(uuid.uuid4())
        self.title = title
        self.summary = summary
        self.created_by = created_by or []  # List of director IDs
        self.steps: List[PlanStep] = []
        self.alternatives: List[PlanAlternative] = []
        self.confidence = 0.0
        self.estimated_total_duration = 0.0
        self.debate_transcript: List[DebateMessage] = []
        self.created_at = datetime.now()
        self.metadata: Dict[str, Any] = {}

    def add_step(self, step: PlanStep):
        """Add a step to the plan."""
        self.steps.append(step)
        self.estimated_total_duration += step.estimated_duration

    def add_alternative(self, alternative: PlanAlternative):
        """Add an alternative approach."""
        self.alternatives.append(alternative)

    def add_debate_message(self, message: DebateMessage):
        """Add a message to the debate transcript."""
        self.debate_transcript.append(message)

    def validate(self) -> tuple[bool, str]:
        """
        Validate plan for circular dependencies and invalid references.

        Returns:
            (is_valid, error_message)
        """
        step_ids = {step.step_id for step in self.steps}

        # Check for invalid dependencies
        for step in self.steps:
            for dep_id in step.dependencies:
                if dep_id not in step_ids:
                    return False, f"Step {step.step_id} depends on non-existent step {dep_id}"

        # Check for circular dependencies using DFS
        visited = set()
        rec_stack = set()

        def has_cycle(step_id: str) -> bool:
            visited.add(step_id)
            rec_stack.add(step_id)

            # Find step
            step = next((s for s in self.steps if s.step_id == step_id), None)
            if not step:
                return False

            # Check dependencies
            for dep_id in step.dependencies:
                if dep_id not in visited:
                    if has_cycle(dep_id):
                        return True
                elif dep_id in rec_stack:
                    return True

            rec_stack.remove(step_id)
            return False

        for step in self.steps:
            if step.step_id not in visited:
                if has_cycle(step.step_id):
                    return False, "Circular dependency detected in plan steps"

        return True, ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON."""
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "summary": self.summary,
            "created_by": self.created_by,
            "steps": [step.to_dict() for step in self.steps],
            "alternatives": [alt.to_dict() for alt in self.alternatives],
            "confidence": self.confidence,
            "estimated_total_duration": self.estimated_total_duration,
            "debate_transcript": [msg.to_dict() for msg in self.debate_transcript],
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DirectorPlan':
        """Deserialize from dictionary."""
        plan = cls(
            title=data.get("title", ""),
            summary=data.get("summary", ""),
            created_by=data.get("created_by", []),
        )
        plan.plan_id = data.get("plan_id", str(uuid.uuid4()))
        plan.steps = [PlanStep.from_dict(s) for s in data.get("steps", [])]
        plan.confidence = data.get("confidence", 0.0)
        plan.estimated_total_duration = data.get("estimated_total_duration", 0.0)
        plan.metadata = data.get("metadata", {})

        # Reconstruct debate transcript
        for msg_data in data.get("debate_transcript", []):
            plan.debate_transcript.append(DebateMessage(**msg_data))

        return plan
