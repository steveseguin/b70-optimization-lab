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


V6B_CONTEXT_DOMAINS = [
    {
        "id": "incident-log-triage",
        "scenario": "a production API incident with logs and partial metrics",
        "focus": "timeline, root-cause hypotheses, missing evidence, and rollback",
        "context": """Context:
2026-07-06T14:03:12Z api-gateway-7 WARN cache_miss_rate=0.41 route=/v1/chat tenant=acme
2026-07-06T14:04:55Z api-gateway-7 ERROR upstream_timeout_ms=30000 route=/v1/chat request_id=req-1882
2026-07-06T14:05:18Z worker-2 INFO deploy_sha=9f31a2c feature_cache_key_v2=true
2026-07-06T14:07:44Z redis-3 WARN evicted_keys=18421 used_memory=29.7GiB maxmemory=30.0GiB
metric p95_latency_ms: 820 -> 6400, 5xx_rate: 0.2% -> 6.8%, cache_hit_rate: 83% -> 49%
Change window: cache key normalization deployed at 14:02Z to 50% of tenants.""",
    },
    {
        "id": "sql-analytics-table",
        "scenario": "a product analytics question with table schemas and sample rows",
        "focus": "joins, assumptions, validation queries, and decision-ready numbers",
        "context": """Context:
tables:
users(user_id, signup_at, plan, region)
events(event_id, user_id, event_name, occurred_at, session_id)
invoices(invoice_id, user_id, amount_usd, status, paid_at)
sample users: u1 pro us, u2 free eu, u3 pro us, u4 team apac
sample events: u1 export_clicked 2026-07-01, u1 export_done 2026-07-01, u3 export_clicked 2026-07-02
sample invoices: u1 49 paid, u3 49 failed, u4 199 paid
Question: estimate paid-pro export completion rate for July 1-7 and list validation checks.""",
    },
    {
        "id": "yaml-systemd-config",
        "scenario": "a deployment controlled by YAML, environment variables, and systemd",
        "focus": "safe defaults, drift, smoke tests, logging, and rollback",
        "context": """Context:
service file:
[Service]
Environment=MODEL_PATH=/mnt/models/qwen27
Environment=MAX_MODEL_LEN=2048
Environment=ENABLE_GRAPH=1
ExecStart=/opt/serve-vllm.sh --port 19410 --gpu-memory-utilization 0.90
Restart=on-failure
YAML override:
max_num_batched_tokens: 1024
enable_prompt_cache: false
speculative_tokens: 3
Recent drift: staging has MAX_MODEL_LEN=32768 and gpu-memory-utilization=0.82.""",
    },
    {
        "id": "python-stacktrace",
        "scenario": "a Python patch that fixed one bug but introduced intermittent failures",
        "focus": "minimal reproduction, likely cause, patch review, and tests",
        "context": """Context:
Traceback:
  File "scheduler.py", line 188, in assign_slot
    state.blocks[slot].copy_(saved)
IndexError: index 32 is out of bounds for dimension 0 with size 32
Patch:
- if slot:
-     restore(slot)
+ if slot is not None:
+     restore(slot)
Observed: failure appears only when slot=32 after a rejected speculative batch.
Test gap: existing tests cover slot None, slot 0, and slot 3, not upper-bound slots.""",
    },
    {
        "id": "benchmark-variance-table",
        "scenario": "a local inference benchmark with variance and temperature concerns",
        "focus": "fair comparison, variance controls, telemetry, and promotion rules",
        "context": """Context:
run,label,gpu,temp_c,median_tok_s,p10_tok_s,cached_tokens
1,baseline,gpu0,54,67.3,62.1,0
2,candidate,gpu1,56,68.0,62.0,0
3,baseline,gpu2,71,64.1,58.4,0
4,candidate,gpu3,70,64.8,58.5,0
Known variance band from crossover tests: about 4.4%.
Rule: do not promote if the candidate gain is inside variance without same-window or crossover evidence.""",
    },
    {
        "id": "customer-ticket-debug",
        "scenario": "a customer report with partial symptoms and unclear cause",
        "focus": "clarifying questions, hypothesis ranking, safe response, and escalation",
        "context": """Context:
Ticket:
"Since Friday the assistant is slower and sometimes repeats the same sentence. We changed nothing except enabling long context. It happens on invoice summaries."
Known facts:
- account beta-17 moved from profile q8-fast to q8-long at 09:20 Friday
- prompt tokens rose from 900 median to 11800 median
- decode tokens per second stayed near 120 on short prompts
- TTFT rose from 0.8s to 7.4s on long prompts
- no quality logs include the repeated-sentence example yet""",
    },
    {
        "id": "security-audit-snippet",
        "scenario": "a data-handling workflow with security and compliance risk",
        "focus": "scope, policy assumptions, audit evidence, and risk reduction",
        "context": """Context:
Workflow:
1. Support downloads a CSV from the billing admin.
2. CSV columns: email, company, last4_card, invoice_total, freeform_notes.
3. A local script sends rows to an LLM endpoint for classification.
4. Logs keep request bodies for 14 days for debugging.
Policy note: emails and freeform notes are personal data; last4_card is sensitive billing metadata.
Proposed change: hash email, redact notes, and keep request hashes instead of bodies.""",
    },
    {
        "id": "code-review-worker",
        "scenario": "a worker that batches writes, retries failures, and persists dead letters",
        "focus": "correctness, concurrency, durability, metrics, and tests",
        "context": """Context:
def flush(batch):
    for item in batch:
        try:
            db.write(item.key, item.value)
        except TimeoutError:
            retry_queue.append(item)
    ack(batch)

Known issue: if db.write succeeds but ack(batch) fails, the whole batch is replayed.
Metric gap: retry_queue length is exported, but duplicate write count is not.
Requirement: at-least-once is acceptable, but duplicate billing writes are not.""",
    },
    {
        "id": "capacity-sheet",
        "scenario": "four independent GPU replicas serving short single-session requests",
        "focus": "routing, queueing, saturation, memory limits, and failover",
        "context": """Context:
GPU inventory: 4 x Intel Arc Pro B70, 32GiB each.
Profile A: 125 tok/s decode, TTFT 0.55s, max_model_len 2048, one replica per GPU.
Profile B: 112 tok/s decode, TTFT 1.9s, max_model_len 32768, one replica per GPU.
Traffic: 12 requests/minute peak, p95 output 420 tokens, occasional 16K prompts.
Goal: preserve short-prompt speed while offering a safe long-context route.""",
    },
    {
        "id": "api-payload-webhook",
        "scenario": "a client library integrating pagination, retries, auth refresh, and webhooks",
        "focus": "error handling, idempotency, rate limits, example code, and observability",
        "context": """Context:
POST /imports returns {"job_id":"job_82","status":"queued"}.
GET /imports/job_82?page=2 returns {"items":[...],"next_page":3}.
Webhook payload: {"job_id":"job_82","event":"completed","signature":"sha256=..."}.
Rate limit headers: x-ratelimit-remaining=12, retry-after=3.
Failure reports: duplicate webhooks, expired OAuth tokens mid-pagination, and 429 retry storms.""",
    },
    {
        "id": "release-note-draft",
        "scenario": "a messy internal draft that needs a concise technical announcement",
        "focus": "structure, tone, factual precision, missing context, and final wording",
        "context": """Context:
Rough draft:
"we changed the serving thing to be faster. it should be around 120 tokens now maybe. dont use old config. long context should work but the first token can be slower. quality tests were fine. also no cache cheating."
Facts:
- strict fresh median is 124.98 tok/s on the short suite
- cached_tokens must be 0 for headline claims
- 32K service smoke passed, but expected decode is about 115 tok/s in that mode
- rollback is profile q8-stable-20260630""",
    },
    {
        "id": "test-failure-report",
        "scenario": "a flaky workflow where unit tests pass but production behavior regresses",
        "focus": "test gaps, deterministic reproduction, fixtures, and owner actions",
        "context": """Context:
Unit tests: 218 passed.
Integration test: skipped because TEST_WITH_XPU=0.
Production symptom: every 30-60 requests, first generated token is wrong, then output recovers.
Recent change: graph capture enabled for decode; prefill remains eager.
Canary failures:
expected: blue, green, orange, red
observed: blue, green, red, yellow
Hypothesis in ticket: eager state restore races captured decode replay.""",
    },
]


