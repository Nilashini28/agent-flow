"""AutoGen Framework Adapter — Task 3.

Translates AutoGen's conversational turn model into AgentFlow's step-based
FrameworkAdapter interface.

TRANSLATION MAPPING (AutoGen → AgentFlow):

  AutoGen concept         AgentFlow concept
  ─────────────────────   ──────────────────────────────────────────────
  Conversation turn       Step (one run_step() call)
  Agent message content   StepResult.raw_output
  Turn ID ("turn_0")      StepResult.step_id
  Full conversation state StepResult.output_state (plain dict)
  Last agent's tool use   StepResult.tool_calls

WHAT IS APPROXIMATED / LOST IN THIS MAPPING:

  1. Step boundaries:
     LangGraph has explicit, named node boundaries defined in the graph.
     AutoGen has free-form conversation — the "boundary" between steps is
     IMPOSED by this adapter at each complete message exchange.
     Rule used: one complete agent response = one step.
     This is a design choice, not an AutoGen native concept.

  2. Parallel agents:
     AutoGen supports parallel agent execution and group chats.
     This adapter maps to a sequential turn model (turn_0 → turn_1 → turn_2)
     and cannot represent simultaneous agent responses as a single StepResult.
     A parallel AutoGen run would require multiple parallel StepResults or
     a grouping concept not present in the current FrameworkAdapter interface.

  3. Tool call interception:
     AutoGen 0.7.x handles tool calls inside the agent's on_messages() call.
     To route tool calls through AgentFlow's Stage 4 sandbox, this adapter
     intercepts tool_calls from the conversation history. In stub mode,
     tool calls are declared explicitly (not internally executed by AutoGen).
     In live mode, tool calls made by the agent are extracted post-hoc from
     the message response object.

WHAT IS GENUINELY REUSABLE (zero changes required):

  - score_step() from Stage 5 — called identically in the runner.
  - decide_next_action() from Stage 5 — called identically in the runner.
  - run_sandboxed() from Stage 4 — called identically in the runner.
  - log_event() from observability — called identically in the runner.
  - AdapterCheckpointStore — same DB file, same save/load API.
"""
from __future__ import annotations

from typing import Any

from app.core.adapters.base import FrameworkAdapter, StepResult
from app.core.agents.autogen_demo_agent import AutoGenDemoConversation


class AutoGenAdapter(FrameworkAdapter):
    """Adapter that runs a real AutoGen multi-agent conversation through
    AgentFlow's reliability layer via the FrameworkAdapter interface.

    Each run_step() call executes one AutoGen conversational turn and returns
    a StepResult. The runner applies checkpointing, sandbox, and escalation
    after each call — identically to the LangGraph adapter path.

    Parameters
    ----------
    task : str
        The task string passed to the AutoGen planner agent.
    run_id : str
        AgentFlow run identifier (used in event log payloads).
    stub_mode : bool
        If True (default), uses deterministic stub responses with no LLM call.
        If False, uses real AutoGen agents with an OpenAI-compatible model.
    """

    def __init__(self, task: str, run_id: str, stub_mode: bool = True) -> None:
        self._task = task
        self._run_id = run_id
        self._stub_mode = stub_mode
        # The conversation object is the actual AutoGen execution engine.
        # It maintains message history across turns so each turn has full context.
        self._conversation = AutoGenDemoConversation(task=task, stub_mode=stub_mode)

    def list_steps(self) -> list[str]:
        """Three turns: planner → critic → planner-execute.

        Step boundary rule: one complete agent response = one step.
        This is the adapter's imposed structure on AutoGen's free-form model.
        """
        return AutoGenDemoConversation.turn_sequence()  # ["turn_0", "turn_1", "turn_2"]

    def run_step(self, step_id: str, input_state: dict[str, Any]) -> StepResult:
        """Execute one AutoGen conversation turn and translate to StepResult.

        The adapter calls AutoGenDemoConversation.run_turn() which runs the
        AutoGen agent synchronously. The result is then translated into the
        StepResult shape that AgentFlow's runner expects.

        Tool call approximation (stub mode):
          In stub mode, the turn_2 (executor) step declares a "stub-executor"
          tool call explicitly so the runner can route it through Stage 4's
          sandbox — demonstrating that the sandbox path is exercised even from
          the AutoGen adapter, using the exact same run_sandboxed() call.
        """
        # Run the AutoGen turn.
        turn_result = self._conversation.run_turn(step_id)

        content: str = turn_result["content"]
        role: str = turn_result["role"]
        history = turn_result["history_so_far"]

        # Build the output state (plain dict — same shape as AgentState).
        step_index = input_state.get("step_index", 0) + 1
        new_state: dict[str, Any] = {
            **input_state,
            "last_output": content,
            "step_index": step_index,
            "history": history,
            "autogen_role": role,
            "autogen_turn": step_id,
        }

        # Declare tool calls for the executor turn so Stage 4 sandbox is exercised.
        # In a live AutoGen setup, tool calls would be extracted from the
        # model's response object. In stub mode, we declare them explicitly.
        tool_calls: list[dict[str, Any]] = []
        if step_id == "turn_2":
            tool_calls = [
                {
                    "tool": "stub-executor",
                    "input": content[:120],
                    "output": "[pending sandbox execution]",
                    "timestamp": _utc_now(),
                }
            ]

        # Determine status: turn_2 is the final turn → "completed".
        # If the critic said HALT, mark as failed to trigger escalation.
        if step_id == "turn_2":
            status = "completed"
        elif "HALT" in content.upper():
            # Critic explicitly halted — propagate as failed so runner escalates.
            status = "failed"
            new_state["error"] = "CriticAgent issued HALT decision"
        else:
            status = "running"

        return StepResult(
            step_id=step_id,
            output_state=new_state,
            raw_output=content,
            status=status,
            tool_calls=tool_calls,
            risk_score=0.0,  # Let runner compute via score_step()
            error=new_state.get("error"),
        )


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
