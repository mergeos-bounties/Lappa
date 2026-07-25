"""Presence store: discovery, freshness, and the ways a shared folder lies."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import pytest

from lappa import presence
from lappa.presence import NotJoinedError, PresenceStore, PresenceUnavailableError


def store(tmp_path, **kwargs) -> PresenceStore:
    return PresenceStore(tmp_path / "presence", **kwargs)


def age_record(path, seconds: float) -> None:
    """Backdate a record file the way a silent peer would look."""
    now = time.time()
    os.utime(path, (now - seconds, now - seconds))


# --- joining / leaving ------------------------------------------------------
def test_join_creates_one_record_and_lists_self(tmp_path):
    peer = store(tmp_path, user="alice")
    peer.join(package="diff_drive_2w", file="launch/sim.launch.py")

    files = sorted(p.name for p in (tmp_path / "presence").iterdir())
    assert files == [f"peer-{peer.session_id}.json"]

    listed = peer.peers()
    assert len(listed) == 1
    assert listed[0].user == "alice"
    assert listed[0].is_self is True
    assert listed[0].package == "diff_drive_2w"
    assert listed[0].online is True


def test_two_sessions_in_one_directory_see_each_other(tmp_path):
    alice = store(tmp_path, user="alice")
    bob = store(tmp_path, user="bob")
    alice.join(package="pkg_a")
    bob.join(package="pkg_b")

    assert {p.user for p in alice.peers()} == {"alice", "bob"}
    assert alice.peers()[0].is_self is True  # self sorts first
    assert alice.snapshot()["others"] == 1
    assert bob.peers(include_self=False)[0].user == "alice"


def test_leave_removes_the_record(tmp_path):
    peer = store(tmp_path)
    peer.join()
    assert peer.leave() is True
    assert peer.peers() == []
    assert peer.leave() is False  # already gone, still no exception


def test_heartbeat_requires_join(tmp_path):
    with pytest.raises(NotJoinedError):
        store(tmp_path).heartbeat()


def test_touch_does_not_create_a_record_for_a_read_only_client(tmp_path):
    peer = store(tmp_path)
    assert peer.touch(file="README.md") is None
    assert peer.records() == []


def test_partial_heartbeat_keeps_untouched_fields(tmp_path):
    peer = store(tmp_path)
    peer.join(package="diff_drive_2w", file="setup.py", sim=True)
    peer.heartbeat(file="launch/sim.launch.py")

    current = peer.peers()[0]
    assert current.file == "launch/sim.launch.py"
    assert current.package == "diff_drive_2w"  # not wiped by the partial update
    assert current.sim is True

    peer.heartbeat(package=None)
    assert peer.peers()[0].package is None  # explicit None does clear it


def test_heartbeat_refreshes_freshness(tmp_path):
    peer = store(tmp_path, ttl_s=5)
    peer.join()
    record = peer.record_path()
    age_record(record, 60)
    assert peer.peers() == []

    peer.heartbeat()
    assert len(peer.peers()) == 1


# --- freshness --------------------------------------------------------------
def test_record_past_ttl_is_offline_but_kept(tmp_path):
    peer = store(tmp_path, ttl_s=10)
    peer.join()
    age_record(peer.record_path(), 40)

    assert peer.peers() == []
    stale = peer.peers(include_stale=True)
    assert len(stale) == 1
    assert stale[0].online is False
    assert stale[0].age_s == pytest.approx(40, abs=3)


def test_peer_with_a_wrong_clock_stays_visible(tmp_path):
    """A shared drive means unsynced clocks; freshness comes from mtime.

    Bob's machine is ten minutes behind. His record is fresh on disk, so he is
    online, and the disagreement is reported instead of hiding him.
    """
    alice = store(tmp_path, ttl_s=45)
    bob = store(tmp_path, user="bob", clock=lambda: time.time() - 600)
    alice.join()
    bob.join()

    seen = {p.user: p for p in alice.peers()}
    assert set(seen) == {alice.user, "bob"}
    assert seen["bob"].online is True
    assert seen["bob"].clock_skew_s == pytest.approx(-600, abs=5)
    assert seen[alice.user].clock_skew_s == pytest.approx(0, abs=2)


def test_dead_process_on_this_host_is_offline_immediately(tmp_path):
    """A crashed IDE leaves a fresh record behind; the pid gives it away."""
    ghost = store(tmp_path, user="ghost", host="samebox", pid=_dead_pid())
    ghost.join()
    viewer = store(tmp_path, user="viewer", host="samebox")

    assert viewer.peers(include_self=False) == []
    assert viewer.peers(include_stale=True, include_self=False)[0].online is False


def test_dead_pid_on_another_host_is_still_trusted(tmp_path):
    """Pid 999999 on someone else's box says nothing about our process table."""
    remote = store(tmp_path, user="remote", host="otherbox", pid=_dead_pid())
    remote.join()
    viewer = store(tmp_path, user="viewer", host="samebox")

    peers = viewer.peers(include_self=False)
    assert [p.user for p in peers] == ["remote"]
    assert peers[0].online is True


