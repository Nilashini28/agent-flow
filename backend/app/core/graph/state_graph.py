"""LangGraph StateGraph wiring + checkpointer attachment.

This is the graph-native core: nodes are checkpointed after every
transition, so a crash mid-run can resume from the last completed node
instead of restarting the whole task.

Routing summary (after verify_step):
  risk <= escalation_continue_max  -> "act"           (safe to proceed)
  risk <= escalation_approve_max   -> END (awaiting)  (human approval needed)
  risk >  escalation_approve_max   -> END (halted)    (too risky; stop here)

# STAGE-2: checkpoint recovery (resume after halt/crash) wires in here.
# STAGE-5: escalation hooks (Slack / human-in-the-loop) attach to
#           route_after_verify's REQUEST_APPROVAL branch.
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
        # Risk is between continue_max and approve_max: pause and surface to a
        # human operator.  The run stays in the checkpoint store; Stage-2 will
        # allow resumption once approval is granted.
        log_event(
            run_id,
            "routing_decision",
            {"decision": "REQUEST_APPROVAL", "risk_score": risk},
        )
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
