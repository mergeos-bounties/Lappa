"""Procedural 3D meshes (OBJ), auto-fit alignment, and URDF assembly for robot packages.

Supports full 3D workflows:
- generate / library meshes
- parse OBJ bounds and auto-fit scale/center to a target box
- attach visuals onto existing URDF links without duplicate-link corruption
- build an entire aligned multi-link robot (chassis + wheels + sensors)
- export a scene3d JSON consumed by the IDE WebGL viewer
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from lappa.config import WORKSPACES, ensure_dirs
from lappa.package_loader import load_package
from lappa.packager import resolve_package_path

MESH_PRESETS = {
    "box": {"description": "Axis-aligned box body"},
    "cylinder": {"description": "Vertical cylinder (wheel / pillar)"},
    "sphere": {"description": "Sphere"},
    "wheel": {"description": "Thin cylinder wheel (Y-axis spin)"},
    "chassis": {"description": "Mobile base plate (box)"},
    "tricycle_chassis": {"description": "Y-frame tricycle chassis with equipment deck"},
    "xe_tham_do_chassis": {"description": "0.40 x 0.26 x 0.15 m chassis from TUPM96/xe_tham_do"},
    "arm_link": {"description": "Elongated link for planar arm"},
    "lidar_dome": {"description": "Hemisphere sensor dome"},
}

# Default kinematic layout per demo kind (meters, ROS REP-103: x forward, y left, z up)
ROBOT_LAYOUTS: dict[str, dict[str, Any]] = {
    "diff_drive_2w": {
        "chassis": {"preset": "chassis", "size": [0.42, 0.30, 0.10], "xyz": [0.0, 0.0, 0.08]},
        "wheels": [
            {"name": "wheel_left", "xyz": [0.0, 0.16, 0.05], "radius": 0.05, "width": 0.03},
            {"name": "wheel_right", "xyz": [0.0, -0.16, 0.05], "radius": 0.05, "width": 0.03},
        ],
        "lidar": {"xyz": [0.05, 0.0, 0.16], "radius": 0.04},
    },
    "omni_3w": {
        "chassis": {"preset": "chassis", "size": [0.36, 0.36, 0.08], "xyz": [0.0, 0.0, 0.07]},
        "wheels": [
            {
                "name": "wheel_0",
                "xyz": [0.12, 0.0, 0.04],
                "radius": 0.04,
                "width": 0.025,
                "yaw": 0.0,
            },
            {
                "name": "wheel_1",
                "xyz": [-0.06, 0.104, 0.04],
                "radius": 0.04,
                "width": 0.025,
                "yaw": 2.094,
            },
            {
                "name": "wheel_2",
                "xyz": [-0.06, -0.104, 0.04],
                "radius": 0.04,
                "width": 0.025,
                "yaw": -2.094,
            },
        ],
        "lidar": {"xyz": [0.0, 0.0, 0.14], "radius": 0.035},
    },
    "tricycle_3w": {
        "chassis": {
            "preset": "xe_tham_do_chassis",
            "size": [0.40, 0.26, 0.15],
            "xyz": [0.0, 0.0, 0.14],
        },
        "wheels": [
            {
                "name": "wheel_steer",
                "xyz": [0.25, 0.0, 0.085],
                "radius": 0.085,
                "width": 0.055,
            },
            {
                "name": "wheel_rear_l",
                "xyz": [-0.13, 0.15, 0.10],
                "radius": 0.10,
                "width": 0.055,
            },
            {
                "name": "wheel_rear_r",
                "xyz": [-0.13, -0.15, 0.10],
                "radius": 0.10,
                "width": 0.055,
            },
        ],
        "lidar": {"xyz": [0.0, 0.0, 0.30], "radius": 0.045},
    },
    "ackermann_4w": {
        "chassis": {"preset": "chassis", "size": [0.50, 0.32, 0.12], "xyz": [0.0, 0.0, 0.09]},
        "wheels": [
            {"name": "wheel_fl", "xyz": [0.18, 0.14, 0.05], "radius": 0.05, "width": 0.03},
            {"name": "wheel_fr", "xyz": [0.18, -0.14, 0.05], "radius": 0.05, "width": 0.03},
            {"name": "wheel_rl", "xyz": [-0.18, 0.14, 0.05], "radius": 0.05, "width": 0.03},
            {"name": "wheel_rr", "xyz": [-0.18, -0.14, 0.05], "radius": 0.05, "width": 0.03},
        ],
        "lidar": {"xyz": [0.1, 0.0, 0.18], "radius": 0.04},
    },
    "simple_arm": {
        "chassis": {"preset": "box", "size": [0.12, 0.12, 0.06], "xyz": [0.0, 0.0, 0.03]},
        "links": [
            {
                "name": "link1",
                "preset": "arm_link",
                "length": 0.55,
                "thickness": 0.05,
                "xyz": [0.25, 0.0, 0.08],
            },
            {
                "name": "link2",
                "preset": "arm_link",
                "length": 0.45,
                "thickness": 0.04,
                "xyz": [0.70, 0.0, 0.08],
            },
        ],
        "wheels": [],
        "lidar": None,
    },
}


def list_presets() -> list[dict[str, str]]:
    return [{"id": k, **v} for k, v in MESH_PRESETS.items()]


def _obj_header(name: str) -> list[str]:
    return [f"# Lappa procedural mesh: {name}", f"o {name}"]


def _box(sx: float, sy: float, sz: float) -> tuple[list[str], dict]:
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    verts = [
        (-hx, -hy, -hz),
        (hx, -hy, -hz),
        (hx, hy, -hz),
        (-hx, hy, -hz),
        (-hx, -hy, hz),
        (hx, -hy, hz),
        (hx, hy, hz),
        (-hx, hy, hz),
    ]
    faces = [
        (1, 2, 3, 4),
        (5, 8, 7, 6),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 8, 4),
        (4, 8, 5, 1),
    ]
    lines = _obj_header("box")
    for v in verts:
        lines.append(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f}")
    for f in faces:
        lines.append("f " + " ".join(str(i) for i in f))
    return lines, {"kind": "box", "size": [sx, sy, sz], "vertices": len(verts)}


def _cylinder(
    radius: float,
    height: float,
    segments: int = 24,
    axis: str = "z",
) -> tuple[list[str], dict]:
    lines = _obj_header("cylinder")
    segs = max(8, min(segments, 64))
    verts: list[tuple[float, float, float]] = []
    h2 = height / 2

    def put(x: float, y: float, z: float) -> None:
        if axis == "y":
            verts.append((x, z, y))
        elif axis == "x":
            verts.append((z, y, x))
        else:
            verts.append((x, y, z))

    put(0, 0, -h2)
    put(0, 0, h2)
    for i in range(segs):
        a = 2 * math.pi * i / segs
        c, s = math.cos(a) * radius, math.sin(a) * radius
        put(c, s, -h2)
        put(c, s, h2)
    for v in verts:
        lines.append(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f}")
    for i in range(segs):
        b0 = 3 + i * 2
        b1 = 3 + ((i + 1) % segs) * 2
        t0 = b0 + 1
        t1 = b1 + 1
        lines.append(f"f 1 {b0} {b1}")
        lines.append(f"f 2 {t1} {t0}")
        lines.append(f"f {b0} {t0} {t1} {b1}")
    return lines, {
        "kind": "cylinder",
        "radius": radius,
        "height": height,
        "axis": axis,
        "vertices": len(verts),
    }


def _sphere(radius: float, segments: int = 16) -> tuple[list[str], dict]:
    lines = _obj_header("sphere")
    segs = max(8, min(segments, 32))
    verts: list[tuple[float, float, float]] = []
    for i in range(segs + 1):
        phi = math.pi * i / segs
        for j in range(segs):
            theta = 2 * math.pi * j / segs
            x = radius * math.sin(phi) * math.cos(theta)
            y = radius * math.sin(phi) * math.sin(theta)
            z = radius * math.cos(phi)
            verts.append((x, y, z))
    for v in verts:
        lines.append(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f}")
    for i in range(segs):
        for j in range(segs):
            a = i * segs + j + 1
            b = i * segs + (j + 1) % segs + 1
            c = (i + 1) * segs + (j + 1) % segs + 1
            d = (i + 1) * segs + j + 1
            lines.append(f"f {a} {b} {c} {d}")
    return lines, {"kind": "sphere", "radius": radius, "vertices": len(verts)}


def _chassis(length: float, width: float, height: float) -> tuple[list[str], dict]:
    return _box(length, width, height)


def _xe_tham_do_chassis(
    length: float,
    width: float,
    height: float,
) -> tuple[list[str], dict]:
    lines, meta = _box(length, width, height)
    meta.update(
        {
            "kind": "xe_tham_do_chassis",
            "source": "https://github.com/TUPM96/xe_tham_do",
        }
    )
    return lines, meta


def _tricycle_chassis(
    length: float,
    width: float,
    height: float,
) -> tuple[list[str], dict]:
    """Build a compact Y-frame inspired by full-size front-steer tricycles."""
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []

    def add_box(
        cx: float,
        cy: float,
        cz: float,
        sx: float,
        sy: float,
        sz: float,
        yaw: float = 0.0,
    ) -> None:
        hx, hy, hz = sx / 2, sy / 2, sz / 2
        cos_yaw, sin_yaw = math.cos(yaw), math.sin(yaw)
        first = len(vertices) + 1
        for local_x, local_y, local_z in (
            (-hx, -hy, -hz),
            (hx, -hy, -hz),
            (hx, hy, -hz),
            (-hx, hy, -hz),
            (-hx, -hy, hz),
            (hx, -hy, hz),
            (hx, hy, hz),
            (-hx, hy, hz),
        ):
            vertices.append(
                (
                    cx + local_x * cos_yaw - local_y * sin_yaw,
                    cy + local_x * sin_yaw + local_y * cos_yaw,
                    cz + local_z,
                )
            )
        for face in (
            (0, 1, 2, 3),
            (4, 7, 6, 5),
            (0, 4, 5, 1),
            (1, 5, 6, 2),
            (2, 6, 7, 3),
            (3, 7, 4, 0),
        ):
            faces.append(tuple(first + index for index in face))

    def add_beam(
        start: tuple[float, float],
        end: tuple[float, float],
        beam_width: float,
        z: float,
        beam_height: float,
    ) -> None:
        dx, dy = end[0] - start[0], end[1] - start[1]
        add_box(
            (start[0] + end[0]) / 2,
            (start[1] + end[1]) / 2,
            z,
            math.hypot(dx, dy),
            beam_width,
            beam_height,
            math.atan2(dy, dx),
        )

    rail_height = height * 0.28
    rail_z = -height * 0.24
    add_box(0.015, 0.0, rail_z, length * 0.82, width * 0.13, rail_height)
    add_box(-length * 0.30, 0.0, rail_z, length * 0.12, width * 0.94, rail_height)
    add_beam(
        (-length * 0.31, width * 0.39),
        (length * 0.34, width * 0.09),
        width * 0.11,
        rail_z,
        rail_height,
    )
    add_beam(
        (-length * 0.31, -width * 0.39),
        (length * 0.34, -width * 0.09),
        width * 0.11,
        rail_z,
        rail_height,
    )

    # A narrow electronics tray keeps the structural Y rails visible.
    add_box(-length * 0.06, 0.0, 0.0, length * 0.42, width * 0.42, height * 0.18)
    add_box(-length * 0.17, 0.0, height * 0.25, length * 0.25, width * 0.42, height * 0.28)
    add_box(length * 0.40, 0.0, height * 0.03, length * 0.14, width * 0.28, height * 0.55)

    lines = _obj_header("tricycle_chassis")
    lines.extend(f"v {x:.5f} {y:.5f} {z:.5f}" for x, y, z in vertices)
    lines.extend("f " + " ".join(str(index) for index in face) for face in faces)
    return lines, {
        "kind": "tricycle_chassis",
        "size": [length, width, height],
        "vertices": len(vertices),
        "components": 7,
    }


def _arm_link(length: float, thickness: float) -> tuple[list[str], dict]:
    return _box(length, thickness, thickness)


def _lidar_dome(radius: float, segments: int = 16) -> tuple[list[str], dict]:
    lines = _obj_header("lidar_dome")
    segs = max(8, min(segments, 32))
    verts: list[tuple[float, float, float]] = [(0, 0, 0)]
    rings = max(4, segs // 2)
    for i in range(1, rings + 1):
        phi = (math.pi / 2) * i / rings
        for j in range(segs):
            theta = 2 * math.pi * j / segs
            x = radius * math.sin(phi) * math.cos(theta)
            y = radius * math.sin(phi) * math.sin(theta)
            z = radius * math.cos(phi)
            verts.append((x, y, max(0.0, z)))
    for v in verts:
        lines.append(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f}")
    for j in range(segs):
        a = 2 + j
        b = 2 + (j + 1) % segs
        lines.append(f"f 1 {a} {b}")
    return lines, {"kind": "lidar_dome", "radius": radius, "vertices": len(verts)}


def generate_mesh(
    preset: str,
    *,
    sx: float = 0.4,
    sy: float = 0.3,
    sz: float = 0.15,
    radius: float = 0.08,
    height: float = 0.05,
    length: float = 0.5,
    thickness: float = 0.06,
    segments: int = 24,
) -> tuple[str, dict[str, Any]]:
    p = (preset or "box").lower()
    if p not in MESH_PRESETS:
        raise ValueError(f"unknown preset {preset}; choose {list(MESH_PRESETS)}")
    if p == "box":
        lines, meta = _box(sx, sy, sz)
    elif p == "cylinder":
        lines, meta = _cylinder(radius, height, segments, axis="z")
    elif p == "sphere":
        lines, meta = _sphere(radius, segments)
    elif p == "wheel":
        lines, meta = _cylinder(radius, height, segments, axis="y")
    elif p == "chassis":
        lines, meta = _chassis(sx, sy, sz)
    elif p == "tricycle_chassis":
        lines, meta = _tricycle_chassis(sx, sy, sz)
    elif p == "xe_tham_do_chassis":
        lines, meta = _xe_tham_do_chassis(sx, sy, sz)
    elif p == "arm_link":
        lines, meta = _arm_link(length, thickness)
    elif p == "lidar_dome":
        lines, meta = _lidar_dome(radius, segments)
    else:
        lines, meta = _box(sx, sy, sz)
    meta = {**meta, "preset": p}
    return "\n".join(lines) + "\n", meta


# ---------- OBJ parse / fit ----------


def parse_obj_vertices(obj_text: str) -> list[tuple[float, float, float]]:
    verts: list[tuple[float, float, float]] = []
    for line in obj_text.splitlines():
        if line.startswith("v "):
            parts = line.split()
            if len(parts) >= 4:
                try:
                    verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
                except ValueError:
                    continue
    return verts


def mesh_bounds(obj_text: str) -> dict[str, Any]:
    verts = parse_obj_vertices(obj_text)
    if not verts:
        return {
            "min": [0.0, 0.0, 0.0],
            "max": [0.0, 0.0, 0.0],
            "center": [0.0, 0.0, 0.0],
            "size": [0.0, 0.0, 0.0],
            "vertices": 0,
        }
    xs, ys, zs = zip(*verts)
    mn = [min(xs), min(ys), min(zs)]
    mx = [max(xs), max(ys), max(zs)]
    center = [(mn[i] + mx[i]) / 2 for i in range(3)]
    size = [mx[i] - mn[i] for i in range(3)]
    return {"min": mn, "max": mx, "center": center, "size": size, "vertices": len(verts)}


def transform_obj(
    obj_text: str,
    *,
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
    translate: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> str:
    """Scale then translate vertex positions in OBJ text."""
    out: list[str] = []
    sx, sy, sz = scale
    tx, ty, tz = translate
    for line in obj_text.splitlines():
        if line.startswith("v "):
            parts = line.split()
            if len(parts) >= 4:
                try:
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    x = x * sx + tx
                    y = y * sy + ty
                    z = z * sz + tz
                    out.append(f"v {x:.6f} {y:.6f} {z:.6f}")
                    continue
                except ValueError:
                    pass
        out.append(line)
    return "\n".join(out) + ("\n" if not obj_text.endswith("\n") else "")


def fit_obj_to_box(
    obj_text: str,
    target_size: tuple[float, float, float],
    *,
    center: bool = True,
    uniform: bool = False,
) -> tuple[str, dict[str, Any]]:
    """
    Scale mesh so its AABB matches target_size (and optionally center at origin).

    Returns fitted OBJ text + fit report (scales, bounds before/after).
    """
    before = mesh_bounds(obj_text)
    size = before["size"]
    scales = []
    for i in range(3):
        if size[i] < 1e-9:
            scales.append(1.0)
        else:
            scales.append(float(target_size[i]) / float(size[i]))
    if uniform:
        s = min(s for s in scales if s > 0) if any(s > 0 for s in scales) else 1.0
        scales = [s, s, s]
    # center first (translate by -center * scale after scale: apply scale then -center*scale)
    cx, cy, cz = before["center"]
    if center:
        # v' = (v - center) * scale
        # = v*scale - center*scale
        translate = (-cx * scales[0], -cy * scales[1], -cz * scales[2])
    else:
        translate = (0.0, 0.0, 0.0)
    fitted = transform_obj(obj_text, scale=(scales[0], scales[1], scales[2]), translate=translate)
    after = mesh_bounds(fitted)
    report = {
        "before": before,
        "after": after,
        "scale": scales,
        "target_size": list(target_size),
        "uniform": uniform,
        "centered": center,
    }
    return fitted, report


def _library_dir() -> Path:
    ensure_dirs()
    d = WORKSPACES / "meshes_library"
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_model(
    preset: str,
    name: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    obj_text, meta = generate_mesh(preset, **kwargs)
    mid = name or f"{preset}_{meta.get('kind', 'mesh')}"
    mid = re.sub(r"[^\w\-]+", "_", mid)
    path = _library_dir() / f"{mid}.obj"
    path.write_text(obj_text, encoding="utf-8")
    bounds = mesh_bounds(obj_text)
    meta = {**meta, "bounds": bounds}
    meta_path = _library_dir() / f"{mid}.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "id": mid,
        "obj_path": str(path),
        "meta_path": str(meta_path),
        "meta": meta,
        "bounds": bounds,
        "bytes": path.stat().st_size,
    }


def fit_library_model(
    model_id: str,
    target_size: list[float] | tuple[float, float, float],
    *,
    uniform: bool = False,
    save_as: str | None = None,
) -> dict[str, Any]:
    """Auto-fit a library mesh to a target AABB; write back (or save_as)."""
    lib = _library_dir()
    src = lib / f"{model_id}.obj"
    if not src.is_file():
        raise FileNotFoundError(f"model {model_id} not in library")
    text = src.read_text(encoding="utf-8")
    fitted, report = fit_obj_to_box(
        text,
        (float(target_size[0]), float(target_size[1]), float(target_size[2])),
        center=True,
        uniform=uniform,
    )
    out_id = save_as or f"{model_id}_fit"
    out_id = re.sub(r"[^\w\-]+", "_", out_id)
    out = lib / f"{out_id}.obj"
    out.write_text(fitted, encoding="utf-8")
    meta = {
        "preset": "fitted",
        "source": model_id,
        "fit": report,
        "bounds": report["after"],
    }
    (lib / f"{out_id}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "id": out_id,
        "obj_path": str(out),
        "meta": meta,
        "fit": report,
        "bytes": out.stat().st_size,
    }


def list_library() -> list[dict[str, Any]]:
    root = _library_dir()
    out = []
    for p in sorted(root.glob("*.obj")):
        meta_p = p.with_suffix(".json")
        meta: dict[str, Any] = {}
        if meta_p.is_file():
            try:
                meta = json.loads(meta_p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        if "bounds" not in meta:
            meta["bounds"] = mesh_bounds(p.read_text(encoding="utf-8"))
        out.append(
            {
                "id": p.stem,
                "obj_path": str(p),
                "meta": meta,
                "bounds": meta.get("bounds"),
                "bytes": p.stat().st_size,
            }
        )
    return out


def get_model_obj(model_id: str) -> str:
    path = _library_dir() / f"{model_id}.obj"
    if not path.is_file():
        raise FileNotFoundError(f"model {model_id} not found")
    return path.read_text(encoding="utf-8")


# ---------- URDF helpers ----------


def _fmt_xyz(xyz: tuple[float, float, float] | list[float] | str) -> str:
    if isinstance(xyz, str):
        return xyz.strip()
    return f"{float(xyz[0]):.5f} {float(xyz[1]):.5f} {float(xyz[2]):.5f}"


def _fmt_rpy(rpy: tuple[float, float, float] | list[float] | str) -> str:
    if isinstance(rpy, str):
        return rpy.strip()
    return f"{float(rpy[0]):.5f} {float(rpy[1]):.5f} {float(rpy[2]):.5f}"


def _fmt_scale(scale: tuple[float, float, float] | list[float] | str) -> str:
    if isinstance(scale, str):
        return scale.strip()
    return f"{float(scale[0]):.5f} {float(scale[1]):.5f} {float(scale[2]):.5f}"


def _visual_collision_block(
    mesh_uri: str,
    xyz: str,
    rpy: str,
    scale: str,
    rgba: str = "0.2 0.55 0.95 1",
) -> str:
    return f"""    <visual>
      <origin xyz="{xyz}" rpy="{rpy}"/>
      <geometry>
        <mesh filename="{mesh_uri}" scale="{scale}"/>
      </geometry>
      <material name="lappa_mesh">
        <color rgba="{rgba}"/>
      </material>
    </visual>
    <collision>
      <origin xyz="{xyz}" rpy="{rpy}"/>
      <geometry>
        <mesh filename="{mesh_uri}" scale="{scale}"/>
      </geometry>
    </collision>
