from __future__ import annotations
from flower.engine.errors import CycleError, GraphRuleError, MaxChildrenError
from flower.i18n import t


def rule_message(error: GraphRuleError) -> str:
    """Sentence for a refused mutation, for the status bar.

    The engine raises structured exceptions and never carries wording; this
    is where a rule becomes a phrase the user reads."""
    if isinstance(error, MaxChildrenError):
        return t("error.max_children",
                 type=error.node_type.value, max=error.max_children)
    if isinstance(error, CycleError):
        return t("error.cycle")
    return str(error)
