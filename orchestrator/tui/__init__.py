"""Textual-based TUI dashboard for the orchestrator."""

try:
    from .app import DashboardApp
    __all__ = ['DashboardApp']
    TUI_AVAILABLE = True
except ImportError:
    TUI_AVAILABLE = False
    __all__ = []
