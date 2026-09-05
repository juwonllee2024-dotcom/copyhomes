"""Save one file to multiple explicit local homes, safely."""

from .core import (
    HomePlan,
    Plan,
    PlanConflictError,
    UndoConflictError,
    build_plan,
    save_plan,
    undo_receipt,
)

__all__ = [
    "HomePlan",
    "Plan",
    "PlanConflictError",
    "UndoConflictError",
    "build_plan",
    "save_plan",
    "undo_receipt",
]

__version__ = "0.1.0"
