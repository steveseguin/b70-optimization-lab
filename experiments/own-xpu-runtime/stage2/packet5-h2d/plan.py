#!/usr/bin/env python3
"""CPU-only census-derived copy plan; never imports a device library."""
import argparse
import hashlib
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CENSUS = ROOT / "experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json"
CENSUS_SHA = "3312f5a18582788c5c6c84572fd616488b6835b454272c81eec218a58521607c"
CHUNK = 128 * 2**20
REPS = 20

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def chunks(size):
    if type(size) is not int or not 0 < size <= 256 * 2**20:
        raise ValueError("bounded copy size")
    return [min(CHUNK, size - off) for off in range(0, size, CHUNK)]

def make_plan():
    if sha(CENSUS) != CENSUS_SHA:
        raise ValueError("census identity changed")
    tensors = json.loads(CENSUS.read_text())["tensors"]
    groups = {}
    for layer in range(48):
        parts = []
        for part in ("gate", "up", "down"):
            rows = [t for t in tensors if t["name"] == f"blk.{layer}.ffn_{part}_exps.weight"]
            if len(rows) != 1 or rows[0]["shape"][0] != 512 or rows[0]["bytes"] % 512:
                raise ValueError("expert extent")
            t = rows[0]
            parts.append(dict(part=part, grid=t["type"], bytes=t["bytes"] // 512))
        key = tuple((p["grid"], p["bytes"]) for p in parts)
        group = groups.setdefault(key, dict(layers=[], parts=parts, triplet_bytes=sum(p["bytes"] for p in parts)))
        group["layers"].append(layer)
    cases = []
    for i, group in enumerate(groups.values()):
        for count in (1, 10):
            n = count * group["triplet_bytes"]
            cases.append(dict(label=f"grid{i}-experts{count}", bytes=n, chunks=chunks(n), experts=count))
    for mib in (64, 256):
        n = mib * 2**20
        cases.append(dict(label=f"block-{mib}MiB", bytes=n, chunks=chunks(n), experts=None))
    return dict(schema="own-runtime.h2d.plan.v1", measured=False, census_sha256=CENSUS_SHA,
                expert_grids=list(groups.values()), cases=cases, repetitions=REPS, seconds=120,
                active_expert_bytes_per_token=sum(len(g["layers"])*10*g["triplet_bytes"] for g in groups.values()),
                copy_limit_bytes=CHUNK, pending_limit=2,
                overlap=dict(kernel="packet2 IQ2_S GEMV", rows=640, columns=2560, subgroup=16,
                             independent_buffers=True, modes=["copy-only", "compute-only", "serial", "concurrent"]),
                requested_peak=dict(card_a_device_bytes=2*256*2**20+524800+5120+1280,
                                    card_a_pinned_bytes=256*2**20, card_a_pageable_bytes=256*2**20,
                                    optional_card_b_device_bytes=256*2**20, optional_card_b_pinned_bytes=256*2**20,
                                    driver_shadow_bytes=None, runtime_overhead_bytes=None))

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--dry-plan", action="store_true", required=True)
    p.parse_args(); print(json.dumps(make_plan(), indent=2))
