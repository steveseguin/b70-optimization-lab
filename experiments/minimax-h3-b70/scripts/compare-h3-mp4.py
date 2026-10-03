#!/usr/bin/env python3
"""Compare two MiniMax-H3 clip.mp4 files frame by frame on the CPU (PyAV only, no torch, no GPU).

The exact instrument is compare-h3-runs.py on tensors.safetensors. Duet/batch clips do not save tensors,
so this is the fallback: decode both x264 files and report the 8-bit difference of what was actually
saved. It includes the encoder's own response to the input change, so read it as "how different are the
two saved videos", not as the decode's arithmetic error.

    compare-h3-mp4.py <a.mp4> <b.mp4> [--json OUT]
"""
import argparse, json, sys
import av
import numpy as np


def frames(path):
    with av.open(str(path)) as c:
        for f in c.decode(video=0):
            yield f.to_ndarray(format="rgb24").astype(np.int16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a"); ap.add_argument("b"); ap.add_argument("--json")
    args = ap.parse_args()
    n = 0; sse = 0.0; sad = 0.0; worst = 0; differing = 0; total = 0; worst_frame = -1; per_frame_max = []
    for fa, fb in zip(frames(args.a), frames(args.b)):
        d = np.abs(fa - fb)
        m = int(d.max()); per_frame_max.append(m)
        if m > worst: worst, worst_frame = m, n
        sse += float((d.astype(np.float64) ** 2).sum()); sad += float(d.sum())
        differing += int((d > 0).sum()); total += d.size; n += 1
    mse = sse / total
    out = {
        "frames": n, "shape_elements_per_frame": total // max(n, 1),
        "mean_abs_diff_255": round(sad / total, 4), "max_abs_diff_255": worst, "worst_frame": worst_frame,
        "fraction_differing": round(differing / total, 4),
        "psnr_db": None if mse == 0 else round(10 * np.log10(255.0 ** 2 / mse), 2),
        "median_per_frame_max": float(np.median(per_frame_max)) if per_frame_max else None,
    }
    print(json.dumps(out, indent=2))
    if args.json:
        json.dump(out, open(args.json, "w"), indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
