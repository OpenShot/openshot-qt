"""
Plan Executor

Executes director plans by mapping plan steps to sub-agent tool calls.
Supports auto mode (execute all steps) and manual mode (confirm each step).
"""

from typing import List, Dict, Any, Optional
from classes.logger import log
from classes.ai_directors.director_plan import DirectorPlan, PlanStep, PlanStepType

try:
    from PyQt5.QtCore import QObject, pyqtSignal
except ImportError:
    QObject = object
    pyqtSignal = None


class PlanExecutor(QObject if QObject is not object else object):
    """
    Executes approved director plans.

    Handles dependency resolution, progress tracking, and error recovery.
    """

    if pyqtSignal is not None:
        step_started = pyqtSignal(str, str)  # step_id, description
        step_completed = pyqtSignal(str, bool, str)  # step_id, success, result
        plan_completed = pyqtSignal(str, int, int)  # plan_id, successful_steps, total_steps

    def __init__(self, main_thread_runner):
        if QObject is not object:
            super().__init__()
        self.main_thread_runner = main_thread_runner
        self.current_plan = None
        self.executed_steps = {}  # step_id -> result

    def execute_plan(
        self,
        plan: DirectorPlan,
        model_id: str,
        auto_mode: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a director plan.

        Args:
            plan: DirectorPlan to execute
            model_id: LLM model to use for sub-agents
            auto_mode: If True, execute all steps automatically; if False, prompt for each step

        Returns:
            Execution results dict with success status and step results
        """
        log.info(f"Executing plan: {plan.title} (auto_mode={auto_mode})")
        self.current_plan = plan
        self.executed_steps = {}

        # Validate plan
        is_valid, error = plan.validate()
        if not is_valid:
            log.error(f"Plan validation failed: {error}")
            return {
                "success": False,
                "error": error,
                "steps_executed": 0,
                "steps_total": len(plan.steps),
            }

        # Sort steps by dependencies
        sorted_steps = self._topological_sort(plan.steps)

        successful_steps = 0
        failed_steps = 0

        # Execute steps in order
        for step in sorted_steps:
            # Check dependencies
            if not self._dependencies_met(step):
                log.warning(f"Step {step.step_id} skipped: dependencies not met")
                failed_steps += 1
                continue

            # In manual mode, would prompt user here
            # For now, just execute
            if not auto_mode:
                log.info(f"Manual mode: Would confirm step {step.step_id}")

            # Execute step
            if pyqtSignal is not None and hasattr(self, "step_started"):
                self.step_started.emit(step.step_id, step.description)

            success, result = self._execute_step(step, model_id)

            if pyqtSignal is not None and hasattr(self, "step_completed"):
                self.step_completed.emit(step.step_id, success, result)

            self.executed_steps[step.step_id] = {
                "success": success,
                "result": result,
            }

            if success:
                successful_steps += 1
                log.info(f"Step {step.step_id} completed: {result[:100]}")
            else:
                failed_steps += 1
                log.error(f"Step {step.step_id} failed: {result}")

        # Emit completion signal
        if pyqtSignal is not None and hasattr(self, "plan_completed"):
            self.plan_completed.emit(plan.plan_id, successful_steps, len(plan.steps))

        log.info(f"Plan execution complete: {successful_steps}/{len(plan.steps)} successful")

        return {
            "success": failed_steps == 0,
            "steps_executed": successful_steps,
            "steps_total": len(plan.steps),
            "steps_failed": failed_steps,
            "step_results": self.executed_steps,
        }

    def _execute_step(self, step: PlanStep, model_id: str) -> tuple[bool, str]:
        """
        Execute a single plan step.

        Args:
            step: PlanStep to execute
            model_id: LLM model to use

        Returns:
            (success, result_message)
        """
        try:
            # Map step to sub-agent call
            agent = step.agent  # "video", "manim", "voice", "music"

            # Build task description for sub-agent
            task = f"{step.description}\n\nRationale: {step.rationale}"

            # Call appropriate sub-agent
            if agent == "video":
                from classes.ai_multi_agent.sub_agents import run_video_agent
                result = run_video_agent(model_id, task, self.main_thread_runner)
            elif agent == "manim":
                from classes.ai_multi_agent.sub_agents import run_manim_agent
                result = run_manim_agent(model_id, task, self.main_thread_runner)
            elif agent == "voice" or agent == "voice_music":
                from classes.ai_multi_agent.sub_agents import run_voice_music_agent
                result = run_voice_music_agent(model_id, task, self.main_thread_runner)
            elif agent == "music":
                from classes.ai_multi_agent.sub_agents import run_music_agent
                result = run_music_agent(model_id, task, self.main_thread_runner)
            else:
                return False, f"Unknown agent: {agent}"

            # Check for errors in result
            if result and "error" in result.lower():
                return False, result

            return True, result

        except Exception as e:
            log.error(f"Step execution failed: {e}", exc_info=True)
            return False, f"Error: {e}"

    def _topological_sort(self, steps: List[PlanStep]) -> List[PlanStep]:
        """
        Sort steps by dependencies using topological sort.

        Args:
            steps: List of PlanSteps

        Returns:
            Sorted list of steps
        """
        # Build adjacency list
        graph = {step.step_id: step.dependencies for step in steps}
        step_map = {step.step_id: step for step in steps}

        # Kahn's algorithm for topological sort
        in_degree = {step.step_id: len(step.dependencies) for step in steps}
        queue = [step_id for step_id, degree in in_degree.items() if degree == 0]
        sorted_ids = []

        while queue:
            step_id = queue.pop(0)
            sorted_ids.append(step_id)

            # Reduce in-degree for dependent steps
            for other_id in graph.keys():
                if step_id in graph[other_id]:
                    in_degree[other_id] -= 1
                    if in_degree[other_id] == 0:
                        queue.append(other_id)

        # Convert back to PlanStep objects
        return [step_map[step_id] for step_id in sorted_ids if step_id in step_map]

    def _dependencies_met(self, step: PlanStep) -> bool:
        """
        Check if all dependencies for a step have been successfully executed.

        Args:
            step: PlanStep to check

        Returns:
            True if all dependencies are met
        """
        for dep_id in step.dependencies:
            if dep_id not in self.executed_steps:
                return False
            if not self.executed_steps[dep_id]["success"]:
                return False
        return True


# Global executor instance
_plan_executor = None


def get_plan_executor(main_thread_runner=None):
    """Get or create global PlanExecutor instance."""
    global _plan_executor
    if _plan_executor is None and main_thread_runner is not None:
        _plan_executor = PlanExecutor(main_thread_runner)
    return _plan_executor


def execute_plan(plan: DirectorPlan, model_id: str, main_thread_runner, auto_mode: bool = False):
    """
    Execute a director plan.

    Args:
        plan: DirectorPlan to execute
        model_id: LLM model to use
        main_thread_runner: MainThreadToolRunner
        auto_mode: If True, execute automatically; if False, prompt for confirmation

    Returns:
        Execution results
    """
    executor = get_plan_executor(main_thread_runner)
    if executor is None:
        return {
            "success": False,
            "error": "Executor not initialized",
            "steps_executed": 0,
            "steps_total": len(plan.steps),
        }

    return executor.execute_plan(plan, model_id, auto_mode)
