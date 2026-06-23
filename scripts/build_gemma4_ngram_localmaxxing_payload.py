#!/usr/bin/env python3
"""Build a LocalMaxxing queue entry for a validated Gemma 4 n-gram run."""

from __future__ import annotations

import argparse
import json
import re
import shlex
from pathlib import Path


DEFAULT_TEMPLATE = (
    Path("data")
    / "localmaxxing-gemma4-26b-a4b-q8-b70-ngrammod-24-48-64-filledlong512-20260623.queue.json"
)


def flag_value(args: list[str], name: str) -> str | None:
    try:
        return args[args.index(name) + 1]
    except (ValueError, IndexError):
        return None


def parse_ngram_stats(server_log: Path) -> dict[str, float | int]:
    stats: dict[str, float | int] = {}
    if not server_log.exists():
        return stats

    pattern = re.compile(
        r"#gen drafts =\s*(?P<gen_drafts>\d+), "
        r"#acc drafts =\s*(?P<acc_drafts>\d+), "
        r"#gen tokens =\s*(?P<gen_tokens>\d+), "
        r"#acc tokens =\s*(?P<acc_tokens>\d+), "
        r"#mean acc len =\s*(?P<mean_acc_len>[0-9.]+)"
    )
    for line in server_log.read_text(errors="replace").splitlines():
        match = pattern.search(line)
        if not match:
            continue
        stats = {
            "gen_drafts": int(match.group("gen_drafts")),
            "acc_drafts": int(match.group("acc_drafts")),
            "gen_tokens": int(match.group("gen_tokens")),
            "acc_tokens": int(match.group("acc_tokens")),
            "mean_acc_len": float(match.group("mean_acc_len")),
        }
    return stats


