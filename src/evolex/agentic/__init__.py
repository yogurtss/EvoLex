"""Information-gain driven agentic control for EvoLex KG runs."""

from evolex.agentic.controller import AgenticKGRunner
from evolex.agentic.math import (
    action_utility,
    binary_entropy,
    expected_information_gain,
)

__all__ = [
    "AgenticKGRunner",
    "action_utility",
    "binary_entropy",
    "expected_information_gain",
]
