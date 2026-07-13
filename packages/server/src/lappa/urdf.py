"""Lightweight URDF parsing → link/joint graph → 2D "stick" figure.

Parses a robot description (URDF XML) into links and joints, resolves each
link's pose relative to the root by walking the joint tree, and emits a simple
stick-figure overlay: one node per link plus one segment per joint (base → child).

The IDE canvas consumes ``stick_figure()`` to draw a top-down (XY) sketch of the
robot — at minimum the base link and its wheels — without needing any meshes.
Everything here is dependency-free (xml.etree only) so it runs in the sim path.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from lappa.packager import resolve_package_path


def _parse_triplet(value: str | None, default: tuple[float, float, float]) -> list[float]:
    """Parse a whitespace-separated "x y z" attribute into 3 floats."""
    if not value:
        return list(default)
    parts = value.replace(",", " ").split()
    out: list[float] = []
    for i in range(3):
        try:
            out.append(float(parts[i]))
        except (IndexError, ValueError):
            out.append(default[i])
    return out


def _classify_link(name: str) -> str:
    """Best-effort role from a link name (used for colouring the sticks)."""
    low = name.lower()
    if "wheel" in low:
        return "wheel"
    if "lidar" in low or "laser" in low or "scan" in low:
        return "lidar"
    if "base_link" in low or low in {"base", "chassis"}:
        return "base"
    if "footprint" in low:
        return "footprint"
    if "link" in low or "arm" in low:
        return "arm_link"
    return "part"


def parse_urdf(urdf_text: str) -> dict[str, Any]:
    """Parse URDF XML text into a ``{"robot", "links", "joints"}`` dict.

    Links carry their declared visual origin; joints carry parent/child and the
    origin (xyz/rpy) that places the child frame relative to the parent.
    Raises ``ValueError`` on malformed XML.
    """
    try:
        root = ET.fromstring(urdf_text)
    except ET.ParseError as exc:
        raise ValueError(f"invalid URDF XML: {exc}") from exc

    robot_name = root.attrib.get("name", "robot")

    links: list[dict[str, Any]] = []
    for link_el in root.findall("link"):
        name = link_el.attrib.get("name")
        if not name:
            continue
        origin_el = link_el.find("./visual/origin")
        xyz = _parse_triplet(origin_el.attrib.get("xyz") if origin_el is not None else None,
                             (0.0, 0.0, 0.0))
        rpy = _parse_triplet(origin_el.attrib.get("rpy") if origin_el is not None else None,
                             (0.0, 0.0, 0.0))
        links.append({
            "name": name,
            "role": _classify_link(name),
            "has_visual": link_el.find("visual") is not None,
            "visual_xyz": xyz,
            "visual_rpy": rpy,
        })

    joints: list[dict[str, Any]] = []
    for joint_el in root.findall("joint"):
        name = joint_el.attrib.get("name", "")
        jtype = joint_el.attrib.get("type", "fixed")
        parent_el = joint_el.find("parent")
        child_el = joint_el.find("child")
        parent = parent_el.attrib.get("link") if parent_el is not None else None
        child = child_el.attrib.get("link") if child_el is not None else None
        if not parent or not child:
            continue
        origin_el = joint_el.find("origin")
        xyz = _parse_triplet(origin_el.attrib.get("xyz") if origin_el is not None else None,
                             (0.0, 0.0, 0.0))
        rpy = _parse_triplet(origin_el.attrib.get("rpy") if origin_el is not None else None,
                             (0.0, 0.0, 0.0))
        joints.append({
            "name": name,
            "type": jtype,
            "parent": parent,
            "child": child,
            "xyz": xyz,
            "rpy": rpy,
        })

    return {"robot": robot_name, "links": links, "joints": joints}


def link_poses(parsed: dict[str, Any]) -> dict[str, list[float]]:
    """Resolve every link's origin (x, y, z) relative to the root link.

    Walks the joint tree accumulating joint origin translations. Links not
    reachable from the root fall back to the origin. Yaw/rotation is not
    accumulated — a top-down stick sketch only needs translated positions.
    """
    link_names = [link["name"] for link in parsed["links"]]
    if not link_names:
        return {}

    children = {j["child"] for j in parsed["joints"]}
    roots = [n for n in link_names if n not in children]
    root = roots[0] if roots else link_names[0]

    child_joints: dict[str, list[dict[str, Any]]] = {}
    for joint in parsed["joints"]:
        child_joints.setdefault(joint["parent"], []).append(joint)

    poses: dict[str, list[float]] = {root: [0.0, 0.0, 0.0]}
    stack = [root]
    visited = {root}
    while stack:
        parent = stack.pop()
        base = poses[parent]
        for joint in child_joints.get(parent, []):
            child = joint["child"]
            if child in visited:
                continue
            xyz = joint["xyz"]
            poses[child] = [base[0] + xyz[0], base[1] + xyz[1], base[2] + xyz[2]]
            visited.add(child)
            stack.append(child)

    # any orphan links default to origin so they still render
    for name in link_names:
        poses.setdefault(name, [0.0, 0.0, 0.0])
    return poses


def stick_figure(urdf_text: str) -> dict[str, Any]:
    """Build a 2D (top-down XY) stick-figure overlay from URDF text.

    Returns nodes (one per link, with x/y in metres and a role) and segments
    (one per joint, base → child) so the canvas can draw simple sticks joining
    the base link to each wheel/sensor/child link.
    """
    parsed = parse_urdf(urdf_text)
    poses = link_poses(parsed)
    roles = {link["name"]: link["role"] for link in parsed["links"]}

    nodes = [
        {
            "link": name,
            "role": roles.get(name, "part"),
            "x": round(pos[0], 5),
            "y": round(pos[1], 5),
            "z": round(pos[2], 5),
        }
        for name, pos in poses.items()
    ]
    nodes.sort(key=lambda n: n["link"])

    segments = []
    for joint in parsed["joints"]:
        parent, child = joint["parent"], joint["child"]
        if parent not in poses or child not in poses:
            continue
        p, c = poses[parent], poses[child]
        segments.append({
            "joint": joint["name"],
            "type": joint["type"],
            "parent": parent,
            "child": child,
            "x1": round(p[0], 5),
            "y1": round(p[1], 5),
            "x2": round(c[0], 5),
            "y2": round(c[1], 5),
        })

    return {
        "robot": parsed["robot"],
        "nodes": nodes,
        "segments": segments,
        "link_count": len(nodes),
        "joint_count": len(parsed["joints"]),
    }


def _find_urdf(pkg_path: Path) -> Path | None:
    urdf_dir = pkg_path / "urdf"
    if urdf_dir.is_dir():
        preferred = urdf_dir / "robot.urdf"
        if preferred.is_file():
            return preferred
        for cand in sorted(urdf_dir.glob("*.urdf")):
            return cand
    for cand in sorted(pkg_path.rglob("*.urdf")):
        return cand
    return None


def package_stick_figure(package: str) -> dict[str, Any]:
    """Load a package's URDF and return its stick-figure overlay.

    Raises ``FileNotFoundError`` when the package has no URDF file.
    """
    pkg_path = resolve_package_path(package)
    urdf_file = _find_urdf(pkg_path)
    if urdf_file is None:
        raise FileNotFoundError(f"no URDF found in package {package}")
    result = stick_figure(urdf_file.read_text(encoding="utf-8"))
    result["package"] = pkg_path.name
    result["urdf"] = str(urdf_file)
    return result
