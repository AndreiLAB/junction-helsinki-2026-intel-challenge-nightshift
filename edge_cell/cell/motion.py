"""Scripted motion: move slowly in a straight joint-space line to a taught pose."""
from __future__ import annotations

import numpy as np


class PoseMove:
    """Each tick returns the next action toward `target`, limited per joint. Done when settled."""

    def __init__(self, target, max_step, tol: float = 2.0, settle_s: float = 0.4, keep_gripper: bool = False):
        self.target = np.asarray(target, np.float32).copy()
        self.keep_gripper = keep_gripper   # holding a brick: do not change the grip
        self.max_step = np.asarray(max_step, np.float32)
        self.tol = tol
        self.settle_s = settle_s
        self.cmd = None
        self._near_since = None

    def start(self, q, now):
        self.cmd = np.asarray(q, np.float32).copy()
        self._near_since = None
        if self.keep_gripper:
            self.target[5] = self.cmd[5]

    def step(self, q, frames, now):
        if self.cmd is None:
            self.start(q, now)
        delta = np.clip(self.target - self.cmd, -self.max_step, self.max_step)
        self.cmd = self.cmd + delta
        return self.cmd.copy()

    def done(self, q, frames, now):
        q = np.asarray(q, np.float32)
        # gripper excluded from "arrived": it may stall on a held brick
        near = bool(np.all(np.abs(q[:5] - self.target[:5]) <= self.tol))
        if not near:
            self._near_since = None
            return False
        if self._near_since is None:
            self._near_since = now
        return now - self._near_since >= self.settle_s


class Hold:
    """Hold the last commanded position (used during INSPECT / DECIDE)."""

    def __init__(self, cmd):
        self.cmd = np.asarray(cmd, np.float32).copy()

    def step(self, q, frames, now):
        return self.cmd.copy()


class Route:
    """Several PoseMoves in a row: intermediate points need only be reached roughly (no settle), the last one
    settles. Same step/done interface as PoseMove."""

    def __init__(self, targets, max_step, tol=2.0, settle_s=0.4, keep_gripper=False, via_tol=6.0):
        self.moves = [PoseMove(t, max_step, via_tol if i < len(targets) - 1 else tol,
                               0.0 if i < len(targets) - 1 else settle_s, keep_gripper)
                      for i, t in enumerate(targets)]
        self.i = 0
        self.target = self.moves[-1].target

    def start(self, q, now):
        self.i = 0
        self.moves[0].start(q, now)

    def step(self, q, frames, now):
        m = self.moves[self.i]
        if self.i < len(self.moves) - 1 and m.done(q, frames, now):
            self.i += 1
            nxt = self.moves[self.i]
            nxt.start(m.cmd if m.cmd is not None else q, now)
            nxt.cmd = m.cmd.copy() if m.cmd is not None else np.asarray(q, np.float32).copy()
            m = nxt
        return m.step(q, frames, now)

    def done(self, q, frames, now):
        return self.i == len(self.moves) - 1 and self.moves[-1].done(q, frames, now)


def plan_route(q, target, travel=None, pan_thresh=12.0, lift_thresh=30.0):
    """Up, sideways, down. If the pan (joint 0) changes a lot, or the arm must move far in shoulder/elbow/wrist
    (e.g. it starts low inside a bowl), and a 'travel' pose is taught:
    1) raise to the travel posture, keeping the current pan / wrist roll / gripper
    2) turn the pan to the target's pan, still raised
    3) go down to the target.  Otherwise (small move) a direct move."""
    q = np.asarray(q, np.float32)
    target = np.asarray(target, np.float32)
    far = abs(float(target[0] - q[0])) >= pan_thresh or float(np.max(np.abs(target[1:4] - q[1:4]))) > lift_thresh
    if travel is None or not far:
        return [target]
    t = np.asarray(travel, np.float32)
    up = t.copy(); up[0] = q[0]; up[4] = q[4]; up[5] = q[5]
    over = t.copy(); over[0] = target[0]; over[4] = target[4]; over[5] = q[5]
    return [up, over, target]
