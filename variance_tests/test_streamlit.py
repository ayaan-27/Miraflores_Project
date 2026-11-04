from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

from variance_workspace.data import Workspace
from variance_workspace.workflow import Service
from variance_tests.fakes import Planner
import variance_workspace.runtime as runtime

ROOT = Path(__file__).resolve().parents[1]


def click(app, label):
    button = next(b for b in app.button if b.label == label)
    return button.click().run(timeout=30)


def test_streamlit_review_evidence_and_revised_workpaper(tmp_path, monkeypatch):
    service = Service(Workspace(tmp_path), Planner())
    monkeypatch.setattr(runtime, "get_service", lambda key: service)
    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
    assert not app.exception
    assert app.title[0].value == "Month-end review"
    assert any(m.value == "$26,000.00" for m in app.metric)
    click(app, "Investigate")
    assert not app.exception
    assert next(b for b in app.button if b.label == "Approve workpaper").disabled
    app.text_input(key="reviewer_name").set_value("Ayaan Khan")
    app.text_area(key="review_note").set_value("Please supply the annual agreement and service dates.")
    click(app, "Request evidence")
    assert not app.exception
    assert any(h.value == "Additional evidence" for h in app.subheader)
    click(app, "Use sample agreement")
    assert not app.exception
    assert any("$4,000.00" in c.value for c in app.caption)
    assert not next(b for b in app.button if b.label == "Approve workpaper").disabled
    app.text_area(key="review_note").set_value("Checked the agreement, monthly allocation, and proposed entry.")
    click(app, "Approve workpaper")
    assert not app.exception
    assert any(s.value == "Workpaper approved" for s in app.success)
    run = service.view(service.latest("6100"))
    assert run["completion"]["journal_posted"] is False
    assert len(run["history"]) == 2


def test_streamlit_switches_to_bonus_and_below_threshold_account(tmp_path, monkeypatch):
    service = Service(Workspace(tmp_path), Planner())
    monkeypatch.setattr(runtime, "get_service", lambda key: service)
    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
    app.radio(key="account_choice").set_value("6200").run()
    click(app, "Investigate")
    assert not app.exception
    assert any("supported" in s.value for s in app.success)
    app.radio(key="account_choice").set_value("6400").run()
    assert next(b for b in app.button if b.label == "Investigate").disabled
