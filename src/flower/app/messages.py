from __future__ import annotations
from flower.engine.errors import CycleError, GraphRuleError, MaxChildrenError


def rule_message(error: GraphRuleError) -> str:
    """French sentence for a refused mutation, for the status bar.

    The engine raises structured exceptions and never carries wording; this
    is where a rule becomes a phrase the user reads."""
    if isinstance(error, MaxChildrenError):
        return (
            f"Un nœud « {error.node_type.value} » ne peut avoir plus de "
            f"{error.max_children} enfant(s)."
        )
    if isinstance(error, CycleError):
        return "Un nœud ne peut pas devenir son propre descendant."
    return str(error)
