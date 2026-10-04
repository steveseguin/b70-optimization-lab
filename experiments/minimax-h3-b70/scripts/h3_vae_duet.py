#!/usr/bin/env python3
"""MiniMax-H3 video-VAE decode, one process per card (the lever-2 redo that threads failed).

The threaded two-card decode measured 1.01x in batch window 4 (2026-09-19): the GIL is held
across this torch/XPU build's blocking ops, so the two worker threads never overlapped.  The
H3 duet (h3_duet.py, same day) proved the fix: separate processes, one card each, tensors
through /dev/shm.  This script applies exactly that pattern to the tiled VAE decode.

Same job split, same blend order, same arithmetic as `decode_video_two_card` -- job k to card
k % n, tiles gathered POSITIONALLY, `_stitch_tiles`/`_blend`/trim on the blending card with
the driver's own VAE copy -- so the output must reproduce the single-card decode BYTewise;
that is the gate (compare against the source run's video_tensor_sha256).

Usage:
  h3_vae_duet.py --latents-from <run>/tensors.safetensors [--cards 0 1] [--autocast off]
                 [--work-dir /dev/shm/...]
Prints the decoded video tensor's sha256 and, if the source run's receipt is next to the
latents, whether it matches.
"""

import json
import logging
import os
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_h3_t2v as R

LOG = logging.getLogger("h3-vae-duet")
POLL_S = 0.002


def _send(tensors: dict, box: pathlib.Path, stem: str) -> None:
    from safetensors.torch import save_file

    tmp = box / f".{stem}.tmp"
    save_file({k: v.cpu().contiguous() for k, v in tensors.items()}, str(tmp))
    os.replace(tmp, box / f"{stem}.st")
    (box / f"{stem}.ready.tmp").write_text("1")
    os.replace(box / f"{stem}.ready.tmp", box / f"{stem}.ready")


# Worker processes the parent is waiting on. Filled by `_spawn_workers`; empty inside a worker.
_WATCHED: list = []


def _await_file(path: pathlib.Path, stop: pathlib.Path) -> None:
    """Wait for a marker file. Fails within a quarter of a second if a watched worker has died, instead of
    leaving the caller to its own timeout: on 2026-10-03 a crashed worker cost the full 900 s."""
    last_check = 0.0
    while not path.exists():
        if stop.exists():
            raise SystemExit(f"vae-duet: stop while waiting for {path.name}")
        now = time.time()
        if _WATCHED and now - last_check > 0.25:
            last_check = now
            for rank, proc in enumerate(_WATCHED):
                code = proc.poll()
                if code not in (None, 0):
                    raise RuntimeError(f"vae-duet: worker rank {rank} exited with code {code} while waiting for "
                                       f"{path.name}; see worker-{rank}.log beside it")
        time.sleep(POLL_S)


def _args_for_worker(vae_tiling: str):
    class A:  # the slice of run_h3_t2v args that load_video_vae reads
        pass

    a = A()
    a.vae_tiling = vae_tiling
    return a


