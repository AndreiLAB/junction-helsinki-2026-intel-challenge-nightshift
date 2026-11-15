"""Fakes for mock mode and tests: a tiny simulated world, robot, skills, inspector and checks. All MOCK."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import numpy as np

from cell.motion import PoseMove


class FakeWorld:
    """Truth the fakes share. bricks: list of 'good' / 'defect' / 'unsure' (unsure scores mid-range once)."""

    def __init__(self, bricks, miss_first_pick=(), seed=0):
        self.plate = list(bricks)
        self.held = None
        self.bowls = {"good": [], "defect": []}
        self.miss_first_pick = set(miss_first_pick)   # plate positions whose first pick misses
        self._picked = 0
        self.rng = np.random.default_rng(seed)

    def pick(self):
        if not self.plate:
            return
        n = self._picked
        self._picked += 1
        if n in self.miss_first_pick:
            self.miss_first_pick.discard(n)
            self._picked -= 1
            return
        self.held = self.plate.pop(0)

    def drop(self, where):
        if self.held is None:
            return
        if where == "plate":
            self.plate.insert(0, self.held)
        else:
            self.bowls[where].append(self.held)
        self.held = None


class FakeRobot:
    """q moves toward the last command with a first-order lag (like a servo)."""

    def __init__(self, q0, alpha=0.5):
        self.q = np.asarray(q0, np.float32).copy()
        self.alpha = alpha
        self.cmd = self.q.copy()

    def send(self, action):
        self.cmd = np.asarray(action, np.float32)

    def step(self):
        self.q = self.q + self.alpha * (self.cmd - self.q)
        return self.q.copy()


class FakeSkill(PoseMove):
    """Stands in for the learned policy: drives to an end pose, then changes the world."""

    def __init__(self, name, world, end_pose, max_step, effect):
        super().__init__(end_pose, max_step)
        self.name, self.world, self.effect = name, world, effect
        self.instruction = ""
        self._applied = False

    def start(self, q, now):
        super().start(q, now)
        self._applied = False

    def done(self, q, frames, now):
        d = super().done(q, frames, now)
        if d and not self._applied:
            self._applied = True
            self.effect()
        return d


def make_fake_skills(world, poses, max_step):
    return {
        "pick_present": FakeSkill("pick_present", world, poses["inspect"], max_step, world.pick),
        "place_good": FakeSkill("place_good", world, poses["above_plate"], max_step, lambda: world.drop("good")),
        "place_defect": FakeSkill("place_defect", world, poses["above_plate"], max_step, lambda: world.drop("defect")),
    }


class FakeInspector:
    """Same interface as inspection/service.py: submit() returns at once, poll() -> dict or None."""

    def __init__(self, world, latency_s=0.05, t_low=0.4, t_high=0.6):
        self.world, self.latency_s = world, latency_s
        self.t_low, self.t_high = t_low, t_high
        self._result = None
        self._lock = threading.Lock()
        self._seen_unsure = {}
        self.n = 0

    def submit(self, frame_rgb, depth_mm=None, view="inspect"):
        with self._lock:
            self._result = None
        held = self.world.held
        threading.Thread(target=self._work, args=(held, view), daemon=True).start()

    def _work(self, held, view):
        time.sleep(self.latency_s)
        self.n += 1
        if held is None:
            res = {"verdict": "NO_BRICK", "score": 0.0}
        else:
            score = {"good": 0.1, "defect": 0.9, "unsure": 0.5}[held]
            verdict = "GOOD" if score < self.t_low else "DEFECT" if score > self.t_high else "UNCERTAIN"
            res = {"verdict": verdict, "score": score}
        res.update({"brick_idx": None, "ts": time.time(), "t_low": self.t_low, "t_high": self.t_high,
                    "views": [{"view": view, "score": res["score"]}], "heatmap_png": None, "model": "fake",
                    "precision": "-", "device": "CPU", "latency_ms": self.latency_s * 1000, "evidence": "MOCK"})
        with self._lock:
            self._result = res

    def poll(self):
        with self._lock:
            r, self._result = self._result, None
        return r


class FakeChecks:
    """CPU checks, answered from world truth in mock mode."""

    def __init__(self, world):
        self.world = world

    def plate_empty(self, frames):
        return not self.world.plate and self.world.held is None

    def brick_held(self, frames):
        return self.world.held is not None

    def snapshot(self, frames):
        return {k: len(v) for k, v in self.world.bowls.items()}

    def placed_ok(self, before, frames):
        after = self.snapshot(frames)
        return sum(after.values()) > sum((before or {}).values())
