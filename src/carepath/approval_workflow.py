"""Human approval gate for previously redacted synthetic reports.

No raw document, image or identifying OCR may enter this graph. The in-memory
checkpointer is for demos only; its lifetime and deletion need API integration.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from typing import Callable, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class ApprovalState(TypedDict, total=False):
    redacted_text: str
    report_digest: str
    review_status: str
    evidence: str


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate_redacted_text(text: str) -> None:
    if not isinstance(text, str) or not text.strip() or len(text) > 20000:
        raise ValueError("A nonempty redacted report is required")
    # These are narrow backstops, NOT complete PII identification.
    if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text):
        raise ValueError("Report still contains an email address")
    if "<PERSON>" not in text and "<EMAIL_ADDRESS>" not in text:
        # For a hackathon demonstration demand at least one explicit redaction.
        raise ValueError("Report has no recognizable redaction marker")


class ApprovalWorkflow:
    """Demo service with server-owned checkpoint state and opaque run identifiers."""

    def __init__(self, retrieve_evidence: Callable[[str], str]):
        self._retrieve = retrieve_evidence
        self._checkpointer = InMemorySaver()
        builder = StateGraph(ApprovalState)
        builder.add_node("review", self._review)
        builder.add_node("retrieve_evidence", self._retrieve_node)
        builder.add_edge(START, "review")
        builder.add_conditional_edges(
            "review", lambda state: "retrieve_evidence"
            if state.get("review_status") == "approved" else END,
            {"retrieve_evidence": "retrieve_evidence", END: END},
        )
        builder.add_edge("retrieve_evidence", END)
        self._graph = builder.compile(checkpointer=self._checkpointer)

    @staticmethod
    def _review(state: ApprovalState) -> dict:
        decision = interrupt({
            "kind": "redacted_report_review",
            "redacted_text": state["redacted_text"],
            "report_digest": state["report_digest"],
            "message": "Confirm that the report is accurate and no personal details remain.",
        })
        approved = (
            isinstance(decision, dict)
            and decision.get("approved") is True
            and isinstance(decision.get("report_digest"), str)
            and hmac.compare_digest(decision["report_digest"], state["report_digest"])
        )
        return {"review_status": "approved" if approved else "rejected"}

    def _retrieve_node(self, state: ApprovalState) -> dict:
        if state.get("review_status") != "approved":
            raise PermissionError("Report has not been approved")
        # Integration point for Member 2. Pass only user-confirmed redacted text.
        return {"evidence": self._retrieve(state["redacted_text"])}

    def start(self, redacted_text: str) -> tuple[str, dict]:
        _validate_redacted_text(redacted_text)
        run_id = uuid4().hex
        config = {"configurable": {"thread_id": run_id}}
        result = self._graph.invoke({
            "redacted_text": redacted_text,
            "report_digest": _digest(redacted_text),
            "review_status": "pending",
        }, config=config)
        if not result.get("__interrupt__"):
            raise RuntimeError("Workflow failed to pause for approval")
        return run_id, result["__interrupt__"][0].value

    def respond(self, run_id: str, approved: bool, report_digest: str) -> ApprovalState:
        if not isinstance(approved, bool):
            raise ValueError("approved must be a boolean")
        config = {"configurable": {"thread_id": run_id}}
        snapshot = self._graph.get_state(config)
        if not snapshot.values or not snapshot.next or "review" not in snapshot.next:
            raise ValueError("No pending approval for this run")
        result = self._graph.invoke(
            Command(resume={"approved": approved, "report_digest": report_digest}),
            config=config,
        )
        return result

    def delete(self, run_id: str) -> None:
        """Delete the workflow checkpoint. This does not delete external artefacts."""
        self._checkpointer.delete_thread(run_id)
