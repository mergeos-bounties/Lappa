"""Lightweight presence for multi-user Lappa workspaces.

No server, no ports, no extra dependency: every peer writes one small JSON
record into a shared *presence directory* and refreshes it on a heartbeat.
Listing that directory is the whole discovery protocol, so presence works the
same way a shared workspace already works -- on one machine (several IDE
processes) or on a network share that several people have mounted.

Freshness is judged from the record file's mtime *as this machine sees it*,
not from the timestamp inside the record.  On a shared drive the peers'
wall clocks disagree, and a peer whose clock runs a few minutes behind would
otherwise look permanently offline to everybody else.  The writer's own clock
is still stored so the UI can report the skew instead of hiding the peer.

Presence is advisory.  It never blocks an edit and never holds a lock: it
answers "who else is in here right now", which is what the IDE needs before it
silently overwrites somebody's save.
"""

from __future__ import annotations

import getpass
import json
import os
import re
import socket
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from lappa.config import WORKSPACES, ensure_dirs

RECORD_VERSION = 1
RECORD_PREFIX = "peer-"
RECORD_SUFFIX = ".json"

#: A peer is "online" while its record has been refreshed inside this window.
DEFAULT_TTL_S = 45.0
#: Suggested refresh interval for clients (a third of the TTL: two missed
#: heartbeats still leave the peer online, so a slow share does not blink).
HEARTBEAT_S = 15.0
#: Records older than ``TTL * REAP_FACTOR`` belong to a session that died
#: without leaving; only then is the file removed.
REAP_FACTOR = 10

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_MAX_TEXT = 200


class PresenceError(RuntimeError):
    """Base class for presence failures."""


class NotJoinedError(PresenceError):
    """Raised when a heartbeat/leave is attempted before joining."""


class PresenceUnavailableError(PresenceError):
    """Raised when the presence directory cannot be written to."""


@dataclass
class Peer:
    """One session seen in the presence directory."""

    session_id: str
    user: str = "anonymous"
    host: str = ""
    pid: int = 0
    package: str | None = None
    file: str | None = None
    sim: bool = False
    joined_at: float = 0.0
    seen_at: float = 0.0
    age_s: float = 0.0
    online: bool = True
    is_self: bool = False
    clock_skew_s: float = 0.0
    version: int = RECORD_VERSION
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["age_s"] = round(self.age_s, 3)
        data["clock_skew_s"] = round(self.clock_skew_s, 3)
        return data

    def label(self) -> str:
        return f"{self.user}@{self.host}" if self.host else self.user


def _text(value: Any, limit: int = _MAX_TEXT) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit]


def default_user() -> str:
    env = _text(os.environ.get("LAPPA_USER"), 64)
    if env:
        return env
    try:
        return _text(getpass.getuser(), 64) or "anonymous"
    except (OSError, KeyError):  # pragma: no cover - no user db (slim containers)
        return "anonymous"


def default_host() -> str:
    env = _text(os.environ.get("LAPPA_HOST"), 64)
    if env:
        return env
    try:
        return _text(socket.gethostname(), 64) or ""
    except OSError:  # pragma: no cover - hostname lookup is best effort
        return ""


def presence_dir(explicit: str | Path | None = None) -> Path:
    """Resolve the directory peers share.

    ``LAPPA_PRESENCE_DIR`` wins, then ``<first workspace root>/.lappa/presence``
    (the workspace root is the thing collaborators already share), then a
    per-user fallback so a workspace-less install still works.
    """
    if explicit:
        return Path(explicit).expanduser()
    env = _text(os.environ.get("LAPPA_PRESENCE_DIR"), 4096)
    if env:
        return Path(env).expanduser()
    from lappa import workspace as workspace_store  # local import: avoids a cycle

    roots = workspace_store.workspace_roots()
    if roots:
        return roots[0] / ".lappa" / "presence"
    ensure_dirs()
    return WORKSPACES / "presence"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return True  # unknown pid: assume alive, TTL still applies
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True
    return True


