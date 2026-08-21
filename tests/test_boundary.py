import ast
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1] / "src" / "flower" / "engine"
SRC = ENGINE.parents[1]

# The engine must run without a graphical toolkit, and must never depend on
# the layer that consumes it. Both rules are checked on the AST rather than
# with a text search, so the words are only caught in real import statements
# and not in a docstring or a comment.
FORBIDDEN = ("PySide6", "flower.app")


def _package_name(path: Path) -> str:
    """The dotted package that resolves this file's relative imports.

    Mirrors Python's own `__package__`: for a regular module it is the
    parent package (drop the last segment); for a package's `__init__.py`
    it is the module itself, since a package's `__name__` already *is* its
    package name.
    """
    parts = list(path.relative_to(SRC).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
        return ".".join(parts)
    return ".".join(parts[:-1])


def _resolve_relative(package: str, level: int, module: str | None) -> str:
    """Resolve a relative `from` import to an absolute dotted module path.

    Follows the same rule as CPython's import machinery: `level=1` targets
    `package` itself (`from . import x`), `level=2` targets its parent
    (`from .. import x`), and so on - each extra dot strips one more
    trailing segment from `package` before `module` is appended.
    """
    parts = package.split(".") if package else []
    base_parts = parts[: len(parts) - (level - 1)]
    if module:
        base_parts = base_parts + module.split(".")
    return ".".join(base_parts)


def _imported_modules(tree: ast.AST, package: str) -> list[str]:
    """All dotted module names a file's import statements actually reference.

    For `ast.ImportFrom`, Python lets a multi-segment target such as
    `flower.app` be split across `node.module` ("flower") and
    `alias.name` ("app") - e.g. `from flower import app`. Looking only at
    `node.module` would miss that entirely, so this also builds the joined
    "<base>.<alias>" name for every alias.

    Relative imports (`from ..app import x`) are resolved against the
    importing file's own package (see `_resolve_relative`) before the same
    check applies. The engine only uses absolute imports today, but nothing
    in the language stops a future file from reaching for the app layer
    through a relative import instead, and this guard must catch that too.

    Dynamic imports (e.g. `importlib.import_module("PySide6.QtCore")`) are
    invisible to a static AST walk and are intentionally out of scope.
    """
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module if node.level == 0 else _resolve_relative(package, node.level, node.module)
            if base:
                modules.append(base)
            modules.extend(f"{base}.{alias.name}" if base else alias.name for alias in node.names)
    return modules


def test_the_engine_package_exists():
    assert ENGINE.is_dir()
    assert list(ENGINE.rglob("*.py"))


def test_the_engine_never_imports_qt_or_the_app():
    offences = []
    for path in sorted(ENGINE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        package = _package_name(path)
        for module in _imported_modules(tree, package):
            if any(module == f or module.startswith(f + ".") for f in FORBIDDEN):
                offences.append(f"{path.relative_to(SRC.parent)}: {module}")
    assert offences == [], "the engine must stay free of Qt and of flower.app:\n" + "\n".join(offences)
