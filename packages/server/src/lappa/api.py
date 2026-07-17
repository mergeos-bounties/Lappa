from __future__ import annotations

from pathlib import Path
from typing import Any

from lappa import (
    __version__,
    docker_bridge,
    models3d,
    packager,
    ros2_versions,
    urdf,
    workspace as workspace_store,
)
from lappa.config import DEMOS_ROOT, ensure_dirs
from lappa.package_loader import list_demo_packages, load_package, read_file, write_file
from lappa.sim.session import SESSION

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover
    raise ImportError('pip install -e ".[api]"') from exc

ensure_dirs()
app = FastAPI(title="Lappa", version=__version__)

# Active workspace package path (default first demo)
_active: Path | None = None


def _active_package():
    global _active
    if _active and _active.is_dir():
        return load_package(_active)
    pkg = workspace_store.active_package()
    if pkg:
        _active = pkg.path
        return pkg
    raise HTTPException(404, "no packages")


class FileBody(BaseModel):
    path: str
    content: str


class CmdBody(BaseModel):
    linear_x: float = 0.0
    linear_y: float = 0.0
    angular_z: float = 0.0


class StartBody(BaseModel):
    demo: str = "diff_drive_2w"
    package: str | None = None


class HotReloadBody(BaseModel):
    enabled: bool = True


class Ros2VersionBody(BaseModel):
    distro: str


class BundleBody(BaseModel):
    packages: list[str] | None = None
    distro: str | None = None
    out_name: str | None = None


class ModelCreateBody(BaseModel):
    preset: str = "box"
    name: str | None = None
    sx: float = 0.4
    sy: float = 0.3
    sz: float = 0.15
    radius: float = 0.08
    height: float = 0.05
    length: float = 0.5
    thickness: float = 0.06
    segments: int = 24


class ModelAttachBody(BaseModel):
    package: str
    model_id: str
    link_name: str = "base_link"
    xyz: str = "0 0 0"
    rpy: str = "0 0 0"
    scale: str = "1 1 1"
    auto_fit: bool = True
    target_size: list[float] | None = None
    replace: bool = True


class ModelFitBody(BaseModel):
    model_id: str
    target_size: list[float] = [0.4, 0.3, 0.12]
    uniform: bool = False
    save_as: str | None = None


class BuildRobotBody(BaseModel):
    package: str
    kind: str | None = None


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "lappa",
        "version": __version__,
        "demos": [p.name for p in list_demo_packages(DEMOS_ROOT)],
        "packages": [p.name for p in workspace_store.workspace_packages()],
        "docker": docker_bridge.status().get("available"),
        "ros2": ros2_versions.get_selected(),
    }


@app.get("/api/demos")
def api_demos() -> list[dict]:
    return [p.to_dict() for p in list_demo_packages(DEMOS_ROOT)]


@app.get("/api/workspace/packages")
def api_workspace_packages() -> list[dict]:
    return [p.to_dict() for p in workspace_store.workspace_packages()]


@app.get("/api/workspace/state")
def api_workspace_state() -> dict:
    active = _active_package()
    return {
        "state": workspace_store.load_workspace_state(),
        "roots": [str(p) for p in workspace_store.workspace_roots()],
        "active": active.to_dict(),
        "packages": [p.to_dict() for p in workspace_store.workspace_packages()],
    }


@app.post("/api/workspace/open")
def api_open(body: dict[str, str]) -> dict:
    global _active
    raw = body.get("path") or body.get("demo") or ""
    try:
        pkg = workspace_store.resolve_package_ref(raw, base_dir=Path.cwd())
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    _active = pkg.path.resolve()
    workspace_store.set_active_package(_active)
    return load_package(_active).to_dict()


@app.get("/api/workspace")
def api_workspace() -> dict:
    return _active_package().to_dict()


@app.get("/api/files")
def api_read(path: str) -> dict:
    pkg = _active_package()
    try:
        content = read_file(pkg, path)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(400, str(e)) from e
    return {"path": path, "content": content}


@app.put("/api/files")
def api_write(body: FileBody) -> dict:
    pkg = _active_package()
    try:
        write_file(pkg, body.path, body.content)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    SESSION.notify_file_change(body.path)
    return {"ok": True, "path": body.path}


@app.post("/api/sim/start")
def api_sim_start(body: StartBody) -> dict:
    pkg = None
    if body.package:
        try:
            pkg = workspace_store.resolve_package_ref(body.package, base_dir=Path.cwd())
        except FileNotFoundError:
            pkg = None
    if not pkg and body.demo:
        try:
            pkg = workspace_store.resolve_package_ref(body.demo, base_dir=Path.cwd())
        except FileNotFoundError:
            pkg = None
    demo = pkg.name if pkg else body.demo
    path = pkg.path if pkg else DEMOS_ROOT / body.demo
    return SESSION.start(demo, path if path.is_dir() else None)


@app.post("/api/sim/stop")
def api_sim_stop() -> dict:
    return SESSION.stop()


@app.get("/api/sim/state")
def api_sim_state() -> dict:
    return SESSION.tick()


@app.get("/api/sim/status")
def api_sim_status() -> dict:
    return SESSION.status()


@app.post("/api/sim/cmd")
def api_sim_cmd(body: CmdBody) -> dict:
    return SESSION.cmd(body.linear_x, body.linear_y, body.angular_z)


@app.get("/api/sim/trajectory.csv")
def api_sim_trajectory_csv():
    from fastapi.responses import Response

    csv = SESSION.trajectory_csv()
    return Response(
        content=csv,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="lappa_trajectory.csv"'},
    )


