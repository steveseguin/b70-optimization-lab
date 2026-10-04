#!/usr/bin/env python3
"""MiniMax-H3 duet: the block-24 split as two PROCESSES, one per card, clips staggered.

Lever 5 (notes/2026-09-19-speed-plan.md §4, "the idle half"; ledger idea #4 in
notes/2026-09-20-realtime-goal.md).  In the single-process runner the two halves of the
denoiser are strictly serial: card 0 runs blocks 0-23, `cross_card()`, card 1 runs 24-49, so
~half the card-seconds of every forward are idle.  The two-card VAE decode already proved that
two THREADS do not overlap on this torch/XPU build (the GIL is held across blocking XPU ops;
measured 1.01x in batch window 4).  So the duet uses two PROCESSES:

  rank 0 (card 0): embeddings, timestep branch, blocks 0..split-1
  rank 1 (card 1): blocks split..N-1, norm_out, both output projections

The crossing payload -- hidden_states [1, seq, 5376] bf16, temb, adaln indices, the rope pair
-- goes through /dev/shm (tmpfs, RAM speed), once per forward per clip: the same values the
boundary hooks move through host RAM in the single-process path, just between processes.

Exactness contract: each clip's arithmetic is exactly the single-run path's.  Same weights
(the same loader, filtered by rank), same block order, same scheduler; only the transport of
the mid-state differs, and a copy changes no bits.  The gate is bytewise: duet clip hashes
must equal the standalone receipts of the same prompt/seed/settings (smoke_h3.sh `duet`,
BATCH_REF_<i>).

Staggering: the driver runs one thread per clip, each thread a full unmodified pipeline call
over the duet proxy transformer.  While rank 1 finishes clip A's forward, rank 0 is already
running clip B's -- each worker is a FIFO, so both cards stay busy.  Two clips in ~one clip's
sample time is the ideal; the measurement lands in each clip's receipt.

Pruned denoiser only (the activation budget for two live clips does not fit the int8 path --
speed-plan §4), no LoRA on this track (the goal track is the base model).
"""

import json
import logging
import os
import pathlib
import subprocess
import sys
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_h3_t2v as R

LOG = logging.getLogger("h3-duet")
POLL_S = 0.002

REQ_KEYS = (
    "hidden_states", "audio_hidden_states", "encoder_hidden_states", "timestep",
    "timestep_indices", "token_tags", "position_ids", "video_indices", "audio_indices",
    "text_indices",
)
MID_KEYS = ("hidden_states", "temb", "adaln_indices", "rope_cos", "rope_sin",
            "timestep_indices", "video_indices", "audio_indices")
RESP_KEYS = ("video_output", "audio_output")


# ---------------------------------------------------------------------------------------------
# /dev/shm wire protocol: q0/req_<seq>.* (driver -> rank 0), q1/mid_<seq>.* (rank 0 -> rank 1),
# resp/resp_<seq>.* (rank 1 -> driver).  `.ready` is created by atomic rename; the consumer
# deletes the whole message after reading.  safetensors on tmpfs: RAM speed, mmap reads.
# ---------------------------------------------------------------------------------------------

def _send(tensors: dict, box: pathlib.Path, stem: str) -> None:
    from safetensors.torch import save_file

    tmp = box / f".{stem}.tmp"
    save_file({k: v.cpu().contiguous() for k, v in tensors.items()}, str(tmp))
    os.replace(tmp, box / f"{stem}.st")
    (box / f"{stem}.ready.tmp").write_text("1")
    os.replace(box / f"{stem}.ready.tmp", box / f"{stem}.ready")


def _recv(box: pathlib.Path, stem: str, stop: pathlib.Path):
    from safetensors.torch import load_file

    ready = box / f"{stem}.ready"
    while not ready.exists():
        if stop.exists():
            raise SystemExit(f"duet: stop requested while waiting for {box.name}/{stem}")
        time.sleep(POLL_S)
    tensors = load_file(str(box / f"{stem}.st"))
    ready.unlink()
    (box / f"{stem}.st").unlink()
    return tensors


# ---------------------------------------------------------------------------------------------
# Worker: one process, one card (ZE_AFFINITY_MASK set by the launcher), one half of the model.
# ---------------------------------------------------------------------------------------------

