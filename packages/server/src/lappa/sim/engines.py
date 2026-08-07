"""Native kinematics simulators (no ROS2 host install required)."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Twist:
    linear_x: float = 0.0
    linear_y: float = 0.0
    angular_z: float = 0.0


@dataclass
class SimState:
    demo: str
    kind: str
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0
    joints: list[float] = field(default_factory=list)
    twist: Twist = field(default_factory=Twist)
    lidar: list[float] = field(default_factory=list)
    t: float = 0.0
    running: bool = False
    collision: bool = False
    mode: str = "native"  # native | docker
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "demo": self.demo,
            "kind": self.kind,
            "x": round(self.x, 4),
            "y": round(self.y, 4),
            "theta": round(self.theta, 4),
            "joints": [round(j, 4) for j in self.joints],
            "twist": {
                "linear_x": self.twist.linear_x,
                "linear_y": self.twist.linear_y,
                "angular_z": self.twist.angular_z,
            },
            "lidar": [round(r, 3) for r in self.lidar],
            "t": round(self.t, 3),
            "running": self.running,
            "collision": self.collision,
            "mode": self.mode,
            "message": self.message,
        }


def _wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


# Simple axis-aligned obstacles in world frame (x, y, half_w, half_h)
DEFAULT_OBSTACLES: list[tuple[float, float, float, float]] = [
    # Bounded mapping room.
    (0.0, 4.0, 4.08, 0.08),
    (0.0, -4.0, 4.08, 0.08),
    (4.0, 0.0, 0.08, 4.08),
    (-4.0, 0.0, 0.08, 4.08),
    (2.0, 0.5, 0.35, 0.35),
    (-1.5, 1.2, 0.4, 0.25),
    (0.8, -1.8, 0.3, 0.5),
    (1.2, 1.5, 0.25, 0.25),
    # Corridor wall stubs for denser lidar scenes
    (-0.2, 2.4, 1.2, 0.15),
    (2.6, -0.8, 0.15, 0.9),
    (0.0, -2.2, 0.2, 0.2),  # pillar_center
    (-2.4, -0.5, 0.35, 0.35),  # ramp_block
    (1.8, -1.6, 0.3, 0.2),  # dock_pad
    (-0.9, 1.8, 0.15, 0.15),  # gate_post
    (0.5, 0.9, 0.28, 0.28),  # cargo_crate
    (-1.8, -1.5, 0.35, 0.2),  # charging_dock
    (2.2, 1.0, 0.4, 0.15),  # shelf_rack
    (1.5, 2.0, 0.3, 0.3),  # barrel_stack
]


def _ray_hit_aabb(
    ox: float,
    oy: float,
    dx: float,
    dy: float,
    cx: float,
    cy: float,
    hx: float,
    hy: float,
    max_r: float,
) -> float | None:
    """Ray vs AABB (center + half extents). Return distance or None."""
    inv_dx = 1e9 if abs(dx) < 1e-9 else 1.0 / dx
    inv_dy = 1e9 if abs(dy) < 1e-9 else 1.0 / dy
    tx1 = (cx - hx - ox) * inv_dx
    tx2 = (cx + hx - ox) * inv_dx
    ty1 = (cy - hy - oy) * inv_dy
    ty2 = (cy + hy - oy) * inv_dy
    tmin = max(min(tx1, tx2), min(ty1, ty2))
    tmax = min(max(tx1, tx2), max(ty1, ty2))
    if tmax < 0 or tmin > tmax:
        return None
    t = tmin if tmin >= 0 else tmax
    if t < 0 or t > max_r:
        return None
    return t


def _lidar_scan(
    x: float,
    y: float,
    theta: float,
    n: int = 36,
    max_range: float = 3.0,
    obstacles: list[tuple[float, float, float, float]] | None = None,
) -> list[float]:
    """Synthetic 2D lidar: free-space ring shortened by AABB obstacle hits."""
    obs = obstacles if obstacles is not None else DEFAULT_OBSTACLES
    ranges: list[float] = []
    for i in range(n):
        ang = theta + (2 * math.pi * i / n)
        dx, dy = math.cos(ang), math.sin(ang)
        hit = max_range
        for cx, cy, hx, hy in obs:
            d = _ray_hit_aabb(x, y, dx, dy, cx, cy, hx, hy, max_range)
            if d is not None and d < hit:
                hit = d
        ranges.append(hit)
    return ranges


def _circle_hits_aabb(
    x: float,
    y: float,
    radius: float,
    obstacle: tuple[float, float, float, float],
) -> bool:
    cx, cy, half_w, half_h = obstacle
    nearest_x = max(cx - half_w, min(x, cx + half_w))
    nearest_y = max(cy - half_h, min(y, cy + half_h))
    return (x - nearest_x) ** 2 + (y - nearest_y) ** 2 < radius**2


class BaseEngine:
    kind = "base"
    lidar_rays = 36
    lidar_range = 3.0
    robot_radius = 0.2

    def __init__(self, demo: str):
        self.state = SimState(demo=demo, kind=self.kind)
        self._last = time.monotonic()
        self.obstacles = list(DEFAULT_OBSTACLES)

    def set_cmd(self, linear_x: float = 0.0, linear_y: float = 0.0, angular_z: float = 0.0) -> None:
        self.state.twist = Twist(linear_x, linear_y, angular_z)

    def step(self, dt: float | None = None) -> SimState:
        """Advance simulation.

        ``dt`` is seconds. When omitted, uses wall-clock since last step.
        On Windows / tight GUI loops the measured delta can be ~0; we floor to
        1/60s while running so teleop and tests always integrate motion.
        """
        now = time.monotonic()
        if dt is None:
            measured = min(0.1, max(0.0, now - self._last))
            # Burst ticks (Qt timer + processEvents, unit tests) can yield ~0.
            if self.state.running and measured < 1e-4:
                measured = 1.0 / 60.0
            dt = measured
        else:
            dt = min(0.1, max(0.0, float(dt)))
        self._last = now
        if self.state.running:
            self._integrate(dt)
            self.state.t += dt
            self.state.lidar = _lidar_scan(
                self.state.x,
                self.state.y,
                self.state.theta,
                n=self.lidar_rays,
                max_range=self.lidar_range,
                obstacles=self.obstacles,
            )
        return self.state

    def _integrate(self, dt: float) -> None:
        raise NotImplementedError

    def _pose_is_clear(self, x: float, y: float) -> bool:
        return not any(
            _circle_hits_aabb(x, y, self.robot_radius, obstacle) for obstacle in self.obstacles
        )

    def reset(self) -> None:
        demo, kind = self.state.demo, self.state.kind
        mode = self.state.mode
        self.state = SimState(demo=demo, kind=kind, mode=mode)
        self._last = time.monotonic()


class DiffDrive2W(BaseEngine):
    kind = "diff_drive_2w"

    def __init__(self, demo: str):
        super().__init__(demo)
        self.state.joints = [0.0, 0.0]  # left, right wheel angles (rad)

    def _integrate(self, dt: float) -> None:
        v = self.state.twist.linear_x
        w = self.state.twist.angular_z
        th = self.state.theta
        self.state.x += v * math.cos(th) * dt
        self.state.y += v * math.sin(th) * dt
        self.state.theta = _wrap(th + w * dt)
        # wheel odometry spin for 3D viz (track ~0.32 m, r=0.05)
        track, r = 0.32, 0.05
        v_l = v - w * track / 2
        v_r = v + w * track / 2
        self.state.joints[0] = _wrap(self.state.joints[0] + (v_l / r) * dt)
        self.state.joints[1] = _wrap(self.state.joints[1] + (v_r / r) * dt)


class Omni3W(BaseEngine):
    kind = "omni_3w"

    def __init__(self, demo: str):
        super().__init__(demo)
        self.state.joints = [0.0, 0.0, 0.0]

    def _integrate(self, dt: float) -> None:
        vx = self.state.twist.linear_x
        vy = self.state.twist.linear_y
        w = self.state.twist.angular_z
        th = self.state.theta
        c, s = math.cos(th), math.sin(th)
        self.state.x += (c * vx - s * vy) * dt
        self.state.y += (s * vx + c * vy) * dt
        self.state.theta = _wrap(th + w * dt)
        r = 0.04
        for i in range(3):
            # approximate wheel spin from planar speed magnitude
            self.state.joints[i] = _wrap(
                self.state.joints[i]
                + (math.hypot(vx, vy) + abs(w) * 0.12) / r * dt * (1 if i % 2 == 0 else -1)
            )


class Tricycle3W(BaseEngine):
    kind = "tricycle_3w"
    lidar_rays = 180
    lidar_range = 8.0
    robot_radius = 0.22

    def __init__(self, demo: str):
        super().__init__(demo)
        self.state.joints = [0.0, 0.0, 0.0]

    def _integrate(self, dt: float) -> None:
        # linear_x = speed, angular_z treated as steering rate → curvature
        v = self.state.twist.linear_x
        steer = max(-0.75, min(0.75, self.state.twist.angular_z))
        L = 0.35  # wheelbase
        th = self.state.theta
        next_x = self.state.x + v * math.cos(th) * dt
        next_y = self.state.y + v * math.sin(th) * dt
        next_theta = _wrap(th + (v / L) * math.tan(steer) * dt)
        self.state.joints[0] = steer
        if not self._pose_is_clear(next_x, next_y):
            self.state.collision = True
            self.state.message = "footprint blocked by obstacle"
            return
        self.state.collision = False
        self.state.message = "native sim running"
        self.state.x = next_x
        self.state.y = next_y
        self.state.theta = next_theta
        wheel_delta = (v / 0.13) * dt
        self.state.joints[1] = _wrap(self.state.joints[1] + wheel_delta)
        self.state.joints[2] = _wrap(self.state.joints[2] + wheel_delta)


class Ackermann4W(BaseEngine):
    kind = "ackermann_4w"

    def _integrate(self, dt: float) -> None:
        v = self.state.twist.linear_x
        delta = max(-0.7, min(0.7, self.state.twist.angular_z))
        L = 0.5
        th = self.state.theta
        self.state.x += v * math.cos(th) * dt
        self.state.y += v * math.sin(th) * dt
        self.state.theta = _wrap(th + (v / L) * math.tan(delta) * dt)


class SimpleArm(BaseEngine):
    kind = "simple_arm"

    def __init__(self, demo: str):
        super().__init__(demo)
        self.state.joints = [0.4, -0.6]
        self.state.x = 0.0
        self.state.y = 0.0

    def _integrate(self, dt: float) -> None:
        # twist.linear_x / angular_z drive joint velocities
        j0 = self.state.joints[0] + self.state.twist.linear_x * dt
        j1 = self.state.joints[1] + self.state.twist.angular_z * dt
        self.state.joints = [
            max(-2.5, min(2.5, j0)),
            max(-2.5, min(2.5, j1)),
        ]
        # FK tip for canvas
        l1, l2 = 0.6, 0.5
        self.state.x = l1 * math.cos(self.state.joints[0]) + l2 * math.cos(
            self.state.joints[0] + self.state.joints[1]
        )
        self.state.y = l1 * math.sin(self.state.joints[0]) + l2 * math.sin(
            self.state.joints[0] + self.state.joints[1]
        )


class Mecanum4W(BaseEngine):
    """Holonomic mecanum base: independent vx, vy, yaw (tracked-style demo id alias)."""

    kind = "mecanum_4w"

    def __init__(self, demo: str):
        super().__init__(demo)
        self.state.joints = [0.0, 0.0, 0.0, 0.0]  # FL FR RL RR wheel spins
        self.state.message = "mecanum holonomic"

    def _integrate(self, dt: float) -> None:
        vx = self.state.twist.linear_x
        vy = self.state.twist.linear_y
        w = self.state.twist.angular_z
        th = self.state.theta
        c, s = math.cos(th), math.sin(th)
        # body → world
        self.state.x += (c * vx - s * vy) * dt
        self.state.y += (s * vx + c * vy) * dt
        self.state.theta = _wrap(th + w * dt)
        r = 0.05
        # inverse kinematics-ish wheel rates for viz
        lx, ly = 0.2, 0.18  # half length / width
        wheels = [
            vx - vy - (lx + ly) * w,  # FL
            vx + vy + (lx + ly) * w,  # FR
            vx + vy - (lx + ly) * w,  # RL
            vx - vy + (lx + ly) * w,  # RR
        ]
        for i, wi in enumerate(wheels):
            self.state.joints[i] = _wrap(self.state.joints[i] + (wi / r) * dt)


ENGINES: dict[str, type[BaseEngine]] = {
    "diff_drive_2w": DiffDrive2W,
    "omni_3w": Omni3W,
    "tricycle_3w": Tricycle3W,
    "ackermann_4w": Ackermann4W,
    "simple_arm": SimpleArm,
    "mecanum_4w": Mecanum4W,
    "tracked_base": Mecanum4W,  # alias for tracked-style holonomic demos
}


def create_engine(demo_id: str) -> BaseEngine:
    cls = ENGINES.get(demo_id, DiffDrive2W)
    return cls(demo_id)