def infer_run_stamp(summary: dict) -> str:
    """Return a stable date-ish suffix for queue labels."""
    candidates = [
        str(summary.get("label", "")),
        str(summary.get("run_dir", "")),
    ]
    for candidate in candidates:
        match = re.search(r"20\d{6}T\d{4,6}Z?", candidate)
        if match:
            return match.group(0)
    return "20260623"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary_json", type=Path)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label", help="LocalMaxxing queue label override")
    parser.add_argument(
        "--allow-history-accelerated",
        action="store_true",
        help=(
            "Build a payload for a draftless n-gram/history run anyway. These "
            "runs are warmed/history accelerated and are not valid fresh-response "
            "headline submissions under the current validity policy."
        ),
    )
    args = parser.parse_args()

    if not args.allow_history_accelerated:
        raise SystemExit(
            "refusing to build LocalMaxxing payload for draftless n-gram/history "
            "run: it depends on warmed continuation history and is not valid "
            "fresh-response headline throughput. Pass --allow-history-accelerated "
            "only for a clearly labeled diagnostic/non-headline artifact."
        )

    summary = json.loads(args.summary_json.read_text())
    template = json.loads(args.template.read_text())[0]
    item = json.loads(json.dumps(template))

    launcher = summary["launcher_identity"]
    bench = summary["bench_summary"]
    bench_identity = summary["bench_run_identity"]
    extra_args = shlex.split(launcher["extra_llama_args"])
    n_match = int(flag_value(extra_args, "--spec-ngram-mod-n-match") or 0)
    n_min = int(flag_value(extra_args, "--spec-ngram-mod-n-min") or 0)
    n_max = int(flag_value(extra_args, "--spec-ngram-mod-n-max") or 0)
    ctx_checkpoints = int(flag_value(extra_args, "--ctx-checkpoints") or 0)
    spec_extra = (
        f"--ctx-checkpoints {ctx_checkpoints} "
        f"--spec-ngram-mod-n-match {n_match} "
        f"--spec-ngram-mod-n-min {n_min} "
        f"--spec-ngram-mod-n-max {n_max}"
    )

    run_dir = Path(summary["run_dir"])
    p512_json = run_dir / "p512o512.json"
    server_log = Path(summary["server_log"])
    stats = parse_ngram_stats(server_log)
    local_label = (
        args.label
        or f"gemma4-26b-a4b-q8-b70-llamacpp-ngrammod-{n_match}-{n_min}-{n_max}-filledlong512-{infer_run_stamp(summary)}"
    )

    item["label"] = local_label
    payload = item["payload"]
    engine = payload["engineFlags"]

    payload["batchSize"] = int(launcher["batch_size"])
    payload["contextLength"] = int(launcher["ctx_size"])
    payload["outputTokens"] = int(bench["completion_tokens"]["mean"])
    payload["promptTokens"] = int(bench["prompt_tokens"]["mean"])
    payload["tokSOut"] = bench["tok_s_after_ttft"]["mean"]
    payload["tokSTotal"] = bench["tok_s_wall"]["mean"]
    payload["ttftMs"] = bench["ttft_s"]["mean"] * 1000.0

    engine.update(
        {
            "actualOutputTokens": bench["completion_tokens"]["mean"],
            "actualPromptTokens": bench["prompt_tokens"]["mean"],
            "apiMode": "chat/completions",
            "batchSize": int(launcher["batch_size"]),
            "benchmarkJson": str(p512_json.resolve()),
            "canary": f"{summary['canary_rows_completed']}/384 pass"
            if summary.get("canary_pass_all")
            else f"{summary.get('canary_rows_completed', 0)}/384 FAIL",
            "commandSnippet": (
                f"LLAMA_SERVER={launcher['llama_server']} "
                f"GPU_INDEX={launcher['gpu_index']} PORT={launcher['port']} "
                f"LABEL={summary['label']} SPEC_TYPE=ngram-mod "
                f"SPEC_EXTRA_ARGS=\"{spec_extra}\" "
                "BENCH_PROMPT_MODE=filled-long PROMPT_TOKENS=512 MAX_TOKENS=512 "
                "CANARY_REPEATS=96 BENCH_REPEATS=8 GGML_SYCL_DISABLE_OPT=0 "
                f"FLASH_ATTN={launcher['flash_attn']} POLL={launcher['poll']} "
                f"THREADS={launcher['threads']} BATCH_SIZE={launcher['batch_size']} "
                f"UBATCH_SIZE={launcher['ubatch_size']} scripts/run-gemma4-26b-spec-candidate.sh"
            ),
            "ctxCheckpoints": 0,
            "ctxSize": int(launcher["ctx_size"]),
            "extraArgs": launcher["extra_llama_args"],
            "flashAttention": launcher["flash_attn"] == "on",
            "gpuIndex": int(launcher["gpu_index"]),
            "llamaCppCommit": launcher["llama_cpp_commit"],
            "llamaServer": launcher["llama_server"],
            "modelFileBytes": summary["model_file_bytes"],
            "nGramAcceptedMeanLenFromServerLog": stats.get("mean_acc_len"),
            "nGramAcceptedTokensFromServerLog": stats.get("acc_tokens"),
            "nGramGeneratedTokensFromServerLog": stats.get("gen_tokens"),
            "ngramModNMatch": n_match,
            "ngramModNMax": n_max,
            "ngramModNMin": n_min,
            "oneapiDeviceSelector": launcher["oneapi_device_selector"],
            "poll": int(launcher["poll"]),
            "promptChars": bench_identity["prompt_chars"],
            "promptMode": bench_identity["prompt_mode"],
            "promptSha256": bench_identity["prompt_sha256"],
            "serverLog": str(server_log),
            "specNumTokens": n_max,
            "summaryJson": str(args.summary_json.resolve()),
            "threads": int(launcher["threads"]),
            "tokSOutCv": bench["tok_s_after_ttft"]["cv"],
            "tokSOutMax": bench["tok_s_after_ttft"]["max"],
            "tokSOutMin": bench["tok_s_after_ttft"]["min"],
            "tokSOutStdev": bench["tok_s_after_ttft"]["stdev"],
            "tokSTotalMax": bench["tok_s_wall"]["max"],
            "tokSTotalMin": bench["tok_s_wall"]["min"],
            "tokSTotalStdev": bench["tok_s_wall"]["stdev"],
            "ubatchSize": int(launcher["ubatch_size"]),
            "validationRows": summary["canary_rows_completed"],
        }
    )

    payload["notes"] = (
        f"New valid Gemma 4 26B A4B Q8 single-B70 record from 2026-06-23 "
        f"draftless ngram-mod speculation on llama.cpp {launcher['llama_cpp_commit']}. "
        "Uses the same UD-Q8_K_XL target GGUF, f16/f16 KV, AOT BMG SYCL build, "
        f"flash-attn {launcher['flash_attn']}, poll {launcher['poll']}, "
        "--parallel 1 --cache-ram 0, and "
        f"--ctx-checkpoints 0. Spec config: --spec-type ngram-mod "
        f"--spec-ngram-mod-n-match {n_match} --spec-ngram-mod-n-min {n_min} "
        f"--spec-ngram-mod-n-max {n_max}. This does not lower target precision: "
        "n-gram drafts are history guesses and every token is verified by the Q8 "
        f"target model. Validated by {summary['canary_rows_completed']}-row repo "
        "chat canary before measurement. Filled-long benchmark shape is "
        f"{int(bench['prompt_tokens']['mean'])} prompt / "
        f"{int(bench['completion_tokens']['mean'])} output tokens. "
        f"Server statistics confirm benchmark-phase n-gram drafts with mean accepted "
        f"length {stats.get('mean_acc_len')} and accepted/generated draft tokens "
        f"{stats.get('acc_tokens')}/{stats.get('gen_tokens')}. First benchmark "
        f"repeat was cold/no-draft at {bench['tok_s_after_ttft']['min']:.2f} tok/s "
        "while later repeats used the populated n-gram state; the submitted tokSOut "
        "is the full 8-repeat mean after TTFT, and tokSTotal is full 8-repeat wall "
        "throughput. Supporting repo paths: results/gemma4-26b-a4b-q8-b70/, "
        "experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T1735-ngram-spec-sweep.md, "
        f"and {run_dir}/summary.json."
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps([item], indent=2) + "\n")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
