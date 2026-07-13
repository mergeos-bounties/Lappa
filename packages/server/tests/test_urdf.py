import pytest

from lappa import urdf
from lappa.config import DEMOS_ROOT

SAMPLE_URDF = """<?xml version="1.0"?>
<robot name="unit_bot">
  <link name="base_footprint"/>
  <joint name="base_joint" type="fixed">
    <parent link="base_footprint"/>
    <child link="base_link"/>
    <origin xyz="0 0 0.08" rpy="0 0 0"/>
  </joint>

  <link name="base_link">
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0"/>
      <geometry><box size="0.4 0.3 0.1"/></geometry>
    </visual>
  </link>

  <link name="wheel_left"/>
  <joint name="wheel_left_joint" type="continuous">
    <parent link="base_link"/>
    <child link="wheel_left"/>
    <origin xyz="0 0.16 -0.03" rpy="0 0 0"/>
    <axis xyz="0 1 0"/>
  </joint>

  <link name="wheel_right"/>
  <joint name="wheel_right_joint" type="continuous">
    <parent link="base_link"/>
    <child link="wheel_right"/>
    <origin xyz="0 -0.16 -0.03" rpy="0 0 0"/>
    <axis xyz="0 1 0"/>
  </joint>
</robot>
"""


def test_parse_urdf_links_and_joints():
    parsed = urdf.parse_urdf(SAMPLE_URDF)
    assert parsed["robot"] == "unit_bot"
    names = {link["name"] for link in parsed["links"]}
    assert names == {"base_footprint", "base_link", "wheel_left", "wheel_right"}
    joint_names = {j["name"] for j in parsed["joints"]}
    assert joint_names == {"base_joint", "wheel_left_joint", "wheel_right_joint"}
    wheel_joint = next(j for j in parsed["joints"] if j["name"] == "wheel_left_joint")
    assert wheel_joint["type"] == "continuous"
    assert wheel_joint["xyz"] == [0.0, 0.16, -0.03]


def test_parse_urdf_invalid_xml_raises():
    with pytest.raises(ValueError):
        urdf.parse_urdf("<robot><link name=oops></robot>")


def test_link_poses_accumulate_from_root():
    parsed = urdf.parse_urdf(SAMPLE_URDF)
    poses = urdf.link_poses(parsed)
    assert poses["base_footprint"] == [0.0, 0.0, 0.0]
    assert poses["base_link"] == [0.0, 0.0, 0.08]
    # wheel offset accumulates on top of base_link
    assert poses["wheel_left"] == pytest.approx([0.0, 0.16, 0.05])
    assert poses["wheel_right"] == pytest.approx([0.0, -0.16, 0.05])


def test_stick_figure_base_and_wheels():
    fig = urdf.stick_figure(SAMPLE_URDF)
    assert fig["robot"] == "unit_bot"
    assert fig["link_count"] == 4
    assert fig["joint_count"] == 3
    roles = {n["link"]: n["role"] for n in fig["nodes"]}
    assert roles["base_link"] == "base"
    assert roles["wheel_left"] == "wheel"
    assert roles["wheel_right"] == "wheel"
    # at least a base + wheel segment must be present (acceptance: base + wheels)
    seg_children = {s["child"] for s in fig["segments"]}
    assert "wheel_left" in seg_children
    assert "wheel_right" in seg_children
    wheel_seg = next(s for s in fig["segments"] if s["child"] == "wheel_left")
    assert wheel_seg["parent"] == "base_link"
    assert wheel_seg["x2"] == pytest.approx(0.0)
    assert wheel_seg["y2"] == pytest.approx(0.16)


def test_stick_figure_orphan_link_defaults_to_origin():
    text = """<?xml version="1.0"?>
<robot name="orphan_bot">
  <link name="base_link"/>
  <link name="floating_sensor"/>
</robot>
"""
    fig = urdf.stick_figure(text)
    assert fig["link_count"] == 2
    floating = next(n for n in fig["nodes"] if n["link"] == "floating_sensor")
    assert floating["x"] == 0.0 and floating["y"] == 0.0


@pytest.mark.parametrize("demo", ["diff_drive_2w", "omni_3w", "ackermann_4w", "tricycle_3w"])
def test_package_stick_figure_real_demo_urdfs(demo):
    fig = urdf.package_stick_figure(demo)
    assert fig["package"] == demo
    assert fig["link_count"] >= 3
    roles = {n["role"] for n in fig["nodes"]}
    assert "base" in roles
    assert "wheel" in roles


def test_package_stick_figure_missing_package_raises():
    with pytest.raises(FileNotFoundError):
        urdf.package_stick_figure("does_not_exist_pkg")


def test_demo_urdfs_still_present():
    assert (DEMOS_ROOT / "diff_drive_2w" / "urdf" / "robot.urdf").is_file()
