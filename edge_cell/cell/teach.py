"""Teach poses with live teleop: the FOLLOWER copies the LEADER (slowly, through cell/safety.py), and on Enter
we save the FOLLOWER's measured position. Started by a human in the Robot tab: ./teach_poses.sh
Waits for GO. Ctrl+C stops cleanly (follower holds its position).
Studio must NOT be on a recording / run screen (it would hold both arms)."""
import copy
import queue
import sys
import threading
import time

import numpy as np
import yaml

from cell.safety import Safety
from common.config import JOINTS, load_station, repo_path

POSES = [
    ("home", "the RESTING position, exactly where your pick-and-show demos STARTED"),
    ("inspect", "the INSPECTION point, exactly where you held bricks in front of the inspection camera"),
    ("inspect_view2", "the inspection point, WRIST TURNED about a quarter turn one way"),
    ("inspect_view3", "the inspection point, WRIST TURNED about a quarter turn the OTHER way"),
    ("above_plate", "just ABOVE the BLUE start bowl, gripper OPEN"),
    ("above_good", "just ABOVE the GREEN (good) bowl, low enough to drop a brick in, gripper as if holding a brick"),
    ("above_defect", "just ABOVE the PINK (defective) bowl, low enough to drop a brick in, gripper as if holding a brick"),
    ("travel", "the TRAVEL position: arm RAISED HIGH, well above the bowls and above the inspection camera"),
]
DEFAULT = ["home", "inspect", "inspect_view2", "inspect_view3", "above_plate"]


def main():
    global POSES
    from physicalai.robot.so101 import SO101
    wanted = sys.argv[1:] or DEFAULT
    POSES = [p for p in POSES if p[0] in wanted]
    cfg = copy.deepcopy(load_station())
    cfg["safety"]["speed"] = 1.0           # teleop: per-tick limit at full table value (about 45 units/s)
    calib_l = yaml.safe_load(open(repo_path("configs/calibration/leader.json")))
    calib_f = yaml.safe_load(open(repo_path("configs/calibration/follower.json")))
    leader = SO101(port=cfg["robot"]["leader_port"], calibration=calib_l, role="leader", unit="normalized")
    follower = SO101(port=cfg["robot"]["follower_port"], calibration=calib_f, role="follower", unit="normalized")
    print("\nThis will switch ON the follower arm. It will slowly move to copy the controller arm.")
    print("Clear the area around the follower arm. Keep a hand near its power switch.")
    if input("Type GO and press Enter to start (anything else quits): ").strip().upper() != "GO":
        print("Not started.")
        return 0
    try:
        leader.connect()
        follower.connect()
    except Exception as e:
        print("\nCannot open the arms. Is Studio on a recording or run screen? Leave it and retry.\n", e)
        for r in (leader, follower):
            try:
                r.disconnect()
            except Exception:
                pass
        return 1

    safety = Safety(cfg)
    safety.reset(np.asarray(follower.get_observation().state, np.float32))
    lines: queue.Queue = queue.Queue()
    threading.Thread(target=lambda: [lines.put(l) for l in sys.stdin], daemon=True).start()
    out, i, period = {}, 0, 1.0 / 30
    print("\nFollower is live. Move the CONTROLLER arm; the follower copies it (a bit slower).")
    print(f"\n>>> Pose 1/{len(POSES)}: move to {POSES[0][1]}.\n    Wait until the follower is there and still, then press Enter.")
    try:
        while i < len(POSES):
            t0 = time.monotonic()
            target = np.asarray(leader.get_observation().state, np.float32)
            follower.send_action(safety.filter(target))
            try:
                lines.get_nowait()
                qs = []
                for _ in range(10):
                    qs.append(np.asarray(follower.get_observation().state, np.float32))
                    follower.send_action(safety.filter(target))
                    time.sleep(period)
                q, jitter = np.mean(qs, axis=0), float(np.max(np.std(qs, axis=0)))
                if jitter > 1.5:
                    print(f"    The arm was still moving (wobble {jitter:.1f}). Hold still and press Enter again.")
                else:
                    name = POSES[i][0]
                    out[name] = [round(float(x), 1) for x in q]
                    print(f"    saved {name}: " + ", ".join(f"{j}={v:.0f}" for j, v in zip(JOINTS, q)))
                    i += 1
                    if i < len(POSES):
                        print(f"\n>>> Pose {i + 1}/{len(POSES)}: move to {POSES[i][1]}.\n    Then press Enter.")
            except queue.Empty:
                pass
            time.sleep(max(0.0, period - (time.monotonic() - t0)))
    except KeyboardInterrupt:
        print("\nstopped (Ctrl+C); saving what we have")
    finally:
        for r in (follower, leader):
            try:
                r.disconnect()
            except Exception as e:
                print("disconnect:", e)
    p = repo_path("configs/poses_taught.yaml")
    old = (yaml.safe_load(open(p)) or {}).get("poses", {}) if p.exists() else {}
    old.update(out)
    out = old
    with open(p, "w") as f:
        yaml.safe_dump({"poses": out, "taught_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "source": "follower measured during leader teleop"}, f)
    print(f"\nDONE. Saved {len(out)} poses to {p}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
