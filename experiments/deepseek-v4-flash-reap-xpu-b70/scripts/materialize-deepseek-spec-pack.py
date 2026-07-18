#!/usr/bin/env python3
"""Materialize a randomized held-out speculative-decoding request pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import secrets
from pathlib import Path

from transformers import AutoTokenizer


SHORT_COUNTS = {"code": 12, "math_reasoning": 10, "mixed": 20, "tools_json": 6}
SHORT_TOKEN_BUCKETS = ((32, 128), (129, 512), (513, 900))
OUTPUT_BUCKETS = ((8, 48), (96, 192), (256, 512))
WORDS = (
    "amber birch cobalt delta ember fern granite harbor indigo juniper kelp "
    "lilac maple nickel opal pine quartz river saffron thyme umber violet "
    "willow xenon yarrow zinc atlas beacon cipher drift elm frost grove helix"
).split()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_exclusive(path: Path, payload: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(payload)


def base_prompt(category: str, rng: random.Random, nonce: str) -> str:
    a, b, c = (rng.randint(11, 9999) for _ in range(3))
    w = rng.sample(WORDS, 6)
    if category == "code":
        return (
            f"Request nonce {nonce}. Diagnose a concurrency bug in a bounded queue "
            f"whose capacities change from {a} to {b}. Provide a minimal patch, tests "
            f"for cancellation and wraparound, and explain why the tempting {w[0]} "
            f"shortcut races. Do not rely on prior requests."
        )
    if category == "math_reasoning":
        return (
            f"Request nonce {nonce}. A process starts with {a}, applies x -> "
            f"(3x+{b}) mod {c + 10007}, and records only every seventh state. "
            "Derive a checkable method for the 40th record, state assumptions, and "
            "verify the result by an independent invariant."
        )
    if category == "tools_json":
        return (
            f"Request nonce {nonce}. Return strict JSON only with keys plan, risks, "
            f"and checks for moving {a} {w[1]} records between regions {w[2]} and "
            f"{w[3]}. Use integers for limits and include exactly three checks."
        )
    return (
        f"Request nonce {nonce}. Compare two deployment plans: {w[0]} uses {a} "
        f"workers with delayed acknowledgements, while {w[1]} uses {b} workers and "
        f"periodic checkpoints every {c % 97 + 3} events. Recommend one, quantify "
        "failure modes, and give a reversible migration sequence."
    )


def pad_to_bucket(
    tokenizer: object,
    prompt: str,
    low: int,
    high: int,
    rng: random.Random,
) -> tuple[str, int]:
    tokens = tokenizer.encode(prompt, add_special_tokens=False)
    while len(tokens) < low:
        serial = rng.randint(100000, 999999)
        prompt += " Evidence fragment " + str(serial) + ": " + " ".join(
            rng.sample(WORDS, 8)
        ) + "."
        tokens = tokenizer.encode(prompt, add_special_tokens=False)
    if len(tokens) > high:
        tokens = tokens[:high]
        prompt = tokenizer.decode(tokens, skip_special_tokens=True)
        tokens = tokenizer.encode(prompt, add_special_tokens=False)
    if not low <= len(tokens) <= high:
        raise ValueError(f"could not fit prompt into bucket {low}-{high}: {len(tokens)}")
    return prompt, len(tokens)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-candidate", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--pack", choices=("A", "B"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if args.out.exists():
        raise SystemExit(f"refusing to overwrite held-out pack: {args.out}")
    for path in (args.frozen_candidate, args.contract):
        if not path.is_file():
            raise SystemExit(f"missing required file: {path}")
    frozen = json.loads(args.frozen_candidate.read_text())
    contract = json.loads(args.contract.read_text())
    if frozen.get("holdout_seed_materialized") is not False:
        raise SystemExit("candidate was not frozen before held-out materialization")
    if contract.get("contract_id") != "deepseek-v4-flash-b70-spec-eval-v1":
        raise SystemExit("unexpected evaluation contract")

    seed_hex = secrets.token_hex(32)
    rng = random.Random(int(seed_hex, 16))
    tokenizer = AutoTokenizer.from_pretrained(
        args.tokenizer, trust_remote_code=False, local_files_only=True
    )
    requests = []
    ordinal = 0
    for category, count in SHORT_COUNTS.items():
        for _ in range(count):
            bucket = SHORT_TOKEN_BUCKETS[ordinal % len(SHORT_TOKEN_BUCKETS)]
            output_bucket = OUTPUT_BUCKETS[ordinal % len(OUTPUT_BUCKETS)]
            nonce = secrets.token_hex(12)
            prompt, prompt_tokens = pad_to_bucket(
                tokenizer,
                base_prompt(category, rng, nonce),
                *bucket,
                rng,
            )
            requests.append(
                {
                    "label": f"{args.pack}-short-{ordinal:03d}",
                    "category": category,
                    "prompt": prompt,
                    "prompt_tokens": prompt_tokens,
                    "max_tokens": rng.randint(*output_bucket),
                    "long_context": False,
                }
            )
            ordinal += 1

    for long_index in range(16):
        target = 2048 if long_index % 2 == 0 else 4096
        nonce = secrets.token_hex(12)
        prompt = (
            f"Request nonce {nonce}. The following independent field notes are "
            "unpredictable. Identify contradictions and recover the final numbered "
            "instruction; do not assume repeated text."
        )
        prompt, prompt_tokens = pad_to_bucket(
            tokenizer, prompt, target, target + 24, rng
        )
        requests.append(
            {
                "label": f"{args.pack}-long-{long_index:03d}",
                "category": "long_context",
                "prompt": prompt,
                "prompt_tokens": prompt_tokens,
                "max_tokens": 128 if long_index % 2 == 0 else 256,
                "long_context": True,
            }
        )
    rng.shuffle(requests)

    payload = {
        "schema_version": 1,
        "classification": "deepseek_v4_spec_heldout_pack",
        "pack": args.pack,
        "seed_hex": seed_hex,
        "candidate_manifest": {
            "path": str(args.frozen_candidate.resolve()),
            "sha256": sha256(args.frozen_candidate.resolve()),
        },
        "contract": {
            "path": str(args.contract.resolve()),
            "sha256": sha256(args.contract.resolve()),
        },
        "request_count": len(requests),
        "labels_must_not_be_sent_to_server": True,
        "requests": requests,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_exclusive(args.out, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
