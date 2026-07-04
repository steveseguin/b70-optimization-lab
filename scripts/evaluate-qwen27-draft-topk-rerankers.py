#!/usr/bin/env python3
"""Evaluate simple Qwen27 draft top-k rerankers offline.

Diagnostic only. This script uses draft top-k traces plus verifier traces to
estimate whether cheap reranking rules can improve accepted tokens per MTP
step before any endpoint/source experiment is attempted.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


NEG_INF = -1_000_000_000.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft-topk", required=True)
    parser.add_argument("--verify-trace", required=True)
    parser.add_argument("--result-json", default="")
    parser.add_argument("--out", default="")
    return parser.parse_args()


def load_jsonl(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        row["_line_no"] = line_no
        rows.append(row)
    return rows


def verify_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        for rec in row.get("records") or []:
            num_draft = int(rec.get("num_draft_tokens") or 0)
            if num_draft <= 0:
                continue
            draft_ids = [int(x) for x in rec.get("draft_token_ids") or []]
            target_ids = [
                int(x) for x in rec.get("target_argmax_token_ids") or []
            ]
            if draft_ids and all(x == 0 for x in draft_ids):
                continue
            if len(draft_ids) < num_draft or len(target_ids) < num_draft:
                continue
            out.append({
                "ts": float(row.get("ts") or 0.0),
                "draft_ids": draft_ids[:num_draft],
                "target_ids": target_ids[:num_draft],
                "prefix_accepted": int(rec.get("prefix_accepted") or 0),
            })
    return out


def draft_groups(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for row in rows:
        pos = row.get("draft_pos")
        if pos == 0 and current:
            groups.append(current)
            current = []
        current.append(row)
        if len(current) == 3:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def group_sampled_ids(group: list[dict[str, Any]]) -> tuple[int, ...]:
    sampled: list[int] = []
    for row in group:
        sampled_ids = row.get("sampled_token_ids") or []
        if not sampled_ids:
            break
        sampled.append(int(sampled_ids[0]))
    return tuple(sampled)


def align_groups(
    groups: list[list[dict[str, Any]]],
    records: list[dict[str, Any]],
    *,
    lookahead: int = 64,
) -> tuple[list[tuple[list[dict[str, Any]], dict[str, Any]]], dict[str, Any]]:
    aligned: list[tuple[list[dict[str, Any]], dict[str, Any]]] = []
    group_index = 0
    exact = 0
    fallback = 0
    skipped = 0

    for rec in records:
        wanted = tuple(rec["draft_ids"][:3])
        found_index = None
        for candidate_index in range(group_index,
                                     min(len(groups), group_index + lookahead)):
            sampled = group_sampled_ids(groups[candidate_index])
            if sampled[:len(wanted)] == wanted:
                found_index = candidate_index
                break
        if found_index is None:
            if group_index >= len(groups):
                break
            found_index = group_index
            fallback += 1
        else:
            exact += 1
            skipped += found_index - group_index
        aligned.append((groups[found_index], rec))
        group_index = found_index + 1

    skipped += max(0, len(groups) - group_index)
    return aligned, {
        "exact_group_matches": exact,
        "fallback_matches": fallback,
        "skipped_draft_groups": skipped,
        "unused_verify_records": max(0, len(records) - len(aligned)),
    }


def prompt_windows(result_json: str) -> list[dict[str, Any]]:
    if not result_json:
        return []
    result = json.loads(Path(result_json).read_text())
    windows = []
    for row in result.get("rows") or []:
        start = row.get("request_started_epoch_s")
        end = row.get("request_ended_epoch_s")
        if start is None or end is None:
            continue
        windows.append({
            "start": float(start),
            "end": float(end),
            "prompt_index": int(row.get("prompt_index") or 0),
            "prompt_id": row.get("prompt_id"),
        })
    return windows


def assign_prompt(ts: float, windows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for window in windows:
        # Permit a small boundary tolerance because traces and stream timing are
        # emitted from different code paths.
        if window["start"] - 0.5 <= ts <= window["end"] + 0.5:
            return window
    return None


def accepted_len(pred_ids: list[int], target_ids: list[int]) -> int:
    accepted = 0
    for pred_id, target_id in zip(pred_ids, target_ids):
        if pred_id != target_id:
            break
        accepted += 1
    return accepted


def build_steps(
    aligned: list[tuple[list[dict[str, Any]], dict[str, Any]]],
    windows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for step_index, (group, rec) in enumerate(aligned):
        if len(group) < 3 or len(rec["target_ids"]) < 3:
            continue
        positions = []
        for pos in range(3):
            top_ids_rows = group[pos].get("top_token_ids") or []
            top_values_rows = group[pos].get("top_values") or []
            if not top_ids_rows or not top_values_rows:
                break
            positions.append({
                "ids": [int(x) for x in top_ids_rows[0]],
                "values": [float(x) for x in top_values_rows[0]],
                "target": int(rec["target_ids"][pos]),
            })
        if len(positions) != 3:
            continue
        window = assign_prompt(float(rec.get("ts") or 0.0), windows)
        steps.append({
            "step_index": step_index,
            "prompt_index": None if window is None else window["prompt_index"],
            "prompt_id": None if window is None else window["prompt_id"],
            "positions": positions,
        })
    return steps


def predict_base(pos: dict[str, Any]) -> int:
    return int(pos["ids"][0])


def predict_margin(pos: dict[str, Any], threshold: float, rank: int) -> int:
    ids = pos["ids"]
    values = pos["values"]
    if rank >= len(ids) or len(values) < 2:
        return int(ids[0])
    margin = float(values[0]) - float(values[1])
    if margin < threshold:
        return int(ids[rank])
    return int(ids[0])


def predict_bias(pos_index: int, pos: dict[str, Any],
                 bias: dict[tuple[int, int], float]) -> int:
    best_id = int(pos["ids"][0])
    best_score = float(pos["values"][0]) + bias[(pos_index, best_id)]
    for token_id, value in zip(pos["ids"][1:], pos["values"][1:]):
        token_id = int(token_id)
        score = float(value) + bias[(pos_index, token_id)]
        if score > best_score:
            best_id = token_id
            best_score = score
    return best_id


def evaluate_steps(steps: list[dict[str, Any]], predictor) -> dict[str, Any]:
    prefix_sum = 0
    token_hits = 0
    target_in_topk = 0
    positions = 0
    per_pos_hits: Counter[int] = Counter()
    per_pos_total: Counter[int] = Counter()
    accepted_hist: Counter[int] = Counter()

    for step in steps:
        pred_ids: list[int] = []
        target_ids: list[int] = []
        for pos_index, pos in enumerate(step["positions"]):
            pred = int(predictor(pos_index, pos))
            target = int(pos["target"])
            pred_ids.append(pred)
            target_ids.append(target)
            token_hits += pred == target
            target_in_topk += target in pos["ids"]
            positions += 1
            per_pos_hits[pos_index] += pred == target
            per_pos_total[pos_index] += 1
        prefix = accepted_len(pred_ids, target_ids)
        prefix_sum += prefix
        accepted_hist[prefix] += 1

    if not steps:
        return {"steps": 0}
    return {
        "steps": len(steps),
        "mean_target_tokens_per_step": 1.0 + prefix_sum / len(steps),
        "token_match_rate": token_hits / positions if positions else None,
        "target_in_topk_rate": target_in_topk / positions if positions else None,
        "accepted_hist": {str(k): v for k, v in sorted(accepted_hist.items())},
        "per_position_match_rate": {
            str(k): per_pos_hits[k] / per_pos_total[k]
            for k in sorted(per_pos_total)
        },
    }


def split_steps(steps: list[dict[str, Any]]) -> tuple[list[dict[str, Any]],
                                                     list[dict[str, Any]], str]:
    if all(step["prompt_index"] is not None for step in steps):
        train = [s for s in steps if int(s["prompt_index"]) % 2 == 0]
        test = [s for s in steps if int(s["prompt_index"]) % 2 == 1]
        return train, test, "prompt_index_parity"
    train = [s for s in steps if int(s["step_index"]) % 2 == 0]
    test = [s for s in steps if int(s["step_index"]) % 2 == 1]
    return train, test, "step_index_parity"


def find_margin_rule(train: list[dict[str, Any]],
                     test: list[dict[str, Any]]) -> dict[str, Any]:
    thresholds = [
        NEG_INF, -2.0, -1.0, -0.5, -0.25, -0.1, -0.05, 0.0, 0.05, 0.1,
        0.25, 0.5, 1.0, 2.0, -NEG_INF,
    ]
    best: dict[str, Any] | None = None
    for rank in (1, 2, 3):
        for t0 in thresholds:
            for t1 in thresholds:
                for t2 in thresholds:
                    thresholds_by_pos = [t0, t1, t2]

                    def predictor(pos_index: int, pos: dict[str, Any]) -> int:
                        return predict_margin(
                            pos, thresholds_by_pos[pos_index], rank)

                    train_eval = evaluate_steps(train, predictor)
                    key = (
                        train_eval.get("mean_target_tokens_per_step") or 0.0,
                        train_eval.get("token_match_rate") or 0.0,
                    )
                    if best is None or key > best["key"]:
                        test_eval = evaluate_steps(test, predictor)
                        best = {
                            "key": key,
                            "rank": rank + 1,
                            "thresholds": thresholds_by_pos,
                            "train": train_eval,
                            "test": test_eval,
                        }
    assert best is not None
    best.pop("key", None)
    return best


def train_sparse_bias(train: list[dict[str, Any]],
                      test: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    train_positions = [
        (step["step_index"], pos_index, pos)
        for step in train
        for pos_index, pos in enumerate(step["positions"])
    ]
    for lr in (0.05, 0.1, 0.2, 0.5, 1.0):
        for epochs in (1, 2, 4, 8):
            bias: defaultdict[tuple[int, int], float] = defaultdict(float)
            order = list(range(len(train_positions)))
            for epoch in range(epochs):
                random.Random(20260704 + epoch).shuffle(order)
                for idx in order:
                    _, pos_index, pos = train_positions[idx]
                    target = int(pos["target"])
                    if target not in pos["ids"]:
                        continue
                    pred = predict_bias(pos_index, pos, bias)
                    if pred == target:
                        continue
                    bias[(pos_index, target)] += lr
                    bias[(pos_index, pred)] -= lr

            def predictor(pos_index: int, pos: dict[str, Any]) -> int:
                return predict_bias(pos_index, pos, bias)

            train_eval = evaluate_steps(train, predictor)
            test_eval = evaluate_steps(test, predictor)
            results.append({
                "lr": lr,
                "epochs": epochs,
                "nonzero_bias_terms": sum(1 for value in bias.values()
                                          if abs(value) > 1e-12),
                "train": train_eval,
                "test": test_eval,
            })
    results.sort(
        key=lambda row: (
            row["test"].get("mean_target_tokens_per_step") or 0.0,
            row["test"].get("token_match_rate") or 0.0,
        ),
        reverse=True,
    )
    return results[:8]


def main() -> int:
    args = parse_args()
    draft_rows = load_jsonl(args.draft_topk)
    verifier_rows = verify_records(load_jsonl(args.verify_trace))
    aligned, alignment = align_groups(draft_groups(draft_rows), verifier_rows)
    steps = build_steps(aligned, prompt_windows(args.result_json))
    train, test, split = split_steps(steps)

    base_train = evaluate_steps(train, lambda _pos_index, pos: predict_base(pos))
    base_test = evaluate_steps(test, lambda _pos_index, pos: predict_base(pos))
    oracle_train = evaluate_steps(
        train,
        lambda _pos_index, pos: (
            int(pos["target"]) if int(pos["target"]) in pos["ids"]
            else predict_base(pos)
        ),
    )
    oracle_test = evaluate_steps(
        test,
        lambda _pos_index, pos: (
            int(pos["target"]) if int(pos["target"]) in pos["ids"]
            else predict_base(pos)
        ),
    )
    margin = find_margin_rule(train, test)
    sparse_bias = train_sparse_bias(train, test)

    summary = {
        "classification": "diagnostic_only_offline_reranker_eval",
        "draft_topk": args.draft_topk,
        "verify_trace": args.verify_trace,
        "result_json": args.result_json or None,
        "alignment": alignment,
        "steps": len(steps),
        "split": split,
        "train_steps": len(train),
        "test_steps": len(test),
        "base": {"train": base_train, "test": base_test},
        "oracle_topk": {"train": oracle_train, "test": oracle_test},
        "best_margin_rule": margin,
        "best_sparse_bias": sparse_bias,
    }
    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
