"""Explicit interface-test entrypoint. Never deploy this file as the product."""
from pathlib import Path
import tempfile
import streamlit as st
from variance_workspace.data import Workspace
from variance_workspace.workflow import Service
from variance_tests.fakes import Planner
import variance_workspace.runtime as runtime

@st.cache_resource(show_spinner=False)
def fixture_service(key):
    return Service(Workspace(Path(tempfile.gettempdir()) / "variance-ui-fixture" / key), Planner())

runtime.get_service = fixture_service
import importlib
import streamlit_app
importlib.reload(streamlit_app)
streamlit_app.main()
