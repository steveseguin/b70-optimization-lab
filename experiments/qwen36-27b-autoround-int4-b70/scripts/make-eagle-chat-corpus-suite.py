#!/usr/bin/env python3
"""Generate a non-final chat prompt suite for Qwen27 EAGLE data collection.

The fixed realistic promotion suite must stay isolated from draft training.
This generator creates deterministic, diverse engineering/business prompts for
EAGLE corpus collection and held-out calibration only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DOMAINS = [
    (
        "incident-response",
        "a production API outage caused by a cache invalidation rule",
        "impact, timeline, detection gaps, mitigation, and owner handoff",
    ),
    (
        "database-operations",
        "a multi-tenant database migration with strict availability goals",
        "replication checks, rollback criteria, customer impact, and evidence",
    ),
    (
        "security-review",
        "a credential-rotation incident after a leaked deployment token",
        "blast radius, abuse paths, containment, audit logs, and prevention",
    ),
    (
        "performance-debug",
        "a local inference server with unstable decode throughput",
        "benchmark identity, device telemetry, variance controls, and next probes",
    ),
    (
        "api-design",
        "a bulk import API with validation jobs and webhook callbacks",
        "idempotency, abuse limits, schema evolution, observability, and rollout",
    ),
    (
        "capacity-planning",
        "four independent GPU replicas serving single-session workloads",
        "routing, queueing, saturation signals, memory limits, and failover",
    ),
    (
        "code-review",
        "a worker that batches writes, retries failures, and persists dead letters",
        "correctness, concurrency, durability, metrics, and tests",
    ),
    (
        "quality-gates",
        "a benchmark promotion process for local model optimization",
        "fresh prompts, cache controls, quality checks, variance, and audit logs",
    ),
    (
        "release-planning",
        "a risky runtime optimization behind environment flags",
        "rollout stages, monitoring, rollback, owner checklist, and user impact",
    ),
    (
        "long-context",
        "a 32K-context model service with retrieval-style prompts",
        "TTFT, prefill throughput, recall checks, memory pressure, and regressions",
    ),
    (
        "support-escalation",
        "a customer report of slower responses after a model-server upgrade",
        "questions to ask, local diagnostics, escalation data, and safe rollback",
    ),
    (
        "architecture-tradeoff",
        "a decision between kernel work, speculative decoding, and service caching",
        "expected gains, correctness risks, validation cost, and sequencing",
    ),
]


TASKS = [
    (
        "runbook",
        "Write an operational runbook",
        "Use numbered steps with commands or concrete checks where relevant.",
    ),
    (
        "memo",
        "Write a decision memo",
        "State the recommendation, rejected options, risks, and follow-up owners.",
    ),
    (
        "review",
        "Review the proposal as a senior engineer",
        "Put blocking issues first, then non-blocking improvements and tests.",
    ),
    (
        "debug-plan",
        "Create a debugging plan",
        "Separate evidence, hypotheses, experiments, expected outcomes, and stop conditions.",
    ),
    (
        "json-plan",
        "Return compact JSON",
        "Include keys summary, risks, experiments, validation, and rollback.",
    ),
    (
        "checklist",
        "Create a launch checklist",
        "Include preflight, live monitoring, quality gates, rollback, and postmortem evidence.",
    ),
    (
        "teaching-note",
        "Explain the topic to a new teammate",
        "Define terms, show tradeoffs, mention common traps, and end with next actions.",
    ),
    (
        "test-plan",
        "Write a test plan",
        "Include unit, integration, load, failure, and quality checks with pass/fail gates.",
    ),
]


CONSTRAINTS = [
    "Keep the answer practical and avoid marketing language.",
    "Be concise but include enough detail for another engineer to execute.",
    "Do not assume access to proprietary tools beyond logs, shell commands, and metrics.",
    "Call out what evidence would change the recommendation.",
    "Include at least one concrete validation step and one rollback condition.",
    "Avoid repeating the same sentence structure across sections.",
]


VARIANT_GUIDANCE = [
    (
        "baseline",
        "Use a balanced answer with short sections and concrete examples.",
    ),
    (
        "executive",
        "Use a concise leadership-facing tone, but keep technical evidence.",
    ),
    (
        "implementation",
        "Emphasize exact implementation steps, commands, data paths, and tests.",
    ),
    (
        "failure-analysis",
        "Focus on failure modes, rollback triggers, and evidence quality.",
    ),
    (
        "handoff",
        "Write for a teammate who must continue the work without prior context.",
    ),
    (
        "audit",
        "Treat the answer as an audit artifact with assumptions and residual risk.",
    ),
]


def build_prompts(*, variants_per_pair: int = 1) -> list[dict[str, str]]:
    if variants_per_pair < 1:
        raise ValueError("--variants-per-pair must be >= 1")
    if variants_per_pair > len(VARIANT_GUIDANCE):
        raise ValueError(
            f"--variants-per-pair must be <= {len(VARIANT_GUIDANCE)}"
        )
    prompts: list[dict[str, str]] = []
    for domain_index, (domain_id, scenario, focus) in enumerate(DOMAINS):
        for task_index, (task_id, instruction, task_constraint) in enumerate(TASKS):
            for variant_index in range(variants_per_pair):
                constraint = CONSTRAINTS[
                    (domain_index + task_index + variant_index)
                    % len(CONSTRAINTS)
                ]
                variant_id, variant_guidance = VARIANT_GUIDANCE[variant_index]
                suffix = "" if variants_per_pair == 1 else f"-{variant_id}"
                prompt_id = f"{domain_id}-{task_id}{suffix}"
                prompt = (
                    f"{instruction} for {scenario}.\n\n"
                    f"Focus on {focus}.\n"
                    f"{task_constraint}\n"
                    f"{constraint}\n"
                    f"{variant_guidance}\n"
                    "Use realistic names for systems, metrics, and artifacts, "
                    "but do not refer to any benchmark final-suite prompt."
                )
                prompts.append({
                    "id": prompt_id,
                    "family": domain_id,
                    "task": task_id,
                    "variant": variant_id,
                    "prompt": prompt,
                })
    return prompts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(
            "experiments/qwen36-27b-autoround-int4-b70/"
            "eagle-chat-corpus-v2-suite.json"
        ),
    )
    parser.add_argument(
        "--variants-per-pair",
        type=int,
        default=1,
        help=(
            "Number of deterministic prompt variants to emit for each "
            "domain/task pair. Default 1 preserves the original 96-prompt v2 "
            "suite; 4 emits a 384-prompt non-final training suite."
        ),
    )
    parser.add_argument(
        "--suite-id",
        default="qwen36-27b-autoround-int4-b70-eagle-chat-corpus-v2",
    )
    parser.add_argument("--version", default="2026-07-04")
    args = parser.parse_args()
    prompts = build_prompts(variants_per_pair=args.variants_per_pair)
    payload = {
        "suite_id": args.suite_id,
        "version": args.version,
        "classification": "diagnostic_only_nonfinal_eagle_training",
        "policy": (
            "Use only for EAGLE corpus collection, held-out calibration, and "
            "draft research. Do not use as a final promotion benchmark or "
            "LocalMaxxing throughput claim."
        ),
        "prompt_count": len(prompts),
        "variants_per_pair": args.variants_per_pair,
        "families": sorted({p["family"] for p in prompts}),
        "tasks": sorted({p["task"] for p in prompts}),
        "variants": sorted({p["variant"] for p in prompts}),
        "prompts": prompts,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