@app.post("/api/sim/trajectory/clear")
def api_sim_trajectory_clear() -> dict:
    SESSION.clear_trajectory()
    return {"ok": True, "trajectory_points": 0}


@app.post("/api/hot-reload")
def api_hot_reload(body: HotReloadBody) -> dict:
    SESSION.hot_reload = body.enabled
    return {"hot_reload": SESSION.hot_reload}


@app.get("/api/docker/status")
def api_docker_status() -> dict:
    return docker_bridge.status()


@app.get("/api/docker/show")
def api_docker_show() -> dict:
    return docker_bridge.show_info()


@app.post("/api/docker/start")
def api_docker_start() -> dict:
    return docker_bridge.start_runtime()


@app.post("/api/docker/stop")
def api_docker_stop() -> dict:
    return docker_bridge.stop_runtime()


class DockerLaunchBody(BaseModel):
    demo: str = "diff_drive_2w"


@app.post("/api/docker/launch")
def api_docker_launch(body: DockerLaunchBody) -> dict:
    """Start ros2 launch for a demo package inside the Docker container.

    Package sources are the same tree the IDE opens/edits (packages/demos).
    """
    return docker_bridge.launch_demo(body.demo)


@app.post("/api/docker/launch/stop")
def api_docker_launch_stop() -> dict:
    return docker_bridge.stop_launch()


@app.get("/api/docker/launch")
def api_docker_launch_status() -> dict:
    return docker_bridge.launch_status()


@app.get("/api/docker/launch/logs")
def api_docker_launch_logs(after: int = 0, limit: int = 200) -> dict:
    """Poll redacted Docker/native launch logs using the returned cursor."""
    return docker_bridge.launch_logs(after=after, limit=limit)


# --- ROS2 version ---
@app.get("/api/ros2/versions")
def api_ros2_versions() -> dict:
    return {"versions": ros2_versions.list_versions(), "selected": ros2_versions.get_selected()}


@app.get("/api/ros2/version")
def api_ros2_version_get() -> dict:
    return ros2_versions.get_selected()


@app.post("/api/ros2/version")
def api_ros2_version_set(body: Ros2VersionBody) -> dict:
    try:
        selected = ros2_versions.set_selected(body.distro)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    docker_bridge.apply_ros2_dockerfile(body.distro)
    return {"ok": True, "selected": selected}


# --- Package bundling ---
@app.get("/api/packages")
def api_packages() -> list[dict]:
    return packager.list_bundleable()


@app.post("/api/packages/bundle")
def api_bundle(body: BundleBody) -> dict:
    try:
        return packager.package_bundle(body.packages, body.distro, body.out_name)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/packages/bundles")
def api_bundles() -> list[dict]:
    return packager.list_bundles()


@app.get("/api/packages/bundles/{filename}")
def api_download_bundle(filename: str) -> FileResponse:
    # prevent path traversal
    safe = Path(filename).name
    path = packager._bundle_root() / safe
    if not path.is_file() or path.suffix != ".zip":
        raise HTTPException(404, "bundle not found")
    return FileResponse(path, filename=safe, media_type="application/zip")


# --- 3D models ---
@app.get("/api/models/presets")
def api_model_presets() -> list[dict]:
    return models3d.list_presets()


@app.get("/api/models")
def api_models() -> list[dict]:
    return models3d.list_library()


@app.post("/api/models")
def api_model_create(body: ModelCreateBody) -> dict:
    try:
        return models3d.create_model(
            body.preset,
            name=body.name,
            sx=body.sx,
            sy=body.sy,
            sz=body.sz,
            radius=body.radius,
            height=body.height,
            length=body.length,
            thickness=body.thickness,
            segments=body.segments,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/models/attach")
def api_model_attach(body: ModelAttachBody) -> dict:
    try:
        return models3d.attach_model_to_package(
            body.package,
            body.model_id,
            link_name=body.link_name,
            xyz=body.xyz,
            rpy=body.rpy,
            scale=body.scale,
            auto_fit=body.auto_fit,
            target_size=body.target_size,
            replace=body.replace,
        )
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/models/fit")
def api_model_fit(body: ModelFitBody) -> dict:
    try:
        return models3d.fit_library_model(
            body.model_id,
            body.target_size,
            uniform=body.uniform,
            save_as=body.save_as,
        )
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/models/build-robot")
def api_build_robot(body: BuildRobotBody) -> dict:
    """Generate full aligned multi-link 3D robot (chassis + wheels + lidar)."""
    try:
        return models3d.build_aligned_robot(body.package, kind=body.kind)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/models/attachments/{package}")
def api_model_attachments(package: str) -> list[dict]:
    try:
        return models3d.package_attachments(package)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/api/models/{model_id}/obj")
def api_model_obj(model_id: str):
    from fastapi.responses import PlainTextResponse

    try:
        text = models3d.get_model_obj(model_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    return PlainTextResponse(text, media_type="text/plain")


@app.get("/api/packages/{package}/scene3d")
def api_package_scene3d(package: str) -> dict:
    try:
        return models3d.package_scene3d(package)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/api/packages/{package}/urdf/sticks")
def api_package_urdf_sticks(package: str) -> dict:
    """Parse the package URDF and return a 2D stick-figure overlay."""
    try:
        return urdf.package_stick_figure(package)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/packages/{package}/mesh/{filename}")
def api_package_mesh(package: str, filename: str):
    from fastapi.responses import PlainTextResponse

    try:
        path = models3d.read_package_mesh(package, filename)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/plain")


