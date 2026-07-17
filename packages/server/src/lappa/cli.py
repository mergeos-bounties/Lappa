from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from lappa import (
    __version__,
    docker_bridge,
    models3d,
    packager,
    ros2_versions,
    workspace as workspace_store,
)
from lappa.config import DEMOS_ROOT, ensure_dirs
from lappa.package_loader import list_demo_packages
from lappa.sim.session import SESSION

app = typer.Typer(help="Lappa — ROS2 package IDE server CLI", no_args_is_help=True)
workspace_app = typer.Typer(help="Workspace / package")
demos_app = typer.Typer(help="Demo robots")
sim_app = typer.Typer(help="Native / docker sim")
docker_app = typer.Typer(help="Docker show mode")
ros2_app = typer.Typer(help="ROS2 distro selection")
pkg_app = typer.Typer(help="Bundle / package ROS2 pkgs")
model_app = typer.Typer(help="Procedural 3D meshes")
path_app = typer.Typer(help="Path fixture tools")
app.add_typer(workspace_app, name="workspace")
app.add_typer(demos_app, name="demos")
app.add_typer(sim_app, name="sim")
app.add_typer(docker_app, name="docker")
app.add_typer(ros2_app, name="ros2")
app.add_typer(pkg_app, name="package")
app.add_typer(model_app, name="model")
app.add_typer(path_app, name="path")
console = Console()


def _path_points_from_fixture(path: Path) -> list[tuple[float, float]]:
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise typer.BadParameter(f"could not read fixture: {exc}", param_hint="--file") from exc
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"invalid JSON fixture: {exc}", param_hint="--file") from exc

    points = data.get("points") if isinstance(data, dict) else None
    if not isinstance(points, list) or len(points) < 2:
        raise typer.BadParameter("fixture must contain at least two points", param_hint="--file")

    parsed: list[tuple[float, float]] = []
    for index, point in enumerate(points):
        if not isinstance(point, list | tuple) or len(point) < 2:
            raise typer.BadParameter(f"point {index} must contain x and y", param_hint="--file")
        try:
            parsed.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError) as exc:
            raise typer.BadParameter(
                f"point {index} x/y values must be numeric", param_hint="--file"
            ) from exc
    return parsed


def _path_stats(points: list[tuple[float, float]]) -> dict[str, float | int]:
    length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))
    net = math.hypot(points[-1][0] - points[0][0], points[-1][1] - points[0][1])
    return {
        "points": len(points),
        "path_length_m": round(length, 4),
        "net_displacement_m": round(net, 4),
    }


def _resample(
    points: list[tuple[float, float]], step_m: float
) -> list[tuple[float, float]]:
    """Resample a polyline at fixed step meters.

    Walks along each segment inserting points every *step_m*.
    The first and last original points are always included.
    """
    if step_m <= 0:
        raise ValueError("step_m must be positive")
    if len(points) < 2:
        return list(points)

    result: list[tuple[float, float]] = [points[0]]
    remaining = 0.0

    def _maybe_append(pt: tuple[float, float]) -> None:
        """Append pt if it differs from the last point."""
        last = result[-1]
        if abs(pt[0] - last[0]) > 1e-12 or abs(pt[1] - last[1]) > 1e-12:
            result.append(pt)

    for a, b in zip(points, points[1:]):
        seg_x = b[0] - a[0]
        seg_y = b[1] - a[1]
        seg_len = math.hypot(seg_x, seg_y)
        if seg_len < 1e-12:
            continue

        # Walk from the first step boundary along this segment
        dist = step_m - remaining if remaining > 0 else step_m
        while dist < seg_len + 1e-12:
            t = min(dist / seg_len, 1.0) if seg_len > 0 else 0.0
            _maybe_append((a[0] + t * seg_x, a[1] + t * seg_y))
            dist += step_m
        remaining = dist - seg_len

    # Ensure last point is included
    _maybe_append(points[-1])

    return result


@app.command("version")
def version_cmd() -> None:
    rprint({"version": __version__})


@app.command("gui")
def gui_cmd() -> None:
    """Launch modern Qt desktop shell (pip install -e '.[gui]')."""
    from lappa.gui.app import main as gui_main

    raise SystemExit(gui_main())


