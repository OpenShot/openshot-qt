"""
Director Voting System

Enables pre-execution voting where directors review and vote on proposed plan steps.
Supports approve/conditional/reject votes with conflict resolution.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
from enum import Enum
import json

from classes.logger import log


class VoteType(Enum):
    """Vote options for directors"""
    APPROVE = "approve"
    CONDITIONAL = "conditional"
    REJECT = "reject"


@dataclass
class DirectorVote:
    """A single director's vote on a plan step"""
    director_id: str
    director_name: str
    step_id: str
    vote: VoteType
    confidence: float
    rationale: str
    suggested_modifications: Dict[str, Any] = field(default_factory=dict)


class DirectorVotingPhase:
    """Manages pre-execution voting by directors"""

    def __init__(self, directors: List):
        """
        Initialize voting phase.

        Args:
            directors: List of Director objects
        """
        self.directors = directors

    def run_voting(
        self,
        plan,
        analyses: List,
        model_id: str,
    ) -> Dict[str, List[DirectorVote]]:
        """
        Run voting phase where each director votes on each step.

        Args:
            plan: DirectorPlan with steps to vote on
            analyses: List of DirectorAnalysis from initial analysis phase
            model_id: LLM model to use

        Returns:
            Dictionary mapping step_id to list of DirectorVotes
        """
        log.info(f"Phase 4: Running voting with {len(self.directors)} directors on {len(plan.steps)} steps")

        voting_results = {}

        for step in plan.steps:
            step_votes = []

            for director in self.directors:
                try:
                    vote = self._get_director_vote(director, step, plan, analyses, model_id)
                    step_votes.append(vote)
                    log.debug(f"{director.name} voted {vote.vote.value} on step {step.step_id[:8]}")
                except Exception as e:
                    log.error(f"Failed to get vote from {director.name}: {e}", exc_info=True)
                    # Create default approve vote on error
                    step_votes.append(DirectorVote(
                        director_id=director.id,
                        director_name=director.name,
                        step_id=step.step_id,
                        vote=VoteType.APPROVE,
                        confidence=0.5,
                        rationale="Default vote due to error",
                        suggested_modifications={}
                    ))

            voting_results[step.step_id] = step_votes

        return voting_results

    def _get_director_vote(
        self,
        director,
        step,
        plan,
        analyses: List,
        model_id: str,
    ) -> DirectorVote:
        """
        Get a single director's vote on a step.

        Args:
            director: Director object
            step: PlanStep to vote on
            plan: Full DirectorPlan for context
            analyses: Director analyses
            model_id: LLM model ID

        Returns:
            DirectorVote
        """
        voting_prompt = f"""Review this proposed action step and vote on whether it should be executed.

PROPOSED STEP:
  Description: {step.description}
  Tool: {step.tool_name}
  Arguments: {json.dumps(step.tool_args, indent=2)}
  Agent: {step.agent}
  Rationale: {step.rationale}
  Confidence: {step.confidence}

YOUR PERSPECTIVE as {director.name}:
{director.get_system_prompt()[:500]}

VOTE OPTIONS:
1. APPROVE - Execute as proposed (no changes needed)
2. CONDITIONAL - Approve with modifications (suggest specific changes to tool_args)
3. REJECT - Do not execute (explain why this would harm the video)

Respond ONLY with valid JSON in this exact format:
{{
  "vote": "approve|conditional|reject",
  "confidence": 0.85,
  "rationale": "Brief explanation of your vote",
  "suggested_modifications": {{
    "tool_args": {{"param_name": new_value}}
  }}
}}

Be concise and specific. Focus on your area of expertise."""

        try:
            # Call LLM
            from classes.ai_llm_registry import get_model
            from langchain_core.messages import SystemMessage, HumanMessage

            llm = get_model(model_id)
            response = llm.invoke([
                SystemMessage(content=director.get_system_prompt()),
                HumanMessage(content=voting_prompt)
            ])

            response_text = response.content if hasattr(response, 'content') else str(response)

            # Parse JSON response
            # Extract JSON from response (handle markdown code blocks)
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                vote_data = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in response")

            # Validate vote type
            vote_str = vote_data.get('vote', 'approve').lower()
            if vote_str not in ['approve', 'conditional', 'reject']:
                vote_str = 'approve'

            return DirectorVote(
                director_id=director.id,
                director_name=director.name,
                step_id=step.step_id,
                vote=VoteType(vote_str),
                confidence=float(vote_data.get('confidence', 0.7)),
                rationale=vote_data.get('rationale', 'No rationale provided'),
                suggested_modifications=vote_data.get('suggested_modifications', {}),
            )

        except Exception as e:
            log.error(f"Failed to parse vote from {director.name}: {e}", exc_info=True)
            # Default to approve on parse error
            return DirectorVote(
                director_id=director.id,
                director_name=director.name,
                step_id=step.step_id,
                vote=VoteType.APPROVE,
                confidence=0.6,
                rationale=f"Default approve (parsing error: {str(e)[:100]})",
                suggested_modifications={}
            )

    def resolve_votes(
        self,
        voting_results: Dict[str, List[DirectorVote]]
    ) -> Dict[str, Dict]:
        """
        Determine consensus for each step based on votes.

        Args:
            voting_results: Dictionary mapping step_id to list of votes

        Returns:
            Dictionary mapping step_id to resolution:
            {
                "approved": bool,
                "modifications": dict,
                "consensus": str,
                "votes": {"approve": int, "conditional": int, "reject": int}
            }
        """
        resolutions = {}

        for step_id, votes in voting_results.items():
            approve_count = sum(1 for v in votes if v.vote == VoteType.APPROVE)
            conditional_count = sum(1 for v in votes if v.vote == VoteType.CONDITIONAL)
            reject_count = sum(1 for v in votes if v.vote == VoteType.REJECT)

            total = len(votes)
            approval_rate = approve_count / total if total > 0 else 0

            # Consensus rules
            if approval_rate >= 0.7:
                # Strong approval (70%+ approve)
                approved = True
                consensus = "Strong approval"
                modifications = {}

            elif (approve_count + conditional_count) / total >= 0.7:
                # Conditional approval (70%+ approve or conditional)
                approved = True
                consensus = "Conditional approval"

                # Merge suggested modifications from conditional votes
                modifications = self._merge_modifications(
                    [v.suggested_modifications for v in votes if v.vote == VoteType.CONDITIONAL]
                )

            else:
                # Insufficient consensus (too many rejections)
                approved = False
                consensus = "Insufficient consensus"
                modifications = {}

            resolutions[step_id] = {
                "approved": approved,
                "modifications": modifications,
                "consensus": consensus,
                "votes": {
                    "approve": approve_count,
                    "conditional": conditional_count,
                    "reject": reject_count,
                }
            }

            log.debug(f"Step {step_id[:8]}: {consensus} (A:{approve_count} C:{conditional_count} R:{reject_count})")

        return resolutions

    def _merge_modifications(self, modifications_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge suggested modifications from multiple directors.

        Takes the median or most common value for each parameter.

        Args:
            modifications_list: List of modification dictionaries

        Returns:
            Merged modifications dictionary
        """
        if not modifications_list:
            return {}

        merged = {}

        # Collect all suggested tool_args
        all_tool_args = []
        for mods in modifications_list:
            if 'tool_args' in mods and isinstance(mods['tool_args'], dict):
                all_tool_args.append(mods['tool_args'])

        if not all_tool_args:
            return {}

        # For each parameter, take the median value
        param_values = {}
        for tool_args in all_tool_args:
            for key, value in tool_args.items():
                if key not in param_values:
                    param_values[key] = []
                param_values[key].append(value)

        # Calculate median or most common value
        merged_tool_args = {}
        for key, values in param_values.items():
            if all(isinstance(v, (int, float)) for v in values):
                # Numeric: take median
                sorted_values = sorted(values)
                median_idx = len(sorted_values) // 2
                merged_tool_args[key] = sorted_values[median_idx]
            else:
                # Non-numeric: take most common
                from collections import Counter
                most_common = Counter(values).most_common(1)
                if most_common:
                    merged_tool_args[key] = most_common[0][0]

        return {"tool_args": merged_tool_args}
