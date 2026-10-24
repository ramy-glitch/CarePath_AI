import pytest
from carepath.approval_workflow import ApprovalWorkflow

REPORT = "FULL BLOOD COUNT Patient Name: <PERSON> Email: <EMAIL_ADDRESS> Haemoglobin: 13.5 g/dL"


def test_approval_required_before_retrieval():
    calls = []
    flow = ApprovalWorkflow(lambda text: calls.append(text) or "NHS evidence placeholder")
    run_id, preview = flow.start(REPORT)
    assert preview["redacted_text"] == REPORT
    assert calls == []
    state = flow.respond(run_id, True, preview["report_digest"])
    assert state["review_status"] == "approved"
    assert state["evidence"] == "NHS evidence placeholder"
    assert calls == [REPORT]
    flow.delete(run_id)


def test_rejection_blocks_retrieval():
    calls = []
    flow = ApprovalWorkflow(lambda text: calls.append(text) or "not reached")
    run_id, preview = flow.start(REPORT)
    result = flow.respond(run_id, False, preview["report_digest"])
    assert result["review_status"] == "rejected"
    assert calls == []
    with pytest.raises(ValueError):
        flow.respond(run_id, True, preview["report_digest"])
    flow.delete(run_id)


def test_digest_mismatch_fails_closed():
    calls = []
    flow = ApprovalWorkflow(lambda text: calls.append(text) or "not reached")
    run_id, _preview = flow.start(REPORT)
    result = flow.respond(run_id, True, "wrong-digest")
    assert result["review_status"] == "rejected"
    assert not calls
    flow.delete(run_id)


def test_unredacted_email_is_rejected():
    flow = ApprovalWorkflow(lambda _text: "unused")
    with pytest.raises(ValueError):
        flow.start("Patient Name: <PERSON> john.smith@example.com")