@app.command("demo")
def demo_cmd() -> None:
    """Offline smoke: sim engines + ROS2 version + bundle + 3D mesh attach."""
    ensure_dirs()
    packs = list_demo_packages(DEMOS_ROOT)
    rprint({"demos": len(packs), "names": [p.name for p in packs]})
    for p in packs:
        SESSION.start(p.name, p.path)
        SESSION.cmd(linear_x=0.4, linear_y=0.2, angular_z=0.2)
        for _ in range(5):
            time.sleep(0.05)
            SESSION.tick()
        st = SESSION.tick()
        rprint(f"  {p.name}: x={st.get('x')} y={st.get('y')} theta={st.get('theta')}")
        SESSION.stop()
    # ROS2 versions
    sel = ros2_versions.get_selected()
    rprint({"ros2_selected": sel.get("id"), "docker_image": sel.get("docker_image")})
    ros2_versions.set_selected("jazzy")
    rprint({"switched_to": ros2_versions.get_selected()["id"]})
    ros2_versions.set_selected(sel.get("id") or "humble")
    docker_bridge.apply_ros2_dockerfile()
    # packager
    bundle = packager.package_bundle(["diff_drive_2w", "omni_3w"], distro="humble")
    rprint({"bundle": bundle["filename"], "size": bundle["size_bytes"]})
    # Full aligned 3D robot (chassis + wheels + lidar fitted)
    built = models3d.build_aligned_robot("diff_drive_2w")
    rprint(
        {
            "3d_robot": built["package"],
            "links": built["links"],
            "models": built["models"],
            "scene_nodes": built["scene"]["count"],
        }
    )
    # trajectory CSV
    from lappa.config import WORKSPACES

    SESSION.start("diff_drive_2w", DEMOS_ROOT / "diff_drive_2w")
    SESSION.cmd(linear_x=0.5, angular_z=0.3)
    for _ in range(8):
        time.sleep(0.05)
        SESSION.tick()
    WORKSPACES.mkdir(parents=True, exist_ok=True)
    csv_path = WORKSPACES / "demo_trajectory.csv"
    csv_path.write_text(SESSION.trajectory_csv(), encoding="utf-8")
    rprint({"trajectory_csv": str(csv_path), "points": SESSION.status()["trajectory_points"]})
    SESSION.stop()
    dstat = docker_bridge.status()
    rprint({"docker": dstat["available"], "daemon": dstat.get("daemon"), "gui": True})
    rprint("Lappa demo complete (sim + ros2 version + package + 3d + trajectory).")


@demos_app.command("list")
def demos_list() -> None:
    table = Table(title="Lappa demos")
    table.add_column("Id")
    table.add_column("Description")
    table.add_column("Files")
    for p in list_demo_packages(DEMOS_ROOT):
        table.add_row(p.name, p.description[:60], str(len(p.files)))
    console.print(table)


@app.command("list-demos")
def list_demos_compat(
    path: Path | None = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository root to scan. Omit to list bundled demos.",
    ),
) -> None:
    """List demo packages and their paths (compatibility command)."""
    if path is None:
        discovered = [(pkg.name, pkg.path) for pkg in list_demo_packages(DEMOS_ROOT)]
    else:
        packages_dir = path.resolve() / "packages"
        if not packages_dir.is_dir():
            rprint(f"No packages directory found at {packages_dir}")
            return
        discovered = [
            (demo.parent.name, demo)
            for demo in sorted(packages_dir.glob("*/demo"))
            if demo.is_dir()
        ]
        demos_dir = packages_dir / "demos"
        if demos_dir.is_dir():
            discovered.extend(
                (package.name, package)
                for package in sorted(demos_dir.iterdir())
                if package.is_dir() and (package / "package.xml").is_file()
            )

    if not discovered:
        rprint("No demo packages found.")
        return
    rprint(f"Found {len(discovered)} demo package(s):")
    for name, demo_path in discovered:
        print(f"{name}\t{demo_path}")


@path_app.command("stats")
def path_stats_cmd(
    file: Path = typer.Option(
        ...,
        "--file",
        "-f",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="JSON fixture with a points array.",
    ),
) -> None:
    """Print path length and net displacement for a polyline fixture."""
    rprint(_path_stats(_path_points_from_fixture(file)))


