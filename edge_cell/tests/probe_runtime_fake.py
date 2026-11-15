"""Pure-software probe of physicalai.runtime.RobotRuntime.

Uses a FAKE robot (no serial port) and no cameras. Demonstrates:
 (b) a custom ActionSource (connect/update/disconnect)
 (c) per-action callbacks (on_action_ready may transform, on_action_sent notifies, on_tick telemetry)
"""
import time
from dataclasses import dataclass
import numpy as np
from physicalai.runtime import RobotRuntime

JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]

@dataclass
class FakeObs:
    joint_positions: np.ndarray
    timestamp: float
    sensor_data: dict | None = None
    images: dict | None = None
    @property
    def state(self): return self.joint_positions

class FakeRobot:
    def __init__(self): self.q = np.zeros(6, np.float32); self._c = False; self.sent = []
    def connect(self): self._c = True
    def disconnect(self): self._c = False
    def is_connected(self): return self._c
    def get_observation(self): return FakeObs(self.q.copy(), time.monotonic())
    def send_action(self, action, *, goal_time=0.1): self.q = np.asarray(action, np.float32); self.sent.append(self.q.copy())
    @property
    def joint_names(self): return JOINTS
    @property
    def device_ids(self): return ()

class ScriptedSource:
    """Our own action source: called once per cycle; returns a (6,) action in robot units."""
    def connect(self, *, bus, session_id): self.t0 = time.monotonic()
    def update(self, robot_state, camera_frames, step):
        a = robot_state.state.copy(); a[0] = 10.0 * np.sin(time.monotonic() - self.t0); a[5] = 50.0
        return a
    def disconnect(self): pass

class Clamp:
    def __init__(self): self.n_ready = self.n_sent = self.n_tick = 0
    def on_action_ready(self, *, action, step):
        self.n_ready += 1
        return np.clip(action, [-100]*5 + [0], [100]*5 + [100])
    def on_action_sent(self, *, action, step): self.n_sent += 1
    def on_tick(self, event): self.n_tick += 1

robot, cb = FakeRobot(), Clamp()
rt = RobotRuntime(robot=robot, action_source=ScriptedSource(), fps=30, cameras={}, callbacks=[cb])
rt.connect()
steps = rt.run(duration_s=0.5)
rt.disconnect()
print("steps", steps, "reason", rt.last_run_reason, "ready/sent/tick", cb.n_ready, cb.n_sent, cb.n_tick)
print("last sent", np.round(robot.sent[-1], 2))