def _dead_pid() -> int:
    """A pid that is definitely not running any more (works on Windows too)."""
    proc = subprocess.Popen([sys.executable, "-c", ""])
    proc.wait()
    return proc.pid


# --- hostile / broken directory contents ------------------------------------
def test_corrupt_record_is_skipped_not_fatal(tmp_path):
    good = store(tmp_path, user="good")
    good.join()
    directory = tmp_path / "presence"
    (directory / "peer-torn.json").write_text('{"user": "half', encoding="utf-8")
    (directory / "peer-empty.json").write_text("", encoding="utf-8")
    (directory / "peer-list.json").write_text("[1, 2, 3]", encoding="utf-8")

    assert [p.user for p in good.peers()] == ["good"]


def test_temp_and_foreign_files_are_not_peers(tmp_path):
    peer = store(tmp_path)
    peer.join()
    directory = tmp_path / "presence"
    (directory / ".peer-abc.json.42.tmp").write_text("{}", encoding="utf-8")
    (directory / "README.txt").write_text("shared folder", encoding="utf-8")
    (directory / "peer-nope.txt").write_text("{}", encoding="utf-8")

    assert len(peer.records()) == 1


def test_write_leaves_no_temp_file_behind(tmp_path):
    peer = store(tmp_path)
    peer.join()
    peer.heartbeat()
    names = [p.name for p in (tmp_path / "presence").iterdir()]
    assert names == [f"peer-{peer.session_id}.json"]


def test_record_is_never_read_half_written(tmp_path):
    """os.replace swaps the file in one step, so a reader sees old or new."""
    peer = store(tmp_path)
    peer.join(package="before")
    raw = json.loads(peer.record_path().read_text(encoding="utf-8"))
    assert raw["package"] == "before"
    peer.heartbeat(package="after")
    raw = json.loads(peer.record_path().read_text(encoding="utf-8"))
    assert raw["package"] == "after"


def test_session_id_cannot_escape_the_directory(tmp_path):
    with pytest.raises(ValueError):
        store(tmp_path, session_id="../../evil")
    with pytest.raises(ValueError):
        store(tmp_path).record_path("peer/../../evil")


def test_missing_directory_reads_as_empty(tmp_path):
    peer = store(tmp_path)
    assert peer.peers() == []
    assert peer.records() == []
    assert peer.reap() == 0
    assert peer.snapshot()["count"] == 0


def test_unwritable_directory_raises_presence_unavailable(tmp_path):
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory", encoding="utf-8")
    peer = PresenceStore(blocker)
    with pytest.raises(PresenceUnavailableError):
        peer.join()


# --- reaping ----------------------------------------------------------------
def test_reap_keeps_recently_stale_records(tmp_path):
    dead = store(tmp_path, ttl_s=10, user="dead")
    dead.join()
    age_record(dead.record_path(), 60)  # offline, but only just
    viewer = store(tmp_path, ttl_s=10)

    assert viewer.reap() == 0
    assert len(viewer.records()) == 1


