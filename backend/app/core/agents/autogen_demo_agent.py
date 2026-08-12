"""AutoGen multi-agent demo — Task 3.

Real, functional AutoGen 0.7.x multi-agent conversation with two agents:
  - PlannerAgent : Receives the task, produces a structured plan/proposal.
  - CriticAgent  : Reviews the plan, identifies risks, approves or flags issues.

This mirrors AgentFlow's research→draft→verify→act conceptually, but uses
AutoGen's actual conversational pattern (agents exchanging messages) rather
than LangGraph's explicit node graph.

STUB vs LIVE mode:
  Stub mode (default, AUTOGEN_STUB_MODE=true or stub_mode=True):
    Agents use a custom reply function that produces deterministic, structured
    responses without calling any LLM API. Safe for tests and CI. Zero cost.
  Live mode (AUTOGEN_STUB_MODE=false):
    Agents use the model_client passed in (e.g. OpenAIChatCompletionClient
    with a real API key from ANTHROPIC_API_KEY or OPENAI_API_KEY env var).

The demo agent is designed to be run synchronously from the AutoGenAdapter
via asyncio.run() so it integrates cleanly with AgentFlow's synchronous
runner without requiring the entire stack to be async.
"""
from __future__ import annotations

import asyncio
import os
import re
import textwrap
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Stub LLM response generator ───────────────────────────────────────────────

def _stub_planner_response(task: str, context: str = "") -> str:
    """Deterministic planner response — mirrors the stub LLM in nodes.py."""
    words = re.findall(r"[a-zA-Z]{3,}", task.lower())
    kw = list(dict.fromkeys(words))[:5]
    return (
        f"[PLANNER] Task analysis for: '{task[:60]}'\n"
        f"Keywords: {', '.join(kw)}\n"
        f"Proposed plan:\n"
        f"  Step 1: Research and gather data on {kw[0] if kw else 'primary goal'}\n"
        f"  Step 2: Draft deliverable covering {', '.join(kw[1:3]) if len(kw) > 1 else 'objectives'}\n"
        f"  Step 3: Validate outputs and finalize\n"
        f"Confidence: 0.82 | timestamp: {_utc_now()}"
    )


def _stub_critic_response(plan: str) -> str:
    """Deterministic critic response — risk signals are deterministic from plan."""
    has_risk = any(w in plan.lower() for w in ["delete", "drop", "rm", "shutdown", "critical"])
    risk_note = "Risk: possible destructive action detected." if has_risk else "Risk: low — plan appears safe."
    return (
        f"[CRITIC] Plan review complete.\n"
        f"Assessment: Plan is structured and actionable.\n"
        f"{risk_note}\n"
        f"Recommendation: PROCEED\n"
        f"Confidence: 0.79 | timestamp: {_utc_now()}"
    )


def _stub_executor_response(plan: str, critique: str) -> str:
    """Deterministic executor response — final turn that completes the run."""
    return (
        f"[PLANNER] Acknowledged critique. Executing finalized plan.\n"
        f"Execution log:\n"
        f"  ✓ Research phase complete\n"
        f"  ✓ Draft phase complete\n"
        f"  ✓ Critique incorporated\n"
        f"  ✓ Final output produced\n"
        f"Status: COMPLETED | timestamp: {_utc_now()}"
    )


# ── AutoGen 0.7.x agent conversation ──────────────────────────────────────────

