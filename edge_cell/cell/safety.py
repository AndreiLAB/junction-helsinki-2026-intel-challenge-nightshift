"""Safety layer: every action goes through here before the robot.
- clamp to safe joint ranges
- limit change per tick (relative to the last SENT action, or the measured state on the first tick)
- stop on stale camera frames (raise SafetyStop -> runtime ends the run)
Also usable as a physicalai RobotRuntime callback (on_action_ready)."""
from __future__ import annotations

import time

import numpy as np


class SafetyStop(RuntimeError):
    pass


class Safety:
    def __init__(self, cfg: dict, clock=time.monotonic, log=None):
        sa = cfg["safety"]
        self.lo = np.asarray(sa["joint_min"], np.float32)
        self.hi = np.asarray(sa["joint_max"], np.float32)
        self.max_step = np.asarray(sa["max_step_per_tick"], np.float32) * float(sa["speed"])
        self.stale_s = float(cfg["cameras"]["stale_frame_s"])
        self.clock = clock
        self.log = log
        self.last = None
        self.frame_ts: dict[str, float] = {}
        self.n_clamped = 0
        self.n_rate_limited = 0

    def reset(self, q):
        self.last = np.asarray(q, np.float32).copy()

    def note_frame(self, cam: str, ts: float | None = None):
        self.frame_ts[cam] = self.clock() if ts is None else ts

    def check_frames(self, required=()):
        now = self.clock()
        for cam in required:
            t = self.frame_ts.get(cam)
            if t is None or now - t > self.stale_s:
                age = None if t is None else round(now - t, 3)
                raise SafetyStop(f"stale camera frame: {cam} age={age}s")

    def filter(self, action, q=None):
        a = np.asarray(action, np.float32).reshape(-1)
        if a.shape != (6,) or not np.all(np.isfinite(a)):
            raise SafetyStop(f"bad action {a!r}")
        c = np.clip(a, self.lo, self.hi)
        if not np.array_equal(c, a):
            self.n_clamped += 1
        ref = self.last if self.last is not None else (np.asarray(q, np.float32) if q is not None else c)
        r = np.clip(c, ref - self.max_step, ref + self.max_step)
        if not np.array_equal(r, c):
            self.n_rate_limited += 1
        self.last = r
        return r

    # physicalai RobotRuntime callback hook
    def on_action_ready(self, *, action, step):
        return self.filter(action)
