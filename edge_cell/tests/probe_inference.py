"""Load a Studio OpenVINO export with InferenceModel and run it on fake zero inputs.

Usage: python probe_inference.py <export_dir> [DEVICE=CPU|GPU|NPU] [task]
Pure software: no cameras, no robot. Searches default locations if no path is given.
"""
import glob, os, sys, time
import numpy as np

def find_exports():
    pats = ["~/.local/share/physicalai/models/**/manifest.json", "/home/intel/duplo-cell/**/manifest.json"]
    hits = []
    for p in pats:
        hits += glob.glob(os.path.expanduser(p), recursive=True)
    return [os.path.dirname(h) for h in hits if "plugins" not in h]

path = sys.argv[1] if len(sys.argv) > 1 else (find_exports() or [None])[0]
device = sys.argv[2] if len(sys.argv) > 2 else "CPU"
task = sys.argv[3] if len(sys.argv) > 3 else "pick up the red brick"
if path is None:
    print("NO EXPORT FOUND on disk; pass an export dir."); sys.exit(0)

from physicalai.inference import InferenceModel
t = time.perf_counter(); m = InferenceModel(path, device=device); print(f"load {time.perf_counter()-t:.1f}s", m)
print("adapter inputs:", m.adapter.input_names)
obs = {}
for f in m.input_features:
    shp = tuple(f.shape)
    if f.name == "task":
        obs["task"] = [task]
    elif f.name.startswith("images"):
        c, h, w = shp if shp[0] in (1, 3) else (shp[2], shp[0], shp[1])
        obs[f.name] = np.zeros((1, h, w, 3), np.uint8)  # what PolicySource feeds: (1,H,W,3) uint8 RGB
    elif f.name == "state":
        obs["state"] = np.zeros((1, *shp), np.float32)
    print("feature", f.name, shp, f.dtype)
for i in range(3): m.reset(); m.predict_action_chunk(obs)  # warmup
lat = []
for i in range(10):
    t = time.perf_counter(); chunk = m.predict_action_chunk(obs); lat.append(time.perf_counter() - t)
print("chunk shape", chunk.shape, "median ms", 1000 * np.median(lat), "p90 ms", 1000 * np.percentile(lat, 90))
