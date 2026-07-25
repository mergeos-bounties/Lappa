"""Presence over the HTTP API and the CLI, including the save-conflict signal."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from lappa import presence
from lappa.api import app
from lappa.cli import app as cli_app

client = TestClient(app)


@pytest.fixture()
def shared_dir(tmp_path):
    """Point the process-wide store at a throwaway directory."""
    original = presence.SESSION_PRESENCE
    presence.reset_session_presence(tmp_path / "presence", user="ide")
    yield tmp_path / "presence"
    try:
        presence.SESSION_PRESENCE.leave()
    except presence.PresenceError:  # pragma: no cover - directory already gone
        pass
    presence.SESSION_PRESENCE = original


def other_peer(shared_dir, user="bob", **join_kwargs) -> presence.PresenceStore:
    peer = presence.PresenceStore(shared_dir, user=user)
    peer.join(**join_kwargs)
    return peer


def test_presence_read_is_empty_and_creates_nothing(shared_dir):
    body = client.get("/api/presence").json()

    assert body["joined"] is False
    assert body["peers"] == []
    assert not shared_dir.exists()  # a status poll must not become a peer


def test_join_heartbeat_leave_cycle(shared_dir):
    joined = client.post("/api/presence/join", json={"user": "alice", "package": "pkg"}).json()
    assert joined["joined"] is True
    assert joined["count"] == 1
    assert joined["peers"][0]["user"] == "alice"

    beat = client.post("/api/presence/heartbeat", json={"file": "setup.py"}).json()
    assert beat["peers"][0]["file"] == "setup.py"
    assert beat["peers"][0]["package"] == "pkg"  # partial update keeps the rest

    left = client.post("/api/presence/leave").json()
    assert left["left"] is True
    assert client.get("/api/presence").json()["peers"] == []


def test_heartbeat_before_join_is_a_conflict(shared_dir):
    r = client.post("/api/presence/heartbeat", json={"file": "setup.py"})
    assert r.status_code == 409
    assert "join" in r.json()["detail"]


def test_presence_lists_another_session(shared_dir):
    other_peer(shared_dir, package="diff_drive_2w", file="setup.py")
    body = client.get("/api/presence").json()

    assert [p["user"] for p in body["peers"]] == ["bob"]
    assert body["others"] == 1
    assert body["peers"][0]["file"] == "setup.py"


def test_file_endpoint_reports_the_other_editor(shared_dir):
    client.post("/api/workspace/open", json={"path": "diff_drive_2w"})
    other_peer(shared_dir, package="diff_drive_2w", file="setup.py")

    body = client.get("/api/presence/file", params={"path": "setup.py"}).json()
    assert body["package"] == "diff_drive_2w"  # defaults to the open package
    assert [p["user"] for p in body["peers"]] == ["bob"]

    empty = client.get("/api/presence/file", params={"path": "package.xml"}).json()
    assert empty["peers"] == []


def test_file_endpoint_ignores_the_same_name_in_another_package(shared_dir):
    client.post("/api/workspace/open", json={"path": "diff_drive_2w"})
    other_peer(shared_dir, package="omni_3w", file="setup.py")

    body = client.get("/api/presence/file", params={"path": "setup.py"}).json()
    assert body["peers"] == []
    named = client.get(
        "/api/presence/file", params={"path": "setup.py", "package": "omni_3w"}
    ).json()
    assert [p["user"] for p in named["peers"]] == ["bob"]


def test_save_warns_about_the_peer_holding_the_same_file(shared_dir):
    client.post("/api/workspace/open", json={"path": "diff_drive_2w"})
    other_peer(shared_dir, package="diff_drive_2w", file="presence_demo.txt")

    r = client.put("/api/files", json={"path": "presence_demo.txt", "content": "hello\n"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True  # advisory: the save still happens
    assert [c["user"] for c in body["conflicts"]] == ["bob"]

    quiet = client.put("/api/files", json={"path": "presence_quiet.txt", "content": "hi\n"})
    assert quiet.json()["conflicts"] == []
    _cleanup(["presence_demo.txt", "presence_quiet.txt"])


def test_save_does_not_make_a_read_only_client_a_peer(shared_dir):
    client.post("/api/workspace/open", json={"path": "diff_drive_2w"})
    client.put("/api/files", json={"path": "presence_solo.txt", "content": "x\n"})

    assert client.get("/api/presence").json()["peers"] == []
    _cleanup(["presence_solo.txt"])


def test_save_tracks_the_file_once_the_ide_has_joined(shared_dir):
    client.post("/api/workspace/open", json={"path": "diff_drive_2w"})
    client.post("/api/presence/join", json={"user": "alice"})
    client.put("/api/files", json={"path": "presence_tracked.txt", "content": "x\n"})

    me = client.get("/api/presence").json()["peers"][0]
    assert me["file"] == "presence_tracked.txt"
    assert me["package"] == "diff_drive_2w"
    _cleanup(["presence_tracked.txt"])


def test_broken_presence_directory_never_breaks_a_save(tmp_path):
    """A dead network share degrades presence, it does not fail the edit."""
    original = presence.SESSION_PRESENCE
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("share is offline", encoding="utf-8")
    presence.SESSION_PRESENCE = presence.PresenceStore(blocker)
    try:
        client.post("/api/workspace/open", json={"path": "diff_drive_2w"})
        r = client.put("/api/files", json={"path": "presence_broken.txt", "content": "x\n"})
        assert r.status_code == 200
        assert r.json()["conflicts"] == []

        joined = client.post("/api/presence/join")
        assert joined.status_code == 503
    finally:
        presence.SESSION_PRESENCE = original
        _cleanup(["presence_broken.txt"])


def _cleanup(names: list[str]) -> None:
    from lappa import workspace as workspace_store

    pkg = workspace_store.resolve_package_ref("diff_drive_2w")
    for name in names:
        (pkg.path / name).unlink(missing_ok=True)


# --- CLI --------------------------------------------------------------------
def test_cli_lists_peers_and_reports_the_directory(tmp_path):
    runner = CliRunner()
    peer = presence.PresenceStore(tmp_path / "presence", user="carol")
    peer.join(package="diff_drive_2w", file="setup.py")

    listed = runner.invoke(cli_app, ["presence", "list", "--dir", str(tmp_path / "presence")])
    assert listed.exit_code == 0
    assert "carol" in listed.output

    where = runner.invoke(
        cli_app, ["presence", "where", "setup.py", "--dir", str(tmp_path / "presence")]
    )
    assert where.exit_code == 0
    assert "carol" in where.output

    directory = runner.invoke(cli_app, ["presence", "dir", "--dir", str(tmp_path / "presence")])
    assert str(tmp_path / "presence") in directory.output


def test_cli_session_joins_and_leaves(tmp_path):
    runner = CliRunner()
    shared = tmp_path / "presence"
    result = runner.invoke(
        cli_app,
        ["presence", "session", "--user", "dave", "--hold", "0", "--dir", str(shared)],
    )

    assert result.exit_code == 0
    assert "'joined': True" in result.output
    assert "'left': True" in result.output
    assert list(shared.iterdir()) == []  # no ghost peer left behind


def test_cli_reap_clears_long_abandoned_records(tmp_path):
    import os
    import time

    shared = tmp_path / "presence"
    ghost = presence.PresenceStore(shared, ttl_s=10, user="ghost")
    ghost.join()
    old = time.time() - 10 * presence.REAP_FACTOR - 120
    os.utime(ghost.record_path(), (old, old))

    result = CliRunner().invoke(cli_app, ["presence", "reap", "--dir", str(shared), "--ttl", "10"])
    assert result.exit_code == 0
    assert "'removed': 1" in result.output
    assert list(shared.iterdir()) == []
