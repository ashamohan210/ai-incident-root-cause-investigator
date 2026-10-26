"""Stable application entry point; backend-connected UI lives in ui.py."""
from .ui import render_app


def render_home() -> None:
    render_app()
