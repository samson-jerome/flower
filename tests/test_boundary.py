import ast
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1] / "src" / "flower" / "engine"

# The engine must run without a graphical toolkit, and must never depend on
# the layer that consumes it. Both rules are checked on the AST rather than
# with a text search, so the words are only caught in real import statements
# and not in a docstring or a comment.
FORBIDDEN = ("PySide6", "flower.app")


def _imported_modules(tree: ast.AST) -> list[str]:
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def test_the_engine_package_exists():
    assert ENGINE.is_dir()
    assert list(ENGINE.rglob("*.py"))


def test_the_engine_never_imports_qt_or_the_app():
    offences = []
    for path in sorted(ENGINE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module in _imported_modules(tree):
            if any(module == f or module.startswith(f + ".") for f in FORBIDDEN):
                offences.append(f"{path.relative_to(ENGINE.parents[2])}: {module}")
    assert offences == [], "the engine must stay free of Qt and of flower.app:\n" + "\n".join(offences)
