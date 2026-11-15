"""Real hardware: follower arm + cameras through the physicalai runtime packages.
Cameras use SharedCamera with Studio's exact camera config, so they attach to Studio's publisher if one is
running, or start the same publisher themselves. The robot must not be in use by Studio."""
from __future__ import annotations

import time

import numpy as np
import yaml

from common.config import repo_path


def open_follower(cfg):
    from physicalai.robot.so101 import SO101
    calib = yaml.safe_load(open(repo_path(cfg["robot"]["follower_calibration"])))
    r = SO101(port=cfg["robot"]["follower_port"], calibration=calib, role="follower", unit="normalized")
    r.connect()
    return r


def read_q(robot):
    return np.asarray(robot.get_observation().state, np.float32)


class Cameras:
    def __init__(self, cfg, names=("top", "inspect", "wrist")):
        from physicalai.capture import SharedCamera
        from physicalai.config import Config
        self.cams = {}
        for n in names:
            c = cfg["cameras"][n]
            fp = dict(cfg["cameras"]["fingerprint"][n])
            camcfg = Config("physicalai.capture.UVCCamera",
                            {"device": fp, "width": c["width"], "height": c["height"], "fps": c["fps"]})
            self.cams[n] = SharedCamera(camera=camcfg, color_mode="rgb", idle_timeout=5.0)
        self.ts = {}

    def connect(self, timeout=10.0):
        for c in self.cams.values():
            c.connect(timeout=timeout)

    def read(self):
        """Latest frame per camera: RGB uint8 HxWx3. Frame.timestamp is time.monotonic() of the publisher."""
        out = {}
        for n, c in self.cams.items():
            f = c.read_latest()
            self.ts[n] = float(f.timestamp)
            out[n] = np.asarray(f.data)
        return out

    def age(self, n):
        t = self.ts.get(n)
        return None if t is None else time.monotonic() - t

    def disconnect(self):
        for c in self.cams.values():
            try:
                c.disconnect()
            except Exception:
                pass
