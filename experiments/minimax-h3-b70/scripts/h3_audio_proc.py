#!/usr/bin/env python3
"""MiniMax-H3 audio-VAE decode worker: one persistent process on the spare card.

During a two-proc video decode, card 1 carries only its 9.7 GiB video-VAE replica plus tile
activations -- ~20 GiB free.  The audio VAE is 2.25 GiB and one decode is ~3 s, so the whole
audio phase hides inside the 40 s video decode instead of sitting serialized behind it.

Protocol (mirrors h3_vae_duet.py: atomic rename = message):
  driver writes  <work>/job-<i>.st          (audio_latents, fp32, [1,C,N])
  then           <work>/job-<i>.ready
  worker answers <work>/job-<i>-out.st      (audio fp32 [1,2,N] + sampling_rate in .json)
  then           <work>/job-<i>-out.ready
  driver deletes job files after reading.  <work>/stop ends the worker.

Same VAE, same dtype, same decode call as _decode_audio_one -- only the card differs, and the
bytewise batch gate is the proof that card choice changes nothing.
"""

import json
import logging
import os
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_h3_t2v as R

LOG = logging.getLogger("h3-audio-proc")
POLL_S = 0.002


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--card", type=int, required=True)
    p.add_argument("--work-dir", type=pathlib.Path, required=True)
    p.add_argument("--vae-tiling", default="auto", choices=["auto", "on", "off"])
    args = p.parse_args(argv)

    import torch
    from safetensors.torch import load_file, save_file

    torch.set_grad_enabled(False)
    work = args.work_dir
    stop = work / "stop"

    timings: dict[str, float] = {}
    device = torch.device(f"xpu:{args.card}")
    audio_vae = R.load_audio_vae(args, timings, device)  # reads no args fields; returns the VAE
    LOG.info("audio worker ready on xpu:%d (%.1f s)", args.card, sum(timings.values()))
    (work / "worker.ready").write_text("1")

    import re

    job_re = re.compile(r"job-\d+\.ready")  # NOT job-<i>-out.ready, the worker's own answers
    while not stop.exists():
        jobs = sorted(p for p in work.glob("job-*.ready") if job_re.fullmatch(p.name))
        if not jobs:
            time.sleep(POLL_S)
            continue
        ready = jobs[0]
        stem = ready.name[: -len(".ready")]
        latents = load_file(str(work / f"{stem}.st"))["audio_latents"]
        t0 = time.time()
        audio, _, sampling_rate = R._decode_audio_one(
            torch, {}, audio_vae, device, latents, phase_name="decode.audio"
        )
        out_st = work / f"{stem}-out.st"
        save_file({"audio": audio.cpu().contiguous()}, str(out_st) + ".tmp")
        os.replace(str(out_st) + ".tmp", out_st)
        (work / f"{stem}-out.json").write_text(json.dumps({"sampling_rate": sampling_rate}))
        (work / f"{stem}-out.ready").write_text("1")
        (work / f"{stem}.st").unlink()
        ready.unlink()
        LOG.info("%s decoded in %.2f s", stem, time.time() - t0)
    LOG.info("stop flag seen; exiting")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