def _worker(args, plan, config, rank: int, duet_dir: pathlib.Path) -> int:
    import torch
    from diffusers.models.modeling_utils import get_parameter_dtype
    from diffusers.models.transformers.transformer_minimax_h3 import MINIMAX_H3_MODALITY_NUM

    dev = torch.device("xpu:0")  # the only card this process can see
    timings: dict[str, float] = {}
    model, _, _, _ = R.load_sharded_transformer(args, plan, config, timings, duet_rank=rank)
    LOG.info("[rank %d] half loaded: %s", rank,
             {k: round(v, 2) for k, v in timings.items()})
    (duet_dir / f"worker-{rank}.ready").write_text("1")
    stop = duet_dir / "stop"

    blocks = list(model.transformer_blocks)
    lo = 0 if rank == 0 else plan.split_index
    hi = plan.split_index if rank == 0 else len(blocks)
    half = blocks[lo:hi]

    def head(t):
        # transformer_minimax_h3.py L622-645, verbatim: projections, the packed scatter, the
        # timestep branch and the AdaLN row plan.  The arithmetic is the stock forward's.
        rotary_emb = model.rope(t["position_ids"].to(dev))
        video_embeds = model.proj_in(t["hidden_states"].to(dev).to(get_parameter_dtype(model.proj_in)))
        audio_embeds = model.audio_proj_in(
            t["audio_hidden_states"].to(dev).to(get_parameter_dtype(model.audio_proj_in)))
        text_embeds = model.context_embedder(
            t["encoder_hidden_states"].to(dev).to(get_parameter_dtype(model.context_embedder)))
        text_embeds = model.token_refiner(text_embeds)
        seq = t["position_ids"].shape[0]
        hidden = text_embeds.new_zeros((text_embeds.shape[0], seq, text_embeds.shape[-1]))
        hidden = hidden.index_copy(1, t["text_indices"].to(dev), text_embeds)
        hidden = hidden.index_copy(1, t["video_indices"].to(dev), video_embeds.to(text_embeds.dtype))
        hidden = hidden.index_copy(1, t["audio_indices"].to(dev), audio_embeds.to(text_embeds.dtype))
        temb = model.time_proj(t["timestep"].to(dev))
        temb = model.time_embedder(temb.to(get_parameter_dtype(model.time_embedder)))
        adaln_indices = t["timestep_indices"].to(dev) * MINIMAX_H3_MODALITY_NUM + t["token_tags"].to(dev)
        return hidden, temb, adaln_indices, rotary_emb

    with torch.no_grad():
        torch.set_grad_enabled(False)
        while True:
            if rank == 0:
                box, stem = duet_dir / "q0", None
                names = sorted((duet_dir / "q0").glob("req_*.ready"))
                if not names:
                    if stop.exists():
                        break
                    time.sleep(POLL_S)
                    continue
                stem = names[0].name[: -len(".ready")]
                t = _recv(duet_dir / "q0", stem, stop)
                seq = stem.split("_", 1)[1]
                hidden, temb, adaln_indices, rotary_emb = head(t)
                for block in half:
                    hidden = block(hidden, temb, adaln_indices, rotary_emb)
                _send({
                    "hidden_states": hidden, "temb": temb, "adaln_indices": adaln_indices,
                    "rope_cos": rotary_emb[0], "rope_sin": rotary_emb[1],
                    "timestep_indices": t["timestep_indices"],
                    "video_indices": t["video_indices"], "audio_indices": t["audio_indices"],
                }, duet_dir / "q1", f"mid_{seq}")
                LOG.info("[rank 0] forward %s: head+blocks done", seq)
            else:
                names = sorted((duet_dir / "q1").glob("mid_*.ready"))
                if not names:
                    if stop.exists():
                        break
                    time.sleep(POLL_S)
                    continue
                stem = names[0].name[: -len(".ready")]
                m = _recv(duet_dir / "q1", stem, stop)
                seq = stem.split("_", 1)[1]
                hidden = m["hidden_states"].to(dev)
                temb = m["temb"].to(dev)
                adaln_indices = m["adaln_indices"].to(dev)
                rotary_emb = (m["rope_cos"].to(dev), m["rope_sin"].to(dev))
                for block in half:
                    hidden = block(hidden, temb, adaln_indices, rotary_emb)
                # L658-660: both heads over every row, then the per-modality select.
                timestep_indices = m["timestep_indices"].to(dev)
                hidden = model.norm_out(hidden, temb, timestep_indices).to(
                    get_parameter_dtype(model.proj_out))
                video_output = model.proj_out(hidden).index_select(1, m["video_indices"].to(dev))
                audio_output = model.audio_proj_out(hidden).index_select(1, m["audio_indices"].to(dev))
                _send({"video_output": video_output, "audio_output": audio_output},
                      duet_dir / "resp", f"resp_{seq}")
                LOG.info("[rank 1] forward %s: blocks+heads done", seq)
    LOG.info("[rank %d] stop", rank)
    return 0


# ---------------------------------------------------------------------------------------------
# Driver: the proxy transformer, one pipeline call per clip on its own thread.
# ---------------------------------------------------------------------------------------------