@path_app.command("resample")
def path_resample_cmd(
    file: Path = typer.Option(
        ...,
        "--file",
        "-f",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="JSON fixture with a points array.",
    ),
    step_m: float = typer.Option(
        0.5,
        "--step-m",
        "-s",
        min=0.001,
        help="Step size in meters for resampling.",
    ),
) -> None:
    """Resample a polyline fixture at fixed step meters and print new length and points."""
    points = _path_points_from_fixture(file)
    resampled = _resample(points, step_m)
    stats = _path_stats(resampled)
    stats["step_m"] = step_m
    rprint(stats)
    console.print("[dim]Points:[/dim]")
    for px, py in resampled:
        console.print(f"  [{px:.4f}, {py:.4f}]")


@workspace_app.command("open")
def workspace_open(path: Path) -> None:
    pkg = workspace_store.resolve_package_ref(path, base_dir=Path.cwd())
    workspace_store.set_active_package(pkg.path)
    rprint(pkg.to_dict())


@workspace_app.command("list")
def workspace_list() -> None:
    table = Table(title="Workspace packages")
    table.add_column("Name")
    table.add_column("Files")
    table.add_column("Path")
    for pkg in workspace_store.workspace_packages():
        table.add_row(pkg.name, str(len(pkg.files)), str(pkg.path))
    console.print(table)


@workspace_app.command("roots")
def workspace_roots_cmd() -> None:
    table = Table(title="Workspace roots")
    table.add_column("Path")
    for root in workspace_store.workspace_roots():
        table.add_row(str(root))
    console.print(table)


@workspace_app.command("add")
def workspace_add(path: Path) -> None:
    state = workspace_store.add_workspace_root(path if path.is_absolute() else Path.cwd() / path)
    rprint({"ok": True, "roots": state["roots"]})


@workspace_app.command("remove")
def workspace_remove(path: Path) -> None:
    state = workspace_store.remove_workspace_root(
        path if path.is_absolute() else Path.cwd() / path
    )
    rprint({"ok": True, "roots": state["roots"]})


@workspace_app.command("new")
def workspace_new(
    include_samples: bool = typer.Option(
        False,
        "--include-samples",
        help="Seed the new workspace with bundled sample packages.",
    ),
) -> None:
    state = workspace_store.create_workspace(include_samples=include_samples)
    rprint({"ok": True, **state})


@sim_app.command("start")
def sim_start(
    demo: str = typer.Option("diff_drive_2w", "--demo", "-d"),
    package: str | None = typer.Option(None, "--package", "-p"),
) -> None:
    pkg = None
    if package:
        pkg = workspace_store.resolve_package_ref(package, base_dir=Path.cwd())
    elif demo:
        try:
            pkg = workspace_store.resolve_package_ref(demo, base_dir=Path.cwd())
        except FileNotFoundError:
            pkg = None
    path = pkg.path if pkg else DEMOS_ROOT / demo
    out = SESSION.start(pkg.name if pkg else demo, path if path.is_dir() else None)
    rprint(out)


@sim_app.command("status")
def sim_status() -> None:
    rprint(SESSION.status())


@sim_app.command("stop")
def sim_stop() -> None:
    rprint(SESSION.stop())


@sim_app.command("cmd")
def sim_cmd(
    lx: float = typer.Option(0.3, "--lx"),
    ly: float = typer.Option(0.0, "--ly"),
    az: float = typer.Option(0.1, "--az"),
) -> None:
    rprint(SESSION.cmd(lx, ly, az))


@sim_app.command("summary")
def sim_summary() -> None:
    """Print compact sim session summary (pose, joints count, lidar rays)."""
    st = SESSION.status()
    state = st.get("state") or st
    lidar = state.get("lidar") or []
    joints = state.get("joints") or []
    traj = st.get("trajectory_stats") or SESSION.trajectory_stats()
    rprint(
        {
            "demo": state.get("demo") or st.get("demo"),
            "kind": state.get("kind"),
            "running": state.get("running"),
            "pose": {
                "x": state.get("x"),
                "y": state.get("y"),
                "theta": state.get("theta"),
            },
            "n_joints": len(joints),
            "n_lidar": len(lidar),
            "lidar_min": min(lidar) if lidar else None,
            "t": state.get("t"),
            "trajectory": traj,
        }
    )


@sim_app.command("stats")
def sim_stats() -> None:
    """Trajectory metrics only (distance, speed, idle, efficiency)."""
    rprint(SESSION.trajectory_stats())