V6B_TASKS = [
    (
        "summarize-context",
        "Summarize the pasted context",
        "Separate known facts, interpretation, risks, and next actions.",
    ),
    (
        "diagnose-evidence",
        "Diagnose the issue from the evidence",
        "Rank hypotheses, identify missing data, and avoid overclaiming.",
    ),
    (
        "extract-decision-table",
        "Extract a decision table",
        "Include only fields that affect priority, risk, owner, or next step.",
    ),
    (
        "write-json",
        "Return compact JSON",
        "Use stable keys and concrete values; include uncertainty where relevant.",
    ),
    (
        "direct-answer",
        "Answer the user's question directly",
        "Start with the answer, then give short reasoning and caveats.",
    ),
    (
        "review-plan",
        "Review the proposed plan as a senior engineer",
        "Put blockers first, then fixes, validation, and residual risk.",
    ),
    (
        "write-code-or-query",
        "Write the command, query, or code needed for the scenario",
        "Keep it runnable and add a short explanation of how to validate it.",
    ),
    (
        "draft-response",
        "Draft the message or handoff that should be sent next",
        "Be accurate, specific, and action-oriented without overpromising.",
    ),
]


def build_context_prompts(
    *,
    variants_per_pair: int = 1,
    domains: list[dict[str, str]] | None = None,
    tasks: list[tuple[str, str, str]] | None = None,
    variant_guidance: list[tuple[str, str]] | None = None,
) -> list[dict[str, str]]:
    domains = domains or V6B_CONTEXT_DOMAINS
    tasks = tasks or V6B_TASKS
    variant_guidance = variant_guidance or V6_VARIANT_GUIDANCE
    if variants_per_pair < 1:
        raise ValueError("--variants-per-pair must be >= 1")
    if variants_per_pair > len(variant_guidance):
        raise ValueError(
            f"--variants-per-pair must be <= {len(variant_guidance)}"
        )
    prompts: list[dict[str, str]] = []
    for domain_index, domain in enumerate(domains):
        for task_index, (task_id, instruction, task_constraint) in enumerate(tasks):
            for variant_index in range(variants_per_pair):
                constraint = CONSTRAINTS[
                    (domain_index + task_index + variant_index)
                    % len(CONSTRAINTS)
                ]
                variant_id, guidance = variant_guidance[variant_index]
                suffix = "" if variants_per_pair == 1 else f"-{variant_id}"
                prompt_id = f"{domain['id']}-{task_id}{suffix}"
                prompt = (
                    f"{instruction} for {domain['scenario']}.\n\n"
                    f"{domain['context']}\n\n"
                    f"Focus on {domain['focus']}.\n"
                    f"{task_constraint}\n"
                    f"{constraint}\n"
                    f"{guidance}\n"
                    "Use only the pasted context plus clearly stated assumptions. "
                    "Do not say no context was provided, and do not refer to any "
                    "benchmark final-suite prompt."
                )
                prompts.append({
                    "id": prompt_id,
                    "family": domain["id"],
                    "task": task_id,
                    "variant": variant_id,
                    "prompt": prompt,
                })
    return prompts


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
        choices=("ops", "chat-v6", "chat-v6b"),
        help=(
            "Prompt-family preset. 'ops' preserves the existing v2-v5 "
            "engineering/business suite shape; 'chat-v6' emits broader "
            "non-final chat-style prompts for EAGLE/DFlash training; "
            "'chat-v6b' emits concrete pasted-context prompts to avoid "
            "no-context answers in summarization/extraction tasks."
        ),
    )
    parser.add_argument("--version", default="2026-07-04")
    args = parser.parse_args()
    if args.preset == "chat-v6b":
        prompts = build_context_prompts(
            variants_per_pair=args.variants_per_pair,
        )
    elif args.preset == "chat-v6":
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
