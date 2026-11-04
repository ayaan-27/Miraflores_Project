from pathlib import Path
import re
import streamlit as st

from .data import Workspace
from .model import Model, DATA_ROOT
from .workflow import Service


@st.cache_resource(show_spinner=False)
def get_model():
    return Model()


@st.cache_resource(show_spinner=False, max_entries=20)
def get_service(key: str):
    if not re.fullmatch(r"[a-f0-9]{32}", key):
        raise ValueError("Invalid workspace.")
    return Service(Workspace(DATA_ROOT / "workspaces" / key), get_model())
