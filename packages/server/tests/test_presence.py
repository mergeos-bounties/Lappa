import time

import pytest

from lappa.presence import PRESENCE_TTL_S, PresenceStore, _presence_path


@pytest.fixture(autouse=True)
def _clean_presence_file():
    """Remove the shared presence JSON so each test starts fresh."""
    path = _presence_path()
    if path.is_file():
        path.unlink()


def test_generate_peer_id():
    store = PresenceStore()
    assert len(store.peer_id) == 12
    assert store.peer_id.isalnum()


def test_heartbeat_returns_snapshot():
    store = PresenceStore()
    snap = store.heartbeat(peer_name="alice", workspace_name="demo")
    assert snap["my_name"] == "alice"
    assert snap["workspace"] == "demo"
    assert "peers" in snap
    assert "peer_count" in snap
    assert snap["peer_count"] >= 1


def test_leave_removes_peer():
    store = PresenceStore()
    store.heartbeat(peer_name="bob")
    snap_before = store.snapshot()
    assert snap_before["peer_count"] >= 1
    store.leave()
    snap_after = store.snapshot()
    assert snap_after["peer_count"] == 0


def test_peers_expire():
    store = PresenceStore()
    store.heartbeat(peer_name="eve")
    # Fast-forward: set heartbeat to old time AND persist so the file reflects it
    store._last_heartbeat = time.time() - (PRESENCE_TTL_S + 10)
    store._persist()  # writes stale heartbeat to file; cleanup removes it
    snap = store.snapshot()
    assert snap["peer_count"] == 0


def test_multiple_peers():
    store1 = PresenceStore()
    store2 = PresenceStore()
    store1.heartbeat("alpha", "room1")
    store2.heartbeat("beta", "room1")
    snap = store1.snapshot()
    assert snap["peer_count"] >= 2
    names = [p["name"] for p in snap["peers"]]
    assert "alpha" in names
    assert "beta" in names