def test_reap_removes_long_abandoned_records_but_not_our_own(tmp_path):
    old = store(tmp_path, ttl_s=10, user="old")
    old.join()
    age_record(old.record_path(), 10 * presence.REAP_FACTOR + 60)

    viewer = store(tmp_path, ttl_s=10)
    viewer.join()
    assert viewer.reap() == 1
    assert [p.session_id for p in viewer.records()] == [viewer.session_id]


# --- "who has this file open" ----------------------------------------------
def test_peers_on_file_finds_the_other_editor(tmp_path):
    alice = store(tmp_path, user="alice")
    bob = store(tmp_path, user="bob")
    alice.join(package="diff_drive_2w", file="launch/sim.launch.py")
    bob.join(package="diff_drive_2w", file="launch/sim.launch.py")

    others = alice.peers_on_file("launch/sim.launch.py", package="diff_drive_2w")
    assert [p.user for p in others] == ["bob"]  # self excluded by default
    assert len(alice.peers_on_file("launch/sim.launch.py", include_self=True)) == 2


def test_peers_on_file_normalises_separators(tmp_path):
    windows = store(tmp_path, user="win")
    windows.join(package="pkg", file="launch\\sim.launch.py")
    viewer = store(tmp_path, user="viewer")

    assert [p.user for p in viewer.peers_on_file("./launch/sim.launch.py")] == ["win"]


def test_peers_on_file_ignores_other_packages_and_other_files(tmp_path):
    other_pkg = store(tmp_path, user="other_pkg")
    other_file = store(tmp_path, user="other_file")
    other_pkg.join(package="pkg_b", file="setup.py")
    other_file.join(package="pkg_a", file="README.md")
    viewer = store(tmp_path, user="viewer")

    assert viewer.peers_on_file("setup.py", package="pkg_a") == []
    assert [p.user for p in viewer.peers_on_file("setup.py")] == ["other_pkg"]


def test_stale_editor_does_not_raise_a_conflict(tmp_path):
    gone = store(tmp_path, ttl_s=10, user="gone")
    gone.join(package="pkg", file="setup.py")
    age_record(gone.record_path(), 90)
    viewer = store(tmp_path, ttl_s=10)

    assert viewer.peers_on_file("setup.py", package="pkg") == []


# --- directory resolution ---------------------------------------------------
def test_presence_dir_prefers_explicit_then_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LAPPA_PRESENCE_DIR", str(tmp_path / "from_env"))
    assert presence.presence_dir() == tmp_path / "from_env"
    assert presence.presence_dir(tmp_path / "explicit") == tmp_path / "explicit"

    monkeypatch.delenv("LAPPA_PRESENCE_DIR")
    fallback = presence.presence_dir()
    assert fallback.name == "presence"


def test_directory_is_pinned_after_first_use(tmp_path, monkeypatch):
    monkeypatch.setenv("LAPPA_PRESENCE_DIR", str(tmp_path / "first"))
    peer = PresenceStore()
    peer.join()
    monkeypatch.setenv("LAPPA_PRESENCE_DIR", str(tmp_path / "second"))

    peer.heartbeat()  # keeps refreshing the record it created
    assert peer.dir == tmp_path / "first"
    assert (tmp_path / "first" / f"peer-{peer.session_id}.json").is_file()
    assert not (tmp_path / "second").exists()


def test_default_user_uses_env_override(monkeypatch):
    monkeypatch.setenv("LAPPA_USER", "  Anna  ")
    assert presence.default_user() == "Anna"


def test_snapshot_reports_the_shared_directory(tmp_path):
    peer = store(tmp_path, user="alice", ttl_s=30)
    peer.join(package="pkg")
    snap = peer.snapshot()

    assert snap["dir"] == str(tmp_path / "presence")
    assert snap["ttl_s"] == 30
    assert snap["joined"] is True
    assert snap["count"] == 1
    assert snap["peers"][0]["user"] == "alice"