class DuetTransformerProxy:  # NOT nn.Module: the pipeline only calls it and reads config/dtype.
    """Stands in for the sharded transformer in `build_pipeline`.  Every forward is one
    request on the duet wire; the arithmetic happens on the two worker cards."""

    def __init__(self, torch, config: dict, duet_dir: pathlib.Path):
        self._torch = torch
        self.config = type("DuetConfig", (), dict(config))()
        self.dtype = torch.bfloat16
        self._dir = duet_dir
        self._lock = threading.Lock()
        self._seq = 0
        self._stop = duet_dir / "stop"
        # The pipeline asks the transformer where latents should live; card 0 keeps the
        # scheduler's latent updates on the same device class as the single-run path.
        self._anchor = torch.nn.Parameter(torch.zeros(1, device="xpu:0"))

    def parameters(self):
        return iter([self._anchor])
    @property
    def device(self):
        return self._anchor.device

    def to(self, *a, **k):
        return self

    def eval(self):
        return self

    def train(self, mode=True):
        return self

    def forward(self, hidden_states, audio_hidden_states, encoder_hidden_states, timestep,
                timestep_indices, token_tags, position_ids, video_indices, audio_indices,
                text_indices, attention_kwargs=None, return_dict=True):
        from diffusers.models.transformers.transformer_minimax_h3 import MiniMaxH3TransformerOutput

        with self._lock:
            seq = self._seq
            self._seq += 1
        _send({
            "hidden_states": hidden_states, "audio_hidden_states": audio_hidden_states,
            "encoder_hidden_states": encoder_hidden_states, "timestep": timestep,
            "timestep_indices": timestep_indices, "token_tags": token_tags,
            "position_ids": position_ids, "video_indices": video_indices,
            "audio_indices": audio_indices, "text_indices": text_indices,
        }, self._dir / "q0", f"req_{seq:06d}")
        out = _recv(self._dir / "resp", f"resp_{seq:06d}", self._stop)
        # The driver's pipeline keeps latents on the CPU (the proxy owns no card), so the
        # scheduler step consumes CPU tensors; keep the outputs there too.  The gate then tells
        # us whether CPU-vs-XPU scheduler math is bit-identical to the single-run path.
        video_output = out["video_output"]
        audio_output = out["audio_output"]
        if not return_dict:
            return (video_output, audio_output)
        return MiniMaxH3TransformerOutput(sample=video_output, audio_sample=audio_output)

    __call__ = forward


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    args = R.build_parser().parse_args(argv)

    if os.environ.get("B70_H3_DUET_RANK") is not None:
        # Worker entrypoint: same argv, one rank, one visible card.
        rank = int(os.environ["B70_H3_DUET_RANK"])
        duet_dir = pathlib.Path(os.environ["B70_H3_DUET_DIR"])
        config = json.loads(R.TRANSFORMER_CONFIG.read_text())
        import torch  # after ZE_AFFINITY_MASK, which the launcher already set
        header = R.read_header(R.denoiser_path(args.denoiser))
        plan = R.plan_split(header, config, args.adaln_dtype, args.split_index, args.denoiser, None)
        return _worker(args, plan, config, rank, duet_dir)

    R.require_wrapper()  # smoke_h3.sh only: watchdog + MemorySwapMax=0 are the freeze defense
    # ---- driver ------------------------------------------------------------------------------
    if args.prompts_file is None:
        LOG.error("duet mode runs a batch: pass --prompts-file with at least 2 prompts")
        return 2
    if args.denoiser != "pruned":
        LOG.error("duet is pruned-only (the int8 activation budget does not fit two live clips)")
        return 2
    if args.lora:
        LOG.error("duet is the lossless goal track: no LoRA")
        return 2
    prompts = R._read_prompts_file(args.prompts_file)
    if len(prompts) < 2:
        LOG.error("a duet needs at least 2 prompts to stagger; got %d", len(prompts))
        return 2

    import torch

    if not torch.xpu.is_available() or torch.xpu.device_count() < 2:
        LOG.error("duet needs both B70s visible to the driver")
        return 2
    torch.set_grad_enabled(False)

    run_name = args.run_name or time.strftime("duet-%Y%m%dT%H%M%SZ", time.gmtime())
    out_dir = args.out_dir / run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    duet_dir = pathlib.Path("/dev/shm") / f"h3duet-{run_name}"
    for sub in ("q0", "q1", "resp"):
        (duet_dir / sub).mkdir(parents=True, exist_ok=True)
    LOG.info("duet run %s -> %s (wire %s)", run_name, out_dir, duet_dir)

    timings: dict[str, float] = {}
    config = json.loads(R.TRANSFORMER_CONFIG.read_text())
    denoiser = R.denoiser_path(args.denoiser)
    header = R.read_header(denoiser)
    plan = R.plan_split(header, config, args.adaln_dtype, args.split_index, args.denoiser, None)
    devices = [torch.device(f"xpu:{i}") for i in args.cards]

    # Phase 1: all prompts encoded by one encoder load (the batch path, unchanged).
    with R.phase("encode", timings):
        encoded = R.encode_prompts(args, prompts, timings)
    encoder_peak = R.card_memory(torch, devices)

    # Phase 2: the two workers load their halves, one process per card.
    workers = []
    for rank, card in enumerate(args.cards):
        env = dict(os.environ)
        env["ZE_AFFINITY_MASK"] = str(card)
        env["B70_H3_DUET_RANK"] = str(rank)
        env["B70_H3_DUET_DIR"] = str(duet_dir)
        env.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")
        log = open(out_dir / f"worker-{rank}.log", "w")
        workers.append(subprocess.Popen(
            [sys.executable, str(pathlib.Path(__file__).resolve())] + (argv if argv is not None else sys.argv[1:]),
            env=env, stdout=log, stderr=subprocess.STDOUT,
        ))
    for rank in (0, 1):
        ready = duet_dir / f"worker-{rank}.ready"
        t0 = time.time()
        while not ready.exists():
            if workers[rank].poll() is not None:
                LOG.error("worker %d died during load; see %s", rank, out_dir / f"worker-{rank}.log")
                (duet_dir / "stop").write_text("1")
                return 1
            time.sleep(0.25)
        LOG.info("worker %d ready in %.1f s", rank, time.time() - t0)

    # Phase 3: one pipeline call per clip, each on its own thread, over the SHARED proxy.
    # Each thread gets its own pipeline instance: the schedulers carry per-run state
    # (`_step_index`), and sharing one ran both clips' steps on one counter (IndexError at the
    # last step).  The proxy and the two workers are the only shared parts, and both are FIFOs.
    proxy = DuetTransformerProxy(torch, config, duet_dir)

    clips: list[dict | None] = [None] * len(prompts)
    build_lock = threading.Lock()  # diffusers' lazy importer is not thread-safe; builds are 0 s
    errors: list = []

    def run_clip(i: int, prompt_embeds, text_token_tags, token_ids) -> None:
        try:
            generator = torch.Generator(device="cpu").manual_seed(args.seed)
            with build_lock:
                pipe = R.build_pipeline(args, proxy, timings)
            if args.video_shift is not None:
                pipe.scheduler.set_shift(args.video_shift)
            if args.audio_shift is not None:
                pipe.audio_scheduler.set_shift(args.audio_shift)
            call_kwargs = dict(
                prompt_embeds=prompt_embeds.cpu(),
                text_token_tags=text_token_tags.cpu(),
                num_frames=args.frames,
                num_inference_steps=args.steps,
                generator=generator,
            )
            if args.height is not None:
                call_kwargs["height"] = args.height
            if args.width is not None:
                call_kwargs["width"] = args.width
            with R.phase(f"sample.{i}", timings):
                result = pipe(**call_kwargs, output=["latents", "audio_latents"])
            clips[i] = {
                "prompt": prompts[i],
                "token_ids": token_ids,
                "latents": result["latents"].detach().to("cpu", copy=True),
                "audio_latents": result["audio_latents"].detach().to("cpu", copy=True),
            }
        except BaseException as exc:  # noqa: BLE001 - reported after the join
            errors.append((i, exc))
            LOG.exception("clip %d failed", i)

    threads = [
        threading.Thread(target=run_clip, args=(i, *encoded[i]), name=f"clip-{i}", daemon=True)
        for i in range(len(prompts))
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    (duet_dir / "stop").write_text("1")
    for w in workers:
        w.wait(timeout=60)
    if errors:
        LOG.error("duet failed: %s", errors)
        import shutil
        shutil.rmtree(duet_dir, ignore_errors=True)  # host RAM; the worker logs are in the run folder
        return 1

    # The sampling wire lives in /dev/shm, which is host RAM: drop it before the decoders load (the worker logs
    # were already copied into the run folder).
    import shutil
    shutil.rmtree(duet_dir, ignore_errors=True)

    # Phase 4-5: the stock batch decode and per-clip receipts (decoders loaded once).
    sample_peak = R.card_memory(torch, devices)
    return R._decode_and_write_batch(
        torch, args, timings, devices, clips, run_name, out_dir, plan, denoiser, None,
        encoder_peak, [sample_peak] * len(clips),
    )


if __name__ == "__main__":
    raise SystemExit(main())
