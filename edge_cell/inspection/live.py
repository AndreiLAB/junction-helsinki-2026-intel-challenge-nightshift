"""Live defect verdict from Studio's inspect camera (reads Studio's shared picture, never opens the camera).
Usage: ./inspect_live.sh   (Ctrl+C to stop). Studio must have the 'cell' environment open (recording or run screen)."""
import sys
import time

import numpy as np

from common.config import ROOT, load_station
from inspection.service import Inspector


def main():
    from physicalai.capture import SharedCamera
    cfg = load_station()
    ins = Inspector(cfg, heatmap_dir=ROOT / "runs/live_heatmaps")
    print(f"model {ins.model_name} on {ins.device} (compiled in {ins.compile_s:.1f}s); "
          f"GOOD < {ins.t_low} <= UNCERTAIN <= {ins.t_high} < DEFECT")
    cam = SharedCamera.from_publisher(cfg["cameras"]["inspect"]["publisher"])
    try:
        cam.connect(timeout=5.0)
    except Exception as e:
        print("Cannot see Studio's inspect camera. Open the 'cell' environment in Studio first.", e)
        return 1
    try:
        while True:
            fr = cam.read_latest()
            s, amap, ms = ins.score(np.asarray(fr.data))
            v = ins.verdict(s)
            bar = "#" * int(s * 30)
            print(f"{time.strftime('%H:%M:%S')}  {v:9s} score {s:.2f} |{bar:<30}| {ms:.0f} ms on {ins.device}", flush=True)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("stopped")
    finally:
        cam.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
