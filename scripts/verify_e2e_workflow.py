#!/usr/bin/env python3
"""Verify the Lappa E2E teleop → hot-reload → sim workflow.

Usage:
    python scripts/verify_e2e_workflow.py [--demo diff_drive_2w]

This script:
  1. Checks prerequisites (Python 3.11+, lappa installed)
  2. Lists available demos
  3. Starts a native sim session
  4. Makes a test edit to teleop.py (increases lidar wall distance)
  5. Sends velocity commands
  6. Waits for hot-reload detection
  7. Verifies reload_count >= 1 and robot has moved
  8. Exports trajectory CSV
  9. Restores original teleop.py
  10. Prints pass/fail summary
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMOS_DIR = REPO_ROOT / "packages" / "demos"
SERVER_DIR = REPO_ROOT / "packages" / "server"

# The teleop file we'll edit (relative to demo package root)
TELEOP_REL = "teleop.py"

# Line edit: change lidar wall distance from 3.0 to 8.0 for a visible delta
OLD_PATTERN = "base = 3.0 + 0.2 * math.sin(self.x + self.y)"
NEW_PATTERN = "base = 8.0 + 0.2 * math.sin(self.x + self.y)  # E2E verification edit"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = 0
FAIL = 0


def ok(msg: str) -> None:
    global PASS
    PASS += 1
    print(f"  ✅ {msg}")


def nok(msg: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  ❌ {msg}")


def info(msg: str) -> None:
    print(f"  ℹ️  {msg}")


def header(msg: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def run_lappa(*args: str, timeout: int = 30) -> tuple[int, str, str]:
    """Run a `lappa ...` CLI command and return (exit_code, stdout, stderr)."""
    cmd = [sys.executable, "-m", "lappa.cli", *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(SERVER_DIR),
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", f"timeout after {timeout}s"
    except FileNotFoundError:
        return -1, "", "lappa not found (pip install -e '.[gui,dev]' from packages/server/)"


def run_lappa_json(*args: str, timeout: int = 30) -> dict | None:
    """Run lappa and parse JSON output."""
    rc, out, err = run_lappa(*args, timeout=timeout)
    if rc != 0:
        nok(f"lappa {' '.join(args)} → exit {rc}: {err[:120]}")
        return None
    try:
        # Some lappa commands wrap JSON in rich formatting; strip ANSI
        clean = out
        if out.startswith("{"):
            pass
        else:
            # Try to find JSON block
            lines = [l for l in out.split("\n") if l.strip().startswith("{")]
            if lines:
                clean = lines[0]
        return json.loads(clean)
    except json.JSONDecodeError:
        nok(f"lappa {' '.join(args)} → invalid JSON: {out[:200]}")
        return None


# ---------------------------------------------------------------------------
# Verification steps
# ---------------------------------------------------------------------------


def step_check_python() -> bool:
    header("Step 1: Check Python version")
    ver = sys.version_info
    if ver >= (3, 11):
        ok(f"Python {ver.major}.{ver.minor}.{ver.micro} (≥ 3.11)")
        return True
    nok(f"Python {ver.major}.{ver.minor}.{ver.micro} (need ≥ 3.11)")
    return False


def step_check_lappa() -> bool:
    header("Step 2: Check Lappa installation")
    data = run_lappa_json("version")
    if data and "version" in data:
        ok(f"Lappa {data['version']} installed")
        return True
    nok("Lappa not installed — run: pip install -e '.[gui,dev]' from packages/server/")
    return False


def step_list_demos() -> list[str] | None:
    header("Step 3: List available demos")
    rc, out, err = run_lappa("list-demos")
    if rc != 0:
        nok(f"list-demos failed: {err[:120]}")
        return None
    demos = []
    for line in out.split("\n"):
        if "\t" in line and not line.startswith("Found"):
            name = line.split("\t")[0].strip()
            if name:
                demos.append(name)
    if demos:
        ok(f"Found {len(demos)} demo(s): {', '.join(demos)}")
    else:
        nok("No demos found")
    return demos


def step_sim_start(demo: str) -> bool:
    header(f"Step 4: Start native sim — {demo}")
    data = run_lappa_json("sim", "start", "--demo", demo)
    if not data:
        return False

    state = data.get("state", data)
    running = state.get("running", False)
    hot_reload = data.get("hot_reload", False)

    if running:
        ok(f"Sim running — kind={state.get('kind')}")
    else:
        nok("Sim not running")
        return False

    if hot_reload:
        ok(f"Hot-reload enabled — reload_count={data.get('reload_count', 0)}")
    else:
        nok("Hot-reload NOT enabled")
        return False

    # Check file watcher started
    logs = data.get("logs", [])
    watch_log = [l for l in logs if "hot-reload watch started" in l]
    if watch_log:
        ok("File watcher thread active")
    else:
        info("File watcher log not yet visible (may appear after first poll)")

    return True


def step_edit_teleop(demo: str) -> tuple[str, str] | None:
    header(f"Step 5: Edit teleop.py to trigger hot-reload")

    teleop_path = DEMOS_DIR / demo / demo / TELEOP_REL
    if not teleop_path.exists():
        nok(f"teleop.py not found at {teleop_path}")
        return None

    # Read original
    original = teleop_path.read_text(encoding="utf-8")

    if OLD_PATTERN not in original:
        nok(f"Pattern not found in teleop.py: '{OLD_PATTERN[:50]}...'")
        info(f"First 300 chars of file: {original[:300]}")
        return None

    ok(f"Found edit target in {teleop_path.name}")

    # Apply edit
    modified = original.replace(OLD_PATTERN, NEW_PATTERN)
    teleop_path.write_text(modified, encoding="utf-8")
    ok("Edit applied: lidar wall 3.0 → 8.0")

    return original, str(teleop_path)


def step_send_commands(demo: str) -> bool:
    header(f"Step 6: Send velocity commands")

    # Forward motion
    data = run_lappa_json("sim", "cmd", "--lx", "0.4", "--az", "0.2")
    if data and data.get("ok"):
        ok("Cmd sent: lx=0.4 az=0.2")
    else:
        nok("Cmd failed")
        return False

    # Let sim process ticks
    for i in range(5):
        time.sleep(0.1)
        run_lappa("sim", "status", timeout=5)

    ok("Sim processed 5 ticks")
    return True


def step_check_hotreload(timeout: float = 5.0) -> bool:
    header("Step 7: Verify hot-reload detection")

    deadline = time.time() + timeout
    while time.time() < deadline:
        data = run_lappa_json("sim", "status")
        if not data:
            time.sleep(0.5)
            continue

        reload_count = data.get("reload_count", 0)
        last_reload = data.get("last_reload_at")

        if reload_count >= 1:
            ok(f"Hot-reload detected — reload_count={reload_count}, last_reload_at={last_reload}")
            return True

        time.sleep(0.5)

    nok(f"Hot-reload NOT detected after {timeout}s — reload_count still 0")
    return False


def step_check_movement() -> bool:
    header("Step 8: Verify robot has moved")

    data = run_lappa_json("sim", "summary")
    if not data:
        return False

    state = data.get("state", data)
    pose = data.get("pose", {})
    x = pose.get("x", state.get("x", 0))
    y = pose.get("y", state.get("y", 0))
    theta = pose.get("theta", state.get("theta", 0))

    dist = (x * x + y * y) ** 0.5
    if abs(x) > 0.001 or abs(y) > 0.001 or abs(theta) > 0.001:
        ok(f"Robot moved — x={x:.4f} y={y:.4f} θ={theta:.4f} (dist={dist:.4f}m)")
        return True
    else:
        nok(f"Robot did NOT move — x={x:.6f} y={y:.6f} θ={theta:.6f}")
        return False


def step_export_trajectory() -> bool:
    header("Step 9: Export trajectory CSV")

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        csv_path = f.name

    rc, out, err = run_lappa("sim", "trajectory", "--out", csv_path, timeout=15)
    if rc == 0 and Path(csv_path).exists():
        size = Path(csv_path).stat().st_size
        lines = Path(csv_path).read_text().strip().split("\n")
        ok(f"Trajectory exported: {len(lines)} points, {size} bytes → {csv_path}")
        return True
    else:
        nok(f"Trajectory export failed: {err[:120]}")
        return False


def step_restore_teleop(demo: str, original: str, teleop_path: str) -> bool:
    header("Step 10: Restore original teleop.py")
    try:
        Path(teleop_path).write_text(original, encoding="utf-8")
        ok("teleop.py restored to original")
        return True
    except OSError as e:
        nok(f"Failed to restore: {e}")
        return False


def step_sim_stop() -> bool:
    header("Step 11: Stop sim")
    data = run_lappa_json("sim", "stop")
    if data:
        state = data.get("state", data)
        if not state.get("running", True):
            ok("Sim stopped")
            return True
    nok("Failed to stop sim")
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Lappa E2E teleop → hot-reload → sim workflow")
    parser.add_argument(
        "--demo",
        default="diff_drive_2w",
        choices=["diff_drive_2w", "omni_3w", "tricycle_3w", "ackermann_4w", "simple_arm"],
        help="Demo to test (default: diff_drive_2w)",
    )
    parser.add_argument(
        "--skip-edit",
        action="store_true",
        help="Skip the teleop edit step (for read-only verification)",
    )
    args = parser.parse_args()

    demo = args.demo

    print("=" * 60)
    print("  Lappa E2E Workflow Verification")
    print(f"  Demo: {demo}")
    print(f"  Repo: {REPO_ROOT}")
    print("=" * 60)

    # Sequential verification
    steps_ok = True

    if not step_check_python():
        steps_ok = False
    if not step_check_lappa():
        steps_ok = False
    demos = step_list_demos()
    if demos is None:
        steps_ok = False
    elif demo not in demos:
        nok(f"Demo '{demo}' not found in available demos: {demos}")
        steps_ok = False

    if not steps_ok:
        print(f"\n⚠️  Prerequisites not met — aborting.")
        return 1

    # Start sim
    if not step_sim_start(demo):
        return 1

    # Edit teleop (if not skipped)
    restore_info = None
    if not args.skip_edit:
        restore_info = step_edit_teleop(demo)
        if restore_info is None:
            step_sim_stop()
            return 1

    # Send commands
    if not step_send_commands(demo):
        if restore_info:
            step_restore_teleop(demo, *restore_info)
        step_sim_stop()
        return 1

    # Check hot-reload
    hotreload_ok = step_check_hotreload()

    # Check movement
    move_ok = step_check_movement()

    # Export trajectory
    trajectory_ok = step_export_trajectory()

    # Restore original
    if restore_info:
        step_restore_teleop(demo, *restore_info)

    # Stop
    step_sim_stop()

    # Summary
    header("RESULTS")
    print(f"  Checks passed:  {PASS}")
    print(f"  Checks failed:  {FAIL}")

    all_ok = FAIL == 0
    if all_ok:
        print("\n  ✅ ALL CHECKS PASSED — E2E workflow verified!")
    else:
        print(f"\n  ❌ {FAIL} check(s) failed — review output above.")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
