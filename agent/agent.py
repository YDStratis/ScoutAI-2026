"""Compatibility shim so ADK discovery finds root_agent from the agent/ directory."""
try:
    from coach_agent.agent import root_agent  # run from inside agent/ (adk web)
except ImportError:
    from .coach_agent.agent import root_agent  # imported as package agent.agent

__all__ = ["root_agent"]
