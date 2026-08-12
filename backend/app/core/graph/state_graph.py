"""LangGraph StateGraph wiring + checkpointer attachment.

This is the graph-native core: nodes are checkpointed after every
transition, so a crash mid-run can resume from the last completed node
instead of restarting the whole task.

Routing summary (after verify_step):
  risk <= escalation_continue_max  -> "act"            (safe to proceed)
  risk <= escalation_approve_max   -> blocks on gate   (human approval needed)
  risk >  escalation_approve_max   -> END (halted)     (too risky; stop here)

Stage-5 approval gate:
  REQUEST_APPROVAL registers a threading.Event in escalations._GATES,
  logs status=awaiting_approval, then blocks the graph thread until the
  frontend calls POST /approve or /reject. On approve the run continues
  to act_step; on reject it ends with status=halted.
"""
from langgraph.graph import END, StateGraph

from app.core.checkpointing.checkpointer import get_checkpointer
from app.core.escalation.thresholds import decide_next_action
from app.core.graph.nodes import act_step, draft_step, research_step, verify_step
from app.core.graph.schemas import AgentState
from app.observability.event_log import log_event


def route_after_verify(state: AgentState) -> str:
    """Map the verify_step risk_score to the next graph node (or END).

    Returns a string key that matches the mapping passed to
    add_conditional_edges(), or the sentinel END constant.
    """
    risk = state.get("risk_score", 0.0)
    run_id = state.get("run_id", "unknown")
    decision = decide_next_action(risk)

    if decision == "HALT":
        # Risk exceeds escalation_approve_max: unsafe to proceed or seek
        # approval — halt the run immediately.  Status is left as "running"
        # here; the caller/checkpointer layer (Stage-2) is responsible for
        # persisting the final state with status="halted".
        log_event(run_id, "routing_decision", {"decision": "HALT", "risk_score": risk})
        return END  # type: ignore[return-value]

    if decision == "REQUEST_APPROVAL":
        # ── Stage-5 approval gate ────────────────────────────────────────────
        # Register a threading.Event gate, log awaiting_approval into the
        # timeline (the frontend polls this and shows the amber banner), then
        # block this thread until Approve or Reject arrives via HTTP.
        from app.api.routes.escalations import (
            clear_gate,
            get_decision,
            register_approval_gate,
        )

        gate = register_approval_gate(run_id)
        log_event(
            run_id,
            "awaiting_approval",
            {"risk_score": risk, "decision": "REQUEST_APPROVAL", "status": "awaiting_approval"},
        )
        log_event(
            run_id,
            "routing_decision",
            {"decision": "REQUEST_APPROVAL", "risk_score": risk},
        )

        # Block until the frontend calls /approve or /reject (no timeout —
        # this is intentional: the run waits indefinitely for human input).
        gate.wait()
        human_decision = get_decision(run_id)
        clear_gate(run_id)

        if human_decision == "approved":
            log_event(run_id, "escalation_approved", {"risk_score": risk})
            # Mutate state so act_step sees updated status.
            state["status"] = "running"  # type: ignore[index]
            return "act"
        else:
            log_event(run_id, "escalation_rejected", {"risk_score": risk})
            state["status"] = "halted"   # type: ignore[index]
            return END  # type: ignore[return-value]

    # decision == "CONTINUE": risk is within the safe threshold — proceed to
    # act_step and let the agent execute the verified plan.
    log_event(run_id, "routing_decision", {"decision": "CONTINUE", "risk_score": risk})
    return "act"


def build_graph():
    """Construct and compile the AgentFlow StateGraph.

    Returns a CompiledGraph ready for .invoke() / .stream() calls.
    The checkpointer is injected here so every node transition is persisted;
    swap get_checkpointer() to return a PostgresSaver for production (Stage-2).
    """
    graph = StateGraph(AgentState)

    graph.add_node("research", research_step)
    graph.add_node("draft", draft_step)
    graph.add_node("verify", verify_step)
    graph.add_node("act", act_step)

    graph.set_entry_point("research")
    graph.add_edge("research", "draft")
    graph.add_edge("draft", "verify")

    # Conditional routing: verify_step computes risk_score; route_after_verify
    # maps that to either "act" (safe) or END (halt / awaiting approval).
    graph.add_conditional_edges(
        "verify",
        route_after_verify,
        {
            "act": "act",  # CONTINUE branch
            END: END,      # HALT or REQUEST_APPROVAL branch
        },
    )

    graph.add_edge("act", END)

    return graph.compile(checkpointer=get_checkpointer())
