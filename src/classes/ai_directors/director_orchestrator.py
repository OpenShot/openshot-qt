"""
Director Orchestrator

Coordinates multiple directors through analysis, debate, and consensus phases.
"""

from typing import List, Dict, Any
import concurrent.futures
from classes.logger import log
from classes.ai_directors.director_agent import Director, DirectorAnalysis
from classes.ai_directors.director_plan import DirectorPlan, DebateMessage


class DirectorOrchestrator:
    """
    Orchestrates multiple directors through the analysis and debate process.

    Flow:
    1. Phase 1: Parallel analysis (each director analyzes independently)
    2. Phase 2: Structured debate (directors respond to each other)
    3. Phase 3: Consensus synthesis (aggregate into unified plan)
    """

    def __init__(
        self,
        directors: List[Director],
        max_debate_rounds: int = 3,
        max_workers: int = 3,
    ):
        self.directors = directors
        self.max_debate_rounds = max_debate_rounds
        self.max_workers = max_workers

    def run_directors(
        self,
        model_id: str,
        task: str,
        main_thread_runner,
        project_data: Dict[str, Any],
    ) -> DirectorPlan:
        """
        Run full director workflow: analysis → debate → synthesis → voting.

        Args:
            model_id: LLM model to use
            task: User's task/request
            main_thread_runner: MainThreadToolRunner for tool execution
            project_data: Current project state

        Returns:
            DirectorPlan with aggregated recommendations and voting results
        """
        log.info(f"Running {len(self.directors)} directors for task: {task}")
        self.model_id = model_id
        self.main_thread_runner = main_thread_runner

        # Get thinking dock for streaming updates
        thinking_dock = self._get_thinking_dock()

        # Phase 1: Parallel analysis
        if thinking_dock:
            thinking_dock.set_phase("Phase 1: Analysis")
            thinking_dock.add_message(
                "Orchestrator",
                f"Starting analysis with {len(self.directors)} directors...",
                "decision"
            )

        analyses = self._parallel_analysis(project_data, thinking_dock)

        # Phase 2: Structured debate
        if thinking_dock:
            thinking_dock.set_phase("Phase 2: Debate")
            thinking_dock.add_message(
                "Orchestrator",
                f"Directors are now debating their findings...",
                "decision"
            )

        debate_messages = self._run_debate(analyses, thinking_dock)

        # Phase 3: Synthesize consensus plan
        if thinking_dock:
            thinking_dock.set_phase("Phase 3: Synthesis")
            thinking_dock.add_message(
                "Orchestrator",
                "Synthesizing consensus plan from all analyses and debate...",
                "decision"
            )

        plan = self._synthesize_consensus(task, analyses, debate_messages)

        if thinking_dock:
            thinking_dock.add_message(
                "Orchestrator",
                f"Generated plan with {len(plan.steps)} steps",
                "decision"
            )

        # Phase 4: Voting
        if thinking_dock:
            thinking_dock.set_phase("Phase 4: Voting")
            thinking_dock.add_message(
                "Orchestrator",
                "Directors are now voting on each proposed step...",
                "decision"
            )

        try:
            from classes.ai_directors.director_voting import DirectorVotingPhase

            voting_phase = DirectorVotingPhase(self.directors)
            voting_results = voting_phase.run_voting(plan, analyses, model_id)

            # Stream voting results to thinking dock
            if thinking_dock:
                for step in plan.steps:
                    votes = voting_results.get(step.step_id, [])
                    for vote in votes:
                        thinking_dock.add_message(
                            vote.director_name,
                            f"Vote: {vote.vote.value.upper()} - {vote.rationale}",
                            "voting"
                        )

            # Resolve votes
            resolutions = voting_phase.resolve_votes(voting_results)

            # Apply resolutions to plan
            plan = self._apply_voting_resolutions(plan, voting_results, resolutions)

            if thinking_dock:
                thinking_dock.add_message(
                    "Orchestrator",
                    "Voting complete. Plan updated based on director consensus.",
                    "decision"
                )
                thinking_dock.set_phase("Complete")

        except Exception as e:
            log.error(f"Voting phase failed: {e}", exc_info=True)
            if thinking_dock:
                thinking_dock.add_message(
                    "Orchestrator",
                    f"Voting phase encountered an error: {str(e)[:100]}",
                    "decision"
                )

        log.info(f"Generated plan with {len(plan.steps)} steps (after voting)")
        return plan

    def _parallel_analysis(self, project_data: Dict[str, Any], thinking_dock=None) -> List[DirectorAnalysis]:
        """
        Run directors in parallel for independent analysis.

        Args:
            project_data: Current project state
            thinking_dock: Optional ThinkingDockWidget for streaming updates

        Returns:
            List of DirectorAnalysis from each director
        """
        log.info(f"Phase 1: Parallel analysis with {len(self.directors)} directors")

        # Stream start messages
        if thinking_dock:
            for director in self.directors:
                thinking_dock.add_message(
                    director.name,
                    f"Starting analysis from {director.name} perspective...",
                    "analysis"
                )

        # Get analysis tools
        from classes.ai_directors.director_tools import get_director_analysis_tools_for_langchain
        analysis_tools = get_director_analysis_tools_for_langchain()

        analyses = []

        # Run directors in parallel with ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_director = {
                executor.submit(
                    director.analyze_project,
                    self.model_id,
                    analysis_tools,
                    self.main_thread_runner
                ): director
                for director in self.directors
            }

            for future in concurrent.futures.as_completed(future_to_director):
                director = future_to_director[future]
                try:
                    analysis = future.result()
                    analyses.append(analysis)
                    log.info(f"{director.name}: Analysis complete")

                    if thinking_dock:
                        thinking_dock.add_message(
                            director.name,
                            f"Analysis complete. Overall assessment: {analysis.analysis_text[:100]}...",
                            "analysis"
                        )

                except Exception as e:
                    log.error(f"{director.name}: Analysis failed: {e}", exc_info=True)
                    if thinking_dock:
                        thinking_dock.add_message(
                            director.name,
                            f"Analysis failed: {str(e)[:100]}",
                            "analysis"
                        )

        return analyses

    def _run_debate(self, analyses: List[DirectorAnalysis], thinking_dock=None) -> List[DebateMessage]:
        """
        Run structured debate between directors.

        Args:
            analyses: Initial analyses from each director
            thinking_dock: Optional ThinkingDockWidget for streaming updates

        Returns:
            List of DebateMessages from the debate
        """
        log.info(f"Phase 2: Running debate ({self.max_debate_rounds} rounds)")

        debate_messages = []

        # Add initial analyses as debate messages
        for analysis in analyses:
            message = DebateMessage(
                director_id=analysis.director_id,
                director_name=analysis.director_name,
                round_number=0,
                message_type="analysis",
                content=analysis.analysis_text,
                references=[],
            )
            debate_messages.append(message)

        # Run debate rounds
        for round_num in range(1, self.max_debate_rounds + 1):
            log.info(f"Debate round {round_num}/{self.max_debate_rounds}")

            if thinking_dock:
                thinking_dock.add_message(
                    "Orchestrator",
                    f"Round {round_num}/{self.max_debate_rounds}",
                    "debate"
                )

            # Each director critiques peer analyses
            for director in self.directors:
                try:
                    response = director.critique_peer_analysis(
                        self.model_id,
                        analyses,
                        round_num,
                    )

                    # Convert response to debate message
                    content = f"Round {round_num} response from {director.name}"
                    if response.agreements:
                        content += f"\n\nAgreements: {', '.join(response.agreements)}"
                    if response.disagreements:
                        content += f"\n\nDisagreements: {', '.join(response.disagreements)}"
                    if response.new_insights:
                        content += f"\n\nNew Insights: {', '.join(response.new_insights)}"
                    if response.revised_recommendations:
                        content += f"\n\nRevised Recommendations: {', '.join(response.revised_recommendations)}"

                    message = DebateMessage(
                        director_id=director.id,
                        director_name=director.name,
                        round_number=round_num,
                        message_type="critique",
                        content=content,
                        references=[a.director_id for a in analyses if a.director_id != director.id],
                    )
                    debate_messages.append(message)

                    # Stream to thinking dock
                    if thinking_dock:
                        summary = content[:150] + "..." if len(content) > 150 else content
                        thinking_dock.add_message(
                            director.name,
                            summary,
                            "debate"
                        )

                except Exception as e:
                    log.error(f"{director.name}: Debate round {round_num} failed: {e}", exc_info=True)

            # Check for convergence (simplified: just run all rounds for now)
            # TODO: Implement convergence detection

        return debate_messages

    def _synthesize_consensus(
        self,
        task: str,
        analyses: List[DirectorAnalysis],
        debate_messages: List[DebateMessage],
    ) -> DirectorPlan:
        """
        Synthesize consensus plan from analyses and debate.

        Args:
            task: Original user task
            analyses: Director analyses
            debate_messages: Debate transcript

        Returns:
            DirectorPlan with aggregated recommendations
        """
        log.info("Phase 3: Synthesizing consensus plan")

        # Create plan
        plan = DirectorPlan(
            title=f"Director Plan: {task}",
            summary="Aggregated recommendations from directors",
            created_by=[d.id for d in self.directors],
        )

        # Add debate transcript
        for message in debate_messages:
            plan.add_debate_message(message)

        # Synthesize plan using LLM
        try:
            from classes.ai_llm_registry import get_model
            from langchain_core.messages import SystemMessage, HumanMessage

            # Build synthesis prompt
            director_summaries = []
            for analysis in analyses:
                director_summaries.append(
                    f"**{analysis.director_name}:**\n{analysis.analysis_text[:800]}"
                )

            # Get tool registry
            from classes.ai_directors.tool_registry import ToolRegistry
            tool_catalog = ToolRegistry.get_tool_catalog()

            synthesis_prompt = f"""Based on the director analyses below, create executable action steps to improve this video.

Original Task: {task}

Director Analyses:
{chr(10).join(director_summaries)}

Create 3-7 specific steps in JSON array format. Each step must include:
- description: Clear action description
- rationale: Why this improves the video (reference vision scores if used)
- tool_name: Actual tool name from catalog
- tool_args: Specific parameters with calculated values
- agent: Which agent executes this (video/transitions/tts/music)
- confidence: How confident (0.0-1.0)

{tool_catalog}

IMPORTANT:
- Use actual tool names (add_effect, adjust_audio, etc.) not "manual_action"
- Calculate specific parameter values from analysis data
- If vision analysis shows low scores, calculate adjustments using the formulas provided
- Reference vision scores in rationale (e.g., "lighting score 0.65")

Respond with ONLY a JSON array:
[
  {{
    "description": "Apply brightness correction to Clip 2",
    "rationale": "Vision analysis shows lighting score 0.65 vs adjacent clips 0.90",
    "tool_name": "add_effect",
    "tool_args": {{"clip_id": "clip_002", "effect_type": "brightness_contrast", "brightness": 1.15, "contrast": 1.05}},
    "agent": "video",
    "confidence": 0.85
  }}
]"""

            llm = get_model(self.model_id)
            messages = [
                SystemMessage(content="You are a video editing expert synthesizing feedback from multiple directors into an actionable plan."),
                HumanMessage(content=synthesis_prompt),
            ]

            response = llm.invoke(messages)
            response_text = response.content if hasattr(response, 'content') else str(response)

            # Store synthesis as summary
            plan.summary = response_text

            # Parse response into steps
            # For now, create a simple set of steps based on common recommendations
            steps = self._parse_plan_steps(response_text, analyses)
            for step in steps:
                plan.add_step(step)

        except Exception as e:
            log.error(f"Plan synthesis failed: {e}", exc_info=True)
            # Fallback: create basic plan
            from classes.ai_directors.director_plan import PlanStep, PlanStepType
            import uuid

            step = PlanStep(
                step_id=str(uuid.uuid4()),
                type=PlanStepType.EDIT_TIMELINE,
                description=f"Review director feedback and apply improvements manually",
                agent="video",
                tool_name="manual_review",
                tool_args={},
                rationale="Plan synthesis encountered an error",
                confidence=0.5,
            )
            plan.add_step(step)

        # Calculate overall confidence
        if analyses:
            plan.confidence = sum(a.confidence for a in analyses) / len(analyses)

        return plan

    def _parse_plan_steps(self, plan_text: str, analyses: List[DirectorAnalysis]):
        """
        Parse plan text into PlanStep objects.

        Attempts to parse JSON first, falls back to text parsing if that fails.

        Args:
            plan_text: LLM-generated plan text (JSON or numbered list)
            analyses: Director analyses for context

        Returns:
            List of PlanStep objects
        """
        import json
        import re
        from classes.ai_directors.director_plan import PlanStep, PlanStepType
        import uuid

        # Try JSON parsing first
        json_match = re.search(r'\[[\s\S]*\]', plan_text)
        if json_match:
            try:
                steps_data = json.loads(json_match.group())
                steps = []

                for step_data in steps_data:
                    # Determine step type from tool_name
                    step_type = self._map_tool_to_step_type(step_data.get('tool_name', ''))

                    step = PlanStep(
                        step_id=str(uuid.uuid4()),
                        type=step_type,
                        description=step_data.get('description', 'Unnamed step'),
                        agent=step_data.get('agent', 'video'),
                        tool_name=step_data.get('tool_name', 'manual_action'),
                        tool_args=step_data.get('tool_args', {}),
                        rationale=step_data.get('rationale', ''),
                        confidence=step_data.get('confidence', 0.7),
                        dependencies=step_data.get('dependencies', []),
                    )
                    steps.append(step)

                if steps:
                    log.info(f"Successfully parsed {len(steps)} steps from JSON")
                    return steps

            except Exception as e:
                log.warning(f"JSON parsing failed: {e}, falling back to text parsing")

        # Fallback: Text parsing
        return self._parse_text_plan(plan_text)

    def _parse_text_plan(self, plan_text: str):
        """Parse numbered text plan into steps (fallback method)"""
        from classes.ai_directors.director_plan import PlanStep, PlanStepType
        import uuid

        steps = []
        lines = plan_text.split('\n')
        step_description = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line starts a new step
            if any(line.startswith(f"{i}.") or line.startswith(f"Step {i}") for i in range(1, 20)):
                if step_description:
                    steps.append(self._create_step_from_description(step_description))
                step_description = line
            else:
                if step_description:
                    step_description += " " + line

        if step_description:
            steps.append(self._create_step_from_description(step_description))

        if not steps:
            steps.append(PlanStep(
                step_id=str(uuid.uuid4()),
                type=PlanStepType.EDIT_TIMELINE,
                description="Apply director recommendations",
                agent="video",
                tool_name="manual_action",
                tool_args={},
                rationale="Based on director consensus",
                confidence=0.7,
            ))

        return steps

    def _create_step_from_description(self, description: str) -> 'PlanStep':
        """Create a PlanStep from a text description."""
        from classes.ai_directors.director_plan import PlanStep, PlanStepType
        import uuid

        # Clean up description (remove numbering)
        desc = description
        for i in range(1, 20):
            desc = desc.replace(f"{i}. ", "").replace(f"Step {i}: ", "").replace(f"Step {i}. ", "")

        # Determine step type based on keywords
        desc_lower = desc.lower()
        if any(word in desc_lower for word in ['cut', 'trim', 'split', 'clip']):
            step_type = PlanStepType.SPLIT_CLIP
        elif any(word in desc_lower for word in ['transition', 'fade', 'dissolve']):
            step_type = PlanStepType.ADD_TRANSITION
        elif any(word in desc_lower for word in ['audio', 'sound', 'music', 'volume']):
            step_type = PlanStepType.ADJUST_AUDIO
        elif any(word in desc_lower for word in ['effect', 'filter', 'color', 'grading']):
            step_type = PlanStepType.ADD_EFFECT
        elif any(word in desc_lower for word in ['reorder', 'move', 'rearrange']):
            step_type = PlanStepType.REORDER_CLIPS
        else:
            step_type = PlanStepType.EDIT_TIMELINE

        return PlanStep(
            step_id=str(uuid.uuid4()),
            type=step_type,
            description=desc[:200],  # Limit length
            agent="video",
            tool_name="manual_action",  # Will be mapped to actual tools in executor
            tool_args={},
            rationale="Based on director recommendations",
            confidence=0.7,
        )

    def _map_tool_to_step_type(self, tool_name: str) -> 'PlanStepType':
        """
        Map tool name to PlanStepType enum.

        Args:
            tool_name: Name of the tool

        Returns:
            Appropriate PlanStepType
        """
        from classes.ai_directors.director_plan import PlanStepType

        tool_name_lower = tool_name.lower()

        if 'split' in tool_name_lower or 'cut' in tool_name_lower:
            return PlanStepType.SPLIT_CLIP
        elif 'transition' in tool_name_lower:
            return PlanStepType.ADD_TRANSITION
        elif 'audio' in tool_name_lower or 'volume' in tool_name_lower:
            return PlanStepType.ADJUST_AUDIO
        elif 'effect' in tool_name_lower or 'filter' in tool_name_lower:
            return PlanStepType.ADD_EFFECT
        elif 'music' in tool_name_lower or 'generate_music' in tool_name_lower:
            return PlanStepType.ADD_MUSIC
        elif 'tts' in tool_name_lower or 'voice' in tool_name_lower or 'generate_tts' in tool_name_lower:
            return PlanStepType.ADD_VOICE
        elif 'remove' in tool_name_lower or 'delete' in tool_name_lower:
            return PlanStepType.REMOVE_CLIP
        elif 'reorder' in tool_name_lower or 'move' in tool_name_lower:
            return PlanStepType.REORDER_CLIPS
        else:
            return PlanStepType.EDIT_TIMELINE

    def _apply_voting_resolutions(
        self,
        plan: DirectorPlan,
        voting_results: Dict,
        resolutions: Dict,
    ) -> DirectorPlan:
        """
        Apply voting results to the plan.

        Updates steps based on director votes:
        - Approved steps remain unchanged
        - Conditionally approved steps get modified
        - Rejected steps are marked with low confidence

        Args:
            plan: Original DirectorPlan
            voting_results: Vote data from DirectorVotingPhase
            resolutions: Consensus data from resolve_votes()

        Returns:
            Updated DirectorPlan
        """
        filtered_steps = []

        for step in plan.steps:
            resolution = resolutions.get(step.step_id)

            if not resolution:
                # No resolution (shouldn't happen, but handle gracefully)
                filtered_steps.append(step)
                continue

            if not resolution['approved']:
                # Step rejected - add note and mark low confidence
                step.director_notes['voting'] = f"Rejected by directors: {resolution['consensus']}"
                step.director_notes['vote_breakdown'] = str(resolution['votes'])
                step.confidence = 0.3  # Mark as low confidence
                filtered_steps.append(step)
                log.info(f"Step rejected: {step.description[:50]}")
                continue

            # Apply modifications if conditional approval
            if resolution['modifications']:
                tool_args_mods = resolution['modifications'].get('tool_args', {})
                if tool_args_mods:
                    step.tool_args.update(tool_args_mods)
                    step.director_notes['voting'] = f"Modified: {resolution['consensus']}"
                    step.director_notes['modifications'] = str(tool_args_mods)
                    log.info(f"Step modified: {step.description[:50]} - {tool_args_mods}")
            else:
                step.director_notes['voting'] = resolution['consensus']

            step.director_notes['vote_breakdown'] = str(resolution['votes'])
            filtered_steps.append(step)

        # Store voting metadata in plan
        plan.steps = filtered_steps
        if not hasattr(plan, 'metadata') or plan.metadata is None:
            plan.metadata = {}
        plan.metadata['voting_results'] = voting_results
        plan.metadata['resolutions'] = resolutions

        return plan

    def _get_thinking_dock(self):
        """
        Get the thinking dock widget if available.

        Returns:
            ThinkingDockWidget or None
        """
        try:
            from classes.app import get_app
            app = get_app()
            if hasattr(app, 'window') and hasattr(app.window, 'thinking_dock'):
                return app.window.thinking_dock
        except Exception as e:
            log.debug(f"Thinking dock not available: {e}")
        return None


