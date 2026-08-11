"""Basic smoke tests for the three memory tiers."""
from app.core.memory import short_term, episodic


def test_short_term_scratchpad_roundtrip():
    short_term.set_value("run-x", "key", "value")
    assert short_term.get_scratchpad("run-x")["key"] == "value"
    short_term.clear("run-x")
    assert short_term.get_scratchpad("run-x") == {}


def test_episodic_add_and_query():
    episodic.add_step("run-x", "step-1", "researched topic A")
    results = episodic.query_similar("topic A", n_results=1)
    assert results is not None
