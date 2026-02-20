"""
Plan graph builder: tree of what the AI is doing during an edit run.
Root -> branches (Script, Imaging, Manim, Music) -> steps (tool calls).
Built by instrumenting the root agent (start_branch/end_branch) and main-thread tools (add_step).
Thread-safe: worker thread sets branch, main thread adds steps.
"""

import json
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from classes.logger import log

# Branch display names for UI
BRANCH_LABELS = {
    "video": "Imaging",
    "manim": "Manim",
    "voice_music": "Script",
    "music": "Music",
}


def _new_id() -> str:
    return str(uuid.uuid4())[:8]


def _make_node(
    node_type: str,
    label: str,
    parent_id: Optional[str] = None,
    description: str = "",
    tool_name: str = "",
    args: Optional[Dict] = None,
    result: str = "",
) -> Dict[str, Any]:
    return {
        "id": _new_id(),
        "type": node_type,
        "label": label,
        "parent_id": parent_id,
        "description": description or "",
        "tool_name": tool_name or "",
        "args": args if args is not None else {},
        "result": result or "",
        "children": [],
        "created_at": time.time(),
    }


class PlanBuilder:
    """
    Builds a plan graph during one agent run.
    - Worker thread: start_plan, start_branch, end_branch, end_plan.
    - Main thread: add_step (uses current_branch set by worker).
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._root: Optional[Dict[str, Any]] = None
        self._current_branch_id: Optional[str] = None
        self._nodes_by_id: Dict[str, Dict[str, Any]] = {}
        self._prompt = ""

    def start_plan(self, user_prompt: str) -> None:
        """Start a new plan for this edit run. Call from worker before run_agent."""
        with self._lock:
            self._prompt = user_prompt or ""
            self._root = _make_node("root", "Edit plan", parent_id=None, description=user_prompt)
            self._root["prompt"] = self._prompt
            self._nodes_by_id = {self._root["id"]: self._root}
            self._current_branch_id = None
        log.debug("PlanBuilder: start_plan")

    def start_branch(self, branch_key: str, task_description: str = "") -> None:
        """
        Start a branch (e.g. video, manim, voice_music, music). Call from worker when root invokes that agent.
        """
        with self._lock:
            if self._root is None:
                return
            label = BRANCH_LABELS.get(branch_key, branch_key.replace("_", " ").title())
            node = _make_node(
                "branch",
                label,
                parent_id=self._root["id"],
                description=task_description or "",
            )
            node["branch_key"] = branch_key
            self._nodes_by_id[node["id"]] = node
            self._root["children"].append(node)
            self._current_branch_id = node["id"]
        log.debug("PlanBuilder: start_branch %s", branch_key)

    def end_branch(self) -> None:
        """End the current branch. Call from worker when sub-agent returns."""
        with self._lock:
            self._current_branch_id = None
        log.debug("PlanBuilder: end_branch")

    def add_step(self, tool_name: str, args_json: str, result: str) -> None:
        """
        Add a step (tool call) under the current branch. Call from main thread in run_tool.
        If no branch is set (e.g. single-agent path), creates an implicit "General" branch under root.
        """
        with self._lock:
            if self._root is None:
                return
            branch_id = self._current_branch_id
            if branch_id is None:
                # Single-agent path: create implicit "General" branch for this run
                general = _make_node("branch", "General", parent_id=self._root["id"], description="")
                general["branch_key"] = "general"
                self._nodes_by_id[general["id"]] = general
                self._root["children"].append(general)
                branch_id = general["id"]
            try:
                args = json.loads(args_json) if args_json else {}
            except Exception:
                args = {}
            result_preview = (result or "")[:500]
            if len(result or "") > 500:
                result_preview += "..."
            label = _friendly_tool_name(tool_name)
            node = _make_node(
                "step",
                label,
                parent_id=branch_id,
                tool_name=tool_name,
                args=args,
                result=result_preview,
            )
            self._nodes_by_id[node["id"]] = node
            parent = self._nodes_by_id.get(branch_id)
            if parent is not None:
                parent["children"].append(node)
        log.debug("PlanBuilder: add_step %s", tool_name)

    def end_plan(self) -> None:
        """Finalize the plan. Call from worker when run_agent returns."""
        with self._lock:
            self._current_branch_id = None
        log.debug("PlanBuilder: end_plan")

    def get_current_branch(self) -> Optional[str]:
        """For internal use: return current branch id (under lock)."""
        with self._lock:
            return self._current_branch_id

    def get_plan_json(self) -> Optional[Dict[str, Any]]:
        """Return the current plan as a JSON-serializable dict, or None if no plan."""
        with self._lock:
            if self._root is None:
                return None
            return _copy_node(self._root)

    def get_plan_json_string(self) -> str:
        """Return the current plan as a JSON string for the UI."""
        plan = self.get_plan_json()
        if plan is None:
            return "null"
        return json.dumps(plan, default=str)

    def clear(self) -> None:
        """Clear the plan (e.g. when starting a new chat)."""
        with self._lock:
            self._root = None
            self._nodes_by_id = {}
            self._current_branch_id = None
            self._prompt = ""

    def get_breakdown(self) -> Dict[str, List[Dict]]:
        """
        Return a breakdown by category: transitions, captioning, script, etc.
        Derived from tool names and branch labels.
        """
        with self._lock:
            if self._root is None:
                return {}
        plan = self.get_plan_json()
        if not plan:
            return {}
        breakdown = {"imaging": [], "script": [], "manim": [], "music": []}
        for branch in plan.get("children", []):
            key = branch.get("branch_key", branch.get("label", "").lower())
            key = key.replace(" ", "_")
            if key not in breakdown:
                breakdown[key] = []
            for step in branch.get("children", []):
                breakdown[key].append({
                    "label": step.get("label", ""),
                    "tool_name": step.get("tool_name", ""),
                    "result_preview": (step.get("result", "") or "")[:200],
                })
        return {k: v for k, v in breakdown.items() if v}


def _copy_node(n: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in n.items() if k != "children"}
    out["children"] = [_copy_node(c) for c in n.get("children", [])]
    return out


def _friendly_tool_name(name: str) -> str:
    """Convert tool name to a short label for the graph."""
    if not name:
        return "Tool"
    if name.endswith("_tool"):
        name = name[:-5]
    return name.replace("_", " ").title()


# Singleton
_plan_builder: Optional[PlanBuilder] = None
_plan_builder_lock = threading.Lock()


def get_plan_builder() -> PlanBuilder:
    global _plan_builder
    with _plan_builder_lock:
        if _plan_builder is None:
            _plan_builder = PlanBuilder()
        return _plan_builder
