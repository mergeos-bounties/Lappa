"""Active sim session + hot-reload bookkeeping."""

from __future__ import annotations

import itertools
import threading
import time
from pathlib import Path
from typing import Any

from lappa.export.csv import trajectory_csv_text
from lappa.package_loader import RosPackage, load_package
from lappa.sim.engines import BaseEngine, create_engine


class SimSession:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.engine: BaseEngine | None = None
        self.package: RosPackage | None = None
        self.hot_reload = True
        self.reload_count = 0
        self.last_reload_at: float | None = None
        self.logs: list[str] = []
        self.trajectory: list[dict[str, Any]] = []
        self._stop_watch = threading.Event()
        self._watch_thread: threading.Thread | None = None
        self._mtimes: dict[str, float] = {}

    def log(self, msg: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        self.logs.append(line)
        if len(self.logs) > 300:
            self.logs = self.logs[-300:]

    def start(self, demo_id: str, package_path: Path | None = None) -> dict[str, Any]:
        with self._lock:
            self.stop_watch_unlocked()
            self.engine = create_engine(demo_id)
            self.engine.state.running = True
            self.engine.state.message = "native sim running"
            self.trajectory = []
            if package_path:
                self.package = load_package(package_path)
            self.log(f"sim start demo={demo_id} mode=native")
            if self.hot_reload and self.package:
                self.start_watch_unlocked()
            return self.status_unlocked()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if self.engine:
                self.engine.state.running = False
                self.engine.state.message = "stopped"
            self.stop_watch_unlocked()
            self.log("sim stop")
            return self.status_unlocked()

    def cmd(self, linear_x: float = 0.0, linear_y: float = 0.0, angular_z: float = 0.0) -> dict:
        with self._lock:
            if not self.engine:
                return {"ok": False, "error": "no session"}
            self.engine.set_cmd(linear_x, linear_y, angular_z)
            return {"ok": True, "twist": self.engine.state.twist.__dict__}

    def trajectory_stats(self) -> dict[str, Any]:
        """Summary metrics for the recorded native-sim trajectory."""
        with self._lock:
            return self.trajectory_stats_unlocked()

    def trajectory_stats_unlocked(self) -> dict[str, Any]:
        rows = list(self.trajectory)
        if not rows:
            return {
                "points": 0,
                "distance_m": 0.0,
                "duration_s": 0.0,
                "avg_speed_mps": 0.0,
                "max_speed_mps": 0.0,
                "net_displacement_m": 0.0,
                "path_efficiency": 0.0,
                "idle_time_s": 0.0,
            }
        dist = 0.0
        max_seg = 0.0
        idle = 0.0
        for a, b in itertools.pairwise(rows):
            dx = float(b.get("x", 0) - a.get("x", 0))
            dy = float(b.get("y", 0) - a.get("y", 0))
            seg = (dx * dx + dy * dy) ** 0.5
            dt = max(1e-6, float(b.get("t", 0) - a.get("t", 0)))
            max_seg = max(max_seg, seg / dt)
            dist += seg
            # count time with near-zero motion as idle
            if seg / dt < 0.02:
                idle += dt
        t0 = float(rows[0].get("t", 0))
        t1 = float(rows[-1].get("t", 0))
        duration = max(0.0, t1 - t0)
        avg_speed = dist / duration if duration > 1e-6 else 0.0
        ndx = float(rows[-1].get("x", 0) - rows[0].get("x", 0))
        ndy = float(rows[-1].get("y", 0) - rows[0].get("y", 0))
        net = (ndx * ndx + ndy * ndy) ** 0.5
        efficiency = (net / dist) if dist > 1e-9 else 0.0
        return {
            "points": len(rows),
            "distance_m": round(dist, 4),
            "duration_s": round(duration, 4),
            "avg_speed_mps": round(avg_speed, 4),
            "max_speed_mps": round(max_seg, 4),
            "net_displacement_m": round(net, 4),
            "path_efficiency": round(efficiency, 4),
            "idle_time_s": round(idle, 4),
            "demo": rows[-1].get("demo"),
        }

    def tick(self) -> dict[str, Any]:

        with self._lock:
            if not self.engine:
                return {"running": False}
            st = self.engine.step()
            row = {
                "t": round(st.t, 4),
                "x": round(st.x, 6),
                "y": round(st.y, 6),
                "theta": round(st.theta, 6),
                "linear_x": st.twist.linear_x,
                "linear_y": st.twist.linear_y,
                "angular_z": st.twist.angular_z,
                "demo": st.demo,
            }
            self.trajectory.append(row)
            if len(self.trajectory) > 5000:
                self.trajectory = self.trajectory[-5000:]
            result = st.to_dict()
            result["obstacles"] = [list(obstacle) for obstacle in self.engine.obstacles]
            return result

    def status(self) -> dict[str, Any]:
        with self._lock:
            return self.status_unlocked()

    def status_unlocked(self) -> dict[str, Any]:
        st = self.engine.state.to_dict() if self.engine else {"running": False}
        traj = self.trajectory_stats_unlocked() if self.trajectory else {"points": 0}
        return {
            "state": st,
            "package": self.package.to_dict() if self.package else None,
            "hot_reload": self.hot_reload,
            "reload_count": self.reload_count,
            "last_reload_at": self.last_reload_at,
            "trajectory_points": len(self.trajectory),
            "trajectory_stats": traj,
            "logs": self.logs[-40:],
        }

    def trajectory_csv(self) -> str:
        with self._lock:
            lines = ["t,x,y,theta,linear_x,linear_y,angular_z,demo"]
            for r in self.trajectory:
                lines.append(
                    f"{r['t']},{r['x']},{r['y']},{r['theta']},"
                    f"{r['linear_x']},{r['linear_y']},{r['angular_z']},{r['demo']}"
                )
            return "\n".join(lines) + ("\n" if lines else "")

    def trajectory_rich_csv(self) -> str:
        with self._lock:
            return trajectory_csv_text(self.trajectory)

    def clear_trajectory(self) -> None:
        with self._lock:
            self.trajectory = []

    def notify_file_change(self, rel: str) -> None:
        with self._lock:
            if not self.hot_reload or not self.engine:
                return
            self.reload_count += 1
            self.last_reload_at = time.time()
            self.engine.state.message = f"hot-reload #{self.reload_count}: {rel}"
            self.log(f"hot-reload {rel}")
            # Soft restart kinematics but keep pose for mobile bases
            if self.engine.state.kind == "simple_arm":
                pass
            else:
                # brief flash message only; continuous motion
                pass

    def start_watch_unlocked(self) -> None:
        self.stop_watch_unlocked()
        if not self.package:
            return
        root = self.package.path
        self._mtimes = {}
        for p in root.rglob("*"):
            if p.is_file():
                try:
                    self._mtimes[str(p)] = p.stat().st_mtime
                except OSError:
                    pass
        self._stop_watch.clear()

        def loop() -> None:
            while not self._stop_watch.wait(0.5):
                if not self.package:
                    continue
                for p in self.package.path.rglob("*"):
                    if not p.is_file():
                        continue
                    key = str(p)
                    try:
                        m = p.stat().st_mtime
                    except OSError:
                        continue
                    prev = self._mtimes.get(key)
                    if prev is None:
                        self._mtimes[key] = m
                        continue
                    if m > prev:
                        self._mtimes[key] = m
                        rel = p.relative_to(self.package.path).as_posix()
                        self.notify_file_change(rel)

        self._watch_thread = threading.Thread(target=loop, daemon=True)
        self._watch_thread.start()
        self.log("hot-reload watch started")

    def stop_watch_unlocked(self) -> None:
        self._stop_watch.set()
        self._watch_thread = None


SESSION = SimSession()