def _worker(rank: int, work: pathlib.Path, vae_tiling: str) -> int:
    import torch

    dev = torch.device("xpu:0")  # ZE_AFFINITY_MASK pins this process to its card
    timings: dict[str, float] = {}
    vae, _ = R.load_video_vae(_args_for_worker(vae_tiling), timings, dev)
    LOG.info("[rank %d] VAE resident: %s", rank, {k: round(v, 2) for k, v in timings.items()})
    (work / f"worker-{rank}.ready").write_text("1")
    stop = work / "stop"

    from safetensors.torch import load_file

    jobs = json.loads((work / f"jobs-{rank}.json").read_text())
    meta = json.loads((work / "plan.json").read_text())
    tokens_chunk_size = meta["tokens_chunk_size"]
    token_overlap = meta["token_overlap"]
    y_indices = meta["y_indices"]
    y_lengths = meta["y_lengths"]
    x_indices = meta["x_indices"]
    x_lengths = meta["x_lengths"]
    ratio = meta["spatial_ratio"]

    # The picture-decode precision is the driver's `--autocast`, handed down in the environment.
    # Until 2026-10-03 the workers ignored it: `--vae-autocast fp16` on the two-proc path ran the
    # fp32 decode and only the blend sat inside the autocast context, so the receipt said fp16
    # while the pixels (and the 41 s) were fp32's. `off` is a nullcontext: the exact path is untouched.
    autocast = os.environ.get("B70_VAE_DUET_AUTOCAST", "off")
    LOG.info("[rank %d] tile decode autocast: %s", rank, autocast)

    def decode_z(z, tiles_dir: pathlib.Path) -> None:
        with torch.no_grad(), R.vae_autocast_context(torch, autocast, dev):
            torch.set_grad_enabled(False)
            for k, c, i, j in jobs:
                start = c * tokens_chunk_size  # `_decode` L815-816
                zc = z[:, :, start : start + tokens_chunk_size + token_overlap]
                i_pos, i_len = y_indices[i], y_lengths[i]
                j_pos, j_len = x_indices[j], x_lengths[j]
                tile = zc[..., i_pos // ratio : i_pos // ratio + i_len // ratio,
                          j_pos // ratio : j_pos // ratio + j_len // ratio]  # `_decode_clip` L755-759
                out = vae.decoder(vae.post_quant_conv(tile))  # `_decode_clip` L760
                _send({"tile": out}, tiles_dir, f"tile_{k:05d}")
                del out, tile, zc
                LOG.info("[rank %d] tile %d done", rank, k)

    if os.environ.get("B70_VAE_DUET_SERVE") == "1":
        # Persistent mode: the VAE stays resident; each job arrives as j<i>-z.st and gets its
        # own tiles-j<i>/ box, so a batch pays the 15 s spawn+load ONCE instead of per clip.
        idx = 0
        while not stop.exists():
            z_ready = work / f"j{idx}-z.ready"
            if not z_ready.exists():
                time.sleep(POLL_S)
                continue
            z = load_file(str(work / f"j{idx}-z.st"))["z"].to(dev)
            decode_z(z, work / f"tiles-j{idx}")
            del z
            # The job's z file is SHARED by both workers: neither may delete it. (2026-10-03 gate:
            # rank 1 unlinked it first, rank 0 died on FileNotFoundError after job 0 and job 1 hung
            # for the full 900 s timeout.) The server removes it once both ranks report done.
            (work / f"j{idx}-rank{rank}.done").write_text("1")
            idx += 1
        return 0

    _await_file(work / "z.ready", stop)
    z = load_file(str(work / "z.st"))["z"].to(dev)
    decode_z(z, work / "tiles")
    (work / f"worker-{rank}.done").write_text("1")
    return 0


def _prep_z(torch, vae, latents):
    """Cast, scale, pad, plan -- mirrors `decode_video_two_card`/`_decode` exactly."""
    from diffusers.models.modeling_utils import get_parameter_dtype

    want_dtype = get_parameter_dtype(vae.decoder)
    latents_mean = torch.tensor(vae.config.latents_mean).view(1, -1, 1, 1, 1)
    latents_std = torch.tensor(vae.config.latents_std).view(1, -1, 1, 1, 1)
    z = (latents * latents_std + latents_mean).to(want_dtype)  # `_decode`'s input scaling
    plan = R.vae_decode_plan(vae, z)
    if plan["pad_tokens"] > 0:  # `_decode` L809-810
        z = torch.cat([z, z[:, :, -1:].repeat(1, 1, plan["pad_tokens"], 1, 1)], dim=2)
    return z, plan


def _write_plan_and_jobs(work: pathlib.Path, vae, plan) -> None:
    (work / "plan.json").write_text(json.dumps({
        "tokens_chunk_size": vae.tokens_chunk_size,
        "token_overlap": int(vae.token_overlap),
        "y_indices": plan["y_indices"], "y_lengths": plan["y_lengths"],
        "x_indices": plan["x_indices"], "x_lengths": plan["x_lengths"],
        "spatial_ratio": vae.spatial_compression_ratio,
    }))
    num_chunks = plan["num_chunks"]
    jobs = [(c, i, j) for c in range(num_chunks)
            for i in range(len(plan["y_indices"])) for j in range(len(plan["x_indices"]))]
    for rank in range(2):
        mine = [[k, c, i, j] for k, (c, i, j) in enumerate(jobs) if k % 2 == rank]
        (work / f"jobs-{rank}.json").write_text(json.dumps(mine))


def _spawn_workers(work: pathlib.Path, cards, vae_tiling: str, serve: bool, latents_from,
                   autocast: str = "off"):
    workers = []
    for rank, card in enumerate(cards):
        env = dict(os.environ)
        env["ZE_AFFINITY_MASK"] = str(card)
        env["B70_VAE_DUET_RANK"] = str(rank)
        env["B70_VAE_DUET_DIR"] = str(work)
        if serve:
            env["B70_VAE_DUET_SERVE"] = "1"
        env["B70_VAE_DUET_AUTOCAST"] = autocast
        env.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")
        log = open(work / f"worker-{rank}.log", "w")
        argv = [sys.executable, str(pathlib.Path(__file__).resolve()),
                "--vae-tiling", vae_tiling]
        if latents_from is not None:  # argparse compat only; workers never read it
            argv += ["--latents-from", str(latents_from)]
        workers.append(subprocess.Popen(argv, env=env, stdout=log, stderr=subprocess.STDOUT))
    _WATCHED[:] = workers
    return workers


def _collect_blend(torch, load_file, vae, plan, z, tiles_dir: pathlib.Path, stop,
                   autocast: str, blend_device):
    """Gather tiles POSITIONALLY and blend exactly as `decode_video_two_card` does: stitch per
    chunk, drop the chunk's tiles, temporal cross-fade, concat, trim.  Returns video fp32 CPU
    [1,3,T,H,W] in [0,1]."""
    num_chunks, pad_tokens = plan["num_chunks"], plan["pad_tokens"]
    y_indices, x_indices = plan["y_indices"], plan["x_indices"]
    tiles_per_chunk = len(y_indices) * len(x_indices)
    decoded_chunks = []
    overlap = None
    with R.vae_autocast_context(torch, autocast, blend_device):
        for c in range(num_chunks):  # `_decode` L812-828
            base = c * tiles_per_chunk
            rows = []
            for i in range(len(y_indices)):
                row = []
                for j in range(len(x_indices)):
                    k = base + i * len(x_indices) + j
                    _await_file(tiles_dir / f"tile_{k:05d}.ready", stop)
                    tile = load_file(str(tiles_dir / f"tile_{k:05d}.st"))["tile"].to(blend_device)
                    (tiles_dir / f"tile_{k:05d}.ready").unlink()
                    (tiles_dir / f"tile_{k:05d}.st").unlink()
                    row.append(tile)
                rows.append(row)
            clip = vae._stitch_tiles(rows, plan["y_overlaps"], plan["x_overlaps"])  # L763
            del rows
            chunk_num_frames = vae.tokens_chunk_size * vae.temporal_compression_ratio
            for j in range(int(vae.config.token_drop > 0) + 1):
                frame_start = j * chunk_num_frames
                chunk = clip[:, :, frame_start : frame_start + chunk_num_frames]
                chunk = chunk[:, :, vae.frame_pre_padding :]
                if j == 0:
                    if overlap is not None:
                        chunk = vae._blend(overlap, chunk, vae.frame_overlap, dim=-3)
                    decoded_chunks.append(chunk)
                else:
                    overlap = chunk
            del clip
        if overlap is not None:
            decoded_chunks.append(overlap)
        dec = torch.cat(decoded_chunks, dim=2)
        if pad_tokens > 0:  # `_decode` L832-841
            intra_tail = vae.config.clip_length % vae.temporal_compression_ratio
            num_tokens_before_pad = z.shape[2] - pad_tokens
            pad_frames = sum(
                intra_tail if intra_tail and (num_tokens_before_pad + k) % vae.tokens_chunk_size == 0
                else vae.temporal_compression_ratio
                for k in range(pad_tokens)
            )
            dec = dec[:, :, :-pad_frames]
    pixel_mean = torch.tensor((0.485, 0.456, 0.406), device=blend_device).view(1, -1, 1, 1, 1)
    pixel_std = torch.tensor((0.229, 0.224, 0.225), device=blend_device).view(1, -1, 1, 1, 1)
    video = (dec.float() * pixel_std + pixel_mean).clamp(0, 1)
    return video.detach().float().cpu().contiguous()


def _serve(args, torch, work: pathlib.Path) -> int:
    """Persistent batch mode: one blend VAE, two resident workers, jobs j0, j1, ...
    Driver writes j<i>-in.st + j<i>-in.ready; we answer j<i>-out.st + j<i>-out.ready.
    Saves the ~15 s spawn+VAE-load the single-shot mode pays per clip."""
    from safetensors.torch import load_file, save_file

    timings: dict[str, float] = {}
    blend_device = torch.device(f"xpu:{args.cards[0]}")
    vae, _ = R.load_video_vae(_args_for_worker(args.vae_tiling), timings, blend_device)
    stop = work / "stop"

    # The plan and job split depend only on the canvas, which is fixed within a batch --
    # but they are computed from the FIRST job's z and then every later job is asserted
    # identical, so a mixed-shape batch fails loudly instead of blending wrong.
    workers = None
    plan = None
    idx = 0
    try:
        while not stop.exists():
            in_ready = work / f"j{idx}-in.ready"
            if not in_ready.exists():
                time.sleep(POLL_S)
                continue
            latents = load_file(str(work / f"j{idx}-in.st"))["latents"].detach().to("cpu", copy=True)
            z, this_plan = _prep_z(torch, vae, latents)
            del latents
            if plan is None:
                plan = this_plan
                _write_plan_and_jobs(work, vae, plan)
                workers = _spawn_workers(work, args.cards, args.vae_tiling, serve=True,
                                         latents_from=None, autocast=args.autocast)
                for rank in (0, 1):
                    _await_file(work / f"worker-{rank}.ready", stop)
                LOG.info("serve: workers resident, plan fixed (%d tiles/job)",
                         plan["num_chunks"] * len(plan["y_indices"]) * len(plan["x_indices"]))
            else:
                for key in ("pad_tokens", "num_chunks", "y_indices", "x_indices"):
                    assert this_plan[key] == plan[key], f"serve: job {idx} plan drifted: {key}"
            tiles_dir = work / f"tiles-j{idx}"
            tiles_dir.mkdir(exist_ok=True)
            _send({"z": z}, work, f"j{idx}-z")
            (work / f"j{idx}-in.st").unlink()
            in_ready.unlink()
            t0 = time.time()
            video_cpu = _collect_blend(torch, load_file, vae, plan, z, tiles_dir, stop,
                                       args.autocast, blend_device)
            del z
            for rank in (0, 1):  # both workers have finished reading the shared z before it goes
                _await_file(work / f"j{idx}-rank{rank}.done", stop)
            for name in (f"j{idx}-z.st", f"j{idx}-z.ready", f"j{idx}-rank0.done", f"j{idx}-rank1.done"):
                (work / name).unlink(missing_ok=True)
            save_file({"video": video_cpu}, str(work / f"j{idx}-out.st") + ".tmp")
            os.replace(str(work / f"j{idx}-out.st") + ".tmp", work / f"j{idx}-out.st")
            (work / f"j{idx}-out.ready").write_text("1")
            LOG.info("serve: job %d decoded in %.1f s (sha256 %s)", idx, time.time() - t0,
                     R.sha256_tensor(video_cpu)[:16])
            del video_cpu
            idx += 1
        return 0
    finally:
        stop.write_text("1")
        for w in workers or []:
            try:
                w.wait(timeout=30)
            except subprocess.TimeoutExpired:
                w.kill()


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--latents-from", type=pathlib.Path, default=None,
                   help="single-shot mode: decode these latents; not needed for --serve")
    p.add_argument("--serve", action="store_true",
                   help="persistent batch mode: jobs arrive as j<i>-in.st in --work-dir")
    p.add_argument("--cards", type=int, nargs=2, default=[0, 1])
    p.add_argument("--autocast", default="off", choices=["off", "fp16", "bf16"],
                   help="off is the only lossless-goal-track setting")
    p.add_argument("--vae-tiling", default="auto", choices=["auto", "on", "off"])
    p.add_argument("--work-dir", type=pathlib.Path, default=None)
    p.add_argument("--video-out", type=pathlib.Path, default=None,
                   help="write the decoded video tensor (fp32, [1,3,T,H,W] in [0,1]) here as "
                   "safetensors, for the caller to pick up -- the batch integration path")
    args = p.parse_args(argv)

    if os.environ.get("B70_VAE_DUET_RANK") is not None:
        return _worker(int(os.environ["B70_VAE_DUET_RANK"]),
                       pathlib.Path(os.environ["B70_VAE_DUET_DIR"]), args.vae_tiling)
    R.require_wrapper()  # smoke_h3.sh only: the unwrapped standalone run froze the host (09-20/21)

    import torch

    torch.set_grad_enabled(False)
    work = args.work_dir or pathlib.Path("/dev/shm") / f"h3vaeduet-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    (work / "tiles").mkdir(parents=True, exist_ok=True)
    LOG.info("work dir %s", work)

    if args.serve:
        return _serve(args, torch, work)
    if args.latents_from is None:
        p.error("--latents-from is required outside --serve")

    from safetensors.torch import load_file

    payload = load_file(str(args.latents_from))
    latents = payload["latents"].detach().to("cpu", copy=True)
    del payload

    # Blend card: the driver's own VAE copy on card A.  9.7 GiB beside each worker's 9.7 GiB
    # replica leaves the cards with 12+ GiB free each -- the tiles are 22 MB apiece.
    timings: dict[str, float] = {}
    blend_device = torch.device(f"xpu:{args.cards[0]}")
    vae, _ = R.load_video_vae(_args_for_worker(args.vae_tiling), timings, blend_device)

    z, plan = _prep_z(torch, vae, latents)
    del latents
    _send({"z": z}, work, "z")
    _write_plan_and_jobs(work, vae, plan)

    workers = _spawn_workers(work, args.cards, args.vae_tiling, serve=False,
                             latents_from=args.latents_from, autocast=args.autocast)
    stop = work / "stop"
    try:
        for rank in (0, 1):
            _await_file(work / f"worker-{rank}.ready", stop)

        t0 = time.time()
        video_cpu = _collect_blend(torch, load_file, vae, plan, z, work / "tiles", stop,
                                   args.autocast, blend_device)
        LOG.info("two-process decode+blend in %.1f s", time.time() - t0)

        if args.video_out is not None:
            from safetensors.torch import save_file

            save_file({"video": video_cpu}, str(args.video_out))
        digest = R.sha256_tensor(video_cpu)
        LOG.info("video tensor sha256 %s", digest)

        source_receipt = args.latents_from.parent / "receipt.json"
        if source_receipt.exists():
            src = json.loads(source_receipt.read_text())
            want = src.get("hashes", {}).get("video_tensor_sha256")
            LOG.info("source %s: %s", src.get("run_name"),
                     "MATCH (bytewise-equal)" if want == digest else f"DIFFERS ({want})")
            return 0 if want == digest else 1
        return 0
    finally:
        stop.write_text("1")
        for w in workers:
            try:
                w.wait(timeout=30)
            except subprocess.TimeoutExpired:
                w.kill()


if __name__ == "__main__":
    raise SystemExit(main())