@demos_app.command("info")
def demos_info(
    name: str = typer.Argument(..., help="Demo package id e.g. diff_drive_2w"),
) -> None:
    """Show package path, file count, and launch file for a demo."""
    from lappa.config import DEMOS_ROOT
    from lappa.package_loader import load_package

    path = DEMOS_ROOT / name
    if not path.is_dir():
        rprint({"ok": False, "error": f"unknown demo {name}"})
        raise typer.Exit(1)
    pkg = load_package(path)
    launches = [f for f in pkg.files if "/launch/" in f or f.startswith("launch/")]
    rprint(
        {
            "name": pkg.name,
            "path": str(pkg.path),
            "files": len(pkg.files),
            "description": pkg.description,
            "launch_files": launches[:20],
            "has_urdf": any(f.endswith(".urdf") for f in pkg.files),
        }
    )


@sim_app.command("trajectory")
def sim_trajectory(
    out: Path | None = typer.Option(None, "--out", "-o", help="Write CSV path"),
    rich_columns: bool = typer.Option(
        False,
        "--rich",
        help="Export velocity, acceleration, jerk, and 3D rotation columns.",
    ),
) -> None:
    """Export recorded odom trail as CSV."""
    csv = SESSION.trajectory_rich_csv() if rich_columns else SESSION.trajectory_csv()
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(csv, encoding="utf-8")
        rprint({"ok": True, "path": str(out), "bytes": out.stat().st_size})
    else:
        print(csv)


@docker_app.command("status")
def docker_status() -> None:
    rprint(docker_bridge.status())


@docker_app.command("show")
def docker_show() -> None:
    rprint(docker_bridge.show_info())


@docker_app.command("start")
def docker_start() -> None:
    """Start Docker runtime (demos mounted at /ws/src for IDE edits)."""
    rprint(docker_bridge.start_runtime())


@docker_app.command("stop")
def docker_stop() -> None:
    rprint(docker_bridge.stop_runtime())


@docker_app.command("build")
def docker_build(
    demo: str = typer.Option(
        "",
        "--demo",
        "-d",
        help="Package to colcon-build (empty = all under /ws/src)",
    ),
) -> None:
    """colcon build ROS2 package(s) inside the container."""
    rprint(docker_bridge.build_package(demo or None))


@docker_app.command("launch")
def docker_launch(
    demo: str = typer.Option("diff_drive_2w", "--demo", "-d", help="Demo package name"),
    no_rebuild: bool = typer.Option(False, "--no-rebuild", help="Skip colcon build"),
) -> None:
    """Load ROS2, colcon-build package, ros2 launch <pkg> sim.launch.py."""
    rprint(docker_bridge.launch_demo(demo, rebuild=not no_rebuild))


@docker_app.command("launch-stop")
def docker_launch_stop() -> None:
    rprint(docker_bridge.stop_launch())


@docker_app.command("logs")
def docker_logs(
    after: int = typer.Option(0, "--after", help="Only return events after this cursor"),
    limit: int = typer.Option(200, "--limit", help="Maximum events to return"),
) -> None:
    """Read redacted Docker/native launch logs for IDE and automation clients."""
    rprint(docker_bridge.launch_logs(after=after, limit=limit))


@ros2_app.command("list")
def ros2_list() -> None:
    table = Table(title="ROS2 versions")
    table.add_column("Id")
    table.add_column("Name")
    table.add_column("Ubuntu")
    table.add_column("Status")
    table.add_column("Image")
    sel = ros2_versions.get_selected()["id"]
    for v in ros2_versions.list_versions():
        mark = " *" if v["id"] == sel else ""
        table.add_row(v["id"] + mark, v["name"], v["ubuntu"], v["status"], v["docker_image"])
    console.print(table)


@ros2_app.command("get")
def ros2_get() -> None:
    rprint(ros2_versions.get_selected())


@ros2_app.command("set")
def ros2_set(distro: str = typer.Argument(..., help="humble|iron|jazzy|kilted|rolling")) -> None:
    selected = ros2_versions.set_selected(distro)
    docker_bridge.apply_ros2_dockerfile(distro)
    rprint(selected)


@pkg_app.command("list")
def pkg_list() -> None:
    for p in packager.list_bundleable():
        rprint(f"{p['name']}: {p['files']} files — {p['description'][:50]}")


@pkg_app.command("bundle")
def pkg_bundle(
    packages: list[str] | None = typer.Option(
        None,
        "--pkg",
        "-p",
        help="Package name (repeatable). Default: all demos.",
    ),
    distro: str | None = typer.Option(None, "--distro", "-d"),
) -> None:
    names = packages if packages else None
    rprint(packager.package_bundle(names, distro=distro))