def run_directors(model_id: str, task: str, director_ids: List[str], main_thread_runner) -> str:
    """
    Entry point for running directors from root agent.

    Args:
        model_id: LLM model to use
        task: User's task
        director_ids: List of director IDs to use
        main_thread_runner: MainThreadToolRunner

    Returns:
        Status message
    """
    try:
        from classes.ai_directors.director_loader import get_director_loader

        # Load directors
        loader = get_director_loader()
        directors = []
        for director_id in director_ids:
            director = loader.load_director(director_id)
            if director:
                directors.append(director)
            else:
                log.warning(f"Failed to load director: {director_id}")

        if not directors:
            return "Error: No directors loaded"

        # Run orchestrator
        orchestrator = DirectorOrchestrator(directors)
        plan = orchestrator.run_directors(model_id, task, main_thread_runner, {})

        # Display plan in UI
        try:
            from classes.app import get_app
            app = get_app()
            if hasattr(app, 'window') and hasattr(app.window, 'dockPlanReview'):
                # Show plan in review UI
                app.window.dockPlanReview.show_plan(plan)
                return f"Directors analyzed the project and created a plan with {len(plan.steps)} steps. Review the plan in the Plan Review panel."
            else:
                return f"Directors analyzed the project. Generated plan with {len(plan.steps)} steps. Plan Review UI not available."
        except Exception as e:
            log.error(f"Failed to display plan in UI: {e}", exc_info=True)
            return f"Directors analyzed the project. Generated plan with {len(plan.steps)} steps, but failed to display UI."

    except Exception as e:
        log.error(f"run_directors failed: {e}", exc_info=True)
        return f"Error: {e}"
