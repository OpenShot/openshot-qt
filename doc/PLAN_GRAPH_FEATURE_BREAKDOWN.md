# Plan Graph Feature – Idea Breakdown

This doc breaks down the **plan graph** feature for the AI video editing tool: no integration yet, just structure and mapping to the codebase.

---

## 1. What You Want (in your words)

- **When:** User prompts to edit video → the tool does the edit **and** shows a **plan graph**.
- **What the graph is:** A hierarchy of what the tool is doing:
  - **Root node** = the user’s edit request (or “this edit”).
  - **Branches** = high-level areas, e.g. **Script**, **Imaging** (and any other relevant branches).
  - Under each branch, sub-branches for the actual steps (e.g. under Script: generate script, add captions; under Imaging: transitions, effects, etc.).
- **Where it appears:** In both **agent mode** (chat) and **appearance mode** (visual graph).
- **Per node:** Each section shows **description** and/or **code** of what’s being done.
- **Interaction:** User can **click a section** and **edit / re-prompt** that specific part (like in agent mode).
- **Persistence:** **Database** (or similar) to store, per user prompt / edit session:
  - What was done.
  - Breakdown: transitions, captioning, script, etc.
- **Tech:** Start with a **Python** layer; use **HTML/CSS** and optionally **React** for the graph UI.

---

## 2. Mapping to the Current Codebase

### 2.1 How editing works today

- **Entry:** User types in the **AI chat** → `AIChat.send_message()` → `run_agent()`.
- **Root agent** (`root_agent.run_root_agent`):
  - Has 4 tools: `invoke_video_agent`, `invoke_manim_agent`, `invoke_voice_music_agent`, `invoke_music_agent`.
  - Routes the user message to one (or over time, several) **sub-agents**.
- **Sub-agents** (in `sub_agents.py`):
  - **Video:** timeline, clips, export, video generation, split, etc. (OpenShot tools).
  - **Manim:** educational/math animation.
  - **Voice/Music:** TTS, tagging, storylines.
  - **Music:** Suno background music.
- **Execution:** Each sub-agent runs `run_agent_with_tools()` with its own tools. Tools run on the **main thread** via `MainThreadToolRunner.run_tool()`.
- **Signals:** `tool_started(name, args_json)` and `tool_completed(name, result)` are already emitted and shown in the **chat** as a flat list of “activity steps” (`addActivityStep` / `completeLastActivityStep` in `chat_ui`).

So today you have:

- A **tree in logic**: Root → (video | manim | voice_music | music) → (many tools).
- A **flat list in UI**: only the leaf tool calls (name + args) are shown in the chat; the “root → sub-agent” level is not visualized.

### 2.2 “Agent mode” vs “Appearance mode”

In the codebase there isn’t a formal split named “agent mode” vs “appearance mode.” For this feature it’s useful to define:

- **Agent mode:** The current **chat + tool steps** view (conversation + linear list of tool calls). The plan graph here would be the **same logical plan** shown in a compact form (e.g. inline or in a panel next to chat).
- **Appearance mode:** A **dedicated graph view** (hierarchy of nodes, same data, different layout). Could be a second tab/panel or a separate dock.

So: **one plan graph data structure**, **two presentations** (chat context + graph view).

---

## 3. Breaking the Idea into Pieces

### 3.1 Data: the “plan graph”

You need a **tree (or DAG)** that represents one “edit run”:

- **Root:** e.g. “Edit: &lt;user prompt&gt;” or “Session / Edit #N.”
- **Level 1 (branches):** High-level categories. Today these map naturally to:
  - **Script** (voice, TTS, captions, storylines) → from `invoke_voice_music_agent` (+ possibly video tools that touch captions).
  - **Imaging** (timeline, clips, effects, transitions, video generation) → from `invoke_video_agent`.
  - **Manim** (educational animation) → from `invoke_manim_agent`.
  - **Music** (Suno, background music) → from `invoke_music_agent`.
- **Level 2+:** Under each branch, the **actual tool calls** (and optionally grouped):
  - e.g. under Imaging: “Add transition,” “Generate video,” “Export,” “Add clip,” etc.
  - Each node can store: **label**, **description**, **tool name**, **args**, **result** (or summary), and optionally **code** if the tool is script/code-like.