class AutoGenDemoConversation:
    """Drives a two-agent AutoGen conversation and exposes it turn-by-turn.

    Design choice: this class is NOT async internally. It uses asyncio.run()
    per-turn so the AutoGenAdapter (called from AgentFlow's synchronous runner)
    can consume one turn at a time without making the entire runner async.

    Turn boundary rule:
      Each complete message from one agent = one turn. The conversation
      follows the fixed sequence:
        turn_0 : PlannerAgent produces a plan  (analogous to research+draft)
        turn_1 : CriticAgent  reviews the plan (analogous to verify)
        turn_2 : PlannerAgent executes/finalises (analogous to act)

      Three turns is the minimum that demonstrates a real multi-agent exchange.
      The adapter maps each turn to one StepResult, preserving the conversation
      context across turns via self._history.
    """

    _TURN_SEQUENCE = ["turn_0", "turn_1", "turn_2"]

    def __init__(self, task: str, stub_mode: bool = True) -> None:
        self.task = task
        self.stub_mode = stub_mode
        self._history: list[dict[str, str]] = []
        self._agents_built = False
        self._agentchat_available = False
        self._check_availability()

    def _check_availability(self) -> None:
        try:
            import autogen_agentchat  # noqa: F401
            self._agentchat_available = True
        except ImportError:
            self._agentchat_available = False

    def run_turn(self, turn_id: str) -> dict[str, Any]:
        """Execute one turn and return its output dict.

        Returns a dict with: role, content, turn_id, history_so_far.
        """
        if self.stub_mode or not self._agentchat_available:
            return self._run_stub_turn(turn_id)
        return asyncio.run(self._run_live_turn(turn_id))

    # ── Stub turn execution ────────────────────────────────────────────────────

    def _run_stub_turn(self, turn_id: str) -> dict[str, Any]:
        """Run one turn using deterministic stub responses (no LLM call)."""
        if turn_id == "turn_0":
            content = _stub_planner_response(self.task)
            role = "planner"
        elif turn_id == "turn_1":
            prior = self._history[-1]["content"] if self._history else ""
            content = _stub_critic_response(prior)
            role = "critic"
        elif turn_id == "turn_2":
            plan = self._history[0]["content"] if len(self._history) > 0 else ""
            critique = self._history[1]["content"] if len(self._history) > 1 else ""
            content = _stub_executor_response(plan, critique)
            role = "planner"
        else:
            raise ValueError(f"Unknown turn_id {turn_id!r}")

        entry = {"turn_id": turn_id, "role": role, "content": content}
        self._history.append(entry)
        return {**entry, "history_so_far": list(self._history)}

    # ── Live AutoGen turn execution ────────────────────────────────────────────

    async def _run_live_turn(self, turn_id: str) -> dict[str, Any]:
        """Run one turn using real AutoGen 0.7.x agents (requires model_client)."""
        from autogen_agentchat.agents import AssistantAgent
        from autogen_agentchat.messages import TextMessage
        from autogen_core import CancellationToken

        # Build agents lazily (heavy — model client init happens once).
        if not self._agents_built:
            await self._build_agents()

        if turn_id == "turn_0":
            msg = TextMessage(content=f"Plan this task: {self.task}", source="user")
            result = await self._planner.on_messages([msg], CancellationToken())
            content = result.chat_message.content
            role = "planner"
        elif turn_id == "turn_1":
            prior = self._history[-1]["content"] if self._history else ""
            msg = TextMessage(content=f"Review this plan:\n{prior}", source="user")
            result = await self._critic.on_messages([msg], CancellationToken())
            content = result.chat_message.content
            role = "critic"
        elif turn_id == "turn_2":
            plan = self._history[0]["content"] if len(self._history) > 0 else ""
            critique = self._history[1]["content"] if len(self._history) > 1 else ""
            msg = TextMessage(
                content=f"Execute this plan (critique addressed):\n{plan}\nCritique:\n{critique}",
                source="user",
            )
            result = await self._planner.on_messages([msg], CancellationToken())
            content = result.chat_message.content
            role = "planner"
        else:
            raise ValueError(f"Unknown turn_id {turn_id!r}")

        entry = {"turn_id": turn_id, "role": role, "content": content}
        self._history.append(entry)
        return {**entry, "history_so_far": list(self._history)}

    async def _build_agents(self) -> None:
        from autogen_agentchat.agents import AssistantAgent
        from autogen_ext.models.openai import OpenAIChatCompletionClient

        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "stub")
        model_client = OpenAIChatCompletionClient(model="gpt-4o-mini", api_key=api_key)

        self._planner = AssistantAgent(
            name="PlannerAgent",
            model_client=model_client,
            system_message=(
                "You are a strategic planner. When given a task, produce a clear, "
                "numbered action plan. Be concise (3–5 steps max). When given critique, "
                "acknowledge it and produce a final execution summary."
            ),
        )
        self._critic = AssistantAgent(
            name="CriticAgent",
            model_client=model_client,
            system_message=(
                "You are a risk analyst. Review plans for safety, feasibility, and "
                "completeness. Flag any irreversible actions or high-risk steps. "
                "End with PROCEED, REVISE, or HALT."
            ),
        )
        self._agents_built = True

    def get_history(self) -> list[dict[str, str]]:
        return list(self._history)

    @classmethod
    def turn_sequence(cls) -> list[str]:
        return list(cls._TURN_SEQUENCE)
