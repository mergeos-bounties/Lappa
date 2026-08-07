"""Workspace state and ROS package discovery."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from lappa.config import DEMOS_ROOT, WORKSPACES, ensure_dirs
from lappa.package_loader import RosPackage, load_package

WORKSPACE_FILE = "workspace.json"
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "install",
    "log",
    "node_modules",
}


def workspace_file(state_path: Path | None = None) -> Path:
    ensure_dirs()
    return state_path or (WORKSPACES / WORKSPACE_FILE)


def default_workspace_state() -> dict[str, Any]:
    return {
        "name": "Default",
        "roots": [str(DEMOS_ROOT.resolve())],
        "active_package": None,
    }


def _clean_roots(roots: list[str | Path]) -> list[str]:
    seen: set[str] = set()
    clean: list[str] = []
    for raw in roots:
        try:
            path = Path(raw).expanduser().resolve()
        except (OSError, RuntimeError, ValueError):
            continue
        key = str(path)
        if key not in seen:
            seen.add(key)
            clean.append(key)
    return clean


def load_workspace_state(state_path: Path | None = None) -> dict[str, Any]:
    path = workspace_file(state_path)
    if not path.is_file():
        return default_workspace_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_workspace_state()
    roots = data.get("roots") if isinstance(data, dict) else None
    if not isinstance(roots, list):
        roots = []
    active = data.get("active_package") if isinstance(data, dict) else None
    name = data.get("name") if isinstance(data, dict) else None
    return {
        "name": str(name or "Workspace"),
        "roots": _clean_roots(roots),
        "active_package": str(active) if active else None,
    }


def save_workspace_state(state: dict[str, Any], state_path: Path | None = None) -> dict[str, Any]:
    path = workspace_file(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "name": str(state.get("name") or "Workspace"),
        "roots": _clean_roots(state.get("roots") or []),
        "active_package": state.get("active_package") or None,
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def create_workspace(
    name: str = "Workspace",
    roots: list[str | Path] | None = None,
    *,
    include_samples: bool = False,
    state_path: Path | None = None,
) -> dict[str, Any]:
    initial_roots = list(roots or [])
    if include_samples:
        initial_roots.insert(0, DEMOS_ROOT)
    return save_workspace_state(
        {"name": name, "roots": initial_roots, "active_package": None},
        state_path=state_path,
    )


def workspace_roots(state_path: Path | None = None) -> list[Path]:
    state = load_workspace_state(state_path)
    roots: list[Path] = []
    for raw in state.get("roots") or []:
        path = Path(raw)
        if path.is_dir():
            roots.append(path)
    return roots


def add_workspace_root(
    root: str | Path,
    *,
    state_path: Path | None = None,
) -> dict[str, Any]:
    path = Path(root).expanduser().resolve()
    if not path.is_dir():
        raise FileNotFoundError(str(root))
    state = load_workspace_state(state_path)
    roots = list(state.get("roots") or [])
    roots.append(path)
    state["roots"] = _clean_roots(roots)
    return save_workspace_state(state, state_path=state_path)


def remove_workspace_root(
    root: str | Path,
    *,
    state_path: Path | None = None,
) -> dict[str, Any]:
    path = str(Path(root).expanduser().resolve())
    state = load_workspace_state(state_path)
    state["roots"] = [r for r in state.get("roots") or [] if str(Path(r).resolve()) != path]
    return save_workspace_state(state, state_path=state_path)


def is_ros_package_dir(path: str | Path) -> bool:
    p = Path(path)
    return p.is_dir() and (p / "package.xml").is_file()


def _walk_package_dirs(root: Path, max_depth: int) -> list[Path]:
    found: list[Path] = []
    root = root.resolve()
    for current, dirnames, filenames in os.walk(root):
        cur = Path(current)
        try:
            rel = cur.relative_to(root)
        except ValueError:
            continue
        depth = 0 if rel == Path(".") else len(rel.parts)
        dirnames[:] = sorted(
            d
            for d in dirnames
            if d not in SKIP_DIRS and not d.startswith(".") and depth < max_depth
        )
        if "package.xml" in filenames:
            found.append(cur)
            dirnames[:] = []
    return found


def discover_packages(root: str | Path, *, max_depth: int = 5) -> list[RosPackage]:
    path = Path(root).expanduser().resolve()
    if not path.is_dir():
        return []
    dirs = _walk_package_dirs(path, max_depth=max_depth)
    packages: dict[str, RosPackage] = {}
    for pkg_dir in dirs:
        try:
            pkg = load_package(pkg_dir)
        except OSError:
            continue
        packages[str(pkg.path)] = pkg
    return sorted(packages.values(), key=lambda p: (p.name.lower(), str(p.path).lower()))


def workspace_packages(state_path: Path | None = None) -> list[RosPackage]:
    packages: dict[str, RosPackage] = {}
    for root in workspace_roots(state_path):
        for pkg in discover_packages(root):
            packages[str(pkg.path)] = pkg
    return sorted(packages.values(), key=lambda p: (p.name.lower(), str(p.path).lower()))


def set_active_package(
    package_path: str | Path | None,
    *,
    state_path: Path | None = None,
) -> dict[str, Any]:
    state = load_workspace_state(state_path)
    state["active_package"] = str(Path(package_path).resolve()) if package_path else None
    return save_workspace_state(state, state_path=state_path)


def active_package(state_path: Path | None = None) -> RosPackage | None:
    state = load_workspace_state(state_path)
    raw = state.get("active_package")
    if raw and is_ros_package_dir(raw):
        return load_package(Path(raw))
    packages = workspace_packages(state_path)
    return packages[0] if packages else None


def resolve_package_ref(
    ref: str | Path,
    *,
    base_dir: Path | None = None,
    state_path: Path | None = None,
) -> RosPackage:
    text = str(ref).strip()
    if not text:
        raise FileNotFoundError("package reference is empty")

    explicit = Path(text).expanduser()
    candidates: list[Path] = []
    if explicit.is_absolute():
        candidates.append(explicit)
    else:
        if base_dir:
            candidates.append(base_dir / explicit)
        candidates.append(DEMOS_ROOT / explicit)

    for cand in candidates:
        cand = cand.resolve()
        if is_ros_package_dir(cand):
            return load_package(cand)

    for pkg in workspace_packages(state_path):
        if text in {pkg.name, pkg.path.name, str(pkg.path)}:
            return pkg
    raise FileNotFoundError(f"package not found: {text}")
