#!/usr/bin/env python3
"""Crash-safe single-B70 long-haul training for the K160 EAGLE head."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import torch
from safetensors import safe_open


SCRIPT_DIR = Path(__file__).resolve().parent
SIGNAL_TRAINER_PATH = SCRIPT_DIR / "train-k160-eagle-signal-head.py"
SIGNAL_SPEC = importlib.util.spec_from_file_location(
    "k160_eagle_signal_head", SIGNAL_TRAINER_PATH
)
if SIGNAL_SPEC is None or SIGNAL_SPEC.loader is None:
    raise RuntimeError(f"cannot import {SIGNAL_TRAINER_PATH}")
signal_trainer = importlib.util.module_from_spec(SIGNAL_SPEC)
sys.modules[SIGNAL_SPEC.name] = signal_trainer
SIGNAL_SPEC.loader.exec_module(signal_trainer)

CHECKPOINT_SCHEMA = "k160-eagle-longhaul-checkpoint-v1"
METRICS_SCHEMA = "k160-eagle-longhaul-dev-metrics-v1"
CHECKPOINT_PATTERN = re.compile(r"checkpoint-step-(\d+)\.pt$")


def append_jsonl(
    path: Path, payload: dict[str, Any], *, durable: bool = True
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        stream.write(json.dumps(payload, sort_keys=True) + "\n")
        stream.flush()
        if durable:
            os.fsync(stream.fileno())


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    with temporary.open("w") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def atomic_torch_save(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    try:
        torch.save(payload, temporary)
        with temporary.open("r+b") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class HardTimeout:
    """Exit the worker so the detached supervisor can resume a saved checkpoint."""

    def __init__(self, seconds: int, event: str, identity: int):
        self.seconds = seconds
        self.event = event
        self.identity = identity
        self.timer: threading.Timer | None = None

    def __enter__(self) -> HardTimeout:
        if self.seconds > 0:
            self.timer = threading.Timer(self.seconds, self._expire)
            self.timer.daemon = True
            self.timer.start()
        return self

    def _expire(self) -> None:
        print(
            json.dumps(
                {
                    "event": self.event,
                    "identity": self.identity,
                    "timeout_s": self.seconds,
                }
            ),
            flush=True,
        )
        os._exit(124)

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.timer is not None:
            self.timer.cancel()


def assert_single_xpu_environment() -> None:
    inherited = {
        name: os.getenv(name)
        for name in ("LOCAL_RANK", "RANK", "WORLD_SIZE", "MASTER_ADDR", "MASTER_PORT")
        if os.getenv(name) is not None
    }
    if inherited:
        raise RuntimeError(f"distributed environment was not scrubbed: {sorted(inherited)}")
    ccl_keys = sorted(name for name in os.environ if name.startswith("CCL_"))
    if ccl_keys or os.getenv("LD_PRELOAD"):
        raise RuntimeError("single-card worker inherited oneCCL or LD_PRELOAD state")
    if os.getenv("ZE_AFFINITY_MASK") != "1":
        raise RuntimeError("long-haul worker requires ZE_AFFINITY_MASK=1")
    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise RuntimeError("XPU mask did not expose exactly one device")
    if torch.distributed.is_initialized():
        raise RuntimeError("single-card worker inherited a process group")


def read_metrics_steps(path: Path) -> set[int]:
    steps: set[int] = set()
    if not path.exists():
        return steps
    with path.open() as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                steps.add(int(row["step"]))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise RuntimeError(
                    f"invalid metrics row {line_number} in {path}"
                ) from error
    return steps


def checkpoint_candidates(output_dir: Path) -> list[tuple[int, Path]]:
    candidates = []
    for path in output_dir.glob("checkpoint-step-*.pt"):
        match = CHECKPOINT_PATTERN.match(path.name)
        if match:
            candidates.append((int(match.group(1)), path))
    return sorted(candidates, reverse=True)


def load_latest_checkpoint(output_dir: Path) -> tuple[Path, dict[str, Any]] | None:
    failures = []
    for expected_step, path in checkpoint_candidates(output_dir):
        try:
            payload = torch.load(path, map_location="cpu", weights_only=True)
            if (
                payload.get("schema_version") != CHECKPOINT_SCHEMA
                or int(payload.get("global_step", -1)) != expected_step
                or "optimizer_state_dict" not in payload
                or "stream_state" not in payload
            ):
                raise RuntimeError("checkpoint contract mismatch")
            return path, payload
        except Exception as error:  # continue to the most recent intact checkpoint
            failures.append(f"{path.name}: {error}")
    if failures:
        raise RuntimeError("no intact long-haul checkpoint: " + "; ".join(failures))
    return None


def validate_data_pair(
    train_identity: dict[str, Any], dev_identity: dict[str, Any]
) -> None:
    if (
        dev_identity["other_prompt_set_sha256"] != train_identity["prompt_set_sha256"]
        or train_identity["other_prompt_set_sha256"] != dev_identity["prompt_set_sha256"]
        or train_identity["prompt_set_sha256"] == dev_identity["prompt_set_sha256"]
    ):
        raise RuntimeError("DEV capture is not reciprocally disjoint from training")


def load_dev_lineage(args: argparse.Namespace, dev_identity: dict[str, Any]):
    if signal_trainer.file_sha256(args.dev_request_manifest) != dev_identity[
        "request_manifest_sha256"
    ]:
        raise RuntimeError("DEV request manifest differs from capture validation")
    with args.dev_request_manifest.open() as stream:
        request_rows = [json.loads(line) for line in stream if line.strip()]
    with args.dev_replay_manifest.open() as stream:
        replay_rows = [json.loads(line) for line in stream if line.strip()]
    if len(replay_rows) != len(request_rows):
        raise RuntimeError("DEV replay and trajectory manifest lengths differ")
    category_by_key: dict[int, str] = {}
    prompt_hashes: set[str] = set()
    for index, (replay_row, trajectory) in enumerate(
        zip(replay_rows, request_rows, strict=True)
    ):
        if (
            int(replay_row["trajectory_index"]) != index
            or replay_row["trajectory_request_id"] != trajectory["request_id"]
        ):
            raise RuntimeError("DEV replay lineage does not match trajectories")
        key = int(replay_row["request_key"])
        if key in category_by_key:
            raise RuntimeError("DEV replay request-key collision")
        category_by_key[key] = trajectory["category"]
        prompt_hashes.add(trajectory["prompt_sha256"])
    return category_by_key, prompt_hashes


@torch.inference_mode()
def run_dev_eval(
    model: torch.nn.Module,
    device: torch.device,
    args: argparse.Namespace,
    checkpoint_path: Path,
    dev_identity: dict[str, Any],
    category_by_key: dict[int, str],
    prompt_hashes: set[str],
) -> dict[str, Any]:
    accepted = torch.zeros(7, dtype=torch.int64)
    cycles = 0
    evaluated_keys: set[int] = set()
    model.eval()
    eval_started = time.time()
    for shard in sorted(args.dev_data_dir.glob("features-*.safetensors")):
        with safe_open(shard, framework="pt", device="cpu") as tensors:
            data = {name: tensors.get_tensor(name) for name in tensors.keys()}
        anchors = signal_trainer.eligible_anchors(
            data["request_key"], data["position_id"]
        )
        for offset in range(0, anchors.numel(), args.eval_batch):
            chosen = anchors[offset : offset + args.eval_batch]
            with HardTimeout(args.eval_batch_timeout, "dev_batch_timeout", cycles):
                shifted = chosen.unsqueeze(1) + torch.arange(7).unsqueeze(0)
                context_rows, context_mask = signal_trainer.context_rows_and_mask(
                    data["request_key"], data["position_id"], chosen
                )
                context_features = data["features_bf16"][context_rows]
                context_features = context_features.masked_fill(
                    ~context_mask[..., None, None], 0
                ).to(device)
                context_tokens = data["input_token_id"][context_rows].to(device)
                context_mask = context_mask.to(device)
                labels = data["next_target_token_id"][shifted]
                keys = data["request_key"][chosen]
                if any(int(key) not in category_by_key for key in keys.tolist()):
                    raise RuntimeError("DEV capture has a request key absent from lineage")
                evaluated_keys.update(map(int, keys.tolist()))
                survived = torch.ones(chosen.numel(), dtype=torch.bool)
                predictions = []
                with signal_trainer.autocast_context(device):
                    sequence = model.context_sequence(context_features, context_tokens)
                    state, logits = model.decode(sequence, context_mask)
                    previous_prediction = None
                    for position in range(7):
                        if position:
                            state, logits, sequence, context_mask = model.step(
                                state,
                                previous_prediction,
                                sequence,
                                context_mask,
                            )
                        predicted = logits.argmax(dim=-1)
                        predictions.append(predicted.cpu())
                        previous_prediction = predicted
                for position, predicted in enumerate(predictions):
                    survived &= predicted == labels[:, position]
                    accepted[position] += survived.sum()
                signal_trainer.synchronize_device(device)
            cycles += chosen.numel()
    if cycles == 0:
        raise RuntimeError("DEV evaluation found zero eligible anchors")
    conditional = []
    marginal = []
    for position, count in enumerate(accepted.tolist()):
        marginal.append(count / cycles)
        denominator = cycles if position == 0 else int(accepted[position - 1])
        conditional.append(count / denominator if denominator else 0.0)
    mean_p2_p7 = sum(conditional[1:]) / 6
    overall = accepted.sum().item() / (7 * cycles)
    return {
        "schema_version": "k160-eagle-longhaul-offline-eval-v1",
        "cycles": cycles,
        "accepted_through_position_counts": accepted.tolist(),
        "marginal_acceptance": marginal,
        "conditional_acceptance": conditional,
        "p1": conditional[0],
        "mean_conditional_p2_p7": mean_p2_p7,
        "overall_draft_token_acceptance": overall,
        "emitted_tokens_per_cycle_estimate": 1 + accepted.sum().item() / cycles,
        "evaluated_request_keys": len(evaluated_keys),
        "checkpoint": str(checkpoint_path.resolve()),
        "checkpoint_sha256": signal_trainer.file_sha256(checkpoint_path),
        "evaluation_data_identity": dev_identity,
        "request_manifest": str(args.dev_request_manifest.resolve()),
        "replay_manifest": str(args.dev_replay_manifest.resolve()),
        "prompt_set_sha256": signal_trainer.hashlib.sha256(
            "\n".join(sorted(prompt_hashes)).encode()
        ).hexdigest(),
        "elapsed_s": time.time() - eval_started,
        "go_signal": mean_p2_p7 > 0.75 and overall > 0.40,
    }


def optimizer_for(model: torch.nn.Module, args: argparse.Namespace):
    decay, no_decay = [], []
    for name, parameter in model.named_parameters():
        (no_decay if "norm" in name or parameter.ndim == 1 else decay).append(parameter)
    return torch.optim.AdamW(
        [
            {"params": decay, "weight_decay": args.weight_decay},
            {"params": no_decay, "weight_decay": 0.0},
        ],
        lr=args.learning_rate,
        betas=(0.9, 0.95),
        eps=1e-8,
    )


def learning_rate(args: argparse.Namespace, run_step_zero_based: int) -> float:
    warmup = max(1, int(args.additional_steps * args.warmup_fraction))
    if run_step_zero_based < warmup:
        return args.learning_rate * (run_step_zero_based + 1) / warmup
    progress = (run_step_zero_based - warmup) / max(
        1, args.additional_steps - warmup
    )
    progress = min(max(progress, 0.0), 1.0)
    return args.learning_rate * (
        args.minimum_lr_ratio
        + (1 - args.minimum_lr_ratio)
        * 0.5
        * (1 + math.cos(math.pi * progress))
    )


def resume_contract(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "initial_global_step": args.initial_global_step,
        "initial_anchors": args.initial_anchors,
        "anchors_per_epoch": args.anchors_per_epoch,
        "additional_steps": args.additional_steps,
        "checkpoint_every": args.checkpoint_every,
        "microbatch": args.microbatch,
        "gradient_accumulation": args.gradient_accumulation,
        "learning_rate": args.learning_rate,
        "warmup_fraction": args.warmup_fraction,
        "minimum_lr_ratio": args.minimum_lr_ratio,
        "weight_decay": args.weight_decay,
        "seed": args.seed,
        "eval_batch": args.eval_batch,
    }


def checkpoint_payload(
    *,
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    stream: Any,
    args: argparse.Namespace,
    global_step: int,
    run_step: int,
    anchors: int,
    interval_loss_sum: float,
    interval_loss_count: int,
    target_identity: dict[str, Any],
    train_identity: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": CHECKPOINT_SCHEMA,
        "head_config": asdict(signal_trainer.HeadConfig()),
        "feature_boundaries": signal_trainer.FEATURE_BOUNDARIES,
        "state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "stream_state": stream.state_dict(),
        "torch_rng_state": torch.get_rng_state(),
        "global_step": global_step,
        "run_step": run_step,
        "anchors": anchors,
        "epoch": anchors / args.anchors_per_epoch,
        "interval_loss_sum": interval_loss_sum,
        "interval_loss_count": interval_loss_count,
        "target_tensor_identity": target_identity,
        "training_data_identity": train_identity,
        "resume_contract": resume_contract(args),
        "schedule": {
            "name": "warmup_cosine_decay",
            "additional_steps": args.additional_steps,
            "warmup_fraction": args.warmup_fraction,
            "minimum_lr_ratio": args.minimum_lr_ratio,
            "peak_learning_rate": args.learning_rate,
        },
        "runtime": {
            "precision": "bf16_autocast_fp32_adamw",
            "gradient_checkpointing": True,
            "execution_mode": "eager",
            "world_size": 1,
            "ze_affinity_mask": os.getenv("ZE_AFFINITY_MASK"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-data-dir", type=Path, required=True)
    parser.add_argument("--train-capture-validation", type=Path, required=True)
    parser.add_argument("--dev-data-dir", type=Path, required=True)
    parser.add_argument("--dev-capture-validation", type=Path, required=True)
    parser.add_argument("--dev-request-manifest", type=Path, required=True)
    parser.add_argument("--dev-replay-manifest", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--warm-start-checkpoint", type=Path, required=True)
    parser.add_argument("--initial-global-step", type=int, required=True)
    parser.add_argument("--initial-anchors", type=int, required=True)
    parser.add_argument("--anchors-per-epoch", type=int, required=True)
    parser.add_argument("--additional-steps", type=int, required=True)
    parser.add_argument("--checkpoint-every", type=int, default=3000)
    parser.add_argument("--microbatch", type=int, default=8)
    parser.add_argument("--gradient-accumulation", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--warmup-fraction", type=float, default=0.03)
    parser.add_argument("--minimum-lr-ratio", type=float, default=0.10)
    parser.add_argument("--weight-decay", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=160719)
    parser.add_argument("--step-timeout", type=int, default=60)
    parser.add_argument("--eval-batch-timeout", type=int, default=120)
    parser.add_argument("--eval-batch", type=int, default=64)
    parser.add_argument("--log-every", type=int, default=100)
    args = parser.parse_args()

    assert_single_xpu_environment()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stop_path = args.output_dir / "STOP"
    metrics_path = args.output_dir / "metrics.jsonl"
    train_metrics_path = args.output_dir / "training-metrics.jsonl"
    events_path = args.output_dir / "events.jsonl"
    eval_dir = args.output_dir / "evaluations"
    eval_dir.mkdir(exist_ok=True)

    if args.initial_anchors + args.additional_steps * (
        args.microbatch * args.gradient_accumulation
    ) != 5 * args.anchors_per_epoch:
        raise RuntimeError("configured continuation does not end at five epochs")

    device = torch.device("xpu", 0)
    torch.xpu.set_device(0)
    torch.manual_seed(args.seed)
    shards = sorted(args.train_data_dir.glob("features-*.safetensors"))
    stream = signal_trainer.ShardStream(shards, 0, 1, args.microbatch, args.seed)
    embedding, lm_head, target_identity = signal_trainer.load_frozen_target_tensors(
        args.model_root
    )
    train_identity = signal_trainer.dataset_fingerprint(
        args.train_data_dir, args.train_capture_validation
    )
    dev_identity = signal_trainer.dataset_fingerprint(
        args.dev_data_dir, args.dev_capture_validation
    )
    validate_data_pair(train_identity, dev_identity)
    category_by_key, prompt_hashes = load_dev_lineage(args, dev_identity)

    model = signal_trainer.K160EagleSignalHead(
        signal_trainer.HeadConfig(), embedding, lm_head
    ).to(device)
    model.gradient_checkpointing = True
    optimizer = optimizer_for(model, args)
    loaded = load_latest_checkpoint(args.output_dir)
    if loaded is None:
        warm = torch.load(
            args.warm_start_checkpoint, map_location="cpu", weights_only=True
        )
        if (
            warm.get("head_config") != asdict(signal_trainer.HeadConfig())
            or tuple(warm.get("feature_boundaries", ()))
            != signal_trainer.FEATURE_BOUNDARIES
            or warm.get("target_tensor_identity") != target_identity
            or warm.get("training_data_identity") != train_identity
            or int(warm.get("training_steps", -1)) != args.initial_global_step
        ):
            raise RuntimeError("warm-start checkpoint identity mismatch")
        model.load_state_dict(warm["state_dict"], strict=True)
        stream.advance(args.initial_anchors)
        global_step = args.initial_global_step
        run_step = 0
        anchors = args.initial_anchors
        interval_loss_sum = 0.0
        interval_loss_count = 0
        resume_path = None
    else:
        resume_path, resume = loaded
        if (
            resume.get("head_config") != asdict(signal_trainer.HeadConfig())
            or tuple(resume.get("feature_boundaries", ()))
            != signal_trainer.FEATURE_BOUNDARIES
            or resume.get("target_tensor_identity") != target_identity
            or resume.get("training_data_identity") != train_identity
            or resume.get("resume_contract") != resume_contract(args)
        ):
            raise RuntimeError("resume checkpoint identity mismatch")
        model.load_state_dict(resume["state_dict"], strict=True)
        optimizer.load_state_dict(resume["optimizer_state_dict"])
        stream.load_state_dict(resume["stream_state"])
        torch.set_rng_state(resume["torch_rng_state"])
        global_step = int(resume["global_step"])
        run_step = int(resume["run_step"])
        anchors = int(resume["anchors"])
        interval_loss_sum = float(resume["interval_loss_sum"])
        interval_loss_count = int(resume["interval_loss_count"])
        if global_step != args.initial_global_step + run_step:
            raise RuntimeError("resume checkpoint step accounting mismatch")
        if anchors != args.initial_anchors + run_step * (
            args.microbatch * args.gradient_accumulation
        ):
            raise RuntimeError("resume checkpoint anchor accounting mismatch")

    config = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
    } | {
        "schema_version": "k160-eagle-longhaul-config-v1",
        "metrics_path": str(metrics_path.resolve()),
        "stop_sentinel": str(stop_path.resolve()),
        "target_tensor_identity": target_identity,
        "training_data_identity": train_identity,
        "dev_data_identity": dev_identity,
    }
    atomic_write_json(args.output_dir / "training-config.json", config)
    append_jsonl(
        events_path,
        {
            "event": "worker_start",
            "pid": os.getpid(),
            "global_step": global_step,
            "run_step": run_step,
            "anchors": anchors,
            "epoch": anchors / args.anchors_per_epoch,
            "resume_checkpoint": str(resume_path) if resume_path else None,
            "device": str(device),
            "xpu_device_count": torch.xpu.device_count(),
            "ze_affinity_mask": os.getenv("ZE_AFFINITY_MASK"),
            "oneapi_device_selector": os.getenv("ONEAPI_DEVICE_SELECTOR"),
            "world_size": 1,
            "ddp": False,
            "process_group_initialized": torch.distributed.is_initialized(),
            "execution_mode": "eager",
            "precision": "bf16_autocast_fp32_adamw",
            "gradient_checkpointing": True,
            "step_timeout_s": args.step_timeout,
            "utc_epoch_s": time.time(),
        },
    )

    evaluated_steps = read_metrics_steps(metrics_path)

    def evaluate_checkpoint(checkpoint_path: Path, mean_loss: float) -> None:
        nonlocal interval_loss_sum, interval_loss_count
        result = run_dev_eval(
            model,
            device,
            args,
            checkpoint_path,
            dev_identity,
            category_by_key,
            prompt_hashes,
        )
        result |= {
            "step": global_step,
            "run_step": run_step,
            "anchors": anchors,
            "epoch": anchors / args.anchors_per_epoch,
            "loss": mean_loss,
        }
        eval_path = eval_dir / f"eval-step-{global_step:06d}.json"
        atomic_write_json(eval_path, result)
        metric = {
            "schema_version": METRICS_SCHEMA,
            "step": global_step,
            "anchors": anchors,
            "epoch": anchors / args.anchors_per_epoch,
            "P1": result["p1"],
            "mean_cond_P2_P7": result["mean_conditional_p2_p7"],
            "overall": result["overall_draft_token_acceptance"],
            "loss": mean_loss,
            "conditional_P1_P7": result["conditional_acceptance"],
            "dev_anchors": result["cycles"],
            "eval_elapsed_s": result["elapsed_s"],
            "checkpoint": str(checkpoint_path.resolve()),
            "evaluation": str(eval_path.resolve()),
            "learning_rate": learning_rate(args, max(0, run_step - 1)),
            "go_signal": result["go_signal"],
            "utc_epoch_s": time.time(),
        }
        append_jsonl(metrics_path, metric)
        append_jsonl(events_path, {"event": "dev_complete"} | metric)
        evaluated_steps.add(global_step)
        interval_loss_sum = 0.0
        interval_loss_count = 0
        model.train()

    def save_and_evaluate_checkpoint() -> None:
        checkpoint_path = args.output_dir / f"checkpoint-step-{global_step:06d}.pt"
        payload = checkpoint_payload(
            model=model,
            optimizer=optimizer,
            stream=stream,
            args=args,
            global_step=global_step,
            run_step=run_step,
            anchors=anchors,
            interval_loss_sum=interval_loss_sum,
            interval_loss_count=interval_loss_count,
            target_identity=target_identity,
            train_identity=train_identity,
        )
        atomic_torch_save(payload, checkpoint_path)
        atomic_write_json(
            args.output_dir / "latest-checkpoint.json",
            {
                "step": global_step,
                "run_step": run_step,
                "anchors": anchors,
                "epoch": anchors / args.anchors_per_epoch,
                "path": str(checkpoint_path.resolve()),
                "utc_epoch_s": time.time(),
            },
        )
        append_jsonl(
            events_path,
            {
                "event": "checkpoint_complete",
                "step": global_step,
                "path": str(checkpoint_path.resolve()),
                "utc_epoch_s": time.time(),
            },
        )
        mean_loss = interval_loss_sum / interval_loss_count
        evaluate_checkpoint(checkpoint_path, mean_loss)

    if resume_path and global_step not in evaluated_steps:
        recovery_loss = (
            interval_loss_sum / interval_loss_count
            if interval_loss_count
            else float("nan")
        )
        evaluate_checkpoint(resume_path, recovery_loss)
    elif resume_path and global_step in evaluated_steps:
        interval_loss_sum = 0.0
        interval_loss_count = 0

    optimizer.zero_grad(set_to_none=True)
    model.train()
    worker_started = time.time()
    stopped = False
    while run_step < args.additional_steps:
        if stop_path.exists():
            if interval_loss_count:
                save_and_evaluate_checkpoint()
            stopped = True
            break
        step_started = time.time()
        next_global_step = global_step + 1
        with HardTimeout(args.step_timeout, "training_step_timeout", next_global_step):
            total_value = torch.zeros((), device=device)
            ce_value = torch.zeros((), device=device)
            feature_value = torch.zeros((), device=device)
            for _ in range(args.gradient_accumulation):
                batch = signal_trainer.move_batch(stream.next_batch(), device)
                with signal_trainer.autocast_context(device):
                    loss, components = model(batch)
                    loss = loss / args.gradient_accumulation
                loss.backward()
                total_value += loss.detach()
                ce_value += components["ce"] / args.gradient_accumulation
                feature_value += (
                    components["feature"] / args.gradient_accumulation
                )
            grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            lr = learning_rate(args, run_step)
            for group in optimizer.param_groups:
                group["lr"] = lr
            optimizer.step()
            optimizer.zero_grad(set_to_none=True)
            signal_trainer.synchronize_device(device)
        global_step = next_global_step
        run_step += 1
        anchors += args.microbatch * args.gradient_accumulation
        step_elapsed = time.time() - step_started
        loss_value = float(total_value)
        interval_loss_sum += loss_value
        interval_loss_count += 1
        train_row = {
            "step": global_step,
            "run_step": run_step,
            "anchors": anchors,
            "epoch": anchors / args.anchors_per_epoch,
            "loss": loss_value,
            "ce": float(ce_value),
            "feature_regularization": float(feature_value),
            "learning_rate": lr,
            "gradient_norm": float(grad_norm),
            "step_elapsed_s": step_elapsed,
            "elapsed_worker_s": time.time() - worker_started,
            "attempt_pid": os.getpid(),
        }
        append_jsonl(train_metrics_path, train_row, durable=False)
        if run_step == 1 or run_step % args.log_every == 0:
            print(json.dumps({"event": "training_metric"} | train_row), flush=True)

        periodic = run_step % args.checkpoint_every == 0
        final = run_step == args.additional_steps
        stop_after_step = stop_path.exists()
        if periodic or final or stop_after_step:
            save_and_evaluate_checkpoint()
            if stop_after_step or stop_path.exists():
                stopped = True
                break

    append_jsonl(
        events_path,
        {
            "event": "worker_exit",
            "reason": "stop_sentinel" if stopped else "plan_complete",
            "step": global_step,
            "run_step": run_step,
            "anchors": anchors,
            "epoch": anchors / args.anchors_per_epoch,
            "utc_epoch_s": time.time(),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
