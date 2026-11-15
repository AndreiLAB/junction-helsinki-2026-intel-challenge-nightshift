"""Cut 'brick held at the inspection point' frames from a Studio dataset.
Takes the last `tail_s` seconds of each pick_present episode from the inspect camera, a few frames each.
Usage: <backend python> -m inspection.extract_frames <dataset_dir> <out_dir> [tail_s=1.2] [per_ep=4]"""
import sys
from pathlib import Path

import av
import numpy as np
import pandas as pd
from PIL import Image

PICK = "Pick up a brick and hold it in front of the inspection camera."


def main(ds, out, tail_s=1.2, per_ep=4, cam="inspect"):
    ds, out = Path(ds), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    eps = pd.concat(pd.read_parquet(p) for p in sorted((ds / "meta/episodes").rglob("*.parquet")))
    k = f"videos/observation.images.{cam}"
    n = 0
    for (ci, fi), grp in eps.groupby([f"{k}/chunk_index", f"{k}/file_index"]):
        wanted = []
        for _, e in grp.iterrows():
            if PICK not in list(e["tasks"]):
                continue
            t1 = float(e[f"{k}/to_timestamp"])
            for t in np.linspace(t1 - tail_s, t1 - 0.1, per_ep):
                wanted.append((t, int(e["episode_index"])))
        if not wanted:
            continue
        wanted.sort()
        vid = ds / f"videos/observation.images.{cam}/chunk-{ci:03d}/file-{fi:03d}.mp4"
        with av.open(str(vid)) as c:
            st = c.streams.video[0]
            i = 0
            for fr in c.decode(st):
                ts = float(fr.pts * st.time_base)
                while i < len(wanted) and ts >= wanted[i][0]:
                    t, ep = wanted[i]
                    Image.fromarray(fr.to_ndarray(format="rgb24")).save(out / f"ep{ep:03d}_{t:08.2f}.png")
                    n += 1
                    i += 1
                if i >= len(wanted):
                    break
    print(f"wrote {n} frames to {out}")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], *(float(a[2]),) if len(a) > 2 else (), *(int(a[3]),) if len(a) > 3 else ())