So the **minimal node** could look like:

- `id`, `parent_id` (or `children`)
- `type`: `"root" | "branch" | "step"`
- `label`: short title
- `description`: human-readable what’s being done
- `tool_name`, `args`, `result`: for leaf “step” nodes
- Optional: `code` or `code_ref` for script/code display

You can start with a **Python-only** representation (e.g. dataclasses or a small module that builds this tree during the run).

### 3.2 Where does the graph data come from?

Two main options:

**Option A – Instrument the current run (recommended to start)**  
- While the root agent and sub-agents run, **record**:
  - When the root calls `invoke_X_agent(task)` → create a **branch** node “X” with description from `task`.
  - When a sub-agent calls a tool → create a **step** node under that branch (tool name, args, result).
- So the graph is **built as a side effect** of the existing flow; no change to how the model “thinks,” only we add a **plan builder** that listens to tool invocations and builds the tree.
- **Pros:** No new “plan” phase; works with current root + sub-agents.  
- **Cons:** Hierarchy is “by routing” (which agent + which tool), not by a separate “plan” from the LLM.

**Option B – Plan-first, then execute**  
- First call: “Given this user prompt, output a structured plan (script, imaging, music, …).”
- Then execute that plan (or map it to agents/tools) and attach tool results to plan nodes.
- **Pros:** Plan can be more semantic (e.g. “add intro caption,” “smooth transition at 0:30”).  
- **Cons:** Two LLM rounds; need to align plan steps to actual tool calls.

**Practical path:** Start with **Option A** (instrument current run). Add a **plan builder** that:
- Subscribes to or is called from the same place that currently emits `tool_started` / `tool_completed`.
- Knows “current branch” (which invoke_* is running) so it can attach step nodes to the right branch.

Later you can add an optional “plan-first” phase and merge that with the instrumented tree.

### 3.3 Database (persistence)

- **What to store:** Per “edit” or “session”:
  - User prompt (and maybe session id, project id, timestamp).
  - Serialized **plan graph** (nodes + edges or parent refs).
  - Optional: breakdown fields (e.g. “transitions: […], captioning: […], script: […]”) for quick filters/display.
- **Where:** Could be SQLite (e.g. a table `edit_plans` with `id`, `prompt`, `graph_json`, `breakdown_json`, `created_at`, `project_id`). No need for a heavy DB at first.
- **When:** Write after an edit run completes (or on each tool_completed if you want incremental saves).

### 3.4 “Breakdown” (transitions, captioning, script, …)

- This can be a **view** over the same graph:
  - Walk the tree and tag nodes by **type** (e.g. transition, captioning, script, music, effect, export).
  - Either tag during instrumentation (when you record a tool, you know its type) or infer from tool name/args.
- Store as a **summary** in the DB (e.g. `breakdown: { "transitions": [...], "captioning": [...], "script": [...] }`) for quick display and filters.

### 3.5 UI: agent mode vs appearance mode

- **Agent mode:**  
  - Keep current chat + activity steps.  
  - **Add:** A compact “plan” summary (e.g. same graph data rendered as a small tree or list next to the message that triggered the edit). Clicking a node could open a “re-prompt for this part” input (same as agent mode, but scoped to that node).

- **Appearance mode:**  
  - A **graph view** (tree or DAG): nodes = root, branches, steps; edges = parent → child.  
  - Each node: label, description, optional code/result.  
  - **Click node** → same “edit this part” flow: e.g. open a prompt input that re-runs only that branch/step or sends a follow-up message with context (“change this: …”).

- **Shared:** One source of truth for the plan graph (in-memory for current run, then DB for history). Both modes read from that.

### 3.6 “Click and edit / re-prompt for that part”

- **Meaning:** User clicks a graph node (e.g. “Add transition”) and can type a new prompt for **that** part only.
- **Implementation options:**
  - **Simple:** Pre-fill the chat input with context like “About [Add transition]: ” and send as a normal follow-up; the root agent may route to the same sub-agent again. No need to “re-run only that node” in v1.
  - **Richer:** Pass “scope” with the message (e.g. `scope: { "node_id": "...", "branch": "imaging" }`) so the agent (or a dedicated handler) focuses on that part; optionally re-run only that sub-agent with the new prompt.

