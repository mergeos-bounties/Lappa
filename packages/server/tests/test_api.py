import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from lappa.api import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "diff_drive_2w" in body["demos"]


def test_demos_and_sim():
    r = client.get("/api/demos")
    assert r.status_code == 200
    assert len(r.json()) >= 5

    r = client.post("/api/sim/start", json={"demo": "diff_drive_2w"})
    assert r.status_code == 200
    assert r.json()["state"]["running"] is True

    client.post("/api/sim/cmd", json={"linear_x": 0.5, "angular_z": 0.1})
    st = client.get("/api/sim/state").json()
    assert "x" in st

    client.post("/api/sim/stop")


def test_docker_status_endpoint():
    r = client.get("/api/docker/status")
    assert r.status_code == 200
    assert "available" in r.json()


def test_ros2_versions_api():
    r = client.get("/api/ros2/versions")
    assert r.status_code == 200
    body = r.json()
    assert any(v["id"] == "humble" for v in body["versions"])
    r = client.post("/api/ros2/version", json={"distro": "jazzy"})
    assert r.status_code == 200
    assert r.json()["selected"]["id"] == "jazzy"
    client.post("/api/ros2/version", json={"distro": "humble"})


def test_bundle_and_models_api():
    r = client.post(
        "/api/packages/bundle",
        json={"packages": ["diff_drive_2w"], "distro": "humble", "out_name": "api_test_bundle"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    r = client.get("/api/packages/bundles")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = client.get("/api/models/presets")
    assert r.status_code == 200
    assert len(r.json()) >= 5
    r = client.post("/api/models", json={"preset": "chassis", "name": "api_chassis"})
    assert r.status_code == 200
    mid = r.json()["id"]
    r = client.post(
        "/api/models/attach",
        json={"package": "omni_3w", "model_id": mid},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_urdf_sticks_api():
    r = client.get("/api/packages/diff_drive_2w/urdf/sticks")
    assert r.status_code == 200
    body = r.json()
    assert body["package"] == "diff_drive_2w"
    assert body["link_count"] >= 3
    roles = {n["role"] for n in body["nodes"]}
    assert "base" in roles
    assert "wheel" in roles
    assert body["joint_count"] >= 1

    r = client.get("/api/packages/no_such_pkg/urdf/sticks")
    assert r.status_code == 404
