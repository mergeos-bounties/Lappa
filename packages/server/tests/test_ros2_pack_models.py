from pathlib import Path

from lappa import models3d, packager, ros2_versions
from lappa.config import DEMOS_ROOT


def test_ros2_versions_list_and_set():
    versions = ros2_versions.list_versions()
    ids = {v["id"] for v in versions}
    assert "humble" in ids
    assert "jazzy" in ids
    assert "rolling" in ids
    prev = ros2_versions.get_selected()["id"]
    sel = ros2_versions.set_selected("jazzy")
    assert sel["id"] == "jazzy"
    assert "docker_image" in sel
    ros2_versions.set_selected(prev)


def test_package_bundle_zip():
    result = packager.package_bundle(
        ["diff_drive_2w"], distro="humble", out_name="test_bundle_unit"
    )
    assert result["ok"] is True
    path = Path(result["path"])
    assert path.is_file()
    assert path.stat().st_size > 100
    assert result["ros2_distro"] == "humble"
    bundles = packager.list_bundles()
    assert any(b["filename"] == result["filename"] for b in bundles)


def test_mesh_create_and_attach():
    mesh = models3d.create_model("wheel", name="unit_wheel_test", radius=0.06, height=0.03)
    assert mesh["ok"]
    assert Path(mesh["obj_path"]).is_file()
    assert "v " in Path(mesh["obj_path"]).read_text(encoding="utf-8")
    assert mesh["bounds"]["vertices"] > 0
    att = models3d.attach_model_to_package(
        "diff_drive_2w",
        mesh["id"],
        auto_fit=True,
        target_size=[0.1, 0.04, 0.1],
        replace=True,
    )
    assert att["ok"]
    assert Path(att["mesh"]).is_file()
    urdf = Path(att["urdf"]).read_text(encoding="utf-8")
    assert "mesh" in urdf
    assert mesh["id"] in urdf
    # no duplicate base_link_mesh spam
    assert urdf.count('name="base_link_mesh"') == 0
    attachments = models3d.package_attachments("diff_drive_2w")
    assert any(a["model_id"] == mesh["id"] for a in attachments)


def test_fit_obj_to_box():
    text, _ = models3d.generate_mesh("box", sx=2.0, sy=1.0, sz=0.5)
    fitted, report = models3d.fit_obj_to_box(text, (0.4, 0.2, 0.1), center=True)
    after = report["after"]["size"]
    assert abs(after[0] - 0.4) < 1e-3
    assert abs(after[1] - 0.2) < 1e-3
    assert abs(after[2] - 0.1) < 1e-3
    center = report["after"]["center"]
    assert abs(center[0]) < 1e-3
    assert abs(center[1]) < 1e-3
    assert abs(center[2]) < 1e-3
    assert "v " in fitted


def test_tricycle_uses_xe_tham_do_chassis_dimensions():
    text, meta = models3d.generate_mesh("xe_tham_do_chassis", sx=0.40, sy=0.26, sz=0.15)
    bounds = models3d.mesh_bounds(text)
    assert meta["kind"] == "xe_tham_do_chassis"
    assert meta["source"].endswith("TUPM96/xe_tham_do")
    assert bounds["vertices"] == 8
    assert bounds["size"] == [0.4, 0.26, 0.15]


def test_build_aligned_robot_diff_drive():
    result = models3d.build_aligned_robot("diff_drive_2w")
    assert result["ok"]
    assert result["links"] >= 3  # chassis + 2 wheels (+ lidar)
    urdf = Path(result["urdf"]).read_text(encoding="utf-8")
    assert 'name="base_link"' in urdf
    assert 'name="wheel_left"' in urdf
    assert 'name="wheel_right"' in urdf
    assert urdf.count("<robot") == 1
    assert "continuous" in urdf
    scene = result["scene"]
    assert scene["count"] >= 3
    assert all("mesh_url" in n for n in scene["nodes"])


def test_build_aligned_robot_omni():
    result = models3d.build_aligned_robot("omni_3w")
    assert result["ok"]
    urdf = Path(result["urdf"]).read_text(encoding="utf-8")
    assert "wheel_0" in urdf
    assert "wheel_1" in urdf
    assert "wheel_2" in urdf


def test_package_scene3d():
    models3d.build_aligned_robot("diff_drive_2w")
    scene = models3d.package_scene3d("diff_drive_2w")
    assert scene["package"] == "diff_drive_2w"
    assert scene["count"] >= 1
    mesh_path = models3d.read_package_mesh("diff_drive_2w", Path(scene["nodes"][0]["mesh"]).name)
    assert mesh_path.is_file()


def test_all_mesh_presets_generate():
    for preset in models3d.MESH_PRESETS:
        text, meta = models3d.generate_mesh(preset)
        assert text.startswith("#")
        assert "v " in text
        assert meta["preset"] == preset


def test_demos_still_present():
    assert (DEMOS_ROOT / "diff_drive_2w" / "package.xml").is_file()
