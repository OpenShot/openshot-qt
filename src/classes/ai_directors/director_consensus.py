"""
Director Consensus

Handles debate logic and consensus-building between directors.
"""

from typing import List, Dict, Any
from classes.logger import log
from classes.ai_directors.director_agent import Director, DirectorAnalysis, DirectorResponse
from classes.ai_directors.director_plan import DebateMessage


class DirectorDebate:
    """
    Manages multi-round debate between directors.

    Directors review each other's analyses and provide feedback,
    leading to consensus or presenting multiple alternatives.
    """

    def __init__(self, directors: List[Director], max_rounds: int = 3):
        self.directors = directors
        self.max_rounds = max_rounds
        self.rounds: List[List[DebateMessage]] = []

    def run_debate(
        self,
        analyses: List[DirectorAnalysis],
    ) -> List[DebateMessage]:
        """
        Run structured debate between directors.

        Args:
            analyses: Initial analyses from each director

        Returns:
            Full debate transcript as list of DebateMessages
        """
        all_messages = []

        # Round 0: Initial analyses
        for analysis in analyses:
            message = DebateMessage(
                director_id=analysis.director_id,
                director_name=analysis.director_name,
                round_number=0,
                message_type="analysis",
                content=analysis.analysis_text,
                references=[],
            )
            all_messages.append(message)

        # Debate rounds
        for round_num in range(1, self.max_rounds + 1):
            log.info(f"Debate round {round_num}/{self.max_rounds}")

            round_messages = self._debate_round(analyses, round_num)
            all_messages.extend(round_messages)

            # Check for convergence
            if self._has_converged(round_messages):
                log.info(f"Consensus reached in round {round_num}")
                break

        return all_messages

    def _debate_round(
        self,
        analyses: List[DirectorAnalysis],
        round_number: int,
    ) -> List[DebateMessage]:
        """
        Execute one round of debate.

        Each director reviews peer analyses and provides responses.

        Args:
            analyses: Current analyses from all directors
            round_number: Current round number

        Returns:
            Messages from this round
        """
        round_messages = []

        # TODO: Implement actual debate with LLM
        # For now, placeholder
        for director in self.directors:
            response = director.critique_peer_analysis(analyses, round_number)

            # Convert response to debate message
            content = f"Round {round_number} response from {director.name}"
            message = DebateMessage(
                director_id=director.id,
                director_name=director.name,
                round_number=round_number,
                message_type="critique",
                content=content,
                references=[a.director_id for a in analyses if a.director_id != director.id],
            )
            round_messages.append(message)

        return round_messages

    def _has_converged(self, round_messages: List[DebateMessage]) -> bool:
        """
        Check if directors have reached consensus.

        Args:
            round_messages: Messages from current round

        Returns:
            True if consensus reached
        """
        # TODO: Implement convergence detection
        # Check for agreement keywords, similar recommendations, etc.
        return False


class ConsensusBuilder:
    """
    Builds consensus plan from director analyses and debate.

    Aggregates recommendations, resolves conflicts, and creates
    unified execution plan.
    """

    def __init__(self):
        pass

    def build_plan(
        self,
        task: str,
        analyses: List[DirectorAnalysis],
        debate_messages: List[DebateMessage],
    ):
        """
        Build consensus plan from analyses and debate.

        Args:
            task: Original user task
            analyses: Director analyses
            debate_messages: Full debate transcript

        Returns:
            DirectorPlan
        """
        from classes.ai_directors.director_plan import DirectorPlan

        # TODO: Implement plan building
        # - Extract recommendations from all directors
        # - Identify common themes
        # - Resolve conflicts (voting, priority, etc.)
        # - Create ordered steps with dependencies
        # - Add alternatives for contested decisions

        plan = DirectorPlan(
            title=f"Consensus Plan: {task}",
            summary="Aggregated from director debate",
            created_by=[a.director_id for a in analyses],
        )

        # Add debate transcript
        for message in debate_messages:
            plan.add_debate_message(message)

        return plan