@pkg_app.command("bundles")
def pkg_bundles() -> None:
    rprint(packager.list_bundles())


@pkg_app.command("template")
def pkg_template(
    name: str = typer.Argument(..., help="New demo package name (snake_case)"),
    robot_type: str = typer.Option("diff_drive", "--type", "-t", help="Robot type: diff_drive, ackermann, mecanum"),
) -> None:
    """Generate a new demo package from template."""
    from lappa.config import DEMOS_ROOT
    import shutil
    template_name = f"{robot_type}_2w" if robot_type == "diff_drive" else f"{robot_type}_4w"
    src = DEMOS_ROOT / template_name
    if not src.exists():
        available = [d.name for d in DEMOS_ROOT.iterdir() if d.is_dir() and not d.name.startswith('.')]
        rprint(f"[red]Template {template_name} not found.[/red] Available: {available}")
        raise typer.Exit(1)
    dest = DEMOS_ROOT / name
    if dest.exists():
        rprint(f"[red]Package {name} already exists.[/red]")
        raise typer.Exit(1)
    shutil.copytree(src, dest)
    # Replace package name in setup.py and package.xml
    for f in dest.rglob("setup.py"):
        content = f.read_text()
        f.write_text(content.replace(template_name, name))
    for f in dest.rglob("package.xml"):
        content = f.read_text()
        f.write_text(content.replace(template_name, name))
    rprint(f"[green]Created[/green] {dest}")
    rprint(f"cd {dest} && colcon build")


@model_app.command("presets")
def model_presets() -> None:
    for p in models3d.list_presets():
        rprint(f"{p['id']}: {p['description']}")


@model_app.command("create")
def model_create(
    preset: str = typer.Argument("box"),
    name: str | None = typer.Option(None, "--name", "-n"),
) -> None:
    rprint(models3d.create_model(preset, name=name))


@model_app.command("list")
def model_list() -> None:
    rprint(models3d.list_library())


@model_app.command("attach")
def model_attach(
    package: str = typer.Argument(..., help="Demo package id"),
    model_id: str = typer.Argument(..., help="Model id from library"),
    auto_fit: bool = typer.Option(True, "--auto-fit/--no-auto-fit"),
    link: str = typer.Option("base_link", "--link"),
) -> None:
    rprint(
        models3d.attach_model_to_package(
            package,
            model_id,
            link_name=link,
            auto_fit=auto_fit,
        )
    )


@model_app.command("fit")
def model_fit(
    model_id: str = typer.Argument(..., help="Library model id"),
    sx: float = typer.Option(0.4, "--sx"),
    sy: float = typer.Option(0.3, "--sy"),
    sz: float = typer.Option(0.12, "--sz"),
    uniform: bool = typer.Option(False, "--uniform"),
    save_as: str | None = typer.Option(None, "--as", help="Output model id"),
) -> None:
    """Auto-scale mesh AABB to target size (khớp 3D)."""
    rprint(
        models3d.fit_library_model(
            model_id,
            [sx, sy, sz],
            uniform=uniform,
            save_as=save_as,
        )
    )


@model_app.command("build-robot")
def model_build_robot(
    package: str = typer.Argument(..., help="Demo package id"),
    kind: str | None = typer.Option(None, "--kind", "-k", help="Layout kind (default=package name)"),
) -> None:
    """Build full aligned 3D robot (chassis + wheels + lidar) into package URDF."""
    rprint(models3d.build_aligned_robot(package, kind=kind))


@model_app.command("scene")
def model_scene(package: str = typer.Argument(...)) -> None:
    """Print package scene3d JSON for the WebGL viewer."""
    rprint(models3d.package_scene3d(package))


@app.command("serve")
def serve_cmd(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8840, "--port"),
) -> None:
    """Serve the local automation API only. The IDE is the Qt desktop app."""
    ensure_dirs()
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit('Install API extras: pip install -e ".[api]"') from exc
    from lappa.api import app as fastapi_app

    rprint(f"Lappa API -> http://{host}:{port}")
    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")


@app.command("desktop")
def desktop_cmd() -> None:
    """Launch the Qt desktop IDE."""
    from lappa.gui.app import main as gui_main

    raise SystemExit(gui_main())


if __name__ == "__main__":
    app()