"""


def _link_block(
    link_name: str,
    mesh_uri: str,
    xyz: str = "0 0 0",
    rpy: str = "0 0 0",
    scale: str = "1 1 1",
    rgba: str = "0.2 0.55 0.95 1",
) -> str:
    return (
        f'  <link name="{link_name}">\n'
        + _visual_collision_block(mesh_uri, xyz, rpy, scale, rgba)
        + "  </link>\n"
    )


def _fixed_joint(name: str, parent: str, child: str, xyz: str, rpy: str = "0 0 0") -> str:
    return f"""  <joint name="{name}" type="fixed">
    <parent link="{parent}"/>
    <child link="{child}"/>
    <origin xyz="{xyz}" rpy="{rpy}"/>
  </joint>
"""


def _continuous_joint(
    name: str,
    parent: str,
    child: str,
    xyz: str,
    rpy: str = "0 0 0",
    axis: str = "0 1 0",
) -> str:
    return f"""  <joint name="{name}" type="continuous">
    <parent link="{parent}"/>
    <child link="{child}"/>
    <origin xyz="{xyz}" rpy="{rpy}"/>
    <axis xyz="{axis}"/>
  </joint>
"""


def write_robot_urdf(
    package_name: str,
    links_and_joints_xml: str,
    urdf_path: Path,
) -> Path:
    urdf_path.parent.mkdir(parents=True, exist_ok=True)
    body = f"""<?xml version="1.0"?>
