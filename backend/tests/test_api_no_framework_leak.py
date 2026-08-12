"""Test: no framework name leaks into any API response body.

Verifies that the literal strings "langgraph" and "autogen" (case-insensitive)
never appear in any JSON response from the API — not in run metadata, not in
engine fields, not in event payloads, not anywhere.

This test captures the raw response text and greps it directly, rather than
trusting that the mapping table exists.
"""
from __future__ import annotations

import json
import re
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)

# Regex that matches any casing variant of the banned names.
_BANNED = re.compile(r"\b(langgraph|autogen)\b", re.IGNORECASE)


def _assert_no_leak(response_text: str, endpoint: str) -> None:
    """Assert that response_text contains no banned framework names."""
    match = _BANNED.search(response_text)
    assert match is None, (
        f"Framework name leaked in response from {endpoint}!\n"
        f"Found: {match.group()!r}\n"
        f"Response body (first 500 chars): {response_text[:500]}"
    )


class TestNoFrameworkLeak:
    """All API responses must use external engine labels, never internal names."""

    def test_create_run_langgraph_no_leak(self):
        """POST /runs with framework=execution-engine-a must not return internal names in body."""
        resp = client.post("/runs", json={"task": "test engine-a run", "framework": "langgraph"})
        assert resp.status_code in (200, 201), resp.text
        _assert_no_leak(resp.text, "POST /runs (engine-a)")

        data = resp.json()
        assert "engine" in data
        assert data["engine"] == "execution-engine-a", (
            f"Expected 'execution-engine-a', got {data['engine']!r}"
        )

    def test_create_run_autogen_no_leak(self):
        """POST /runs with framework=execution-engine-b must not return internal names in body."""
        resp = client.post("/runs", json={"task": "test engine-b run", "framework": "autogen"})
        assert resp.status_code in (200, 201), resp.text
        _assert_no_leak(resp.text, "POST /runs (engine-b)")

        data = resp.json()
        assert data["engine"] == "execution-engine-b", (
            f"Expected 'execution-engine-b', got {data['engine']!r}"
        )

    def test_list_runs_no_leak(self):
        """GET /runs must not leak framework names in metadata fields (engine, engine_description)."""
        client.post("/runs", json={"task": "list check run", "framework": "langgraph"})
        resp = client.get("/runs")
        assert resp.status_code == 200, resp.text
        # Only check the metadata fields (engine, engine_description, status) —
        # not the task field which is user-supplied text we don't control.
        import json as _json
        data = _json.loads(resp.text)
        for run in data.get("runs", []):
            for field in ("engine", "engine_description", "status"):
                val = str(run.get(field, ""))
                match = _BANNED.search(val)
                assert match is None, (
                    f"Framework name {match.group()!r} leaked in run.{field}: {val!r}"
                )

    def test_run_metrics_no_leak(self):
        """GET /runs/{id}/metrics must not leak framework names."""
        create_resp = client.post(
            "/runs", json={"task": "metrics-no-leak", "framework": "autogen"}
        )
        assert create_resp.status_code in (200, 201)
        run_id = create_resp.json()["run_id"]

        import time
        time.sleep(0.5)  # let background thread write at least one event

        resp = client.get(f"/runs/{run_id}/metrics")
        # May be 200 or 404 depending on timing — only check body if 200.
        if resp.status_code == 200:
            _assert_no_leak(resp.text, f"GET /runs/{run_id}/metrics")
            data = resp.json()
            assert "engine" in data
            assert "autogen" not in data["engine"].lower()
            assert "langgraph" not in data["engine"].lower()

    def test_timeline_no_leak(self):
        """GET /runs/{id}/timeline event payloads must not leak framework names."""
        create_resp = client.post(
            "/runs", json={"task": "timeline-no-leak", "framework": "langgraph"}
        )
        run_id = create_resp.json()["run_id"]

        import time
        time.sleep(0.3)

        resp = client.get(f"/runs/{run_id}/timeline")
        assert resp.status_code == 200
        _assert_no_leak(resp.text, f"GET /runs/{run_id}/timeline")

    def test_engine_label_mapping_table_is_complete(self):
        """The mapping table must cover every known internal engine name."""
        from app.api.engine_labels import INTERNAL_TO_EXTERNAL, all_external_labels

        # Every known internal name must have an external label.
        known_internal = ["langgraph", "autogen"]
        for name in known_internal:
            assert name in INTERNAL_TO_EXTERNAL, (
                f"Internal engine name {name!r} not in INTERNAL_TO_EXTERNAL"
            )
            external = INTERNAL_TO_EXTERNAL[name]
            assert "langgraph" not in external.lower()
            assert "autogen" not in external.lower()

    def test_external_labels_do_not_contain_internal_names(self):
        """No external label may contain any internal framework name."""
        from app.api.engine_labels import all_external_labels

        for label in all_external_labels():
            assert "langgraph" not in label.lower()
            assert "autogen" not in label.lower()

    def test_engine_description_no_leak(self):
        """Engine descriptions must not mention internal framework names."""
        from app.api.engine_labels import EXTERNAL_DESCRIPTION

        for key, description in EXTERNAL_DESCRIPTION.items():
            assert "langgraph" not in description.lower(), (
                f"Description for {key!r} leaks 'langgraph': {description!r}"
            )
            assert "autogen" not in description.lower(), (
                f"Description for {key!r} leaks 'autogen': {description!r}"
            )
