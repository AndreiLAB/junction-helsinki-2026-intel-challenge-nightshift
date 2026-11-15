"""REPLAY check of an exported policy against recorded demos (no robot, no cameras).

For a few episodes per task, at several moments, feed the recorded state + camera frames to the model and compare
its predicted next actions with what the human actually did. Also swaps the task text on place episodes to see
whether the instruction steers the arm (good bowl vs defective bowl).

Usage: python tests/replay_policy.py <export_dir> [DEVICE] [episodes per task]
Numbers printed are REPLAY (recorded inputs, mostly training episodes, so optimistic).
"""
import json
import sys
import time

import numpy as np
from lerobot.datasets.lerobot_dataset import LeRobotDataset

from physicalai.inference import InferenceModel

DS = "/home/intel/.local/share/physicalai/datasets/d0c7cc23-2299-4a17-a697-fa06545a1dd9"
TASKS = ["Pick up a brick and hold it in front of the inspection camera.",
         "Put the brick in the good bowl.", "Put the brick in the defective bowl."]
H = 30  # compare the first 30 predicted actions (1 s)


def frame_obs(ds, i, task):
    s = ds[i]
    o = {"state": s["observation.state"].numpy().astype(np.float32)[None], "task": [task]}
    for c in ("top", "inspect", "wrist"):
        img = s[f"observation.images.{c}"].numpy()          # (3,H,W) float 0..1
        o[f"images.{c}"] = np.ascontiguousarray((img.transpose(1, 2, 0) * 255).round().astype(np.uint8))[None]
    return o


def main():
    path = sys.argv[1]
    dev = sys.argv[2] if len(sys.argv) > 2 else "GPU"
    per = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    ds = LeRobotDataset("local/duplo_v1", root=DS)
    eps = ds.meta.episodes
    t = time.perf_counter()
    m = InferenceModel(path, device=dev)
    print(f"load {time.perf_counter() - t:.1f}s on {dev}")
    by_task = {k: [] for k in TASKS}
    for e in range(len(eps)):
        by_task[eps[e]["tasks"][0]].append(e)
    lat, out = [], {}
    for task, elist in by_task.items():
        errs = []
        for e in elist[:: max(1, len(elist) // per)][:per]:
            a0, a1 = eps[e]["dataset_from_index"], eps[e]["dataset_to_index"]
            for frac in (0.0, 0.3, 0.6):
                i = a0 + int(frac * (a1 - a0 - H))
                o = frame_obs(ds, i, task)
                m.reset()
                t = time.perf_counter()
                ch = np.asarray(m.predict_action_chunk(o))
                lat.append((time.perf_counter() - t) * 1000)
                gt = np.stack([ds.hf_dataset[j]["action"].numpy() for j in range(i, i + H)])
                err = np.abs(ch[:H] - gt).mean(0)
                errs.append(err)
                swap = None
                if task != TASKS[0]:
                    other = TASKS[1] if task == TASKS[2] else TASKS[2]
                    o2 = dict(o, task=[other])
                    m.reset()
                    ch2 = np.asarray(m.predict_action_chunk(o2))
                    swap = float(ch2[-1, 0] - ch[-1, 0])   # pan at end of chunk: other task minus own task
                print(f"ep {e:3d} t={frac:.1f} {task[:28]:28s} mean|err| per joint "
                      + " ".join(f"{x:5.1f}" for x in err)
                      + (f"   pan(end) if task swapped: {swap:+.1f}" if swap is not None else ""))
        out[task] = np.mean(errs, 0).round(2).tolist()
    print("\nchunk shape", ch.shape, f"latency median {np.median(lat):.0f} ms, p90 {np.percentile(lat, 90):.0f} ms ({dev})")
    print(json.dumps({"device": dev, "mean_abs_err_first_1s": out, "lat_ms_median": float(np.median(lat))}, indent=1))


if __name__ == "__main__":
    main()
