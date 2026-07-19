#!/usr/bin/env python3
"""One-time, CPU-only materializer for the DeepSeek spec-eval v1 packs.

The generated packs are deterministic review artifacts.  This script refuses
to overwrite them.  It deliberately builds heterogeneous, unique context
records instead of repeating padding phrases.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
QUALITY = ROOT / "experiments/deepseek-v4-flash-reap-xpu-b70/quality"
CONTRACT = QUALITY / "spec-eval-contract-v1.json"
OUTPUTS = {
    "A": QUALITY / "spec-eval-heldout-pack-a-v1.json",
    "B": QUALITY / "spec-eval-heldout-pack-b-v1.json",
}
PACK_SEEDS = {
    "A": 0x4A7D_91C3_02EF_B865,
    "B": 0xB63E_24A9_D107_5CF2,
}
SHORT_COUNTS = {"code": 12, "math_reasoning": 10, "mixed": 20, "tools_json_exact": 6}
PROMPT_BUCKETS = ((32, 128), (129, 512), (513, 900))
OUTPUT_BUCKETS = ((8, 48), (96, 192), (256, 512))
LONG_TARGETS = (2048, 4096)

CODE_TASKS = [
    "Repair a bounded asynchronous queue whose cancelled waiter can consume the next producer notification. Give a minimal Python patch, a deterministic interleaving test, and the invariant preserved by the fix.",
    "Implement a Rust parser for length-prefixed frames that rejects truncation and integer overflow without copying payload bytes. Include the function, error enum, and four edge-case tests.",
    "Diagnose a PostgreSQL query that double-counts sessions when time ranges overlap. Rewrite it using range operations, explain index selection, and show a counterexample for the original join.",
    "Write a Go token-bucket limiter that supports monotonic-clock refill, concurrent callers, and a live capacity change. Include tests for clock rollback and burst exhaustion.",
    "Refactor a TypeScript streaming JSON decoder so UTF-8 code points split across chunks are preserved. Supply the core code and tests for invalid tails and backpressure.",
    "Design a C++ ring buffer with sequence counters that distinguishes empty from wrapped slots. State memory-order requirements and give a two-thread litmus test.",
    "Fix a Bash deployment script that loses the original exit status inside an EXIT trap. Preserve logs, temporary-directory cleanup, and signal behavior; include a shellcheck-clean example.",
    "Implement a Python topological sorter that reports one concrete directed cycle while keeping stable order for independent nodes. Analyze complexity and test duplicate edges.",
    "Migrate a protobuf field from a scalar to a repeated representation without breaking old readers. Show compatible schemas, adapter logic, and a staged rollout test matrix.",
    "Debug an LRU cache where replacing an existing key corrupts the linked list after an eviction. Provide pseudocode for each mutation and property-based invariants.",
    "Implement a Java retry scheduler with decorrelated jitter, a total deadline, and cancellation propagation. Demonstrate how it avoids synchronized retry storms.",
    "Review a WebAssembly host-call boundary that trusts guest-provided pointer arithmetic. Produce a safe bounds-check routine and adversarial tests near the address-space limit.",
]

MATH_TASKS = [
    "A reservoir starts with 730 liters. Each hour 7/40 evaporates, then 96 liters arrive. Derive a closed form, find the first hour above 500 liters after hour 8, and verify by recurrence.",
    "For integers n, solve 17n congruent to 43 modulo 221. Show the gcd test, give the least nonnegative solution, and verify it without decimal approximations.",
    "A biased coin has unknown head probability with Beta(3,5) prior. After 11 heads and 7 tails, derive the posterior and the predictive probability of exactly two heads in the next three flips.",
    "Find the minimum-cost path in a four-stage network with edge tolls that depend on arrival parity. Define the expanded state graph and prove why ordinary node-only Dijkstra is insufficient.",
    "A polynomial has integer coefficients, p(0)=6, p(1)=10, p(2)=24, and degree at most three. Recover p(7), showing finite differences and a direct substitution check.",
    "Determine the number of onto functions from a seven-element labeled set to a four-element labeled set. Use inclusion-exclusion and independently check via Stirling numbers.",
    "A triangle has side lengths 13, 14, and 15. Compute its inradius and distance between incenter and circumcenter, retaining exact radicals until the end.",
    "Analyze the recurrence a(n)=4a(n-1)-4a(n-2)+3^n with a(0)=2 and a(1)=5. Derive the exact form and verify the first three terms.",
    "Three sensors fail independently with probabilities 0.07, 0.12, and 0.20, but the alarm reports failure with sensitivity 0.94 and false-positive rate 0.03. Compute the posterior that at least one sensor failed.",
    "Prove or disprove: every connected graph with distinct edge weights has a unique second-lightest spanning tree. If false, provide the smallest explicit counterexample and enumerate its tree weights.",
]

MIXED_TASKS = [
    "Prepare a reversible cutover plan for moving a busy reservation service from local timestamps to UTC while clients remain on mixed versions. Include invariants, telemetry, rollback triggers, and one worked daylight-saving example.",
    "Compare two archival reports that disagree about a bridge inspection. Reconcile dates, distinguish observation from inference, and draft three questions whose answers would resolve the conflict.",
    "Explain to a senior engineer why a faster median can coexist with worse user experience. Use a numerical latency distribution, queueing effects, and a concrete dashboard design.",
    "Design an experiment to test whether a new search ranking improves rare-query satisfaction without leaking query labels into routing. Specify sampling, blindness, metrics, and stopping rules.",
    "Turn a vague request for 'exactly once delivery' into a precise service contract. Cover idempotency keys, retention, retries, partitions, and what the system cannot promise.",
    "Write a concise incident analysis for a certificate rotation that succeeded on most nodes but stranded long-lived connections. Separate cause, trigger, contributing factors, and preventive actions.",
    "Evaluate a proposal to compress scientific telemetry before anomaly detection. Discuss lossy transforms, calibration drift, reproducible validation, and a decision threshold.",
    "Create a procurement comparison for two storage systems where one has lower purchase cost and the other lower recovery time. Include a five-year model and uncertainty analysis.",
    "Draft a field protocol for measuring stream depth during a storm when instruments may drift. Include redundant observations, safe abort conditions, and later data correction.",
    "Explain how to distinguish correlation, temporal precedence, and causation in a study linking night shifts to medication errors. Propose a stronger follow-up design.",
    "Plan a multilingual documentation migration that preserves stable anchors and old inbound links. Include redirects, translation ownership, search indexing, and rollback.",
    "Assess an authentication flow that uses email magic links on shared devices. Model threats, usability tradeoffs, session binding, and recovery without assuming trusted mail clients.",
    "Summarize a fictional city budget dispute for a neutral public briefing. Separate agreed figures, contested assumptions, distributional effects, and unknowns.",
    "Design a museum inventory reconciliation after barcode labels were swapped on a subset of crates. Use chain of custody, probabilistic matches, and a no-destructive-testing rule.",
    "Construct a test plan for a navigation system in tunnels where GPS disappears intermittently. Cover simulation, physical trials, safety boundaries, and acceptance criteria.",
    "Advise a research team on publishing a negative replication result. Address statistical power, materials release, respectful comparison, and claims the data do not support.",
    "Develop a maintenance schedule for pumps with unequal failure costs and sparse inspection data. Explain the model, sensitivity checks, and manual override policy.",
    "Analyze a contract clause whose deadline is stated in both business days and calendar dates that disagree. Present interpretations, operational risk, and a clarification draft.",
    "Propose a privacy-preserving method to estimate transit crowding from device counts. Cover aggregation, bias, retention, and an audit that catches re-identification risk.",
    "Create a handoff for a partially completed data migration. Identify authoritative state, immutable evidence, restart procedure, and checks that prevent replaying completed batches.",
]

JSON_TASKS = [
    "Return only one JSON object describing a three-step failover drill. Required keys are steps, abort_conditions, and owner. Each step must have an integer order and a boolean reversible field.",
    "Extract the supplied shipment facts into strict JSON only. Use keys shipment_id, stops, total_mass_kg, and anomalies; preserve null rather than inventing missing values.",
    "Return strict JSON only for a dependency upgrade decision with keys approve, reasons, required_tests, and rollback_version. reasons and required_tests must be arrays of strings.",
    "Normalize the described temperature readings into JSON only with keys unit, samples, rejected_indices, and mean_of_valid. Do not include markdown or explanatory text.",
    "Produce exactly one JSON object for an access review. Keys: subject, keep_roles, remove_roles, expires_at, evidence. Sort both role arrays lexicographically.",
    "Convert the incident timeline into strict JSON only with keys events, first_detection_utc, mitigation_utc, and unresolved. Every event needs ts, actor, and action.",
]

# Pack B uses disjoint task statements, not paraphrases or case variants of A.
B_CODE_TASKS = [
    "Implement a Kotlin merge iterator over sorted, nullable database cursors. It must close exhausted cursors, preserve duplicate keys, and surface the first I/O error; include resource-leak tests.",
    "Repair a Ruby interval map whose split operation drops a boundary value when two half-open ranges touch. Give the corrected algorithm and randomized model-based tests.",
    "Write a Zig decoder for a binary header with mixed-endian fields and a trailing CRC32. Reject reserved bits before allocation and demonstrate five malformed inputs.",
    "Design a Lua coroutine pool that cannot resume a task after its deadline. Include ownership rules, a fake-clock test harness, and handling for nested cancellation.",
    "Optimize a SQLite recursive query that walks package dependencies while reporting cycles and shortest depth. Provide schema, indexes, query, and an explain-plan interpretation.",
    "Implement a C# incremental CSV reader that handles quoted newlines, doubled quotes, and a byte-order mark across buffer boundaries. Include fuzz properties.",
    "Fix an Erlang supervision tree where a transient child restart can exceed a global retry budget. Show the revised topology and failure-injection tests.",
    "Write a Swift actor that batches telemetry uploads by size or deadline without losing the final batch during shutdown. State reentrancy assumptions and tests.",
    "Review a C memory-mapped-file scanner for SIGBUS risk after concurrent truncation. Propose a safe API boundary, recovery behavior, and a reproducible regression test.",
    "Implement a Haskell diff for ordered trees that emits a minimal stable edit script under a stated cost model. Prove termination and test repeated labels.",
    "Repair a Node.js HTTP proxy that forwards hop-by-hop headers and mishandles early client disconnects. Supply the relevant code and socket-lifecycle tests.",
    "Design a Scala checkpoint writer using atomic rename and directory fsync. Explain crash states before and after each syscall and give a fault-injection matrix.",
]

B_MATH_TASKS = [
    "A worker alternates two transformations: x maps to (5x+7)/8, then to (3x+11)/5. Starting at 64, derive the value after twelve full rounds and verify with a matrix recurrence.",
    "Find every integer solution to 9x+14y=503 subject to x and y nonnegative. Derive the parameterization and minimize 4x+7y over the feasible set.",
    "A diagnostic test is applied twice with conditionally independent outcomes given disease status. With prevalence 0.015, sensitivity 0.91, and specificity 0.96, compute the posterior after one positive and one negative.",
    "Count circular seatings of five adults and four children when no three children are consecutive, identifying rotations but not reflections. Show an inclusion-exclusion or gap argument.",
    "Diagonalize the recurrence vector u(n+1)=[[2,1],[1,2]]u(n) for u(0)=(4,1), then find the least n for which both components exceed 100000.",
    "A box contains red, blue, and green tokens in ratio 3:4:5. Sampling four without replacement gives exactly two blue with probability 33/91. Determine the smallest possible box size or prove none exists.",
    "Compute the area enclosed by y=|x^2-4x+3| and y=x+3, giving exact intersection points and integrating piecewise.",
    "A 6-by-6 grid path moves only right or up and must avoid two specified interior points. Count valid paths through one marked edge using a decomposition check.",
    "Determine whether 2^341 is congruent to 2 modulo 341 without invoking a calculator. Factor the modulus, reason in each component, and reconcile the result with primality tests.",
    "Minimize the maximum absolute error when approximating the three values 1, 7, and 19 by a line a+bn at n=0,1,2. Derive the equioscillation solution and verify optimality.",
]

B_MIXED_TASKS = [
    "Plan the recovery of a wet photographic archive where catalog cards and negatives were separated. Prioritize safety, provenance, reversible handling, and uncertainty labels.",
    "Assess a hospital proposal to predict missed appointments from administrative records. Cover fairness, intervention harms, prospective validation, and an appeal mechanism.",
    "Create a decision memo for replacing diesel backup generators with batteries at a remote clinic. Model outage duration, maintenance, fuel logistics, and phased fallback.",
    "Explain how a census boundary change can create an apparent population jump. Give a reconciliation method, a numerical illustration, and publication caveats.",
    "Draft a protocol for merging two customer-support taxonomies without invalidating historical trends. Include dual coding, mapping confidence, and sunset criteria.",
    "Investigate why a greenhouse trial improved yield but reduced flavor scores. Separate measurement artifacts, treatment interactions, and a confirmatory experiment.",
    "Design a public warning system for a river whose gauges report at unequal delays. Specify uncertainty, message escalation, accessibility, and false-alarm review.",
    "Write a neutral comparison of leasing versus buying specialized laboratory equipment under volatile demand. Include option value, downtime, training, and exit costs.",
    "Prepare an oral-history consent process that allows narrators to embargo selected passages. Address versioning, withdrawal, derivative works, and researcher access.",
    "Analyze a school transport schedule that is efficient on average but routinely strands one rural route. Propose metrics and constraints that expose the inequity.",
    "Develop a verification plan for digitized land records when scans are clear but handwritten indexes contain abbreviations. Combine double entry, sampling, and escalation.",
    "Assess a newsroom policy that automatically translates breaking alerts. Model speed versus accuracy, human review thresholds, correction propagation, and source preservation.",
    "Create a conservation plan for an urban pond affected by road salt and invasive plants. Distinguish reversible trials from long-term interventions and define monitoring.",
    "Explain to finance and engineering why cloud egress estimates disagree. Reconcile billing units, retries, replication, compression, and observation windows.",
    "Design a blinded taste study comparing packaging changes when participants can sometimes hear the container open. Identify leakage channels and mitigation.",
    "Write a handover for a legal discovery export interrupted midway. Preserve chain of custody, deduplication state, resumability, and independent completeness checks.",
    "Evaluate a plan to infer building occupancy from electricity demand. Address confounding, calibration seasons, privacy, and a safe operational use boundary.",
    "Construct a tabletop exercise for a regional payment outage involving banks with different settlement windows. Include injects, decision logs, and recovery evidence.",
    "Advise a botanical survey on combining observations from experts and volunteers. Cover observer bias, duplicate sightings, rare-species secrecy, and reproducible scoring.",
    "Draft a postmortem for a map update that routed trucks under a low bridge. Separate data lineage, validation gaps, release controls, and measurable follow-ups.",
]

B_JSON_TASKS = [
    "Return strict JSON only for a laboratory sample transfer. Keys must be transfer_id, source, destination, containers, and exceptions; each container needs id and seal_intact.",
    "Encode the described election audit batches as one JSON object only with keys batches, ballots_checked, discrepancies, and escalate. All counts must be integers.",
    "Produce JSON only for a feature rollback using keys feature, decision, signals, actions, and next_review_utc. decision must be either rollback or retain.",
    "Extract the supplied meeting decisions into strict JSON only. Required keys: decisions, deferred, attendees_missing, and recording_hash; do not infer absent owners.",
    "Return exactly one JSON object for a water-quality alert with keys station, observations, severity, notify, and expires_utc. Preserve observation units verbatim.",
    "Normalize the described book loans into JSON only with keys patron, items, overdue_count, and fees_cents. Sort items by due_date then item_id.",
]

A_JSON_FACTS = [
    "The drill owner is Meera. Step 1 isolates the west link and is reversible; step 2 promotes replica cedar and is reversible; step 3 retires stale leases and is not reversible. Abort if replication lag exceeds 19 seconds or two health probes fail.",
    "Shipment SH-804 leaves Aster Bay, stops at Rowan Summit then Cedar Quay, and ends at Northpass. Crates weigh 410, 275, and 95 kg. The second seal is scratched; arrival temperature is not recorded.",
    "Version 6.4.2 fixes CVE-77 but changes the wire schema. Approve only after downgrade, mixed-version, and corrupted-frame tests. The rollback version is 6.3.9; two pilot nodes showed no errors.",
    "Readings are 18.4 C, 18.7 C, -91.0 C, 18.5 C, and 18.8 C. Index 2 is a disconnected-probe sentinel and must be rejected; retain Celsius.",
    "Subject is oona@example.test. Keep roles audit_reader and billing_viewer; remove legacy_admin and temp_export. Access expires 2026-08-03T16:00:00Z; evidence ticket is AR-551.",
    "At 02:14Z Inez detected checksum failures. At 02:19Z Jovan disabled writer-3. At 02:27Z Kira shifted traffic east. Mitigation completed at 02:31Z; delayed invoices remain unresolved.",
]

B_JSON_FACTS = [
    "Transfer TR-992 moves from freezer F2 to vault V7. Containers C14 and C19 have intact seals; C22 has a broken seal. The exception note says C22 requires quarantine.",
    "Batch north-3 checked 420 ballots with 1 discrepancy; batch west-8 checked 380 with 0; batch quay-2 checked 205 with 4. Escalate because a batch exceeded two discrepancies.",
    "Feature compact_routes is under review. Signals are error_rate=0.031 and stale_reads=17. Decision is rollback; actions are disable writer and restore index. Next review is 2026-07-22T14:30:00Z.",
    "The meeting approved rotating keys and deferred deleting the old archive. Farah and Lucan were absent. No owner was assigned for deletion. Recording hash is 9b77c118.",
    "Station willow-4 observed chloride 318 mg/L and conductivity 1410 uS/cm. Severity is high, notify is true, and the alert expires 2026-07-20T06:00:00Z.",
    "Patron P-71 has B14 due 2026-07-21, B09 due 2026-07-21, and B33 due 2026-07-18. B33 is overdue. Fees total 425 cents.",
]

PEOPLE = "Amina Boran Celeste Dario Elin Farah Gita Haruto Inez Jovan Kira Lucan Meera Niko Oona Pavel Rina Soren Talia Uzair Veda Wren Ximena Yara Zubin".split()
PLACES = "Aster Bay Cedar Quay Dunlin Eastmere Fox Hollow Garnet Inlet Juniper Knoll Larch Mesa Northpass Oriel Port Rowan Summit Tern Vale Willow Yard Zephyr".split()
OBJECTS = "anvil beacon cistern diode envelope flywheel gauge hatch insulator journal kiln ledger manifold nozzle optic pulley relay spindle turbine valve".split()
VERBS = "audited balanced catalogued diverted examined flagged guarded indexed logged measured negotiated observed recalibrated sealed transferred validated".split()
QUALIFIERS = "after sunrise before dispatch during drizzle near the eastern boundary under manual supervision without network access beside the reserve pump following a checksum mismatch prior to the night shift while the secondary clock was isolated".split(" ")


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def tokenish_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+|[^\w\s]", text))


def diversity(text: str, width: int = 8) -> dict[str, float | int]:
    atoms = re.findall(r"\w+|[^\w\s]", text.lower())
    shingles = [tuple(atoms[i : i + width]) for i in range(max(0, len(atoms) - width + 1))]
    unique = len(set(shingles))
    return {
        "tokenish_count": len(atoms),
        "shingle_width": width,
        "shingle_count": len(shingles),
        "unique_shingle_count": unique,
        "unique_shingle_fraction": 1.0 if not shingles else unique / len(shingles),
    }


def fact_line(rng: random.Random, serial: int, style: int) -> str:
    person = rng.choice(PEOPLE)
    place = f"{rng.choice(PLACES)} {rng.choice(PLACES)}"
    obj = rng.choice(OBJECTS)
    verb = rng.choice(VERBS)
    day = 3 + (serial * 7) % 25
    hour = (serial * 11 + rng.randrange(7)) % 24
    minute = (serial * 17 + rng.randrange(13)) % 60
    amount = 41 + ((serial * 137 + rng.randrange(97)) % 8800)
    checksum = hashlib.sha256(f"{serial}:{person}:{place}:{amount}".encode()).hexdigest()[:10]
    variants = (
        f"On June {day:02d} at {hour:02d}:{minute:02d}, {person} {verb} the {obj} at {place}; the signed count was {amount}, and receipt {checksum} remained legible.",
        f"Record {serial:03d} pairs {place} with {person}: pressure {amount % 173 + 19} kPa, batch {checksum}, and a note that the {obj} was {verb} only after the backup clock agreed.",
        f"The {obj} entry from {place} lists lot {checksum}, quantity {amount}, reviewer {person}, and status '{verb}'; its margin corrects day {day:02d}, not the measured value.",
        f"{person}'s memorandum distinguishes a visual check at {place} ({hour:02d}:{minute:02d}) from the later {obj} test; archive key {checksum} ties both to parcel {amount % 997}.",
        f"Station {place} reported that the {obj} changed from {amount % 89 + 10} to {amount % 131 + 30} units. {person} then {verb} sample {checksum} on the {day:02d}th.",
        f"A cross-check by {person} found ledger cell {serial * 13 + 5}, marker {checksum}, and {amount % 311 + 17} sealed items at {place}; the {obj} was not moved.",
        f"Dispatch note {checksum}: route through {place}, ask for {person}, verify {amount % 71 + 20} fasteners on the {obj}, then compare the {day:02d} June seal with the blue register.",
        f"Unlike the noon summary, the {hour:02d}:{minute:02d} worksheet says {person} {verb} {amount % 503 + 90} grams beside the {obj} at {place}; checksum {checksum} is authoritative.",
    )
    return variants[style % len(variants)]


def dossier(rng: random.Random, desired_tokenish: int, heading: str) -> str:
    lines = [heading]
    serial = rng.randrange(1000, 9000)
    while tokenish_count("\n".join(lines)) < desired_tokenish:
        lines.append(fact_line(rng, serial, len(lines) - 1))
        serial += rng.randrange(3, 19)
    return "\n".join(lines)


def fit_short(base: str, bucket: tuple[int, int], rng: random.Random, tag: str) -> str:
    low, high = bucket
    current = tokenish_count(base)
    if current < low:
        target = low + (high - low) * 2 // 5
        base += "\n\nCase dossier (all entries are independent):\n" + dossier(rng, target - current, tag)
    if tokenish_count(base) > high:
        raise ValueError(f"short prompt exceeded tokenish bucket {bucket}: {tokenish_count(base)}")
    return base


def plant_long_evidence(
    kind: str, index: int, pack: str, context: str
) -> tuple[str, str, dict[str, Any]]:
    lines = context.splitlines()
    key = hashlib.sha256(f"{pack}:{index}:long-evidence".encode()).hexdigest()[:12]
    a = 113 + index * 17
    b = 271 + index * 19
    c = 419 + index * 23
    positions = (max(2, len(lines) // 9), len(lines) // 2, max(3, len(lines) - 4))
    if kind == "prose":
        lines.insert(positions[0], f"Authoritative key {key} says the Juniper transfer closed at 09:42 on July 11 under witness Rina.")
        lines.insert(positions[2], f"A later copy carrying the same authoritative key {key} says that transfer closed at 08:17 on July 10 under witness Rina; both cannot be chronological originals.")
        instruction = f"Write a coherent account separating recorded facts from inference. Cite six archive keys, and identify the contradiction involving authoritative key {key}."
        oracle = {"contradiction_key": key, "times": ["2026-07-11 09:42", "2026-07-10 08:17"]}
    elif kind == "code":
        lines.insert(positions[0], f"Schema rule {key}: a receipt key may appear many times, but its quantity and reviewer must remain identical across all appearances.")
        lines.insert(positions[2], f"Validation case {key}: the first conflicting update must report both source line numbers without discarding either raw record.")
        instruction = f"Design typed data structures and a streaming validator for schema rule {key}. Include deterministic diagnostics, complexity, and tests for a far-separated conflict."
        oracle = {"schema_key": key, "required_diagnostic_fields": ["first_line", "conflicting_line"]}
    elif kind == "math_reasoning":
        lines.insert(positions[0], f"Calculation register {key} declares three independent counts: alpha={a}, beta={b}, gamma={c}.")
        lines.insert(positions[2], f"Check rule {key}: weighted checksum equals (3*alpha + 5*beta + 7*gamma) modulo 997; no other quantities belong in this calculation.")
        instruction = f"For calculation register {key}, report the sum, median, and weighted checksum. Show substitutions and one independent arithmetic check."
        oracle = {"register": key, "sum": a + b + c, "median": b, "weighted_checksum_mod_997": (3 * a + 5 * b + 7 * c) % 997}
    elif kind == "extraction":
        lines.insert(positions[0], f"Authoritative extraction {key}-A: time=04:26, person=Veda, quantity={a}, checksum={key[:8]}aa.")
        lines.insert(positions[2], f"Authoritative extraction {key}-B: time=21:09, person=Haruto, quantity={c}, checksum={key[:8]}bb.")
        instruction = f"Return a compact table containing only authoritative extractions {key}-A and {key}-B with exact time, person, quantity, and checksum. Do not substitute nearby records."
        oracle = {"extraction_key": key, "rows": [{"time": "04:26", "person": "Veda", "quantity": a, "checksum": f"{key[:8]}aa"}, {"time": "21:09", "person": "Haruto", "quantity": c, "checksum": f"{key[:8]}bb"}]}
    else:
        lines.insert(positions[0], f"Chain origin {key}: Amina passed token {key[:6]}-oak to the custodian named only in the middle link.")
        lines.insert(positions[1], f"Chain middle {key}: custodian Soren exchanged {key[:6]}-oak for {key[:6]}-reed and recorded destination Willow Yard.")
        lines.insert(positions[2], f"Chain terminus {key}: Willow Yard received {key[:6]}-reed from Soren at 23:18; similar beacon records with other keys are decoys.")
        instruction = f"Recover the three-link chain for key {key}. Give origin person/token, middle custodian/new token/destination, and terminus time; reject noun-sharing decoys."
        oracle = {"chain_key": key, "origin": ["Amina", f"{key[:6]}-oak"], "middle": ["Soren", f"{key[:6]}-reed", "Willow Yard"], "terminus_time": "23:18"}
    return "\n".join(lines), instruction, oracle


def make_long(pack: str, index: int, rng: random.Random) -> dict[str, Any]:
    kinds = ("prose", "code", "math_reasoning", "extraction", "adversarial_low_locality")
    kind = kinds[(index * 3 + (0 if pack == "A" else 2)) % len(kinds)]
    target = LONG_TARGETS[index % 2]
    # The exact frozen tokenizer count is deliberately deferred to endpoint
    # usage.  Tokenish targets leave room for chat-template tokens.
    body_target = target - 90
    title = f"Independent archive for review {index + 1}; entries are intentionally nonchronological and nonrepetitive."
    context, instruction, oracle = plant_long_evidence(
        kind, index, pack, dossier(rng, body_target, title)
    )
    prompt = (
        f"Read the following one-time record set for review folio {37 + index * 11}. "
        "Do not use facts from any other request.\n\n"
        + context
        + "\n\n"
        + instruction
    )
    return {
        "local_id": f"{pack.lower()}-long-{index + 1:02d}",
        "category": kind,
        "prompt_token_target": target,
        "prompt_token_bucket": [target - 256, target + 256],
        "output_token_bucket": [96, 192] if target == 2048 else [256, 512],
        "max_tokens": 160 if target == 2048 else 320,
        "long_context": True,
        "prompt": prompt,
        "construction_tokenish_count": tokenish_count(prompt),
        "diversity": diversity(context),
        "client_oracle": oracle,
    }


def make_pack(pack: str) -> dict[str, Any]:
    rng = random.Random(PACK_SEEDS[pack])
    requests: list[dict[str, Any]] = []
    ordinal = 0
    task_groups = (
        (("code", CODE_TASKS), ("math_reasoning", MATH_TASKS), ("mixed", MIXED_TASKS), ("tools_json_exact", JSON_TASKS))
        if pack == "A"
        else (("code", B_CODE_TASKS), ("math_reasoning", B_MATH_TASKS), ("mixed", B_MIXED_TASKS), ("tools_json_exact", B_JSON_TASKS))
    )
    for category, tasks in task_groups:
        if len(tasks) != SHORT_COUNTS[category]:
            raise AssertionError(f"bad task count for {category}")
        for task_index, task in enumerate(tasks):
            bucket = PROMPT_BUCKETS[ordinal % len(PROMPT_BUCKETS)]
            output_bucket = OUTPUT_BUCKETS[(ordinal + (1 if pack == "B" else 0)) % len(OUTPUT_BUCKETS)]
            context_tag = f"Supporting records for case {task_index + 1}; use only facts relevant to the stated task."
            if category == "tools_json_exact":
                case_detail = (A_JSON_FACTS if pack == "A" else B_JSON_FACTS)[task_index]
            else:
                case_detail = fact_line(rng, 10000 + ordinal * 23, task_index)
            prompt = fit_short(
                task + "\n\nA case-specific observation follows; incorporate it only when relevant:\n" + case_detail,
                bucket,
                rng,
                context_tag,
            )
            requests.append(
                {
                    "local_id": f"{pack.lower()}-short-{ordinal + 1:02d}",
                    "category": category,
                    "prompt_token_bucket": list(bucket),
                    "output_token_bucket": list(output_bucket),
                    "max_tokens": (output_bucket[0] + output_bucket[1]) // 2,
                    "long_context": False,
                    "prompt": prompt,
                    "construction_tokenish_count": tokenish_count(prompt),
                }
            )
            ordinal += 1
    requests.extend(make_long(pack, index, rng) for index in range(16))
    prompt_hashes = [hashlib.sha256(row["prompt"].encode("utf-8")).hexdigest() for row in requests]
    if len(set(prompt_hashes)) != len(prompt_hashes):
        raise AssertionError("duplicate prompts")
    long_lines = [
        line
        for row in requests
        if row["long_context"]
        for line in row["prompt"].splitlines()
        if line.strip()
    ]
    if max(Counter(long_lines).values()) != 1:
        raise AssertionError("long-context line repeated")
    minimum_diversity = min(
        row["diversity"]["unique_shingle_fraction"]
        for row in requests
        if row["long_context"]
    )
    payload: dict[str, Any] = {
        "schema_version": 1,
        "suite_id": f"deepseek-v4-flash-b70-spec-eval-heldout-pack-{pack.lower()}-v1",
        "version": 1,
        "pack": pack,
        "classification": "frozen_heldout_speculation_evaluation",
        "contract_id": "deepseek-v4-flash-b70-spec-eval-v1",
        "public_continuity_suite_distinct": True,
        "labels_must_not_be_sent_to_server": True,
        "request_count": len(requests),
        "short_request_count": 48,
        "long_context_request_count": 16,
        "short_category_counts": SHORT_COUNTS,
        "construction": {
            "generator": "build-frozen-spec-eval-packs-v1.py",
            "generator_version": 1,
            "deterministic_seed_sha256": hashlib.sha256(str(PACK_SEEDS[pack]).encode()).hexdigest(),
            "long_context_exact_line_repetitions": 0,
            "long_context_minimum_unique_8gram_fraction": minimum_diversity,
            "token_count_note": "construction_tokenish_count is a CPU-only structural estimate; the evaluator must gate on endpoint usage.prompt_tokens",
        },
        "requests": requests,
    }
    payload["frozen_requests_sha256"] = canonical_sha(requests)
    return payload


def validate_contract() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    workloads = contract["workloads"]
    if workloads["short_normal_requests_per_pack"] != 48 or workloads["long_context_requests_per_pack"] != 16:
        raise SystemExit("contract workload shape changed; refusing v1 materialization")
    if workloads["short_normal_mix"] != SHORT_COUNTS:
        raise SystemExit("contract category mix changed; refusing v1 materialization")


def main() -> int:
    validate_contract()
    pending = [path for path in OUTPUTS.values() if path.exists()]
    if pending:
        raise SystemExit(f"refusing to overwrite frozen packs: {[str(path) for path in pending]}")
    payloads = {pack: make_pack(pack) for pack in OUTPUTS}
    if set(row["prompt"] for row in payloads["A"]["requests"]) & set(row["prompt"] for row in payloads["B"]["requests"]):
        raise SystemExit("pack A/B prompt overlap")
    for pack, path in OUTPUTS.items():
        with path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(payloads[pack], indent=2, ensure_ascii=False, sort_keys=True) + "\n")
        path.chmod(0o444)
        print(f"{path} {hashlib.sha256(path.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
