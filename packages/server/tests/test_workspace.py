from pathlib import Path

import pytest

from lappa import workspace


def _pkg(root: Path, name: str) -> Path:
    path = root / name
    path.mkdir(parents=True)
    (path / "package.xml").write_text(
        f"""<package format="3">
  <name>{name}</name>
  <version>0.1.0</version>
  <description>{name}</description>
  <maintainer email="dev@example.com">Dev</maintainer>
  <license>MIT</license>
  <export><build_type>ament_python</build_type></export>
</package>
""",
        encoding="utf-8",
    )
    (path / name).mkdir()
    (path / name / "__init__.py").write_text("", encoding="utf-8")
    return path


def test_discover_packages_scans_workspace_root(tmp_path):
    src = tmp_path / "ros_ws" / "src"
    alpha = _pkg(src, "alpha_bot")
    beta = _pkg(src, "beta_arm")

    packages = workspace.discover_packages(src)

    assert [p.name for p in packages] == ["alpha_bot", "beta_arm"]
    assert {p.path for p in packages} == {alpha.resolve(), beta.resolve()}


def test_discover_packages_skips_build_install_log(tmp_path):
    src = tmp_path / "src"
    real = _pkg(src, "real_pkg")
    _pkg(tmp_path / "build", "generated_pkg")
    _pkg(tmp_path / "install", "installed_pkg")
    _pkg(tmp_path / "log", "logged_pkg")

    packages = workspace.discover_packages(tmp_path)

    assert [p.name for p in packages] == ["real_pkg"]
    assert packages[0].path == real.resolve()


def test_workspace_state_add_open_and_resolve(tmp_path):
    src = tmp_path / "ws" / "src"
    pkg_path = _pkg(src, "nav_stack")
    state_path = tmp_path / "workspace.json"

    workspace.create_workspace(state_path=state_path)
    workspace.add_workspace_root(src, state_path=state_path)
    packages = workspace.workspace_packages(state_path)
    workspace.set_active_package(pkg_path, state_path=state_path)

    assert [p.name for p in packages] == ["nav_stack"]
    assert workspace.active_package(state_path).name == "nav_stack"
    assert (
        workspace.resolve_package_ref("nav_stack", state_path=state_path).path == pkg_path.resolve()
    )
    assert workspace.resolve_package_ref(pkg_path, state_path=state_path).name == "nav_stack"


def test_resolve_package_ref_reports_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        workspace.resolve_package_ref("missing_pkg", state_path=tmp_path / "workspace.json")
