"""Operational metrics (Prometheus).

The ledger answers "what happened"; this answers "what's happening now".
Counters are fed from the kernel event bus, so anything the guard sees is
countable without instrumenting individual skills.
"""

from __future__ import annotations

from prometheus_client import (
    CollectorRegistry, Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST,
)

registry = CollectorRegistry()

TOOL_CALLS = Counter("bsos_tool_calls_total", "Tool calls through the guard",
                     ["agent", "outcome"], registry=registry)
POLICY_DENIALS = Counter("bsos_policy_denials_total", "Policy denials",
                         ["policy"], registry=registry)
ESCALATIONS = Counter("bsos_escalations_total", "Policy escalations",
                      ["policy"], registry=registry)
GRANT_VIOLATIONS = Counter("bsos_grant_violations_total", "Grant violations",
                           ["agent"], registry=registry)
GATE_REJECTIONS = Counter("bsos_gate_rejections_total", "Originality gate rejections",
                          registry=registry)
HTTP_REQUESTS = Counter("bsos_http_requests_total", "API requests",
                        ["method", "status"], registry=registry)
GRAPH_BUDGET = Gauge("bsos_graph_rate_budget_remaining", "Graph API calls left this hour",
                     registry=registry)


def attach_to_bus(bus) -> None:
    def on_event(topic: str, event: dict) -> None:
        outcome = event.get("outcome", "")
        if topic == "tool_call":
            TOOL_CALLS.labels(agent=event.get("agent", "?"), outcome=outcome).inc()
        elif topic == "policy_evaluation":
            policy = event.get("policy_id", "?")
            if outcome == "deny":
                POLICY_DENIALS.labels(policy=policy).inc()
            elif outcome == "escalate":
                ESCALATIONS.labels(policy=policy).inc()
        elif topic == "grant_violation":
            GRANT_VIOLATIONS.labels(agent=event.get("agent", "?")).inc()

    bus.subscribe("*", on_event)


def render() -> tuple[bytes, str]:
    return generate_latest(registry), CONTENT_TYPE_LATEST