class PresenceStore:
    """Read/write access to one presence directory."""

    def __init__(
        self,
        directory: str | Path | None = None,
        *,
        ttl_s: float = DEFAULT_TTL_S,
        session_id: str | None = None,
        user: str | None = None,
        host: str | None = None,
        pid: int | None = None,
        clock=time.time,
    ) -> None:
        self._explicit_dir = directory
        self._dir: Path | None = None
        self.ttl_s = float(ttl_s) if ttl_s and ttl_s > 0 else DEFAULT_TTL_S
        self.session_id = self._check_session_id(session_id or uuid4().hex[:12])
        self.user = _text(user, 64) or default_user()
        self.host = _text(host, 64) if host is not None else default_host()
        self.pid = int(pid) if pid is not None else os.getpid()
        self._clock = clock
        self._joined = False
        self._state: dict[str, Any] = {}

    # --- helpers ---------------------------------------------------------
    @property
    def dir(self) -> Path:
        """Presence directory, resolved once and then pinned.

        Resolution is deferred so importing ``lappa.presence`` does not read
        workspace state, and pinned so a session that joined keeps refreshing
        the record it created even if the active workspace changes underneath.
        """
        if self._dir is None:
            self._dir = Path(presence_dir(self._explicit_dir))
        return self._dir

    @staticmethod
    def _check_session_id(session_id: str) -> str:
        text = str(session_id).strip()
        if not _SESSION_ID_RE.match(text):
            # A session id becomes a file name; anything path-ish is refused
            # rather than sanitised, so a bad id can never point outside the dir.
            raise ValueError(f"invalid session id: {session_id!r}")
        return text

    def record_path(self, session_id: str | None = None) -> Path:
        sid = self._check_session_id(session_id or self.session_id)
        return self.dir / f"{RECORD_PREFIX}{sid}{RECORD_SUFFIX}"

    @property
    def joined(self) -> bool:
        return self._joined

    def _write(self, data: dict[str, Any]) -> dict[str, Any]:
        path = self.record_path()
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = self.dir / f".{path.name}.{self.pid}.tmp"
            tmp.write_text(json.dumps(data), encoding="utf-8")
            os.replace(tmp, path)  # atomic: readers never see a half record
        except OSError as exc:
            raise PresenceUnavailableError(f"{self.dir}: {exc}") from exc
        return dict(data)

    # --- writing ---------------------------------------------------------
    def join(
        self,
        *,
        package: str | None = None,
        file: str | None = None,
        sim: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = float(self._clock())
        self._state = {
            "version": RECORD_VERSION,
            "session_id": self.session_id,
            "user": self.user,
            "host": self.host,
            "pid": self.pid,
            "package": _text(package),
            "file": _text(file, 512),
            "sim": bool(sim),
            "joined_at": now,
            "seen_at": now,
            "extra": dict(extra or {}),
        }
        self._joined = True
        return self._write(self._state)

    def heartbeat(self, **fields: Any) -> dict[str, Any]:
        """Refresh this session's record, optionally updating fields.

        Passing ``package=None`` explicitly clears the field; omitting it keeps
        the previous value (the IDE sends partial updates).
        """
        if not self._joined:
            raise NotJoinedError("join() before heartbeat()")
        for key in ("package", "file", "sim", "extra"):
            if key in fields:
                value = fields[key]
                if key == "sim":
                    self._state[key] = bool(value)
                elif key == "extra":
                    self._state[key] = dict(value or {})
                else:
                    self._state[key] = _text(value, 512 if key == "file" else _MAX_TEXT)
        self._state["seen_at"] = float(self._clock())
        return self._write(self._state)

    def touch(self, **fields: Any) -> dict[str, Any] | None:
        """Heartbeat if this session joined, otherwise do nothing.

        Read-only clients (a status poll, a CI run) must not materialise a
        presence record just by touching a file.
        """
        if not self._joined:
            return None
        try:
            return self.heartbeat(**fields)
        except PresenceUnavailableError:
            return None

    def leave(self) -> bool:
        if not self._joined:
            return False
        self._joined = False
        try:
            self.record_path().unlink()
        except FileNotFoundError:
            return False
        except OSError as exc:  # pragma: no cover - share went away mid-session
            raise PresenceUnavailableError(f"{self.dir}: {exc}") from exc
        return True

    # --- reading ---------------------------------------------------------
    def _read_record(self, path: Path) -> Peer | None:
        try:
            stat = path.stat()
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None  # peer left while we were listing
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return None  # torn or foreign file: ignore, never crash the IDE
        if not isinstance(raw, dict):
            return None

        session_id = _text(raw.get("session_id"), 64) or path.stem[len(RECORD_PREFIX) :]
        seen_at = raw.get("seen_at")
        seen_at = float(seen_at) if isinstance(seen_at, int | float) else 0.0
        joined_at = raw.get("joined_at")
        joined_at = float(joined_at) if isinstance(joined_at, int | float) else seen_at
        pid = raw.get("pid")
        pid = int(pid) if isinstance(pid, int) else 0
        host = _text(raw.get("host"), 64) or ""
        age = max(0.0, float(self._clock()) - stat.st_mtime)

        online = age <= self.ttl_s
        if online and host and host == self.host and not _pid_alive(pid):
            # Same machine, process gone: the IDE crashed without leaving.
            # Only trusted on our own host -- a pid from another box means
            # nothing here.  A recycled pid errs toward showing the peer.
            online = False

        return Peer(
            session_id=session_id,
            user=_text(raw.get("user"), 64) or "anonymous",
            host=host,
            pid=pid,
            package=_text(raw.get("package")),
            file=_text(raw.get("file"), 512),
            sim=bool(raw.get("sim")),
            joined_at=joined_at,
            seen_at=seen_at,
            age_s=age,
            online=online,
            is_self=session_id == self.session_id,
            clock_skew_s=(seen_at - stat.st_mtime) if seen_at else 0.0,
            version=int(raw.get("version") or RECORD_VERSION),
            extra=raw.get("extra") if isinstance(raw.get("extra"), dict) else {},
        )

    def records(self) -> list[Peer]:
        """Every readable record, stale ones included."""
        if not self.dir.is_dir():
            return []
        peers: list[Peer] = []
        try:
            entries = sorted(self.dir.iterdir())
        except OSError:
            return []
        for path in entries:
            name = path.name
            if name.startswith(".") or not name.startswith(RECORD_PREFIX):
                continue
            if not name.endswith(RECORD_SUFFIX):
                continue
            peer = self._read_record(path)
            if peer:
                peers.append(peer)
        peers.sort(key=lambda p: (not p.is_self, p.user.lower(), p.session_id))
        return peers

    def peers(self, *, include_stale: bool = False, include_self: bool = True) -> list[Peer]:
        out = []
        for peer in self.records():
            if not include_stale and not peer.online:
                continue
            if not include_self and peer.is_self:
                continue
            out.append(peer)
        return out

    def peers_on_file(
        self,
        file: str,
        *,
        package: str | None = None,
        include_self: bool = False,
    ) -> list[Peer]:
        """Who else currently has *file* open (same package, if given)."""
        target = _text(file, 512)
        if not target:
            return []
        wanted = target.replace("\\", "/").lstrip("./")
        pkg = _text(package)
        out = []
        for peer in self.peers(include_self=include_self):
            if not peer.file:
                continue
            if peer.file.replace("\\", "/").lstrip("./") != wanted:
                continue
            if pkg and peer.package and peer.package != pkg:
                continue
            out.append(peer)
        return out

    def reap(self, *, force: bool = False) -> int:
        """Delete records left behind by sessions that died long ago.

        Stale-but-recent records are kept: a peer on a laggy share is offline,
        not gone, and deleting its file would make it re-appear as a brand new
        session on the next heartbeat.
        """
        if not self.dir.is_dir():
            return 0
        cutoff = self.ttl_s * REAP_FACTOR
        removed = 0
        for peer in self.records():
            if peer.is_self and not force:
                continue
            if peer.age_s < cutoff and not force:
                continue
            try:
                self.record_path(peer.session_id).unlink()
                removed += 1
            except (FileNotFoundError, ValueError):
                continue  # already gone, or a name we refuse to touch
            except OSError:
                continue
        return removed

    def snapshot(self, *, include_stale: bool = False) -> dict[str, Any]:
        peers = self.peers(include_stale=include_stale)
        return {
            "dir": str(self.dir),
            "ttl_s": self.ttl_s,
            "heartbeat_s": HEARTBEAT_S,
            "session_id": self.session_id,
            "joined": self._joined,
            "user": self.user,
            "host": self.host,
            "peers": [p.to_dict() for p in peers],
            "count": len(peers),
            "others": sum(1 for p in peers if not p.is_self),
        }


#: Process-wide store used by the API/GUI so one IDE process is one peer.
SESSION_PRESENCE = PresenceStore()


def reset_session_presence(directory: str | Path | None = None, **kwargs: Any) -> PresenceStore:
    """Point the process-wide store at another directory (tests, GUI restart)."""
    global SESSION_PRESENCE
    if SESSION_PRESENCE.joined:
        try:
            SESSION_PRESENCE.leave()
        except PresenceError:  # pragma: no cover - best effort
            pass
    SESSION_PRESENCE = PresenceStore(directory, **kwargs)
    return SESSION_PRESENCE
