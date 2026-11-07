"""Clicks through the real app headlessly. Run with:  python -m pytest -q"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parent.parent / "app.py")


def button(at, label):
    return next(b for b in at.button if b.label == label)


def test_full_flow():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert "DEMO SEED DATA" in at.error[0].value

    button(at, "Run auto-schedule").click().run()
    assert not at.exception
    assert any(m.label == "Rule violations" and m.value == "0" for m in at.metric)
    assert any(m.label == "Assigned" and m.value == "11" for m in at.metric)

    # escalation panel shows the unstaffed Staten Island emergency
    assert any("T-1021" in e.value for e in at.error)

    # acknowledge it
    at.text_input(key="ack_a_T-1021").set_value("Called supervisor").run()
    at.text_input(key="ack_o_T-1021").set_value("Supervisor on duty").run()
    next(b for b in at.button if b.label == "Acknowledge escalation").click().run()
    assert not at.exception

    # deliberately invalid manual assign is rejected and state is unchanged
    at.selectbox(key="msg_ticket").select("T-1005").run()
    at.selectbox(key="m_slot").select("S1").run()
    at.selectbox(key="m_mech").select("Mechanic A (M1)").run()
    at.selectbox(key="m_help").select("Helper A (H1)").run()
    button(at, "Assign crew").click().run()
    assert not at.exception
    assert any(m.label == "Assigned" and m.value == "11" for m in at.metric)

    # reset keeps tickets and log
    next(c for c in at.checkbox if c.label == "Yes, reset the schedule").check().run()
    button(at, "Reset schedule").click().run()
    assert any(m.label == "Assigned" and m.value == "0" for m in at.metric)
    assert any(m.label == "Valid tickets" and m.value == "19" for m in at.metric)


def test_messages_tab_blocks_off_duty_and_sends_simulated():
    at = AppTest.from_file(APP, default_timeout=30).run()
    button(at, "Run auto-schedule").click().run()
    assert not at.exception
    # an absent person is blocked
    at.selectbox(key="msg_to").set_value("Mechanic E (Mechanic)").run()
    assert any("MESSAGE_BLOCKED_OFF_DUTY" in w.value for w in at.warning)
    button(at, "Send message").click().run()
    assert any("Not sent" in e.value for e in at.error)
    # a present person can be messaged
    at.selectbox(key="msg_to").set_value("Mechanic C (Mechanic)").run()
    at.selectbox(key="msg_ticket").set_value("T-1003").run()
    button(at, "Send message").click().run()
    assert not at.exception


def test_p1_agents_show_in_messages_tab():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert any(s.value == "Intake agent (advisory)" for s in at.subheader)
    at.selectbox(key="explain_code").set_value("NO_ACK").run()
    assert any("Next human action" in m.value for m in at.markdown)
    assert "Shift handover DRAFT" in at.text_area(key="handover_draft").value


def test_switch_to_mock_maximo_source():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.selectbox(key="source_pick").set_value("Mock Maximo feed").run()
    assert not at.exception
    assert any(m.label == "Valid tickets" and m.value == "19" for m in at.metric)
    assert any("Mock Maximo feed" in c.value for c in at.caption)