You can start with the simple version and add scope later.

---

## 4. Tech: Python first, then HTML/CSS, then React (optional)

- **Python (first):**
  - A small module (e.g. `plan_graph.py` or under `classes/`):
    - **Plan builder:** Receives events (root invoked X; tool Y started/completed) and builds the tree (in-memory).
    - **Data structures:** Node (id, parent, type, label, description, tool_name, args, result, …).
    - **Serialization:** To dict/JSON for the frontend and for DB.
  - Optionally: **DB layer** (SQLite) to save/load plans by session or prompt.

- **HTML/CSS (+ JS):**
  - A **minimal graph view** can be:
    - A simple nested list (ul/li) or a set of divs with lines (CSS borders or SVG) to show hierarchy.
    - Load plan JSON from Python (e.g. via Qt WebChannel, like the existing chat_ui).
  - No React needed for a first version.

- **React (optional) later:**
  - Use React (e.g. in `chat_ui` or a new `plan_graph_ui`) for a richer graph: drag, zoom, expand/collapse, better layout (e.g. dagre, elkjs). The Python side still only provides the JSON.

---

## 5. Suggested order of work (when you do integrate)

1. **Python – plan builder**
   - Define node types and a simple tree structure.
   - Hook into the agent run (e.g. where `tool_started`/`tool_completed` are emitted, plus root’s invoke_* calls) and build the graph during one edit run.
   - Expose the current run’s graph (and optionally last N from memory) to the UI.

2. **Python – persistence**
   - SQLite (or similar): save plan (and breakdown) per prompt/session; load on demand.

3. **UI – appearance mode**
   - New panel or tab that receives plan JSON (e.g. via QWebChannel) and renders a simple graph (HTML/CSS or minimal JS). Click node → show description/code and “Edit this” prompt input.

4. **UI – agent mode**
   - In chat, show the same plan (compact: e.g. tree or list) next to the assistant message for the edit; same “click to edit” behavior.

5. **Refinements**
   - Breakdown view (transitions, captioning, script, …).
   - Optional plan-first phase.
   - React + proper graph layout if you need it.

---

## 6. Summary table

| Concept              | Meaning / implementation |
|----------------------|---------------------------|
| **Plan graph**       | Tree: root → branches (Script, Imaging, Manim, Music) → steps (tool calls). Built by instrumenting current agent run. |
| **Agent mode**       | Chat view + same plan shown in compact form; click node → re-prompt that part. |
| **Appearance mode**  | Dedicated graph view (hierarchy); same data; click node → edit/re-prompt. |
| **Per-node content** | Label, description, tool name/args/result, optional code. |
| **Database**         | Store per prompt/session: prompt, graph JSON, breakdown (transitions, captioning, script, …). |
| **Tech**             | Python (plan builder + optional DB) → HTML/CSS/JS for graph → React later if needed. |

This breakdown should give you a clear map from “idea” to “data + where it comes from + how it’s shown,” so you can implement step by step without integrating everything at once.

---

## Implementation status (as implemented)

- **Plan graph package** (`src/plan_graph/`): All plan-graph code lives here. Builder (`builder.py`), persistence (`storage.py`), dock (`dock.py`), and UI (`ui/index.html`). Thread-safe `get_plan_builder()` singleton.
- **Hooks**: Root agent (`root_agent.py`) calls `start_branch`/`end_branch` around each `invoke_*`; `MainThreadToolRunner.run_tool` calls `add_step` and emits `plan_updated`.
- **Persistence**: SQLite at `USER_PATH/plan_history.db`; `save_plan()` after each run; `list_plans()`, `load_plan(id)`.
- **UI**: **Plan Graph** dock. Show via **View → Docks → Plan Graph**. Updates live as tools run and with final plan when the response is ready. Clearing chat clears the plan.
- **Next steps** (optional): Click-to-edit (re-prompt for a node), load/save plan history in UI, breakdown view (transitions, captioning, script).