<!-- Lappa aligned 3D robot - package {package_name} -->
<robot name="{package_name}">
{links_and_joints_xml}
</robot>
"""
    urdf_path.write_text(body, encoding="utf-8")
    return urdf_path


def sanitize_urdf(urdf_text: str) -> str:
    """Remove BOM and legacy Lappa attach spam (duplicate base_link_mesh links)."""
    text = urdf_text.lstrip("\ufeff")
    # drop every base_link_mesh block (old broken attach path)
    text = re.sub(
        r'\s*<link\s+name="base_link_mesh"\s*>.*?</link>\s*',
        "\n",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # collapse multiple empty base_link stubs into one handled by upsert
    empty_base = list(re.finditer(r'<link\s+name="base_link"\s*/\s*>', text)) + list(
        re.finditer(r'<link\s+name="base_link"\s*>\s*</link>', text)
    )
    if len(empty_base) > 1:
        for m in empty_base[1:]:
            text = text[: m.start()] + text[m.end() :]
    return text


def upsert_link_visual(
    urdf_text: str,
    link_name: str,
    mesh_uri: str,
    xyz: str,
    rpy: str,
    scale: str,
) -> str:
    """Replace or insert visual/collision for an existing link; create link if missing."""
    urdf_text = sanitize_urdf(urdf_text)
    link_re = re.compile(
        rf'(<link\s+name="{re.escape(link_name)}"\s*>)(.*?)(</link>)',
        re.DOTALL,
    )
    vc = _visual_collision_block(mesh_uri, xyz, rpy, scale)
    m = link_re.search(urdf_text)
    if m:
        # strip old visual/collision inside this link
        inner = m.group(2)
        inner = re.sub(r"<visual\b.*?</visual>\s*", "", inner, flags=re.DOTALL)
        inner = re.sub(r"<collision\b.*?</collision>\s*", "", inner, flags=re.DOTALL)
        new_inner = "\n" + vc + inner
        return urdf_text[: m.start()] + m.group(1) + new_inner + m.group(3) + urdf_text[m.end() :]
    # self-closing empty link → expand
    sc = re.search(rf'<link\s+name="{re.escape(link_name)}"\s*/\s*>', urdf_text)
    if sc:
        block = _link_block(link_name, mesh_uri, xyz, rpy, scale)
        return urdf_text[: sc.start()] + block + urdf_text[sc.end() :]
    # append new link before </robot>
    block = _link_block(link_name, mesh_uri, xyz, rpy, scale)
    if "</robot>" in urdf_text:
        return urdf_text.replace("</robot>", block + "</robot>")
    return urdf_text + "\n" + block


def attach_model_to_package(
    package: str,
    model_id: str,
    link_name: str = "base_link",
    xyz: str = "0 0 0",
    rpy: str = "0 0 0",
    scale: str = "1 1 1",
    *,
    auto_fit: bool = True,
    target_size: list[float] | None = None,
    replace: bool = True,
) -> dict[str, Any]:
    """
    Copy mesh into package meshes/ and attach as visual on ``link_name``.

    When auto_fit=True, scales the mesh so its AABB matches target_size
    (default 0.4×0.3×0.12) and centers origin — then attaches with unit scale.
    """
    pkg_path = resolve_package_path(package)
    lib = _library_dir()
    obj = lib / f"{model_id}.obj"
    if not obj.is_file():
        raise FileNotFoundError(f"model {model_id} not in library — create_model first")

    obj_text = obj.read_text(encoding="utf-8")
    fit_report: dict[str, Any] | None = None
    if auto_fit:
        ts = target_size or [0.4, 0.3, 0.12]
        obj_text, fit_report = fit_obj_to_box(
            obj_text,
            (float(ts[0]), float(ts[1]), float(ts[2])),
            center=True,
            uniform=False,
        )
        scale = "1 1 1"
        # mesh already centered; keep xyz as link offset
    else:
        # still center mesh at origin so xyz is meaningful
        b = mesh_bounds(obj_text)
        cx, cy, cz = b["center"]
        if abs(cx) + abs(cy) + abs(cz) > 1e-6:
            obj_text = transform_obj(obj_text, translate=(-cx, -cy, -cz))

    meshes = pkg_path / "meshes"
    meshes.mkdir(parents=True, exist_ok=True)
    dest = meshes / f"{model_id}.obj"
    dest.write_text(obj_text, encoding="utf-8")
    bounds = mesh_bounds(obj_text)
    meta = {"model_id": model_id, "bounds": bounds, "fit": fit_report}
    (meshes / f"{model_id}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    urdf_dir = pkg_path / "urdf"
    urdf_dir.mkdir(parents=True, exist_ok=True)
    urdf_path = urdf_dir / "robot.urdf"
    pkg = load_package(pkg_path)
    mesh_uri = f"package://{pkg.name}/meshes/{model_id}.obj"
    xyz_s, rpy_s, scale_s = _fmt_xyz(xyz), _fmt_rpy(rpy), _fmt_scale(scale)

    if urdf_path.is_file() and replace:
        text = urdf_path.read_text(encoding="utf-8")
        # strip BOM / junk duplicate empty links of same name later via upsert
        if f'name="{link_name}"' not in text:
            # ensure base skeleton
            if "</robot>" not in text:
                text = f'<?xml version="1.0"?>\n<robot name="{pkg.name}">\n</robot>\n'
        text = upsert_link_visual(text, link_name, mesh_uri, xyz_s, rpy_s, scale_s)
        urdf_path.write_text(text, encoding="utf-8")
    else:
        write_robot_urdf(
            pkg.name,
            _link_block(link_name, mesh_uri, xyz_s, rpy_s, scale_s),
            urdf_path,
        )

    # attachment registry (dedupe by link)
    reg = pkg_path / "meshes" / "attachments.json"
    attachments: list[dict[str, Any]] = []
    if reg.is_file():
        try:
            attachments = json.loads(reg.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            attachments = []
    entry = {
        "model_id": model_id,
        "link": link_name,
        "mesh": f"meshes/{model_id}.obj",
        "xyz": xyz_s,
        "rpy": rpy_s,
        "scale": scale_s,
        "auto_fit": auto_fit,
        "bounds": bounds,
    }
    attachments = [a for a in attachments if a.get("link") != link_name]
    attachments.append(entry)
    reg.write_text(json.dumps(attachments, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "package": pkg.name,
        "package_path": str(pkg_path),
        "mesh": str(dest),
        "urdf": str(urdf_path),
        "attachment": entry,
        "attachments": attachments,
        "fit": fit_report,
        "bounds": bounds,
    }


def package_attachments(package: str) -> list[dict[str, Any]]:
    pkg_path = resolve_package_path(package)
    reg = pkg_path / "meshes" / "attachments.json"
    if not reg.is_file():
        return []
    try:
        return json.loads(reg.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def build_aligned_robot(package: str, kind: str | None = None) -> dict[str, Any]:
    """
    Generate a complete multi-link robot with chassis + wheels (+ lidar) meshes
    placed at correct kinematic offsets for the demo kind.
    """
    pkg_path = resolve_package_path(package)
    pkg = load_package(pkg_path)
    layout_key = kind or package
    layout = ROBOT_LAYOUTS.get(layout_key) or ROBOT_LAYOUTS["diff_drive_2w"]

    meshes = pkg_path / "meshes"
    meshes.mkdir(parents=True, exist_ok=True)
    xml_parts: list[str] = []
    attachments: list[dict[str, Any]] = []
    created: list[str] = []

    # --- chassis as base_link ---
    ch = layout["chassis"]
    sx, sy, sz = ch["size"]
    chassis = create_model(
        ch.get("preset", "chassis"),
        name=f"{pkg.name}_chassis",
        sx=sx,
        sy=sy,
        sz=sz,
    )
    # mesh already sized; center at 0; URDF origin lifts chassis center to xyz
    obj_text = Path(chassis["obj_path"]).read_text(encoding="utf-8")
    dest = meshes / f"{chassis['id']}.obj"
    dest.write_text(obj_text, encoding="utf-8")
    mesh_uri = f"package://{pkg.name}/meshes/{chassis['id']}.obj"
    # visual origin 0 inside link; joint/base placement via z of chassis center
    cz = float(ch["xyz"][2])
    xml_parts.append(_link_block("base_link", mesh_uri, xyz="0 0 0", scale="1 1 1"))
    # lift whole robot so wheels sit on z=0 ground: chassis center at cz
    # (we bake ground by putting wheel centers at z=radius)
    attachments.append(
        {
            "model_id": chassis["id"],
            "link": "base_link",
            "mesh": f"meshes/{chassis['id']}.obj",
            "xyz": "0 0 0",
            "rpy": "0 0 0",
            "scale": "1 1 1",
            "role": "chassis",
        }
    )
    created.append(chassis["id"])

    # optional dummy world origin offset via base_footprint
    xml_parts.insert(
        0,
        f"""  <link name="base_footprint"/>
  <joint name="base_joint" type="fixed">
    <parent link="base_footprint"/>
    <child link="base_link"/>
    <origin xyz="0 0 {cz:.5f}" rpy="0 0 0"/>
  </joint>
