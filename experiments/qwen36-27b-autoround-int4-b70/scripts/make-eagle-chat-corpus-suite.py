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
    (
        "cost-optimization",
        "an inference service whose GPU cost per successful request is rising",
        "utilization, batching tradeoffs, quality constraints, cache boundaries, and reporting",
    ),
    (
        "edge-deployment",
        "a model endpoint being moved from a central cluster to local edge devices",
        "hardware variance, observability, rollout safety, fallback routing, and support load",
    ),
    (
        "data-pipeline",
        "a nightly analytics pipeline that feeds model-quality dashboards",
        "schema drift, late data, validation, lineage, and reproducibility",
    ),
    (
        "incident-postmortem",
        "a production regression caused by a performance optimization that passed smoke tests",
        "root cause, missed signals, impact accounting, action items, and owner follow-up",
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
    (
        "risk-register",
        "Create a risk register",
        "List risks, likelihood, impact, detection signal, mitigation, owner, and review date.",
    ),
    (
        "migration-plan",
        "Write a migration plan",
        "Include phases, compatibility checks, data validation, cutover, rollback, and communication.",
    ),
    (
        "slo-analysis",
        "Analyze service-level objectives",
        "Cover user-facing metrics, measurement windows, alert thresholds, error budget, and tradeoffs.",
    ),
    (
        "customer-response",
        "Draft a customer-facing response",
        "Be transparent, technically accurate, action-oriented, and avoid overpromising.",
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


V6_DOMAINS = [
    (
        "code-debugging",
        "a Python service patch that fixed one bug but introduced intermittent failures",
        "stack traces, minimal reproduction, patch review, tests, and rollback criteria",
    ),
    (
        "sql-data-analysis",
        "a product analytics question answered from partially documented SQL tables",
        "joins, missing data, assumptions, validation queries, and decision-ready summary",
    ),
    (
        "config-devops",
        "a deployment controlled by YAML, environment variables, and systemd units",
        "configuration drift, safe defaults, smoke tests, logging, and rollback",
    ),
    (
        "api-client-integration",
        "a client library integrating pagination, retries, auth refresh, and webhooks",
        "error handling, idempotency, rate limits, example code, and observability",
    ),
    (
        "product-support",
        "a user report that a new feature is confusing and sometimes produces wrong output",
        "clarifying questions, reproduction steps, user-facing response, and escalation",
    ),
    (
        "personal-productivity",
        "a busy technical lead trying to organize a week of meetings and deliverables",
        "prioritization, tradeoffs, schedule constraints, communication, and follow-through",
    ),
    (
        "document-editing",
        "a messy internal draft that needs to become a concise technical announcement",
        "structure, tone, factual precision, missing context, and final wording",
    ),
    (
        "quantitative-planning",
        "a capacity or budget question with approximate numbers and uncertain assumptions",
        "calculation steps, sensitivity ranges, constraints, caveats, and recommendation",
    ),
    (
        "compliance-security-advice",
        "a team asking whether a data-handling workflow creates security or compliance risk",
        "scope, policy assumptions, risk reduction, audit evidence, and safe language",
    ),
    (
        "general-technical-qa",
        "a practical engineering question that needs a direct but nuanced answer",
        "definitions, tradeoffs, examples, limitations, and next checks",
    ),
    (
        "dependency-upgrade",
        "a framework upgrade that changes APIs, performance characteristics, and packaging",
        "migration order, compatibility, test coverage, deprecation risk, and rollback",
    ),
    (
        "testing-strategy",
        "a flaky workflow where unit tests pass but production behavior still regresses",
        "test gaps, fixtures, deterministic reproduction, monitoring, and owner actions",
    ),
    (
        "observability-logs",
        "a pasted log excerpt with mixed warnings, errors, timestamps, and metric names",
        "signal extraction, likely root cause, unknowns, next commands, and alert tuning",
    ),
    (
        "shell-automation",
        "a local automation task that should be reliable, idempotent, and easy to audit",
        "shell commands, dry-run behavior, file safety, logging, and failure recovery",
    ),
    (
        "migration-support",
        "a customer-facing migration from one runtime or model profile to another",
        "compatibility, quality expectations, validation, communication, and fallback",
    ),
    (
        "customer-debugging",
        "a support case where the user has partial symptoms and may be misattributing cause",
        "questions, hypothesis ranking, plain-language explanation, and concrete next steps",
    ),
]


V6_TASKS = [
    (
        "direct-answer",
        "Answer the user's question directly",
        "Start with the answer, then give the reasoning and caveats.",
    ),
    (
        "compare-options",
        "Compare the viable options",
        "Use a compact table or clearly separated tradeoffs, then choose a default.",
    ),
    (
        "rewrite",
        "Rewrite the provided rough material",
        "Improve clarity and structure while preserving technical meaning.",
    ),
    (
        "summarize-context",
        "Summarize the pasted context",
        "Separate known facts, likely interpretation, unknowns, and next actions.",
    ),
    (
        "extract-table",
        "Extract the important details into a table",
        "Include only fields that would change a decision or follow-up task.",
    ),
    (
        "emit-json-yaml",
        "Return a structured JSON or YAML artifact",
        "Use stable keys, concrete values, and short explanatory strings.",
    ),
    (
        "write-code-tests",
        "Write code or tests for the scenario",
        "Include a short explanation of the assumptions and how to run it.",
    ),
    (
        "diagnose-logs",
        "Diagnose the symptoms from the available evidence",
        "Rank hypotheses, list checks, and avoid claiming certainty too early.",
    ),
    (
        "calculate",
        "Calculate the likely outcome from approximate inputs",
        "Show the math, note uncertainty, and provide a decision threshold.",
    ),
    (
        "draft-email",
        "Draft a concise message to a stakeholder",
        "Be accurate, action-oriented, and avoid overpromising.",
    ),
    (
        "ambiguous-answer",
        "Answer under ambiguity",
        "State assumptions, give a useful answer, and identify what would change it.",
    ),
    (
        "step-by-step-plan",
        "Create a step-by-step plan",
        "Keep the steps executable and include validation checkpoints.",
    ),
]


V6_VARIANT_GUIDANCE = [
    (
        "messy-user",
        "The user wording is informal and slightly messy; answer clearly without correcting their style.",
    ),
    (
        "terse",
        "Use a terse answer with minimal formatting and no unnecessary preamble.",
    ),
    (
        "code-first",
        "Lead with the concrete command, code, query, or config when one is useful.",
    ),
    (
        "table-first",
        "Lead with a compact table when it improves scanability.",
    ),
    (
        "structured-only",
        "Use a structured artifact only; avoid narrative except short field values.",
    ),
    (
        "reviewer",
        "Respond as a skeptical reviewer who wants evidence and clear failure modes.",
    ),
]


def build_prompts(
    *,
    variants_per_pair: int = 1,
    domains: list[tuple[str, str, str]] | None = None,
    tasks: list[tuple[str, str, str]] | None = None,
    variant_guidance: list[tuple[str, str]] | None = None,
) -> list[dict[str, str]]:
    domains = domains or DOMAINS
    tasks = tasks or TASKS
    variant_guidance = variant_guidance or VARIANT_GUIDANCE
    if variants_per_pair < 1:
        raise ValueError("--variants-per-pair must be >= 1")
    if variants_per_pair > len(variant_guidance):
        raise ValueError(
            f"--variants-per-pair must be <= {len(variant_guidance)}"
        )
    prompts: list[dict[str, str]] = []
    for domain_index, (domain_id, scenario, focus) in enumerate(domains):
        for task_index, (task_id, instruction, task_constraint) in enumerate(tasks):
            for variant_index in range(variants_per_pair):
                constraint = CONSTRAINTS[
                    (domain_index + task_index + variant_index)
                    % len(CONSTRAINTS)
                ]
                variant_id, guidance = variant_guidance[variant_index]
                suffix = "" if variants_per_pair == 1 else f"-{variant_id}"
                prompt_id = f"{domain_id}-{task_id}{suffix}"
                prompt = (
                    f"{instruction} for {scenario}.\n\n"
                    f"Focus on {focus}.\n"
                    f"{task_constraint}\n"
                    f"{constraint}\n"
                    f"{guidance}\n"
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
    parser.add_argument(
        "--preset",
        default="ops",
        choices=("ops", "chat-v6"),
        help=(
            "Prompt-family preset. 'ops' preserves the existing v2-v5 "
            "engineering/business suite shape; 'chat-v6' emits broader "
            "non-final chat-style prompts for EAGLE/DFlash training."
        ),
    )
    parser.add_argument("--version", default="2026-07-04")
    args = parser.parse_args()
    if args.preset == "chat-v6":
        prompts = build_prompts(
            variants_per_pair=args.variants_per_pair,
            domains=V6_DOMAINS,
            tasks=V6_TASKS,
            variant_guidance=V6_VARIANT_GUIDANCE,
        )
    else:
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
