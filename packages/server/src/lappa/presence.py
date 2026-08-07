"""Collaborative workspace presence — optional peer awareness.

Tracks who is active in a workspace and provides a lightweight
presence API so multiple Lappa IDE instances can discover each
other on the same LAN or via a shared signal server.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from lappa.config import WORKSPACES, ensure_dirs

PRESENCE_FILE = "presence.json"
PRESENCE_TTL_S = 120  # peers expire after 2 min without heartbeat
CLEANUP_INTERVAL_S = 30


def _presence_path() -> Path:
    ensure_dirs()
    return WORKSPACES / PRESENCE_FILE


def _generate_peer_id() -> str:
    return uuid.uuid4().hex[:12]


class PresenceStore:
    """Thread-safe presence registry backed by a shared JSON file."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._peer_id: str = _generate_peer_id()
        self._peer_name: str = ""
        self._workspace_name: str = ""
        self._last_heartbeat: float = 0.0

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    @property
    def peer_id(self) -> str:
        return self._peer_id

    def heartbeat(self, peer_name: str = "", workspace_name: str = "") -> dict[str, Any]:
        """Register or refresh this peer. Returns full presence snapshot."""
        with self._lock:
            self._peer_name = peer_name or self._peer_name
            self._workspace_name = workspace_name or self._workspace_name
            self._last_heartbeat = time.time()
            self._persist()
            return self.snapshot()

    def leave(self) -> dict[str, Any]:
        """Remove this peer and persist."""
        with self._lock:
            self._remove_peer(self._peer_id)
            return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        """Return current peers (including self) and workspace metadata."""
        with self._lock:
            data = self._load()
            now = time.time()
            peers: list[dict[str, Any]] = []
            for pid, entry in data.get("peers", {}).items():
                age = now - entry.get("heartbeat", 0)
                if age < PRESENCE_TTL_S:
                    peers.append(
                        {
                            "peer_id": pid,
                            "name": entry.get("name", ""),
                            "workspace": entry.get("workspace", ""),
                            "age_s": round(age, 1),
                        }
                    )
            peers.sort(key=lambda p: p["name"] or p["peer_id"])
            return {
                "my_peer_id": self._peer_id,
                "my_name": self._peer_name,
                "workspace": self._workspace_name,
                "peers": peers,
                "peer_count": len(peers),
            }

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------
    def _load(self) -> dict[str, Any]:
        path = _presence_path()
        if not path.is_file():
            return {"peers": {}}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"peers": {}}

    def _persist(self) -> None:
        data = self._load()
        data.setdefault("peers", {})[self._peer_id] = {
            "name": self._peer_name,
            "workspace": self._workspace_name,
            "heartbeat": self._last_heartbeat,
        }
        # Cleanup stale peers
        now = time.time()
        stale = [
            pid
            for pid, entry in data["peers"].items()
            if now - entry.get("heartbeat", 0) >= PRESENCE_TTL_S
        ]
        for pid in stale:
            del data["peers"][pid]
        _presence_path().parent.mkdir(parents=True, exist_ok=True)
        _presence_path().write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def _remove_peer(self, peer_id: str) -> None:
        data = self._load()
        data.get("peers", {}).pop(peer_id, None)
        _presence_path().parent.mkdir(parents=True, exist_ok=True)
        _presence_path().write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


# Module-level singleton for the API layer.
PRESENCE = PresenceStore()
