"""
AI Directors System

This module implements the directors system where multiple AI agents (directors)
analyze video projects, critique them from different perspectives, interact in
debate-style discussions, and produce actionable editing plans.

Architecture:
- Directors are meta-agents that analyze but don't execute
- Directors use read-only analysis tools
- Multiple directors debate to reach consensus
- Plans are reviewed and approved by users before execution
"""

from classes.ai_directors.director_agent import Director, DirectorMetadata, DirectorPersonality
from classes.ai_directors.director_loader import DirectorLoader
from classes.ai_directors.director_plan import DirectorPlan, PlanStep, PlanStepType
from classes.ai_directors.director_orchestrator import DirectorOrchestrator

__all__ = [
    'Director',
    'DirectorMetadata',
    'DirectorPersonality',
    'DirectorLoader',
    'DirectorPlan',
    'PlanStep',
    'PlanStepType',
    'DirectorOrchestrator',
]
