"""AGENTS.md: risk/ imports nothing from Django, does no I/O and reads no clock."""

import ast
from pathlib import Path

import risk

ALLOWED_MODULES = {
    "bisect",
    "collections",
    "dataclasses",
    "decimal",
    "enum",
    "functools",
    "itertools",
    "math",
}
RISK_DIR = Path(risk.__file__).parent


def imported_modules(path: Path) -> set[str]:
    modules = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def test_risk_package_imports_only_pure_standard_library_modules():
    for path in sorted(RISK_DIR.glob("*.py")):
        unexpected = imported_modules(path) - ALLOWED_MODULES - {"risk"}
        assert not unexpected, f"{path.name} imports {sorted(unexpected)}"