""",
    )

    # --- wheels ---
    for w in layout.get("wheels") or []:
        radius = float(w.get("radius", 0.05))
        width = float(w.get("width", 0.03))
        wname = str(w["name"])
        wheel = create_model(
            "wheel",
            name=f"{pkg.name}_{wname}",
            radius=radius,
            height=width,
            segments=28,
        )
        w_obj = Path(wheel["obj_path"]).read_text(encoding="utf-8")
        w_dest = meshes / f"{wheel['id']}.obj"
        w_dest.write_text(w_obj, encoding="utf-8")
        w_uri = f"package://{pkg.name}/meshes/{wheel['id']}.obj"
        wx, wy, wz = (float(v) for v in w["xyz"])
        yaw = float(w.get("yaw", 0.0))
        # wheel mesh axis=Y; for steered wheels rotate about Z
        rpy = f"0 0 {yaw:.5f}"
        xml_parts.append(
            _link_block(
                wname, w_uri, xyz="0 0 0", rpy="0 0 0", scale="1 1 1", rgba="0.15 0.15 0.18 1"
            )
        )
        xml_parts.append(
            _continuous_joint(
                f"{wname}_joint",
                "base_link",
                wname,
                xyz=f"{wx:.5f} {wy:.5f} {wz - cz:.5f}",
                rpy=rpy,
                axis="0 1 0",
            )
        )
        attachments.append(
            {
                "model_id": wheel["id"],
                "link": wname,
                "mesh": f"meshes/{wheel['id']}.obj",
                "xyz": f"{wx:.5f} {wy:.5f} {wz - cz:.5f}",
                "rpy": rpy,
                "scale": "1 1 1",
                "role": "wheel",
                "radius": radius,
            }
        )
        created.append(wheel["id"])

    # --- arm links (simple_arm) ---
    for link in layout.get("links") or []:
        length = float(link.get("length", 0.5))
        thickness = float(link.get("thickness", 0.05))
        lname = str(link["name"])
        al = create_model(
            link.get("preset", "arm_link"),
            name=f"{pkg.name}_{lname}",
            length=length,
            thickness=thickness,
        )
        a_obj = Path(al["obj_path"]).read_text(encoding="utf-8")
        (meshes / f"{al['id']}.obj").write_text(a_obj, encoding="utf-8")
        a_uri = f"package://{pkg.name}/meshes/{al['id']}.obj"
        lx, ly, lz = (float(v) for v in link["xyz"])
        xml_parts.append(_link_block(lname, a_uri, rgba="0.64 0.44 0.97 1"))
        xml_parts.append(
            _fixed_joint(
                f"{lname}_joint", "base_link", lname, xyz=f"{lx:.5f} {ly:.5f} {lz - cz:.5f}"
            )
        )
        attachments.append(
            {
                "model_id": al["id"],
                "link": lname,
                "mesh": f"meshes/{al['id']}.obj",
                "xyz": f"{lx:.5f} {ly:.5f} {lz - cz:.5f}",
                "rpy": "0 0 0",
                "scale": "1 1 1",
                "role": "arm_link",
            }
        )
        created.append(al["id"])

    # --- lidar ---
    lidar = layout.get("lidar")
    if lidar:
        ld = create_model(
            "lidar_dome",
            name=f"{pkg.name}_lidar",
            radius=float(lidar.get("radius", 0.04)),
            segments=20,
        )
        l_obj = Path(ld["obj_path"]).read_text(encoding="utf-8")
        (meshes / f"{ld['id']}.obj").write_text(l_obj, encoding="utf-8")
        l_uri = f"package://{pkg.name}/meshes/{ld['id']}.obj"
        lx, ly, lz = (float(v) for v in lidar["xyz"])
        xml_parts.append(_link_block("lidar_link", l_uri, rgba="0.95 0.55 0.2 1"))
        xml_parts.append(
            _fixed_joint(
                "lidar_joint",
                "base_link",
                "lidar_link",
                xyz=f"{lx:.5f} {ly:.5f} {lz - cz:.5f}",
            )
        )
        attachments.append(
            {
                "model_id": ld["id"],
                "link": "lidar_link",
                "mesh": f"meshes/{ld['id']}.obj",
                "xyz": f"{lx:.5f} {ly:.5f} {lz - cz:.5f}",
                "rpy": "0 0 0",
                "scale": "1 1 1",
                "role": "lidar",
            }
        )
        created.append(ld["id"])

    urdf_path = write_robot_urdf(pkg.name, "\n".join(xml_parts), pkg_path / "urdf" / "robot.urdf")
    reg = meshes / "attachments.json"
    reg.write_text(json.dumps(attachments, indent=2), encoding="utf-8")

    scene = package_scene3d(package)
    return {
        "ok": True,
        "package": pkg.name,
        "kind": layout_key,
        "urdf": str(urdf_path),
        "models": created,
        "attachments": attachments,
        "scene": scene,
        "links": len(attachments) + 1,
    }


def _resolve_mesh_file(pkg_path: Path, mesh_rel_or_uri: str) -> Path | None:
    rel = mesh_rel_or_uri
    if "meshes/" in rel:
        rel = rel[rel.index("meshes/") :]
    rel = rel.replace("package://", "")
    # strip package name prefix if present
    if "/" in rel and not rel.startswith("meshes/"):
        # package://name/meshes/foo.obj
        parts = rel.split("/", 1)
        rel = parts[1] if len(parts) > 1 else rel
    cand = pkg_path / rel
    if cand.is_file():
        return cand
    # bare filename
    cand2 = pkg_path / "meshes" / Path(mesh_rel_or_uri).name
    if cand2.is_file():
        return cand2
    return None


def package_scene3d(package: str) -> dict[str, Any]:
    """
    Build a Three.js-friendly scene description for the package.

    Each node: link, mesh_url (API path), local xyz/rpy/scale, role, color.
    """
    pkg_path = resolve_package_path(package)
    pkg = load_package(pkg_path)
    attachments = package_attachments(package)
    nodes: list[dict[str, Any]] = []

    if not attachments:
        # try parse URDF mesh references
        urdf = pkg_path / "urdf" / "robot.urdf"
        if urdf.is_file():
            text = urdf.read_text(encoding="utf-8")
            for m in re.finditer(
                r'<link\s+name="([^"]+)"[^>]*>.*?<mesh\s+filename="([^"]+)"(?:\s+scale="([^"]+)")?',
                text,
                re.DOTALL,
            ):
                link, filename, scale = m.group(1), m.group(2), m.group(3) or "1 1 1"
                mesh_file = _resolve_mesh_file(pkg_path, filename)
                if not mesh_file:
                    continue
                nodes.append(
                    {
                        "link": link,
                        "parent": "base_link" if link != "base_link" else None,
                        "mesh": f"meshes/{mesh_file.name}",
                        "mesh_url": f"/api/packages/{pkg.name}/mesh/{mesh_file.name}",
                        "xyz": [0.0, 0.0, 0.0],
                        "rpy": [0.0, 0.0, 0.0],
                        "scale": [float(x) for x in scale.split()],
                        "role": "unknown",
                        "bounds": mesh_bounds(mesh_file.read_text(encoding="utf-8")),
                    }
                )
    else:
        for a in attachments:
            mesh_rel = a.get("mesh") or f"meshes/{a.get('model_id')}.obj"
            mesh_file = _resolve_mesh_file(pkg_path, str(mesh_rel))
            xyz = [float(x) for x in str(a.get("xyz", "0 0 0")).split()]
            rpy = [float(x) for x in str(a.get("rpy", "0 0 0")).split()]
            scale = [float(x) for x in str(a.get("scale", "1 1 1")).split()]
            while len(xyz) < 3:
                xyz.append(0.0)
            while len(rpy) < 3:
                rpy.append(0.0)
            while len(scale) < 3:
                scale.append(1.0)
            fname = mesh_file.name if mesh_file else Path(str(mesh_rel)).name
            bounds = (
                mesh_bounds(mesh_file.read_text(encoding="utf-8"))
                if mesh_file and mesh_file.is_file()
                else a.get("bounds")
            )
            role = a.get("role") or ("chassis" if a.get("link") == "base_link" else "part")
            nodes.append(
                {
                    "link": a.get("link"),
                    "parent": None if a.get("link") == "base_link" else "base_link",
                    "mesh": f"meshes/{fname}",
                    "mesh_url": f"/api/packages/{pkg.name}/mesh/{fname}",
                    "xyz": xyz,
                    "rpy": rpy,
                    "scale": scale,
                    "role": role,
                    "bounds": bounds,
                    "model_id": a.get("model_id"),
                }
            )

    return {
        "package": pkg.name,
        "package_path": str(pkg_path),
        "frame": "base_footprint",
        "up": [0, 0, 1],
        "forward": [1, 0, 0],
        "nodes": nodes,
        "count": len(nodes),
    }


def read_package_mesh(package: str, filename: str) -> Path:
    pkg_path = resolve_package_path(package)
    safe = Path(filename).name
    path = pkg_path / "meshes" / safe
    if not path.is_file():
        raise FileNotFoundError(f"mesh {safe} not in package {package}")
    return path
